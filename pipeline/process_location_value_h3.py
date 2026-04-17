"""
Process location_value components to H3 parquet for a territory.

Reads GEE-exported rasters from GCS + generates OSM road distance locally,
then runs H3 zonal stats and computes composite score.

Components (same sources as Misiones):
  c_access_cities   — travel time to cities (Oxford MAP 2015, Nelson 2019 methodology)
  c_healthcare      — travel time to healthcare via Oxford MAP friction_surface_2019 +
                      MCP_Geometric cost distance from OSM hospital/clinic points.
                      GEE cumulativeCost fails in batch mode; computation done locally
                      using skimage.graph.MCP_Geometric (identical algorithm).
  c_nightlights     — VIIRS DNB mean radiance 2022-2024
  c_slope           — terrain slope from Copernicus DEM GLO-30 (FABDEM input)
  c_road_dist       — distance to primary road from OSM

Score orientation:
  c_access_cities → invert (less time = more accessible = higher value)
  c_healthcare    → invert
  c_nightlights   → direct (more light = more activity = higher value)
  c_slope         → invert (flatter = better)
  c_road_dist     → invert (closer = better)

Usage:
  python pipeline/process_location_value_h3.py --territory itapua_py
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time

_GCLOUD = 'gcloud.cmd' if platform.system() == 'Windows' else 'gcloud'

import numpy as np
import pandas as pd
import rasterio
import requests
from scipy.spatial import cKDTree

from config import OUTPUT_DIR, GCS_BUCKET, get_territory
from scoring import run_full_diagnostics, geometric_mean_score

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Helpers ──────────────────────────────────────────────────────────────────

def percentile_rank(series: pd.Series, invert: bool = False) -> pd.Series:
    valid = series.notna() & np.isfinite(series)
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        ranked = series[valid].rank(pct=True) * 100.0
        result[valid] = ranked
    if invert:
        result = 100.0 - result
    return result.round(2)


def sample_raster_at_centroids(raster_path: str, h3_centroids: pd.DataFrame,
                                nodata_val=None) -> np.ndarray:
    """Sample raster at (lng, lat) centroid pairs. Returns array of mean values."""
    with rasterio.open(raster_path) as src:
        nd = nodata_val if nodata_val is not None else src.nodata
        coords = list(zip(h3_centroids['lng'], h3_centroids['lat']))
        vals = np.array([v[0] for v in src.sample(coords)])
        if nd is not None:
            vals = vals.astype(float)
            vals[vals == nd] = np.nan
        return vals


def h3_centroid(h3index: str) -> tuple[float, float]:
    """Return (lat, lng) for an H3 index string."""
    try:
        from h3 import cell_to_latlng
        return cell_to_latlng(h3index)
    except ImportError:
        import h3
        return h3.h3_to_geo(h3index)


# ── Healthcare travel time via MCP ────────────────────────────────────────────

def compute_healthcare_mcp(friction_path: str, facility_coords: list,
                            lats: list, lngs: list) -> np.ndarray:
    """Compute travel time to nearest healthcare facility via MCP_Geometric.

    Uses the Oxford MAP friction surface (min/m) and Dijkstra's algorithm —
    the same computation as GEE's cumulativeCost, executed locally.

    Args:
        friction_path: path to friction surface raster (minutes per meter)
        facility_coords: list of [lon, lat] pairs for healthcare facilities
        lats, lngs: H3 centroid coordinates (arrays)

    Returns:
        Travel time in minutes for each H3 centroid (NaN if unreachable)
    """
    try:
        from skimage.graph import MCP_Geometric
    except ImportError:
        raise ImportError("scikit-image required: pip install scikit-image")

    with rasterio.open(friction_path) as src:
        friction_data = src.read(1).astype(np.float64)
        transform = src.transform
        nodata = src.nodata

        # Pixel size in meters (approximate; at 1°≈111km)
        pixel_w_m = abs(transform.a) * 111_000
        pixel_h_m = abs(transform.e) * 111_000
        pixel_size_m = (pixel_w_m + pixel_h_m) / 2

        # Mask nodata + negative (ocean, NoData) with very high cost
        if nodata is not None:
            friction_data[friction_data == nodata] = 1e8
        friction_data[~np.isfinite(friction_data) | (friction_data < 0)] = 1e8

        # Cost per pixel in minutes = friction(min/m) × pixel_size(m)
        # MCP_Geometric interpolates between pixels, so this is per unit length.
        # Scale so that output is in minutes.
        cost_surface = friction_data * pixel_size_m

        # Facility pixel coordinates
        starts = []
        for coord in facility_coords:
            lon, lat = float(coord[0]), float(coord[1])
            col_f, row_f = ~transform * (lon, lat)
            r, c = int(row_f), int(col_f)
            if 0 <= r < cost_surface.shape[0] and 0 <= c < cost_surface.shape[1]:
                starts.append((r, c))

        if not starts:
            print("    WARNING: no facility pixels found in raster extent")
            return np.full(len(lats), np.nan)

        # Deduplicate starts
        starts = list(set(starts))
        print(f"    MCP from {len(starts)} facility pixels (out of {len(facility_coords)} coords)")

        mcp = MCP_Geometric(cost_surface)
        cumulative_costs, _ = mcp.find_costs(starts)

        # Sample at H3 centroids
        result = np.full(len(lats), np.nan)
        for i, (lat, lng) in enumerate(zip(lats, lngs)):
            col_f, row_f = ~transform * (lng, lat)
            r, c = int(row_f), int(col_f)
            if 0 <= r < cumulative_costs.shape[0] and 0 <= c < cumulative_costs.shape[1]:
                val = cumulative_costs[r, c]
                if val < 1e7:
                    result[i] = round(float(val), 2)

        return result


def compute_slope_from_dem(dem_path: str, output_path: str) -> bool:
    """Compute slope (degrees) from a DEM raster and save to output_path.

    Uses central-difference gradient (same formula as GEE ee.Terrain.slope).
    Returns True if successful.
    """
    try:
        with rasterio.open(dem_path) as src:
            dem = src.read(1).astype(np.float64)
            transform = src.transform
            nodata = src.nodata
            profile = src.profile.copy()
            mean_lat = transform.f + transform.e * dem.shape[0] / 2

        if nodata is not None:
            dem[dem == nodata] = np.nan

        # Pixel size in meters (approximate; latitude-corrected for x)
        pixel_x_m = abs(transform.a) * 111_000 * np.cos(np.radians(mean_lat))
        pixel_y_m = abs(transform.e) * 111_000

        # Central differences (edges use one-sided)
        dz_dx = np.gradient(dem, pixel_x_m, axis=1)
        dz_dy = np.gradient(dem, pixel_y_m, axis=0)

        slope = np.degrees(np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))).astype(np.float32)
        slope[np.isnan(dem)] = np.nan

        profile.update(dtype='float32', count=1, nodata=None)
        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(slope, 1)

        valid = np.sum(np.isfinite(slope))
        print(f"    slope: {valid:,} valid pixels, mean={np.nanmean(slope):.2f} deg")
        return True
    except Exception as e:
        print(f"    ERROR computing slope from DEM: {e}")
        return False


def is_valid_raster(path: str) -> bool:
    """Return True if raster exists and has at least some non-NaN pixels."""
    if not os.path.exists(path):
        return False
    try:
        with rasterio.open(path) as src:
            data = src.read(1)
            nodata = src.nodata
            if nodata is not None:
                valid = np.sum(data != nodata)
            else:
                valid = np.sum(np.isfinite(data))
            return int(valid) > 0
    except Exception:
        return False


# ── OSM road distance ─────────────────────────────────────────────────────────

def compute_road_dist_at_centroids(out_dir: str, bbox: list,
                                   lats: list, lngs: list) -> np.ndarray:
    """Compute distance (m) from each H3 centroid to nearest primary road.

    Uses pre-fetched road geometry points saved by the data preparation step.
    Approximates geodesic distance using scaled Cartesian coordinates.
    """
    road_coords_path = os.path.join(out_dir, 'lv_road_coords.json')

    # Fetch road coords if not cached
    if not os.path.exists(road_coords_path):
        west, south, east, north = bbox
        q_bbox = f"{south},{west},{north},{east}"
        query = f"""[out:json][timeout:60][bbox:{q_bbox}];
