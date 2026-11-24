"""SQL (Athena/Presto) de cada pregunta, parametrizado por los filtros de la app.

Todas leen de derecho_trusted. Los valores que vienen de widgets se validan o se
escapan antes de entrar al texto SQL.
"""

DB = "derecho_trusted"
AREA_CELDA_KM2 = 9.0  # d01 a 3 km -> 3 x 3 km


def q(texto):
    """Escapa comillas simples para meter un texto dentro de un literal SQL."""
    return str(texto).replace("'", "''")


def lista(valores):
    return ", ".join(f"'{q(v)}'" for v in valores)


def ts(dt):
    return f"TIMESTAMP '{dt:%Y-%m-%d %H:%M:%S}'"


def filtro_wrf(p, alias="w", inicio_exclusivo=False):
    """Filtro comun sobre wrf_superficie: particion (fecha), ventana de horas y esquemas."""
    a = f"{alias}." if alias else ""
    op = ">" if inicio_exclusivo else ">="
    return (
        f"{a}fecha IN ({lista(p['fechas'])}) "
        f"AND {a}hora {op} {ts(p['t0'])} AND {a}hora <= {ts(p['t1'])} "
        f"AND {a}esquema IN ({lista(p['esquemas'])})"
    )


def filtro_ciudades(p, columna="c.nombre"):
    if not p["ciudades"]:
        return ""
    return f"AND {columna} IN ({lista(p['ciudades'])})"


def p1(p):
    return f"""
WITH ranked AS (
  SELECT w.esquema, w.hora, w.lat, w.lon, w.viento_10m,
         ROW_NUMBER() OVER (PARTITION BY w.esquema ORDER BY w.viento_10m DESC) AS rk
  FROM {DB}.wrf_superficie w
  WHERE {filtro_wrf(p)}
),
pico AS (SELECT * FROM ranked WHERE rk = 1),
cercana AS (
  SELECT p.esquema, p.hora, p.lat, p.lon, p.viento_10m,
         c.name AS ciudad_cercana, c.state,
         great_circle_distance(p.lat, p.lon, c.lat, c.lon) AS distancia_km,
         ROW_NUMBER() OVER (PARTITION BY p.esquema
                            ORDER BY great_circle_distance(p.lat, p.lon, c.lat, c.lon)) AS rn
  FROM pico p CROSS JOIN {DB}.ciudades c
)
SELECT esquema, hora, ROUND(viento_10m, 2) AS viento_max_ms,
       ROUND(lat, 3) AS lat, ROUND(lon, 3) AS lon,
       ciudad_cercana, state, ROUND(distancia_km, 1) AS distancia_km
FROM cercana WHERE rn = 1
"""


def p1_horas(p):
    return f"""
SELECT w.esquema, w.hora, ROUND(MAX(w.viento_10m), 2) AS viento_max_ms
FROM {DB}.wrf_superficie w
WHERE {filtro_wrf(p)}
GROUP BY w.esquema, w.hora
ORDER BY w.hora
"""


def p2(p):
    return f"""
WITH mx AS (
  SELECT w.esquema, w.i, w.j, MAX(w.viento_10m) AS v, max_by(w.hora, w.viento_10m) AS hora_pico
  FROM {DB}.wrf_superficie w
  WHERE {filtro_wrf(p)}
  GROUP BY w.esquema, w.i, w.j
)
SELECT c.esquema, c.nombre AS ciudad, ROUND(m.v, 2) AS viento_max_ms, m.hora_pico,
       RANK() OVER (PARTITION BY c.esquema ORDER BY m.v DESC) AS posicion
FROM {DB}.ciudad_celda c
JOIN mx m ON m.esquema = c.esquema AND m.i = c.i AND m.j = c.j
WHERE c.tipo = 'ciudad' {filtro_ciudades(p)}
ORDER BY c.esquema, posicion
LIMIT {int(p['top'])}
"""


