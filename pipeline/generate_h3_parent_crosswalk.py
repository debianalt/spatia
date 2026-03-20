"""
Generate H3 parent crosswalk parquet: maps each res-9 hexagon to its parent at res 4-8.

Outputs:
  - h3_parent_crosswalk.parquet  (h3index, lat, lng, h3_res8, h3_res7, h3_res6, h3_res5, h3_res4)

Usage:
  python pipeline/generate_h3_parent_crosswalk.py

Upload to R2:
  wrangler r2 object put neahub-public/data/h3_parent_crosswalk.parquet \
    --file pipeline/output/h3_parent_crosswalk.parquet --remote
"""

import json
import os

import h3
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BOUNDARY_PATH = os.path.join(PROJECT_ROOT, "src", "lib", "data", "misiones_boundary.json")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

H3_BASE_RES = 9
PARENT_RESOLUTIONS = [8, 7, 6, 5, 4]


def load_boundary() -> dict:
    with open(BOUNDARY_PATH, "r", encoding="utf-8") as f:
        geojson = json.load(f)
    if geojson.get("type") == "FeatureCollection":
        return geojson["features"][0]["geometry"]
    elif geojson.get("type") == "Feature":
        return geojson["geometry"]
    return geojson


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading Misiones boundary...")
    boundary = load_boundary()

    print(f"Generating H3 grid at resolution {H3_BASE_RES}...")
    hex_ids = list(h3.geo_to_cells(boundary, res=H3_BASE_RES))
    print(f"  -> {len(hex_ids):,} hexagons")

    print("Computing parent crosswalk...")
    records = []
    for h3id in hex_ids:
        lat, lng = h3.cell_to_latlng(h3id)
        row = {
            "h3index": h3id,
            "lat": round(lat, 6),
            "lng": round(lng, 6),
        }
        for res in PARENT_RESOLUTIONS:
            row[f"h3_res{res}"] = h3.cell_to_parent(h3id, res)
        records.append(row)

    df = pd.DataFrame(records)
    out_path = os.path.join(OUTPUT_DIR, "h3_parent_crosswalk.parquet")
    df.to_parquet(out_path, index=False)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  -> Saved {out_path} ({size_kb:.0f} KB, {len(df):,} rows)")
    print(f"  -> Columns: {list(df.columns)}")

    print(f"\nUpload to R2:")
    print(f"  wrangler r2 object put neahub-public/data/h3_parent_crosswalk.parquet \\")
    print(f"    --file {out_path} --remote")


if __name__ == "__main__":
    main()
