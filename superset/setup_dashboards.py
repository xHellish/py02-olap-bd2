#!/usr/bin/env python3
"""
superset/setup_dashboards.py
Configura Superset automáticamente vía REST API:
  - 1 conexión a postgres-serving
  - 3 datasets  (mart_revenue_by_cat, mart_orders_by_zone, mart_order_status)
  - 9 charts    (3 por dashboard)
  - 3 dashboards requeridos por el enunciado

Ejecutar con Superset corriendo en localhost:8088:
    python superset/setup_dashboards.py
"""
import json
import sys
import time
import requests

BASE = "http://localhost:8088"
USER = "admin"
PASS = "admin"

# URI interna — Superset se conecta desde dentro de Docker
DB_URI = "postgresql://olap:olap123@postgres-serving:5432/restaurantes_marts"

# Sesión compartida para mantener cookies (necesario para CSRF)
SESSION = requests.Session()


# ── Auth ──────────────────────────────────────────────────────────────────────

def login() -> tuple:
    r = SESSION.post(f"{BASE}/api/v1/security/login", json={
        "username": USER, "password": PASS, "provider": "db", "refresh": True,
    })
    r.raise_for_status()
    token = r.json()["access_token"]
    csrf_r = SESSION.get(f"{BASE}/api/v1/security/csrf_token/",
                         headers={"Authorization": f"Bearer {token}"})
    csrf_r.raise_for_status()
    return token, csrf_r.json()["result"]


def hdr(token, csrf):
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRFToken": csrf,
        "Content-Type": "application/json",
        "Referer": BASE,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def find_existing(token, csrf, endpoint, name_col, name):
    r = SESSION.get(
        f"{BASE}/api/v1/{endpoint}/",
        headers=hdr(token, csrf),
        params={"q": json.dumps({"filters": [
            {"col": name_col, "opr": "eq", "value": name}
        ]})},
    )
    items = r.json().get("result", [])
    return items[0]["id"] if items else None


def find_or_create(token, csrf, endpoint, name_col, name, payload) -> int:
    eid = find_existing(token, csrf, endpoint, name_col, name)
    if eid:
        print(f"  -  {name!r} ya existe (id={eid})")
        return eid
    r = SESSION.post(f"{BASE}/api/v1/{endpoint}/",
                     headers=hdr(token, csrf), json=payload)
    if not r.ok:
        print(f"  ERROR creando {name!r}: {r.status_code}")
        print(f"     {r.text[:400]}")
        sys.exit(1)
    rid = r.json()["id"]
    print(f"  OK  {name!r} creado (id={rid})")
    return rid


def metric(col, agg, label):
    return {
        "expressionType": "SIMPLE",
        "column": {"column_name": col},
        "aggregate": agg,
        "label": label,
        "optionName": f"opt_{agg}_{col}",
    }


# ── Database ──────────────────────────────────────────────────────────────────

def create_database(token, csrf) -> int:
    return find_or_create(token, csrf, "database", "database_name",
                          "postgres-serving", {
                              "database_name": "postgres-serving",
                              "sqlalchemy_uri": DB_URI,
                              "expose_in_sqllab": True,
                              "allow_run_async": False,
                          })


# ── Datasets ──────────────────────────────────────────────────────────────────

def create_dataset(token, csrf, db_id, table) -> int:
    did = find_or_create(token, csrf, "dataset", "table_name", table, {
        "database": db_id,
        "schema": "public",
        "table_name": table,
    })
    # sincronizar columnas desde Postgres
    SESSION.put(f"{BASE}/api/v1/dataset/{did}/refresh",
                headers=hdr(token, csrf))
    return did


# ── Charts ────────────────────────────────────────────────────────────────────

def create_chart(token, csrf, name, viz_type, ds_id, extra: dict) -> int:
    base_params = {
        "viz_type": viz_type,
        "datasource": f"{ds_id}__table",
        "row_limit": 50000,
        "time_range": "No filter",
        "color_scheme": "supersetColors",
    }
    params = {**base_params, **extra}
    return find_or_create(token, csrf, "chart", "slice_name", name, {
        "slice_name": name,
        "viz_type": viz_type,
        "datasource_id": ds_id,
        "datasource_type": "table",
        "params": json.dumps(params),
    })


