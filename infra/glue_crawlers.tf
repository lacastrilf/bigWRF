
# ==========================================
# Punto 5 - Catalogacion de datos
# ==========================================

locals {
  catalog_crawlers = {

    raw = {
      name        = "p2-raw-crawler"
      description = "Catalogacion de las fuentes CSV originales"
      database    = aws_glue_catalog_database.raw.name

      paths = [
        "raw/rds/cities/",
        "raw/rds/stations/",
        "raw/rds/runs/",
        "raw/url/asos/",
        "raw/url/spc/"
      ]
    }

    trusted_obs = {
      name        = "p2-trusted-obs-crawler"
      description = "Catalogacion de observaciones y datos de contexto"
      database    = aws_glue_catalog_database.trusted.name

      paths = [
        "trusted/ciudades/",
        "trusted/estaciones/",
        "trusted/corridas/",
        "trusted/obs_asos/",
        "trusted/reportes_spc/"
      ]
    }

    trusted_wrf = {
      name        = "p2-trusted-wrf-crawler"
      description = "Catalogacion de datos meteorologicos WRF"
      database    = aws_glue_catalog_database.trusted.name

      paths = [
        "trusted/wrf_superficie/"
      ]
    }

    trusted_geo = {
      name        = "p2-trusted-geo-crawler"
      description = "Catalogacion de correspondencias geograficas"
      database    = aws_glue_catalog_database.trusted.name

      paths = [
        "trusted/ciudad_celda/"
      ]
    }
  }
}

resource "aws_glue_crawler" "catalog" {

  for_each = local.catalog_crawlers

  name          = each.value.name
  description   = each.value.description
  database_name = each.value.database

  role = data.aws_iam_role.lab.arn

  dynamic "s3_target" {

    for_each = each.value.paths

    content {
      path = "s3://${local.bucket}/${s3_target.value}"

      exclusions = [
        "**/_SUCCESS",
        "**/_temporary/**"
      ]
    }
  }

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }

  recrawl_policy {
    recrawl_behavior = "CRAWL_EVERYTHING"
  }

  configuration = jsonencode({
    Version = 1.0

    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })

  tags = merge(local.tags, {
    Component = "DataCatalog"
    Zone      = each.key
  })
}
