.PHONY: up up-all down clean seed logs ps validate hive-init spark-job neo4j-export-csv neo4j-load neo4j-queries neo4j-routing airflow-up superset-init

# ── Perfiles individuales ─────────────────────────────────────────────────────
core:
	docker compose --profile core up -d

dw:
	docker compose --profile dw up -d

orchestration:
	docker compose --profile orchestration up -d

graph:
	docker compose --profile graph up -d

viz:
	docker compose --profile viz up -d

# ── Combinaciones útiles ───────────────────────────────────────────────────────
up: core dw
	@echo "Core + DW levantados."

up-all:
	docker compose --profile core --profile dw --profile orchestration \
	               --profile graph --profile viz up -d
	@echo "Stack completo levantado."

# ── Generación de datos ────────────────────────────────────────────────────────
seed:
	docker compose --profile core up -d
	docker compose --profile core ps | grep -q "postgres-oltp" || (echo "OLTP no está corriendo" && exit 1)
	pip install -q -r data-generator/requirements.txt
	python data-generator/generate.py

seed-docker:
	docker compose run --rm -e OLTP_HOST=postgres-oltp \
	    --network py02-olap_olap-net \
	    data-generator

# ── Control ────────────────────────────────────────────────────────────────────
down:
	docker compose down

clean:
	docker compose down -v
	@echo "Volúmenes eliminados."

ps:
	docker compose ps

logs:
	docker compose logs -f --tail=50

# ── Hive: aplicar DDL (warehouse/ montado en /warehouse dentro del contenedor) ─
hive-init:
	docker compose exec py02_hiveserver2 /opt/hive/bin/beeline \
	    -u jdbc:hive2://localhost:10000 -n hive -p '' \
	    --silent=true -f /warehouse/00_create_db.hql
	docker compose exec py02_hiveserver2 /opt/hive/bin/beeline \
	    -u jdbc:hive2://localhost:10000/restaurantes_dw -n hive -p '' \
	    --silent=true -f /warehouse/01_dimensions.hql
	docker compose exec py02_hiveserver2 /opt/hive/bin/beeline \
	    -u jdbc:hive2://localhost:10000/restaurantes_dw -n hive -p '' \
	    --silent=true -f /warehouse/02_facts.hql
	docker compose exec py02_hiveserver2 /opt/hive/bin/beeline \
	    -u jdbc:hive2://localhost:10000/restaurantes_dw -n hive -p '' \
	    --silent=true -f /warehouse/03_olap_cubes.hql
	@echo "Hive DW inicializado. Verifica con: docker compose exec py02_hiveserver2 /opt/hive/bin/beeline -u jdbc:hive2://localhost:10000/restaurantes_dw -e 'SHOW TABLES;'"

# ── Spark: submit manual de un job  (JOB=02_build_dw.py) ────────────────────
spark-job:
	docker compose exec py02_spark_master /opt/spark/bin/spark-submit \
	    --master spark://spark-master:7077 \
	    --conf spark.driver.extraClassPath=/opt/spark/jars/postgresql-42.7.4.jar \
	    /opt/spark/jobs/$(JOB)

# ── Spark: pipeline completo de Fase 4 ────────────────────────────────────────
spark-pipeline:
	docker compose exec py02_spark_master /opt/spark/bin/spark-submit \
	    --master spark://spark-master:7077 \
	    /opt/spark/jobs/01_extract.py
	docker compose exec py02_spark_master /opt/spark/bin/spark-submit \
	    --master spark://spark-master:7077 \
	    /opt/spark/jobs/02_build_dw.py
	docker compose exec py02_spark_master /opt/spark/bin/spark-submit \
	    --master spark://spark-master:7077 \
	    /opt/spark/jobs/03_trends.py
	docker compose exec py02_spark_master /opt/spark/bin/spark-submit \
	    --master spark://spark-master:7077 \
	    /opt/spark/jobs/04_peak_hours.py
	docker compose exec py02_spark_master /opt/spark/bin/spark-submit \
	    --master spark://spark-master:7077 \
	    /opt/spark/jobs/05_monthly_growth.py
	docker compose exec py02_spark_master /opt/spark/bin/spark-submit \
	    --master spark://spark-master:7077 \
	    /opt/spark/jobs/06_export_marts.py

# ── Airflow: levantar perfil de orquestación ─────────────────────────────────
airflow-up:
	docker compose --profile orchestration up -d
	@echo "Airflow UI: http://localhost:8081  (admin/admin)"
	@echo "Nota: los paquetes pip se instalan en el primer arranque (~2 min)"

# ── Neo4J: exportar CSVs desde OLTP ──────────────────────────────────────────
neo4j-export-csv:
	docker run --rm --network py02-olap_olap-net \
	    -v "$(CURDIR)/neo4j:/neo4j" \
	    -e OUTPUT_DIR=/neo4j/import \
	    python:3.11-slim \
	    bash -c "pip install -q psycopg2-binary && python /neo4j/export_csvs.py"

# ── Neo4J: cargar grafo ────────────────────────────────────────────────────────
neo4j-load:
	docker compose --profile graph up -d
	@echo "Esperando Neo4J..."
	docker compose exec neo4j bash -c "until wget -q --spider http://localhost:7474; do sleep 3; done"
	docker compose exec neo4j cypher-shell -u neo4j -p neo4j123 \
	    -f /scripts/01_load_graph.cypher

# ── Neo4J: ejecutar consultas Cypher ──────────────────────────────────────────
neo4j-queries:
	docker compose exec neo4j cypher-shell -u neo4j -p neo4j123 \
	    --format verbose \
	    -f /scripts/02_queries.cypher

# ── Neo4J: enrutamiento de entregas ──────────────────────────────────────────
neo4j-routing:
	docker run --rm --network py02-olap_olap-net \
	    -v "$(CURDIR)/routing:/routing" \
	    -e NEO4J_URI=bolt://neo4j:7687 \
	    python:3.11-slim \
	    bash -c "pip install -q neo4j && python /routing/route_assignment.py"

# ── Superset: init admin ───────────────────────────────────────────────────────
superset-init:
	docker compose exec superset superset fab create-admin \
	    --username admin --firstname Admin --lastname User \
	    --email admin@example.com --password admin
	docker compose exec superset superset db upgrade
	docker compose exec superset superset init

# ── Validación rápida ──────────────────────────────────────────────────────────
validate:
	@echo "=== Postgres OLTP ==="
	docker compose exec postgres-oltp pg_isready -U olap -d restaurantes_oltp
	@echo "=== Elasticsearch ==="
	curl -s http://localhost:9200/_cluster/health | python -m json.tool
	@echo "=== Mongo ==="
	docker compose exec mongo mongosh --eval "db.adminCommand('ping')"
