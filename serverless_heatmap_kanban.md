# 🗂️ Project Kanban – Serverless Heatmap

## ✅ Done
- [x] **Set up PostGIS in Docker**  
- [x] **Create schemas** (`ookla_tiles`, `cell_towers`)  
- [x] **Import Ookla parquet** and build Barbados subset  
- [x] **Export GeoJSON** and visualize in Leaflet  

---

## 🔄 In Progress
- [ ] **Sync OpenCelliD towers into PostGIS**  
  - Subtasks:  
    - Fetch data from API  
    - Filter for Barbados (MCC = 342)  
    - Import into `cell_towers` schema  

---

## 📝 To Do (Next Steps)
- [ ] **Generate vector tiles with ST_AsMVT**  
  - Use PostGIS to produce tilesets  
  - Test with Leaflet frontend  

- [ ] **Draft Python-based ETL pipeline**  
  - Automate: fetch → clean → load for both Ookla + OpenCelliD  
  - Store pipeline in GitHub repo  

- [ ] **Deploy as serverless backend**  
  - Options: AWS Lambda, Cloudflare Workers  
  - Host vector tiles + API  

- [ ] **Enhance frontend**  
  - Add interactive filters (ISP, speed, tower density)  
  - Polish UI for demo  

---

## 🚀 Stretch Goals (Future)
- [ ] **Integrate with real-time feeds** (if available)  
- [ ] **Analytics dashboard** (e.g. avg. speed per parish)  
- [ ] **Publish CARICOM case study** (policy + digital sovereignty tie-in)  
