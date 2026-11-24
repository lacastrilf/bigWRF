"""P6. Contra lo observado: error (RMSE) del modelo en viento y lluvia horaria en las
estaciones ASOS, y acierto de la hora del pico de viento.

Cruce: obs_asos (hora redondeada) + ciudad_celda (celda WRF mas cercana a cada estacion) + wrf_superficie.
Supuestos (decir en el informe):
  * ASOS reporta viento SOSTENIDO (viento_10m) y rafaga; WRF da viento instantaneo a la hora en
    punto. Se compara contra el sostenido.
  * Si una estacion tiene varias observaciones en la misma hora se usa la mas cercana a la hora en punto.
  * Ventana de analisis: 12-20 UTC del 2026-08-11.
Salidas en refined/: p6_rmse/ (por esquema) y p6_hora_pico/ (por estacion).
Ejecutar: spark-submit p6_error_asos.py --BUCKET <bucket>
"""
import argparse

from pyspark.sql import SparkSession, Window, functions as F

p = argparse.ArgumentParser()
p.add_argument("--BUCKET", required=True)
args, _ = p.parse_known_args()
B = f"s3://{args.BUCKET}"

spark = SparkSession.builder.appName("p6_error_asos").getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")

INI, FIN = "2026-08-11 12:00:00", "2026-08-11 20:00:00"

wrf = (spark.read.parquet(f"{B}/trusted/wrf_superficie/")
       .filter((F.col("hora") >= INI) & (F.col("hora") <= FIN)))
est = (spark.read.parquet(f"{B}/trusted/ciudad_celda/").filter(F.col("tipo") == "estacion")
       .select("esquema", "station_id", "i", "j"))

# Modelo en la celda de cada estacion
mod = (wrf.join(est, ["esquema", "i", "j"])
          .select("esquema", "station_id", "hora",
                  F.col("viento_10m").alias("viento_mod"),
                  F.col("lluvia_hora_mm").alias("lluvia_mod")))

# Una observacion por estacion y hora (la mas cercana a la hora en punto)
obs = spark.read.parquet(f"{B}/trusted/obs_asos/")
w = Window.partitionBy("station_id", "hora").orderBy("desfase_min")
obs = (obs.withColumn("rn", F.row_number().over(w)).filter("rn = 1")
          .select("station_id", "hora",
                  F.col("viento_10m").alias("viento_obs"),
                  F.col("lluvia_hora_mm").alias("lluvia_obs")))

cruce = mod.join(obs, ["station_id", "hora"]).cache()

# ---- RMSE y sesgo por esquema ----
v = cruce.filter(F.col("viento_obs").isNotNull() & F.col("viento_mod").isNotNull())
l = cruce.filter(F.col("lluvia_obs").isNotNull() & F.col("lluvia_mod").isNotNull())
rmse_v = v.groupBy("esquema").agg(
    F.sqrt(F.avg(F.pow(F.col("viento_mod") - F.col("viento_obs"), 2))).alias("rmse_viento_ms"),
    F.avg(F.col("viento_mod") - F.col("viento_obs")).alias("sesgo_viento_ms"),
    F.count("*").alias("n_viento"))
rmse_l = l.groupBy("esquema").agg(
    F.sqrt(F.avg(F.pow(F.col("lluvia_mod") - F.col("lluvia_obs"), 2))).alias("rmse_lluvia_mm"),
    F.avg(F.col("lluvia_mod") - F.col("lluvia_obs")).alias("sesgo_lluvia_mm"),
    F.count("*").alias("n_lluvia"))
rmse = rmse_v.join(rmse_l, "esquema", "outer")
rmse.show(truncate=False)
rmse.write.mode("overwrite").parquet(f"{B}/refined/p6_rmse/")

# ---- Acierto de la hora del pico de viento, por estacion ----
def hora_pico(df, col, nombre):
    r = Window.partitionBy("esquema", "station_id").orderBy(F.col(col).desc_nulls_last())
    return (df.filter(F.col(col).isNotNull())
              .withColumn("rk", F.row_number().over(r)).filter("rk = 1")
              .select("esquema", "station_id", F.col("hora").alias(nombre)))

pico = (hora_pico(cruce, "viento_mod", "hora_pico_modelo")
        .join(hora_pico(cruce, "viento_obs", "hora_pico_obs"), ["esquema", "station_id"])
        .withColumn("error_horas",
                    (F.col("hora_pico_modelo").cast("long") - F.col("hora_pico_obs").cast("long")) / 3600.0))
pico.orderBy("esquema", "station_id").show(30, truncate=False)
pico.write.mode("overwrite").parquet(f"{B}/refined/p6_hora_pico/")
pico.agg(F.avg(F.abs("error_horas")).alias("error_abs_medio_horas"),
         F.avg((F.abs("error_horas") <= 1).cast("int")).alias("fraccion_dentro_de_1h")).show()
