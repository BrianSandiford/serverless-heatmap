import geopandas as gpd
import matplotlib.pyplot as plt

gdf = gpd.read_file("towers_per_tile.geojson")
print("✅ File loaded:", len(gdf), "features")
print(gdf.head())

ax = gdf.plot(column="towers_all", legend=True, cmap="viridis", figsize=(8,6), edgecolor="black", linewidth=0.3)
ax.set_title("Towers per Tile (Barbados)")
plt.tight_layout()
plt.show()
