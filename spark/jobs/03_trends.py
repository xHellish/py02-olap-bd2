"""
Job 03 — Análisis 1: Tendencias de Consumo
Ingresos y unidades vendidas por categoría a lo largo del tiempo.
Usa Window functions (running total, rank por mes).
Exporta a Hive (mart_trends) y postgres-serving.
"""
from common import get_spark, HIVE_DB, write_mart, drop_table
from pyspark.sql import functions as F, Window


def main():
    spark = get_spark("PY02-03-Trends")
    spark.sparkContext.setLogLevel("WARN")

    # ── DataFrame API: leer desde los cubos Hive ──────────────────────────────
    fi = spark.table(f"{HIVE_DB}.fact_order_items")
    dd = spark.table(f"{HIVE_DB}.dim_date")
    dc = spark.table(f"{HIVE_DB}.dim_category")

    base = (
        fi.drop("year", "month")  # remove partition cols to avoid ambiguity with dim_date
          .join(dd, "date_key")
          .join(dc, "category_key")
          .groupBy("year", "month", "month_name", "category_name")
          .agg(
              F.countDistinct("order_id").alias("order_count"),
              F.sum("quantity").alias("units_sold"),
              F.round(F.sum("line_total"), 2).alias("revenue"),
          )
          .withColumn(
              "year_month",
              F.concat(F.col("year").cast("string"), F.lit("-"),
                       F.lpad(F.col("month").cast("string"), 2, "0"))
          )
    )

    # ── SparkSQL: window functions (running total + rank) ─────────────────────
    base.createOrReplaceTempView("v_base_trends")

    result = spark.sql("""
        SELECT
            year,
            month,
            month_name,
            year_month,
            category_name,
            order_count,
            units_sold,
            revenue,
            ROUND(
                SUM(revenue) OVER (
                    PARTITION BY category_name
                    ORDER BY year, month
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ), 2
            ) AS cumulative_revenue,
            RANK() OVER (PARTITION BY year, month ORDER BY revenue DESC) AS revenue_rank_in_month
        FROM v_base_trends
        ORDER BY year, month, revenue DESC
    """)

    # Escribir a Hive (drop+rmtree para idempotencia)
    drop_table(spark, "mart_trends")
    (result.write
           .format("orc")
           .mode("overwrite")
           .saveAsTable(f"{HIVE_DB}.mart_trends"))

    # Exportar a postgres-serving
    write_mart(result, "mart_trends")

    print(f"✅ mart_trends: {result.count()} filas")
    result.show(10, truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
