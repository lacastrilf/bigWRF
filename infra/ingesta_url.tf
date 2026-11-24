# Ingesta automatica de la fuente URL: EventBridge (reloj) -> Lambda -> S3 raw/url/

# ---------- Variables de esta ingesta ----------
variable "event_date" {
  description = "Dia del derecho que descarga la ingesta de URLs"
  type        = string
  default     = "2026-08-11"
}
variable "asos_stations" {
  description = "Codigos FAA de las estaciones ASOS, separados por espacio"
  type        = string
  default     = "ORD MDW GYY FWA DSM MKE IND CID DBQ SBN CMH DTW MSN MLI RFD PIA GRR TOL"
}
variable "ingest_schedule" {
  description = "Cuando se dispara la Lambda (expresion de EventBridge)"
  type        = string
  default     = "rate(1 day)"
}

# ---------- Recursos ----------
data "archive_file" "lambda_url" {
  type        = "zip"
  source_dir  = "${path.module}/../intake/lambda_url"
  output_path = "${path.module}/.build/lambda_url.zip"
}

resource "aws_lambda_function" "ingest_url" {
  function_name    = "p2-ingest-url"
  role             = data.aws_iam_role.lab.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.lambda_url.output_path
  source_code_hash = data.archive_file.lambda_url.output_base64sha256
  timeout          = 120
  memory_size      = 256
  environment {
    variables = {
      BUCKET        = local.bucket
      EVENT_DATE    = var.event_date
      ASOS_STATIONS = var.asos_stations
    }
  }
  depends_on = [null_resource.bucket]
  tags       = local.tags
}

resource "aws_cloudwatch_event_rule" "ingest_url" {
  name                = "p2-ingest-url-schedule"
  description         = "Dispara la ingesta de ASOS y SPC hacia raw/url/"
  schedule_expression = var.ingest_schedule
}

resource "aws_cloudwatch_event_target" "ingest_url" {
  rule = aws_cloudwatch_event_rule.ingest_url.name
  arn  = aws_lambda_function.ingest_url.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest_url.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ingest_url.arn
}

output "lambda_ingest_url" { value = aws_lambda_function.ingest_url.function_name }
