"""
Generador de datos históricos — PY02 OLAP Restaurantes

Crea ~GEN_ORDERS pedidos distribuidos en GEN_MONTHS meses de historia,
con distribución horaria realista (horarios pico), tendencia de crecimiento
mensual, co-compra de productos por grupo de afinidad, geolocalización y
asignación de repartidores.

Uso:
    python generate.py          # usa variables de entorno o defaults
"""

import os
import math
import random
from datetime import datetime, timedelta, timezone

import numpy as np
import psycopg2
import psycopg2.extras
from faker import Faker

from catalog import (
    ZONES, CATEGORIES, PRODUCTS, RESTAURANTS,
    MENUS, AFFINITY_GROUPS, COURIERS,
)

# ── Configuración ─────────────────────────────────────────────────────────────

DB_CONFIG = {
    "host":     os.getenv("OLTP_HOST",     "localhost"),
    "port":     int(os.getenv("OLTP_PORT", "5432")),
    "dbname":   os.getenv("OLTP_DB",       "restaurantes_oltp"),
    "user":     os.getenv("OLTP_USER",     "olap"),
    "password": os.getenv("OLTP_PASSWORD", "olap123"),
}

GEN_MONTHS  = int(os.getenv("GEN_MONTHS",  "12"))
GEN_ORDERS  = int(os.getenv("GEN_ORDERS",  "20000"))
NUM_USERS   = int(os.getenv("GEN_USERS",   "80"))
RANDOM_SEED = int(os.getenv("GEN_SEED",    "42"))

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
fake = Faker("es_MX")
Faker.seed(RANDOM_SEED)

# ── Distribuciones ────────────────────────────────────────────────────────────

# Peso por hora del día (0-23) → horarios pico almuerzo 12-14h y cena 19-21h
HOUR_WEIGHTS = [
    0.3, 0.1, 0.1, 0.1, 0.1, 0.2,   # 0-5
    0.5, 1.0, 1.5, 1.0, 0.8, 1.5,   # 6-11
    3.0, 3.5, 3.0, 1.5, 1.0, 1.5,   # 12-17
    2.5, 4.0, 4.5, 3.5, 2.0, 0.8,   # 18-23
]
HOUR_PROBS = np.array(HOUR_WEIGHTS) / sum(HOUR_WEIGHTS)

# Peso por día de semana (0=lunes … 6=domingo)
DOW_WEIGHTS = [0.8, 0.85, 0.9, 1.0, 1.3, 1.5, 1.1]
DOW_PROBS   = np.array(DOW_WEIGHTS) / sum(DOW_WEIGHTS)

ORDER_STATUSES = {
    "completed":  0.68,
    "cancelled":  0.15,
    "delivering": 0.07,
    "preparing":  0.05,
    "confirmed":  0.03,
    "pending":    0.02,
}

PAYMENT_METHODS = {"card": 0.50, "cash": 0.30, "wallet": 0.20}

# ── Utilidades ────────────────────────────────────────────────────────────────

def weighted_choice(mapping: dict):
    keys   = list(mapping.keys())
    probs  = list(mapping.values())
    return random.choices(keys, weights=probs, k=1)[0]


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def jitter(coord: float, radius: float = 0.015) -> float:
    """Desplaza una coordenada hasta radius grados (~1.5 km)."""
    return coord + random.uniform(-radius, radius)


def random_point_near(zone_key: str):
    z = ZONES[zone_key]
    return jitter(z["lat"]), jitter(z["lon"])


def sample_products_for_order(all_product_ids: list[int]) -> list[int]:
    """Selecciona 1-4 productos con sesgo de co-compra."""
    group = random.choices(
        AFFINITY_GROUPS,
        weights=[g["weight"] for g in AFFINITY_GROUPS],
        k=1
    )[0]
    # filtra índices válidos y mapea a IDs reales
    valid_indices = [i for i in group["products"] if i < len(all_product_ids)]
    if not valid_indices:
        valid_indices = list(range(len(all_product_ids)))
    n = min(random.randint(1, 4), len(valid_indices))
    return random.sample([all_product_ids[i] for i in valid_indices], n)


