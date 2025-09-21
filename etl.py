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