# ── Dashboard layout ──────────────────────────────────────────────────────────

def build_layout(chart_ids: list) -> str:
    """Dos columnas: primera fila ancha, resto en pares."""
    layout = {
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": []},
        "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": ""}},
    }
    rows = []
    for i, cid in enumerate(chart_ids):
        ck = f"CHART-{i}"
        rk = f"ROW-{i}"
        width = 12 if i == 0 else 6
        layout[ck] = {
            "type": "CHART", "id": ck, "children": [],
            "meta": {"chartId": cid, "width": width, "height": 50,
                     "sliceName": f"chart-{cid}"},
        }
        layout[rk] = {
            "type": "ROW", "id": rk,
            "children": [ck],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        rows.append(rk)
    layout["GRID_ID"]["children"] = rows
    return json.dumps(layout)


def create_dashboard(token, csrf, title, chart_ids) -> int:
    rid = find_or_create(token, csrf, "dashboard", "dashboard_title", title, {
        "dashboard_title": title,
        "published": True,
        "position_json": build_layout(chart_ids),
    })
    # Vincular charts al dashboard (relación slices)
    r = SESSION.put(f"{BASE}/api/v1/dashboard/{rid}",
                    headers=hdr(token, csrf),
                    json={"slices": chart_ids})
    if r.ok:
        print(f"    charts vinculados: {chart_ids}")
    else:
        print(f"    WARN al vincular charts: {r.status_code} {r.text[:200]}")
    return rid


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("── Conectando a Superset ────────────────────────────────────")
    try:
        token, csrf = login()
    except Exception as e:
        print(f"✗ No se pudo autenticar: {e}")
        print("  Asegúrate de que Superset esté corriendo en http://localhost:8088")
        print("  y de haber ejecutado: make superset-init")
        sys.exit(1)
    print("  ✓ Autenticado correctamente")

    print("\n── Base de datos ────────────────────────────────────────────")
    db_id = create_database(token, csrf)

    print("\n── Datasets ─────────────────────────────────────────────────")
    ds_rev  = create_dataset(token, csrf, db_id, "mart_revenue_by_cat")
    ds_zone = create_dataset(token, csrf, db_id, "mart_orders_by_zone")
    ds_stat = create_dataset(token, csrf, db_id, "mart_order_status")

    # ── Dashboard 1: Ingresos por Mes y Categoría ─────────────────────────────
    print("\n── Dashboard 1: Ingresos por Mes y Categoría ───────────────")
    # mart_revenue_by_cat: year, month, month_name, year_month,
    #                      category_name, order_count, units_sold,
    #                      revenue, avg_unit_price

    c1a = create_chart(token, csrf,
        "Ingresos por mes y categoría (líneas)", "echarts_timeseries_line", ds_rev, {
            "x_axis": "year_month",
            "metrics": [metric("revenue", "SUM", "Ingresos (Q)")],
            "groupby": ["category_name"],
            "show_legend": True,
            "rich_tooltip": True,
            "y_axis_format": "SMART_NUMBER",
            "x_axis_title": "Mes",
            "y_axis_title": "Ingresos (Q)",
        })

    c1b = create_chart(token, csrf,
        "Revenue total por categoría (barras)", "dist_bar", ds_rev, {
            "metrics": [metric("revenue", "SUM", "Ingresos (Q)")],
            "groupby": ["category_name"],
            "columns": [],
            "row_limit": 50,
            "order_bars": True,
            "show_legend": False,
            "y_axis_format": "SMART_NUMBER",
        })

    c1c = create_chart(token, csrf,
        "Pedidos y unidades vendidas por mes", "echarts_timeseries_bar", ds_rev, {
            "x_axis": "year_month",
            "metrics": [
                metric("order_count", "SUM", "Pedidos"),
                metric("units_sold",  "SUM", "Unidades"),
            ],
            "groupby": [],
            "show_legend": True,
            "y_axis_format": "SMART_NUMBER",
        })

    # ── Dashboard 2: Actividad de Clientes por Zona ───────────────────────────
    print("\n── Dashboard 2: Actividad de Clientes por Zona ─────────────")
    # mart_orders_by_zone: zone, zone_name, lat, lon, year, month,
    #                      order_count, delivered_count, avg_distance_km,
    #                      avg_delivery_min, total_revenue, avg_ticket

    c2a = create_chart(token, csrf,
        "Pedidos por zona geográfica", "dist_bar", ds_zone, {
            "metrics": [metric("order_count", "SUM", "Pedidos")],
            "groupby": ["zone_name"],
            "columns": [],
            "row_limit": 20,
            "order_bars": True,
            "show_legend": False,
        })

    c2b = create_chart(token, csrf,
        "Revenue total por zona", "dist_bar", ds_zone, {
            "metrics": [metric("total_revenue", "SUM", "Ingresos (Q)")],
            "groupby": ["zone_name"],
            "columns": [],
            "row_limit": 20,
            "order_bars": True,
            "show_legend": False,
            "y_axis_format": "SMART_NUMBER",
        })

    c2c = create_chart(token, csrf,
        "Distancia y tiempo promedio de entrega por zona", "dist_bar", ds_zone, {
            "metrics": [
                metric("avg_distance_km",  "AVG", "Dist. promedio (km)"),
                metric("avg_delivery_min", "AVG", "Tiempo promedio (min)"),
            ],
            "groupby": ["zone_name"],
            "columns": [],
            "row_limit": 20,
            "show_legend": True,
        })

    # ── Dashboard 3: Pedidos Completados vs Cancelados ────────────────────────
    print("\n── Dashboard 3: Pedidos Completados vs Cancelados ───────────")
    # mart_order_status: year, month, month_name, year_month,
    #                    status, payment_method,
    #                    order_count, revenue, avg_ticket

    c3a = create_chart(token, csrf,
        "Pedidos por estado en el tiempo", "echarts_timeseries_line", ds_stat, {
            "x_axis": "year_month",
            "metrics": [metric("order_count", "SUM", "Pedidos")],
            "groupby": ["status"],
            "show_legend": True,
            "rich_tooltip": True,
            "y_axis_format": "SMART_NUMBER",
            "x_axis_title": "Mes",
            "y_axis_title": "Pedidos",
        })

    c3b = create_chart(token, csrf,
        "Distribución de estados de pedido", "pie", ds_stat, {
            "groupby": ["status"],
            "metric": metric("order_count", "SUM", "Pedidos"),
            "show_legend": True,
            "show_labels": True,
            "label_type": "key_value_percent",
            "outerRadius": 70,
        })

    c3c = create_chart(token, csrf,
        "Revenue completados vs cancelados por mes", "echarts_timeseries_bar", ds_stat, {
            "x_axis": "year_month",
            "metrics": [metric("revenue", "SUM", "Ingresos (Q)")],
            "groupby": ["status"],
            "show_legend": True,
            "y_axis_format": "SMART_NUMBER",
            "stack": False,
        })

    # ── Crear dashboards ──────────────────────────────────────────────────────
    print("\n── Dashboards ───────────────────────────────────────────────")
    d1 = create_dashboard(token, csrf,
        "1. Ingresos por Mes y Categoría", [c1a, c1b, c1c])
    d2 = create_dashboard(token, csrf,
        "2. Actividad de Clientes por Zona", [c2a, c2b, c2c])
    d3 = create_dashboard(token, csrf,
        "3. Pedidos Completados vs Cancelados", [c3a, c3b, c3c])

    print(f"""
✅  Superset configurado correctamente.

Entra en http://localhost:8088  (admin / admin)
Dashboards creados:
  → Dashboard {d1}  "1. Ingresos por Mes y Categoría"
  → Dashboard {d2}  "2. Actividad de Clientes por Zona"
  → Dashboard {d3}  "3. Pedidos Completados vs Cancelados"
""")


if __name__ == "__main__":
    main()
