# 🚧 Troubleshooting Log — Serverless Heatmap Project

This document tracks the problems we encountered during development and how we solved them.

---

## 1. Docker container name conflict
**Error:**
```
Error response from daemon: Conflict. The container name "/postgis_container" is already in use...
```
**Cause:** Container with same name already running or exited but not removed.  
**Fix:**
```bash
docker ps -a
docker stop <container_id>
docker rm <container_id>
```

---

## 2. ogr2ogr not recognized
**Error:**
```
ogr2ogr : The term 'ogr2ogr' is not recognized...
```
**Cause:** GDAL not installed on Windows.  
**Fix:** Use GDAL via Docker:
```powershell
docker run --rm -v ${PWD}:/data ghcr.io/osgeo/gdal:ubuntu-full-latest ogr2ogr ...
```

---

## 3. GDAL export driver issue
**Error:** `No such driver 'GeoJSON'`  
**Cause:** Driver name not quoted.  
**Fix:** Use:
```powershell
-f "GeoJSON"
```

---

## 4. GeoJSON with no geometry
**Symptom:** Exported GeoJSON had `geometry = None`.  
**Cause:** Exported table had no geometry.  
**Fix:** Join metrics table back to tiles with geometry:
```sql
SELECT o.geom, a.tile_id, a.towers_all, a.avg_download_kbps, a.avg_upload_kbps
FROM ookla_tiles.raw_mobile_q1_2024_bb o
JOIN analysis.towers_per_tile a
  ON a.tile_id = o.ogc_fid;
```

---

## 5. PowerShell line continuation issues
**Error:** `invalid reference format` when running Docker.  
**Cause:** Linux-style `\` line breaks pasted into PowerShell.  
**Fix:** Use one-liners or backticks (`` ` ``) in PowerShell.

---

## 6. Environment variable not set
**Error:**
```
❌ OPENCELLID_TOKEN is not set.
```
**Cause:** `.env` not loaded or variable not exported.  
**Fix:** Add `.env` + VS Code settings, confirm with Python `os.getenv`.  

---

## 7. OpenCellID API errors
**Error:**
```
info | code
Invalid input data | 3
```
**Cause:** Wrong BBOX parameter order.  
**Fix:** Use correct order `latmin,lonmin,latmax,lonmax`.  

---

## 8. Too-large global CSV
**Problem:** `cell_towers.csv.gz` too big to unzip locally.  
**Fix:** Query Barbados subset via tiled API calls with Python/PowerShell script.

---

## 9. ST_TileEnvelope errors
**Error:**
```
ERROR: function st_tileenvelope(double precision, double precision, integer) does not exist
```
**Cause:** `tile` column already contained WKT polygons.  
**Fix:** Use `ST_GeomFromText` instead of `ST_TileEnvelope`.

---

## 10. WITH + CREATE TABLE syntax
**Error:**
```
syntax error at or near "CREATE"
```
**Cause:** `WITH` placed outside `CREATE TABLE ... AS`.  
**Fix:** Put `WITH` inside the statement.

---

## 11. GeoPandas plotting error
**Error:**
```
ValueError: aspect must be finite and positive
```
**Cause:** GeoJSON had no geometry.  
**Fix:** Re-export with geometry.

---

## 12. Leaflet toggle for visualization
**Problem:** Needed to view both tower count and download speeds.  
**Fix:** Added dropdown + dynamic styling in `index.html`.

---

# ✅ Key Lessons
- Ensure geometry columns exist before exporting.
- Mind syntax differences between PowerShell and Bash.
- Subset large global datasets early (Barbados-only).
- Index geometry columns for faster spatial joins.
- Always verify exported GeoJSON with GeoPandas before web mapping.

