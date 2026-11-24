resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = "p2-vpc" })
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "p2-igw" }
}

# 2 subredes publicas y 2 privadas, una de cada por zona de disponibilidad
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  availability_zone       = local.azs[count.index]
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  map_public_ip_on_launch = true
  tags                    = { Name = "p2-public-${count.index}" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  tags              = { Name = "p2-private-${count.index}" }
}

# NAT: sale a Internet desde las privadas (Glue/EMR instalan paquetes)
resource "aws_eip" "nat" {
  count  = var.enable_nat ? 1 : 0
  domain = "vpc"
  tags   = { Name = "p2-nat-eip" }
}

resource "aws_nat_gateway" "nat" {
  count         = var.enable_nat ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id
  tags          = { Name = "p2-nat" }
  depends_on    = [aws_internet_gateway.igw]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = { Name = "p2-rt-public" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  dynamic "route" {
    for_each = var.enable_nat ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = aws_nat_gateway.nat[0].id
    }
  }
  tags = { Name = "p2-rt-private" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# Endpoint gateway de S3 (gratis): trafico a S3 sin pasar por el NAT
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id, aws_route_table.private.id]
  tags              = { Name = "p2-s3-endpoint" }
}

# ---------- Security groups ----------
resource "aws_security_group" "ec2" {
  name        = "p2-ec2"
  description = "EC2 fuente: SSH desde mi IP"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Glue exige una regla que permita todo el trafico desde si mismo
resource "aws_security_group" "glue" {
  name        = "p2-glue"
  description = "Conexiones de Glue (autorreferenciado)"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port = 0
    to_port   = 65535
    protocol  = "tcp"
    self      = true
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "rds" {
  name        = "p2-rds"
  description = "MariaDB: 3306 desde EC2, Glue y EMR"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id, aws_security_group.glue.id, aws_security_group.emr_master.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# EMR en subred privada necesita 3 grupos: master, core y acceso de servicio
resource "aws_security_group" "emr_master" {
  name                   = "p2-emr-master"
  description            = "EMR master"
  vpc_id                 = aws_vpc.main.id
  revoke_rules_on_delete = true
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "emr_core" {
  name                   = "p2-emr-core"
  description            = "EMR core"
  vpc_id                 = aws_vpc.main.id
  revoke_rules_on_delete = true
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "emr_service" {
  name                   = "p2-emr-service"
  description            = "EMR service access"
  vpc_id                 = aws_vpc.main.id
  revoke_rules_on_delete = true
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

locals {
  emr_pairs = {
    master_self = { sg = aws_security_group.emr_master.id, src = aws_security_group.emr_master.id }
    master_core = { sg = aws_security_group.emr_master.id, src = aws_security_group.emr_core.id }
    core_self   = { sg = aws_security_group.emr_core.id, src = aws_security_group.emr_core.id }
    core_master = { sg = aws_security_group.emr_core.id, src = aws_security_group.emr_master.id }
  }
}

resource "aws_security_group_rule" "emr_internal" {
  for_each                 = local.emr_pairs
  type                     = "ingress"
  security_group_id        = each.value.sg
  source_security_group_id = each.value.src
  from_port                = 0
  to_port                  = 65535
  protocol                 = "-1"
}

resource "aws_security_group_rule" "emr_master_from_service" {
  type                     = "ingress"
  security_group_id        = aws_security_group.emr_master.id
  source_security_group_id = aws_security_group.emr_service.id
  from_port                = 8443
  to_port                  = 8443
  protocol                 = "tcp"
}

resource "aws_security_group_rule" "emr_core_from_service" {
  type                     = "ingress"
  security_group_id        = aws_security_group.emr_core.id
  source_security_group_id = aws_security_group.emr_service.id
  from_port                = 8443
  to_port                  = 8443
  protocol                 = "tcp"
}

resource "aws_security_group_rule" "emr_service_from_master" {
  type                     = "ingress"
  security_group_id        = aws_security_group.emr_service.id
  source_security_group_id = aws_security_group.emr_master.id
  from_port                = 9443
  to_port                  = 9443
  protocol                 = "tcp"
}

resource "aws_security_group_rule" "emr_master_ssh" {
  type              = "ingress"
  security_group_id = aws_security_group.emr_master.id
  cidr_blocks       = [aws_vpc.main.cidr_block]
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
}
