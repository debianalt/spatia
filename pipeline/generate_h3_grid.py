"""
Generate H3 resolution-8 hexagonal grid for Misiones province.

Outputs:
  - hexagons.geojson  (GeoJSON FeatureCollection, ~40K hexagons)
  - h3_radio_crosswalk.parquet  (h3index × redcode spatial join)

Usage:
  python pipeline/generate_h3_grid.py

Tippecanoe (run once manually after GeoJSON generation):
  tippecanoe -o hexagons-v1.pmtiles -z12 -Z5 -l hexagons \
    --no-feature-limit --no-tile-size-limit \
    --coalesce-densest-as-needed \
    pipeline/output/hexagons.geojson
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
RADIOS_PMT = os.path.join(PROJECT_ROOT, "db", "parquets")

H3_RESOLUTION = 8  # ~0.74 km² per hexagon, ~40K hexagons for Misiones


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


def build_crosswalk(hex_gdf: gpd.GeoDataFrame, radios_path: str | None = None) -> pd.DataFrame:
    """
    Spatial join: assign each H3 centroid to the radio censal it falls within.

    If radios GeoJSON/parquet is not available, creates a placeholder
    crosswalk with h3index and empty redcode (to be filled later).
    """
    if radios_path and os.path.exists(radios_path):
        radios = gpd.read_file(radios_path)
        # Use centroid of each hex for point-in-polygon join
        centroids = hex_gdf.copy()
        centroids["geometry"] = centroids.geometry.centroid
        joined = gpd.sjoin(centroids, radios[["redcode", "geometry"]], how="left", predicate="within")
        return joined[["h3index", "redcode"]].drop_duplicates()

    # Placeholder: no radios shapefile available
    return pd.DataFrame({"h3index": hex_gdf["h3index"], "redcode": None})


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading Misiones boundary...")
    boundary = load_boundary()

    print(f"Generating H3 grid at resolution {H3_RESOLUTION}...")
    hex_ids = generate_h3_hexagons(boundary)
    print(f"  → {len(hex_ids):,} hexagons generated")

    print("Building GeoDataFrame...")
    gdf = hexagons_to_geodataframe(hex_ids)

    # Save GeoJSON
    geojson_path = os.path.join(OUTPUT_DIR, "hexagons.geojson")
    gdf.to_file(geojson_path, driver="GeoJSON")
    size_mb = os.path.getsize(geojson_path) / (1024 * 1024)
    print(f"  → Saved {geojson_path} ({size_mb:.1f} MB)")

    # Build crosswalk (placeholder without radios shapefile)
    print("Building H3 ↔ radio crosswalk...")
    crosswalk = build_crosswalk(gdf)
    crosswalk_path = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk.parquet")
    crosswalk.to_parquet(crosswalk_path, index=False)
    print(f"  → Saved {crosswalk_path}")

    print(f"\nDone! Next steps:")
    print(f"  1. Run tippecanoe to generate PMTiles:")
    print(f"     tippecanoe -o hexagons-v1.pmtiles -z12 -Z5 -l hexagons \\")
    print(f"       --no-feature-limit --no-tile-size-limit \\")
    print(f"       --coalesce-densest-as-needed \\")
    print(f"       {geojson_path}")
    print(f"  2. Upload to R2:")
    print(f"     wrangler r2 object put neahub-public/tiles/hexagons-v1.pmtiles --file hexagons-v1.pmtiles --remote")
    print(f"     wrangler r2 object put neahub-public/data/h3_radio_crosswalk.parquet --file {crosswalk_path} --remote")


if __name__ == "__main__":
    main()
