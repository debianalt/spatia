"""
Build Itapúa (Paraguay) buildings PMTiles from Overture Maps.

Uses the overturemaps Python library to stream building footprints within Itapúa's
bounding box, then generates a PMTiles archive using the same tile encoding pipeline
as rebuild_buildings_tiles.py.

No census enrichment (no PY census data available) — properties: best_height_m, area_m2.
Layer name 'buildings' matches the source-layer used by Map.svelte's itapua-buildings-3d.

Usage:
  python pipeline/build_itapua_buildings.py

Output:
  pipeline/output/itapua_buildings.pmtiles

R2 upload (run after confirming output looks correct):
  npx wrangler r2 object put neahub/data/tiles/itapua_buildings.pmtiles \\
    --file pipeline/output/itapua_buildings.pmtiles --remote
"""

import gzip
import math
import os
import time
import warnings
from collections import defaultdict

warnings.filterwarnings("ignore", category=DeprecationWarning)

import overturemaps
import mapbox_vector_tile as mvt
from pmtiles.tile import TileType, zxy_to_tileid
from pmtiles.writer import Compression, Writer as PMTilesWriter
from pyproj import Transformer
from shapely.geometry import mapping
from shapely.ops import clip_by_rect
from shapely.ops import transform as shapely_transform
from shapely import wkb as shapely_wkb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
OUTPUT = os.path.join(OUTPUT_DIR, "itapua_buildings.pmtiles")

# Itapúa, Paraguay — slightly padded to capture border buildings
BBOX = {"west": -57.40, "south": -27.70, "east": -55.00, "north": -26.40}

MIN_ZOOM = 8
MAX_ZOOM = 14
LAYER_NAME = "buildings"   # must match 'source-layer' in Map.svelte
EXTENT = 4096

# UTM zone 20S (EPSG:32720) — correct projection for Paraguay area calculations
_proj = Transformer.from_crs("EPSG:4326", "EPSG:32720", always_xy=True)


def area_m2(geom):
    """Compute polygon area in m² using UTM 20S projection."""
    try:
        return round(shapely_transform(_proj.transform, geom).area, 0)
    except Exception:
        return 0.0


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


# ── Step 1: Fetch buildings from Overture Maps ───────────────────────────────

def load_buildings():
    print("Step 1: Querying Overture Maps API...")
    west, south, east, north = BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"]
    print(f"  bbox: {west},{south} to {east},{north}")

    t0 = time.time()
    reader = overturemaps.record_batch_reader(
        'building',
        bbox=(west, south, east, north),
    )
    if reader is None:
        print("  ERROR: record_batch_reader returned None")
        return []

    features = []
    skipped = 0
    total_rows = 0

    for batch in reader:
        rows = batch.to_pydict()
        n = len(rows['geometry'])
        total_rows += n
        for i in range(n):
            geom_bytes = rows['geometry'][i]
            height = rows['height'][i]
            if geom_bytes is None:
                skipped += 1
                continue
            try:
                geom = shapely_wkb.loads(bytes(geom_bytes))
            except Exception:
                skipped += 1
                continue
            if geom is None or geom.is_empty:
                skipped += 1
                continue
            features.append({
                "geometry": geom,
                "properties": {
                    "best_height_m": round(float(height), 1) if height is not None else 5.0,
                    "area_m2": area_m2(geom),
                },
            })

    print(f"  {total_rows:,} rows in {time.time()-t0:.1f}s -> {len(features):,} valid ({skipped} skipped)")
    return features


# ── Step 2: Generate PMTiles ─────────────────────────────────────────────────

def generate_pmtiles(features):
    print(f"\nStep 2: Generating PMTiles (zoom {MIN_ZOOM}-{MAX_ZOOM})...")
    t0 = time.time()

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
            x_min, x_max = x * scale, (x + 1) * scale - 1
            y_min, y_max = y * scale, (y + 1) * scale - 1

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

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\n  Writing {OUTPUT} ({total_tiles} tiles)...")
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
                "center_lon": (BBOX["west"] + BBOX["east"]) / 2,
                "center_lat": (BBOX["south"] + BBOX["north"]) / 2,
                "center_zoom": 12,
            },
            {
                "name": "itapua_buildings",
                "description": "Building footprints for Itapúa, Paraguay (Overture Maps 2024-11)",
                "vector_layers": [{
                    "id": LAYER_NAME,
                    "fields": {"best_height_m": "Number", "area_m2": "Number"},
                    "minzoom": MIN_ZOOM,
                    "maxzoom": MAX_ZOOM,
                }],
            },
        )

    size_mb = os.path.getsize(OUTPUT) / (1024 * 1024)
    print(f"  -> {OUTPUT} ({size_mb:.1f} MB, {time.time()-t0:.0f}s total)")
    print()
    print("Next step:")
    print(f"  npx wrangler r2 object put neahub/data/tiles/itapua_buildings.pmtiles \\")
    print(f"    --file {OUTPUT} --remote")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    t_start = time.time()
    print("=" * 60)
    print("BUILD ITAPÚA BUILDINGS PMTILES (Overture Maps)")
    print("=" * 60)

    features = load_buildings()
    if not features:
        print("ERROR: no features loaded — check DuckDB httpfs / S3 access")
        return

    generate_pmtiles(features)
    print(f"\nDone in {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    main()
