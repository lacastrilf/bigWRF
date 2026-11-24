# Solo catalogo y conexion. Los jobs, crawlers y workflow se crean despues.
resource "aws_glue_catalog_database" "raw" {
  name = "derecho_raw"
}

resource "aws_glue_catalog_database" "trusted" {
  name = "derecho_trusted"
}

resource "aws_glue_catalog_database" "refined" {
  name = "derecho_refined"
}

resource "aws_glue_connection" "rds" {
  count           = var.enable_rds ? 1 : 0
  name            = "p2-rds-mariadb"
  connection_type = "JDBC"
  connection_properties = {
    JDBC_CONNECTION_URL = "jdbc:mysql://${aws_db_instance.main[0].address}:3306/${var.db_name}?useSSL=false&allowPublicKeyRetrieval=true"
    USERNAME            = var.db_user
    PASSWORD            = random_password.db.result
  }
  physical_connection_requirements {
    availability_zone      = aws_subnet.private[0].availability_zone
    subnet_id              = aws_subnet.private[0].id
    security_group_id_list = [aws_security_group.glue.id]
  }
}

# ---------- Job de ingesta RDS -> S3 raw (punto 3) ----------
resource "aws_s3_object" "rds_to_raw_script" {
  bucket     = local.bucket
  key        = "scripts/glue/rds_to_raw.py"
  source     = "${path.module}/../intake/glue_rds/rds_to_raw.py"
  etag       = filemd5("${path.module}/../intake/glue_rds/rds_to_raw.py")
  depends_on = [null_resource.bucket]
}

resource "aws_glue_job" "rds_to_raw" {
  count             = var.enable_rds ? 1 : 0
  name              = "p2-rds-to-raw"
  role_arn          = data.aws_iam_role.lab.arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 15
  connections       = [aws_glue_connection.rds[0].name]

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${local.bucket}/${aws_s3_object.rds_to_raw_script.key}"
  }

  default_arguments = {
    "--BUCKET"     = local.bucket
    "--CONNECTION" = aws_glue_connection.rds[0].name
    "--TABLES"     = "cities,stations,runs"
    "--TempDir"    = "s3://${local.bucket}/tmp/glue/"
  }
  tags = local.tags
}

# Dispara el job de la RDS segun un horario (ingesta automatica, punto 3)
variable "rds_ingest_schedule" {
  description = "Horario del job RDS -> raw (cron de Glue, UTC)"
  type        = string
  default     = "cron(0 6 * * ? *)" # todos los dias 06:00 UTC
}

resource "aws_glue_trigger" "rds_to_raw" {
  count             = var.enable_rds ? 1 : 0
  name              = "p2-rds-to-raw-schedule"
  type              = "SCHEDULED"
  schedule          = var.rds_ingest_schedule
  start_on_creation = true

  actions {
    job_name = aws_glue_job.rds_to_raw[0].name
  }
  tags = local.tags
}
