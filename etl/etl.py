#!/usr/bin/env python3
"""
ETL pipeline (no GDAL, uses only psql):
1) Import towers CSV -> PostGIS via \copy
2) Ensure Ookla geometry + create Barbados subset
3) Build analysis tables (counts, LTE, nearest LTE distance)
4) Export GeoJSON (Postgres generates FeatureCollection JSON)
"""

import os
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv, find_dotenv



def pg_table_exists(*, host, port=5432, db, user, pwd, qualified_table: str) -> bool:
    """Return True if schema.table exists, else False."""
    import subprocess, os
    env = os.environ.copy()
    env["PGPASSWORD"] = pwd
    sql = f"SELECT to_regclass('{qualified_table}') IS NOT NULL;"
    cmd = ["psql","-h",host,"-p",str(port),"-d",db,"-U",user,"--no-password","-tA","-c",sql]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env).stdout.strip()
    return out == "t"


def sh_show(cmd: list[str], elide_sql: bool = False):
    """Echo a safe version of the command before running."""
    if elide_sql:
        print("→", " ".join(cmd[:-1]), "[SQL elided]")
    else:
        print("→", " ".join(cmd))


def run_psql_sql(*, host: str, port=5432, db: str, user: str, pwd: str, sql: str):
    """Execute a single SQL statement with ON_ERROR_STOP."""
    env = os.environ.copy()
    env["PGPASSWORD"] = pwd
    cmd = [
        "psql", "-h", host, "-p", str(port), "-d", db, "-U", user,
        "--no-password", "-v", "ON_ERROR_STOP=1", "-c", sql,
    ]
    sh_show(cmd, elide_sql=True)
    subprocess.run(cmd, check=True, env=env)


def run_psql_copy_csv(*, host: str, port=5432, db: str, user: str, pwd: str,
                      csv_path: str, dest_table: str, copy_cols: str | None = None):
    """
    Copy a CSV from the client (this container) into Postgres.
    If copy_cols is provided, it must be like: "(col1,col2,...)"
    """
    env = os.environ.copy()
    env["PGPASSWORD"] = pwd
    if copy_cols:
        copy_cmd = fr"\copy {dest_table} {copy_cols} FROM '{csv_path}' WITH (FORMAT csv, HEADER true)"
    else:
        copy_cmd = fr"\copy {dest_table} FROM '{csv_path}' WITH (FORMAT csv, HEADER true)"
    cmd = ["psql","-h",host,"-p",str(port),"-d",db,"-U",user,"--no-password","-v","ON_ERROR_STOP=1","-c",copy_cmd]
    print("→ psql \\copy", csv_path, "→", dest_table, copy_cols or "")
    subprocess.run(cmd, check=True, env=env)


def run_psql_to_file(*, host: str, port=5432, db: str, user: str, pwd: str,
                     sql: str, out_path: str):
    """
    Run a SELECT that returns exactly one JSON row (FeatureCollection) and write it to a file.
    """
    env = os.environ.copy()
    env["PGPASSWORD"] = pwd
    # -t (tuples only), -A (unaligned), so we get just the JSON text
    cmd = [
        "psql", "-h", host, "-p", str(port), "-d", db, "-U", user,
        "--no-password", "-v", "ON_ERROR_STOP=1", "-tA", "-c", sql,
    ]
    sh_show(cmd, elide_sql=True)
    result = subprocess.run(cmd, check=True, env=env, capture_output=True, text=True)
    Path(out_path).write_text(result.stdout.strip() + "\n", encoding="utf-8")
    print("→ wrote", out_path)


