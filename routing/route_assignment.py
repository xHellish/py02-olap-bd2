"""
route_assignment.py — Enrutamiento de entregas para repartidores
Proyecto 2 OLAP — Restaurantes Guatemala

Algoritmo: vecino más cercano (nearest-neighbor heuristic) sobre los pedidos
pendientes de cada repartidor, usando distancias del grafo de zonas en Neo4J
(pre-calculadas con Dijkstra vía GDS).

Uso:
    python routing/route_assignment.py

Variables de entorno opcionales:
    NEO4J_URI      (default: bolt://localhost:7687)
    NEO4J_USER     (default: neo4j)
    NEO4J_PASSWORD (default: neo4j123)
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any

# ─── Configuración ────────────────────────────────────────────────────────────

NEO4J_URI  = os.environ.get("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER",     "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASSWORD", "neo4j123")


# ─── Modelos ─────────────────────────────────────────────────────────────────

@dataclass
class DeliveryOrder:
    order_id: int
    dest_zone: str
    dest_lat: float
    dest_lon: float
    customer: str
    total: float
    distance_km: float = 0.0


@dataclass
class Courier:
    courier_id: int
    name: str
    vehicle: str
    base_zone: str
    base_lat: float
    base_lon: float
    route: list[DeliveryOrder] = field(default_factory=list)
    total_distance_km: float = 0.0


# ─── Utilidades ──────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia euclidiana aproximada en km (Haversine)."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi     = math.radians(lat2 - lat1)
    dlambda  = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── Consultas Neo4J ──────────────────────────────────────────────────────────

def get_couriers(driver) -> list[Courier]:
    """Lee todos los repartidores con su zona base y coordenadas."""
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Courier)
            OPTIONAL MATCH (l:Location {zone: c.base_zone})
            RETURN c.id       AS courier_id,
                   c.name     AS name,
                   c.vehicle  AS vehicle,
                   c.base_zone AS base_zone,
                   COALESCE(l.lat, 14.60) AS lat,
                   COALESCE(l.lon, -90.51) AS lon
            ORDER BY c.id
        """)
        return [
            Courier(
                courier_id=r["courier_id"],
                name=r["name"],
                vehicle=r["vehicle"],
                base_zone=r["base_zone"],
                base_lat=r["lat"],
                base_lon=r["lon"],
            )
            for r in result
        ]


def get_pending_deliveries(driver) -> list[DeliveryOrder]:
    """Lee pedidos con entrega pendiente o en camino."""
    with driver.session() as session:
        result = session.run("""
            MATCH (o:Order)-[:DELIVERED_TO]->(l:Location)
            WHERE o.status IN ['pending', 'preparing', 'delivering']
            MATCH (u:User)-[:PLACED]->(o)
            RETURN o.id       AS order_id,
                   l.zone     AS dest_zone,
                   l.lat      AS dest_lat,
                   l.lon      AS dest_lon,
                   u.name     AS customer,
                   o.total    AS total
            ORDER BY o.id
            LIMIT 60
        """)
        return [
            DeliveryOrder(
                order_id=r["order_id"],
                dest_zone=r["dest_zone"],
                dest_lat=r["dest_lat"],
                dest_lon=r["dest_lon"],
                customer=r["customer"],
                total=r["total"],
            )
            for r in result
        ]


def get_shortest_path_km(driver, zone_from: str, zone_to: str) -> float:
    """
    Usa Dijkstra de GDS para obtener la distancia más corta entre dos zonas.
    Crea y elimina la proyección en memoria en cada llamada (para simplicidad).
    Si GDS falla, devuelve la distancia Haversine como fallback.
    """
    if zone_from == zone_to:
        return 0.0

    with driver.session() as session:
        try:
            # Proyección en memoria
            proj_name = f"routing_{zone_from}_{zone_to}"
            session.run(f"""
                CALL gds.graph.project.cypher(
                    '{proj_name}',
                    'MATCH (l:Location) RETURN id(l) AS id',
                    'MATCH (l1:Location)-[r:ROUTE]->(l2:Location)
                     RETURN id(l1) AS source, id(l2) AS target,
                            r.distance_km AS distance_km'
                )
            """)

            result = session.run(f"""
                MATCH (start:Location {{zone: $from_zone}}),
                      (end:Location   {{zone: $to_zone}})
                CALL gds.shortestPath.dijkstra.stream('{proj_name}', {{
                    sourceNode: id(start),
                    targetNodes: [id(end)],
                    relationshipWeightProperty: 'distance_km'
                }})
                YIELD totalCost
                RETURN totalCost
            """, from_zone=zone_from, to_zone=zone_to)

            record = result.single()
            dist = float(record["totalCost"]) if record else 999.0

            session.run(f"CALL gds.graph.drop('{proj_name}', false)")
            return dist

        except Exception:
            # Fallback: distancia directa entre coordenadas de las zonas
            res = session.run("""
                MATCH (l1:Location {zone: $from_zone}),
                      (l2:Location {zone: $to_zone})
                RETURN l1.lat AS lat1, l1.lon AS lon1,
                       l2.lat AS lat2, l2.lon AS lon2
            """, from_zone=zone_from, to_zone=zone_to).single()
            if res:
                return haversine_km(res["lat1"], res["lon1"], res["lat2"], res["lon2"])
            return 999.0