def p3(p):
    return f"""
SELECT w.esquema, w.hora,
       COUNT_IF(w.viento_10m >= {float(p['umbral'])}) AS celdas_severas,
       COUNT_IF(w.viento_10m >= {float(p['umbral'])}) * {AREA_CELDA_KM2} AS area_km2
FROM {DB}.wrf_superficie w
WHERE {filtro_wrf(p)}
GROUP BY w.esquema, w.hora
ORDER BY w.hora
"""


def _lluvia_por_celda(p):
    # Acumulado del periodo = suma de lluvia_hora_mm con inicio exclusivo (ver p4_lluvia.sql).
    return f"""
SELECT w.esquema, w.i, w.j, ARBITRARY(w.lat) AS lat, ARBITRARY(w.lon) AS lon,
       SUM(w.lluvia_hora_mm) AS lluvia_mm
FROM {DB}.wrf_superficie w
WHERE {filtro_wrf(p, inicio_exclusivo=True)}
GROUP BY w.esquema, w.i, w.j
"""


def p4_max(p):
    return f"""
WITH por_celda AS ({_lluvia_por_celda(p)})
SELECT esquema, ROUND(lluvia_mm, 1) AS lluvia_max_mm, ROUND(lat, 3) AS lat, ROUND(lon, 3) AS lon
FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY esquema ORDER BY lluvia_mm DESC) AS rk
      FROM por_celda) t
WHERE rk = 1
"""


def p4_ciudades(p):
    return f"""
WITH por_celda AS ({_lluvia_por_celda(p)})
SELECT c.esquema, c.nombre AS ciudad, ROUND(pc.lluvia_mm, 1) AS lluvia_mm,
       RANK() OVER (PARTITION BY c.esquema ORDER BY pc.lluvia_mm DESC) AS posicion
FROM {DB}.ciudad_celda c
JOIN por_celda pc ON pc.esquema = c.esquema AND pc.i = c.i AND pc.j = c.j
WHERE c.tipo = 'ciudad' {filtro_ciudades(p)}
ORDER BY c.esquema, posicion
LIMIT {int(p['top'])}
"""


def p5(p):
    return f"""
WITH s AS (
  SELECT c.esquema, c.nombre AS ciudad, w.hora, w.t2_c,
         LAG(w.t2_c) OVER (PARTITION BY c.esquema, c.nombre ORDER BY w.hora) AS t_prev
  FROM {DB}.ciudad_celda c
  JOIN {DB}.wrf_superficie w ON w.esquema = c.esquema AND w.i = c.i AND w.j = c.j
  WHERE c.tipo = 'ciudad' {filtro_ciudades(p)} AND {filtro_wrf(p)}
)
SELECT esquema, ciudad, hora, ROUND(t_prev, 2) AS t_antes_c, ROUND(t2_c, 2) AS t_despues_c,
       ROUND(t_prev - t2_c, 2) AS caida_c
FROM s WHERE t_prev IS NOT NULL
ORDER BY caida_c DESC
LIMIT {int(p['top'])}
"""


def _modelo_vs_asos(p, agrupar):
    sel = "m.esquema" + (", m.station_id" if agrupar == "estacion" else "")
    return f"""
WITH m AS (
  SELECT w.esquema, w.hora, c.station_id,
         w.viento_10m AS mv, w.lluvia_hora_mm AS mr, w.t2_c AS mt
  FROM {DB}.ciudad_celda c
  JOIN {DB}.wrf_superficie w ON w.esquema = c.esquema AND w.i = c.i AND w.j = c.j
  WHERE c.tipo = 'estacion' AND {filtro_wrf(p)}
),
o AS (
  SELECT station_id, hora, AVG(viento_10m) AS ov, AVG(lluvia_hora_mm) AS orr, AVG(t2_c) AS ot
  FROM {DB}.obs_asos
  WHERE hora >= {ts(p['t0'])} AND hora <= {ts(p['t1'])}
  GROUP BY station_id, hora
)
SELECT {sel}, COUNT(*) AS n,
       ROUND(SQRT(AVG(POW(m.mv - o.ov, 2))), 2) AS rmse_viento_ms,
       ROUND(AVG(m.mv - o.ov), 2)               AS sesgo_viento_ms,
       ROUND(SQRT(AVG(POW(m.mr - o.orr, 2))), 2) AS rmse_lluvia_mm,
       ROUND(SQRT(AVG(POW(m.mt - o.ot, 2))), 2)  AS rmse_temp_c
FROM m JOIN o ON o.station_id = m.station_id AND o.hora = m.hora
GROUP BY {sel}
ORDER BY {sel}
"""


