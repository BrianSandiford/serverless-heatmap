# First Task: Install Docker and Run PostGIS Container

This is the very first step in building the **Serverless Telecom Heatmap**.

---

## 🎯 Objective
Set up a local PostGIS database to store and test Ookla and OpenCelliD data before deploying to AWS.

---

## 🧩 Steps

### 1. Install Docker
Ensure Docker Desktop (Windows/macOS) or Docker Engine (Linux) is installed.

Check installation:
```bash
docker --version
```

### 2. Run a PostGIS Container
Run this command to start PostgreSQL + PostGIS locally:

```bash
docker run --name pgis -e POSTGRES_PASSWORD=gis -p 5432:5432 -d postgis/postgis:16-3.4
```

- **Container name:** pgis  
- **User:** postgres  
- **Password:** gis  
- **Port:** 5432  
- **Database:** postgres (default)

Confirm it’s running:
```bash
docker ps
```

### 3. Connect to the Database
Use any SQL client (pgAdmin, DBeaver, or psql CLI).  
Connection string:
```
Host: localhost
Port: 5432
User: postgres
Password: gis
Database: postgres
```

### 4. Create Tables
You’ll create two key tables next:
- **ookla_tiles** – holds speed/latency data from Ookla parquet files.  
- **cell_towers** – holds tower coordinates and metadata from OpenCelliD.  

(SQL schema will be provided in the next step.)

### 5. Load Sample Data
Load a small Barbados subset:
- 500–1,000 Ookla tiles.  
- 1–2K OpenCelliD towers.

Then verify data presence:
```sql
SELECT COUNT(*) FROM ookla_tiles;
SELECT COUNT(*) FROM cell_towers;
```

### 6. Test Geometry & Tiles
Run a test vector tile query:
```sql
SELECT ST_AsMVTGeom(geom, ST_TileEnvelope(12, 1058, 1532)) FROM ookla_tiles LIMIT 1;
```

If it returns a valid geometry blob, your local PostGIS setup works perfectly.

---

## ✅ Outcome
You now have a functioning **local PostGIS environment** with real telecom data ready for:
- Lambda tile builder tests.
- KPI and coverage queries.
- Future AWS migration via SAM.

---

Next step → **Create SQL schema for ookla_tiles and cell_towers.**
