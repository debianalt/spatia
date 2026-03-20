"""
Generate H3 resolution-9 hexagonal grid for Misiones province.

Outputs:
  - hexagons.geojson  (GeoJSON FeatureCollection, ~280K hexagons)
  - h3_radio_crosswalk.parquet  (h3index × redcode × weight, intersection-weighted)

Usage:
  python pipeline/generate_h3_grid.py

Tippecanoe (run once manually after GeoJSON generation):
  tippecanoe -o hexagons-v2.pmtiles -z12 -Z5 -l hexagons \
    --no-feature-limit --no-tile-size-limit \
    --coalesce-densest-as-needed \
    pipeline/output/hexagons-lite.geojson
"""

import json
import os
import sys

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Polygon

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BOUNDARY_PATH = os.path.join(PROJECT_ROOT, "src", "lib", "data", "misiones_boundary.json")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
RADIOS_PATH = os.path.join(OUTPUT_DIR, "radios_misiones.parquet")

H3_RESOLUTION = 9  # ~0.105 km² per hexagon, ~280K hexagons for Misiones


def load_boundary() -> dict:
    """Load Misiones boundary GeoJSON."""
    with open(BOUNDARY_PATH, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    # Handle both Feature and FeatureCollection
    if geojson.get("type") == "FeatureCollection":
        # Use the first (and likely only) feature
        return geojson["features"][0]["geometry"]
    elif geojson.get("type") == "Feature":
        return geojson["geometry"]
    else:
        # Assume it's a raw geometry
        return geojson


def generate_h3_hexagons(boundary_geom: dict) -> list[str]:
    """Polyfill boundary geometry with H3 hexagons at given resolution."""
    hexagons = h3.geo_to_cells(boundary_geom, res=H3_RESOLUTION)
    return list(hexagons)


def hexagons_to_geodataframe(hex_ids: list[str]) -> gpd.GeoDataFrame:
    """Convert H3 hex IDs to a GeoDataFrame with polygon geometries."""
    records = []
    for h3id in hex_ids:
        boundary = h3.cell_to_boundary(h3id)
        # h3 returns (lat, lng) tuples; Shapely needs (lng, lat)
        coords = [(lng, lat) for lat, lng in boundary]
        coords.append(coords[0])  # close the ring
        records.append({
            "h3index": h3id,
            "geometry": Polygon(coords),
            "lat": h3.cell_to_latlng(h3id)[0],
            "lng": h3.cell_to_latlng(h3id)[1],
        })

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    return gdf


def build_weighted_crosswalk(hex_gdf: gpd.GeoDataFrame, radios_path: str) -> pd.DataFrame:
    """
    Intersection-weighted crosswalk: each H3 hexagon is linked to every
    radio censal it overlaps, with a weight proportional to the fraction
    of the radio's area covered by the intersection.

    weight = intersection_area / radio_area  (sums to ~1.0 per redcode)
    """
    if not os.path.exists(radios_path):
        print(f"  WARNING: {radios_path} not found — run export_radios.py first")
        return pd.DataFrame({"h3index": hex_gdf["h3index"], "redcode": None, "weight": None})

    radios = gpd.read_parquet(radios_path)
    radios = radios.to_crs(epsg=32721)   # UTM 21S for area in m²
    hex_proj = hex_gdf.to_crs(epsg=32721)

    # Pre-compute radio areas
    radios["radio_area"] = radios.geometry.area

    print("  Computing spatial overlay (intersection)...")
    overlay = gpd.overlay(hex_proj, radios, how="intersection")
    overlay["intersection_area"] = overlay.geometry.area

    # Map radio_area back and compute weight
    radio_area_map = radios.set_index("redcode")["radio_area"]
    overlay["radio_area"] = overlay["redcode"].map(radio_area_map)
    overlay["weight"] = overlay["intersection_area"] / overlay["radio_area"]

    result = overlay[["h3index", "redcode", "weight"]].reset_index(drop=True)
    print(f"  -> {len(result):,} crosswalk rows")
    return result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading Misiones boundary...")
    boundary = load_boundary()

    print(f"Generating H3 grid at resolution {H3_RESOLUTION}...")
    hex_ids = generate_h3_hexagons(boundary)
    print(f"  -> {len(hex_ids):,} hexagons generated")

    print("Building GeoDataFrame...")
    gdf = hexagons_to_geodataframe(hex_ids)

    # Save GeoJSON
    geojson_path = os.path.join(OUTPUT_DIR, "hexagons.geojson")
    gdf.to_file(geojson_path, driver="GeoJSON")
    size_mb = os.path.getsize(geojson_path) / (1024 * 1024)
    print(f"  -> Saved {geojson_path} ({size_mb:.1f} MB)")

    # Build weighted crosswalk
    print("Building weighted H3 <-> radio crosswalk...")
    crosswalk = build_weighted_crosswalk(gdf, RADIOS_PATH)
    crosswalk_path = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk.parquet")
    crosswalk.to_parquet(crosswalk_path, index=False)
    print(f"  -> Saved {crosswalk_path}")

    print(f"\nDone! Next steps:")
    print(f"  1. Simplify: python pipeline/simplify_geojson.py")
    print(f"  2. Tippecanoe:")
    print(f"     tippecanoe -o pipeline/output/hexagons-v2.pmtiles -z12 -Z5 -l hexagons \\")
    print(f"       --no-feature-limit --no-tile-size-limit \\")
    print(f"       --coalesce-densest-as-needed \\")
    print(f"       pipeline/output/hexagons-lite.geojson")
    print(f"  3. Upload: python pipeline/upload_to_r2.py --all")


if __name__ == "__main__":
    main()
