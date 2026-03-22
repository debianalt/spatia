"""Simplify hexagons GeoJSON: reduce coordinate precision, keep only h3index."""
import json
import os

INPUT = os.path.join(os.path.dirname(__file__), "output", "hexagons.geojson")
OUTPUT = os.path.join(os.path.dirname(__file__), "output", "hexagons-lite.geojson")

def round_coords(coords, precision=5):
    if isinstance(coords[0], (list, tuple)):
        return [round_coords(c, precision) for c in coords]
    return [round(c, precision) for c in coords]

with open(INPUT, "r") as f:
    data = json.load(f)

for feat in data["features"]:
    feat["properties"] = {"h3index": feat["properties"]["h3index"]}
    feat["geometry"]["coordinates"] = round_coords(feat["geometry"]["coordinates"])

with open(OUTPUT, "w") as f:
    json.dump(data, f, separators=(",", ":"))

size = os.path.getsize(OUTPUT) / (1024 * 1024)
print(f"Saved {OUTPUT} ({size:.1f} MB, {len(data['features'])} features)")
