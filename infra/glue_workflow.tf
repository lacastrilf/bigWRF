# ============================================================
# BigWRF - Workflow de preparacion y catalogacion
# ============================================================

resource "aws_glue_workflow" "preparacion_catalogo" {
  name                = "p2-preparacion-catalogo"
  description         = "Orquestacion de jobs ETL y crawlers RAW y TRUSTED"
  max_concurrent_runs = 1

  tags = merge(local.tags, {
    Component = "DataWorkflow"
  })
}

# ============================================================
# Trigger 1 - Inicio bajo demanda
# ============================================================

resource "aws_glue_trigger" "workflow_inicio" {
  name          = "p2-workflow-inicio"
  type          = "ON_DEMAND"
  workflow_name = aws_glue_workflow.preparacion_catalogo.name

  actions {
    crawler_name = aws_glue_crawler.catalog["raw"].name
  }
}

# ============================================================
# Trigger 2 - RAW catalogado -> Jobs WRF y OBS
# ============================================================

resource "aws_glue_trigger" "workflow_etl" {
  name              = "p2-workflow-etl"
  type              = "CONDITIONAL"
  workflow_name     = aws_glue_workflow.preparacion_catalogo.name
  start_on_creation = true

  predicate {
    logical = "AND"

    conditions {
      crawler_name     = aws_glue_crawler.catalog["raw"].name
      crawl_state      = "SUCCEEDED"
      logical_operator = "EQUALS"
    }
  }

  actions {
    job_name = aws_glue_job.wrf_etl.name

    arguments = {
      "--INPUT_PREFIX"  = "raw/wrf/"
      "--OUTPUT_PREFIX" = "trusted/wrf_superficie/"
    }
  }

  actions {
    job_name = aws_glue_job.obs_etl.name
  }
}

# ============================================================
# Trigger 3 - WRF y OBS exitosos -> GEO y catalogacion
# ============================================================

resource "aws_glue_trigger" "workflow_geo_obs_wrf" {
  name              = "p2-workflow-geo-obs-wrf"
  type              = "CONDITIONAL"
  workflow_name     = aws_glue_workflow.preparacion_catalogo.name
  start_on_creation = true

  predicate {
    logical = "AND"

    conditions {
      job_name         = aws_glue_job.wrf_etl.name
      state            = "SUCCEEDED"
      logical_operator = "EQUALS"
    }

    conditions {
      job_name         = aws_glue_job.obs_etl.name
      state            = "SUCCEEDED"
      logical_operator = "EQUALS"
    }
  }

  actions {
    job_name = aws_glue_job.ciudad_celda.name
  }

  actions {
    crawler_name = aws_glue_crawler.catalog["trusted_obs"].name
  }

  actions {
    crawler_name = aws_glue_crawler.catalog["trusted_wrf"].name
  }
}

# ============================================================
# Trigger 4 - GEO exitoso -> Catalogacion geografica
# ============================================================

resource "aws_glue_trigger" "workflow_catalogo_geo" {
  name              = "p2-workflow-catalogo-geo"
  type              = "CONDITIONAL"
  workflow_name     = aws_glue_workflow.preparacion_catalogo.name
  start_on_creation = true

  predicate {
    logical = "AND"

    conditions {
      job_name         = aws_glue_job.ciudad_celda.name
      state            = "SUCCEEDED"
      logical_operator = "EQUALS"
    }
  }

  actions {
    crawler_name = aws_glue_crawler.catalog["trusted_geo"].name
  }
}
