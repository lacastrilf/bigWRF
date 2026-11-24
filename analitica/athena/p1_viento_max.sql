-- P1. ¿Cuál fue el viento máximo a 10 m, a qué hora y cerca de qué ciudad?
-- Motor: Athena. Ventana de análisis: 12-20 UTC del 2026-08-11.
-- Valor de control (reporte SCC26): Thompson 34.12 m/s a las 18 UTC, ~13 km de Fort Wayne, IN.
-- "Cerca de una ciudad" = ciudad de la tabla ciudades con menor distancia al punto del pico.

WITH ranked AS (
  SELECT esquema, hora, i, j, lat, lon, viento_10m,
         ROW_NUMBER() OVER (PARTITION BY esquema ORDER BY viento_10m DESC) AS rk
  FROM derecho_trusted.wrf_superficie
  WHERE fecha = '2026-08-11'
    AND hora BETWEEN TIMESTAMP '2026-08-11 12:00:00' AND TIMESTAMP '2026-08-11 20:00:00'
),
pico AS (
  SELECT * FROM ranked WHERE rk = 1
),
cercana AS (
  SELECT p.esquema, p.hora, p.lat, p.lon, p.viento_10m,
         c.name AS ciudad_cercana, c.state,
         great_circle_distance(p.lat, p.lon, c.lat, c.lon) AS distancia_km,
         ROW_NUMBER() OVER (
           PARTITION BY p.esquema
           ORDER BY great_circle_distance(p.lat, p.lon, c.lat, c.lon)
         ) AS rn
  FROM pico p
  CROSS JOIN derecho_trusted.ciudades c
)
SELECT esquema,
       hora,
       ROUND(viento_10m, 2)  AS viento_max_ms,
       ROUND(lat, 2)         AS lat,
       ROUND(lon, 2)         AS lon,
       ciudad_cercana,
       state,
       ROUND(distancia_km, 1) AS distancia_km
FROM cercana
WHERE rn = 1;