# ─── Algoritmo de enrutamiento ────────────────────────────────────────────────

def nearest_neighbor_assign(
    couriers: list[Courier],
    deliveries: list[DeliveryOrder],
    dist_fn,
) -> list[Courier]:
    """
    Asigna pedidos a repartidores usando heurística del vecino más cercano:
    1. Reparte equitativamente entre couriers (máx deliveries/couriers pedidos cada uno).
    2. Para cada courier, ordena los pedidos por proximidad acumulada (greedy).
    """
    if not couriers or not deliveries:
        return couriers

    unassigned = list(deliveries)
    max_per_courier = math.ceil(len(unassigned) / len(couriers))

    for courier in couriers:
        cur_lat, cur_lon = courier.base_lat, courier.base_lon
        cur_zone = courier.base_zone

        while unassigned and len(courier.route) < max_per_courier:
            # Vecino más cercano desde la posición actual
            best_idx = min(
                range(len(unassigned)),
                key=lambda i: haversine_km(
                    cur_lat, cur_lon,
                    unassigned[i].dest_lat, unassigned[i].dest_lon
                )
            )
            next_order = unassigned.pop(best_idx)
            leg_dist = dist_fn(cur_zone, next_order.dest_zone)
            next_order.distance_km = leg_dist
            courier.route.append(next_order)
            courier.total_distance_km += leg_dist
            cur_lat  = next_order.dest_lat
            cur_lon  = next_order.dest_lon
            cur_zone = next_order.dest_zone

    return couriers


# ─── Salida ───────────────────────────────────────────────────────────────────

def print_routes(couriers: list[Courier]) -> None:
    print("\n" + "=" * 70)
    print("ASIGNACIÓN DE RUTAS DE ENTREGA")
    print("=" * 70)

    total_orders = 0
    for c in couriers:
        if not c.route:
            continue
        total_orders += len(c.route)
        print(f"\n  Repartidor: {c.name}  [{c.vehicle}]  (base: {c.base_zone})")
        print(f"  Pedidos asignados: {len(c.route)}   "
              f"Distancia total: {c.total_distance_km:.1f} km")
        print(f"  {'#':>3}  {'Pedido':>7}  {'Destino':<10}  {'Dist(km)':>9}  Cliente")
        print(f"  {'-'*3}  {'-'*7}  {'-'*10}  {'-'*9}  {'-'*20}")
        for i, order in enumerate(c.route, 1):
            print(f"  {i:>3}  {order.order_id:>7}  {order.dest_zone:<10}  "
                  f"{order.distance_km:>9.2f}  {order.customer}")

    print("\n" + "=" * 70)
    print(f"Total pedidos asignados: {total_orders}")
    print("=" * 70 + "\n")


def export_json(couriers: list[Courier], path: str = "routing/route_results.json") -> None:
    data: list[dict[str, Any]] = [
        {
            "courier_id":         c.courier_id,
            "name":               c.name,
            "vehicle":            c.vehicle,
            "base_zone":          c.base_zone,
            "total_distance_km":  round(c.total_distance_km, 2),
            "orders": [
                {
                    "order_id":    o.order_id,
                    "dest_zone":   o.dest_zone,
                    "customer":    o.customer,
                    "total":       o.total,
                    "distance_km": round(o.distance_km, 2),
                }
                for o in c.route
            ],
        }
        for c in couriers
        if c.route
    ]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Resultados guardados en {path}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        from neo4j import GraphDatabase  # pylint: disable=import-outside-toplevel
    except ImportError:
        raise SystemExit(
            "Instala el driver: pip install neo4j\n"
            "  o:  docker run --rm --network py02-olap_olap-net "
            "-v ./routing:/routing python:3.11-slim "
            "bash -c \"pip install -q neo4j && python /routing/route_assignment.py\""
        )

    print(f"Conectando a Neo4J en {NEO4J_URI} …")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

    try:
        driver.verify_connectivity()
    except Exception as e:
        raise SystemExit(f"No se pudo conectar a Neo4J: {e}")

    print("Leyendo repartidores y pedidos pendientes …")
    couriers   = get_couriers(driver)
    deliveries = get_pending_deliveries(driver)

    print(f"  {len(couriers)} repartidores  ·  {len(deliveries)} pedidos pendientes")

    if not deliveries:
        print("No hay pedidos pendientes. Fin.")
        return

    # Función de distancia entre zonas (usa GDS Dijkstra con fallback Haversine)
    dist_cache: dict[tuple[str, str], float] = {}

    def cached_dist(z1: str, z2: str) -> float:
        key = (min(z1, z2), max(z1, z2))
        if key not in dist_cache:
            dist_cache[key] = get_shortest_path_km(driver, z1, z2)
        return dist_cache[key]

    print("Calculando rutas óptimas (vecino más cercano) …")
    couriers = nearest_neighbor_assign(couriers, deliveries, cached_dist)

    print_routes(couriers)
    export_json(couriers)

    driver.close()


if __name__ == "__main__":
    main()
