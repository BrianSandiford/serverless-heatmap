

# Building a Serverless Connectivity Heatmap for Barbados: My Journey (and Lessons Learned)

When I set out to build a **serverless connectivity heatmap** for Barbados, I expected to visualize cell towers — not battle Docker networking, PostGIS quirks, and file sizes larger than my laptop’s RAM.  

This is my story of how a small side project grew from a single Python script into a fully containerized data pipeline — one that now maps **3G, 4G, and 5G coverage** across the island using open data from **Ookla** and **OpenCelliD**.

---

## The Vision: Open, Serverless, and Transparent

The idea was simple:
> Build a public, lightweight map showing mobile coverage and internet performance across Barbados.

The stack would rely only on **open data and open tools**, with three main goals:
- **Serverless:** no heavy backend.
- **Reproducible:** everything containerized.
- **Informative:** merge real tower data with measured speeds.

---

## Phase 1: Early Setup — ETL in Docker, Web Served Manually

I started small — just one Docker container for ETL.  
It used Python, GDAL, and the PostgreSQL client to import OpenCelliD tower data, join it with Ookla’s global parquet tiles, and export GeoJSON files.

There was **no Nginx container** and **no PostGIS container** yet — just local testing and the ETL container doing all the heavy lifting.

To visualize the results, I served the map using Python’s simplest web server:

```bash
python -m http.server
```

That tiny one-liner served `index.html` and let me preview the Leaflet map in my browser. It was crude but effective.

Then came the debugging storm.

---

## The Debugging Odyssey (ETL-Only Phase)

These were the earliest, hardest lessons — all before I introduced the full Docker stack.

### 1. Docker Container Name Conflicts
```
Error: container name "postgis_container" is already in use
```
Docker keeps “stopped” containers around, blocking re-creation.  
**Lesson:** Clean up regularly:
```bash
docker ps -a
docker rm <container_name>
```

### 2. GDAL/ogr2ogr Format Issues
```
No such driver 'GeoJSON'
```
The real problem? Missing quotes:
```bash
-f "GeoJSON"
```
**Lesson:** GDAL syntax is strict — always quote format names.

### 3. Geometry Column Chaos
Imported towers had inconsistent geometry columns (`wkb_geometry`, `geom`, or none).  
Some GeoJSON exports showed `geometry: null`.  
**Lesson:** Standardize your geometry column and SRID right after import.

### 4. The Too-Large Global CSV
The global `cell_towers.csv.gz` file from OpenCelliD was **massive** — far too big to unzip or import locally.  
**Fix:** I wrote a Python/PowerShell script to fetch only the **Barbados subset** via tiled API calls.  
**Lesson:** Always subset early; never process global data when you only need one region.

### 5. Missing Environment Variables
`.env` values weren’t loading properly in Docker, breaking database connections.  
**Lesson:** Always confirm environment propagation — and print variables in your scripts before using them.

### 6. SQL “WITH” Clause Misplacement
A small syntax error caused cascading failures:  
```sql
WITH t AS (...) ;
CREATE TABLE new_table AS SELECT * FROM t;
```
should have been:  
```sql
CREATE TABLE new_table AS
WITH t AS (...) SELECT * FROM t;
```
**Lesson:** SQL syntax is unforgiving — placement matters.

### 7. OpenCelliD API Confusion
```
Invalid input data | 3
```
I had reversed the bounding box coordinates.  
**Lesson:** Longitude always comes before latitude. Always.

### 8. PostGIS Connection Errors
```
psql: could not connect to server: Connection refused
```
It wasn’t credentials — it was Docker networking.  
**Lesson:** Containers can’t see your host’s `localhost` unless explicitly bridged.

---

## Phase 2: The Breakthrough — Full Docker Compose Stack

After stabilizing the ETL pipeline, I expanded the project into a **multi-container setup**:
1. **PostGIS** — the spatial database backend.  
2. **ETL** — automated Python + GDAL ingestion.  
3. **Nginx** — a lightweight static web server for `index.html` and GeoJSON layers.

This was the turning point.  
No more manual imports or mismatched dependencies.  
Every container talked to each other on a shared network.  
From raw CSV and parquet to a running map — all automated.

---

## The Debugging Odyssey, Part II (Full Docker Stack)

### 4. CSV Column Mismatch
The tower CSV’s column order didn’t match the PostGIS table.  
Postgres imported it but shifted every field by one.  
**Lesson:** Explicitly define column order in `\copy` — never rely on headers.

### 5. ogr2ogr Path and Mount Issues
On Windows, volume mounts and PowerShell path syntax clashed.  
GDAL couldn’t find `/data/input.csv` even though it existed.  
**Lesson:** Always verify your mount paths inside the container:
```bash
docker compose exec etl ls /data
```

### 10. Windows Line Continuation Hell
PowerShell breaks multi-line Docker commands because `\` doesn’t escape like Bash.  
**Lesson:** Use backticks (`` ` ``) or one-liners on Windows — or switch to Git Bash.

---

## Phase 3: Visualization and 5G Expansion

With the ETL and database solid, I turned back to the frontend.

The **Leaflet.js** map evolved into a dynamic, layered visualization with:
- **All towers (blue)** for total density,  
- **LTE towers (green)** for 4G coverage,  
- **5G towers (indigo)** for new deployments,  
- and a **heatmap toggle** for density visualization.

Each popup showed:
- Tile ID  
- Tower count  
- Average download/upload speed  
- Nearest LTE or 5G tower distance  

Originally, I served it with:
```bash
python -m http.server
```
But once Nginx was added, everything lived in Docker — from ETL to web delivery.

---

### Adding 5G Support

When Barbados’ 5G rollout began, I normalized the tower data:

```sql
ALTER TABLE cell_towers.bb_towers
  ADD COLUMN IF NOT EXISTS radio_norm text;

UPDATE cell_towers.bb_towers
SET radio_norm = CASE
  WHEN upper(radio) LIKE '%5G%' THEN '5G'
  WHEN upper(radio) LIKE '%LTE%' THEN 'LTE'
  WHEN upper(radio) LIKE '%UMTS%' THEN '3G'
  WHEN upper(radio) LIKE '%GSM%' THEN '2G'
  ELSE 'OTHER'
END;
```

That update unlocked side-by-side LTE and 5G analysis in both SQL and Leaflet.

---

## Lessons Learned

- 🧱 **Docker is best introduced gradually.** Start with ETL-only, then scale up.  
- ⚙️ **PowerShell ≠ Bash.** Adjust commands for your platform.  
- 🌍 **Subset your data early.** Global datasets can overwhelm local machines.  
- 🗺️ **Normalize geometry immediately.** A consistent `geom` column saves hours of debugging.  
- 💡 **Document everything.** Every small fix later becomes automation.

---

## What’s Next

With the foundation stable, the next steps are:
- Correlate **5G coverage** with Ookla **speed performance**,  
- Introduce **operator-level breakdowns** via MCC/MNC,  
- Visualize **speed trends over time** using quarterly Ookla datasets.

This project now acts as both a technical showcase and a transparency tool — helping visualize digital infrastructure growth across Barbados.

---

## Final Thoughts

Looking back, every failure — from “container already exists” to null geometries — taught me something fundamental about reproducibility and data integrity.

I began with a single ETL container and `python -m http.server`.  
Now, I have a fully Dockerized system automating data ingestion, analysis, and visualization end to end.

> **Debugging isn’t a detour. It’s the journey that makes your pipeline bulletproof.**
