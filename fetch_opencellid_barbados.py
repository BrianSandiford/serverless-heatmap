import os
import time
import math
import csv
import requests
from typing import Optional

from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Load .env robustly no matter where you run from (Run button, debugger, terminal)
env_path = find_dotenv(usecwd=True) or str(Path(__file__).parent / ".env")
load_dotenv(env_path)




TOKEN = os.getenv("OPENCELLID_TOKEN")
print("Loaded OPENCELLID_TOKEN (len):", len(TOKEN) if TOKEN else 0)
if not TOKEN:
    # helpful debug so you can see where it's looking
    raise SystemExit(f"❌ OPENCELLID_TOKEN is not set. Tried .env at: {env_path}")



# Barbados extent (latmin, lonmin, latmax, lonmax)
LAT_MIN, LON_MIN = 13.03, -59.95
LAT_MAX, LON_MAX = 13.40, -59.35

# Tile step in degrees (~0.01° ≈ 1.1 km). Keep area < 4 km².
STEP_LAT = 0.01
STEP_LON = 0.01

# Pagination settings
LIMIT = 50
SLEEP_BETWEEN_CALLS = 0.12  # seconds; be polite to the API

# Optional technology filter: "GSM", "UMTS", "LTE", "NR", "NBIOT", "CDMA"
RADIO: Optional[str] = None  # e.g., "LTE" or None for all

# <<< CHANGE THE OUTPUT FILENAME HERE >>>
OUTPUT_CSV = "opencellid_barbados_towers.csv"
# -------------------------------------


def req(url: str, timeout=60, max_retries=3) -> requests.Response:
    """HTTP GET with simple retries."""
    last_err = None
    for _ in range(max_retries):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            time.sleep(0.5)
    raise last_err


def get_size(bbox: str) -> int:
    base = "https://opencellid.org/cell/getInAreaSize"
    q = f"key={TOKEN}&BBOX={bbox}&format=json"
    if RADIO:
        q += f"&radio={RADIO}"
    url = f"{base}?{q}"
    r = req(url, timeout=30)
    try:
        return int(r.json().get("count", 0))
    except Exception:
        return 0


def get_page_csv(bbox: str, offset: int) -> str:
    base = "https://opencellid.org/cell/getInArea"
    q = f"key={TOKEN}&BBOX={bbox}&format=csv&limit={LIMIT}&offset={offset}"
    if RADIO:
        q += f"&radio={RADIO}"
    url = f"{base}?{q}"
    r = req(url, timeout=60)
    return r.text


def main():

    # Prepare output (write header once later)
    wrote_header = False
    total_rows_written = 0
    tiles_visited = 0

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as out_f:
        writer = None  # will init after first page

        lat = LAT_MIN
        while lat < LAT_MAX:
            lat_top = min(lat + STEP_LAT, LAT_MAX)
            lon = LON_MIN
            while lon < LON_MAX:
                lon_right = min(lon + STEP_LON, LON_MAX)

                # API requires: latmin,lonmin,latmax,lonmax
                bbox = f"{lat:.5f},{lon:.5f},{lat_top:.5f},{lon_right:.5f}"
                tiles_visited += 1

                # Ask size (how many cells in this tile)
                try:
                    count = get_size(bbox)
                except Exception as e:
                    print(f"WARNING: size failed for {bbox}: {e}")
                    lon = lon_right
                    time.sleep(SLEEP_BETWEEN_CALLS)
                    continue

                if count > 0:
                    print(f"HIT {bbox} -> {count} cells")
                    pages = math.ceil(count / LIMIT)
                    offset = 0
                    for _ in range(pages):
                        try:
                            csv_text = get_page_csv(bbox, offset)
                        except Exception as e:
                            print(f"WARNING: page fetch failed for {bbox} offset={offset}: {e}")
                            offset += LIMIT
                            time.sleep(SLEEP_BETWEEN_CALLS)
                            continue

                        # split into lines, skip empties
                        lines = [ln for ln in csv_text.splitlines() if ln.strip()]
                        if not lines:
                            offset += LIMIT
                            time.sleep(SLEEP_BETWEEN_CALLS)
                            continue

                        # init writer on first page (use header from API)
                        if not wrote_header:
                            header = lines[0].split(",")
                            writer = csv.writer(out_f)
                            writer.writerow(header)
                            wrote_header = True

                        # write rows without header
                        for row in lines[1:]:
                            writer.writerow(row.split(","))
                            total_rows_written += 1

                        offset += LIMIT
                        time.sleep(SLEEP_BETWEEN_CALLS)
                else:
                    # Uncomment if you want to see empty tiles:
                    # print(f"EMPTY {bbox}")
                    pass

                lon = lon_right
                time.sleep(SLEEP_BETWEEN_CALLS)
            lat = lat_top

    print(f"✅ Done. Tiles visited: {tiles_visited}; rows written: {total_rows_written}")
    print(f"📄 Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
