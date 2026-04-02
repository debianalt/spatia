"""
Rebuild catastro PMTiles with h3index property for data-driven coloring.

Reads catastro parcels from parquet state files, assigns each parcel its
H3 res-9 index (via centroid), and generates a PMTiles archive.

Usage:
  python pipeline/rebuild_catastro_tiles.py

Input:
  pipeline/output/catastro_state/catastro_urbano.parquet
  pipeline/output/catastro_state/catastro_rural.parquet

Output:
  pipeline/output/catastro.pmtiles
"""

import gzip
import math
import os
import time
from collections import defaultdict

from datetime import date, timedelta

import h3
import mapbox_vector_tile as mvt
import pandas as pd
from pmtiles.tile import TileType, zxy_to_tileid
from pmtiles.writer import Compression, Writer as PMTilesWriter
from shapely import wkb
from shapely.geometry import mapping
from shapely.ops import clip_by_rect

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
STATE_DIR = os.path.join(OUTPUT_DIR, "catastro_state")
PMTILES_OUTPUT = os.path.join(OUTPUT_DIR, "catastro.pmtiles")

# PMTiles config — same bbox as buildings (padded Misiones)
MIN_ZOOM = 9
MAX_ZOOM = 14
LAYER_NAME = "catastro"
EXTENT = 4096
BBOX = {"west": -56.1, "south": -28.2, "east": -53.55, "north": -25.44}
H3_RES = 9


# ── Tile math ───────────────────────────────────────────────────────────

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
    buf = (e - w) * 0.10
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


# ── Step 1: Load parcels ────────────────────────────────────────────────

def load_parcels():
    """Load urban + rural parcels from parquet, assign h3index + departamento."""
    print("Step 1: Loading parcels...")

    # Build h3 -> departamento mapping from crosswalk
    xw_path = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk_areal.parquet")
    h3_dept = {}
    if os.path.exists(xw_path):
        xw = pd.read_parquet(xw_path)
        xw["dept"] = xw["redcode"].str[:5]
        best = xw.sort_values("weight", ascending=False).drop_duplicates("h3index")
        h3_dept = dict(zip(best["h3index"], best["dept"]))
        print(f"  H3->dept mapping: {len(h3_dept):,} entries")

    features = []
    skipped = 0
    cutoff_90d = pd.Timestamp(date.today() - timedelta(days=90))

    for tipo, filename in [("urbano", "catastro_urbano.parquet"), ("rural", "catastro_rural.parquet")]:
        path = os.path.join(STATE_DIR, filename)
        if not os.path.exists(path):
            print(f"  WARNING: {path} not found, skipping")
            continue

        df = pd.read_parquet(path)

        # Detect initial snapshot: if all first_seen are the same date,
        # this is the initial load — no parcels are truly "new"
        has_first_seen = "first_seen" in df.columns and df["first_seen"].notna().any()
        is_initial_snapshot = False
        if has_first_seen:
            unique_dates = df["first_seen"].dropna().nunique()
            is_initial_snapshot = unique_dates <= 1
            if is_initial_snapshot:
                print(f"  {tipo}: single snapshot date detected — no parcels marked as new")

        count = 0
        n_new = 0
        for _, row in df.iterrows():
            try:
                geom = wkb.loads(row["geometry"])
            except Exception:
                skipped += 1
                continue

            if geom.is_empty:
                skipped += 1
                continue

            # Compute H3 index from centroid
            centroid = geom.centroid
            h3index = h3.latlng_to_cell(centroid.y, centroid.x, H3_RES)

            # Check if parcel is new (first_seen within 90 days)
            # Skip if initial snapshot (all same date = first load, not incremental)
            is_new = 0
            if not is_initial_snapshot:
                fs = row.get("first_seen")
                if fs is not None and pd.notna(fs):
                    if pd.Timestamp(fs) >= cutoff_90d:
                        is_new = 1
                        n_new += 1

            props = {
                "tipo": tipo,
                "h3index": h3index,
                "area_m2": round(float(row.get("area_m2", 0)), 0),
                "is_new": is_new,
            }
            # Assign departamento from h3->crosswalk mapping
            dept = h3_dept.get(h3index)
            if dept:
                props["departamento"] = dept

            features.append({"geometry": geom, "properties": props})
            count += 1

        print(f"  {tipo}: {count:,} parcels loaded ({n_new:,} new)")

    print(f"  Total: {len(features):,} parcels ({skipped} skipped)")
    return features


# ── Step 2: Generate PMTiles ────────────────────────────────────────────

def generate_pmtiles(features):
    """Build spatial index and generate PMTiles archive."""
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
            "name": "catastro",
            "description": "Catastro parcels for Misiones with H3 index",
            "vector_layers": [{
                "id": LAYER_NAME,
                "fields": {
                    "tipo": "String",
                    "h3index": "String",
                    "area_m2": "Number",
                    "departamento": "String",
                    "is_new": "Number",
                },
                "minzoom": MIN_ZOOM,
                "maxzoom": MAX_ZOOM,
            }],
        }
        writer.finalize(header, metadata)

    size_mb = os.path.getsize(PMTILES_OUTPUT) / (1024 * 1024)
    elapsed = time.time() - t0
    print(f"  -> {PMTILES_OUTPUT} ({size_mb:.1f} MB, {elapsed:.0f}s total)")


# ── Main ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("REBUILD CATASTRO PMTILES (with h3index)")
    print("=" * 60)

    features = load_parcels()
    if not features:
        print("No parcels loaded, aborting.")
        exit(1)

    generate_pmtiles(features)
    print("\nDone!")
