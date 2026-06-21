"""
Exporta las tablas del OLTP a CSVs para importar en Neo4J.
Corre dentro del contenedor que tenga acceso a postgres-oltp y al
directorio de import de Neo4J (/neo4j/import o /output).

Uso:
    docker run --rm --network py02-olap_olap-net \\
        -v ./neo4j:/neo4j python:3.11-slim \\
        bash -c "pip install -q psycopg2-binary && python /neo4j/export_csvs.py"
"""

import csv
import math
import os
import sys

import psycopg2

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/neo4j/import")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CONN_PARAMS = dict(
    host=os.environ.get("OLTP_HOST", "postgres-oltp"),
    port=int(os.environ.get("OLTP_PORT", "5432")),
    dbname=os.environ.get("OLTP_DB", "restaurantes_oltp"),
    user=os.environ.get("OLTP_USER", "olap"),
    password=os.environ.get("OLTP_PASSWORD", "olap123"),
)


def write_csv(filename: str, rows: list[dict], fieldnames: list[str]) -> None:
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {filename}: {len(rows)} filas → {path}")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en km entre dos coordenadas geográficas."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Zonas geográficas del proyecto
ZONES = {
    "zona_1":  (14.6407, -90.5133),
    "zona_4":  (14.6257, -90.5218),
    "zona_9":  (14.6032, -90.5172),
    "zona_10": (14.5994, -90.5069),
    "zona_11": (14.6050, -90.5333),
    "zona_13": (14.5775, -90.5283),
    "antigua": (14.5586, -90.7295),
}

ZONE_NAMES = {
    "zona_1":  "Zona 1",
    "zona_4":  "Zona 4",
    "zona_9":  "Zona 9",
    "zona_10": "Zona 10",
    "zona_11": "Zona 11",
    "zona_13": "Zona 13",
    "antigua": "Antigua Guatemala",
}


