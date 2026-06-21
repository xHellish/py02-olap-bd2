"""
Job 06 — Export Marts
Exporta todos los marts de análisis a postgres-serving para Superset.
También crea vistas de soporte (zona × revenue, productos top) que
no requieren la instalación completa de Hive en el cliente Superset.
"""
from common import get_spark, HIVE_DB, write_mart
from pyspark.sql import functions as F


MARTS_TO_EXPORT = [
    "mart_trends",
    "mart_peak_hours",
    "mart_monthly_growth",
]

# Vistas adicionales que Superset consultará directamente
CUBES_TO_EXPORT = [
    ("cube_revenue_month_category",  "mart_revenue_by_cat"),
    ("cube_orders_by_zone",          "mart_orders_by_zone"),
    ("cube_order_status",            "mart_order_status"),
    ("cube_peak_hours",              "mart_peak_hours_cube"),
    ("cube_product_ranking",         "mart_product_ranking"),
    ("cube_courier_performance",     "mart_courier_perf"),
]


def main():
    spark = get_spark("PY02-06-ExportMarts")
    spark.sparkContext.setLogLevel("WARN")
    spark.sql(f"USE {HIVE_DB}")

    print("── Exportando marts de análisis ──")
    for mart in MARTS_TO_EXPORT:
        df = spark.table(f"{HIVE_DB}.{mart}")
        write_mart(df, mart)
        print(f"  {mart}: {df.count()} filas → postgres-serving")

    print("── Exportando cubos OLAP ──")
    for hive_view, pg_table in CUBES_TO_EXPORT:
        df = spark.sql(f"SELECT * FROM {HIVE_DB}.{hive_view}")
        write_mart(df, pg_table)
        print(f"  {hive_view} → {pg_table}: {df.count()} filas")

    # Mart adicional: resumen ejecutivo (una fila por KPI global)
    summary = spark.sql("""
        SELECT
            COUNT(*)                          AS total_orders,
            SUM(CASE WHEN status='completed' THEN 1 END) AS completed_orders,
            ROUND(SUM(total), 2)              AS total_revenue,
            ROUND(AVG(total), 2)              AS avg_ticket,
            COUNT(DISTINCT customer_key)      AS unique_customers,
            COUNT(DISTINCT restaurant_key)    AS active_restaurants
        FROM fact_orders
    """)
    write_mart(summary, "mart_executive_summary")
    print(f"  mart_executive_summary: exportado")

    print("✅ Todos los marts exportados a postgres-serving.")
    spark.stop()


if __name__ == "__main__":
    main()
