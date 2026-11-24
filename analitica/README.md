# Analítica (puntos 6, 7 y 8)

Consultas sobre las tablas de `derecho_trusted` (catálogo de Glue). Cada pregunta tiene su archivo versionado.
**Estado: escritas, NO ejecutadas.** Falta correrlas cuando `trusted/` tenga datos y validar los valores de control.

## Preguntas (solo corrida Thompson, `case1`)

| # | Pregunta | Motor | Archivo | Valor de control |
|---|---|---|---|---|
| P1 | Viento máximo a 10 m, hora y ciudad cercana | Athena | `athena/p1_viento_max.sql` | 34,12 m/s a las 18 UTC, cerca de Fort Wayne |
| P2 | Ciudades ordenadas por viento máximo, 12-20 UTC | Hive (EMR) | `hive/p2_ranking_ciudades.sql` | — |
| P3 | km² con viento severo (≥ 25,7 m/s) por hora | PySpark | `pyspark/p3_area_severa.py` | — |
| P4 | Lluvia acumulada máxima y ciudades con más lluvia | SparkSQL (EMR) | `sparksql/p4_lluvia.sql` | 113,8 mm (máximo del dominio) |
| P5 | Mayor caída de temperatura a 2 m en una hora | PySpark | `pyspark/p5_caida_temperatura.py` | — |
| P6 | Error (RMSE) del modelo vs ASOS y acierto de la hora del pico | PySpark | `pyspark/p6_error_asos.py` | — |
| P7 | Reportes del SPC que caen cerca de celdas con viento severo simulado | Athena | `athena/p7_spc_vs_modelo.sql` | — |

Cambio frente al documento maestro: con una sola corrida no hay comparación entre esquemas. P6 compara
contra lo observado, y P7 (antes "costo vs acierto") se reemplazó por la comparación con los reportes del SPC.

## Tablas que usan (base `derecho_trusted`)

| Tabla | Columnas relevantes |
|---|---|
| `wrf_superficie` (particiones `esquema`, `fecha`) | `hora, i, j, lat, lon, t2_c, viento_10m, lluvia_acum_mm, lluvia_hora_mm` |
| `ciudad_celda` | `esquema, tipo ('ciudad'/'estacion'), id_ubicacion, city_id, station_id, nombre, i, j, distancia_km` |
| `ciudades` | `city_id, name, state, lat, lon, population` |
| `estaciones`, `corridas` | datos de contexto de la RDS |
| `obs_asos` | `station_id, hora, hora_obs, desfase_min, viento_10m, rafaga_ms, lluvia_hora_mm, t2_c, presion_hpa` |
| `reportes_spc` | `hora, viento_mph, viento_ms, location, state, lat, lon` |

## Supuestos a decir en el informe

- Ventana de análisis 12-20 UTC del 2026-08-11 (la del reporte SCC26).
- "Cerca de una ciudad": P1 usa la ciudad de menor distancia (haversine) al punto del pico; P2, P4 y P5 usan la celda de malla más cercana a cada ciudad (`ciudad_celda`).
- Área: cada celda de d01 mide 3 km × 3 km = 9 km².
- ASOS reporta viento sostenido y WRF el instantáneo a la hora en punto; P6 compara contra el sostenido.
- P4: la lluvia de una celda es la suma de `lluvia_hora_mm` de las horas 13 a 20. Si no da 113,8 mm, probar incluir la hora 12 (variante B en el archivo).
- P7: "cerca" = ±0,1° (~10 km). Aproximación simple, no una distancia exacta.

## Cómo ejecutar

- **Athena:** pegar el `.sql` en el editor, workgroup `p2-derecho`, base `derecho_trusted`. Para guardar en `refined/` usar el `CREATE TABLE ... AS` comentado al final (cambiar `<BUCKET>`).
- **Hive:** en el nodo master de EMR, `beeline -u jdbc:hive2://localhost:10000 -f hive/p2_ranking_ciudades.sql`.
- **SparkSQL:** `spark-sql -f sparksql/p4_lluvia.sql` en el master de EMR.
- **PySpark:** como step de EMR (`spark-submit pyspark/p3_area_severa.py --BUCKET <bucket>`) o como job de Glue pasando `--BUCKET`.

## Pendiente de verificar al ejecutar

- Nombres de tablas y columnas contra el catálogo real (los de arriba salen del código de los jobs de preparación).
- Que `hora` quede como `timestamp` en el catálogo (las consultas lo asumen) y `fecha` como partición de texto.
- Hora de los reportes del SPC: el día convectivo del SPC va de 12 UTC a 12 UTC, así que revisar cómo asignó el job la fecha a los reportes posteriores a las 00 UTC.
- Valores de control de P1 (34,12 m/s) y P4 (113,8 mm).
