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
    JDBC_CONNECTION_URL = "jdbc:mysql://${aws_db_instance.main[0].address}:3306/${var.db_name}"
    USERNAME            = var.db_user
    PASSWORD            = random_password.db.result
  }
  physical_connection_requirements {
    availability_zone      = aws_subnet.private[0].availability_zone
    subnet_id              = aws_subnet.private[0].id
    security_group_id_list = [aws_security_group.glue.id]
  }
}
