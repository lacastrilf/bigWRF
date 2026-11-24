terraform {
  required_version = ">= 1.5"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.0" }
    null   = { source = "hashicorp/null", version = "~> 3.2" }
    random = { source = "hashicorp/random", version = "~> 3.5" }
  }
}

provider "aws" {
  region = var.region
  # Credenciales: variables de entorno AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
  # y AWS_SESSION_TOKEN copiadas de "AWS Details" del Learner Lab.
}

data "aws_caller_identity" "me" {}
data "aws_availability_zones" "az" { state = "available" }

# Roles que ya existen en Learner Lab (no se pueden crear roles nuevos)
data "aws_iam_role" "lab" { name = var.lab_role_name }

locals {
  bucket = "p2-derecho-${data.aws_caller_identity.me.account_id}"
  azs    = slice(data.aws_availability_zones.az.names, 0, 2)
  tags   = { Project = "proyecto2-derecho" }
}
