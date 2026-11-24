resource "aws_emr_cluster" "main" {
  count         = var.enable_emr ? 1 : 0
  name          = "p2-derecho-emr"
  release_label = "emr-6.15.0"
  applications  = ["Hadoop", "Hive", "Spark", "Livy", "JupyterEnterpriseGateway"]
  log_uri       = "s3://${local.bucket}/emr-logs/"
  service_role  = var.emr_service_role

  ec2_attributes {
    subnet_id                         = aws_subnet.private[0].id
    key_name                          = var.key_name
    instance_profile                  = "arn:aws:iam::${data.aws_caller_identity.me.account_id}:instance-profile/${var.emr_instance_profile}"
    emr_managed_master_security_group = aws_security_group.emr_master.id
    emr_managed_slave_security_group  = aws_security_group.emr_core.id
    service_access_security_group     = aws_security_group.emr_service.id
  }

  master_instance_group {
    instance_type = var.emr_instance_type
  }
  core_instance_group {
    instance_type  = var.emr_instance_type
    instance_count = 2
  }

  # Hive y Spark usan el Glue Data Catalog como metastore
  configurations_json = jsonencode([
    {
      Classification = "hive-site"
      Properties = {
        "hive.metastore.client.factory.class" = "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory"
      }
    },
    {
      Classification = "spark-hive-site"
      Properties = {
        "hive.metastore.client.factory.class" = "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory"
      }
    }
  ])

  auto_termination_policy {
    idle_timeout = var.emr_idle_timeout_s
  }

  keep_job_flow_alive_when_no_steps = true
  tags                              = local.tags

  depends_on = [null_resource.bucket, aws_nat_gateway.nat, aws_vpc_endpoint.s3, aws_security_group_rule.emr_internal]
}
