# El recurso aws_s3_bucket lee configuraciones (object lock) que el SCP del
# Learner Lab bloquea con 403, asi que el bucket se crea con la AWS CLI.
resource "null_resource" "bucket" {
  triggers = { name = local.bucket, region = var.region }
  provisioner "local-exec" {
    command = "aws s3api head-bucket --bucket ${self.triggers.name} 2>/dev/null || aws s3api create-bucket --bucket ${self.triggers.name} --region ${self.triggers.region}"
  }
  provisioner "local-exec" {
    when    = destroy
    command = "aws s3 rb s3://${self.triggers.name} --force || true"
  }
}

resource "aws_s3_bucket_public_access_block" "lake" {
  depends_on              = [null_resource.bucket]
  bucket                  = local.bucket
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# "Carpetas" de las zonas del data lake
resource "aws_s3_object" "zones" {
  depends_on = [null_resource.bucket]
  for_each = toset([
    "raw/wrf/", "raw/rds/", "raw/url/",
    "trusted/", "refined/", "athena-results/", "scripts/", "tmp/", "emr-logs/",
  ])
  bucket  = local.bucket
  key     = each.value
  content = ""
}
