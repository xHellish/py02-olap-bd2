.PHONY: up up-all down clean seed logs ps validate

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

# ── Hive: aplicar DDL manualmente ─────────────────────────────────────────────
hive-init:
	docker compose exec hiveserver2 beeline -u jdbc:hive2://localhost:10000 \
	    -f /opt/hive/scripts/00_create_db.hql
	docker compose exec hiveserver2 beeline -u jdbc:hive2://localhost:10000 \
	    -f /opt/hive/scripts/01_dimensions.hql
	docker compose exec hiveserver2 beeline -u jdbc:hive2://localhost:10000 \
	    -f /opt/hive/scripts/02_facts.hql
	docker compose exec hiveserver2 beeline -u jdbc:hive2://localhost:10000 \
	    -f /opt/hive/scripts/03_olap_cubes.hql

# ── Spark: submit manual de un job ────────────────────────────────────────────
spark-job:
	docker compose exec spark-master spark-submit \
	    --master spark://spark-master:7077 \
	    /opt/bitnami/spark/jobs/$(JOB)

# ── Neo4J: cargar grafo ────────────────────────────────────────────────────────
neo4j-load:
	docker compose exec neo4j cypher-shell -u neo4j -p neo4j123 \
	    -f /var/lib/neo4j/import/01_load_graph.cypher

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
