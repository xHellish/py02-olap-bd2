"""
DAG ETL OLAP — Proyecto 2
Pipeline completo: OLTP → Spark → Hive DW → análisis → marts Postgres.

Estructura:
    extract_postgres
        └── build_hive_dw
              ├── run_trends
              ├── run_peak_hours
              ├── run_monthly_growth
              └── check_catalog_changed ──► reindex_elasticsearch
                                       └──► skip_reindex
              (todos los anteriores)
                        └── export_marts
                                └── data_quality_checks
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator

# ─── Constantes ──────────────────────────────────────────────────────────────

SPARK_CONTAINER = "py02_spark_master"
OLTP_CONN = dict(host="postgres-oltp", port=5432,
                 dbname="restaurantes_oltp", user="olap", password="olap123")
SERVING_CONN = dict(host="postgres-serving", port=5432,
                    dbname="restaurantes_marts", user="olap", password="olap123")
ES_URL = "http://elasticsearch:9200"

# ─── Callables ───────────────────────────────────────────────────────────────

def run_spark_job(job_filename: str, **_context) -> None:
    """Ejecuta spark-submit dentro del contenedor spark-master vía Docker SDK."""
    import docker  # pylint: disable=import-outside-toplevel

    client = docker.from_env()
    container = client.containers.get(SPARK_CONTAINER)

    cmd = f"/opt/spark/bin/spark-submit /opt/spark/jobs/{job_filename}"
    result = container.exec_run(cmd, stdout=True, stderr=True, stream=False)

    output = result.output or b""
    print(output.decode("utf-8", errors="replace"))

    if result.exit_code != 0:
        raise RuntimeError(
            f"Spark job '{job_filename}' finalizó con exit code {result.exit_code}"
        )


def check_catalog_changed(**context) -> str:
    """
    BranchPythonOperator: hashea el catálogo de productos.
    Si cambió → reindex_elasticsearch; si no → skip_reindex.
    """
    import psycopg2  # pylint: disable=import-outside-toplevel

    with psycopg2.connect(**OLTP_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, price, category_id, available "
                "FROM products ORDER BY id"
            )
            rows = cur.fetchall()

    catalog_hash = hashlib.md5(
        json.dumps(rows, default=str).encode()
    ).hexdigest()

    ti = context["ti"]
    prev_hash: str | None = ti.xcom_pull(
        task_ids="check_catalog_changed",
        dag_id="etl_olap_dag",
        include_prior_dates=True,
        key="catalog_hash",
    )
    ti.xcom_push(key="catalog_hash", value=catalog_hash)

    if prev_hash is None or prev_hash != catalog_hash:
        print(f"Catálogo cambió ({prev_hash} → {catalog_hash}). Reindexando ES.")
        return "reindex_elasticsearch"

    print(f"Catálogo sin cambios ({catalog_hash}). Saltando reindex.")
    return "skip_reindex"


def reindex_elasticsearch(**_context) -> None:
    """
    Reindexa el catálogo de productos en Elasticsearch.
    Solo se ejecuta cuando el catálogo cambió (rama de check_catalog_changed).
    """
    import psycopg2  # pylint: disable=import-outside-toplevel
    from elasticsearch import Elasticsearch, helpers  # pylint: disable=import-outside-toplevel

    es = Elasticsearch([ES_URL])

    with psycopg2.connect(**OLTP_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.name, p.price::float, p.available, c.name AS category
                FROM products p
                JOIN categories c ON p.category_id = c.id
            """)
            products = cur.fetchall()

    index_name = "productos"
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
    es.indices.create(index=index_name, body={
        "mappings": {
            "properties": {
                "name":      {"type": "text"},
                "price":     {"type": "float"},
                "available": {"type": "boolean"},
                "category":  {"type": "keyword"},
            }
        }
    })

    actions = [
        {
            "_index": index_name,
            "_id": row[0],
            "_source": {
                "id": row[0], "name": row[1], "price": row[2],
                "available": row[3], "category": row[4],
            },
        }
        for row in products
    ]
    helpers.bulk(es, actions)
    print(f"✅ Reindexados {len(products)} productos en Elasticsearch.")


