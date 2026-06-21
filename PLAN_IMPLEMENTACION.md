# Plan de Implementación — Proyecto 2: Análisis y Procesamiento OLAP

> Documento guía para el desarrollo. Cada fase tiene: **objetivo**, **archivos a crear**, **pasos**, **comandos de validación** y **criterios de aceptación** (checklist). Se desarrolla en orden; cada fase desbloquea la siguiente.

---

## 0. Reglas y convenciones del proyecto

- **`Proyecto1/` es solo referencia** (sistema de microservicios del PY01). **No se modifica.**
- **Todo el código del P2 vive en la raíz** `E:\Escritorio\Proyecto 2 OLAP\`, fuera de `Proyecto1/`.
- El P2 es un **stack autocontenido**: monta su propia fuente operacional (Postgres/Mongo) con el modelo extendido a **pedidos + entregas + geolocalización + historia**, inspirándose en el catálogo del PY01.
- Stack levantado con **Docker Compose**, por perfiles para no agotar la RAM.
- Idioma de código/comentarios: consistente con el repo (español en docs, inglés técnico donde aplique).

### Mapa de evaluación (para no perder de vista el peso)

| Criterio | % | Fase que lo cubre |
|---|---|---|
| Data Warehouse y OLAP (Hive) | 20 | Fase 3 |
| Procesamiento con Spark | 20 | Fase 4 |
| Visualización (Superset) | 15 | Fase 7 |
| Orquestación (Airflow) | 15 | Fase 5 |
| Neo4J (grafo + Cypher + rutas) | 15 | Fase 6 |
| Enrutamiento de entregas | 10 | Fase 6 |
| Documentación | 5 | Fase 8 |

---

## Resumen de fases

| Fase | Nombre | Entregable principal | Depende de |
|---|---|---|---|
| 0 | Reglas y convenciones | — | — |
| 1 | Scaffolding e infraestructura | `docker-compose.yml`, `.env`, estructura | — |
| 2 | Generación de datos (fuente OLTP) | Postgres con pedidos/entregas/geo + historia | 1 |
| 3 | Data Warehouse + OLAP (Hive) | Esquema estrella + 5 cubos | 2 |
| 4 | Procesamiento Spark | 3 análisis + carga al DW + marts | 3 |
| 5 | Orquestación Airflow | DAG modular y programado | 4 |
| 6 | Neo4J: grafo, Cypher y rutas | Grafo + consultas + enrutamiento | 2 |
| 7 | Visualización (Superset) | 3 dashboards | 4 |
| 8 | Documentación y demo | PDF técnico + capturas/video | todas |

---

## Fase 1 — Scaffolding e infraestructura base

**Objetivo:** dejar el esqueleto del repo y el `docker-compose.yml` con todos los servicios definidos (aunque algunos se afinen después).

### Estructura a crear (en la raíz)

```
Proyecto 2 OLAP/
├── docker-compose.yml
├── .env.example
├── .env                    # copia local (en .gitignore)
├── .gitignore
├── Makefile
├── README.md
├── data-generator/
├── warehouse/
├── spark/jobs/
├── airflow/dags/
├── neo4j/import/
├── routing/
├── superset/assets/
└── docs/diagrams/
```

### Servicios del `docker-compose.yml`

| Servicio | Imagen | Puerto host | Perfil |
|---|---|---|---|
| `postgres-oltp` | postgres:16 | 5432 | core |
| `mongo` | mongo:8 | 27017 | core (opcional) |
| `elasticsearch` | elasticsearch:8.15.5 | 9200 | core |
| `hive-metastore` | apache/hive:4.0.0 | 9083 | dw |
| `hiveserver2` | apache/hive:4.0.0 | 10000 | dw |
| `spark-master` | bitnami/spark:3.5 | 8080 | dw |
| `spark-worker` | bitnami/spark:3.5 | — | dw |
| `postgres-airflow` | postgres:16 | — | orchestration |
| `airflow-webserver` | apache/airflow:2.10 | 8081 | orchestration |
| `airflow-scheduler` | apache/airflow:2.10 | — | orchestration |
| `neo4j` | neo4j:5 (+GDS) | 7474 / 7687 | graph |
| `postgres-serving` | postgres:16 | 5433 | viz |
| `superset` | apache/superset | 8088 | viz |

> **Perfiles**: `docker compose --profile core --profile dw up -d`, etc. Documentar combinaciones en el README.

### `.env.example` (variables mínimas)

```
# OLTP
OLTP_DB=restaurantes_oltp
OLTP_USER=olap
OLTP_PASSWORD=olap123
# Serving (Superset)
SERVING_DB=restaurantes_marts
# Neo4J
NEO4J_AUTH=neo4j/neo4j123
# Airflow
AIRFLOW_UID=50000
# Generación de datos
GEN_MONTHS=12          # meses de historia a generar
GEN_ORDERS=20000       # volumen objetivo de pedidos
```

### Pasos
1. Crear carpetas y archivos vacíos / placeholder.
2. Escribir `docker-compose.yml` con los servicios y perfiles.
3. Escribir `.gitignore` (`.env`, `__pycache__`, `*.parquet`, volúmenes locales, `node_modules`).
4. `Makefile` con atajos: `up`, `down`, `seed`, `dw`, `dag`, `graph`, `logs`, `clean`.
5. `README.md` inicial con prerequisitos y orden de arranque.

### Validación
```bash
docker compose --profile core up -d
docker compose ps          # postgres-oltp, mongo, elasticsearch -> healthy
curl http://localhost:9200/_cluster/health
```

### ✅ Criterios de aceptación
- [ ] La estructura de carpetas existe en la raíz (no dentro de `Proyecto1/`).
- [ ] `docker compose config` valida sin errores.
- [ ] El perfil `core` levanta Postgres, Mongo y Elasticsearch en estado healthy.
- [ ] README explica perfiles y orden de arranque.

---

## Fase 2 — Generación de datos (fuente OLTP + historia)

**Objetivo:** poblar el Postgres operacional con el **modelo extendido** y **meses de historia** para que Spark tenga "grandes volúmenes" y datos para tendencias/horarios/crecimiento.

### Modelo operacional (extiende el del PY01)

Reusa: `users`, `restaurants`, `categories`, `products`, `menus`, `menu_products`.
**Añade (lo que el PY01 no tiene):**
- `orders` (id, user_id, restaurant_id, order_ts, status[pending|confirmed|preparing|delivering|completed|cancelled], total, payment_method)
- `order_items` (id, order_id, product_id, quantity, unit_price, line_total)
- `couriers` (id, name, vehicle, base_lat, base_lon)
- `deliveries` (id, order_id, courier_id, dest_lat, dest_lon, zone, distance_km, eta_min, delivered_ts)
- Coordenadas y `zone` en `restaurants` y en clientes (zonas de Ciudad de Guatemala como en el seed del PY01).

### Archivos a crear (`data-generator/`)
- `requirements.txt` → `faker`, `psycopg2-binary`, `pymongo`, `numpy`
- `schema.sql` → DDL del modelo operacional en Postgres
- `catalog.py` → categorías/productos/restaurantes (basados en el seed del PY01)
- `generate.py` → genera usuarios, pedidos históricos, items, repartidores, entregas con geo
- `Dockerfile` (opcional, para correrlo como contenedor one-shot)

### Reglas de generación (realismo para los análisis)
- **Historia**: distribuir `order_ts` en `GEN_MONTHS` hacia atrás desde hoy.
- **Crecimiento mensual**: tendencia creciente leve mes a mes (para que el análisis 3 muestre algo).
- **Horarios pico**: concentrar pedidos en almuerzo (12–14h) y cena (19–21h).
- **Estados**: ~70% completed, ~15% cancelled, resto en otros (para dashboard completados vs cancelados).
- **Co-compra**: ciertos productos aparecen juntos con más probabilidad (para el top-5 de Neo4J).
- **Geo**: destinos dispersos por zonas alrededor de las coordenadas de cada restaurante.

### Pasos
1. Escribir `schema.sql` y aplicarlo al `postgres-oltp`.
2. Implementar `generate.py` parametrizado por `GEN_MONTHS` / `GEN_ORDERS`.
3. Ejecutar la carga y verificar volúmenes.

### Validación
```bash
make seed     # o: python data-generator/generate.py
docker compose exec postgres-oltp psql -U olap -d restaurantes_oltp -c \
  "SELECT status, count(*) FROM orders GROUP BY status;"
