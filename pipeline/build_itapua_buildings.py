"""
Build Itapúa (Paraguay) buildings PMTiles from Overture Maps with census enrichment.

Pipeline:
  1. Fetch building footprints from Overture Maps API
  2. Classify residential vs non-residential (Overture subtype/class + area heuristic)
  3. Spatial join buildings → distritos (from itapua_py_gaul_distritos.geojson)
  4. Area-proportional population distribution using DGEEC Censo 2022 district totals
  5. Generate PMTiles with enriched properties

Properties per building in output tiles:
  best_height_m, area_m2, is_residential (0/1), subtype, est_personas,
  distrito, distrito_pop, distrito_hog

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

import geopandas as gpd
import overturemaps
import mapbox_vector_tile as mvt
import pandas as pd
from pmtiles.tile import TileType, zxy_to_tileid
from pmtiles.writer import Compression, Writer as PMTilesWriter
from pyproj import Transformer
from shapely.geometry import mapping
from shapely.ops import clip_by_rect
from shapely.ops import transform as shapely_transform
from shapely.strtree import STRtree
from shapely import wkb as shapely_wkb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
OUTPUT = os.path.join(OUTPUT_DIR, "itapua_buildings.pmtiles")
CENSO_CSV = os.path.join(SCRIPT_DIR, "data", "itapua_censo_2022.csv")
DISTRITOS_GEOJSON = os.path.join(OUTPUT_DIR, "itapua_py_gaul_distritos.geojson")

# Itapúa, Paraguay — slightly padded to capture border buildings
BBOX = {"west": -57.40, "south": -27.70, "east": -55.00, "north": -26.40}

MIN_ZOOM = 8
MAX_ZOOM = 14
LAYER_NAME = "buildings"   # must match 'source-layer' in Map.svelte
EXTENT = 4096

# UTM zone 20S (EPSG:32720) — correct projection for Paraguay area calculations
_proj = Transformer.from_crs("EPSG:4326", "EPSG:32720", always_xy=True)

# Residential classification sets
_RES_CLASSES = {
    'house', 'apartments', 'detached', 'dormitory', 'bungalow', 'cabin',
    'terrace', 'residential', 'semidetached_house', 'static_caravan',
}
_NON_RES_SUBTYPES = {
    'commercial', 'industrial', 'civic', 'education', 'medical', 'religious',
    'entertainment', 'military', 'agricultural', 'transportation', 'service', 'outbuilding',
}
_NON_RES_CLASSES = {
    'commercial', 'industrial', 'retail', 'warehouse', 'office', 'school',
    'university', 'hospital', 'church', 'mosque', 'hotel', 'garage', 'farm',
    'barn', 'factory', 'greenhouse', 'hangar', 'civic', 'education', 'medical',
    'religious', 'service', 'outbuilding',
}


def area_m2(geom):
    """Compute polygon area in m² using UTM 20S projection."""
    try:
        return round(shapely_transform(_proj.transform, geom).area, 0)
    except Exception:
        return 0.0


def classify_residential(subtype, bclass, a):
    """Return (is_residential bool, label str).

    Priority: explicit Overture subtype/class → area heuristic (>700m²) → default residential.
    """
    label = bclass or subtype or ""

    if subtype == 'residential' or bclass in _RES_CLASSES:
        return True, label
    if subtype in _NON_RES_SUBTYPES or bclass in _NON_RES_CLASSES:
        return False, label
    # Large unclassified building — likely non-residential
    if a > 700:
        return False, label
    return True, label


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


# ── Step 0: Load census data + distrito polygons ──────────────────────────

def load_censo():
    """Return dict: distrito_name → {personas, hogares}."""
    df = pd.read_csv(CENSO_CSV)
    return {
        row.distrito: {"personas": int(row.total_personas), "hogares": int(row.total_hogares)}
        for _, row in df.iterrows()
    }


def load_distritos():
    """Return (gdf with ADM2_NAME, list of Shapely geometries, list of names)."""
    gdf = gpd.read_file(DISTRITOS_GEOJSON)
    return gdf, list(gdf.geometry), list(gdf["ADM2_NAME"])


# ── Step 1: Fetch + classify buildings from Overture ─────────────────────

def load_buildings():
    """Fetch from Overture Maps and classify each building."""
    print("Step 1: Querying Overture Maps API...")
    west, south, east, north = BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"]
    print(f"  bbox: {west},{south} to {east},{north}")

    t0 = time.time()
    reader = overturemaps.record_batch_reader("building", bbox=(west, south, east, north))
    if reader is None:
        print("  ERROR: record_batch_reader returned None")
        return []

    features = []
    skipped = 0
    total_rows = 0
    n_residential = 0

    for batch in reader:
        rows = batch.to_pydict()
        n = len(rows["geometry"])
        total_rows += n

        subtype_col = rows.get("subtype", [None] * n)
        class_col   = rows.get("class",   [None] * n)

        for i in range(n):
            geom_bytes = rows["geometry"][i]
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

            height   = rows["height"][i]
            subtype  = subtype_col[i]
            bclass   = class_col[i]
            a        = area_m2(geom)
            is_res, label = classify_residential(subtype, bclass, a)

            if is_res:
                n_residential += 1

            features.append({
                "geometry":      geom,
                "best_height_m": round(float(height), 1) if height is not None else 5.0,
                "area_m2":       a,
                "is_residential": is_res,
                "subtype":       label,
                # filled in later
                "distrito":      "",
                "est_personas":  0,
                "distrito_pop":  0,
                "distrito_hog":  0,
            })

    print(f"  {total_rows:,} rows -> {len(features):,} valid ({skipped} skipped)")
    print(f"  Residential: {n_residential:,} ({100*n_residential/max(1,len(features)):.1f}%)")
    print(f"  Time: {time.time()-t0:.1f}s")
    return features


# ── Step 2: Spatial join buildings → distritos ────────────────────────────

def assign_districts(features, dist_geoms, dist_names):
    """Bulk point-in-polygon using STRtree: assign distrito to each building."""
    print("\nStep 2: Spatial join buildings -> distritos...")
    t0 = time.time()

    tree = STRtree(dist_geoms)
    centroids = [feat["geometry"].centroid for feat in features]

    # Returns (input_indices, tree_indices) for all within relationships
    result = tree.query(centroids, predicate="within")

    assigned = 0
    if len(result[0]) > 0:
        for ci, di in zip(result[0], result[1]):
            features[ci]["distrito"] = dist_names[di]
            assigned += 1

    print(f"  Assigned: {assigned:,} / {len(features):,} buildings  ({time.time()-t0:.1f}s)")


# ── Step 3: Area-proportional population distribution ─────────────────────

def distribute_population(features, censo):
    """For each distrito, distribute population to residential buildings by area."""
    print("\nStep 3: Distributing population...")
    t0 = time.time()

    dist_res_area = defaultdict(float)
    for feat in features:
        if feat["is_residential"] and feat["distrito"]:
            dist_res_area[feat["distrito"]] += feat["area_m2"]

    total_est = 0
    for feat in features:
        d = feat["distrito"]
        dist_data = censo.get(d, {"personas": 0, "hogares": 0})
        feat["distrito_pop"] = dist_data["personas"]
        feat["distrito_hog"] = dist_data["hogares"]

        if feat["is_residential"] and d and dist_res_area[d] > 0 and dist_data["personas"] > 0:
            est = max(0, round(dist_data["personas"] * feat["area_m2"] / dist_res_area[d]))
            feat["est_personas"] = est
            total_est += est

    print(f"  Total est_personas assigned: {total_est:,}  ({time.time()-t0:.1f}s)")

    # Quick sanity check per district
    by_dist = defaultdict(int)
    for feat in features:
        if feat["est_personas"] > 0:
            by_dist[feat["distrito"]] += feat["est_personas"]
    print("  District totals (top 5):")
    for d, v in sorted(by_dist.items(), key=lambda x: -x[1])[:5]:
        expected = censo.get(d, {}).get("personas", "?")
        print(f"    {d}: est={v:,}  census={expected:,}")


# ── Step 4: Generate PMTiles ──────────────────────────────────────────────

def generate_pmtiles(features):
    print(f"\nStep 4: Generating PMTiles (zoom {MIN_ZOOM}-{MAX_ZOOM})...")
    t0 = time.time()

    # Build PMTiles-ready feature list (geometry + properties only)
    tile_features = []
    for feat in features:
        tile_features.append({
            "geometry": feat["geometry"],
            "properties": {
                "best_height_m":  feat["best_height_m"],
                "area_m2":        int(feat["area_m2"]),
                "is_residential": 1 if feat["is_residential"] else 0,
                "subtype":        feat["subtype"],
                "est_personas":   feat["est_personas"],
                "distrito":       feat["distrito"],
                "distrito_pop":   feat["distrito_pop"],
                "distrito_hog":   feat["distrito_hog"],
            },
        })

    print("  Building spatial index...")
    grid = defaultdict(list)
    for i, feat in enumerate(tile_features):
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
                [tile_features[i] for i in candidate_indices], bounds, LAYER_NAME, EXTENT
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
                "description": "Building footprints for Itapúa, Paraguay (Overture Maps) with DGEEC Censo 2022",
                "vector_layers": [{
                    "id": LAYER_NAME,
                    "fields": {
                        "best_height_m":  "Number",
                        "area_m2":        "Number",
                        "is_residential": "Number",
                        "subtype":        "String",
                        "est_personas":   "Number",
                        "distrito":       "String",
                        "distrito_pop":   "Number",
                        "distrito_hog":   "Number",
                    },
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


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    t_start = time.time()
    print("=" * 60)
    print("BUILD ITAPÚA BUILDINGS PMTILES (Overture Maps + DGEEC 2022)")
    print("=" * 60)

    print("\nStep 0: Loading censo + distrito boundaries...")
    censo = load_censo()
    print(f"  Census: {len(censo)} distritos loaded")
    gdf, dist_geoms, dist_names = load_distritos()
    print(f"  Distritos: {len(dist_names)} polygons")

    features = load_buildings()
    if not features:
        print("ERROR: no features loaded")
        return

    assign_districts(features, dist_geoms, dist_names)
    distribute_population(features, censo)
    generate_pmtiles(features)

    print(f"\nDone in {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    main()
