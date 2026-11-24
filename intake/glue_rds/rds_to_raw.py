"""Job de Glue: exporta tablas de la RDS MariaDB a S3 (zona raw) como CSV, sin transformar.

Lee por JDBC usando la conexion de Glue (que lleva la red, el usuario y la clave) y escribe
  s3://<BUCKET>/raw/rds/<tabla>/part-*.csv      (con encabezado)

Argumentos: --BUCKET, --CONNECTION (nombre de la conexion Glue), --TABLES (separadas por coma)
"""
import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET", "CONNECTION", "TABLES"])
glue = GlueContext(SparkContext.getOrCreate())
job = Job(glue)
job.init(args["JOB_NAME"], args)

for tabla in [t.strip() for t in args["TABLES"].split(",") if t.strip()]:
    dyf = glue.create_dynamic_frame.from_options(
        connection_type="mysql",
        connection_options={
            "useConnectionProperties": "true",
            "connectionName": args["CONNECTION"],
            "dbtable": tabla,
        },
    )
    df = dyf.toDF()
    destino = f"s3://{args['BUCKET']}/raw/rds/{tabla}/"
    # tablas pequenas: un solo archivo por tabla
    df.coalesce(1).write.mode("overwrite").option("header", True).csv(destino)
    print(f"{tabla}: {df.count()} filas -> {destino}")

job.commit()
