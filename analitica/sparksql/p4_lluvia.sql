-- P4. ¿Cuál fue la precipitación acumulada máxima del dominio y qué ciudades recibieron más lluvia?
-- Motor: SparkSQL (spark-sql en EMR, o spark.sql(...) en un job).
-- Valor de control (reporte SCC26, 12-20 UTC): Thompson 113.8 mm de máximo en el dominio.
--
-- Definicion usada: lluvia de una celda = suma de lluvia_hora_mm de las horas 13..20 UTC
-- (equivale a acumulado(20 UTC) - acumulado(12 UTC)). Si no coincide con 113.8 mm, probar la
-- variante B (horas 12..20, 9 incrementos) y dejar documentado cual coincide con el reporte.

-- Maximo del dominio y celda donde ocurre
WITH por_celda AS (
  SELECT esquema, i, j, lat, lon, SUM(lluvia_hora_mm) AS lluvia_mm
  FROM derecho_trusted.wrf_superficie
  WHERE fecha = '2026-08-11'
    AND hora >  TIMESTAMP '2026-08-11 12:00:00'   -- variante B: >=
    AND hora <= TIMESTAMP '2026-08-11 20:00:00'
  GROUP BY esquema, i, j, lat, lon
)
SELECT esquema, ROUND(lluvia_mm, 1) AS lluvia_max_mm, ROUND(lat, 2) AS lat, ROUND(lon, 2) AS lon
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY esquema ORDER BY lluvia_mm DESC) AS rk FROM por_celda
) t
WHERE rk = 1;

-- Ciudades que mas lluvia recibieron (celda mas cercana a cada ciudad)
WITH por_celda AS (
  SELECT esquema, i, j, SUM(lluvia_hora_mm) AS lluvia_mm
  FROM derecho_trusted.wrf_superficie
  WHERE fecha = '2026-08-11'
    AND hora >  TIMESTAMP '2026-08-11 12:00:00'
    AND hora <= TIMESTAMP '2026-08-11 20:00:00'
  GROUP BY esquema, i, j
)
SELECT c.esquema, c.nombre AS ciudad, ROUND(p.lluvia_mm, 1) AS lluvia_mm,
       RANK() OVER (PARTITION BY c.esquema ORDER BY p.lluvia_mm DESC) AS posicion
FROM derecho_trusted.ciudad_celda c
JOIN por_celda p ON p.esquema = c.esquema AND p.i = c.i AND p.j = c.j
WHERE c.tipo = 'ciudad'
ORDER BY c.esquema, posicion;
