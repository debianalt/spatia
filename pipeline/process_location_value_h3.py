"""
Process location_value components to H3 parquet for a territory.

Reads 4 GEE-exported rasters from GCS + generates OSM road distance locally,
then runs H3 zonal stats and computes composite score.

Components (same sources as Misiones):
  c_access_cities   — travel time to cities (Oxford MAP 2015, Nelson 2019 methodology)
  c_healthcare      — travel time to healthcare (Oxford MAP friction + OSM facilities)
  c_nightlights     — VIIRS DNB mean radiance 2022-2024
  c_slope           — terrain slope from SRTM 30m
  c_road_dist       — distance to primary road from OSM Paraguay

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
import subprocess
import sys
import time

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
    gee_rasters = {
        'c_access_cities': os.path.join(out_dir, 'lv_cities_access.tif'),
        'c_healthcare':    os.path.join(out_dir, 'lv_healthcare.tif'),
        'c_nightlights':   os.path.join(out_dir, 'lv_viirs_annual.tif'),
        'c_slope':         os.path.join(out_dir, 'lv_slope.tif'),
    }

    missing = [(col, path) for col, path in gee_rasters.items()
               if not os.path.exists(path)]
    if missing:
        print(f"\nDownloading {len(missing)} rasters from GCS...")
        for col, path in missing:
            fname = os.path.basename(path)
            gcs_path = f"gs://{GCS_BUCKET}/satellite/{gcs_subdir}{fname}"
            print(f"  {gcs_path} -> {path}")
            r = subprocess.run(
                ['gcloud', 'storage', 'cp', gcs_path, path],
                capture_output=True, text=True
            )
            if r.returncode != 0:
                print(f"  WARNING: failed to download {fname}: {r.stderr}")

    # Verify which rasters exist
    available = {col: path for col, path in gee_rasters.items()
                 if os.path.exists(path)}
    missing_cols = [col for col in gee_rasters if col not in available]
    if missing_cols:
        print(f"  WARNING: Missing rasters: {missing_cols}. These components will be skipped.")

    if not available:
        print("ERROR: No rasters available. Run gee_export_location_value.py first.")
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

    # ── Healthcare distance (KDTree from OSM facilities) ──────────────────
    # GEE cumulativeCost failed; use same KDTree approach as roads.
    # Source: 874 OSM hospitals/clinics in Itapúa (cached from Overpass).
    # Replaces GEE lv_healthcare.tif proxy (which was identical to cities access).
    health_cache = os.path.join(out_dir, 'lv_healthcare_facilities.json')
    if os.path.exists(health_cache) and 'c_healthcare' not in data:
        print("  c_healthcare: computing from OSM facility coords...")
        try:
            with open(health_cache) as f:
                hc_pts = json.load(f)
            mean_lat = float(np.mean(lats))
            cos_lat = np.cos(np.radians(mean_lat))
            METERS_PER_DEG = 111_000.0
            hc_arr = np.array(hc_pts)
            hc_xy = np.column_stack([hc_arr[:, 0] * cos_lat, hc_arr[:, 1]])
            q_xy = np.column_stack([np.array(lngs) * cos_lat, np.array(lats)])
            tree = cKDTree(hc_xy)
            dists_deg, _ = tree.query(q_xy)
            hc_dist = (dists_deg * METERS_PER_DEG).astype(np.float32)
            data['c_healthcare'] = hc_dist
            print(f"    valid={np.isfinite(hc_dist).sum():,}/{n:,}  mean={np.nanmean(hc_dist):.0f} m")
        except Exception as e:
            print(f"    WARNING: healthcare distance failed: {e}")
    elif 'c_healthcare' in data:
        # Check if it's actually the proxy (identical to cities access)
        if 'c_access_cities' in data:
            corr = np.corrcoef(
                data['c_healthcare'][np.isfinite(data['c_healthcare']) & np.isfinite(data['c_access_cities'])],
                data['c_access_cities'][np.isfinite(data['c_healthcare']) & np.isfinite(data['c_access_cities'])]
            )[0, 1]
            if abs(corr) > 0.999:
                print("  c_healthcare: detected as cities proxy (r>0.999), replacing with OSM distance")
                if os.path.exists(health_cache):
                    try:
                        with open(health_cache) as f:
                            hc_pts = json.load(f)
                        mean_lat = float(np.mean(lats))
                        cos_lat = np.cos(np.radians(mean_lat))
                        METERS_PER_DEG = 111_000.0
                        hc_arr = np.array(hc_pts)
                        hc_xy = np.column_stack([hc_arr[:, 0] * cos_lat, hc_arr[:, 1]])
                        q_xy = np.column_stack([np.array(lngs) * cos_lat, np.array(lats)])
                        tree = cKDTree(hc_xy)
                        dists_deg, _ = tree.query(q_xy)
                        data['c_healthcare'] = (dists_deg * METERS_PER_DEG).astype(np.float32)
                        print(f"    replaced with OSM proximity: mean={np.nanmean(data['c_healthcare']):.0f} m")
                    except Exception as e:
                        print(f"    WARNING: OSM healthcare distance failed: {e}")

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
    col_rename = {
        'c_access_cities': 'c_access_cities_min',
        'c_healthcare':    'c_healthcare_min',
        'c_nightlights':   'c_nightlights',
        'c_slope':         'c_slope_deg',
        'c_road_dist':     'c_road_dist_m',
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
