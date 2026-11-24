
"""
AWS Glue Job: Correspondencia geografica WRF.

Encuentra la celda WRF mas cercana a cada
ciudad y estacion utilizando Haversine.

Entradas:
    trusted/wrf_superficie/
    trusted/ciudades/
    trusted/estaciones/

Salida:
    trusted/ciudad_celda/
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions

from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# ==========================================
# 1. Configuracion
# ==========================================

args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "BUCKET"]
)

BUCKET = args["BUCKET"]
TRUSTED = f"s3://{BUCKET}/trusted"

sc = SparkContext.getOrCreate()
glue = GlueContext(sc)
spark = glue.spark_session

job = Job(glue)
job.init(args["JOB_NAME"], args)

spark.conf.set("spark.sql.session.timeZone", "UTC")
spark.conf.set("spark.sql.shuffle.partitions", "32")

sc.setLogLevel("WARN")

RADIO_TIERRA_KM = 6371.0

# ==========================================
# 2. Leer datos de los jobs anteriores
# ==========================================

wrf = spark.read.parquet(
    f"{TRUSTED}/wrf_superficie/"
)

ciudades = spark.read.parquet(
    f"{TRUSTED}/ciudades/"
)

estaciones = spark.read.parquet(
    f"{TRUSTED}/estaciones/"
)

# ==========================================
# 3. Extraer la malla de WRF
# ==========================================

# Solo necesitamos el primer instante
# de cada esquema: la malla es fija.

primeras_horas = (
    wrf.groupBy("esquema")
    .agg(F.min("hora").alias("hora"))
)

malla = (
    wrf
    .join(
        F.broadcast(primeras_horas),
        ["esquema", "hora"],
        "inner"
    )
    .select(
        "esquema",
        "i",
        "j",
        F.col("lat").alias("lat_celda"),
        F.col("lon").alias("lon_celda")
    )
    .filter(
        F.col("lat_celda").between(-90, 90) &
        F.col("lon_celda").between(-180, 180)
    )
    .dropDuplicates()
)

print("=== MALLA WRF ===")
malla.groupBy("esquema").count().show()

# ==========================================
# 4. Unificar ciudades y estaciones
# ==========================================

puntos_ciudades = ciudades.select(
    F.lit("ciudad").alias("tipo"),

    F.col("city_id").cast("string").alias(
        "id_ubicacion"
    ),

    F.col("city_id"),

    F.lit(None).cast("string").alias(
        "station_id"
    ),

    F.col("name").alias("nombre"),

    F.col("lat").alias("lat_ubicacion"),
    F.col("lon").alias("lon_ubicacion")
)

puntos_estaciones = estaciones.select(
    F.lit("estacion").alias("tipo"),

    F.col("station_id").alias("id_ubicacion"),

    F.lit(None).cast("int").alias("city_id"),

    F.col("station_id"),

    F.col("name").alias("nombre"),

    F.col("lat").alias("lat_ubicacion"),
    F.col("lon").alias("lon_ubicacion")
)

ubicaciones = puntos_ciudades.unionByName(
    puntos_estaciones
)

print("=== UBICACIONES ===")

ubicaciones.groupBy("tipo").count().show()

# ==========================================
# 5. Comparar ubicaciones con celdas
# ==========================================

# Las ubicaciones son pocas, por lo que
# usamos broadcast para distribuirlas.

candidatos = malla.crossJoin(
    F.broadcast(ubicaciones)
)

# ==========================================
# 6. Calcular distancia Haversine
# ==========================================

lat1 = F.radians(F.col("lat_ubicacion"))
lon1 = F.radians(F.col("lon_ubicacion"))

lat2 = F.radians(F.col("lat_celda"))
lon2 = F.radians(F.col("lon_celda"))

delta_lat = lat2 - lat1
delta_lon = lon2 - lon1

a = (
    F.pow(F.sin(delta_lat / 2), 2)
    +
    F.cos(lat1)
    * F.cos(lat2)
    * F.pow(F.sin(delta_lon / 2), 2)
)

# Evitar errores de precision numerica.
a = F.greatest(
    F.lit(0.0),
    F.least(F.lit(1.0), a)
)

distancia = (
    2
    * RADIO_TIERRA_KM
    * F.asin(F.sqrt(a))
)

candidatos = candidatos.withColumn(
    "distancia_km",
    distancia
)

# ==========================================
# 7. Seleccionar la celda mas cercana
# ==========================================

ventana = (
    Window
    .partitionBy(
        "esquema",
        "tipo",
        "id_ubicacion"
    )
    .orderBy(
        F.col("distancia_km").asc(),
        F.col("i").asc(),
        F.col("j").asc()
    )
)

resultado = (
    candidatos
    .withColumn(
        "ranking",
        F.row_number().over(ventana)
    )
    .filter(F.col("ranking") == 1)
    .drop("ranking")
)

# ==========================================
# 8. Organizar resultado final
# ==========================================

resultado = resultado.select(
    "esquema",
    "tipo",
    "id_ubicacion",
    "city_id",
    "station_id",
    "nombre",
    "lat_ubicacion",
    "lon_ubicacion",
    "i",
    "j",
    "lat_celda",
    "lon_celda",
    "distancia_km"
)

# ==========================================
# 9. Guardar en S3
# ==========================================

destino = f"{TRUSTED}/ciudad_celda/"

(
    resultado
    .coalesce(1)
    .write
    .mode("overwrite")
    .option("compression", "snappy")
    .parquet(destino)
)

# ==========================================
# 10. Validacion
# ==========================================

final = spark.read.parquet(destino)

print("=== CORRESPONDENCIAS GENERADAS ===")

final.select(
    "esquema",
    "tipo",
    "nombre",
    "i",
    "j",
    F.round(
        "distancia_km", 4
    ).alias("distancia_km")
).orderBy(
    "esquema", "tipo", "nombre"
).show(100, truncate=False)

print("=== REGISTROS POR TIPO ===")

final.groupBy(
    "esquema", "tipo"
).count().show()

print("=== DISTANCIAS ===")

final.agg(
    F.min("distancia_km").alias("distancia_min"),
    F.avg("distancia_km").alias("distancia_prom"),
    F.max("distancia_km").alias("distancia_max")
).show(truncate=False)

esperados = (
    wrf.select("esquema").distinct().count()
    * ubicaciones.count()
)

obtenidos = final.count()

print(f"Registros esperados: {esperados}")
print(f"Registros obtenidos: {obtenidos}")

if obtenidos != esperados:
    raise RuntimeError(
        "Cantidad de correspondencias incorrecta"
    )

print(f"[OK] Datos disponibles en {destino}")

job.commit()
