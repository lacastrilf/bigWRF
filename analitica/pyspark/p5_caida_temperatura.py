"""P5. Piscina fría: ¿dónde y a qué hora cayó más la temperatura a 2 m en una sola hora?

Usa una ventana lag por celda (esquema, i, j) ordenada por hora.
Salidas en refined/:
  p5_caida_ciudades/  -> mayor caida horaria en cada ciudad (celda mas cercana)
  p5_caida_dominio/   -> mayor caida horaria en todo el dominio
Ejecutar: spark-submit p5_caida_temperatura.py --BUCKET <bucket>
"""
import argparse

from pyspark.sql import SparkSession, Window, functions as F

p = argparse.ArgumentParser()
p.add_argument("--BUCKET", required=True)
args, _ = p.parse_known_args()
B = f"s3://{args.BUCKET}"

spark = SparkSession.builder.appName("p5_caida_temperatura").getOrCreate()
wrf = spark.read.parquet(f"{B}/trusted/wrf_superficie/")
celdas = spark.read.parquet(f"{B}/trusted/ciudad_celda/").filter(F.col("tipo") == "ciudad")

w = Window.partitionBy("esquema", "i", "j").orderBy("hora")

def con_cambio(df):
    return (df.withColumn("t2_anterior", F.lag("t2_c").over(w))
              .withColumn("hora_anterior", F.lag("hora").over(w))
              # solo pasos de exactamente una hora
              .filter(F.col("hora").cast("long") - F.col("hora_anterior").cast("long") == 3600)
              .withColumn("caida_c", F.col("t2_anterior") - F.col("t2_c")))

# --- Dominio completo ---
dom = con_cambio(wrf.select("esquema", "i", "j", "lat", "lon", "hora", "t2_c"))
r = Window.partitionBy("esquema").orderBy(F.col("caida_c").desc())
dominio = (dom.withColumn("rk", F.row_number().over(r)).filter("rk = 1")
              .select("esquema", "hora", "lat", "lon", "t2_anterior", "t2_c", "caida_c"))
dominio.show(truncate=False)
dominio.write.mode("overwrite").parquet(f"{B}/refined/p5_caida_dominio/")

# --- Por ciudad (solo las celdas de las ciudades) ---
sub = wrf.join(celdas.select("esquema", "i", "j", F.col("nombre").alias("ciudad")),
               ["esquema", "i", "j"])
w2 = Window.partitionBy("esquema", "ciudad").orderBy("hora")
ciu = (sub.withColumn("t2_anterior", F.lag("t2_c").over(w2))
          .withColumn("hora_anterior", F.lag("hora").over(w2))
          .filter(F.col("hora").cast("long") - F.col("hora_anterior").cast("long") == 3600)
          .withColumn("caida_c", F.col("t2_anterior") - F.col("t2_c")))
r2 = Window.partitionBy("esquema", "ciudad").orderBy(F.col("caida_c").desc())
ciudades = (ciu.withColumn("rk", F.row_number().over(r2)).filter("rk = 1")
               .select("esquema", "ciudad", "hora", "t2_anterior", "t2_c", "caida_c")
               .orderBy("esquema", F.col("caida_c").desc()))
ciudades.show(30, truncate=False)
ciudades.write.mode("overwrite").parquet(f"{B}/refined/p5_caida_ciudades/")
