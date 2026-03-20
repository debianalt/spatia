"""
Generate PMTiles from hexagons-lite.geojson using pure Python.

Replaces tippecanoe for environments without a C++ compiler.
Uses mapbox-vector-tile for MVT encoding and pmtiles for the archive.

Usage:
  python pipeline/geojson_to_pmtiles.py

Output:
  pipeline/output/hexagons-v2.pmtiles
"""

import gzip
import json
import math
import os
import time
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import mapbox_vector_tile as mvt
from pmtiles.tile import TileType, zxy_to_tileid
from pmtiles.writer import Compression, Writer as PMTilesWriter
from shapely.geometry import mapping, shape
from shapely.ops import clip_by_rect

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(SCRIPT_DIR, "output", "hexagons-lite.geojson")
OUTPUT = os.path.join(SCRIPT_DIR, "output", "hexagons-v2.pmtiles")

MIN_ZOOM = 5
MAX_ZOOM = 12
LAYER_NAME = "hexagons"
EXTENT = 4096

# Misiones bounding box (tight)
BBOX = {"west": -56.1, "south": -28.2, "east": -53.5, "north": -25.9}


def lng_lat_to_tile(lng, lat, zoom):
    """Convert lng/lat to tile x/y at given zoom."""
    n = 2 ** zoom
    x = int((lng + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    x = max(0, min(n - 1, x))
    y = max(0, min(n - 1, y))
    return x, y


def tile_bounds(x, y, z):
    """Return (west, south, east, north) for tile z/x/y."""
    n = 2 ** z
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return west, south, east, north


def get_tiles_for_bbox(bbox, zoom):
    """Get all tile coordinates covering a bounding box at given zoom."""
    x_min, y_min = lng_lat_to_tile(bbox["west"], bbox["north"], zoom)
    x_max, y_max = lng_lat_to_tile(bbox["east"], bbox["south"], zoom)
    tiles = []
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tiles.append((x, y))
    return tiles


def features_to_mvt(features, tile_bounds_wsen, layer_name, extent=4096):
    """Encode features into MVT bytes, clipping to tile bounds."""
    w, s, e, n = tile_bounds_wsen
    # Small buffer to avoid clipping artifacts at tile edges
    buf = (e - w) * 0.01
    clipped = []
    for feat in features:
        geom = feat["geometry"]
        try:
            c = clip_by_rect(geom, w - buf, s - buf, e + buf, n + buf)
        except Exception:
            continue
        if c.is_empty:
            continue
        clipped.append({
            "geometry": c,
            "properties": feat["properties"],
        })

    if not clipped:
        return None

    # Build layer dict for mapbox_vector_tile
    layer = {
        "name": layer_name,
        "features": [
            {
                "geometry": mapping(f["geometry"]),
                "properties": f["properties"],
            }
            for f in clipped
        ],
    }

    return mvt.encode(
        [layer],
        quantize_bounds=(w, s, e, n),
        extents=extent,
    )


def main():
    t0 = time.time()

    print(f"Loading {INPUT}...")
    with open(INPUT, "r") as f:
        geojson = json.load(f)

    # Parse all features into shapely geometries
    features = []
    for feat in geojson["features"]:
        geom = shape(feat["geometry"])
        features.append({
            "geometry": geom,
            "properties": feat.get("properties", {}),
        })
    print(f"  -> {len(features):,} features loaded")

    # Build spatial index (simple grid at zoom 12 for fast lookup)
    print("Building spatial index...")
    from collections import defaultdict
    grid = defaultdict(list)
    for i, feat in enumerate(features):
        c = feat["geometry"].centroid
        tx, ty = lng_lat_to_tile(c.x, c.y, MAX_ZOOM)
        grid[(tx, ty)].append(i)

    # Generate tiles
    tile_data = {}
    total_tiles = 0

    for z in range(MIN_ZOOM, MAX_ZOOM + 1):
        tiles = get_tiles_for_bbox(BBOX, z)
        written = 0
        t_z = time.time()

        for x, y in tiles:
            bounds = tile_bounds(x, y, z)

            # Find candidate features via grid lookup
            # Map this tile to zoom-12 tiles it covers
            scale = 2 ** (MAX_ZOOM - z)
            x12_min = x * scale
            x12_max = (x + 1) * scale - 1
            y12_min = y * scale
            y12_max = (y + 1) * scale - 1

            candidate_indices = set()
            for gx in range(x12_min, x12_max + 1):
                for gy in range(y12_min, y12_max + 1):
                    candidate_indices.update(grid.get((gx, gy), []))

            if not candidate_indices:
                continue

            candidates = [features[i] for i in candidate_indices]
            tile_bytes = features_to_mvt(candidates, bounds, LAYER_NAME, EXTENT)

            if tile_bytes:
                compressed = gzip.compress(tile_bytes)
                tile_id = zxy_to_tileid(z, x, y)
                tile_data[tile_id] = compressed
                written += 1

        elapsed = time.time() - t_z
        total_tiles += written
        print(f"  z{z}: {written} tiles ({elapsed:.1f}s)")

    # Write PMTiles
    print(f"\nWriting {OUTPUT} ({total_tiles} tiles)...")
    with open(OUTPUT, "wb") as f:
        writer = PMTilesWriter(f)
        for tile_id in sorted(tile_data.keys()):
            writer.write_tile(tile_id, tile_data[tile_id])

        header = {
            "tile_type": TileType.MVT,
            "tile_compression": Compression.GZIP,
            "min_zoom": MIN_ZOOM,
            "max_zoom": MAX_ZOOM,
            "min_lon": BBOX["west"],
            "min_lat": BBOX["south"],
            "max_lon": BBOX["east"],
            "max_lat": BBOX["north"],
            "center_lon": (BBOX["west"] + BBOX["east"]) / 2,
            "center_lat": (BBOX["south"] + BBOX["north"]) / 2,
            "center_zoom": 8,
        }
        metadata = {
            "name": "hexagons",
            "description": "H3 res-9 hexagonal grid for Misiones",
            "vector_layers": [
                {
                    "id": LAYER_NAME,
                    "fields": {"h3index": "String"},
                    "minzoom": MIN_ZOOM,
                    "maxzoom": MAX_ZOOM,
                }
            ],
        }
        writer.finalize(header, metadata)

    size_mb = os.path.getsize(OUTPUT) / (1024 * 1024)
    elapsed = time.time() - t0
    print(f"  -> {OUTPUT} ({size_mb:.1f} MB, {elapsed:.0f}s total)")


if __name__ == "__main__":
    main()
