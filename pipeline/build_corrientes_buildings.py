"""
Build Corrientes buildings PMTiles from gba_buildings_corrientes (PostGIS).

Mirrors rebuild_buildings_tiles.py but targets the Corrientes-specific table
and bbox. Uses a separate output file (corrientes_buildings.pmtiles) consistent
with the itapua_buildings.pmtiles pattern — no changes to Misiones buildings.

Pre-requisite:
  python pipeline/import_gba_corrientes.py

Usage:
  python pipeline/build_corrientes_buildings.py

Output:
  pipeline/output/corrientes_buildings.pmtiles

R2 upload (after confirming output looks correct):
  npx wrangler r2 object put neahub/data/tiles/corrientes_buildings.pmtiles \\
    --file pipeline/output/corrientes_buildings.pmtiles --remote
"""

import gzip
import math
import os
import time
import warnings
from collections import defaultdict

warnings.filterwarnings("ignore", category=DeprecationWarning)

import mapbox_vector_tile as mvt
import pandas as pd
import psycopg2
from pmtiles.tile import TileType, zxy_to_tileid
from pmtiles.writer import Compression, Writer as PMTilesWriter
from shapely.geometry import mapping
from shapely.ops import clip_by_rect
from shapely import wkb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
PMTILES_OUTPUT = os.path.join(OUTPUT_DIR, "corrientes_buildings.pmtiles")

MIN_ZOOM = 8
MAX_ZOOM = 14
LAYER_NAME = "buildings"   # must match 'source-layer' in Map.svelte
EXTENT = 4096

# Corrientes province bbox (same convention as radios-v3.pmtiles)
BBOX = {"west": -59.8, "south": -30.8, "east": -56.0, "north": -27.3}

PG_BUILDINGS = "dbname=ndvi_misiones user=postgres"
PG_CENSUS = "dbname=posadas user=postgres"


# ── Tile math (identical to rebuild_buildings_tiles.py) ──────────────────────

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


# ── Step 1: Radio-level stats ────────────────────────────────────────────────

def load_radio_stats() -> dict:
    """Load per-radio census attributes for tooltip enrichment."""
    print("Step 1: Loading radio stats for Corrientes...")
    with psycopg2.connect(PG_CENSUS) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT redcode,
                       COALESCE(radios_pob, 0) AS total_personas,
                       COALESCE(radios_hog, 0) AS total_hogares,
                       COALESCE(radios_sup, 0) AS area_km2
                FROM censo_2022.radios_geom
                WHERE codprov = '18' AND redcode IS NOT NULL
            """)
            census = {
                row[0]: {
                    "personas": int(row[1]),
                    "hogares":  int(row[2]),
                    "area_km2": float(row[3]),
                }
                for row in cur
            }
    print(f"  Census: {len(census):,} radios")

    # Building counts per radio
    with psycopg2.connect(PG_BUILDINGS) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT redcode, COUNT(*) AS n
                FROM gba_buildings_corrientes
                WHERE redcode IS NOT NULL
                GROUP BY redcode
            """)
            bldg_counts = {row[0]: int(row[1]) for row in cur}
    print(f"  Building counts: {len(bldg_counts):,} radios with buildings")

    radio_stats = {}
    for redcode, c in census.items():
        n = bldg_counts.get(redcode, 0)
        area = c["area_km2"]
        personas = c["personas"]
        radio_stats[redcode] = {
            "radio_personas":  personas,
            "radio_hogares":   c["hogares"],
            "radio_viviendas": c["hogares"],
            "radio_area_km2":  round(area, 3),
            "densidad_hab_km2": round(personas / area, 1) if area > 0 else 0,
            "n_buildings": n,
        }

    with_bldg = sum(1 for s in radio_stats.values() if s["n_buildings"] > 0)
    print(f"  Merged: {len(radio_stats):,} radios ({with_bldg} with buildings)")
    return radio_stats


# ── Step 2: Load buildings ───────────────────────────────────────────────────

def load_buildings(radio_stats: dict) -> list:
    """Export gba_buildings_corrientes enriched with radio census attributes."""
    print("\nStep 2: Loading buildings from PostGIS...")
    features = []

    with psycopg2.connect(PG_BUILDINGS) as conn:
        with conn.cursor(name="corrientes_cursor") as cur:
            cur.itersize = 50000
            cur.execute("""
                SELECT ST_AsBinary(geom), redcode, best_height_m, area_m2,
                       COALESCE(est_personas, 0) AS est_personas
                FROM gba_buildings_corrientes
                WHERE redcode IS NOT NULL AND geom IS NOT NULL
            """)
            count = 0
            for row in cur:
                geom_wkb, redcode, height, area, est_pers = row
                stats = radio_stats.get(redcode)
                if not stats:
                    continue
                try:
                    geom = wkb.loads(bytes(geom_wkb))
                except Exception:
                    continue
                features.append({
                    "geometry": geom,
                    "properties": {
                        "est_personas":    int(est_pers),
                        "best_height_m":   round(float(height), 1) if height else 5.0,
                        "area_m2":         round(float(area), 0) if area else 0,
                        "redcode":         redcode,
                        "radio_personas":  stats["radio_personas"],
                        "densidad_hab_km2": stats["densidad_hab_km2"],
                        "radio_viviendas": stats["radio_viviendas"],
                        "radio_hogares":   stats["radio_hogares"],
                        "radio_area_km2":  stats["radio_area_km2"],
                    },
                })
                count += 1
                if count % 500_000 == 0:
                    print(f"    {count:,} buildings loaded...")

    print(f"  Total: {len(features):,} buildings loaded")
    return features


