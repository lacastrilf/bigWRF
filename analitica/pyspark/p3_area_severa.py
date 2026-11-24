"""P3. ¿Cuántos km² del dominio tuvieron viento severo (>= 25.7 m/s) en cada hora?

Cada celda de d01 mide 3 km x 3 km = 9 km2, asi que area = celdas severas * 9.
Corre como job de Glue o como step de EMR:  spark-submit p3_area_severa.py --BUCKET <bucket>
Salida: s3://<BUCKET>/refined/p3_area_severa/ (Parquet) y una tabla impresa.
"""
import argparse

from pyspark.sql import SparkSession, functions as F

UMBRAL_MS = 25.7     
AREA_CELDA_KM2 = 9.0  

p = argparse.ArgumentParser()
p.add_argument("--BUCKET", required=True)
args, _ = p.parse_known_args()  

spark = SparkSession.builder.appName("p3_area_severa").getOrCreate()
wrf = spark.read.parquet(f"s3://{args.BUCKET}/trusted/wrf_superficie/")

res = (
    wrf.groupBy("esquema", "hora")
       .agg(F.sum(F.when(F.col("viento_10m") >= UMBRAL_MS, 1).otherwise(0)).alias("celdas_severas"))
       .withColumn("area_km2", F.col("celdas_severas") * F.lit(AREA_CELDA_KM2))
       .orderBy("esquema", "hora")
)

res.show(60, truncate=False)
res.write.mode("overwrite").parquet(f"s3://{args.BUCKET}/refined/p3_area_severa/")
