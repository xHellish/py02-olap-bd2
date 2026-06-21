"""
Job 04 — Análisis 2: Horarios Pico
Conteo de pedidos por hora × día de semana → heatmap operacional.
Identifica franjas de alta demanda para optimización de repartidores.
"""
from common import get_spark, HIVE_DB, write_mart, drop_table
from pyspark.sql import functions as F


def main():
    spark = get_spark("PY02-04-PeakHours")
    spark.sparkContext.setLogLevel("WARN")

    # ── SparkSQL: agregación hora × día_semana ────────────────────────────────
    spark.sql(f"USE {HIVE_DB}")

    result = spark.sql("""
        SELECT
            t.hour,
            t.time_label,
            t.time_of_day,
            d.day_of_week,
            d.day_name,
            d.is_weekend,
            COUNT(*)                        AS order_count,
            ROUND(SUM(fo.total), 2)         AS revenue,
            ROUND(AVG(fo.total), 2)         AS avg_ticket,
            ROUND(AVG(fo.item_count), 1)    AS avg_items
        FROM fact_orders fo
        JOIN dim_time t ON fo.time_key = t.time_key
        JOIN dim_date d ON fo.date_key  = d.date_key
        GROUP BY
            t.hour, t.time_label, t.time_of_day,
            d.day_of_week, d.day_name, d.is_weekend
        ORDER BY d.day_of_week, t.hour
    """)

    # ── DataFrame API: agregar ranking de horas ───────────────────────────────
    from pyspark.sql import Window
    w = Window.orderBy(F.desc("order_count"))
    result_ranked = result.withColumn("global_rank", F.rank().over(w))

    # Escribir a Hive (drop+rmtree para idempotencia)
    drop_table(spark, "mart_peak_hours")
    (result_ranked.write
                  .format("orc")
                  .mode("overwrite")
                  .saveAsTable(f"{HIVE_DB}.mart_peak_hours"))

    # Exportar a postgres-serving
    write_mart(result_ranked, "mart_peak_hours")

    print(f"✅ mart_peak_hours: {result_ranked.count()} filas")

    # Mostrar top-10 combinaciones hora×día con más pedidos
    result_ranked.orderBy("global_rank").show(10, truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
