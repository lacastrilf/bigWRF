-- Evidencia del punto 5 (catálogo con Hive): tabla externa escrita a mano sobre refined/.
-- Requiere que el job de PySpark p3_area_severa.py ya haya escrito en refined/p3_area_severa/.
-- Reemplaza <BUCKET> por el nombre del bucket.

CREATE DATABASE IF NOT EXISTS derecho_refined;

CREATE EXTERNAL TABLE IF NOT EXISTS derecho_refined.p3_area_severa_hive (
  esquema         STRING,
  hora            TIMESTAMP,
  celdas_severas  BIGINT,
  area_km2        DOUBLE
)
STORED AS PARQUET
LOCATION 's3://<BUCKET>/refined/p3_area_severa/';

SELECT * FROM derecho_refined.p3_area_severa_hive ORDER BY hora LIMIT 10;
