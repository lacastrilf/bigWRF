
"""
AWS Glue Job: Observaciones y RDS RAW -> TRUSTED.

Procesa:
    raw/rds/cities/
    raw/rds/stations/
    raw/rds/runs/
    raw/url/asos/
    raw/url/spc/

Genera cinco tablas en formato Parquet.
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions

from pyspark.context import SparkContext
from pyspark.sql import functions as F

# ==========================================
# 1. Configuracion
# ==========================================

args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "BUCKET", "EVENT_DATE"]
)

BUCKET = args["BUCKET"]
EVENT_DATE = args["EVENT_DATE"]

RAW = f"s3://{BUCKET}/raw"
TRUSTED = f"s3://{BUCKET}/trusted"

sc = SparkContext.getOrCreate()
glue = GlueContext(sc)
spark = glue.spark_session

job = Job(glue)
job.init(args["JOB_NAME"], args)

spark.conf.set("spark.sql.session.timeZone", "UTC")
spark.conf.set("spark.sql.ansi.enabled", "false")

sc.setLogLevel("WARN")

# Factores de conversion
KNOT_TO_MS = 0.514444
MPH_TO_MS = 0.44704
INCH_TO_MM = 25.4

# ==========================================
# 2. Funciones auxiliares
# ==========================================

def leer_csv(ruta):

    return (
        spark.read
        .option("header", True)
        .option("inferSchema", False)
        .option("ignoreLeadingWhiteSpace", True)
        .option("ignoreTrailingWhiteSpace", True)
        .option("escape", '"')
        .csv(ruta)
    )


def numero(columna):

    valor = F.trim(F.col(columna))

    return (
        F.when(
            valor.isin("M", "UNK", ""),
            F.lit(None).cast("double")
        )
        .otherwise(valor.cast("double"))
    )


def guardar(df, tabla):

    destino = f"{TRUSTED}/{tabla}/"

    cantidad = df.count()

    if cantidad == 0:
        raise RuntimeError(
            f"La tabla {tabla} no contiene registros"
        )

    (
        df.coalesce(1)
        .write
        .mode("overwrite")
        .option("compression", "snappy")
        .parquet(destino)
    )

    print(f"[OK] {tabla}: {cantidad} registros")
    print(f"     Destino: {destino}")

# ==========================================
# 3. RDS: Cities -> Ciudades
# ==========================================

print("=== PROCESANDO CIUDADES ===")

ciudades = leer_csv(f"{RAW}/rds/cities/")

ciudades = ciudades.select(
    F.col("city_id").cast("int").alias("city_id"),
    F.trim(F.col("name")).alias("name"),
    F.upper(F.trim(F.col("state"))).alias("state"),
    numero("lat").alias("lat"),
    numero("lon").alias("lon"),
    F.col("population").cast("int").alias("population")
)

ciudades = ciudades.filter(
    F.col("city_id").isNotNull() &
    F.col("lat").between(-90, 90) &
    F.col("lon").between(-180, 180)
)

guardar(ciudades, "ciudades")

# ==========================================
# 4. RDS: Stations -> Estaciones
# ==========================================

print("=== PROCESANDO ESTACIONES ===")

estaciones = leer_csv(f"{RAW}/rds/stations/")

estaciones = estaciones.select(
    F.upper(F.trim(F.col("station_id"))).alias("station_id"),
    F.trim(F.col("name")).alias("name"),
    F.upper(F.trim(F.col("state"))).alias("state"),
    numero("lat").alias("lat"),
    numero("lon").alias("lon")
)

estaciones = estaciones.filter(
    F.col("station_id").isNotNull() &
    F.col("lat").between(-90, 90) &
    F.col("lon").between(-180, 180)
)

guardar(estaciones, "estaciones")

# ==========================================
# 5. RDS: Runs -> Corridas
# ==========================================

print("=== PROCESANDO CORRIDAS ===")

corridas = leer_csv(f"{RAW}/rds/runs/")

corridas = corridas.select(
    F.col("run_id").cast("int").alias("run_id"),
    F.lower(F.trim(F.col("scheme"))).alias("esquema"),
    F.col("mp_physics").cast("int").alias("mp_physics"),
    F.col("ranks").cast("int").alias("ranks"),
    F.col("wrf_walltime_s").cast("int").alias("walltime_s"),
    numero("real_walltime_s").alias("real_walltime_s"),
    F.col("sec_per_sim_hour").cast("int").alias(
        "sec_per_sim_hour"
    ),
    F.col("d01_dx_m").cast("int").alias("d01_dx_m"),
    F.col("d02_dx_m").cast("int").alias("d02_dx_m"),
    F.to_timestamp("start_utc").alias("start_utc"),
    F.to_timestamp("end_utc").alias("end_utc"),
    F.col("hardware")
)

guardar(corridas, "corridas")

# ==========================================
# 6. ASOS: Observaciones meteorologicas
# ==========================================

print("=== PROCESANDO ASOS ===")

asos = leer_csv(
    f"{RAW}/url/asos/fecha={EVENT_DATE}/asos.csv"
)

station = F.upper(F.trim(F.col("station")))

# Los codigos estadounidenses de tres caracteres
# se normalizan al identificador ICAO del RDS.
# Ejemplo: ORD -> KORD
station_id = F.when(
    station.rlike("^[A-Z0-9]{3}$"),
    F.concat(F.lit("K"), station)
).otherwise(station)

# Precipitacion traza (T):
# aproximar a cero, conservando un indicador.
precipitacion = F.when(
    F.trim(F.col("p01i")) == "T",
    F.lit(0.0)
).otherwise(numero("p01i") * INCH_TO_MM)

asos = asos.select(
    station_id.alias("station_id"),

    F.to_timestamp(
        "valid", "yyyy-MM-dd HH:mm"
    ).alias("hora_obs"),

    numero("lat").alias("lat"),
    numero("lon").alias("lon"),

    (
        (numero("tmpf") - 32.0) * 5.0 / 9.0
    ).alias("t2_c"),

    (
        (numero("dwpf") - 32.0) * 5.0 / 9.0
    ).alias("punto_rocio_c"),

    numero("relh").alias("humedad_pct"),
    numero("drct").alias("direccion_viento"),

    (
        numero("sknt") * KNOT_TO_MS
    ).alias("viento_10m"),

    (
        numero("gust") * KNOT_TO_MS
    ).alias("rafaga_ms"),

    precipitacion.alias("lluvia_hora_mm"),

    F.coalesce(
        F.trim(F.col("p01i")) == "T",
        F.lit(False)
    ).alias("lluvia_traza"),

    numero("mslp").alias("presion_hpa")
)

# Eliminar registros sin identificador, tiempo
# o coordenadas validas.
asos = asos.filter(
    F.col("station_id").isNotNull() &
    F.col("hora_obs").isNotNull() &
    F.col("lat").between(-90, 90) &
    F.col("lon").between(-180, 180)
)

# Calcular la hora WRF mas cercana.
# Se conserva la fecha original de observacion.
asos = asos.withColumn(
    "hora",
    (
        F.floor(
            (F.col("hora_obs").cast("long") + 1800) / 3600
        ) * 3600
    ).cast("long").cast("timestamp")
)

asos = asos.withColumn(
    "desfase_min",
    F.abs(
        F.col("hora_obs").cast("long") -
        F.col("hora").cast("long")
    ) / 60.0
)

asos = asos.dropDuplicates()

guardar(asos, "obs_asos")

# ==========================================
# 7. SPC: Reportes de viento
# ==========================================

print("=== PROCESANDO REPORTES SPC ===")

spc = leer_csv(
    f"{RAW}/url/spc/fecha={EVENT_DATE}/wind_reports.csv"
)

# La hora viene como HHMM.
# Ejemplo: 1202 -> 12:02 UTC.
spc = spc.withColumn(
    "hhmm",
    F.lpad(F.trim(F.col("Time")), 4, "0")
)

spc = spc.filter(
    F.col("hhmm").rlike("^([01][0-9]|2[0-3])[0-5][0-9]$")
)

# Los reportes SPC abarcan desde las 12 UTC
# hasta las 11:59 UTC del siguiente dia.
fecha_base = F.to_date(F.lit(EVENT_DATE))

spc = spc.withColumn(
    "fecha_reporte",
    F.when(
        F.col("hhmm").cast("int") < 1200,
        F.date_add(fecha_base, 1)
    ).otherwise(fecha_base)
)

spc = spc.withColumn(
    "hora_reporte",
    F.to_timestamp(
        F.concat(
            F.col("fecha_reporte").cast("string"),
            F.lit(" "),
            F.substring("hhmm", 1, 2),
            F.lit(":"),
            F.substring("hhmm", 3, 2),
            F.lit(":00")
        ),
        "yyyy-MM-dd HH:mm:ss"
    )
)

spc = spc.select(
    F.col("hora_reporte").alias("hora"),

    # UNK se conserva como NULL.
    numero("Speed").alias("viento_mph"),

    (
        numero("Speed") * MPH_TO_MS
    ).alias("viento_ms"),

    F.col("Location").alias("location"),
    F.col("County").alias("county"),
    F.col("State").alias("state"),

    numero("Lat").alias("lat"),
    numero("Lon").alias("lon"),

    F.col("Comments").alias("comments")
)

spc = spc.filter(
    F.col("hora").isNotNull() &
    F.col("lat").between(-90, 90) &
    F.col("lon").between(-180, 180)
)

guardar(spc, "reportes_spc")

# ==========================================
# 8. Finalizar
# ==========================================

print("=== ETL FINALIZADO ===")
print("Cinco tablas escritas en TRUSTED")

job.commit()
