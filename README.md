# Proyecto 2 — Análisis y Procesamiento OLAP

**Curso:** Base de Datos 2 — TEC, Sede Central Cartago  
**Dominio:** Sistema de restaurantes con pedidos, entregas y geolocalización

---

## Prerequisitos

| Requisito | Mínimo |
|---|---|
| Docker Desktop | 24+ (con Docker Compose v2) |
| RAM disponible | **12 GB** (stack completo) / **6 GB** (perfil `core + dw`) |
| Python | 3.11+ (solo para el generador de datos) |

> El Proyecto 1 (`Proyecto1/`) es referencia. No se levanta aquí.

---

## Arquitectura

```
                     ┌──────────────────────────────────────────────────┐
                     │                  Apache Airflow                    │
                     │           DAG: etl_olap_dag (diario)               │
                     └───┬──────────┬──────────┬──────────┬─────────────┘
                         │ extract  │ transform │   load   │ reindex (cond.)
       ┌──────────────┐  ▼          ▼           ▼          ▼
       │  FUENTE OLTP │──► Spark ──► Hive DW ──► Postgres ──► Elasticsearch
       │  Postgres +  │    3.5     (estrella)  (serving)
       │  Mongo       │
       └──────┬───────┘
              │ CSV export
              ▼
       ┌──────────────┐       ┌──────────────────┐
       │    Neo4J     │       │  Apache Superset   │
       │ grafo+rutas  │       │   3 dashboards     │
       └──────────────┘       └──────────────────┘
```

---

## Perfiles Docker Compose

El stack se divide en **perfiles** para evitar agotar la RAM:

| Perfil | Servicios | RAM aprox. |
|---|---|---|
| `core` | postgres-oltp, mongo, elasticsearch | ~2 GB |
| `dw` | hive-metastore, hiveserver2, spark-master, spark-worker | ~4 GB |
| `orchestration` | postgres-airflow, airflow-init, airflow-webserver, airflow-scheduler | ~2 GB |
| `graph` | neo4j (con GDS) | ~2 GB |
| `viz` | postgres-serving, superset | ~1 GB |

---

## Orden de despliegue

### 1. Preparar variables de entorno

```bash
cp .env.example .env
# Editar .env si se necesitan credenciales distintas
```

### 2. Levantar la fuente de datos (Core)

```bash
docker compose --profile core up -d
docker compose ps   # postgres-oltp, mongo, elasticsearch → healthy
```

### 3. Generar datos históricos

```bash
# Requiere Python 3.11+ con las dependencias instaladas
pip install -r data-generator/requirements.txt
python data-generator/generate.py

# O con el atajo:
make seed
```

Genera ~20.000 pedidos distribuidos en 12 meses de historia.

### 4. Levantar el Data Warehouse (Hive + Spark)

```bash
docker compose --profile dw up -d
# Esperar ~60s a que Hive metastore inicialice, luego:
make hive-init      # aplica DDL (dimensiones, hechos, cubos)
```

### 5. Correr el pipeline ETL con Spark

```bash
# Manualmente:
make spark-job JOB=01_extract.py
make spark-job JOB=02_build_dw.py
make spark-job JOB=03_trends.py
make spark-job JOB=04_peak_hours.py
make spark-job JOB=05_monthly_growth.py
make spark-job JOB=06_export_marts.py
```

### 6. Levantar Airflow (orquestación)

```bash
docker compose --profile orchestration up -d
# UI: http://localhost:8081  (admin / admin)
```

### 7. Levantar Neo4J y cargar el grafo

```bash
docker compose --profile graph up -d
# Browser: http://localhost:7474  (neo4j / neo4j123)
make neo4j-load
python routing/route_assignment.py
```

### 8. Levantar Superset (visualización)

```bash
docker compose --profile viz up -d
make superset-init  # primera vez
# UI: http://localhost:8088  (admin / admin)
```

### Stack completo (suficiente RAM)

```bash
make up-all
```

---

## URLs de acceso

| Servicio | URL | Credenciales |
|---|---|---|
| Spark Master UI | http://localhost:8080 | — |
| HiveServer2 Web | http://localhost:10002 | — |
| Airflow UI | http://localhost:8081 | admin / admin |
| Neo4J Browser | http://localhost:7474 | neo4j / neo4j123 |
| Superset | http://localhost:8088 | admin / admin |
| Elasticsearch | http://localhost:9200 | — |

---

## Comandos útiles

```bash
make ps          # Estado de contenedores
make logs        # Logs en tiempo real (tail 50)
make down        # Apagar (conserva datos)
make clean       # Apagar y borrar volúmenes (reset total)
make validate    # Health checks rápidos
```

---

## Estructura del proyecto

```
Proyecto 2 OLAP/
├── docker-compose.yml
├── .env / .env.example
├── Makefile
├── README.md
├── PLAN_IMPLEMENTACION.md  # Plan detallado por fases
├── data-generator/         # Fase 2: generador de datos OLTP + historia
├── warehouse/              # Fase 3: DDL Hive (esquema estrella + cubos)
├── spark/jobs/             # Fase 4: jobs PySpark (ETL + análisis)
├── airflow/dags/           # Fase 5: DAG de orquestación
├── neo4j/                  # Fase 6: grafo y consultas Cypher
├── routing/                # Fase 6: módulo de enrutamiento
├── superset/assets/        # Fase 7: dashboards exportables
└── docs/                   # Fase 8: documentación técnica + diagramas
```

---

## Componentes y pesos de evaluación

| Componente | % | Tecnología |
|---|---|---|
| Data Warehouse + OLAP | 20 | Apache Hive, esquema estrella, 5+ cubos |
| Procesamiento con Spark | 20 | PySpark DataFrames + SparkSQL, 3 análisis |
| Visualización | 15 | Apache Superset, 3 dashboards |
| Orquestación | 15 | Apache Airflow, DAG modular |
| Neo4J + Grafos | 15 | Neo4J 5 + GDS, Cypher |
| Enrutamiento | 10 | Vecino más cercano / shortestPath |
| Documentación | 5 | PDF técnico con diagramas |