docker compose exec postgres-oltp psql -U olap -d restaurantes_oltp -c \
  "SELECT date_trunc('month', order_ts) m, count(*) FROM orders GROUP BY m ORDER BY m;"
```

### ✅ Criterios de aceptación
- [ ] Existen `orders`, `order_items`, `couriers`, `deliveries` pobladas.
- [ ] ≥ ~15.000 pedidos repartidos en ≥ 12 meses.
- [ ] Distribución de estados realista (hay completed y cancelled).
- [ ] Pedidos concentrados en horas pico; entregas con lat/lon y zona.
- [ ] Script reproducible y parametrizable por variables de entorno.

---

## Fase 3 — Data Warehouse + OLAP (Apache Hive)

**Objetivo:** esquema estrella en Hive + mínimo 5 cubos/vistas OLAP. (20% de la nota.)

### Esquema estrella

**Hechos**
- `fact_order_items` — grano: línea de pedido. Medidas: `quantity`, `unit_price`, `line_total`. FKs: date, time, product, category, customer, restaurant, location, order_id (degenerada).
- `fact_orders` — grano: pedido. Medidas: `order_total`, `items_count`, `delivery_distance_km`, `delivery_time_min`. FKs: date, time, customer, restaurant, courier, location, status.

**Dimensiones**
- `dim_date` (fecha, año, trimestre, mes, nombre_mes, día, día_semana, es_fin_semana)
- `dim_time` (hora 0–23, franja)
- `dim_product` → `dim_category` (copo de nieve ligero)
- `dim_customer` (usuario, rol, zona)
- `dim_restaurant` (nombre, dirección, zona, lat, lon)
- `dim_location` (zona de entrega, ciudad, lat, lon)
- `dim_courier` (repartidor)

> Cubre las 4 dimensiones del enunciado: **tiempo, ubicación, tipo de producto, frecuencia de uso**.

### Los 5+ cubos OLAP (`warehouse/03_olap_cubes.hql`)

| Vista | Contenido | Sirve a |
|---|---|---|
| `cube_revenue_month_category` | Ingresos por mes × categoría | Dashboard 1 |
| `cube_orders_by_zone` | Pedidos/clientes por zona | Dashboard 2 |
| `cube_orders_status` | Completados vs cancelados por mes | Dashboard 3 |
| `cube_peak_hours` | Pedidos por hora × día de semana | Análisis horarios |
| `cube_product_frequency` | Top productos por frecuencia de compra | Frecuencia de uso |
| `cube_courier_performance` | Entregas/tiempo por repartidor | Liga con rutas |

### Archivos a crear (`warehouse/`)
- `01_dimensions.hql`, `02_facts.hql`, `03_olap_cubes.hql`
- `00_create_db.hql` (crea la base `restaurantes_dw`)

### Pasos
1. Definir DB y tablas (formato Parquet, particionado por año/mes en hechos).
2. Crear las vistas/cubos.
3. La carga real la hace Spark (Fase 4); aquí se valida con un INSERT de prueba.

### Validación
```bash
docker compose exec hiveserver2 beeline -u jdbc:hive2://localhost:10000 \
  -e "SHOW TABLES IN restaurantes_dw;"
