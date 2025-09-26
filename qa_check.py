import json

def check_geojson(path, key):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"🔎 Checking {path} ...")
    print("Total features:", len(data["features"]))

    # Look at the first 3 features
    for f in data["features"][:3]:
        props = f["properties"]
        print({k: props.get(k) for k in [key, "avg_download_kbps", "avg_upload_kbps"]})

# Run checks
check_geojson("towers_per_tile.geojson", "towers_all")
check_geojson("towers_per_tile_lte.geojson", "towers_lte")
