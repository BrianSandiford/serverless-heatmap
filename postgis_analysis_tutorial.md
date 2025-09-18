# PostGIS Analysis Tutorial — Annotated SQL

This document contains all the SQL commands we used, with **line-by-line explanations**.

---

## 1) PostGIS housekeeping on the towers table

```sql
ALTER TABLE cell_towers.bb_towers
  RENAME COLUMN wkb_geometry TO geom;

SELECT UpdateGeometrySRID('cell_towers','bb_towers','geom',4326);

CREATE INDEX IF NOT EXISTS bb_towers_geom_gix
  ON cell_towers.bb_towers USING GIST (geom);

CREATE INDEX IF NOT EXISTS bb_towers_radio_idx ON cell_towers.bb_towers (radio);
CREATE INDEX IF NOT EXISTS bb_towers_mnc_idx   ON cell_towers.bb_towers (mnc);

ANALYZE cell_towers.bb_towers;
```

---

## 2) Build geometry on the Ookla tiles from WKT

```sql
ALTER TABLE ookla_tiles.raw_mobile_q1_2024
  ADD COLUMN IF NOT EXISTS geom geometry(Polygon,4326);

UPDATE ookla_tiles.raw_mobile_q1_2024
SET geom = ST_GeomFromText(tile, 4326)
WHERE tile LIKE 'POLYGON(%';

CREATE INDEX IF NOT EXISTS raw_mobile_q1_2024_geom_gix
  ON ookla_tiles.raw_mobile_q1_2024 USING GIST (geom);
```

---

## 3) Make a Barbados-only subset of Ookla tiles

```sql
DROP TABLE IF EXISTS ookla_tiles.raw_mobile_q1_2024_bb;

CREATE TABLE ookla_tiles.raw_mobile_q1_2024_bb AS
SELECT o.*
FROM ookla_tiles.raw_mobile_q1_2024 o
WHERE o.geom IS NOT NULL
  AND ST_Intersects(
        o.geom,
        ST_MakeEnvelope(-59.95, 13.03, -59.35, 13.40, 4326)
      );

CREATE INDEX IF NOT EXISTS raw_mobile_q1_2024_bb_geom_gix
  ON ookla_tiles.raw_mobile_q1_2024_bb USING GIST (geom);
```

---

## 4) Main analysis: towers per tile + avg speeds

```sql
CREATE SCHEMA IF NOT EXISTS analysis;

DROP TABLE IF EXISTS analysis.towers_per_tile;

CREATE TABLE analysis.towers_per_tile AS
SELECT
  o.ogc_fid                        AS tile_id,
  COUNT(t.*)                       AS towers_all,
  AVG(o.avg_d_kbps)::numeric(12,2) AS avg_download_kbps,
  AVG(o.avg_u_kbps)::numeric(12,2) AS avg_upload_kbps
FROM ookla_tiles.raw_mobile_q1_2024_bb o
LEFT JOIN cell_towers.bb_towers t
  ON ST_Intersects(o.geom, t.geom)
GROUP BY o.ogc_fid;

CREATE INDEX IF NOT EXISTS towers_per_tile_tile_id_idx
  ON analysis.towers_per_tile (tile_id);
```

---

## 5) Variant: break counts by radio (LTE/UMTS/GSM)

```sql
DROP TABLE IF EXISTS analysis.towers_per_tile_by_radio;

CREATE TABLE analysis.towers_per_tile_by_radio AS
SELECT
  o.ogc_fid AS tile_id,
  SUM(CASE WHEN t.radio = 'LTE'  THEN 1 ELSE 0 END) AS towers_lte,
  SUM(CASE WHEN t.radio = 'UMTS' THEN 1 ELSE 0 END) AS towers_umts,
  SUM(CASE WHEN t.radio = 'GSM'  THEN 1 ELSE 0 END) AS towers_gsm,
  COUNT(t.*) AS towers_all,
  AVG(o.avg_d_kbps)::numeric(12,2) AS avg_download_kbps
FROM ookla_tiles.raw_mobile_q1_2024_bb o
LEFT JOIN cell_towers.bb_towers t
  ON ST_Intersects(o.geom, t.geom)
GROUP BY o.ogc_fid;

CREATE INDEX IF NOT EXISTS towers_per_tile_by_radio_tile_id_idx
  ON analysis.towers_per_tile_by_radio (tile_id);
```

---

## 6) Optional: distance to nearest LTE tower

```sql
DROP TABLE IF EXISTS analysis.ookla_centroids;
CREATE TABLE analysis.ookla_centroids AS
SELECT
  o.ogc_fid AS tile_id,
  ST_Centroid(o.geom) AS geom
FROM ookla_tiles.raw_mobile_q1_2024_bb o;

CREATE INDEX IF NOT EXISTS ookla_centroids_gix
  ON analysis.ookla_centroids USING GIST (geom);

DROP TABLE IF EXISTS analysis.nearest_lte_distance;
CREATE TABLE analysis.nearest_lte_distance AS
SELECT
  c.tile_id,
  MIN( ST_DistanceSphere(c.geom, t.geom) ) AS meters_to_nearest_lte
FROM analysis.ookla_centroids c
JOIN cell_towers.bb_towers t ON t.radio = 'LTE'
GROUP BY c.tile_id;

DROP TABLE IF EXISTS analysis.speed_vs_distance;
CREATE TABLE analysis.speed_vs_distance AS
SELECT
  o.ogc_fid AS tile_id,
  n.meters_to_nearest_lte,
  o.avg_d_kbps
FROM ookla_tiles.raw_mobile_q1_2024_bb o
LEFT JOIN analysis.nearest_lte_distance n
  ON o.ogc_fid = n.tile_id;
```

---

## 7) Export with geometry (for ogr2ogr)

```sql
SELECT
  o.geom,
  a.tile_id,
  a.towers_all,
  a.avg_download_kbps,
  a.avg_upload_kbps
FROM ookla_tiles.raw_mobile_q1_2024_bb o
JOIN analysis.towers_per_tile a
  ON a.tile_id = o.ogc_fid;
```

---

## Function glossary

- ST_GeomFromText → parse WKT text into geometry.  
- ST_MakeEnvelope → make a bounding-box rectangle.  
- ST_Intersects → true if geometries overlap.  
- ST_Centroid → center point of polygon.  
- ST_DistanceSphere → spherical distance (meters).  
- UpdateGeometrySRID → register CRS id for a geometry column.  
- CREATE INDEX … USING GIST → build a spatial index.  

---

## Mental model

- **Ookla tile = bucket polygon**  
- **Tower = point**  
- Spatial join = “Which points fall in which bucket?”  
- Group by tile = compute metrics per bucket.  
