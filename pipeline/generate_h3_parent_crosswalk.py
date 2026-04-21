"""
Generate H3 parent crosswalk parquet: maps each res-9 hexagon to its parent at res 4-8.

Outputs:
  - {territory_dir}/h3_parent_crosswalk.parquet  (h3index, lat, lng, h3_res8..h3_res4)

Usage:
  python pipeline/generate_h3_parent_crosswalk.py
  python pipeline/generate_h3_parent_crosswalk.py --territory itapua_py
"""

import argparse
import json
import os
import sys

import h3
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR, get_territory

PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

H3_BASE_RES = 9
PARENT_RESOLUTIONS = [8, 7, 6, 5, 4]

BOUNDARY_FILES = {
    'misiones': os.path.join(PROJECT_ROOT, "src", "lib", "data", "misiones_boundary.json"),
    'itapua_py': os.path.join(PROJECT_ROOT, "src", "lib", "data", "itapua_boundary.json"),
}


def load_boundary(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        geojson = json.load(f)
    if geojson.get("type") == "FeatureCollection":
        return geojson["features"][0]["geometry"]
    elif geojson.get("type") == "Feature":
        return geojson["geometry"]
    return geojson


def load_hex_ids_from_geojson(t_dir: str) -> list[str]:
    """Extract h3index values from existing hexagons.geojson."""
    for fname in ('hexagons.geojson', 'hexagons-lite.geojson'):
        path = os.path.join(t_dir, fname)
        if os.path.exists(path):
            with open(path) as f:
                gj = json.load(f)
            return [feat['properties']['h3index'] for feat in gj['features']]
    return []


def main():
    parser = argparse.ArgumentParser(description="Generate H3 parent crosswalk")
    parser.add_argument("--territory", default="misiones",
                        help="Territory ID (default: misiones)")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    t_prefix = territory['output_prefix']
    t_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/')) if t_prefix else OUTPUT_DIR
    os.makedirs(t_dir, exist_ok=True)

    t_id = territory['id']
    print(f"Territory: {territory['label']} ({t_id})")

    hex_ids = load_hex_ids_from_geojson(t_dir)
    if hex_ids:
        print(f"Loaded {len(hex_ids):,} hexagons from hexagons.geojson")
    else:
        boundary_path = BOUNDARY_FILES.get(t_id)
        if not boundary_path or not os.path.exists(boundary_path):
            print(f"ERROR: No hexagons.geojson or boundary file for {t_id}")
            return 1
        print(f"Loading boundary from {boundary_path}...")
        boundary = load_boundary(boundary_path)
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
    out_path = os.path.join(t_dir, "h3_parent_crosswalk.parquet")
    df.to_parquet(out_path, index=False)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  -> Saved {out_path} ({size_kb:.0f} KB, {len(df):,} rows)")
    print(f"  -> Columns: {list(df.columns)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
