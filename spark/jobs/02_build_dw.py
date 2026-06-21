"""
Job 02 — Build DW
Construye el esquema estrella en restaurantes_dw (Hive):
  • 8 dimensiones (incluyendo dim_date y dim_time generadas)
  • 2 tablas de hechos particionadas por year/month

Usa DataFrame API + SparkSQL según requisitos del enunciado.
Idempotente: sobrescribe particiones existentes.
"""
import os, shutil
from common import get_spark, STAGING_DIR, HIVE_DB
from pyspark.sql import functions as F, Window


# ─── helpers ─────────────────────────────────────────────────────────────────

def _load(spark, table):
    return spark.read.parquet(f"{STAGING_DIR}/{table}.parquet")


def _write_hive(df, table, partition_cols=None):
    writer = df.write.format("orc").mode("overwrite")
    if partition_cols:
        writer = writer.partitionBy(*partition_cols)
    writer.saveAsTable(f"{HIVE_DB}.{table}")


# ─── dimensiones ─────────────────────────────────────────────────────────────

def build_dim_date(spark):
    """Genera un registro por día entre jul-2025 y jun-2026."""
    dates = spark.sql("""
        SELECT sequence(
            to_date('2025-07-01'),
            to_date('2026-06-30'),
            interval 1 day
        ) AS d
    """).select(F.explode("d").alias("full_date"))

    df = dates.select(
        F.date_format("full_date", "yyyyMMdd").cast("int").alias("date_key"),
        F.col("full_date"),
        F.year("full_date").alias("year"),
        F.quarter("full_date").alias("quarter"),
        F.when(F.month("full_date") <= 6, 1).otherwise(2).alias("semester"),
        F.month("full_date").alias("month"),
        F.date_format("full_date", "MMMM").alias("month_name"),
        F.weekofyear("full_date").alias("week_of_year"),
        F.dayofmonth("full_date").alias("day_of_month"),
        F.dayofweek("full_date").alias("day_of_week"),
        F.date_format("full_date", "EEEE").alias("day_name"),
        (F.dayofweek("full_date").isin(1, 7)).alias("is_weekend"),
    )
    _write_hive(df, "dim_date")
    print(f"  dim_date: {df.count()} filas")


def build_dim_time(spark):
    """24 filas (horas 0-23) con etiqueta de franja horaria."""
    hours = spark.range(24).withColumnRenamed("id", "hour")
    df = hours.select(
        F.col("hour").cast("int").alias("time_key"),
        F.col("hour").cast("int").alias("hour"),
        F.concat(F.lpad(F.col("hour").cast("string"), 2, "0"), F.lit(":00")).alias("time_label"),
        F.when(F.col("hour").between(0,  5),  "madrugada")
         .when(F.col("hour").between(6,  11), "mañana")
         .when(F.col("hour").between(12, 14), "almuerzo")
         .when(F.col("hour").between(15, 17), "tarde")
         .when(F.col("hour").between(18, 22), "cena")
         .otherwise("noche").alias("time_of_day"),
    )
    _write_hive(df, "dim_time")
    print(f"  dim_time: {df.count()} filas")


def build_dim_category(spark):
    df = _load(spark, "categories")
    rn = Window.orderBy("id")
    out = df.select(
        F.row_number().over(rn).alias("category_key"),
        F.col("id").alias("category_id"),
        F.col("name").alias("category_name"),
        F.col("description"),
        F.col("icon"),
    )
    _write_hive(out, "dim_category")
    print(f"  dim_category: {out.count()} filas")


def build_dim_product(spark):
    p  = _load(spark, "products")
    c  = _load(spark, "categories")
    rn = Window.orderBy("p.id")
    out = (
        p.alias("p")
         .join(c.alias("c"), p.category_id == c.id)
         .select(
             F.row_number().over(rn).alias("product_key"),
             F.col("p.id").alias("product_id"),
             F.col("p.name").alias("product_name"),
             F.col("c.id").alias("category_key"),
             F.col("c.name").alias("category_name"),
             F.col("p.price").cast("double").alias("unit_price"),
             F.col("p.available"),
         )
    )
    _write_hive(out, "dim_product")
    print(f"  dim_product: {out.count()} filas")


