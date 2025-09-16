# Serverless Heatmap Project

This project is a **tutorial-driven build** of a geospatial heatmap pipeline.  
It uses **PostGIS**, **Docker**, and **Leaflet** to process and visualize real-world datasets (Ookla internet speed test tiles + OpenCelliD cell towers) with a serverless-ready architecture.

---

## 🚀 Project Goals
- Build a lightweight, reproducible pipeline for geospatial data.
- Combine **internet performance data** (Ookla) with **mobile network infrastructure data** (OpenCelliD).
- Serve the results as vector tiles and display them in a **Leaflet web map**.
- Deploy in a **serverless environment** (AWS Lambda / Cloudflare Workers) for scalability.

---

## 📂 Repository Structure
```plaintext
serverless_heatmap/
│── docker-compose.yml          # PostGIS container setup
│── filter_barbados.py          # Python script to filter Ookla parquet to Barbados
│── index.html                  # Leaflet map to visualize GeoJSON output
│── ookla_bb_sample.geojson     # Sample Barbados tiles exported from PostGIS
│── mobile_q1_2024_part0.parquet # Example raw Ookla dataset (local use)
│── opencellid.csv.gz           # Downloaded OpenCelliD global dataset (compressed)
│── opencellid.csv              # Extracted OpenCelliD dataset (local use)
│── pgdata/                     # PostGIS database volume (local only, ignored in .git)
│── venv/                       # Python virtual environment (ignored in .git)
```

## 🛠️ Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/)
- [Python 3.x](https://www.python.org/downloads/)
- Optional: [QGIS](https://qgis.org/) for deeper GIS analysis

---

## 🐘 Database Setup (PostGIS)

### Start the PostGIS container
```bash
docker compose up -d
```

### Connect to the database
```bash
psql -h localhost -U admin -d geodb

```

### Create schemas
```bash
CREATE SCHEMA IF NOT EXISTS ookla_tiles;
CREATE SCHEMA IF NOT EXISTS cell_towers;

```

## 🌐 Data Sources

### 1. Ookla Internet Speed Data
- Public dataset on [AWS Open Data](https://registry.opendata.aws/speedtest-global-performance/).
- Imported into PostGIS using GDAL (`ogr2ogr`) via a Docker GDAL image.
- Normalized into a `geom` column for spatial queries.
- Example Barbados subset exported as `ookla_bb_sample.geojson`.

### 2. OpenCelliD Tower Data
- Requires free API key from [OpenCelliD](https://opencellid.org/).
- Download as CSV (global), filter to **Barbados MCC = 342**, then import into `cell_towers` schema.
- Converted into `POINT` geometries in PostGIS.

---

## 🗺️ Frontend (Leaflet Map)
- `index.html` provides a simple **Leaflet-based map**.
- Loads `ookla_bb_sample.geojson` for Barbados.
- Color-coded tiles show average download speeds.
- Can be extended to load vector tiles (`ST_AsMVT`) from PostGIS.

### To run locally
```bash
python -m http.server 8000

````

Then open:

http://localhost:8000/index.html


## 📜 License

This project is for **educational/tutorial purposes**.

**Data licensing**:  
- Ookla Open Data: [Terms of Use](https://registry.opendata.aws/speedtest-global-performance/)  
- OpenCelliD: [Open Database License (ODbL)](https://opencellid.org/license)  

