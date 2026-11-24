import sys
import os
import math
import boto3
import tempfile
import numpy as np

from netCDF4 import Dataset, chartostring
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# 1. Configuracion de AWS Glue
args = getResolvedOptions(sys.argv, [
    "JOB_NAME", "BUCKET", "INPUT_PREFIX", "OUTPUT_PREFIX"
])
BUCKET = args["BUCKET"]
INPUT_PREFIX = args["INPUT_PREFIX"]
OUTPUT = f's3://{BUCKET}/{args["OUTPUT_PREFIX"]}'

sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

spark.conf.set("spark.sql.session.timeZone", "UTC")
spark.conf.set("spark.sql.shuffle.partitions", "32")
sc.setLogLevel("WARN")

# 2. Identificar archivos NetCDF en S3
s3 = boto3.client("s3")
files = []
for page in s3.get_paginator("list_objects_v2").paginate(
    Bucket=BUCKET, Prefix=INPUT_PREFIX
):
    for obj in page.get("Contents", []):
        key = obj["Key"]
        if os.path.basename(key).startswith("wrfout_d01_"):
            files.append(key)

if not files:
    raise RuntimeError("No se encontraron archivos WRF")
print(f"Archivos encontrados: {len(files)}")
for key in files:
    print(key)

# 3. Lectura distribuida de NetCDF
# Cada tarea descarga y procesa un archivo a la vez.
def procesar_archivos(keys):
    client = boto3.client("s3")
    variables = ["XLAT", "XLONG", "T2", "U10", "V10", "RAINC", "RAINNC"]

    def numero(valor):
        valor = float(valor)
        return valor if math.isfinite(valor) else None

    for key in keys:
        esquema = key.split("esquema=")[1].split("/")[0]
        print(f"Procesando: {key}")

        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "wrf.nc")
            client.download_file(BUCKET, key, ruta)

            with Dataset(ruta, "r") as nc:
                tiempos = chartostring(nc.variables["Times"][:])
                ny = len(nc.dimensions["south_north"])
                nx = len(nc.dimensions["west_east"])

                for t, tiempo in enumerate(tiempos):
                    hora = str(tiempo).replace("_", " ")
                    datos = {
                        v: np.ma.asarray(
                            nc.variables[v][t, :, :], dtype=np.float64
                        ).filled(np.nan).ravel()
                        for v in variables
                    }

                    for j in range(ny):
                        for i in range(nx):
                            idx = j * nx + i
                            yield (
                                esquema, hora, i, j,
                                numero(datos["XLAT"][idx]),
                                numero(datos["XLONG"][idx]),
                                numero(datos["T2"][idx]),
                                numero(datos["U10"][idx]),
                                numero(datos["V10"][idx]),
                                numero(datos["RAINC"][idx]),
                                numero(datos["RAINNC"][idx])
                            )

# 4. Crear DataFrame distribuido
schema = """
    esquema STRING, hora STRING, i INT, j INT,
    lat DOUBLE, lon DOUBLE, t2 DOUBLE,
    u10 DOUBLE, v10 DOUBLE, rainc DOUBLE, rainnc DOUBLE
"""
rdd = sc.parallelize(files, len(files)).mapPartitions(procesar_archivos)
df = spark.createDataFrame(rdd, schema)
df = df.withColumn("hora", F.to_timestamp("hora", "yyyy-MM-dd HH:mm:ss"))
df = df.withColumn("fecha", F.date_format("hora", "yyyy-MM-dd"))

# 5. Transformaciones meteorologicas
df = (
    df.withColumn("t2_c", F.col("t2") - 273.15)
      .withColumn("viento_10m", F.sqrt(F.pow("u10", 2) + F.pow("v10", 2)))
      .withColumn("lluvia_acum_mm", F.col("rainc") + F.col("rainnc"))
)

# 6. Precipitacion horaria por esquema y celda
ventana = Window.partitionBy("esquema", "i", "j").orderBy("hora")
df = (
    df.withColumn("lluvia_anterior", F.lag("lluvia_acum_mm").over(ventana))
      .withColumn("hora_anterior", F.lag("hora").over(ventana))
)
intervalo = F.col("hora").cast("long") - F.col("hora_anterior").cast("long")
diferencia = F.col("lluvia_acum_mm") - F.col("lluvia_anterior")
df = df.withColumn("lluvia_hora_mm", F.when(intervalo == 3600, diferencia))

# Corregir solamente negativos diminutos; conservar los significativos.
df = df.withColumn(
    "lluvia_hora_mm",
    F.when(
        (F.col("lluvia_hora_mm") < 0) & (F.col("lluvia_hora_mm") >= -0.0001),
        F.lit(0.0)
    ).otherwise(F.col("lluvia_hora_mm"))
)

# 7. Seleccionar columnas finales
df = df.select(
    "esquema", "fecha", "hora", "i", "j", "lat", "lon",
    "t2_c", "viento_10m", "lluvia_acum_mm", "lluvia_hora_mm"
)

# 8. Escritura en S3 (reemplaza la salida completa)
(
    df.write.mode("overwrite")
      .option("compression", "snappy")
      .partitionBy("esquema", "fecha")
      .parquet(OUTPUT)
)

# 9. Validacion de los datos escritos
resultado = spark.read.parquet(OUTPUT)
print("=== REGISTROS POR HORA ===")
resultado.groupBy("esquema", "hora").count().orderBy("esquema", "hora").show(100, truncate=False)
print("Total registros:", resultado.count())
resultado.agg(
    F.max("viento_10m").alias("viento_max"),
    F.max("lluvia_acum_mm").alias("lluvia_max"),
    F.min("lluvia_hora_mm").alias("lluvia_hora_min")
).show(truncate=False)
print("=== PROCESAMIENTO FINALIZADO ===")
print(f"Datos disponibles en: {OUTPUT}")
job.commit()