docker compose exec hiveserver2 beeline -u jdbc:hive2://localhost:10000 \
  -e "SELECT * FROM restaurantes_dw.cube_revenue_month_category LIMIT 5;"
```

### ✅ Criterios de aceptación
- [ ] Esquema estrella creado en Hive (2 hechos + 7 dimensiones).
- [ ] ≥ 5 cubos/vistas OLAP que agregan por tiempo, ubicación, tipo de producto y frecuencia.
- [ ] Hechos particionados por año/mes.
- [ ] Diagrama del modelo estrella en `docs/diagrams/`.

---

## Fase 4 — Procesamiento con Apache Spark

**Objetivo:** ETL con DataFrames + SparkSQL que llena el DW y hace los **3 análisis**. (20%.)

### Jobs (`spark/jobs/`)
- `01_extract.py` — lee `postgres-oltp` por JDBC → staging Parquet.
- `02_build_dw.py` — construye dimensiones y hechos → escribe a Hive (`restaurantes_dw`).
- `03_trends.py` — **tendencias de consumo** (qty/ingresos por categoría en el tiempo, window functions).
- `04_peak_hours.py` — **horarios pico** (conteo por hora × día de semana).
- `05_monthly_growth.py` — **crecimiento mensual** (% var. mes a mes con `lag()`).
- `06_export_marts.py` — marts → `postgres-serving` (consumo de Superset).

### Requisitos técnicos
- Usar **DataFrames y SparkSQL** explícitamente (ambos, lo pide el enunciado).
- Driver JDBC de Postgres en el classpath de Spark.
- Conexión a Hive metastore configurada (`hive.metastore.uris`).

### Pasos
1. Configurar Spark con acceso a Hive metastore y driver JDBC.
2. Implementar extract → build_dw (idempotente, sobrescribe particiones).
3. Implementar los 3 análisis y guardarlos (Hive + marts).
4. Exportar marts a `postgres-serving`.

### Validación
```bash
docker compose exec spark-master spark-submit /opt/jobs/02_build_dw.py
docker compose exec spark-master spark-submit /opt/jobs/03_trends.py
# Verificar marts:
docker compose exec postgres-serving psql -U olap -d restaurantes_marts -c "\dt"
```

### ✅ Criterios de aceptación
- [ ] `fact_orders` y `fact_order_items` cargadas desde la fuente vía Spark.
- [ ] Los 3 análisis corren y producen salidas verificables.
- [ ] Se usan DataFrames **y** SparkSQL.
- [ ] Marts disponibles en `postgres-serving` para Superset.
- [ ] Jobs idempotentes (re-ejecutables sin duplicar).

---

## Fase 5 — Orquestación con Apache Airflow

**Objetivo:** un DAG modular y programado que integra todo el pipeline. (15%.)

### DAG (`airflow/dags/etl_olap_dag.py`)

```
extract_postgres ─▶ transform_spark ─▶ load_hive_dw ─▶ build_olap_cubes ─▶ export_marts
                                          │
        check_catalog_changed ──(branch)──┴─▶ reindex_elasticsearch
                                          └─▶ data_quality_checks
