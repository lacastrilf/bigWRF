output "bucket" { value = local.bucket }
output "ec2_ip" { value = var.enable_ec2 ? aws_eip.fuente[0].public_ip : null }
output "rds_endpoint" { value = var.enable_rds ? aws_db_instance.main[0].address : null }
output "db_secret" { value = aws_secretsmanager_secret.db.name }
output "athena_workgroup" { value = aws_athena_workgroup.p2.name }
output "emr_cluster_id" { value = var.enable_emr ? aws_emr_cluster.main[0].id : null }
output "private_subnets" { value = aws_subnet.private[*].id }
output "glue_sg" { value = aws_security_group.glue.id }
