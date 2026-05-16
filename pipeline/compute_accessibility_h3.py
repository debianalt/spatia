"""
Compute accessibility metrics for a territory → sat_accessibility.parquet.

Comparable across territories: same sources (Oxford MAP + OSM) for both Misiones and Itapúa.

Output columns:
  travel_min_capital[_raw]         MCP travel time to capital city (Oxford MAP friction + MCP_Geometric)
  travel_min_cabecera[_raw]        Oxford MAP accessibility_to_cities raster
  dist_nearest_hospital_km[_raw]   OSM hospital/clinic KDTree
  dist_nearest_secundaria_km[_raw] OSM school KDTree
  dist_primary_m[_raw]             OSM road KDTree (motorway/trunk/primary/secondary), stored in km
  score                            PCA geometric mean composite (0–100)
  type                             K-means cluster (1=most accessible, 4=least)
  type_label                       Spanish label
  pca_1, pca_2                     PCA coordinates

Non-_raw columns: percentile rank (inverted: less distance/time = higher rank = more accessible).
_raw columns: physical measurements (minutes or km).

Usage:
  python pipeline/compute_accessibility_h3.py --territory misiones
  python pipeline/compute_accessibility_h3.py --territory itapua_py
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import rasterio
import requests
from scipy.spatial import cKDTree
from sklearn.cluster import KMeans

from config import OUTPUT_DIR, GCS_BUCKET, get_territory
from scoring import run_full_diagnostics, geometric_mean_score, load_goalposts, score_with_goalposts

_GCLOUD = 'gcloud.cmd' if platform.system() == 'Windows' else 'gcloud'

CAPITAL_COORDS = {
    'misiones':       (-27.367,  -55.896),   # Posadas (lat, lng)
    'itapua_py':      (-27.336,  -55.869),   # Encarnación (lat, lng)
    'corrientes':     (-27.4676, -58.8341),  # Corrientes capital (lat, lng)
    'alto_parana_py': (-25.5097, -54.6111),  # Ciudad del Este (lat, lng)
}

TYPE_LABELS = {
    1: 'Bien conectado',
    2: 'Moderadamente aislado',
    3: 'Lejos de ruta primaria',
    4: 'Extremadamente aislado',
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def percentile_rank(series: pd.Series, invert: bool = False) -> pd.Series:
    valid = series.notna() & np.isfinite(series)
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    if invert:
        result = 100.0 - result
    return result.round(2)


def is_valid_raster(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        with rasterio.open(path) as src:
            data = src.read(1)
            nd = src.nodata
            valid = np.sum(data != nd) if nd is not None else np.sum(np.isfinite(data))
            return int(valid) > 0
    except Exception:
        return False


def download_from_gcs(bucket: str, gcs_key: str, local_path: str) -> bool:
    r = subprocess.run(
        [_GCLOUD, 'storage', 'cp', f'gs://{bucket}/{gcs_key}', local_path],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"  WARNING: GCS download failed for {gcs_key}: {r.stderr.strip()}")
    return r.returncode == 0


def h3_centroid(h3index: str) -> tuple[float, float]:
    try:
        from h3 import cell_to_latlng
        return cell_to_latlng(h3index)
    except ImportError:
        import h3
        return h3.h3_to_geo(h3index)


def sample_raster_at_centroids(raster_path: str, lngs: list, lats: list,
                                nodata_val=None) -> np.ndarray:
    with rasterio.open(raster_path) as src:
        nd = nodata_val if nodata_val is not None else src.nodata
        coords = list(zip(lngs, lats))
        vals = np.array([v[0] for v in src.sample(coords)], dtype=np.float64)
        if nd is not None:
            vals[vals == nd] = np.nan
    return vals


def compute_mcp_travel_time(friction_path: str, source_lat: float, source_lng: float,
                             lats: list, lngs: list) -> np.ndarray:
    """MCP least-cost travel time from a single source point (capital city)."""
    try:
        from skimage.graph import MCP_Geometric
    except ImportError:
        raise ImportError("scikit-image required: pip install scikit-image")

    with rasterio.open(friction_path) as src:
        friction = src.read(1).astype(np.float64)
        transform = src.transform
        nd = src.nodata

        pixel_w_m = abs(transform.a) * 111_000
        pixel_h_m = abs(transform.e) * 111_000
        pixel_size_m = (pixel_w_m + pixel_h_m) / 2

        if nd is not None:
            friction[friction == nd] = 1e8
        friction[~np.isfinite(friction) | (friction < 0)] = 1e8

        cost_surface = friction * pixel_size_m

        col_f, row_f = ~transform * (source_lng, source_lat)
        r0, c0 = int(row_f), int(col_f)
        if not (0 <= r0 < cost_surface.shape[0] and 0 <= c0 < cost_surface.shape[1]):
            print(f"  WARNING: capital coords ({source_lat},{source_lng}) outside raster extent")
            return np.full(len(lats), np.nan)

        print(f"  MCP from capital pixel ({r0},{c0})")
        mcp = MCP_Geometric(cost_surface)
        cumulative, _ = mcp.find_costs([(r0, c0)])

        result = np.full(len(lats), np.nan)
        for i, (lat, lng) in enumerate(zip(lats, lngs)):
            col_f, row_f = ~transform * (lng, lat)
            r, c = int(row_f), int(col_f)
            if 0 <= r < cumulative.shape[0] and 0 <= c < cumulative.shape[1]:
                val = cumulative[r, c]
                if val < 1e7:
                    result[i] = round(float(val), 2)
        return result


def fetch_osm_points(bbox: list, amenity_query: str, cache_path: str) -> list:
    """Fetch OSM node/way centroids for a query, return [[lon,lat],...] and cache."""
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            pts = json.load(f)
        print(f"  Loaded {len(pts):,} points from cache: {os.path.basename(cache_path)}")
        return pts

    west, south, east, north = bbox
    q_bbox = f"{south},{west},{north},{east}"
    query = f"[out:json][timeout:120][bbox:{q_bbox}];\n{amenity_query};\nout center;"

    pts = []
    for srv in ['https://overpass.kumi.systems/api/interpreter',
                'https://overpass-api.de/api/interpreter']:
        try:
            r = requests.post(srv, data=query, timeout=150)
            r.raise_for_status()
            for el in r.json().get('elements', []):
                if el['type'] == 'node':
                    pts.append([el['lon'], el['lat']])
                elif el['type'] == 'way' and 'center' in el:
                    pts.append([el['center']['lon'], el['center']['lat']])
            print(f"  Fetched {len(pts):,} points from Overpass")
            break
        except Exception as e:
            print(f"  Overpass {srv}: {e}")

    if pts:
        with open(cache_path, 'w') as f:
            json.dump(pts, f)
    return pts


def fetch_osm_road_coords(bbox: list, cache_path: str) -> list:
    """Fetch road geometry coords from Overpass, return [[lon,lat],...] and cache."""
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            data = json.load(f)
        pts = data if isinstance(data, list) else data.get('road_points', [])
        print(f"  Loaded {len(pts):,} road points from cache")
        return pts

    west, south, east, north = bbox
    q_bbox = f"{south},{west},{north},{east}"
    query = f"""[out:json][timeout:120][bbox:{q_bbox}];
