-- P7. ¿Qué proporción de los reportes de viento del SPC cae cerca de celdas donde el
--     modelo simula viento severo (>= 25.7 m/s, umbral de 50 kt del NWS) en esa misma hora?
-- Motor: Athena.
-- Supuestos (documentar en el informe):
--   * "cerca" = dentro de +/-0.1 grados de lat y lon (~10 km), aproximación simple.
--   * La hora del reporte se redondea a la hora WRF mas cercana.
--   * Solo cuentan reportes con hora y coordenadas validas (ya filtrados en trusted).

WITH severas AS (
  SELECT esquema, hora, lat, lon
  FROM derecho_trusted.wrf_superficie
  WHERE fecha IN ('2026-08-11', '2026-08-12')
    AND viento_10m >= 25.7
),
reportes AS (
  SELECT date_trunc('hour', hora + INTERVAL '30' MINUTE) AS hora_h,
         lat, lon, viento_ms, location, state
  FROM derecho_trusted.reportes_spc
),
esquemas AS (
  SELECT DISTINCT esquema FROM derecho_trusted.corridas
),
cruce AS (
  SELECT e.esquema, r.hora_h, r.lat, r.lon, r.location, r.state,
         COUNT(s.lat) AS celdas_severas_cercanas
  FROM reportes r
  CROSS JOIN esquemas e
  LEFT JOIN severas s
    ON s.esquema = e.esquema
   AND s.hora = r.hora_h
   AND ABS(s.lat - r.lat) <= 0.1
   AND ABS(s.lon - r.lon) <= 0.1
  GROUP BY e.esquema, r.hora_h, r.lat, r.lon, r.location, r.state
)
SELECT esquema,
       COUNT(*)                                              AS reportes_spc,
       COUNT_IF(celdas_severas_cercanas > 0)                 AS con_celda_severa_cercana,
       ROUND(100.0 * COUNT_IF(celdas_severas_cercanas > 0) / COUNT(*), 1) AS porcentaje
FROM cruce
GROUP BY esquema;

