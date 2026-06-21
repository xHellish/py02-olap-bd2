-- ─────────────────────────────────────────────────────────────────────────────
--  Fase 3 — Data Warehouse
--  01_dimensions.hql  →  8 tablas de dimensión del esquema estrella
--
--  Poblar con: spark/jobs/02_build_dw.py (Fase 4)
-- ─────────────────────────────────────────────────────────────────────────────

USE restaurantes_dw;

-- ── DIM DATE ─────────────────────────────────────────────────────────────────
--  Granularidad: un registro por día del período (jul-2025 → jun-2026)
--  Spark la genera con una secuencia de fechas; no se extrae del OLTP.
CREATE TABLE IF NOT EXISTS dim_date (
    date_key      INT     COMMENT 'Surrogate key YYYYMMDD',
    full_date     DATE    COMMENT 'Fecha calendario',
    year          INT,
    quarter       INT,
    semester      INT     COMMENT '1 = ene-jun, 2 = jul-dic',
    month         INT,
    month_name    STRING,
    week_of_year  INT,
    day_of_month  INT,
    day_of_week   INT     COMMENT '1=lunes … 7=domingo',
    day_name      STRING,
    is_weekend    BOOLEAN
)
COMMENT 'Dimensión de fecha (calendario)'
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');

-- ── DIM TIME ─────────────────────────────────────────────────────────────────
--  Granularidad: una fila por hora (0-23). Spark la pre-genera en el ETL.
CREATE TABLE IF NOT EXISTS dim_time (
    time_key    INT    COMMENT 'Hora del día 0-23',
    hour        INT,
    time_label  STRING COMMENT '"00:00" ... "23:00"',
    time_of_day STRING COMMENT 'madrugada|mañana|almuerzo|tarde|cena|noche'
)
COMMENT 'Dimensión de hora del día'
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');

-- ── DIM CATEGORY ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_category (
    category_key  INT    COMMENT 'Surrogate key',
    category_id   INT    COMMENT 'PK natural OLTP',
    category_name STRING,
    description   STRING,
    icon          STRING
)
COMMENT 'Dimensión de categoría de producto'
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');

-- ── DIM PRODUCT ──────────────────────────────────────────────────────────────
--  SCD Tipo 1 — precio vigente (no se guarda historia de precios)
CREATE TABLE IF NOT EXISTS dim_product (
    product_key   INT     COMMENT 'Surrogate key',
    product_id    INT     COMMENT 'PK natural OLTP',
    product_name  STRING,
    category_key  INT     COMMENT 'FK dim_category',
    category_name STRING  COMMENT 'Desnormalizado para queries sin JOIN',
    unit_price    DOUBLE,
    available     BOOLEAN
)
COMMENT 'Dimensión de producto (SCD Tipo 1)'
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');

-- ── DIM CUSTOMER ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key  INT    COMMENT 'Surrogate key',
    user_id       INT    COMMENT 'PK natural OLTP',
    user_name     STRING,
    email         STRING,
    zone          STRING COMMENT 'Zona residencial del cliente',
    lat           DOUBLE,
    lon           DOUBLE
)
COMMENT 'Dimensión de cliente'
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');

-- ── DIM RESTAURANT ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_restaurant (
    restaurant_key INT    COMMENT 'Surrogate key',
    restaurant_id  INT    COMMENT 'PK natural OLTP',
    rest_name      STRING,
    address        STRING,
    zone           STRING,
    lat            DOUBLE,
    lon            DOUBLE,
    rating         DOUBLE
)
COMMENT 'Dimensión de restaurante'
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');

-- ── DIM LOCATION ─────────────────────────────────────────────────────────────
--  Zonas de Ciudad de Guatemala + Antigua (destinos de entrega)
CREATE TABLE IF NOT EXISTS dim_location (
    location_key INT    COMMENT 'Surrogate key',
    zone         STRING COMMENT 'Código de zona (ej: zona_10)',
    zone_name    STRING COMMENT 'Nombre legible (ej: Zona 10)',
    lat          DOUBLE COMMENT 'Latitud centroide de la zona',
    lon          DOUBLE COMMENT 'Longitud centroide de la zona'
)
COMMENT 'Dimensión de zona geográfica de entrega'
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');

-- ── DIM COURIER ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_courier (
    courier_key  INT    COMMENT 'Surrogate key',
    courier_id   INT    COMMENT 'PK natural OLTP',
    courier_name STRING,
    vehicle      STRING COMMENT 'moto|bicicleta|carro',
    base_zone    STRING
)
COMMENT 'Dimensión de repartidor'
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');
