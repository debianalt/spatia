"""
Build Itapúa district polygon PMTiles from GAUL GeoJSON.

Each polygon gets properties: district (ADM2_NAME), adm2_code, personas, hogares.
Source-layer name: 'districts' (must match Map.svelte 'source-layer' value).

Usage:
  python pipeline/build_itapua_districts.py

Output:
  pipeline/output/itapua_districts.pmtiles

R2 upload:
  npx wrangler r2 object put neahub/data/tiles/itapua_districts.pmtiles \
    --file pipeline/output/itapua_districts.pmtiles --remote
"""

import gzip
import math
import os
from collections import defaultdict

import geopandas as gpd
import mapbox_vector_tile as mvt
import pandas as pd
from pmtiles.tile import TileType, zxy_to_tileid
from pmtiles.writer import Compression, Writer as PMTilesWriter
from shapely.ops import clip_by_rect
from shapely.geometry import mapping

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
OUTPUT = os.path.join(OUTPUT_DIR, "itapua_districts.pmtiles")
CENSO_CSV = os.path.join(SCRIPT_DIR, "data", "itapua_censo_2022.csv")
DISTRITOS_GEOJSON = os.path.join(OUTPUT_DIR, "itapua_py_gaul_distritos.geojson")

MIN_ZOOM = 4
MAX_ZOOM = 14
LAYER_NAME = "districts"
EXTENT = 4096

# Itapua bounding box
BBOX = {"west": -57.40, "south": -27.70, "east": -55.00, "north": -26.40}


# ── Tile math ──────────────────────────────────────────────────────────────

def lng_lat_to_tile(lng, lat, zoom):
    n = 2 ** zoom
    x = int((lng + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def tile_bounds(x, y, z):
    n = 2 ** z
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return west, south, east, north


def get_tiles_for_bbox(west, south, east, north, zoom):
    x_min, y_min = lng_lat_to_tile(west, north, zoom)
    x_max, y_max = lng_lat_to_tile(east, south, zoom)
    return [(x, y) for x in range(x_min, x_max + 1) for y in range(y_min, y_max + 1)]


# ── Load data ──────────────────────────────────────────────────────────────

def load_data():
    print("Loading GAUL district polygons...")
    gdf = gpd.read_file(DISTRITOS_GEOJSON)

    print("Loading DGEEC Censo 2022...")
    censo_df = pd.read_csv(CENSO_CSV)
    censo = {
        row.distrito: {"personas": int(row.total_personas), "hogares": int(row.total_hogares)}
        for _, row in censo_df.iterrows()
    }

    features = []
    for _, row in gdf.iterrows():
        name = row["ADM2_NAME"]
        pop = censo.get(name, {"personas": 0, "hogares": 0})
        features.append({
            "geometry": row.geometry,
            "properties": {
                "district":   name,
                "adm2_code":  int(row["ADM2_CODE"]),
                "personas":   pop["personas"],
                "hogares":    pop["hogares"],
            },
        })

    print(f"  {len(features)} district polygons loaded")
    for f in features:
        matched = f["properties"]["personas"] > 0
        if not matched:
            print(f"  WARNING: no census match for '{f['properties']['district']}'")
    return features


# ── Generate PMTiles ───────────────────────────────────────────────────────

def features_to_mvt(features, bounds_wsen):
    w, s, e, n = bounds_wsen
    buf = (e - w) * 0.01
    clipped = []
    for feat in features:
        try:
            c = clip_by_rect(feat["geometry"], w - buf, s - buf, e + buf, n + buf)
        except Exception:
            continue
        if c.is_empty:
            continue
        clipped.append({"geometry": c, "properties": feat["properties"]})
    if not clipped:
        return None
    layer = {
        "name": LAYER_NAME,
        "features": [{"geometry": mapping(f["geometry"]), "properties": f["properties"]} for f in clipped],
    }
    return mvt.encode([layer], quantize_bounds=(w, s, e, n), extents=EXTENT)


def build_spatial_index(features):
    """Map (tile_x, tile_y) at MAX_ZOOM to list of feature indices.

    For polygon features we index by ALL tiles that their bounding box
    intersects at each zoom level — computed lazily in generate_pmtiles.
    Here we just return the flat feature list and let generate_pmtiles
    iterate per tile using the polygon bbox at each zoom.
    """
    return features


def generate_pmtiles(features):
    print(f"\nGenerating PMTiles (zoom {MIN_ZOOM}-{MAX_ZOOM})...")

    tile_data = {}
    total_tiles = 0

    for zoom in range(MIN_ZOOM, MAX_ZOOM + 1):
        tiles = get_tiles_for_bbox(
            BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"], zoom
        )
        for tx, ty in tiles:
            bounds = tile_bounds(tx, ty, zoom)
            w, s, e, n = bounds

            # Check which features intersect this tile
            candidate_features = []
            for feat in features:
                geom = feat["geometry"]
                gb = geom.bounds  # (minx, miny, maxx, maxy)
                if gb[0] <= e and gb[2] >= w and gb[1] <= n and gb[3] >= s:
                    candidate_features.append(feat)

            if not candidate_features:
                continue

            encoded = features_to_mvt(candidate_features, bounds)
            if encoded is None:
                continue

            compressed = gzip.compress(encoded, compresslevel=6)
            tile_id = zxy_to_tileid(zoom, tx, ty)
            tile_data[tile_id] = compressed
            total_tiles += 1

        print(f"  z{zoom}: {total_tiles} tiles written so far")

    print(f"\nWriting {OUTPUT}...")
    center_lng = (BBOX["west"] + BBOX["east"]) / 2
    center_lat = (BBOX["south"] + BBOX["north"]) / 2

    with open(OUTPUT, "wb") as f:
        writer = PMTilesWriter(f)
        for tile_id in sorted(tile_data.keys()):
            writer.write_tile(tile_id, tile_data[tile_id])
        writer.finalize(
            {
                "tile_type": TileType.MVT,
                "tile_compression": Compression.GZIP,
                "min_zoom": MIN_ZOOM,
                "max_zoom": MAX_ZOOM,
                "min_lon": BBOX["west"],
                "min_lat": BBOX["south"],
                "max_lon": BBOX["east"],
                "max_lat": BBOX["north"],
                "center_lon": center_lng,
                "center_lat": center_lat,
                "center_zoom": MIN_ZOOM,
            },
            {
                "name": "itapua_districts",
                "description": "Itapua (Paraguay) GAUL administrative districts with DGEEC 2022 census data",
                "vector_layers": [
                    {
                        "id": LAYER_NAME,
                        "fields": {
                            "district":  "String",
                            "adm2_code": "Number",
                            "personas":  "Number",
                            "hogares":   "Number",
                        },
                        "minzoom": MIN_ZOOM,
                        "maxzoom": MAX_ZOOM,
                    }
                ],
            },
        )

    size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
    print(f"Done: {OUTPUT} ({size_mb:.1f} MB, {total_tiles} tiles)")


if __name__ == "__main__":
    features = load_data()
    generate_pmtiles(features)
