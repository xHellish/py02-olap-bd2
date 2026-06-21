// =============================================================================
// 02_queries.cypher — Consultas Cypher requeridas por el enunciado
// Proyecto 2 OLAP — Restaurantes Guatemala
//
// Ejecutar consulta por consulta (separadas por ;) con:
//   docker compose exec neo4j cypher-shell -u neo4j -p neo4j123 \
//       -f /var/lib/neo4j/import/02_queries.cypher
// =============================================================================

// ─────────────────────────────────────────────────────────────────────────────
// CONSULTA 1: Top-5 productos comprados juntos (co-ocurrencia en pedidos)
// ─────────────────────────────────────────────────────────────────────────────
// Encuentra pares de productos que aparecen juntos en el mismo pedido.
// Útil para recomendaciones tipo "también compraron...".

MATCH (p1:Product)<-[:CONTAINS]-(o:Order)-[:CONTAINS]->(p2:Product)
WHERE p1.id < p2.id
WITH p1.name AS producto_1,
     p2.name AS producto_2,
     COUNT(DISTINCT o) AS pedidos_juntos
ORDER BY pedidos_juntos DESC
LIMIT 5
RETURN producto_1, producto_2, pedidos_juntos;

// ─────────────────────────────────────────────────────────────────────────────
// CONSULTA 2a: Usuarios influyentes — por grado de salida (degree)
// Cuántas personas recomienda implícitamente cada usuario (co-compras en
// el mismo restaurante → relación RECOMMENDS).
// ─────────────────────────────────────────────────────────────────────────────

MATCH (u:User)-[:RECOMMENDS]->(other:User)
WITH u.name AS usuario, u.zone AS zona,
     COUNT(DISTINCT other) AS usuarios_recomendados
ORDER BY usuarios_recomendados DESC
LIMIT 10
RETURN usuario, zona, usuarios_recomendados;

// ─────────────────────────────────────────────────────────────────────────────
// CONSULTA 2b: Usuarios influyentes — PageRank con GDS
// Requiere la proyección del subgrafo en memoria antes de ejecutar.
// ─────────────────────────────────────────────────────────────────────────────

// Crear proyección en memoria (si no existe)
CALL gds.graph.project.cypher(
    'user_recommends_graph',
    'MATCH (u:User) RETURN id(u) AS id',
    'MATCH (u1:User)-[:RECOMMENDS]->(u2:User) RETURN id(u1) AS source, id(u2) AS target'
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;

// Ejecutar PageRank
CALL gds.pageRank.stream('user_recommends_graph', {
    maxIterations: 20,
    dampingFactor:  0.85
})
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS u, score
ORDER BY score DESC
LIMIT 10
RETURN u.name AS usuario, u.zone AS zona,
       ROUND(score, 4) AS pagerank_score;

// Eliminar proyección de memoria
CALL gds.graph.drop('user_recommends_graph', false);

// ─────────────────────────────────────────────────────────────────────────────
// CONSULTA 3a: Camino más corto entre dos zonas (shortestPath nativo)
// ─────────────────────────────────────────────────────────────────────────────

MATCH (start:Location {zone: 'zona_1'}),
      (end:Location   {zone: 'antigua'})
MATCH path = shortestPath((start)-[:ROUTE*]-(end))
RETURN [n IN nodes(path) | n.zone]   AS ruta,
       [r IN relationships(path) | r.distance_km] AS distancias_km,
       REDUCE(total = 0.0, r IN relationships(path) | total + r.distance_km)
           AS distancia_total_km;

// ─────────────────────────────────────────────────────────────────────────────
// CONSULTA 3b: Dijkstra ponderado por distancia (GDS)
// ─────────────────────────────────────────────────────────────────────────────

// Proyección para algoritmos de ruta
CALL gds.graph.project.cypher(
    'zone_routing_graph',
    'MATCH (l:Location) RETURN id(l) AS id',
    'MATCH (l1:Location)-[r:ROUTE]->(l2:Location)
     RETURN id(l1) AS source, id(l2) AS target, r.distance_km AS distance_km'
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;

// Dijkstra desde zona_1 a zona_13
MATCH (start:Location {zone: 'zona_1'}),
      (end:Location   {zone: 'zona_13'})
CALL gds.shortestPath.dijkstra.stream('zone_routing_graph', {
    sourceNode:                id(start),
    targetNodes:               [id(end)],
    relationshipWeightProperty: 'distance_km'
})
YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs
RETURN
    [nodeId IN nodeIds | gds.util.asNode(nodeId).zone] AS ruta_zonas,
    costs                                               AS distancias_parciales_km,
    ROUND(totalCost, 2)                                 AS distancia_total_km;

// Limpiar proyección
CALL gds.graph.drop('zone_routing_graph', false);

// ─────────────────────────────────────────────────────────────────────────────
// CONSULTA EXTRA: Productos más populares por categoría
// ─────────────────────────────────────────────────────────────────────────────

MATCH (o:Order)-[c:CONTAINS]->(p:Product)
WITH p.category AS categoria, p.name AS producto,
     SUM(c.quantity) AS unidades_vendidas,
     COUNT(DISTINCT o) AS pedidos
ORDER BY categoria, unidades_vendidas DESC
WITH categoria,
     COLLECT({producto: producto, unidades: unidades_vendidas})[0..3] AS top3
RETURN categoria, top3;

// ─────────────────────────────────────────────────────────────────────────────
// CONSULTA EXTRA: Repartidores con más entregas y zona más frecuente
// ─────────────────────────────────────────────────────────────────────────────

MATCH (c:Courier)-[:ASSIGNED]->(o:Order)-[:DELIVERED_TO]->(l:Location)
WITH c.name AS repartidor, c.vehicle AS vehiculo, l.zone AS zona,
     COUNT(*) AS entregas
ORDER BY repartidor, entregas DESC
WITH repartidor, vehiculo,
     SUM(entregas) AS total_entregas,
     COLLECT(zona)[0] AS zona_mas_frecuente
ORDER BY total_entregas DESC
RETURN repartidor, vehiculo, total_entregas, zona_mas_frecuente;
