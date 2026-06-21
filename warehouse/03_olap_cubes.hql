-- ─────────────────────────────────────────────────────────────────────────────
--  Fase 3 — Data Warehouse
--  03_olap_cubes.hql  →  6 cubos OLAP como vistas Hive
--
--  Ejecutar DESPUÉS de que Spark haya poblado fact_orders y fact_order_items.
--  Estas vistas son el punto de entrada para Superset y los marts de Spark.
-- ─────────────────────────────────────────────────────────────────────────────

USE restaurantes_dw;

-- ── CUBO 1: Ingresos por Mes y Categoría ─────────────────────────────────────
--  Dashboard: tendencia de revenue por categoría (gráfico de área apilada)
CREATE VIEW IF NOT EXISTS cube_revenue_month_category AS
SELECT
    d.year,
    d.month,
    d.month_name,
    CONCAT(CAST(d.year AS STRING), '-', LPAD(CAST(d.month AS STRING), 2, '0')) AS year_month,
    c.category_name,
    COUNT(DISTINCT fi.order_id)          AS order_count,
    SUM(fi.quantity)                     AS units_sold,
    ROUND(SUM(fi.line_total), 2)         AS revenue,
    ROUND(AVG(fi.line_total / fi.quantity), 2) AS avg_unit_price
FROM   fact_order_items fi
JOIN   dim_date     d ON fi.date_key    = d.date_key
JOIN   dim_category c ON fi.category_key = c.category_key
GROUP BY
    d.year, d.month, d.month_name,
    c.category_name;

-- ── CUBO 2: Pedidos y Revenue por Zona ───────────────────────────────────────
--  Dashboard: mapa de calor / choropleth por zona geográfica
CREATE VIEW IF NOT EXISTS cube_orders_by_zone AS
SELECT
    loc.zone,
    loc.zone_name,
    loc.lat,
    loc.lon,
    d.year,
    d.month,
    COUNT(*)                                                  AS order_count,
    SUM(CASE WHEN fo.is_delivered THEN 1 ELSE 0 END)         AS delivered_count,
    ROUND(AVG(fo.distance_km), 2)                            AS avg_distance_km,
    ROUND(AVG(fo.delivery_time_min), 1)                      AS avg_delivery_min,
    ROUND(SUM(fo.total), 2)                                  AS total_revenue,
    ROUND(AVG(fo.total), 2)                                  AS avg_ticket
FROM   fact_orders  fo
JOIN   dim_date     d   ON fo.date_key     = d.date_key
JOIN   dim_location loc ON fo.location_key = loc.location_key
GROUP BY
    loc.zone, loc.zone_name, loc.lat, loc.lon,
    d.year, d.month;

-- ── CUBO 3: Distribución de Estado de Pedidos ────────────────────────────────
--  Dashboard: comparativa completados vs cancelados (barras agrupadas por mes)
CREATE VIEW IF NOT EXISTS cube_order_status AS
SELECT
    d.year,
    d.month,
    d.month_name,
    CONCAT(CAST(d.year AS STRING), '-', LPAD(CAST(d.month AS STRING), 2, '0')) AS year_month,
    fo.status,
    fo.payment_method,
    COUNT(*)                    AS order_count,
    ROUND(SUM(fo.total), 2)    AS revenue,
    ROUND(AVG(fo.total), 2)    AS avg_ticket
FROM   fact_orders fo
JOIN   dim_date    d ON fo.date_key = d.date_key
GROUP BY
    d.year, d.month, d.month_name,
    fo.status, fo.payment_method;

-- ── CUBO 4: Horas Pico ────────────────────────────────────────────────────────
--  Dashboard: heatmap hora × día-de-semana (identificar picos operativos)
CREATE VIEW IF NOT EXISTS cube_peak_hours AS
SELECT
    t.hour,
    t.time_label,
    t.time_of_day,
    d.day_of_week,
    d.day_name,
    d.is_weekend,
    COUNT(*)                    AS order_count,
    ROUND(SUM(fo.total), 2)    AS revenue,
    ROUND(AVG(fo.total), 2)    AS avg_ticket,
    ROUND(AVG(fo.item_count), 1) AS avg_items_per_order
FROM   fact_orders fo
JOIN   dim_time    t ON fo.time_key = t.time_key
JOIN   dim_date    d ON fo.date_key = d.date_key
GROUP BY
    t.hour, t.time_label, t.time_of_day,
    d.day_of_week, d.day_name, d.is_weekend;

-- ── CUBO 5: Ranking de Productos ─────────────────────────────────────────────
--  Input para Neo4J co-compra y dashboard de productos estrella
CREATE VIEW IF NOT EXISTS cube_product_ranking AS
SELECT
    p.product_name,
    p.category_name,
    p.unit_price                              AS current_price,
    COUNT(DISTINCT fi.order_id)               AS orders_containing,
    SUM(fi.quantity)                          AS units_sold,
    ROUND(SUM(fi.line_total), 2)              AS total_revenue,
    ROUND(AVG(fi.unit_price), 2)              AS avg_sold_price,
    ROUND(SUM(fi.line_total) / SUM(fi.quantity), 2) AS revenue_per_unit
FROM   fact_order_items fi
JOIN   dim_product      p ON fi.product_key = p.product_key
GROUP BY
    p.product_name, p.category_name, p.unit_price;

-- ── CUBO 6: Desempeño de Repartidores ───────────────────────────────────────
--  KPIs operacionales por repartidor (eficiencia, distancia, tiempo)
CREATE VIEW IF NOT EXISTS cube_courier_performance AS
SELECT
    c.courier_name,
    c.vehicle,
    c.base_zone,
    COUNT(*)                                               AS total_assignments,
    SUM(CASE WHEN fo.status = 'completed'  THEN 1 ELSE 0 END) AS completed,
    SUM(CASE WHEN fo.status = 'delivering' THEN 1 ELSE 0 END) AS in_transit,
    ROUND(AVG(fo.distance_km), 2)                         AS avg_distance_km,
    ROUND(AVG(fo.eta_min), 1)                             AS avg_eta_min,
    ROUND(AVG(fo.delivery_time_min), 1)                   AS avg_real_time_min,
    ROUND(AVG(fo.delivery_time_min) - AVG(fo.eta_min), 1) AS avg_delay_min,
    ROUND(SUM(fo.total), 2)                               AS total_revenue_handled
FROM   fact_orders fo
JOIN   dim_courier c ON fo.courier_key = c.courier_key
WHERE  fo.courier_key > 0
GROUP BY
    c.courier_name, c.vehicle, c.base_zone;
