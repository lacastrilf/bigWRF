resource "aws_athena_workgroup" "p2" {
  name          = "p2-derecho"
  force_destroy = true
  configuration {
    enforce_workgroup_configuration = true
    result_configuration {
      output_location = "s3://${local.bucket}/athena-results/"
    }
  }
}
