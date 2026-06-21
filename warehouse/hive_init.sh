#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  Fase 3 — Inicialización del esquema de Hive
#  Ejecutar desde el host una vez que hiveserver2 esté healthy:
#    bash warehouse/hive_init.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

CONTAINER="py02_hiveserver2"
BEELINE="docker exec -i $CONTAINER /opt/hive/bin/beeline -u jdbc:hive2://localhost:10000 -n hive -p '' --silent=true"

echo "[hive-init] Esperando que HiveServer2 acepte conexiones..."
for i in $(seq 1 30); do
    if docker exec "$CONTAINER" nc -z localhost 10000 2>/dev/null; then
        echo "[hive-init] HiveServer2 listo."
        break
    fi
    echo "  intento $i/30..."
    sleep 5
done

echo "[hive-init] Creando base de datos..."
$BEELINE -f /warehouse/00_create_db.hql

echo "[hive-init] Creando dimensiones..."
$BEELINE -f /warehouse/01_dimensions.hql

echo "[hive-init] Creando tablas de hechos..."
$BEELINE -f /warehouse/02_facts.hql

echo "[hive-init] Creando cubos OLAP (vistas)..."
$BEELINE -f /warehouse/03_olap_cubes.hql

echo "[hive-init] Verificando tablas creadas..."
docker exec "$CONTAINER" /opt/hive/bin/beeline \
    -u jdbc:hive2://localhost:10000/restaurantes_dw -n hive -p '' \
    --silent=false \
    -e "SHOW TABLES;"

echo "[hive-init] Esquema del DW inicializado correctamente."
