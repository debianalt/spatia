"""
Build radios-v3.pmtiles covering Misiones (codprov=54) + Corrientes (codprov=18).

Reads all radio polygons from posadas.censo_2022.radios_geom, simplifies geometry,
and generates a PMTiles archive. Each feature carries redcode + codprov properties
so MapLibre can filter by territory.

Usage:
  python pipeline/rebuild_radios_tiles.py

Output:
  pipeline/output/radios-v3.pmtiles

R2 upload (run after confirming output):
  npx wrangler r2 object put neahub/data/tiles/radios-v3.pmtiles \\
    --file pipeline/output/radios-v3.pmtiles --remote
"""

import gzip
import math
import os
import time
import warnings
from collections import defaultdict

warnings.filterwarnings("ignore", category=DeprecationWarning)

import mapbox_vector_tile as mvt
import psycopg2
from pmtiles.tile import TileType, zxy_to_tileid
from pmtiles.writer import Compression, Writer as PMTilesWriter
from shapely.geometry import mapping
from shapely.ops import clip_by_rect
from shapely import wkb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "radios-v3.pmtiles")

PG_CENSUS = "dbname=posadas user=postgres"

MIN_ZOOM = 5
MAX_ZOOM = 12
LAYER_NAME = "radios"
EXTENT = 4096
SIMPLIFY_TOLERANCE = 0.0005  # degrees — ~50m at equator, keeps polygons clean at zoom 12

# Extended bbox covering both Misiones + Corrientes
BBOX = {"west": -59.8, "south": -30.8, "east": -53.5, "north": -25.4}

PROVINCES = ('54', '18')  # Misiones, Corrientes


# ── Tile math (same as rebuild_buildings_tiles.py) ───────────────────────

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


def get_tiles_for_bbox(bbox, zoom):
    x_min, y_min = lng_lat_to_tile(bbox["west"], bbox["north"], zoom)
    x_max, y_max = lng_lat_to_tile(bbox["east"], bbox["south"], zoom)
    return [(x, y) for x in range(x_min, x_max + 1) for y in range(y_min, y_max + 1)]


def features_to_mvt(features, tile_bounds_wsen, layer_name, extent=4096):
    w, s, e, n = tile_bounds_wsen
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
        "name": layer_name,
        "features": [{"geometry": mapping(f["geometry"]), "properties": f["properties"]} for f in clipped],
    }
    return mvt.encode([layer], quantize_bounds=(w, s, e, n), extents=extent)


# ── Step 1: Load radios from PostGIS ────────────────────────────────────

def load_features():
    print("Step 1: Loading radios from PostGIS...")
    conn = psycopg2.connect(PG_CENSUS)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT redcode, codprov, ST_AsBinary(geom)
            FROM censo_2022.radios_geom
            WHERE codprov = ANY(%s)
              AND geom IS NOT NULL
              AND redcode IS NOT NULL
        """, (list(PROVINCES),))
        rows = cur.fetchall()
    conn.close()

    print(f"  {len(rows)} radios fetched")

    features = []
    skipped = 0
    for redcode, codprov, geom_wkb in rows:
        try:
            geom = wkb.loads(bytes(geom_wkb))
        except Exception:
            skipped += 1
            continue
        if geom is None or geom.is_empty:
            skipped += 1
            continue
        # Simplify polygon for tile rendering efficiency
        simplified = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        if simplified.is_empty:
            simplified = geom  # fallback to original if simplification collapses geometry
        features.append({
            "geometry": simplified,
            "properties": {
                "redcode": redcode,
                "codprov": codprov,
            },
        })

    print(f"  {len(features)} features loaded ({skipped} skipped)")
    mis = sum(1 for f in features if f["properties"]["codprov"] == "54")
    cor = sum(1 for f in features if f["properties"]["codprov"] == "18")
    print(f"  Misiones: {mis}, Corrientes: {cor}")
    return features


# ── Step 2: Generate PMTiles ─────────────────────────────────────────────

def generate_pmtiles(features):
    print(f"\nStep 2: Generating PMTiles (zoom {MIN_ZOOM}-{MAX_ZOOM})...")
    t0 = time.time()

    # Spatial index at MAX_ZOOM
    print("  Building spatial index...")
    grid = defaultdict(list)
    for i, feat in enumerate(features):
        c = feat["geometry"].centroid
        tx, ty = lng_lat_to_tile(c.x, c.y, MAX_ZOOM)
        grid[(tx, ty)].append(i)
    print(f"  Index: {len(grid):,} grid cells")

    tile_data = {}
    total_tiles = 0

    for z in range(MIN_ZOOM, MAX_ZOOM + 1):
        tiles = get_tiles_for_bbox(BBOX, z)
        written = 0
        t_z = time.time()

        for x, y in tiles:
            bounds = tile_bounds(x, y, z)

            scale = 2 ** (MAX_ZOOM - z)
            x_min = x * scale
            x_max = (x + 1) * scale - 1
            y_min = y * scale
            y_max = (y + 1) * scale - 1

            candidate_indices = set()
            for gx in range(x_min, x_max + 1):
                for gy in range(y_min, y_max + 1):
                    candidate_indices.update(grid.get((gx, gy), []))

            if not candidate_indices:
                continue

            tile_bytes = features_to_mvt(
                [features[i] for i in candidate_indices], bounds, LAYER_NAME, EXTENT
            )
            if tile_bytes:
                compressed = gzip.compress(tile_bytes)
                tile_data[zxy_to_tileid(z, x, y)] = compressed
                written += 1

        total_tiles += written
        print(f"  z{z}: {written} tiles ({time.time()-t_z:.1f}s)")

    print(f"\n  Writing {OUTPUT_PATH} ({total_tiles} tiles)...")
    with open(OUTPUT_PATH, "wb") as f:
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
            "name": "radios",
            "description": "Census radios for Misiones (AR) + Corrientes (AR) — INDEC Censo 2022",
            "vector_layers": [{
                "id": LAYER_NAME,
                "fields": {"redcode": "String", "codprov": "String"},
                "minzoom": MIN_ZOOM,
                "maxzoom": MAX_ZOOM,
            }],
        }
        writer.finalize(header, metadata)

    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    elapsed = time.time() - t0
    print(f"  -> {OUTPUT_PATH} ({size_mb:.1f} MB, {elapsed:.0f}s total)")
    print()
    print("Next step:")
    print(f"  npx wrangler r2 object put neahub/data/tiles/radios-v3.pmtiles \\")
    print(f"    --file {OUTPUT_PATH} --remote")


def main():
    t_start = time.time()
    print("=" * 60)
    print("REBUILD RADIOS PMTILES v3 (Misiones + Corrientes)")
    print("=" * 60)

    features = load_features()
    generate_pmtiles(features)
    print(f"\nDone in {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    main()