```

- `extract_postgres` → SparkSubmit `01_extract.py`
- `transform_spark` → SparkSubmit `02_build_dw.py`
- `load_hive_dw` / `build_olap_cubes` → beeline / HiveOperator
- `export_marts` → SparkSubmit `06_export_marts.py`
- `check_catalog_changed` → BranchPythonOperator (hash del catálogo de productos)
- `reindex_elasticsearch` → reindexa productos en ES **solo si cambió el catálogo**
- `data_quality_checks` → conteos/no-nulos/integridad referencial

### Configuración
- Executor: **LocalExecutor** (metadatos en `postgres-airflow`).
- Conexiones: `spark_default`, `postgres_oltp`, `elasticsearch_default`.
- `schedule_interval` (p. ej. `@daily`) → ejecución periódica.

### Validación
```bash
docker compose --profile orchestration up -d
# UI: http://localhost:8081
docker compose exec airflow-scheduler airflow dags list
docker compose exec airflow-scheduler airflow dags test etl_olap_dag 2024-01-01
```

### ✅ Criterios de aceptación
- [ ] DAG visible y sin errores de import en la UI.
- [ ] Las tareas corren en orden con dependencias correctas.
- [ ] La rama de reindex de ES se dispara solo si cambia el catálogo.
- [ ] DAG programado (no solo manual).
- [ ] Tareas modulares (una responsabilidad cada una).

---

## Fase 6 — Neo4J: grafo, Cypher y enrutamiento

**Objetivo:** modelar el grafo, consultas Cypher y simular/optimizar rutas. (15% + 10%.)

### Modelo de grafo
- **Nodos:** `User`, `Product`, `Order`, `Restaurant`, `Location` (geonodo), `Courier`.
- **Relaciones:**
  - `(:User)-[:PLACED]->(:Order)`
  - `(:Order)-[:CONTAINS]->(:Product)`
  - `(:Order)-[:DELIVERED_TO]->(:Location)`
  - `(:User)-[:RECOMMENDS]->(:User)`
  - `(:Location)-[:ROUTE {distance_km, time_min}]->(:Location)`
  - `(:Courier)-[:ASSIGNED]->(:Order)`

### Archivos
- `neo4j/import/*.csv` — exportados desde el OLTP (Fase 2/4).
- `neo4j/01_load_graph.cypher` — carga nodos y relaciones (`LOAD CSV`).
- `neo4j/02_queries.cypher` — consultas exigidas.
- `routing/route_assignment.py` — enrutamiento.

### Consultas Cypher exigidas
1. **Top-5 productos comprados juntos** (co-ocurrencia en pedidos).
2. **Usuarios que recomiendan a otros** (influencers por grado / PageRank con GDS).
3. **Caminos mínimos entre ubicaciones** (`shortestPath` / Dijkstra GDS).

### Enrutamiento (10%)
- Heurística **vecino más cercano** sobre entregas pendientes por repartidor, y/o `shortestPath` GDS.
- Salida: rutas optimizadas + asignación por repartidor (tabla/JSON, visualizable).

### Validación
```bash
docker compose --profile graph up -d
# Browser: http://localhost:7474
# Cargar grafo y correr consultas de 02_queries.cypher
python routing/route_assignment.py
```

### ✅ Criterios de aceptación
- [ ] Grafo cargado con nodos y relaciones del modelo.
- [ ] Las 3 consultas Cypher devuelven resultados coherentes.
- [ ] Módulo de enrutamiento produce rutas y asignación por repartidor.
- [ ] Diagrama del grafo en `docs/diagrams/`.

---

## Fase 7 — Visualización (Apache Superset)

**Objetivo:** mínimo 3 dashboards sobre los marts. (15%.)

### Dashboards exigidos
1. **Ingresos por mes y categoría de producto** ← `cube_revenue_month_category`.
2. **Actividad de clientes por zona geográfica** ← `cube_orders_by_zone`.
3. **Pedidos completados vs cancelados** ← `cube_orders_status`.

> (Extra recomendado: horarios pico y rendimiento de repartidores.)

### Pasos
1. Levantar Superset y conectarlo a `postgres-serving`.
2. Registrar datasets (los marts/cubos).
3. Construir charts y armar los 3 dashboards.
4. **Exportar** los dashboards (`superset/assets/`) → entregable importable.

### Validación
```bash
docker compose --profile viz up -d
# UI: http://localhost:8088  (admin/admin)
```

### ✅ Criterios de aceptación
- [ ] 3 dashboards funcionales y bien presentados.
- [ ] Conectados a los marts de `postgres-serving`.
- [ ] Dashboards exportados y reimportables.
- [ ] Capturas en `docs/diagrams/` o `docs/screenshots/`.

---

## Fase 8 — Documentación y demo

**Objetivo:** documento técnico en PDF + evidencia. (5%.)

### Contenido del documento (`docs/technical-doc.md` → exportar a PDF)
- Portada, objetivo y alcance.
- **Diagrama de arquitectura** (flujo de datos completo).
- **Modelo estrella** (dimensiones y hechos) + justificación.
- **Modelo del grafo** Neo4J.
- Decisiones de diseño (por qué Hive + serving Postgres, perfiles Docker, etc.).
- Ejemplos de uso: consultas OLAP, Cypher, salidas de Spark, DAG.
- Instrucciones de despliegue (resumen del README).
- Capturas de dashboards y del DAG.

### Entregables finales (según el PDF de la spec)
- [ ] Código fuente + DAG de Airflow.
- [ ] Scripts/notebooks de Spark.
- [ ] Dashboards exportables.
- [ ] Consultas Cypher + estructura del grafo.
- [ ] Capturas o video demostrativo.
- [ ] Documentación técnica en PDF.

### Empaquetado
- Entrega en **formato comprimido** antes de las 10:00 p.m. del día acordado.
- Penalización: **5% por cada 24 h** de retraso.

### ✅ Criterios de aceptación
- [ ] PDF técnico completo con diagramas y ejemplos.
- [ ] Todos los entregables presentes en el comprimido.
- [ ] README permite reproducir el despliegue de cero.

---

## Apéndice — Comandos rápidos (Makefile sugerido)

```makefile
up:       ## Levanta perfil core
	docker compose --profile core up -d
dw:       ## Levanta DW (Hive + Spark)
	docker compose --profile dw up -d
seed:     ## Genera datos OLTP
	python data-generator/generate.py
dag:      ## Levanta Airflow
	docker compose --profile orchestration up -d
graph:    ## Levanta Neo4J
	docker compose --profile graph up -d
viz:      ## Levanta Superset
	docker compose --profile viz up -d
down:     ## Apaga todo (conserva datos)
	docker compose down
clean:    ## Apaga y borra volúmenes
	docker compose down -v
```

---

## Estado de avance (actualizar conforme se desarrolla)

- [x] Fase 1 — Scaffolding e infraestructura
- [ ] Fase 2 — Generación de datos
- [ ] Fase 3 — Data Warehouse + OLAP (Hive)
- [ ] Fase 4 — Procesamiento Spark
- [ ] Fase 5 — Orquestación Airflow
- [ ] Fase 6 — Neo4J + enrutamiento
- [ ] Fase 7 — Visualización Superset
- [ ] Fase 8 — Documentación y demo
