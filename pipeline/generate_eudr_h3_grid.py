"""
Generate H3 resolution-7 hexagonal grid for EUDR target provinces.

Covers Chaco, Salta, Santiago del Estero, and Formosa (~112K hexagons).
Uses a buffered dissolved boundary to ensure edge hexagons are included.

Outputs:
  - output/eudr/hexagons_eudr.geojson       (full GeoJSON with lat/lng)
  - output/eudr/hexagons_eudr_lite.geojson   (h3index + geometry only, for tippecanoe)

Usage:
  python pipeline/generate_eudr_h3_grid.py
"""

import json
import os
import sys
import time

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Polygon, mapping

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_eudr import (
    H3_EUDR_RESOLUTION,
    OUTPUT_DIR,
    GRID_PATH,
    GRID_LITE_PATH,
    MIN_EUDR_HEXAGONS,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOUNDARY_PATH = os.path.join(
    PROJECT_ROOT, "src", "lib", "data", "eudr_provinces_boundary.json"
)
DISSOLVED_PATH = os.path.join(
    PROJECT_ROOT, "src", "lib", "data", "eudr_provinces_dissolved.json"
)


def load_boundary() -> dict:
    """Load dissolved EUDR boundary GeoJSON, with buffer for edge coverage."""
    path = DISSOLVED_PATH if os.path.exists(DISSOLVED_PATH) else BOUNDARY_PATH

    with open(path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    if geojson.get("type") == "FeatureCollection":
        geom = geojson["features"][0]["geometry"]
    elif geojson.get("type") == "Feature":
        geom = geojson["geometry"]
    else:
        geom = geojson

    # Buffer ~15 km to capture edge hexagons (same pattern as Overture ingest)
    from shapely.geometry import shape as shp_shape
    buffered = shp_shape(geom).buffer(0.15)
    return mapping(buffered)


def load_province_boundaries() -> gpd.GeoDataFrame:
    """Load individual province boundaries for province assignment."""
    if not os.path.exists(BOUNDARY_PATH):
        return None
    return gpd.read_file(BOUNDARY_PATH)


def generate_h3_hexagons(boundary_geom: dict) -> list[str]:
    """Polyfill boundary geometry with H3 hexagons at resolution 7."""
    hexagons = h3.geo_to_cells(boundary_geom, res=H3_EUDR_RESOLUTION)
    return list(hexagons)


def hexagons_to_geodataframe(hex_ids: list[str]) -> gpd.GeoDataFrame:
    """Convert H3 hex IDs to a GeoDataFrame with polygon geometries."""
    records = []
    for h3id in hex_ids:
        boundary = h3.cell_to_boundary(h3id)
        coords = [(lng, lat) for lat, lng in boundary]
        coords.append(coords[0])
        ll = h3.cell_to_latlng(h3id)
        records.append({
            "h3index": h3id,
            "geometry": Polygon(coords),
            "lat": ll[0],
            "lng": ll[1],
        })

    return gpd.GeoDataFrame(records, crs="EPSG:4326")


def assign_provinces(hex_gdf: gpd.GeoDataFrame, provinces: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Assign each hexagon to its province via centroid containment."""
    from shapely.geometry import Point

    centroids = hex_gdf[["h3index", "lat", "lng"]].copy()
    centroids["geometry"] = [Point(lng, lat) for lat, lng in zip(centroids["lat"], centroids["lng"])]
    centroids_gdf = gpd.GeoDataFrame(centroids, crs="EPSG:4326")

    joined = gpd.sjoin(centroids_gdf, provinces[["id", "name", "geometry"]], how="left", predicate="within")
    # Drop duplicates from border hexagons (keep first match)
    joined = joined.drop_duplicates(subset=["h3index"], keep="first")
    joined = joined.set_index("h3index")
    hex_gdf["province_id"] = hex_gdf["h3index"].map(joined["id"]).values
    hex_gdf["province_name"] = hex_gdf["h3index"].map(joined["name"]).values

    # Hexagons in the buffer zone (outside provinces) get null — drop them
    n_outside = hex_gdf["province_id"].isna().sum()
    if n_outside > 0:
        print(f"  Dropping {n_outside:,} hexagons outside province boundaries (buffer zone)")
        hex_gdf = hex_gdf.dropna(subset=["province_id"]).reset_index(drop=True)

    return hex_gdf


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    t0 = time.time()

    print("Loading EUDR boundary (dissolved, buffered)...")
    boundary = load_boundary()

    print(f"Generating H3 grid at resolution {H3_EUDR_RESOLUTION}...")
    hex_ids = generate_h3_hexagons(boundary)
    print(f"  -> {len(hex_ids):,} hexagons generated (including buffer zone)")

    print("Building GeoDataFrame...")
    gdf = hexagons_to_geodataframe(hex_ids)

    # Assign provinces
    provinces = load_province_boundaries()
    if provinces is not None:
        print("Assigning provinces...")
        gdf = assign_provinces(gdf, provinces)
        for prov in gdf["province_name"].dropna().unique():
            n = (gdf["province_name"] == prov).sum()
            print(f"  {prov}: {n:,} hexagons")

    n_final = len(gdf)
    print(f"  -> {n_final:,} hexagons after province assignment")

    if n_final < MIN_EUDR_HEXAGONS:
        print(f"  WARNING: only {n_final:,} hexagons, expected >= {MIN_EUDR_HEXAGONS:,}")

    # Save full GeoJSON
    gdf.to_file(GRID_PATH, driver="GeoJSON")
    size_mb = os.path.getsize(GRID_PATH) / (1024 * 1024)
    print(f"  -> Saved {GRID_PATH} ({size_mb:.1f} MB)")

    # Save lite version (h3index + geometry only, for tippecanoe)
    lite = gdf[["h3index", "geometry"]].copy()
    lite.to_file(GRID_LITE_PATH, driver="GeoJSON")
    size_lite = os.path.getsize(GRID_LITE_PATH) / (1024 * 1024)
    print(f"  -> Saved {GRID_LITE_PATH} ({size_lite:.1f} MB)")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s! ({n_final:,} hexagons at H3 res-{H3_EUDR_RESOLUTION})")


if __name__ == "__main__":
    main()
