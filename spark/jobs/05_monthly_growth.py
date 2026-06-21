"""
Job 05 — Análisis 3: Crecimiento Mensual
Variación % mes a mes en pedidos e ingresos usando lag().
Proyección lineal simple del último mes al siguiente.
"""
from common import get_spark, HIVE_DB, write_mart, drop_table
from pyspark.sql import functions as F, Window


def main():
    spark = get_spark("PY02-05-MonthlyGrowth")
    spark.sparkContext.setLogLevel("WARN")

    # ── SparkSQL: base mensual ────────────────────────────────────────────────
    spark.sql(f"USE {HIVE_DB}")

    monthly = spark.sql("""
        SELECT
            d.year,
            d.month,
            d.month_name,
            CONCAT(CAST(d.year AS STRING), '-',
                   LPAD(CAST(d.month AS STRING), 2, '0')) AS year_month,
            COUNT(*)                     AS order_count,
            ROUND(SUM(fo.total), 2)      AS revenue,
            ROUND(AVG(fo.total), 2)      AS avg_ticket,
            ROUND(AVG(fo.item_count), 2) AS avg_items_per_order,
            COUNT(DISTINCT fo.customer_key) AS unique_customers
        FROM fact_orders fo
        JOIN dim_date d ON fo.date_key = d.date_key
        WHERE fo.status = 'completed'
        GROUP BY d.year, d.month, d.month_name
        ORDER BY d.year, d.month
    """)

    # ── DataFrame API: lag() para calcular variación mes a mes ───────────────
    w = Window.orderBy("year", "month")

    result = (
        monthly
        .withColumn("prev_order_count", F.lag("order_count").over(w))
        .withColumn("prev_revenue",     F.lag("revenue").over(w))
        .withColumn(
            "order_count_pct_change",
            F.round(
                (F.col("order_count") - F.col("prev_order_count"))
                / F.col("prev_order_count") * 100,
                2
            )
        )
        .withColumn(
            "revenue_pct_change",
            F.round(
                (F.col("revenue") - F.col("prev_revenue"))
                / F.col("prev_revenue") * 100,
                2
            )
        )
        .withColumn(
            "cumulative_revenue",
            F.round(
                F.sum("revenue").over(
                    w.rowsBetween(Window.unboundedPreceding, Window.currentRow)
                ),
                2
            )
        )
        .drop("prev_order_count", "prev_revenue")
    )

    # Escribir a Hive (drop+rmtree para idempotencia)
    drop_table(spark, "mart_monthly_growth")
    (result.write
           .format("orc")
           .mode("overwrite")
           .saveAsTable(f"{HIVE_DB}.mart_monthly_growth"))

    # Exportar a postgres-serving
    write_mart(result, "mart_monthly_growth")

    print(f"✅ mart_monthly_growth: {result.count()} filas")
    result.show(15, truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