# ── Carga del schema ──────────────────────────────────────────────────────────

def apply_schema(cur):
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        cur.execute(f.read())
    print("  Schema aplicado.")


def truncate_tables(cur):
    cur.execute("""
        TRUNCATE deliveries, order_items, orders, couriers,
                 menu_products, menus, users, products,
                 restaurants, categories
        RESTART IDENTITY CASCADE
    """)
    print("  Tablas truncadas.")


# ── Inserción del catálogo ────────────────────────────────────────────────────

def insert_catalog(cur):
    # Categorías
    psycopg2.extras.execute_batch(cur, """
        INSERT INTO categories (name, description, icon) VALUES (%s, %s, %s)
    """, [(c["name"], c["description"], c["icon"]) for c in CATEGORIES])
    cur.execute("SELECT id, name FROM categories ORDER BY id")
    cat_map = {row[1]: row[0] for row in cur.fetchall()}

    # Restaurantes
    psycopg2.extras.execute_batch(cur, """
        INSERT INTO restaurants (name, address, phone, description, rating, zone, lat, lon)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, [(r["name"], r["address"], r["phone"], r["description"],
           r["rating"], r["zone"], r["lat"], r["lon"]) for r in RESTAURANTS])
    cur.execute("SELECT id FROM restaurants ORDER BY id")
    rest_ids = [row[0] for row in cur.fetchall()]

    # Productos
    psycopg2.extras.execute_batch(cur, """
        INSERT INTO products (name, description, price, image_url, available, category_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, [(p["name"], p["description"], p["price"],
           f"https://placehold.co/400x300?text={p['name'].replace(' ','+')}",
           p["available"], cat_map[CATEGORIES[p["cat_idx"]]["name"]])
          for p in PRODUCTS])
    cur.execute("SELECT id FROM products ORDER BY id")
    prod_ids = [row[0] for row in cur.fetchall()]

    # Menús y sus productos
    for m in MENUS:
        cur.execute("""
            INSERT INTO menus (name, description, active, restaurant_id)
            VALUES (%s, %s, TRUE, %s) RETURNING id
        """, (m["name"], m["description"], rest_ids[m["rest_idx"]]))
        menu_id = cur.fetchone()[0]
        psycopg2.extras.execute_batch(cur, """
            INSERT INTO menu_products (menu_id, product_id, display_order)
            VALUES (%s, %s, %s)
        """, [(menu_id, prod_ids[pi], order_)
              for order_, pi in enumerate(m["product_indices"], 1)])

    print(f"  Catálogo: {len(CATEGORIES)} cats, {len(RESTAURANTS)} restaurantes, {len(PRODUCTS)} productos.")
    return rest_ids, prod_ids


# ── Usuarios ──────────────────────────────────────────────────────────────────

def insert_users(cur) -> list[dict]:
    zone_keys = list(ZONES.keys())
    users = []

    # Admin fijo
    users.append({
        "name": "Carlos Administrador", "email": "admin@restaurantes.gt",
        "role": "admin", "zone": "zona_10",
        "lat": ZONES["zona_10"]["lat"], "lon": ZONES["zona_10"]["lon"],
    })

    # Clientes sintéticos
    emails_used = {"admin@restaurantes.gt"}
    while len(users) < NUM_USERS + 1:
        email = fake.unique.email()
        if email in emails_used:
            continue
        emails_used.add(email)
        zk = random.choice(zone_keys)
        lat, lon = random_point_near(zk)
        users.append({
            "name":  fake.name(), "email": email,
            "role":  "customer",  "zone":  zk,
            "lat":   lat,         "lon":   lon,
        })

    psycopg2.extras.execute_batch(cur, """
        INSERT INTO users (name, email, password_hash, role, zone, lat, lon)
        VALUES (%s, %s, 'hashed', %s, %s, %s, %s)
    """, [(u["name"], u["email"], u["role"], u["zone"], u["lat"], u["lon"])
          for u in users])

    cur.execute("SELECT id, zone FROM users WHERE role = 'customer' ORDER BY id")
    rows = cur.fetchall()
    print(f"  Usuarios: {len(users)} ({len(rows)} clientes).")
    return rows  # list of (id, zone)


# ── Repartidores ──────────────────────────────────────────────────────────────

def insert_couriers(cur) -> list[dict]:
    records = []
    for c in COURIERS:
        zk = c["base_zone"]
        lat, lon = random_point_near(zk)
        records.append((c["name"], c["vehicle"], zk, lat, lon))

    psycopg2.extras.execute_batch(cur, """
        INSERT INTO couriers (name, vehicle, base_zone, base_lat, base_lon)
        VALUES (%s, %s, %s, %s, %s)
    """, records)

    cur.execute("SELECT id, base_zone, base_lat, base_lon FROM couriers ORDER BY id")
    rows = cur.fetchall()
    print(f"  Repartidores: {len(rows)}.")
    return rows  # list of (id, zone, lat, lon)


# ── Generación de pedidos ─────────────────────────────────────────────────────

def generate_order_timestamp(month_offset: int, growth_factor: float) -> datetime:
    """
    month_offset: 0 = mes más antiguo, GEN_MONTHS-1 = mes más reciente.
    Usa la distribución de hora y día de semana.
    """
    now = datetime.now(tz=timezone.utc)
    # Inicio del mes objetivo
    target_month = now - timedelta(days=30 * (GEN_MONTHS - 1 - month_offset))
    base = target_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = 30

    # Elegir día con sesgo de día de semana
    day_candidates = list(range(days_in_month))
    day_weights    = [DOW_PROBS[(base + timedelta(days=d)).weekday()] for d in day_candidates]
    chosen_day     = random.choices(day_candidates, weights=day_weights, k=1)[0]

    # Elegir hora
    chosen_hour   = int(np.random.choice(24, p=HOUR_PROBS))
    chosen_minute = random.randint(0, 59)
    chosen_second = random.randint(0, 59)

    ts = base + timedelta(days=chosen_day, hours=chosen_hour,
                          minutes=chosen_minute, seconds=chosen_second)
    return ts


def insert_orders(cur, rest_ids, prod_ids, customer_rows, courier_rows):
    # Distribución de pedidos por mes con tendencia creciente
    # Mes 0 (más antiguo): factor 0.6. Mes N-1: factor 1.4
    growth = np.linspace(0.6, 1.4, GEN_MONTHS)
    month_counts = (growth / growth.sum() * GEN_ORDERS).astype(int)
    month_counts[-1] += GEN_ORDERS - month_counts.sum()  # ajuste por redondeo

    prod_price_map: dict[int, float] = {}
    cur.execute("SELECT id, price FROM products")
    for pid, price in cur.fetchall():
        prod_price_map[pid] = float(price)

    orders_batch    = []
    items_batch     = []
    deliveries_batch = []

    order_id_counter = 0  # se llenará tras el INSERT de orders

    print(f"  Generando {GEN_ORDERS} pedidos en {GEN_MONTHS} meses...", flush=True)

    for month_idx, count in enumerate(month_counts):
        for _ in range(count):
            user_id, user_zone = random.choice(customer_rows)
            rest_id            = random.choice(rest_ids)
            ts                 = generate_order_timestamp(month_idx, growth[month_idx])
            status             = weighted_choice(ORDER_STATUSES)
            payment            = weighted_choice(PAYMENT_METHODS)

            chosen_prod_ids    = sample_products_for_order(prod_ids)
            items              = []
            total              = 0.0
            for pid in chosen_prod_ids:
                qty        = random.randint(1, 3)
                unit_price = prod_price_map.get(pid, 50.0)
                line_total = round(qty * unit_price, 2)
                total     += line_total
                items.append((pid, qty, unit_price, line_total))

            orders_batch.append((user_id, rest_id, ts, status, round(total, 2), payment))

    # Bulk insert orders y recuperar IDs generados
    psycopg2.extras.execute_batch(cur, """
        INSERT INTO orders (user_id, restaurant_id, order_ts, status, total, payment_method)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, orders_batch)

    cur.execute("SELECT id, restaurant_id, order_ts, status FROM orders ORDER BY id")
    inserted_orders = cur.fetchall()  # (order_id, rest_id, ts, status)

    # Reconstruir items y deliveries con los order_ids reales
    # Necesitamos re-generar los mismos productos (mismo seed → reproducible)
    random.seed(RANDOM_SEED + 1)
    np.random.seed(RANDOM_SEED + 1)

    for (order_id, rest_id, order_ts, status), orig_order in zip(inserted_orders, orders_batch):
        chosen_prod_ids = sample_products_for_order(prod_ids)
        for pid in chosen_prod_ids:
            qty        = random.randint(1, 3)
            unit_price = prod_price_map.get(pid, 50.0)
            line_total = round(qty * unit_price, 2)
            items_batch.append((order_id, pid, qty, unit_price, line_total))

        # Delivery solo para pedidos completados o en entrega
        if status in ("completed", "delivering"):
            courier_id, c_zone, c_lat, c_lon = random.choice(courier_rows)

            # Coords del restaurante
            cur.execute("SELECT lat, lon FROM restaurants WHERE id = %s", (rest_id,))
            r_lat, r_lon = cur.fetchone()

            # Destino: zona del cliente con pequeño jitter
            dest_lat = jitter(float(r_lat), 0.02)
            dest_lon = jitter(float(r_lon), 0.02)
            dest_zone = random.choice(list(ZONES.keys()))

            dist_km  = round(haversine_km(float(r_lat), float(r_lon), dest_lat, dest_lon), 2)
            eta_min  = int(dist_km * 4 + random.randint(5, 15))

            if status == "completed":
                actual_ts = order_ts + timedelta(minutes=eta_min + random.randint(-3, 10))
            else:
                actual_ts = None  # en ruta, aún no entregado

            deliveries_batch.append((
                order_id, courier_id, dest_zone,
                round(dest_lat, 6), round(dest_lon, 6),
                dist_km, eta_min, actual_ts,
            ))

    print(f"  Insertando {len(items_batch)} ítems de pedido...", flush=True)
    psycopg2.extras.execute_batch(cur, """
        INSERT INTO order_items (order_id, product_id, quantity, unit_price, line_total)
        VALUES (%s, %s, %s, %s, %s)
    """, items_batch, page_size=500)

    print(f"  Insertando {len(deliveries_batch)} entregas...", flush=True)
    psycopg2.extras.execute_batch(cur, """
        INSERT INTO deliveries
            (order_id, courier_id, dest_zone, dest_lat, dest_lon, distance_km, eta_min, delivered_ts)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, deliveries_batch, page_size=500)

    print(f"  Pedidos: {len(inserted_orders)} | Ítems: {len(items_batch)} | Entregas: {len(deliveries_batch)}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n🌱 Generador PY02 — {GEN_ORDERS} pedidos × {GEN_MONTHS} meses\n")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            print("▶ Aplicando schema...")
            apply_schema(cur)

            print("▶ Limpiando datos previos...")
            try:
                truncate_tables(cur)
            except Exception:
                conn.rollback()
                with conn.cursor() as cur2:
                    apply_schema(cur2)

            print("▶ Insertando catálogo...")
            rest_ids, prod_ids = insert_catalog(cur)

            print("▶ Insertando usuarios...")
            customer_rows = insert_users(cur)

            print("▶ Insertando repartidores...")
            courier_rows = insert_couriers(cur)

            print("▶ Generando pedidos + ítems + entregas...")
            insert_orders(cur, rest_ids, prod_ids, customer_rows, courier_rows)

        conn.commit()
        print("\n✅ Generación completada exitosamente.\n")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