def build_dim_customer(spark):
    df = _load(spark, "users").filter(F.col("role") == "customer")
    rn = Window.orderBy("id")
    out = df.select(
        F.row_number().over(rn).alias("customer_key"),
        F.col("id").alias("user_id"),
        F.col("name").alias("user_name"),
        F.col("email"),
        F.col("zone"),
        F.col("lat").cast("double"),
        F.col("lon").cast("double"),
    )
    _write_hive(out, "dim_customer")
    print(f"  dim_customer: {out.count()} filas")


def build_dim_restaurant(spark):
    df = _load(spark, "restaurants")
    rn = Window.orderBy("id")
    out = df.select(
        F.row_number().over(rn).alias("restaurant_key"),
        F.col("id").alias("restaurant_id"),
        F.col("name").alias("rest_name"),
        F.col("address"),
        F.col("zone"),
        F.col("lat").cast("double"),
        F.col("lon").cast("double"),
        F.col("rating").cast("double"),
    )
    _write_hive(out, "dim_restaurant")
    print(f"  dim_restaurant: {out.count()} filas")


def build_dim_location(spark):
    """Zonas únicas de entrega derivadas de las entregas + catálogo de zonas."""
    zones = [
        (1, "zona_1",  "Zona 1",   14.6407, -90.5133),
        (2, "zona_4",  "Zona 4",   14.6257, -90.5218),
        (3, "zona_9",  "Zona 9",   14.6032, -90.5172),
        (4, "zona_10", "Zona 10",  14.5994, -90.5069),
        (5, "zona_11", "Zona 11",  14.6050, -90.5333),
        (6, "zona_13", "Zona 13",  14.5775, -90.5283),
        (7, "antigua", "Antigua",  14.5586, -90.7295),
    ]
    schema = "location_key INT, zone STRING, zone_name STRING, lat DOUBLE, lon DOUBLE"
    out = spark.createDataFrame(zones, schema)
    _write_hive(out, "dim_location")
    print(f"  dim_location: {out.count()} filas")


def build_dim_courier(spark):
    df = _load(spark, "couriers")
    rn = Window.orderBy("id")
    out = df.select(
        F.row_number().over(rn).alias("courier_key"),
        F.col("id").alias("courier_id"),
        F.col("name").alias("courier_name"),
        F.col("vehicle"),
        F.col("base_zone"),
    )
    _write_hive(out, "dim_courier")
    print(f"  dim_courier: {out.count()} filas")


# ─── hechos ───────────────────────────────────────────────────────────────────

