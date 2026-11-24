-- schema.sql : structure of the `derecho` database (MariaDB on RDS)
-- Source of context data for the Derecho WRF case (11 Aug 2026).
-- Re-runnable: drops and recreates the tables. Load seed.sql afterwards.

CREATE DATABASE IF NOT EXISTS derecho CHARACTER SET utf8mb4;
USE derecho;

DROP TABLE IF EXISTS stations;
DROP TABLE IF EXISTS cities;
DROP TABLE IF EXISTS runs;

-- Cities inside the d01 domain. Used to answer "near which city" questions
-- (later joined to the WRF grid through the nearest cell).
CREATE TABLE cities (
  city_id    INT          NOT NULL PRIMARY KEY,
  name       VARCHAR(60)  NOT NULL,
  state      CHAR(2)      NOT NULL,
  lat        DOUBLE       NOT NULL,   
  lon        DOUBLE       NOT NULL,   
  population INT          NULL        
) ENGINE=InnoDB;

-- ASOS surface observation stations.
CREATE TABLE stations (
  station_id VARCHAR(4)   NOT NULL PRIMARY KEY,   -- ICAO code, e.g. KORD
  name       VARCHAR(80)  NOT NULL,
  state      CHAR(2)      NOT NULL,
  lat        DOUBLE       NOT NULL,
  lon        DOUBLE       NOT NULL
) ENGINE=InnoDB;

-- One row per WRF simulation.
CREATE TABLE runs (
  run_id            INT          NOT NULL PRIMARY KEY,
  scheme            VARCHAR(20)  NOT NULL,  
  mp_physics        INT          NOT NULL,   
  ranks             INT          NOT NULL,  
  wrf_walltime_s    INT          NOT NULL,   
  real_walltime_s   DOUBLE       NOT NULL,   
  sec_per_sim_hour  INT          NOT NULL,
  d01_dx_m          INT          NOT NULL,   
  d02_dx_m          INT          NOT NULL,   
  start_utc         DATETIME     NOT NULL,
  end_utc           DATETIME     NOT NULL,
  hardware          VARCHAR(200) NOT NULL
) ENGINE=InnoDB;
