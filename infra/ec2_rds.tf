# ---------- EC2 fuente (archivos NetCDF) ----------
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_instance" "fuente" {
  count                  = var.enable_ec2 ? 1 : 0
  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = "t3.small"
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = var.instance_profile_name
  key_name               = var.key_name
  root_block_device {
    volume_size = var.ec2_disk_gb
    volume_type = "gp3"
  }
  user_data = <<-EOT
    #!/bin/bash
    dnf install -y mariadb105 tmux
    mkdir -p /data/wrf/thompson /data/wrf/morrison
    chown -R ec2-user:ec2-user /data
  EOT
  tags      = merge(local.tags, { Name = "p2-fuente-wrf" })
}

resource "aws_eip" "fuente" {
  count    = var.enable_ec2 ? 1 : 0
  instance = aws_instance.fuente[0].id
  domain   = "vpc"
}

# ---------- RDS MariaDB ----------
resource "random_password" "db" {
  length  = 20
  special = false
}

resource "aws_secretsmanager_secret" "db" {
  name                    = "p2-derecho-rds-${data.aws_caller_identity.me.account_id}"
  recovery_window_in_days = 0
}

resource "aws_db_subnet_group" "main" {
  name       = "p2-db-subnets"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "main" {
  count                  = var.enable_rds ? 1 : 0
  identifier             = "p2-derecho"
  engine                 = "mariadb"
  engine_version         = "10.11"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  storage_type           = "gp2"
  db_name                = var.db_name
  username               = var.db_user
  password               = random_password.db.result
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = false
  monitoring_interval    = 0 # Enhanced monitoring no esta soportado en el lab
  skip_final_snapshot    = true
  tags                   = local.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_user
    password = random_password.db.result
    host     = var.enable_rds ? aws_db_instance.main[0].address : ""
    port     = 3306
    dbname   = var.db_name
  })
}
