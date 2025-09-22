#!/usr/bin/env python3
"""
ETL pipeline:
1) Import towers CSV -> PostGIS
2) Ensure Ookla geometry + create Barbados subset
3) Build analysis tables (counts, LTE, nearest LTE distance)
4) Export GeoJSON for Leaflet
"""
import os, sys, argparse, subprocess
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

def sh(cmd: list[str]):
    """Run a shell command; show it; fail fast on error."""
    print("→", " ".join(cmd))
    subprocess.run(cmd, check=True)

def run_psql_sql(container: str, db: str, user: str, password: str, sql: str):
    """
    Execute a SQL string via psql inside your running PostGIS container.
    - container: the container name (we use POSTGRES_HOST value)
    """
    cmd = [
        "docker","exec",
        "-e", f"PGPASSWORD={password}",
        "-i", container,
        "psql", "-U", user, "-d", db, "-v", "ON_ERROR_STOP=1"
    ]
    print("→ Executing SQL block...")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
    proc.communicate(sql)
    if proc.returncode != 0:
        raise RuntimeError("psql returned non-zero exit status")


def main():
    # Load .env (or environment)
    load_dotenv(find_dotenv(usecwd=True) or ".env")

    parser = argparse.ArgumentParser(description="ETL for Barbados connectivity")
    parser.add_argument("--towers-csv", required=True, help="Path to opencellid_barbados_towers.csv")
    args = parser.parse_args()

    # Config (with defaults)
    host = os.getenv("POSTGRES_HOST", "postgis_container")
    port = os.getenv("POSTGRES_PORT", "5432")
    db   = os.getenv("POSTGRES_DB", "geodb")
    user = os.getenv("POSTGRES_USER", "admin")
    pwd  = os.getenv("POSTGRES_PASSWORD", "StrongPass123")
    gdal_image = os.getenv("GDAL_IMAGE", "ghcr.io/osgeo/gdal:ubuntu-full-latest")
    container  = host  # same as POSTGRES_HOST

    ookla_schema = os.getenv("OOKLA_SCHEMA", "ookla_tiles")
    ookla_table  = os.getenv("OOKLA_TABLE", "raw_mobile_q1_2024")
    ookla_table_bb = os.getenv("OOKLA_TABLE_BB", "raw_mobile_q1_2024_bb")
    towers_schema = os.getenv("TOWERS_SCHEMA", "cell_towers")
    towers_table  = os.getenv("TOWERS_TABLE", "bb_towers")
    analysis_schema = os.getenv("ANALYSIS_SCHEMA", "analysis")

    out1 = os.getenv("OUTPUT_GEOJSON_1", "towers_per_tile.geojson")
    out2 = os.getenv("OUTPUT_GEOJSON_2", "towers_per_tile_lte.geojson")
   
    towers_path = str(Path(args.towers_csv).resolve())
