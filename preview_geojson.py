import geopandas as gpd
import matplotlib.pyplot as plt

# Load the exported GeoJSON
gdf = gpd.read_file("towers_per_tile.geojson")

print("✅ File loaded")
print(gdf.head())  # show first few rows

# Quick plot
gdf.plot(column="towers_all", legend=True, cmap="viridis", figsize=(8, 6))
plt.title("Towers per Tile (Barbados)")
plt.show()
