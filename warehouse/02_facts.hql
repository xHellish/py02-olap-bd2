-- ─────────────────────────────────────────────────────────────────────────────
--  Fase 3 — Data Warehouse
--  02_facts.hql  →  2 tablas de hechos particionadas por año/mes
--
--  Poblar con: spark/jobs/02_build_dw.py (Fase 4)
-- ─────────────────────────────────────────────────────────────────────────────

USE restaurantes_dw;

SET hive.exec.dynamic.partition       = true;
SET hive.exec.dynamic.partition.mode  = nonstrict;
SET hive.exec.max.dynamic.partitions  = 500;

-- ── FACT ORDERS ───────────────────────────────────────────────────────────────
--  Granularidad: un registro por pedido
--  Medidas: total, item_count, distancia, ETA y tiempo real de entrega
--  Particionado por año + mes para acelerar queries de tendencia temporal
CREATE TABLE IF NOT EXISTS fact_orders (
    order_key         BIGINT  COMMENT 'Surrogate key (= order_id en este contexto)',
    order_id          INT     COMMENT 'PK natural OLTP',
    date_key          INT     COMMENT 'FK dim_date',
    time_key          INT     COMMENT 'FK dim_time (hora de la orden)',
    customer_key      INT     COMMENT 'FK dim_customer',
    restaurant_key    INT     COMMENT 'FK dim_restaurant',
    location_key      INT     COMMENT 'FK dim_location (zona de entrega; -1 si sin delivery)',
    courier_key       INT     COMMENT 'FK dim_courier (-1 si sin entrega)',
    -- Estado y pago
    status            STRING  COMMENT 'pending|confirmed|preparing|delivering|completed|cancelled',
    payment_method    STRING  COMMENT 'card|cash|wallet',
    -- Medidas del pedido
    total             DOUBLE  COMMENT 'Total del pedido en GTQ',
    item_count        INT     COMMENT 'Número de líneas de ítem en el pedido',
    -- Medidas de entrega (NULL cuando no hay entrega)
    distance_km       DOUBLE  COMMENT 'Kilómetros de entrega',
    eta_min           INT     COMMENT 'Tiempo estimado en minutos',
    delivery_time_min INT     COMMENT 'Tiempo real (delivered_ts − order_ts) en minutos',
    is_delivered      BOOLEAN COMMENT 'true si status IN (completed, delivering)'
)
COMMENT 'Tabla de hechos — pedidos (granularidad: 1 fila por pedido)'
PARTITIONED BY (year INT, month INT)
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');

-- ── FACT ORDER ITEMS ──────────────────────────────────────────────────────────
--  Granularidad: un registro por línea de ítem
--  Permite análisis a nivel de producto sin pasar por fact_orders
CREATE TABLE IF NOT EXISTS fact_order_items (
    item_key       BIGINT  COMMENT 'Surrogate key',
    order_id       INT     COMMENT 'FK natural al pedido OLTP',
    date_key       INT     COMMENT 'FK dim_date',
    time_key       INT     COMMENT 'FK dim_time',
    product_key    INT     COMMENT 'FK dim_product',
    category_key   INT     COMMENT 'FK dim_category',
    restaurant_key INT     COMMENT 'FK dim_restaurant',
    customer_key   INT     COMMENT 'FK dim_customer',
    -- Medidas
    quantity       INT,
    unit_price     DOUBLE  COMMENT 'Precio unitario en GTQ',
    line_total     DOUBLE  COMMENT 'quantity * unit_price'
)
COMMENT 'Tabla de hechos — líneas de ítem (granularidad: 1 fila por ítem de pedido)'
PARTITIONED BY (year INT, month INT)
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');
