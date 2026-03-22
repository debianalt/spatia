"""
Rebuild buildings PMTiles with correct est_personas and radio-level attributes.

Exports all buildings from gba_buildings + vida_buildings (PostgreSQL ndvi_misiones),
enriches each with census data, and generates a new PMTiles archive.

Also patches radio_stats_master.parquet to fix 26 radios with NULL n_buildings.

Usage:
  python pipeline/rebuild_buildings_tiles.py

Databases required:
  - ndvi_misiones (PostgreSQL): gba_buildings, vida_buildings
  - posadas (PostgreSQL): censo_2022.radios_geom

Output:
  pipeline/output/buildings-v5.pmtiles
  pipeline/output/radio_stats_master.parquet (patched)
"""

import gzip
import json
import math
import os
import sys
import time
import warnings
from collections import defaultdict

warnings.filterwarnings("ignore", category=DeprecationWarning)

import mapbox_vector_tile as mvt
import pandas as pd
import psycopg2
from pmtiles.tile import TileType, zxy_to_tileid
from pmtiles.writer import Compression, Writer as PMTilesWriter
from shapely.geometry import mapping, shape
from shapely.ops import clip_by_rect
from shapely import wkb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
PMTILES_OUTPUT = os.path.join(OUTPUT_DIR, "buildings-v5.pmtiles")
PARQUET_PATH = os.path.join(OUTPUT_DIR, "radio_stats_master.parquet")

# PMTiles config
MIN_ZOOM = 8
MAX_ZOOM = 14
LAYER_NAME = "buildings"
EXTENT = 4096
BBOX = {"west": -56.1, "south": -28.2, "east": -53.5, "north": -25.9}

PG_BUILDINGS = "dbname=ndvi_misiones user=postgres"
PG_CENSUS = "dbname=posadas user=postgres"


# ── Tile math (from geojson_to_pmtiles.py) ───────────────────────────────

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


# ── Step 1: Compute radio-level stats ────────────────────────────────────

def load_radio_stats():
    """Load census data per radio and building counts from both sources."""
    print("Step 1: Loading radio-level stats...")

    # Census data from posadas DB
    with psycopg2.connect(PG_CENSUS) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT redcode,
                       COALESCE(radios_pob, 0) as total_personas,
                       COALESCE(radios_hog, 0) as total_hogares,
                       COALESCE(radios_sup, 0) as area_km2
                FROM censo_2022.radios_geom
                WHERE redcode IS NOT NULL
            """)
            census = {row[0]: {"personas": int(row[1]), "hogares": int(row[2]), "area_km2": float(row[3])} for row in cur}
    print(f"  Census: {len(census)} radios")

    # Building counts from ndvi_misiones DB
    with psycopg2.connect(PG_BUILDINGS) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT redcode, SUM(n) as n_buildings FROM (
                    SELECT redcode, COUNT(*) as n FROM gba_buildings WHERE redcode IS NOT NULL GROUP BY redcode
                    UNION ALL
                    SELECT redcode, COUNT(*) as n FROM vida_buildings WHERE redcode IS NOT NULL GROUP BY redcode
                ) t GROUP BY redcode
            """)
            bldg_counts = {row[0]: int(row[1]) for row in cur}
    print(f"  Building counts: {len(bldg_counts)} radios")

    # Merge: radio-level attributes for tooltip (est_personas comes from DB per building)
    radio_stats = {}
    for redcode, c in census.items():
        n = bldg_counts.get(redcode, 0)
        area = c["area_km2"]
        personas = c["personas"]
        radio_stats[redcode] = {
            "radio_personas": personas,
            "radio_hogares": c["hogares"],
            "radio_viviendas": c["hogares"],  # censo 2022 doesn't distinguish at radio level
            "radio_area_km2": round(area, 3),
            "densidad_hab_km2": round(personas / area, 1) if area > 0 else 0,
            "n_buildings": n,
        }

    with_bldg = sum(1 for s in radio_stats.values() if s["n_buildings"] > 0)
    print(f"  Merged: {len(radio_stats)} radios ({with_bldg} with buildings)")
    return radio_stats


# ── Step 2: Export buildings from PostgreSQL ──────────────────────────────