# ── Step 3: Generate PMTiles ─────────────────────────────────────────────────

def generate_pmtiles(features: list):
    """Build spatial index and write PMTiles archive."""
    print(f"\nStep 3: Generating PMTiles (zoom {MIN_ZOOM}-{MAX_ZOOM})...")
    t0 = time.time()

    print("  Building spatial index...")
    grid: dict = defaultdict(list)
    for i, feat in enumerate(features):
        c = feat["geometry"].centroid
        tx, ty = lng_lat_to_tile(c.x, c.y, MAX_ZOOM)
        grid[(tx, ty)].append(i)
    print(f"  Index: {len(grid):,} grid cells")

    tile_data: dict = {}
    total_tiles = 0

    for z in range(MIN_ZOOM, MAX_ZOOM + 1):
        tiles = get_tiles_for_bbox(BBOX, z)
        written = 0
        t_z = time.time()

        for x, y in tiles:
            bounds = tile_bounds(x, y, z)
            scale = 2 ** (MAX_ZOOM - z)
            x_min, x_max = x * scale, (x + 1) * scale - 1
            y_min, y_max = y * scale, (y + 1) * scale - 1

            candidate_indices: set = set()
            for gx in range(x_min, x_max + 1):
                for gy in range(y_min, y_max + 1):
                    candidate_indices.update(grid.get((gx, gy), []))

            if not candidate_indices:
                continue

            tile_bytes = features_to_mvt(
                [features[i] for i in candidate_indices], bounds, LAYER_NAME, EXTENT
            )
            if tile_bytes:
                tile_data[zxy_to_tileid(z, x, y)] = gzip.compress(tile_bytes)
                written += 1

        total_tiles += written
        print(f"  z{z}: {written} tiles ({time.time()-t_z:.1f}s)")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\n  Writing {PMTILES_OUTPUT} ({total_tiles} tiles)...")
    with open(PMTILES_OUTPUT, "wb") as f:
        writer = PMTilesWriter(f)
        for tile_id in sorted(tile_data.keys()):
            writer.write_tile(tile_id, tile_data[tile_id])
        writer.finalize(
            {
                "tile_type":        TileType.MVT,
                "tile_compression": Compression.GZIP,
                "min_zoom":  MIN_ZOOM,
                "max_zoom":  MAX_ZOOM,
                "min_lon":   BBOX["west"],
                "min_lat":   BBOX["south"],
                "max_lon":   BBOX["east"],
                "max_lat":   BBOX["north"],
                "center_lon": (BBOX["west"] + BBOX["east"]) / 2,
                "center_lat": (BBOX["south"] + BBOX["north"]) / 2,
                "center_zoom": 12,
            },
            {
                "name": "corrientes_buildings",
                "description": "Building footprints for Corrientes (GBA) with census attributes",
                "vector_layers": [{
                    "id": LAYER_NAME,
                    "fields": {
                        "est_personas":    "Number",
                        "best_height_m":   "Number",
                        "area_m2":         "Number",
                        "redcode":         "String",
                        "radio_personas":  "Number",
                        "densidad_hab_km2": "Number",
                        "radio_viviendas": "Number",
                        "radio_hogares":   "Number",
                        "radio_area_km2":  "Number",
                    },
                    "minzoom": MIN_ZOOM,
                    "maxzoom": MAX_ZOOM,
                }],
            },
        )

    size_mb = os.path.getsize(PMTILES_OUTPUT) / (1024 * 1024)
    elapsed = time.time() - t0
    print(f"  -> {PMTILES_OUTPUT} ({size_mb:.1f} MB, {elapsed:.0f}s total)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    t_start = time.time()
    print("=" * 60)
    print("BUILD CORRIENTES BUILDINGS PMTILES")
    print("=" * 60)

    radio_stats = load_radio_stats()
    features = load_buildings(radio_stats)
    generate_pmtiles(features)

    print(f"\nDone in {time.time()-t_start:.0f}s")
    print("\nNext steps:")
    print("  1. Inspect output: pmtiles.io (local file viewer)")
    print("  2. Upload:")
    print(f"     npx wrangler r2 object put neahub/data/tiles/corrientes_buildings.pmtiles \\")
    print(f"       --file {PMTILES_OUTPUT} --remote")
    print("  3. python pipeline/build_crosswalk_corrientes.py")


if __name__ == "__main__":
    main()
