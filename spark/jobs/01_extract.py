"""
Job 01 — Extract
Lee todas las tablas del OLTP vía JDBC y las persiste como Parquet en staging.
Esto desacopla la extracción del resto del pipeline (idempotente).
"""
from common import get_spark, read_oltp, STAGING_DIR
import os

TABLES = [
    "categories", "restaurants", "products", "menus", "menu_products",
    "users", "couriers", "orders", "order_items", "deliveries",
]


def main():
    spark = get_spark("PY02-01-Extract")
    spark.sparkContext.setLogLevel("WARN")

    os.makedirs(STAGING_DIR, exist_ok=True)

    for table in TABLES:
        df = read_oltp(spark, table)
        out = f"{STAGING_DIR}/{table}.parquet"
        df.write.mode("overwrite").parquet(out)
        print(f"  {table}: {df.count()} filas → {out}")

    spark.stop()


if __name__ == "__main__":
    main()