def load_buildings(radio_stats):
    """Load all buildings from both tables, enriched with radio stats."""
    print("\nStep 2: Loading buildings from PostgreSQL...")
    features = []

    with psycopg2.connect(PG_BUILDINGS) as conn:
        with conn.cursor(name="gba_cursor") as cur:
            cur.itersize = 50000
            cur.execute("""
                SELECT ST_AsBinary(geom), redcode, best_height_m, area_m2,
                       COALESCE(est_personas, 0) as est_personas
                FROM gba_buildings
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
                        "est_personas": int(est_pers),
                        "best_height_m": round(float(height), 1) if height else 5.0,
                        "area_m2": round(float(area), 0) if area else 0,
                        "redcode": redcode,
                        "radio_personas": stats["radio_personas"],
                        "densidad_hab_km2": stats["densidad_hab_km2"],
                        "radio_viviendas": stats["radio_viviendas"],
                        "radio_hogares": stats["radio_hogares"],
                        "radio_area_km2": stats["radio_area_km2"],
                    },
                })
                count += 1
                if count % 500000 == 0:
                    print(f"    GBA: {count:,} buildings loaded...")
            print(f"  GBA: {count:,} buildings total")

        with conn.cursor(name="vida_cursor") as cur:
            cur.itersize = 50000
            cur.execute("""
                SELECT ST_AsBinary(ST_GeometryN(geom, 1)), redcode, best_height_m, area_in_meters,
                       COALESCE(est_personas, 0) as est_personas
                FROM vida_buildings
                WHERE redcode IS NOT NULL AND geom IS NOT NULL
            """)
            count_vida = 0
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
                        "est_personas": int(est_pers),
                        "best_height_m": round(float(height), 1) if height else 5.0,
                        "area_m2": round(float(area), 0) if area else 0,
                        "redcode": redcode,
                        "radio_personas": stats["radio_personas"],
                        "densidad_hab_km2": stats["densidad_hab_km2"],
                        "radio_viviendas": stats["radio_viviendas"],
                        "radio_hogares": stats["radio_hogares"],
                        "radio_area_km2": stats["radio_area_km2"],
                    },
                })
                count_vida += 1
            print(f"  VIDA: {count_vida:,} buildings total")

    print(f"  Total: {len(features):,} buildings loaded")
    return features


# ── Step 3: Generate PMTiles ─────────────────────────────────────────────

def generate_pmtiles(features):
    """Build spatial index and generate PMTiles archive."""
    print(f"\nStep 3: Generating PMTiles (zoom {MIN_ZOOM}-{MAX_ZOOM})...")
    t0 = time.time()

    # Spatial index at MAX_ZOOM
    print("  Building spatial index...")
    grid = defaultdict(list)
    for i, feat in enumerate(features):
        c = feat["geometry"].centroid
        tx, ty = lng_lat_to_tile(c.x, c.y, MAX_ZOOM)
        grid[(tx, ty)].append(i)
    print(f"  Index: {len(grid):,} grid cells")

    # Generate tiles
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
    print(f"\n  Writing {PMTILES_OUTPUT} ({total_tiles} tiles)...")
    with open(PMTILES_OUTPUT, "wb") as f:
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
            "center_zoom": 12,
        }
        metadata = {
            "name": "buildings",
            "description": "Building footprints for Misiones (GBA + VIDA) with census attributes",
            "vector_layers": [{
                "id": LAYER_NAME,
                "fields": {
                    "est_personas": "Number",
                    "best_height_m": "Number",
                    "area_m2": "Number",
                    "redcode": "String",
                    "radio_personas": "Number",
                    "densidad_hab_km2": "Number",
                    "radio_viviendas": "Number",
                    "radio_hogares": "Number",
                    "radio_area_km2": "Number",
                },
                "minzoom": MIN_ZOOM,
                "maxzoom": MAX_ZOOM,
            }],
        }
        writer.finalize(header, metadata)

    size_mb = os.path.getsize(PMTILES_OUTPUT) / (1024 * 1024)
    elapsed = time.time() - t0
    print(f"  -> {PMTILES_OUTPUT} ({size_mb:.1f} MB, {elapsed:.0f}s total)")


# ── Step 4: Patch radio_stats_master.parquet ─────────────────────────────

def patch_parquet(radio_stats):
    """Fix n_buildings for radios that had NULL."""
    print(f"\nStep 4: Patching {PARQUET_PATH}...")
    import duckdb

    con = duckdb.connect()
    df = con.execute(f"SELECT * FROM '{PARQUET_PATH}'").fetchdf()

    patched = 0
    for idx, row in df.iterrows():
        rc = row["redcode"]
        stats = radio_stats.get(rc)
        if stats and pd.isna(row.get("n_buildings")):
            df.at[idx, "n_buildings"] = float(stats["n_buildings"])
            patched += 1

    print(f"  Patched {patched} radios with NULL n_buildings")

    backup = PARQUET_PATH.replace(".parquet", "_backup.parquet")
    if os.path.exists(backup):
        os.remove(backup)
    os.rename(PARQUET_PATH, backup)
    df.to_parquet(PARQUET_PATH, index=False)
    print(f"  Backup: {backup}")
    print(f"  Written: {PARQUET_PATH}")

    # Verify
    result = con.execute(f"""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN n_buildings IS NULL THEN 1 ELSE 0 END) as null_bldg
        FROM '{PARQUET_PATH}'
    """).fetchone()
    print(f"  Verify: {result[0]} radios, {result[1]} with NULL n_buildings")


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    t_start = time.time()
    print("=" * 60)
    print("REBUILD BUILDINGS PMTILES")
    print("=" * 60)

    radio_stats = load_radio_stats()
    features = load_buildings(radio_stats)
    generate_pmtiles(features)
    patch_parquet(radio_stats)

    elapsed = time.time() - t_start
    print(f"\nDone in {elapsed:.0f}s")


if __name__ == "__main__":
    main()