def build_facts(spark):
    # Cargar dimensiones ya escritas en Hive (para lookups de surrogate keys)
    spark.sql(f"USE {HIVE_DB}")
    dim_date  = spark.table(f"{HIVE_DB}.dim_date")
    dim_cust  = spark.table(f"{HIVE_DB}.dim_customer")
    dim_rest  = spark.table(f"{HIVE_DB}.dim_restaurant")
    dim_prod  = spark.table(f"{HIVE_DB}.dim_product")
    dim_cat   = spark.table(f"{HIVE_DB}.dim_category")
    dim_loc   = spark.table(f"{HIVE_DB}.dim_location")
    dim_cour  = spark.table(f"{HIVE_DB}.dim_courier")

    orders    = _load(spark, "orders")
    items     = _load(spark, "order_items")
    deliveries= _load(spark, "deliveries")

    # Contar ítems por pedido
    items_per_order = items.groupBy("order_id").agg(F.count("*").alias("item_count"))

    # ── fact_orders ──────────────────────────────────────────────────────────
    # SparkSQL: registrar vistas temporales para usar SQL explícito
    orders.createOrReplaceTempView("v_orders")
    deliveries.createOrReplaceTempView("v_deliveries")
    dim_date.createOrReplaceTempView("v_dim_date")
    dim_cust.createOrReplaceTempView("v_dim_customer")
    dim_rest.createOrReplaceTempView("v_dim_restaurant")
    dim_loc.createOrReplaceTempView("v_dim_location")
    dim_cour.createOrReplaceTempView("v_dim_courier")
    items_per_order.createOrReplaceTempView("v_items_per_order")

    fo = spark.sql("""
        SELECT
            o.id                                         AS order_key,
            o.id                                         AS order_id,
            CAST(date_format(o.order_ts,'yyyyMMdd') AS INT) AS date_key,
            HOUR(o.order_ts)                             AS time_key,
            dc.customer_key,
            dr.restaurant_key,
            COALESCE(dloc.location_key, -1)              AS location_key,
            COALESCE(dcour.courier_key, -1)              AS courier_key,
            o.status,
            o.payment_method,
            CAST(o.total AS DOUBLE)                      AS total,
            COALESCE(ip.item_count, 0)                   AS item_count,
            CAST(d.distance_km AS DOUBLE)                AS distance_km,
            CAST(d.eta_min     AS INT)                   AS eta_min,
            CAST(
                (unix_timestamp(d.delivered_ts)
                 - unix_timestamp(o.order_ts)) / 60
            AS INT)                                      AS delivery_time_min,
            (o.status IN ('completed','delivering'))     AS is_delivered,
            YEAR(o.order_ts)                             AS year,
            MONTH(o.order_ts)                            AS month
        FROM v_orders o
        LEFT JOIN v_deliveries   d    ON o.id = d.order_id
        LEFT JOIN v_dim_customer dc   ON o.user_id = dc.user_id
        LEFT JOIN v_dim_restaurant dr ON o.restaurant_id = dr.restaurant_id
        LEFT JOIN v_dim_location dloc ON d.dest_zone = dloc.zone
        LEFT JOIN v_dim_courier dcour ON d.courier_id = dcour.courier_id
        LEFT JOIN v_items_per_order ip ON o.id = ip.order_id
    """)

    (fo.write
       .format("orc")
       .mode("overwrite")
       .option("orc.compress", "snappy")
       .partitionBy("year", "month")
       .saveAsTable(f"{HIVE_DB}.fact_orders"))
    print(f"  fact_orders: {fo.count()} filas")

    # ── fact_order_items ─────────────────────────────────────────────────────
    # DataFrame API: join encadenado (contrasta con el SQL arriba)
    items.createOrReplaceTempView("v_items")
    dim_prod.createOrReplaceTempView("v_dim_product")
    dim_cat.createOrReplaceTempView("v_dim_category")

    fi = spark.sql("""
        SELECT
            BIGINT(ROW_NUMBER() OVER (ORDER BY i.id))  AS item_key,
            i.order_id,
            CAST(date_format(o.order_ts,'yyyyMMdd') AS INT) AS date_key,
            HOUR(o.order_ts)                           AS time_key,
            dp.product_key,
            dc2.category_key,
            dr2.restaurant_key,
            dcu.customer_key,
            CAST(i.quantity  AS INT)                   AS quantity,
            CAST(i.unit_price AS DOUBLE)               AS unit_price,
            CAST(i.line_total AS DOUBLE)               AS line_total,
            YEAR(o.order_ts)                           AS year,
            MONTH(o.order_ts)                          AS month
        FROM v_items i
        JOIN v_orders          o   ON i.order_id = o.id
        JOIN v_dim_product     dp  ON i.product_id = dp.product_id
        JOIN v_dim_category    dc2 ON dp.category_key = dc2.category_key
        JOIN v_dim_restaurant  dr2 ON o.restaurant_id = dr2.restaurant_id
        JOIN v_dim_customer    dcu ON o.user_id = dcu.user_id
    """)

    (fi.write
       .format("orc")
       .mode("overwrite")
       .option("orc.compress", "snappy")
       .partitionBy("year", "month")
       .saveAsTable(f"{HIVE_DB}.fact_order_items"))
    print(f"  fact_order_items: {fi.count()} filas")


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    spark = get_spark("PY02-02-BuildDW")
    spark.sparkContext.setLogLevel("WARN")
    spark.sql(f"USE {HIVE_DB}")

    # Drop existing DW tables and physical dirs so saveAsTable can recreate them
    db_dir = f"/opt/hive/data/warehouse/{HIVE_DB}.db"
    for tbl in ["fact_order_items", "fact_orders",
                "dim_courier", "dim_location", "dim_restaurant",
                "dim_customer", "dim_product", "dim_category",
                "dim_time", "dim_date"]:
        spark.sql(f"DROP TABLE IF EXISTS {HIVE_DB}.{tbl}")
        tbl_dir = os.path.join(db_dir, tbl)
        if os.path.exists(tbl_dir):
            shutil.rmtree(tbl_dir)

    print("── Dimensiones ──")
    build_dim_date(spark)
    build_dim_time(spark)
    build_dim_category(spark)
    build_dim_product(spark)
    build_dim_customer(spark)
    build_dim_restaurant(spark)
    build_dim_location(spark)
    build_dim_courier(spark)

    print("── Hechos ──")
    build_facts(spark)

    print("✅ DW construido.")
    spark.stop()


if __name__ == "__main__":
    main()