def main() -> None:
    try:
        conn = psycopg2.connect(**CONN_PARAMS)
    except psycopg2.OperationalError as e:
        sys.exit(f"No se pudo conectar a OLTP: {e}")

    print(f"Exportando CSVs a {OUTPUT_DIR} …")

    with conn.cursor() as cur:

        # ── Nodos: usuarios ───────────────────────────────────────────────────
        cur.execute("""
            SELECT id, name, email, role, zone,
                   COALESCE(lat::text,'') AS lat,
                   COALESCE(lon::text,'') AS lon
            FROM users
        """)
        write_csv("users.csv", [
            {"user_id": r[0], "name": r[1], "email": r[2],
             "role": r[3], "zone": r[4], "lat": r[5], "lon": r[6]}
            for r in cur.fetchall()
        ], ["user_id", "name", "email", "role", "zone", "lat", "lon"])

        # ── Nodos: restaurantes ───────────────────────────────────────────────
        cur.execute("""
            SELECT id, name, address, zone,
                   COALESCE(lat::text,'') AS lat,
                   COALESCE(lon::text,'') AS lon,
                   COALESCE(rating::text,'') AS rating
            FROM restaurants
        """)
        write_csv("restaurants.csv", [
            {"rest_id": r[0], "name": r[1], "address": r[2],
             "zone": r[3], "lat": r[4], "lon": r[5], "rating": r[6]}
            for r in cur.fetchall()
        ], ["rest_id", "name", "address", "zone", "lat", "lon", "rating"])

        # ── Nodos: productos ──────────────────────────────────────────────────
        cur.execute("""
            SELECT p.id, p.name, p.price::text, p.available::text, c.name AS category
            FROM products p JOIN categories c ON p.category_id = c.id
        """)
        write_csv("products.csv", [
            {"prod_id": r[0], "name": r[1], "price": r[2],
             "available": r[3], "category": r[4]}
            for r in cur.fetchall()
        ], ["prod_id", "name", "price", "available", "category"])

        # ── Nodos: couriers ───────────────────────────────────────────────────
        cur.execute("SELECT id, name, vehicle, base_zone FROM couriers")
        write_csv("couriers.csv", [
            {"courier_id": r[0], "name": r[1], "vehicle": r[2], "base_zone": r[3]}
            for r in cur.fetchall()
        ], ["courier_id", "name", "vehicle", "base_zone"])

        # ── Nodos: ubicaciones (zonas) ────────────────────────────────────────
        locations = [
            {"zone": z, "zone_name": ZONE_NAMES[z],
             "lat": str(lat), "lon": str(lon)}
            for z, (lat, lon) in ZONES.items()
        ]
        write_csv("locations.csv", locations, ["zone", "zone_name", "lat", "lon"])

        # ── Rels: órdenes ─────────────────────────────────────────────────────
        cur.execute("""
            SELECT id, user_id, restaurant_id, status,
                   total::text, payment_method,
                   to_char(order_ts, 'YYYY-MM-DD HH24:MI:SS') AS order_ts
            FROM orders
        """)
        write_csv("orders.csv", [
            {"order_id": r[0], "user_id": r[1], "rest_id": r[2],
             "status": r[3], "total": r[4], "payment_method": r[5], "order_ts": r[6]}
            for r in cur.fetchall()
        ], ["order_id", "user_id", "rest_id", "status", "total", "payment_method", "order_ts"])

        # ── Rels: ítems de orden ──────────────────────────────────────────────
        cur.execute("""
            SELECT order_id, product_id, quantity, unit_price::text, line_total::text
            FROM order_items
        """)
        write_csv("order_items.csv", [
            {"order_id": r[0], "prod_id": r[1], "quantity": r[2],
             "unit_price": r[3], "line_total": r[4]}
            for r in cur.fetchall()
        ], ["order_id", "prod_id", "quantity", "unit_price", "line_total"])

        # ── Rels: entregas (courier → order → destino) ────────────────────────
        cur.execute("""
            SELECT d.order_id, d.courier_id, d.dest_zone,
                   COALESCE(d.distance_km::text,'') AS distance_km,
                   COALESCE(d.eta_min::text,'')     AS eta_min,
                   o.status
            FROM deliveries d
            JOIN orders o ON o.id = d.order_id
        """)
        write_csv("deliveries.csv", [
            {"order_id": r[0], "courier_id": r[1], "dest_zone": r[2],
             "distance_km": r[3], "eta_min": r[4], "status": r[5]}
            for r in cur.fetchall()
        ], ["order_id", "courier_id", "dest_zone", "distance_km", "eta_min", "status"])

        # ── Rels: recomendaciones implícitas (clientes que comparten restaurante)
        cur.execute("""
            SELECT DISTINCT
                a.user_id AS from_user,
                b.user_id AS to_user,
                o1.restaurant_id
            FROM orders a
            JOIN orders b ON a.restaurant_id = b.restaurant_id
                          AND a.user_id < b.user_id
            JOIN orders o1 ON o1.id = a.id
            LIMIT 300
        """)
        write_csv("user_recommendations.csv", [
            {"from_user": r[0], "to_user": r[1], "via_restaurant": r[2]}
            for r in cur.fetchall()
        ], ["from_user", "to_user", "via_restaurant"])

    conn.close()

    # ── Rels: rutas entre zonas (distancia + tiempo estimado) ─────────────────
    routes = []
    zone_list = list(ZONES.keys())
    for i, z1 in enumerate(zone_list):
        lat1, lon1 = ZONES[z1]
        for z2 in zone_list[i + 1:]:
            lat2, lon2 = ZONES[z2]
            dist = round(haversine_km(lat1, lon1, lat2, lon2), 2)
            time_min = round(dist / 30 * 60, 1)  # velocidad promedio 30 km/h
            routes.append({"from_zone": z1, "to_zone": z2,
                            "distance_km": dist, "time_min": time_min})

    write_csv("zone_routes.csv", routes, ["from_zone", "to_zone", "distance_km", "time_min"])

    print(f"\n✅ Exportación completa — {len(os.listdir(OUTPUT_DIR))} archivos en {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
