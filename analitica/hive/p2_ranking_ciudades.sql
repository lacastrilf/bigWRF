-- P2. Ordenar las ciudades por viento máximo simulado entre 12 y 20 UTC.
-- Motor: Hive en EMR (con el Glue Data Catalog como metastore).
-- Ejecutar: beeline -u jdbc:hive2://localhost:10000 -f p2_ranking_ciudades.sql

SELECT w.esquema,
       c.nombre                          AS ciudad,
       ROUND(MAX(w.viento_10m), 2)       AS viento_max_ms,
       RANK() OVER (PARTITION BY w.esquema ORDER BY MAX(w.viento_10m) DESC) AS posicion
FROM derecho_trusted.wrf_superficie w
JOIN derecho_trusted.ciudad_celda c
  ON  w.esquema = c.esquema
  AND w.i = c.i
  AND w.j = c.j
  AND c.tipo = 'ciudad'
WHERE w.fecha = '2026-08-11'
  AND w.hora BETWEEN CAST('2026-08-11 12:00:00' AS TIMESTAMP)
                 AND CAST('2026-08-11 20:00:00' AS TIMESTAMP)
GROUP BY w.esquema, c.nombre
ORDER BY w.esquema, posicion;
