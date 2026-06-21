// =============================================================================
// 01_load_graph.cypher — Carga del grafo en Neo4J
// Proyecto 2 OLAP — Restaurantes Guatemala
//
// Ejecutar con:
//   docker compose exec neo4j cypher-shell -u neo4j -p neo4j123 \
//       -f /var/lib/neo4j/import/01_load_graph.cypher
//
// Requiere que los CSVs estén en /var/lib/neo4j/import/ (generados por export_csvs.py)
// =============================================================================

// ── Limpiar grafo anterior ────────────────────────────────────────────────────
MATCH (n) DETACH DELETE n;

// ── Índices ───────────────────────────────────────────────────────────────────
CREATE INDEX user_id_idx         IF NOT EXISTS FOR (u:User)       ON (u.id);
CREATE INDEX restaurant_id_idx   IF NOT EXISTS FOR (r:Restaurant) ON (r.id);
CREATE INDEX product_id_idx      IF NOT EXISTS FOR (p:Product)    ON (p.id);
CREATE INDEX order_id_idx        IF NOT EXISTS FOR (o:Order)      ON (o.id);
CREATE INDEX courier_id_idx      IF NOT EXISTS FOR (c:Courier)    ON (c.id);
CREATE INDEX location_zone_idx   IF NOT EXISTS FOR (l:Location)   ON (l.zone);

// ── Nodos: Users ─────────────────────────────────────────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///users.csv' AS row
CREATE (u:User {
    id:    toInteger(row.user_id),
    name:  row.name,
    email: row.email,
    role:  row.role,
    zone:  row.zone,
    lat:   CASE row.lat WHEN '' THEN null ELSE toFloat(row.lat) END,
    lon:   CASE row.lon WHEN '' THEN null ELSE toFloat(row.lon) END
});

// ── Nodos: Restaurants ───────────────────────────────────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///restaurants.csv' AS row
CREATE (r:Restaurant {
    id:      toInteger(row.rest_id),
    name:    row.name,
    address: row.address,
    zone:    row.zone,
    lat:     CASE row.lat WHEN '' THEN null ELSE toFloat(row.lat) END,
    lon:     CASE row.lon WHEN '' THEN null ELSE toFloat(row.lon) END,
    rating:  CASE row.rating WHEN '' THEN null ELSE toFloat(row.rating) END
});

// ── Nodos: Products ──────────────────────────────────────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///products.csv' AS row
CREATE (p:Product {
    id:        toInteger(row.prod_id),
    name:      row.name,
    price:     toFloat(row.price),
    available: (row.available = 'True'),
    category:  row.category
});

// ── Nodos: Couriers ──────────────────────────────────────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///couriers.csv' AS row
CREATE (c:Courier {
    id:        toInteger(row.courier_id),
    name:      row.name,
    vehicle:   row.vehicle,
    base_zone: row.base_zone
});

// ── Nodos: Locations (zonas) ─────────────────────────────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///locations.csv' AS row
CREATE (l:Location {
    zone:      row.zone,
    zone_name: row.zone_name,
    lat:       toFloat(row.lat),
    lon:       toFloat(row.lon)
});

// ── Nodos: Orders ────────────────────────────────────────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///orders.csv' AS row
CREATE (o:Order {
    id:             toInteger(row.order_id),
    status:         row.status,
    total:          toFloat(row.total),
    payment_method: row.payment_method,
    order_ts:       row.order_ts
});

// ── Relaciones: User PLACED Order ────────────────────────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///orders.csv' AS row
MATCH (u:User      {id: toInteger(row.user_id)})
MATCH (o:Order     {id: toInteger(row.order_id)})
MERGE (u)-[:PLACED]->(o);

// ── Relaciones: Order FROM_RESTAURANT Restaurant ─────────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///orders.csv' AS row
MATCH (o:Order      {id: toInteger(row.order_id)})
MATCH (r:Restaurant {id: toInteger(row.rest_id)})
MERGE (o)-[:FROM_RESTAURANT]->(r);

// ── Relaciones: Order CONTAINS Product ───────────────────────────────────────
LOAD CSV WITH HEADERS FROM 'file:///order_items.csv' AS row
CALL {
    WITH row
    MATCH (o:Order   {id: toInteger(row.order_id)})
    MATCH (p:Product {id: toInteger(row.prod_id)})
    MERGE (o)-[c:CONTAINS]->(p)
    SET c.quantity   = toInteger(row.quantity),
        c.unit_price = toFloat(row.unit_price),
        c.line_total = toFloat(row.line_total)
} IN TRANSACTIONS OF 500 ROWS;

// ── Relaciones: Order DELIVERED_TO Location + Courier ASSIGNED Order ─────────
LOAD CSV WITH HEADERS FROM 'file:///deliveries.csv' AS row
MATCH (o:Order  {id: toInteger(row.order_id)})
MATCH (l:Location {zone: row.dest_zone})
MERGE (o)-[dt:DELIVERED_TO]->(l)
SET dt.distance_km = CASE row.distance_km WHEN '' THEN null ELSE toFloat(row.distance_km) END,
    dt.eta_min     = CASE row.eta_min     WHEN '' THEN null ELSE toFloat(row.eta_min)     END,
    dt.status      = row.status;

LOAD CSV WITH HEADERS FROM 'file:///deliveries.csv' AS row
WITH row WHERE row.courier_id IS NOT NULL AND row.courier_id <> ''
MATCH (c:Courier {id: toInteger(row.courier_id)})
MATCH (o:Order   {id: toInteger(row.order_id)})
MERGE (c)-[:ASSIGNED]->(o);

// ── Relaciones: User RECOMMENDS User (co-clientes del mismo restaurante) ──────
LOAD CSV WITH HEADERS FROM 'file:///user_recommendations.csv' AS row
MATCH (u1:User {id: toInteger(row.from_user)})
MATCH (u2:User {id: toInteger(row.to_user)})
MERGE (u1)-[:RECOMMENDS]->(u2);

// ── Relaciones: Location ROUTE Location (grafo de zonas con peso) ─────────────
LOAD CSV WITH HEADERS FROM 'file:///zone_routes.csv' AS row
MATCH (l1:Location {zone: row.from_zone})
MATCH (l2:Location {zone: row.to_zone})
MERGE (l1)-[r:ROUTE]->(l2)
    SET r.distance_km = toFloat(row.distance_km),
        r.time_min    = toFloat(row.time_min)
MERGE (l2)-[r2:ROUTE]->(l1)
    SET r2.distance_km = toFloat(row.distance_km),
        r2.time_min    = toFloat(row.time_min);

// ── Resumen del grafo ─────────────────────────────────────────────────────────
MATCH (n) RETURN labels(n)[0] AS tipo, COUNT(n) AS nodos ORDER BY nodos DESC;