def main():
    # -------- Env & args --------
    load_dotenv(find_dotenv(usecwd=True) or ".env")

    parser = argparse.ArgumentParser(description="ETL for Barbados connectivity (psql-only)")
    parser.add_argument("--towers-csv", required=True, help="Path INSIDE THIS CONTAINER to opencellid_barbados_towers.csv")
    args = parser.parse_args()

    # DB connection (strings are fine for psql)
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    db   = os.getenv("POSTGRES_DB", "geodb")
    user = os.getenv("POSTGRES_USER", "admin")
    pwd  = os.getenv("POSTGRES_PASSWORD", "StrongPass123")

    ookla_schema     = os.getenv("OOKLA_SCHEMA", "ookla_tiles")
    ookla_table      = os.getenv("OOKLA_TABLE", "raw_mobile_q1_2024")
    ookla_table_bb   = os.getenv("OOKLA_TABLE_BB", "raw_mobile_q1_2024_bb")
    towers_schema    = os.getenv("TOWERS_SCHEMA", "cell_towers")
    towers_table     = os.getenv("TOWERS_TABLE", "bb_towers")
    analysis_schema  = os.getenv("ANALYSIS_SCHEMA", "analysis")

    out1 = os.getenv("OUTPUT_GEOJSON_1", "towers_per_tile.geojson")
    out2 = os.getenv("OUTPUT_GEOJSON_2", "towers_per_tile_lte.geojson")

    # IMPORTANT: the CSV path must be valid inside THIS container
    towers_path = str(Path(args.towers_csv).resolve())
    if not Path(towers_path).exists():
        raise FileNotFoundError(
            f"CSV not found at {towers_path} inside this container.\n"
            "Mount the host folder into the etl container in docker-compose, e.g.:\n"
            "  volumes:\n"
            f"    - {Path(args.towers_csv).parent}:/data\n"
            "Then call: --towers-csv /data/opencellid_barbados_towers.csv"
        )

    # -------- DB prerequisites (BEFORE import) --------
    run_psql_sql(host=host, port=port, db=db, user=user, pwd=pwd,
                 sql="CREATE EXTENSION IF NOT EXISTS postgis;")
    run_psql_sql(host=host, port=port, db=db, user=user, pwd=pwd,
                 sql=f"CREATE SCHEMA IF NOT EXISTS {towers_schema} AUTHORIZATION {user};")
    
    # Create the schema if you intend to load Ookla later; harmless if unused
    run_psql_sql(host=host, port=port, db=db, user=user, pwd=pwd,
                sql=f"CREATE SCHEMA IF NOT EXISTS {ookla_schema};")


    # -------- Create table (minimal schema for \copy) --------
    # Adjust column list to match your CSV headers exactly.
    run_psql_sql(host=host, port=port, db=db, user=user, pwd=pwd, sql=f"""
DROP TABLE IF EXISTS {towers_schema}.{towers_table};

CREATE TABLE {towers_schema}.{towers_table} (
  lat           double precision,
  lon           double precision,
  mcc           integer,
  mnc           integer,
  lac           integer,
  cellid        bigint,
  averagesig    integer,
  range         integer,
  samples       integer,
  changeable    integer,
  radio         text,
  rnc           integer,
  cid           integer,
  tac           integer,
  sid           integer,
  nid           integer,
  bid           integer
);
""")

    copy_cols = "(lat,lon,mcc,mnc,lac,cellid,averagesig,range,samples,changeable,radio,rnc,cid,tac,sid,nid,bid)"

    # -------- Load CSV via \copy --------
    run_psql_copy_csv(
        host=host, port=port, db=db, user=user, pwd=pwd,
        csv_path=towers_path,
        dest_table=f"{towers_schema}.{towers_table}",
        copy_cols=copy_cols
    )

    # -------- Ensure towers geometry column + index --------
    sql_fix_towers = f"""
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = '{towers_schema}'
      AND table_name   = '{towers_table}'
      AND column_name  = 'geom'
  ) THEN
    ALTER TABLE {towers_schema}.{towers_table}
      ADD COLUMN geom geometry(Point,4326);

    UPDATE {towers_schema}.{towers_table}
       SET geom = ST_SetSRID(ST_MakePoint(lon,lat),4326)
     WHERE lon IS NOT NULL AND lat IS NOT NULL;
  END IF;
END
$$ LANGUAGE plpgsql;

CREATE INDEX IF NOT EXISTS bb_towers_geom_gix
  ON {towers_schema}.{towers_table} USING GIST (geom);
"""
    run_psql_sql(host=host, port=port, db=db, user=user, pwd=pwd, sql=sql_fix_towers)

    # -------- Ensure Ookla geometry + create Barbados subset --------
    # Ensure the Ookla schema exists (harmless if you don’t load it yet)
    run_psql_sql(host=host, port=port, db=db, user=user, pwd=pwd,
                sql=f"CREATE SCHEMA IF NOT EXISTS {ookla_schema};")

    # ---- Only proceed if the base Ookla table exists ----
    if pg_table_exists(host=host, port=port, db=db, user=user, pwd=pwd,
                      qualified_table=f"{ookla_schema}.{ookla_table}"):

        # Ensure geometry + create Barbados subset
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
        run_psql_sql(host=host, port=port, db=db, user=user, pwd=pwd, sql=sql_geom)

        # Proceed only if the BB subset exists
        if pg_table_exists(host=host, port=port, db=db, user=user, pwd=pwd,
                          qualified_table=f"{ookla_schema}.{ookla_table_bb}"):

            # ----- Analysis tables -----
            run_psql_sql(host=host, port=port, db=db, user=user, pwd=pwd, sql=f"""
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
            """)

            # ----- Exports -----
            run_psql_to_file(
                host=host, port=port, db=db, user=user, pwd=pwd,
                sql=f"""
                WITH data AS (
                  SELECT o.geom, a.tile_id, a.towers_all, a.avg_download_kbps, a.avg_upload_kbps
                  FROM {ookla_schema}.{ookla_table_bb} o
                  JOIN {analysis_schema}.towers_per_tile a ON a.tile_id=o.ogc_fid
                )
                SELECT jsonb_build_object(
                  'type','FeatureCollection',
                  'features', jsonb_agg(
                    jsonb_build_object(
                      'type','Feature',
                      'geometry', ST_AsGeoJSON(geom)::jsonb,
                      'properties', to_jsonb(data) - 'geom'
                    )
                  )
                )::text FROM data;""",
                out_path=str(Path(out1))
            )

            run_psql_to_file(
                host=host, port=port, db=db, user=user, pwd=pwd,
                sql=f"""
                WITH data AS (
                  SELECT o.geom, s.tile_id, s.towers_lte, s.avg_download_kbps, s.avg_upload_kbps,
                        d.meters_to_nearest_lte
                  FROM {ookla_schema}.{ookla_table_bb} o
                  JOIN {analysis_schema}.towers_per_tile_lte s ON s.tile_id=o.ogc_fid
                  LEFT JOIN {analysis_schema}.nearest_lte_distance d ON d.tile_id=o.ogc_fid
                )
                SELECT jsonb_build_object(
                  'type','FeatureCollection',
                  'features', jsonb_agg(
                    jsonb_build_object(
                      'type','Feature',
                      'geometry', ST_AsGeoJSON(geom)::jsonb,
                      'properties', to_jsonb(data) - 'geom'
                    )
                  )
                )::text FROM data;""",
                out_path=str(Path(out2))
            )

            print("\n🎉 ETL complete!")
            print(" -", out1)
            print(" -", out2)

        else:
            print(f"ℹ️ Skipping analysis/exports: missing table {ookla_schema}.{ookla_table_bb}")

    else:
        print(f"ℹ️ Skipping Ookla steps: base table {ookla_schema}.{ookla_table} not found. "
              f"Load Ookla tiles first or set OOKLA_SCHEMA/OOKLA_TABLE.")

if __name__ == "__main__":
    main()
