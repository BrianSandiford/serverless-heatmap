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
    print("→", " ".join(cmd))
    subprocess.run(cmd, check=True)

def run_psql_sql(host, port, db, user, pwd, sql):
    import subprocess
    cmd = [
        "psql",
        f"host={host}",
        f"port={port}",
        f"dbname={db}",
        f"user={user}",
        f"password={pwd}",
        "-v", "ON_ERROR_STOP=1",
        "-c", sql,
    ]
    subprocess.run(cmd, check=True)

def main():
    load_dotenv(find_dotenv(usecwd=True) or ".env")

    parser = argparse.ArgumentParser(description="ETL for Barbados connectivity")
    parser.add_argument("--towers-csv", required=True, help="Path to opencellid_barbados_towers.csv")
    args = parser.parse_args()

    host = os.getenv("POSTGRES_HOST", "postgis_container")
    port = os.getenv("POSTGRES_PORT", "5432")
    db   = os.getenv("POSTGRES_DB", "geodb")
    user = os.getenv("POSTGRES_USER", "admin")
    pwd  = os.getenv("POSTGRES_PASSWORD", "StrongPass123")
    gdal_image = os.getenv("GDAL_IMAGE", "ghcr.io/osgeo/gdal:ubuntu-full-latest")
    container  = host  # same name as POSTGRES_HOST

    ookla_schema = os.getenv("OOKLA_SCHEMA", "ookla_tiles")
    ookla_table  = os.getenv("OOKLA_TABLE", "raw_mobile_q1_2024")
    ookla_table_bb = os.getenv("OOKLA_TABLE_BB", "raw_mobile_q1_2024_bb")
    towers_schema = os.getenv("TOWERS_SCHEMA", "cell_towers")
    towers_table  = os.getenv("TOWERS_TABLE", "bb_towers")
    analysis_schema = os.getenv("ANALYSIS_SCHEMA", "analysis")

    out1 = os.getenv("OUTPUT_GEOJSON_1", "towers_per_tile.geojson")
    out2 = os.getenv("OUTPUT_GEOJSON_2", "towers_per_tile_lte.geojson")

    towers_path = str(Path(args.towers_csv).resolve())
    # 1) Import towers CSV -> PostGIS (detect lat/lon columns; EPSG:4326 point)
    # before: sh(["docker","run","--rm", ... "ogr2ogr", ...])
    # after:
    

    sh([
        "ogr2ogr", "-f", "PostgreSQL",
        f"PG:host={host} port={port} dbname={db} user={user} password={pwd}",
        f"/data/{Path(towers_path).name}",
        "-nln","bb_towers","-lco","SCHEMA=cell_towers","-overwrite",
        #"-nln", f"{towers_schema}.{towers_table}", "-overwrite",
        "-oo", "HEADERS=YES", "-oo", "SEPARATOR=COMMA", "-oo", "AUTODETECT_TYPE=YES",
        "-oo", "X_POSSIBLE_NAMES=lon", "-oo", "Y_POSSIBLE_NAMES=lat",
        "-nlt", "POINT", "-a_srs", "EPSG:4326",
        "-lco","OVERWRITE=YES",
        "-lco","GEOMETRY_NAME=geom"
    ])

    
    sql_fix_towers = f"""
DO $$
BEGIN
  -- If 'geom' doesn't exist yet, repair it
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = '{towers_schema}'
      AND table_name   = '{towers_table}'
      AND column_name  = 'geom'
  ) THEN

    -- Case 1: ogr2ogr created 'wkb_geometry'
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = '{towers_schema}'
        AND table_name   = '{towers_table}'
        AND column_name  = 'wkb_geometry'
    ) THEN
      ALTER TABLE {towers_schema}.{towers_table}
        RENAME COLUMN wkb_geometry TO geom;

    ELSE
      -- Case 2: no geometry column at all -> build from lon/lat
      ALTER TABLE {towers_schema}.{towers_table}
        ADD COLUMN geom geometry(Point,4326);

      UPDATE {towers_schema}.{towers_table}
         SET geom = ST_SetSRID(ST_MakePoint(lon,lat),4326)
       WHERE geom IS NULL AND lon IS NOT NULL AND lat IS NOT NULL;
    END IF;

  END IF;
END
$$ LANGUAGE plpgsql;

-- Ensure spatial index exists
CREATE INDEX IF NOT EXISTS bb_towers_geom_gix
  ON {towers_schema}.{towers_table} USING GIST (geom);
"""

    
    run_psql_sql(host, port, db, user, pwd, "CREATE EXTENSION IF NOT EXISTS postgis;")
    run_psql_sql(host, port, db, user, pwd, f"CREATE SCHEMA IF NOT EXISTS {towers_schema} AUTHORIZATION {user};")


    # 2) Ensure Ookla geometry + create BB subset
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

    # 3) Analysis tables: counts / LTE / nearest LTE
    sql_analysis = f"""
CREATE SCHEMA IF NOT EXISTS {analysis_schema};

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

DROP TABLE IF EXISTS {analysis_schema}.ookla_centroids;
CREATE TABLE {analysis_schema}.ookla_centroids AS
SELECT o.ogc_fid AS tile_id, ST_Centroid(o.geom) AS geom
FROM {ookla_schema}.{ookla_table_bb} o;

CREATE INDEX IF NOT EXISTS ookla_centroids_gix
  ON {analysis_schema}.ookla_centroids USING GIST (geom);

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

    # 4) Export GeoJSONs (must include a geometry in the SELECT)
    sql_export1 = f"""
    SELECT o.geom,
           a.tile_id,
           a.towers_all,
           a.avg_download_kbps,
           a.avg_upload_kbps
    FROM {ookla_schema}.{ookla_table_bb} o
    JOIN {analysis_schema}.towers_per_tile a ON a.tile_id=o.ogc_fid
    """

    sql_export2 = f"""
    SELECT o.geom,
           s.tile_id,
           s.towers_lte,
           s.avg_download_kbps,
           s.avg_upload_kbps,
           d.meters_to_nearest_lte
    FROM {ookla_schema}.{ookla_table_bb} o
    JOIN {analysis_schema}.towers_per_tile_lte s ON s.tile_id=o.ogc_fid
    LEFT JOIN {analysis_schema}.nearest_lte_distance d ON d.tile_id=o.ogc_fid
    """

    out_dir = str(Path(".").resolve())
    sh([
        "docker","run","--rm",
        "-v",f"{out_dir}:/data",
        "--network","heatmapnet",
        gdal_image,
        "ogr2ogr","-f","GeoJSON","/data/"+out1,
        f"PG:host={host} port={port} dbname={db} user={user} password={pwd}",
        "-sql",sql_export1
    ])
    sh([
        "docker","run","--rm",
        "-v",f"{out_dir}:/data",
        "--network","heatmapnet",
        gdal_image,
        "ogr2ogr","-f","GeoJSON","/data/"+out2,
        f"PG:host={host} port={port} dbname={db} user={user} password={pwd}",
        "-sql",sql_export2
    ])

    print("\n🎉 ETL complete!")
    print(" -", out1)
    print(" -", out2)

if __name__ == "__main__":
    main()