(
  way[highway=motorway];
  way[highway=trunk];
  way[highway=primary];
  way[highway=secondary];
);
out geom;"""

    pts = []
    for srv in ['https://overpass.kumi.systems/api/interpreter',
                'https://overpass-api.de/api/interpreter']:
        try:
            r = requests.post(srv, data=query, timeout=150)
            r.raise_for_status()
            for el in r.json().get('elements', []):
                if el['type'] == 'way' and 'geometry' in el:
                    pts.extend([[nd['lon'], nd['lat']] for nd in el['geometry']])
            print(f"  Fetched {len(pts):,} road points from Overpass")
            break
        except Exception as e:
            print(f"  Overpass {srv}: {e}")

    if pts:
        with open(cache_path, 'w') as f:
            json.dump({'road_points': pts}, f)
    return pts


def kdtree_distances_km(query_lats: list, query_lngs: list,
                         point_coords: list) -> np.ndarray:
    """Compute distances to nearest point in km using scaled Cartesian KDTree."""
    if not point_coords:
        return np.full(len(query_lats), np.nan)
    mean_lat = float(np.mean(query_lats))
    cos_lat = np.cos(np.radians(mean_lat))
    pts = np.array(point_coords)
    pts_xy = np.column_stack([pts[:, 0] * cos_lat, pts[:, 1]])
    q_xy = np.column_stack([np.array(query_lngs) * cos_lat, np.array(query_lats)])
    tree = cKDTree(pts_xy)
    dists_deg, _ = tree.query(q_xy)
    return (dists_deg * 111_000.0 / 1000.0).astype(np.float64)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compute accessibility H3 parquet")
    parser.add_argument("--territory", default="misiones")
    parser.add_argument("--mode", choices=["comparable", "local"], default="local",
                        help="comparable: fixed goalpost normalization; local: percentile rank (default)")
    parser.add_argument("--diagnostics", action="store_true")
    args = parser.parse_args()

    goalposts = load_goalposts() if args.mode == "comparable" else None
    if goalposts:
        print(f"  Mode: comparable (goalposts v{goalposts.get('version', '?')})")
        gp_indicators = goalposts.get('indicators', {})
    else:
        gp_indicators = {}

    territory = get_territory(args.territory)
    bbox = territory['bbox']
    out_prefix = territory['output_prefix'].rstrip('/')
    out_dir = os.path.join(OUTPUT_DIR, out_prefix) if out_prefix else OUTPUT_DIR
    gcs_subdir = '' if args.territory == 'misiones' else f"{args.territory}/"

    os.makedirs(out_dir, exist_ok=True)
    print(f"Territory: {args.territory}  |  Output: {out_dir}")

    # ── Rasters ──────────────────────────────────────────────────────────────
    friction_path = os.path.join(out_dir, 'lv_friction.tif')
    cities_path = os.path.join(out_dir, 'lv_cities_access.tif')

    for fname, path in [('lv_friction.tif', friction_path),
                         ('lv_cities_access.tif', cities_path)]:
        if not is_valid_raster(path):
            print(f"  Downloading {fname} from GCS...")
            download_from_gcs(GCS_BUCKET, f'satellite/{gcs_subdir}{fname}', path)

    if not is_valid_raster(friction_path):
        print("ERROR: lv_friction.tif not available. Run gee_export_location_value.py first.")
        return 1
    if not is_valid_raster(cities_path):
        print("ERROR: lv_cities_access.tif not available. Run gee_export_location_value.py first.")
        return 1

    # ── H3 grid ───────────────────────────────────────────────────────────────
    hex_path = os.path.join(out_dir, 'hexagons-lite.geojson')
    if not os.path.exists(hex_path):
        hex_path = os.path.join(out_dir, 'hexagons.geojson')
    print(f"Loading grid: {hex_path}")
    with open(hex_path) as f:
        features = json.load(f)['features']
    n = len(features)
    print(f"  {n:,} hexagons")

    h3ids, lats, lngs = [], [], []
    for feat in features:
        h3id = feat['properties']['h3index']
        lat, lng = h3_centroid(h3id)
        h3ids.append(h3id)
        lats.append(lat)
        lngs.append(lng)

    # ── Travel time to capital (MCP) ─────────────────────────────────────────
    cap_lat, cap_lng = CAPITAL_COORDS[args.territory]
    print(f"\nComputing MCP travel time to capital ({cap_lat:.3f},{cap_lng:.3f})...")
    t0 = time.time()
    travel_capital_raw = compute_mcp_travel_time(friction_path, cap_lat, cap_lng, lats, lngs)
    valid = np.sum(np.isfinite(travel_capital_raw))
    print(f"  valid={valid:,}/{n:,}  mean={np.nanmean(travel_capital_raw):.1f} min  "
          f"({time.time()-t0:.0f}s)")

    # ── Travel time to nearest city (cities_access raster) ───────────────────
    print("\nSampling cities_access raster...")
    travel_cabecera_raw = sample_raster_at_centroids(cities_path, lngs, lats)
    travel_cabecera_raw[travel_cabecera_raw <= 0] = np.nan
    valid = np.sum(np.isfinite(travel_cabecera_raw))
    print(f"  valid={valid:,}/{n:,}  mean={np.nanmean(travel_cabecera_raw):.1f} min")

    # ── Hospital distances (OSM KDTree) ───────────────────────────────────────
    print("\nFetching hospital coords...")
    hosp_cache = os.path.join(out_dir, 'lv_healthcare_facilities.json')
    hosp_query = """(
  node[amenity=hospital];
  node[amenity=clinic];
  node[amenity=doctors];
  way[amenity=hospital];
  way[amenity=clinic];
)"""
    hosp_pts = fetch_osm_points(bbox, hosp_query, hosp_cache)
    dist_hospital_raw = kdtree_distances_km(lats, lngs, hosp_pts)
    print(f"  mean={np.nanmean(dist_hospital_raw):.2f} km")

    # ── School distances (OSM KDTree) ─────────────────────────────────────────
    print("\nFetching school coords...")
    school_cache = os.path.join(out_dir, 'access_school_coords.json')
    school_query = """(
  node[amenity=school];
  node[amenity=college];
  way[amenity=school];
  way[amenity=college];
)"""
    school_pts = fetch_osm_points(bbox, school_query, school_cache)
    dist_school_raw = kdtree_distances_km(lats, lngs, school_pts)
    print(f"  mean={np.nanmean(dist_school_raw):.2f} km")

    # ── Road distances (OSM KDTree) ───────────────────────────────────────────
    print("\nFetching road coords...")
    road_cache = os.path.join(out_dir, 'lv_road_coords.json')
    road_pts = fetch_osm_road_coords(bbox, road_cache)
    dist_road_raw = kdtree_distances_km(lats, lngs, road_pts)
    print(f"  mean={np.nanmean(dist_road_raw):.2f} km")

    # ── Normalize raw values → 0-100 component scores ──────────────────────
    df = pd.DataFrame({
        'h3index': h3ids,
        'travel_capital_raw':   travel_capital_raw,
        'travel_cabecera_raw':  travel_cabecera_raw,
        'hospital_raw':         dist_hospital_raw,
        'school_raw':           dist_school_raw,
        'road_raw':             dist_road_raw,
    })

    RAW_TO_COMPONENT = {
        'travel_capital_raw':  ('r_travel_capital',  'c_travel_capital'),
        'travel_cabecera_raw': ('r_travel_cabecera', 'c_travel_cabecera'),
        'hospital_raw':        ('r_hospital',        'c_dist_hospital'),
        'school_raw':          ('r_school',          'c_dist_school'),
        'road_raw':            ('r_road',            'c_dist_road'),
    }

    if args.mode == 'comparable':
        print("\nNormalizing with goalposts (comparable mode)...")
        for raw_col, (r_col, gp_key) in RAW_TO_COMPONENT.items():
            gp = gp_indicators.get(gp_key)
            if gp:
                df[r_col] = score_with_goalposts(df[raw_col], gp['lo'], gp['hi'], invert=gp.get('invert', False))
                print(f"  {r_col}: goalpost [{gp['lo']}, {gp['hi']}] invert={gp.get('invert')}  mean={df[r_col].mean():.1f}")
            else:
                df[r_col] = percentile_rank(df[raw_col], invert=False)
                print(f"  {r_col}: no goalpost, fallback percentile  mean={df[r_col].mean():.1f}")
    else:
        print("\nComputing percentile ranks (local mode)...")
        for raw_col, (r_col, _gp_key) in RAW_TO_COMPONENT.items():
            df[r_col] = percentile_rank(df[raw_col], invert=False)
            print(f"  {r_col}: mean={df[r_col].mean():.1f}")

    rank_cols = [v[0] for v in RAW_TO_COMPONENT.values()]

    # ── PCA diagnostics (OECD methodology) ───────────────────────────────────
    print("\nRunning PCA diagnostics...")
    valid_mask = df[rank_cols].notna().all(axis=1)
    df_valid = df[valid_mask][rank_cols]
    if len(df_valid) > 100:
        diag = run_full_diagnostics(df_valid, rank_cols, corr_threshold=0.70)
        if args.mode == 'comparable' and goalposts:
            locked = goalposts.get('pca_variable_selection', {}).get('accessibility')
            if locked:
                retained = [c for c in locked if c in rank_cols]
                if not retained:
                    # goalpost lock uses the radio-aggregation naming
                    # (travel_min_posadas / dist_nearest_*; aggregate_radio_to_h3.py).
                    # This raster path uses r_* component names. When the schemes
                    # don't intersect, keep ALL rank_cols: deterministic and
                    # cross-territory comparable (same fixed set for Ita/Cor/AP),
                    # which is the intent of comparable mode.
                    retained = list(rank_cols)
                    print("  [comparable] lock name-scheme mismatch "
                          "(radio vs raster) -> using all rank_cols")
                dropped = [c for c in rank_cols if c not in retained]
                print(f"  [comparable] Locked selection ({len(retained)}): {retained}")
                if dropped:
                    print(f"  [comparable] Excluded: {dropped}")
            else:
                retained = diag['variable_selection']['retained']
                dropped = diag['variable_selection']['dropped']
                print(f"  [comparable] No lock found, using PCA selection: {retained}")
        else:
            retained = diag['variable_selection']['retained']
            dropped = diag['variable_selection']['dropped']
        print(f"  Retained: {retained}")
        if dropped:
            print(f"  Dropped (|r|>0.70): {dropped}")
        if args.diagnostics:
            diag_path = os.path.join(out_dir, 'accessibility_diagnostics.json')
            with open(diag_path, 'w') as f:
                json.dump(diag, f, indent=2, default=str)
            from sklearn.decomposition import PCA
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(df_valid)
            pca = PCA(n_components=2)
            coords = pca.fit_transform(X_scaled)
            df.loc[valid_mask, 'pca_1'] = coords[:, 0].round(6)
            df.loc[valid_mask, 'pca_2'] = coords[:, 1].round(6)
    else:
        retained = rank_cols
    # Store PCA coords if not already done
    if 'pca_1' not in df.columns:
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        col_means = df[rank_cols].mean()
        col_means = col_means.fillna(50.0)  # neutral rank for entirely-NaN columns
        X = df[rank_cols].fillna(col_means)
        X_scaled = scaler.fit_transform(X)
        pca = PCA(n_components=2)
        coords = pca.fit_transform(X_scaled)
        df['pca_1'] = coords[:, 0].round(6)
        df['pca_2'] = coords[:, 1].round(6)

    # ── Composite score ───────────────────────────────────────────────────────
    print("\nComputing composite score...")
    # Neutralize entirely-NaN retained indicators (e.g. an OSM-derived metric
    # with no Overpass features in this territory) — same treatment as the PCA
    # path above. Without this, geometric_mean_score returns all-NaN and the
    # downstream KMeans gets 0 samples. Only triggers on 100%-NaN columns, so
    # territories with full data are unaffected.
    for _c in retained:
        if df[_c].isna().all():
            print(f"  WARN: indicator '{_c}' is entirely NaN — filling neutral 50.0")
            df[_c] = 50.0
    df['score'] = geometric_mean_score(df, retained, floor=1.0).round(1)
    scored_mask = df['score'].notna()
    print(f"  valid={scored_mask.sum():,}/{n:,}  "
          f"mean={df['score'].mean():.1f}  std={df['score'].std():.1f}")

    # ── K-means types (sort clusters by score: 1=best, 4=worst) ──────────────
    print("\nK-means clustering (k=4)...")
    scored = df[scored_mask].copy()
    X_km = scored[retained].fillna(scored[retained].mean()).values
    km = KMeans(n_clusters=4, random_state=42, n_init=10)
    raw_labels = km.fit_predict(X_km)
    # Map cluster IDs: 1=highest score, 4=lowest score
    cluster_means = {c: scored['score'].values[raw_labels == c].mean()
                     for c in range(4)}
    order = sorted(cluster_means, key=lambda c: -cluster_means[c])
    label_map = {c: rank + 1 for rank, c in enumerate(order)}
    scored['type'] = np.array([label_map[l] for l in raw_labels], dtype=np.int32)
    scored['type_label'] = scored['type'].map(TYPE_LABELS)
    print(f"  Counts: {scored['type'].value_counts().sort_index().to_dict()}")

    # ── Assemble output ───────────────────────────────────────────────────────
    out = scored[[
        'h3index', 'score', 'type', 'type_label', 'pca_1', 'pca_2',
        'r_travel_capital', 'r_travel_cabecera',
        'r_hospital', 'r_school', 'r_road',
        'travel_capital_raw', 'travel_cabecera_raw',
        'hospital_raw', 'school_raw', 'road_raw',
    ]].copy()

    out = out.rename(columns={
        'r_travel_capital':  'travel_min_capital',
        'r_travel_cabecera': 'travel_min_cabecera',
        'r_hospital':        'dist_nearest_hospital_km',
        'r_school':          'dist_nearest_secundaria_km',
        'r_road':            'dist_primary_m',
        'travel_capital_raw':  'travel_min_capital_raw',
        'travel_cabecera_raw': 'travel_min_cabecera_raw',
        'hospital_raw':        'dist_nearest_hospital_km_raw',
        'school_raw':          'dist_nearest_secundaria_km_raw',
        'road_raw':            'dist_primary_m_raw',
    })

    out_path = os.path.join(out_dir, 'sat_accessibility.parquet')
    out.to_parquet(out_path, index=False)
    size_mb = os.path.getsize(out_path) / 1024 / 1024

    print(f"\n{'='*60}")
    print(f"  Rows: {len(out):,}")
    print(f"  Types: {out['type'].value_counts().sort_index().to_dict()}")
    print(f"  Saved: {out_path} ({size_mb:.1f} MB)")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