def p6_global(p):
    return _modelo_vs_asos(p, "global")


def p6_estacion(p):
    return _modelo_vs_asos(p, "estacion")


def p7(p):
    return f"""
WITH severas AS (
  SELECT w.esquema, w.hora, w.lat, w.lon
  FROM {DB}.wrf_superficie w
  WHERE {filtro_wrf(p)} AND w.viento_10m >= {float(p['umbral'])}
),
reportes AS (
  SELECT date_trunc('hour', hora + INTERVAL '30' MINUTE) AS hora_h, lat, lon, viento_ms
  FROM {DB}.reportes_spc
  WHERE hora >= {ts(p['t0'])} AND hora <= {ts(p['t1'])}
    AND COALESCE(viento_ms, 0) >= {float(p['viento_min_spc'])}
),
esquemas AS (SELECT DISTINCT esquema FROM {DB}.corridas WHERE esquema IN ({lista(p['esquemas'])})),
cruce AS (
  SELECT e.esquema, r.hora_h, r.lat, r.lon, COUNT(s.lat) AS cercanas
  FROM reportes r CROSS JOIN esquemas e
  LEFT JOIN severas s
    ON s.esquema = e.esquema AND s.hora = r.hora_h
   AND ABS(s.lat - r.lat) <= {float(p['radio_grados'])}
   AND ABS(s.lon - r.lon) <= {float(p['radio_grados'])}
  GROUP BY e.esquema, r.hora_h, r.lat, r.lon
)
SELECT esquema, COUNT(*) AS reportes_spc,
       COUNT_IF(cercanas > 0) AS con_celda_severa_cercana,
       ROUND(100.0 * COUNT_IF(cercanas > 0) / COUNT(*), 1) AS porcentaje
FROM cruce GROUP BY esquema
"""


def explorador_mapa(p):
    col = p["variable"]
    lat0, lat1, lon0, lon1 = p["bbox"]
    return f"""
SELECT w.lat, w.lon, w.{col} AS valor
FROM {DB}.wrf_superficie w
WHERE w.fecha = '{p['hora']:%Y-%m-%d}' AND w.hora = {ts(p['hora'])}
  AND w.esquema = '{q(p['esquema'])}'
  AND w.{col} BETWEEN {float(p['vmin'])} AND {float(p['vmax'])}
  AND w.lat BETWEEN {lat0} AND {lat1} AND w.lon BETWEEN {lon0} AND {lon1}
ORDER BY w.{col} DESC
LIMIT {int(p['limite'])}
"""


def explorador_serie(p):
    col = p["variable"]
    return f"""
SELECT w.hora, c.nombre AS ciudad, w.{col} AS valor
FROM {DB}.ciudad_celda c
JOIN {DB}.wrf_superficie w ON w.esquema = c.esquema AND w.i = c.i AND w.j = c.j
WHERE c.tipo = 'ciudad' AND c.nombre IN ({lista(p['ciudades'])}) AND {filtro_wrf(p)}
ORDER BY w.hora
"""


SQL_CIUDADES = f"SELECT name FROM {DB}.ciudades ORDER BY name"
SQL_ESQUEMAS = f"SELECT DISTINCT esquema FROM {DB}.corridas ORDER BY esquema"
SQL_CIUDADES_GEO = f"SELECT name, lat, lon FROM {DB}.ciudades"
