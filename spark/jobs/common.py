"""
Utilidades compartidas por todos los jobs de Spark — PY02 OLAP
"""
import os
import shutil
from pyspark.sql import SparkSession


OLTP_URL  = "jdbc:postgresql://postgres-oltp:5432/restaurantes_oltp"
OLTP_OPTS = {
    "driver":   "org.postgresql.Driver",
    "user":     os.environ.get("OLTP_USER",     "olap"),
    "password": os.environ.get("OLTP_PASSWORD", "olap123"),
}

SERVING_URL  = "jdbc:postgresql://postgres-serving:5432/restaurantes_marts"
SERVING_OPTS = {
    "driver":   "org.postgresql.Driver",
    "user":     os.environ.get("SERVING_USER",     "olap"),
    "password": os.environ.get("SERVING_PASSWORD", "olap123"),
}

STAGING_DIR  = "/opt/hive/data/warehouse/.staging"
HIVE_DB      = "restaurantes_dw"


def get_spark(app_name: str) -> SparkSession:
    return (
        SparkSession.builder
        .appName(app_name)
        .master("spark://spark-master:7077")
        .config("spark.sql.catalogImplementation", "hive")
        .config("hive.metastore.uris", "thrift://hive-metastore:9083")
        .config("spark.sql.warehouse.dir", "file:///opt/hive/data/warehouse")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .enableHiveSupport()
        .getOrCreate()
    )


def read_oltp(spark: SparkSession, table: str, query: str = None):
    opts = dict(OLTP_OPTS)
    if query:
        opts["query"] = query
    else:
        opts["dbtable"] = table
    return spark.read.format("jdbc").options(url=OLTP_URL, **opts).load()


def drop_table(spark, table: str) -> None:
    """Drops a Hive managed table and removes its physical directory so saveAsTable can recreate it."""
    spark.sql(f"DROP TABLE IF EXISTS {HIVE_DB}.{table}")
    tbl_dir = os.path.join(f"/opt/hive/data/warehouse/{HIVE_DB}.db", table)
    if os.path.exists(tbl_dir):
        shutil.rmtree(tbl_dir)


def write_mart(df, table: str, mode: str = "overwrite"):
    """Escribe un DataFrame a postgres-serving (capa de marts para Superset)."""
    (df.write
       .format("jdbc")
       .option("url", SERVING_URL)
       .option("dbtable", table)
       .option("driver", SERVING_OPTS["driver"])
       .option("user",   SERVING_OPTS["user"])
       .option("password", SERVING_OPTS["password"])
       .mode(mode)
       .save())