(
  way[highway=motorway];
  way[highway=trunk];
  way[highway=primary];
  way[highway=secondary];
);
out geom;"""
        print("  Fetching road geometries from Overpass...")
        road_coords = []
        for srv in ['https://overpass.kumi.systems/api/interpreter',
                    'https://overpass-api.de/api/interpreter']:
            try:
                r = requests.post(srv, data=query, timeout=120)
                r.raise_for_status()
                data = r.json()
                for el in data.get('elements', []):
                    if el['type'] == 'way' and 'geometry' in el:
                        road_coords.extend(
                            [(nd['lon'], nd['lat']) for nd in el['geometry']])
                print(f"  {len(road_coords):,} road points fetched")
                break
            except Exception as e:
                print(f"  Overpass {srv}: {e}")
        if not road_coords:
            raise RuntimeError("No road coords available and Overpass unreachable")
        with open(road_coords_path, 'w') as f:
            json.dump({'road_points': road_coords}, f)
    else:
        with open(road_coords_path) as f:
            road_coords = json.load(f)['road_points']
        print(f"  Loaded {len(road_coords):,} road points from cache")

    # Build scaled Cartesian KDTree (lng scaled by cos(mean_lat))
    mean_lat = np.mean(lats)
    cos_lat = np.cos(np.radians(mean_lat))
    METERS_PER_DEG = 111_000.0

    road_arr = np.array(road_coords)
    road_xy = np.column_stack([road_arr[:, 0] * cos_lat, road_arr[:, 1]])
    query_xy = np.column_stack([np.array(lngs) * cos_lat, np.array(lats)])

    tree = cKDTree(road_xy)
    dists_deg, _ = tree.query(query_xy)
    return (dists_deg * METERS_PER_DEG).astype(np.float32)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Location value H3 zonal stats + scoring")
    parser.add_argument("--territory", default="misiones")
    parser.add_argument("--diagnostics", action="store_true",
                        help="Emit PCA diagnostics JSON")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    bbox = territory['bbox']
    out_prefix = territory['output_prefix'].rstrip('/')
    out_dir = os.path.join(OUTPUT_DIR, out_prefix) if out_prefix else OUTPUT_DIR

    os.makedirs(out_dir, exist_ok=True)

    print(f"Territory: {args.territory}")
    print(f"Output dir: {out_dir}")

    # ── GEE rasters (must be downloaded from GCS first) ───────────────────
    gcs_subdir = '' if args.territory == 'misiones' else f"{args.territory}/"
    # c_healthcare is NOT in this dict — it's computed locally from lv_friction.tif
    gee_rasters = {
        'c_access_cities': os.path.join(out_dir, 'lv_cities_access.tif'),
        'c_nightlights':   os.path.join(out_dir, 'lv_viirs_annual.tif'),
        'c_slope':         os.path.join(out_dir, 'lv_slope.tif'),
    }
    # Friction raster for local healthcare MCP computation
    friction_path = os.path.join(out_dir, 'lv_friction.tif')
    # Raw DEM for local slope computation (GEE ee.Terrain.slope fails on mosaics)
    dem_path = os.path.join(out_dir, 'lv_dem.tif')

    all_raster_files = list(gee_rasters.values()) + [friction_path, dem_path]
    missing_files = [(os.path.basename(p), p) for p in all_raster_files
                     if not os.path.exists(p) or not is_valid_raster(p)]
    if missing_files:
        print(f"\nDownloading {len(missing_files)} rasters from GCS...")
        for fname, path in missing_files:
            gcs_path = f"gs://{GCS_BUCKET}/satellite/{gcs_subdir}{fname}"
            print(f"  {gcs_path} -> {path}")
            r = subprocess.run(
                [_GCLOUD, 'storage', 'cp', gcs_path, path],
                capture_output=True, text=True
            )
            if r.returncode != 0:
                print(f"  WARNING: failed to download {fname}: {r.stderr}")

    # If DEM exists but slope raster is missing/invalid, compute slope locally
    dem_path = os.path.join(out_dir, 'lv_dem.tif')
    slope_path = gee_rasters['c_slope']
    if is_valid_raster(dem_path) and not is_valid_raster(slope_path):
        print("  Computing slope from DEM locally (GEE ee.Terrain.slope fails on mosaic)...")
        compute_slope_from_dem(dem_path, slope_path)

    # Verify which rasters are valid (non-empty)
    available = {col: path for col, path in gee_rasters.items()
                 if is_valid_raster(path)}
    invalid = {col: path for col, path in gee_rasters.items()
               if not is_valid_raster(path)}
    if invalid:
        print(f"  WARNING: Invalid/empty rasters: {list(invalid.keys())}. Skipping.")

    if not available:
        print("ERROR: No valid rasters available. Run gee_export_location_value.py first.")
        return 1

    print(f"\nAvailable raster components: {list(available.keys())}")

    # ── Load hexagon grid ──────────────────────────────────────────────────
    hex_path_lite = os.path.join(out_dir, 'hexagons-lite.geojson')
    hex_path_full = os.path.join(out_dir, 'hexagons.geojson')
    hex_path = hex_path_lite if os.path.exists(hex_path_lite) else hex_path_full

    print(f"\nLoading hexagon grid: {hex_path}")
    with open(hex_path) as f:
        gj = json.load(f)
    features = gj['features']
    n = len(features)
    print(f"  {n:,} hexagons")

    # Build centroid lookup
    print("  Computing H3 centroids...")
    h3ids = []
    lats, lngs = [], []
    for feat in features:
        h3id = feat['properties']['h3index']
        lat, lng = h3_centroid(h3id)
        h3ids.append(h3id)
        lats.append(lat)
        lngs.append(lng)
    centroids = pd.DataFrame({'h3index': h3ids, 'lat': lats, 'lng': lngs})

    # ── Sample rasters at centroids ────────────────────────────────────────
    print("\nSampling rasters at H3 centroids...")
    t0 = time.time()
    data = {'h3index': h3ids}

    for col, path in available.items():
        print(f"  {col}: {path}")
        try:
            vals = sample_raster_at_centroids(path, centroids)
            data[col] = vals
            valid = np.sum(np.isfinite(vals) & (vals >= 0))
            print(f"    valid={valid:,}/{n:,}  mean={np.nanmean(vals):.2f}")
        except Exception as e:
            print(f"    ERROR: {e}")
            data[col] = np.full(n, np.nan)

    # ── OSM road distance (KDTree, no raster) ─────────────────────────────
    print("  c_road_dist: computing from OSM road coords...")
    try:
        road_dist = compute_road_dist_at_centroids(out_dir, bbox, lats, lngs)
        data['c_road_dist'] = road_dist
        valid = np.sum(np.isfinite(road_dist))
        print(f"    valid={valid:,}/{n:,}  mean={np.nanmean(road_dist):.0f} m")
    except Exception as e:
        print(f"    WARNING: road distance failed: {e}")

    # ── Healthcare travel time (Oxford MAP friction + MCP) ────────────────
    # Uses lv_friction.tif (Oxford MAP friction_surface_2019) + hospital coords
    # to compute minimum-cost travel time via MCP_Geometric (= GEE cumulativeCost).
    health_cache = os.path.join(out_dir, 'lv_healthcare_facilities.json')
    if is_valid_raster(friction_path) and os.path.exists(health_cache):
        print("  c_healthcare: computing via MCP from Oxford MAP friction + OSM facilities...")
        try:
            with open(health_cache) as f:
                hc_pts = json.load(f)
            hc_vals = compute_healthcare_mcp(friction_path, hc_pts, lats, lngs)
            data['c_healthcare'] = hc_vals
            valid = np.sum(np.isfinite(hc_vals))
            print(f"    valid={valid:,}/{n:,}  mean={np.nanmean(hc_vals):.1f} min")
        except Exception as e:
            print(f"    WARNING: MCP healthcare failed: {e}")
    elif os.path.exists(health_cache):
        print("  c_healthcare: friction raster missing, falling back to KDTree euclidean...")
        try:
            with open(health_cache) as f:
                hc_pts = json.load(f)
            mean_lat = float(np.mean(lats))
            cos_lat = np.cos(np.radians(mean_lat))
            hc_arr = np.array(hc_pts)
            hc_xy = np.column_stack([hc_arr[:, 0] * cos_lat, hc_arr[:, 1]])
            q_xy = np.column_stack([np.array(lngs) * cos_lat, np.array(lats)])
            tree = cKDTree(hc_xy)
            dists_deg, _ = tree.query(q_xy)
            data['c_healthcare'] = (dists_deg * 111_000.0).astype(np.float32)
            print(f"    valid={np.isfinite(data['c_healthcare']).sum():,}/{n:,}  "
                  f"mean={np.nanmean(data['c_healthcare']):.0f} m")
        except Exception as e:
            print(f"    WARNING: healthcare fallback failed: {e}")
    else:
        print("  c_healthcare: no friction raster or facility cache — component will be missing")

    df = pd.DataFrame(data)
    print(f"  Sampled in {time.time()-t0:.0f}s")

    # ── Percentile rank (orientation-corrected) ────────────────────────────
    print("\nComputing percentile ranks...")
    # All components with inversion flags (invert=True: less = better)
    ALL_COMPONENTS = {
        'c_access_cities': True,
        'c_healthcare':    True,
        'c_nightlights':   False,
        'c_slope':         True,
        'c_road_dist':     True,
    }

    rank_cols = []
    for col, invert in ALL_COMPONENTS.items():
        if col not in df.columns or df[col].isna().all():
            continue
        r_col = f'r_{col}'
        df[r_col] = percentile_rank(df[col], invert=invert)
        rank_cols.append(r_col)
        print(f"  {r_col}: mean={df[r_col].mean():.1f}, std={df[r_col].std():.1f}")

    # ── PCA diagnostics (OECD methodology) ────────────────────────────────
    print("\nRunning PCA diagnostics...")
    valid_mask = df[rank_cols].notna().all(axis=1)
    df_valid = df[valid_mask][rank_cols]

    if len(df_valid) > 100:
        diag = run_full_diagnostics(df_valid, rank_cols, corr_threshold=0.70)
        retained_rcols = diag['variable_selection']['retained']
        dropped = diag['variable_selection']['dropped']
        print(f"  Retained: {retained_rcols}")
        if dropped:
            print(f"  Dropped (|r|>0.70): {dropped}")
        if args.diagnostics:
            diag_path = os.path.join(out_dir, 'location_value_diagnostics.json')
            with open(diag_path, 'w') as f:
                json.dump(diag, f, indent=2, default=str)
            print(f"  Diagnostics: {diag_path}")
    else:
        print("  Too few valid rows for PCA, using all components.")
        retained_rcols = rank_cols

    # ── Composite score: geometric mean ───────────────────────────────────
    print("\nComputing composite score (geometric mean)...")
    df['score'] = geometric_mean_score(df, retained_rcols, floor=1.0)
    df['score'] = df['score'].round(1)

    valid_score = df['score'].notna().sum()
    print(f"  Valid scores: {valid_score:,}/{n:,}")
    print(f"  Score: mean={df['score'].mean():.1f}, std={df['score'].std():.1f}, "
          f"min={df['score'].min():.1f}, max={df['score'].max():.1f}")

    # ── Type labels (quartile bucketing) ──────────────────────────────────
    scored = df[df['score'].notna()].copy()
    try:
        scored['type'] = pd.qcut(scored['score'], 4, labels=[1, 2, 3, 4]).astype(int)
    except ValueError:
        scored['type'] = pd.cut(scored['score'], bins=[0, 25, 50, 75, 100],
                                labels=[1, 2, 3, 4], include_lowest=True).astype(int)
    type_map = {1: 'Accesibilidad baja', 2: 'Accesibilidad moderada',
                3: 'Accesibilidad alta', 4: 'Accesibilidad muy alta'}
    scored['type_label'] = scored['type'].map(type_map)

    # ── Display columns ────────────────────────────────────────────────────
    # Column names must match ANALYSIS_REGISTRY variables in config.ts
    col_rename = {
        'c_access_cities': 'c_access_20k',
        'c_healthcare':    'c_healthcare',
        'c_nightlights':   'c_nightlights',
        'c_slope':         'c_slope',
        'c_road_dist':     'c_road_dist',
    }
    for old, new in col_rename.items():
        if old in scored.columns:
            scored[new] = scored[old].round(2)

    out_cols = ['h3index', 'score', 'type', 'type_label']
    for new in col_rename.values():
        if new in scored.columns:
            out_cols.append(new)

    result = scored[out_cols].copy()

    # ── Save ──────────────────────────────────────────────────────────────
    out_path = os.path.join(out_dir, 'sat_location_value.parquet')
    result.to_parquet(out_path, index=False)
    size_mb = os.path.getsize(out_path) / 1024 / 1024

    print(f"\n{'='*60}")
    print(f"  Rows: {len(result):,}")
    print(f"  Types: {result['type'].value_counts().sort_index().to_dict()}")
    print(f"  Saved: {out_path} ({size_mb:.1f} MB)")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