def data_quality_checks(**_context) -> None:
    """
    Validaciones de calidad sobre los marts en postgres-serving.
    Falla si alguna métrica está fuera de rango.
    """
    import psycopg2  # pylint: disable=import-outside-toplevel

    checks = [
        # (tabla, query, umbral_mínimo, mensaje)
        ("mart_trends",           "SELECT COUNT(*) FROM mart_trends",                    1,    "Sin filas"),
        ("mart_peak_hours",       "SELECT COUNT(*) FROM mart_peak_hours",                1,    "Sin filas"),
        ("mart_monthly_growth",   "SELECT COUNT(*) FROM mart_monthly_growth",            1,    "Sin filas"),
        ("mart_executive_summary","SELECT total_orders FROM mart_executive_summary",  1000,    "< 1000 pedidos"),
        ("no_nulls_trends",       "SELECT COUNT(*) FROM mart_trends WHERE revenue IS NULL", 1000, "revenue nulo > límite"),
    ]

    failed = []
    with psycopg2.connect(**SERVING_CONN) as conn:
        with conn.cursor() as cur:
            for name, query, threshold, msg in checks:
                cur.execute(query)
                val = cur.fetchone()[0]
                # Última validación: quiere que el valor sea MENOR al umbral (nulls)
                if name.startswith("no_nulls"):
                    if val >= threshold:
                        failed.append(f"{name}: {msg} (nulls={val})")
                else:
                    if val < threshold:
                        failed.append(f"{name}: {msg} (valor={val})")

    if failed:
        raise ValueError("Data quality checks fallidos:\n" + "\n".join(failed))

    print("✅ Todos los checks de calidad pasaron.")


# ─── DAG ─────────────────────────────────────────────────────────────────────

default_args = {
    "owner": "py02-olap",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="etl_olap_dag",
    description="Pipeline ETL OLAP: OLTP → Spark → Hive DW → marts Postgres",
    schedule_interval="@daily",
    start_date=datetime(2026, 6, 1),
    catchup=False,
    default_args=default_args,
    tags=["py02", "olap", "spark", "hive"],
) as dag:

    # ── Extracción ────────────────────────────────────────────────────────────
    t_extract = PythonOperator(
        task_id="extract_postgres",
        python_callable=run_spark_job,
        op_args=["01_extract.py"],
    )

    # ── Construcción del DW ───────────────────────────────────────────────────
    t_build_dw = PythonOperator(
        task_id="build_hive_dw",
        python_callable=run_spark_job,
        op_args=["02_build_dw.py"],
    )

    # ── Análisis Spark (en paralelo) ──────────────────────────────────────────
    t_trends = PythonOperator(
        task_id="run_trends",
        python_callable=run_spark_job,
        op_args=["03_trends.py"],
    )

    t_peak = PythonOperator(
        task_id="run_peak_hours",
        python_callable=run_spark_job,
        op_args=["04_peak_hours.py"],
    )

    t_growth = PythonOperator(
        task_id="run_monthly_growth",
        python_callable=run_spark_job,
        op_args=["05_monthly_growth.py"],
    )

    # ── Exportación de marts ──────────────────────────────────────────────────
    t_export = PythonOperator(
        task_id="export_marts",
        python_callable=run_spark_job,
        op_args=["06_export_marts.py"],
    )

    # ── Rama: ¿cambió el catálogo? ────────────────────────────────────────────
    t_check_catalog = BranchPythonOperator(
        task_id="check_catalog_changed",
        python_callable=check_catalog_changed,
    )

    t_reindex_es = PythonOperator(
        task_id="reindex_elasticsearch",
        python_callable=reindex_elasticsearch,
    )

    t_skip_reindex = EmptyOperator(task_id="skip_reindex")

    # ── Calidad de datos ──────────────────────────────────────────────────────
    t_quality = PythonOperator(
        task_id="data_quality_checks",
        python_callable=data_quality_checks,
        trigger_rule="all_done",  # corre aunque la rama saltara el reindex
    )

    # ── Dependencias ─────────────────────────────────────────────────────────
    t_extract >> t_build_dw
    t_build_dw >> [t_trends, t_peak, t_growth, t_check_catalog]
    [t_trends, t_peak, t_growth] >> t_export
    t_check_catalog >> [t_reindex_es, t_skip_reindex]
    [t_export, t_reindex_es, t_skip_reindex] >> t_quality