# Import points with lat/lon as geometry (EPSG:4326)
sh([
    "docker","run","--rm",
    "-v",f"{Path(towers_path).parent}:/data",
    "--network","heatmapnet",
    gdal_image,
    "ogr2ogr","-f","PostgreSQL",
    f"PG:host={host} port={port} dbname={db} user={user} password={pwd}",
    f"/data/{Path(towers_path).name}",
    "-nln",f"{towers_schema}.{towers_table}","-overwrite",
    "-oo","HEADERS=YES","-oo","SEPARATOR=COMMA","-oo","AUTODETECT_TYPE=YES",
    "-oo","X_POSSIBLE_NAMES=lon","-oo","Y_POSSIBLE_NAMES=lat",
    "-nlt","POINT","-a_srs","EPSG:4326"
])
       sql_geom = f"""
ALTER TABLE {ookla_schema}.{ookla_table}
  ADD COLUMN IF NOT EXISTS geom geometry(Polygon,4326);

UPDATE {ookla_schema}.{ookla_table}
SET geom = ST_GeomFromText(tile, 4326)
WHERE geom IS NULL AND tile LIKE 'POLYGON(%';

CREATE INDEX IF NOT EXISTS {ookla_table}_geom_gix
  ON {ookla_schema}.{ookla_table} USING GIST (geom);

DROP TABLE IF EXISTS {ookla_schema}.{ookla_table_bb};
CREATE TABLE {ookla_schema}.{ookla_table_bb} AS
SELECT o.*
FROM {ookla_schema}.{ookla_table} o
WHERE o.geom IS NOT NULL
  AND ST_Intersects(
        o.geom,
        ST_MakeEnvelope(-59.95, 13.03, -59.35, 13.40, 4326)
      );

CREATE INDEX IF NOT EXISTS {ookla_table_bb}_geom_gix
  ON {ookla_schema}.{ookla_table_bb} USING GIST (geom);
"""
    run_psql_sql(container, db, user, pwd, sql_geom)
 

        sql_analysis = f"""
CREATE SCHEMA IF NOT EXISTS {analysis_schema};

-- Count all towers in each tile + carry Ookla averages
DROP TABLE IF EXISTS {analysis_schema}.towers_per_tile;
CREATE TABLE {analysis_schema}.towers_per_tile AS
SELECT
  o.ogc_fid                        AS tile_id,
  COUNT(t.*)                       AS towers_all,
  AVG(o.avg_d_kbps)::numeric(12,2) AS avg_download_kbps,
  AVG(o.avg_u_kbps)::numeric(12,2) AS avg_upload_kbps
FROM {ookla_schema}.{ookla_table_bb} o
LEFT JOIN {towers_schema}.{towers_table} t
  ON ST_Intersects(o.geom, t.geom)
GROUP BY o.ogc_fid;
CREATE INDEX IF NOT EXISTS towers_per_tile_tile_id_idx
  ON {analysis_schema}.towers_per_tile (tile_id);

-- LTE-only counts
DROP TABLE IF EXISTS {analysis_schema}.towers_per_tile_lte;
CREATE TABLE {analysis_schema}.towers_per_tile_lte AS
SELECT
  o.ogc_fid AS tile_id,
  SUM(CASE WHEN t.radio='LTE' THEN 1 ELSE 0 END) AS towers_lte,
  AVG(o.avg_d_kbps)::numeric(12,2) AS avg_download_kbps,
  AVG(o.avg_u_kbps)::numeric(12,2) AS avg_upload_kbps
FROM {ookla_schema}.{ookla_table_bb} o
LEFT JOIN {towers_schema}.{towers_table} t
  ON ST_Intersects(o.geom, t.geom)
GROUP BY o.ogc_fid;
CREATE INDEX IF NOT EXISTS towers_per_tile_lte_tile_id_idx
  ON {analysis_schema}.towers_per_tile_lte (tile_id);

-- Tile centroids (for nearest LTE distance)
DROP TABLE IF EXISTS {analysis_schema}.ookla_centroids;
CREATE TABLE {analysis_schema}.ookla_centroids AS
SELECT o.ogc_fid AS tile_id, ST_Centroid(o.geom) AS geom
FROM {ookla_schema}.{ookla_table_bb} o;
CREATE INDEX IF NOT EXISTS ookla_centroids_gix
  ON {analysis_schema}.ookla_centroids USING GIST (geom);

-- Distance to nearest LTE tower (meters)
DROP TABLE IF EXISTS {analysis_schema}.nearest_lte_distance;
CREATE TABLE {analysis_schema}.nearest_lte_distance AS
SELECT
  c.tile_id,
  MIN(ST_DistanceSphere(c.geom, t.geom)) AS meters_to_nearest_lte
FROM {analysis_schema}.ookla_centroids c
JOIN {towers_schema}.{towers_table} t ON t.radio='LTE'
GROUP BY c.tile_id;
CREATE INDEX IF NOT EXISTS nearest_lte_tile_idx
  ON {analysis_schema}.nearest_lte_distance (tile_id);

-- Final summary (counts + distance)
DROP TABLE IF EXISTS {analysis_schema}.tile_lte_summary;
CREATE TABLE {analysis_schema}.tile_lte_summary AS
SELECT
  l.tile_id,
  l.towers_lte,
  l.avg_download_kbps,
  l.avg_upload_kbps,
  d.meters_to_nearest_lte
FROM {analysis_schema}.towers_per_tile_lte l
LEFT JOIN {analysis_schema}.nearest_lte_distance d USING (tile_id);
"""
    run_psql_sql(container, db, user, pwd, sql_analysis)
