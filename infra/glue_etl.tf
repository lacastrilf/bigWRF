
# ==========================================
# Procesamiento WRF: RAW -> TRUSTED
# ==========================================

# Subir el script de procesamiento a S3
resource "aws_s3_object" "wrf_etl_script" {
  depends_on = [null_resource.bucket]

  bucket = local.bucket
  key    = "scripts/wrf_raw_to_trusted.py"

  source      = "${path.module}/../preparacion_datos/wrf_raw_to_trusted.py"
  source_hash = filemd5("${path.module}/../preparacion_datos/wrf_raw_to_trusted.py")

  content_type = "text/x-python"
}

# ==========================================
# Glue Spark ETL Job 1
# ==========================================

resource "aws_glue_job" "wrf_etl" {
  name        = "wrf-raw-to-trusted"
  description = "Procesamiento distribuido de NetCDF WRF a Parquet"

  role_arn = data.aws_iam_role.lab.arn

  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2

  timeout     = 30
  max_retries = 0

  command {
    name           = "glueetl"
    python_version = "3"

    script_location = "s3://${aws_s3_object.wrf_etl_script.bucket}/${aws_s3_object.wrf_etl_script.key}"
  }

  execution_property {
    max_concurrent_runs = 1
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--additional-python-modules"        = "netCDF4==1.7.2"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"

    "--BUCKET" = local.bucket

    # Rutas temporales para la primera prueba
    "--INPUT_PREFIX"  = "raw/wrf/"
    "--OUTPUT_PREFIX" = "trusted/wrf_superficie/"

    "--TempDir" = "s3://${local.bucket}/tmp/glue/"
  }

  tags = merge(local.tags, {
    Component = "DataPreparation"
    Job       = "WRF-ETL"
  })
}


# ==========================================
# Job 2: Observaciones y RDS RAW -> TRUSTED
# ==========================================

resource "aws_s3_object" "obs_etl_script" {
  depends_on = [null_resource.bucket]

  bucket = local.bucket
  key    = "scripts/obs_raw_to_trusted.py"

  source      = "${path.module}/../preparacion_datos/obs_raw_to_trusted.py"
  source_hash = filemd5("${path.module}/../preparacion_datos/obs_raw_to_trusted.py")

  content_type = "text/x-python"
}

resource "aws_glue_job" "obs_etl" {
  name        = "obs-raw-to-trusted"
  description = "Limpieza de observaciones ASOS, SPC y tablas RDS"

  role_arn = data.aws_iam_role.lab.arn

  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2

  timeout     = 15
  max_retries = 0

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${aws_s3_object.obs_etl_script.bucket}/${aws_s3_object.obs_etl_script.key}"
  }

  execution_property {
    max_concurrent_runs = 1
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"

    "--BUCKET"     = local.bucket
    "--EVENT_DATE" = "2026-08-11"

    "--TempDir" = "s3://${local.bucket}/tmp/glue/"
  }

  tags = merge(local.tags, {
    Component = "DataPreparation"
    Job       = "OBS-ETL"
  })
}


# ==========================================
# Job 3: Correspondencia geografica
# ==========================================

resource "aws_s3_object" "ciudad_celda_script" {
  depends_on = [null_resource.bucket]

  bucket = local.bucket
  key    = "scripts/ciudad_celda.py"

  source      = "${path.module}/../preparacion_datos/ciudad_celda.py"
  source_hash = filemd5("${path.module}/../preparacion_datos/ciudad_celda.py")

  content_type = "text/x-python"
}

resource "aws_glue_job" "ciudad_celda" {
  name        = "ciudad-celda"
  description = "Relacion geografica de ciudades y estaciones con la malla WRF"

  role_arn = data.aws_iam_role.lab.arn

  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2

  timeout     = 20
  max_retries = 0

  command {
    name           = "glueetl"
    python_version = "3"

    script_location = "s3://${aws_s3_object.ciudad_celda_script.bucket}/${aws_s3_object.ciudad_celda_script.key}"
  }

  execution_property {
    max_concurrent_runs = 1
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"

    "--BUCKET" = local.bucket

    "--TempDir" = "s3://${local.bucket}/tmp/glue/"
  }

  tags = merge(local.tags, {
    Component = "DataPreparation"
    Job       = "Ciudad-Celda"
  })
}
