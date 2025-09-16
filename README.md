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
