-- ─────────────────────────────────────────────────────────────────────────────
--  Fase 3 — Data Warehouse
--  00_create_db.hql  →  Crear la base de datos del DW en Hive
-- ─────────────────────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS restaurantes_dw
    COMMENT 'Data Warehouse — Proyecto 2 OLAP (Restaurantes GT)'
    WITH DBPROPERTIES (
        'project'  = 'PY02-OLAP',
        'version'  = '1.0',
        'created'  = '2026'
    );

USE restaurantes_dw;
