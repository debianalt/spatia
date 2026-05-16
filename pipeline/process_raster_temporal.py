"""
Process baseline + current GeoTIFFs to H3 parquets with delta columns.

Reads two rasters per analysis (baseline + current), computes zonal stats
for each hexagon, then produces columns: value, value_baseline, value_delta
for each dynamic band. Fixed bands come from the original full-period raster.

Output schema:
  h3index | score | score_baseline | delta_score | c_ndvi | c_ndvi_baseline | c_ndvi_delta | ...

Usage:
  python pipeline/process_raster_temporal.py --analysis green_capital
  python pipeline/process_raster_temporal.py --analysis all
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import shape

from config import OUTPUT_DIR, H3_RESOLUTION, TERRITORY_CONFIGS, get_territory
from validate import validate_raster

# Default hex grid path for Misiones (backward compat). For other territories,
# resolved at runtime from territory['output_prefix'].
HEXAGONS_PATH = os.path.join(OUTPUT_DIR, "hexagons-lite.geojson")


def resolve_hexgrid_path(output_prefix):
    """Return the hexagon GeoJSON path for the given territory output_prefix."""
    if not output_prefix:
        return HEXAGONS_PATH
    candidate = os.path.join(OUTPUT_DIR, output_prefix.rstrip("/"), "hexagons.geojson")
    if os.path.exists(candidate):
        return candidate
    return os.path.join(OUTPUT_DIR, output_prefix.rstrip("/"), "hexagons-lite.geojson")

# For each analysis: which bands are in the temporal exports, their weights and invert flags.
# These must match the band order in gee_export_analysis_temporal.py outputs.
TEMPORAL_COMPONENTS = {
    'environmental_risk': {
        'dynamic': [
            # (band_idx_in_temporal, col_name, weight, invert)
            (1, 'c_fire', 0.25, False),
            (2, 'c_thermal_amp', 0.20, False),
        ],
        'fixed_from_original': [
            # (col_name, weight, invert) — these come from sat_{analysis}.parquet
            ('c_deforest', 0.25, False),
            ('c_slope', 0.15, False),
            ('c_hand', 0.15, True),
        ],
    },
    'climate_comfort': {
        'dynamic': [
            (1, 'c_heat_day', 0.25, True),
            (2, 'c_heat_night', 0.20, True),
            (3, 'c_precipitation', 0.20, False),
            (4, 'c_frost', 0.15, True),
            (5, 'c_water_stress', 0.20, False),
        ],
        'fixed_from_original': [],
    },
    'green_capital': {
        'dynamic': [
            (1, 'c_ndvi', 0.25, False),
            (2, 'c_npp', 0.20, False),
            (3, 'c_lai', 0.15, False),
            (4, 'c_vcf', 0.20, False),
        ],
        'fixed_from_original': [
            ('c_treecover', 0.20, False),
        ],
    },
    # change_pressure intentionally NOT temporal — canonical version is the
    # trend-based pixel pipeline (build_change_pressure). The level variant
    # here was clobbering it and breaking cross-territory comparability.
    'agri_potential': {
        'dynamic': [
            (1, 'c_precipitation', 0.20, False),
            (2, 'c_gdd', 0.15, False),
        ],
        'fixed_from_original': [
            ('c_soc', 0.20, False),
            ('c_ph_optimal', 0.15, False),
            ('c_clay', 0.15, False),
            ('c_slope', 0.15, True),
        ],
    },
    'forest_health': {
        'dynamic': [
            (1, 'c_ndvi_mean', 0.25, False),
            (2, 'c_fire', 0.20, True),
            (3, 'c_gpp', 0.15, False),
            (4, 'c_et', 0.15, False),
        ],
        'fixed_from_original': [
            ('c_loss_ratio', 0.25, True),
        ],
    },
}


def zonal_stats_band(src, band_idx, geom, nodata=None):
    """Compute mean of a raster band within a polygon."""
    bounds = geom.bounds
    try:
        window = from_bounds(*bounds, transform=src.transform)
        data = src.read(band_idx, window=window).astype(float)
        if data.size == 0:
            return np.nan
        transform = rasterio.windows.transform(window, src.transform)
        mask = geometry_mask([geom], out_shape=data.shape, transform=transform, invert=True)
        data[~mask] = np.nan
        if nodata is not None:
            data[data == nodata] = np.nan
        valid = data[~np.isnan(data)]
        return float(np.mean(valid)) if len(valid) > 0 else np.nan
    except Exception:
        return np.nan


def percentile_rank(series):
    """Percentile rank 0-100."""
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result


def process_temporal(analysis_id, baseline_path, current_path, original_parquet, hexgrid_features, output_path):
    """Process baseline + current rasters and merge with fixed bands from original parquet."""
    config = TEMPORAL_COMPONENTS[analysis_id]
    dynamic_bands = config['dynamic']
    fixed_bands = config['fixed_from_original']

    print(f"\n  Processing {analysis_id} temporal")
    print(f"  Baseline: {baseline_path}")
    print(f"  Current:  {current_path}")
    print(f"  Original: {original_parquet}")
    print(f"  Dynamic bands: {len(dynamic_bands)}, Fixed bands: {len(fixed_bands)}")

    t0 = time.time()

    # Load fixed band values from original parquet
    fixed_df = None
    if fixed_bands and os.path.exists(original_parquet):
        fixed_df = pd.read_parquet(original_parquet)
        fixed_cols = [col for col, _, _ in fixed_bands]
        available = [c for c in fixed_cols if c in fixed_df.columns]
        if available:
            fixed_df = fixed_df[['h3index'] + available].set_index('h3index')
            print(f"  Loaded {len(fixed_df)} hexagons with fixed bands: {available}")
        else:
            print(f"  WARN: no fixed columns found in original parquet")
            fixed_df = None

    # Process both rasters
    results = []
    n_features = len(hexgrid_features)

    with rasterio.open(baseline_path) as src_bl, rasterio.open(current_path) as src_cur:
        print(f"  Baseline: {src_bl.width}x{src_bl.height}, {src_bl.count} bands")
        print(f"  Current:  {src_cur.width}x{src_cur.height}, {src_cur.count} bands")

        for fi, feat in enumerate(hexgrid_features):
            if fi % 50000 == 0 and fi > 0:
                elapsed = time.time() - t0
                rate = fi / elapsed
                eta = (n_features - fi) / rate / 60
                print(f"    {fi:,}/{n_features:,} ({rate:.0f} hex/s, ETA {eta:.1f} min)")

            h3index = (feat.get("properties", {}).get("h3index")
                       or feat.get("properties", {}).get("h3_index")
                       or feat.get("id"))
            geom = shape(feat["geometry"])

            row = {"h3index": h3index}

            for band_idx, col_name, weight, invert in dynamic_bands:
                bl_val = zonal_stats_band(src_bl, band_idx, geom, src_bl.nodata)
                cur_val = zonal_stats_band(src_cur, band_idx, geom, src_cur.nodata)

                row[f'{col_name}_raw_current'] = cur_val
                row[f'{col_name}_raw_baseline'] = bl_val

                if not np.isnan(cur_val) and not np.isnan(bl_val):
                    row[f'{col_name}_raw_delta'] = cur_val - bl_val
                else:
                    row[f'{col_name}_raw_delta'] = np.nan

            results.append(row)

    df = pd.DataFrame(results)
    print(f"  Raw hexagons: {len(df):,}")

    # Merge fixed bands from original parquet
    if fixed_df is not None:
        df = df.set_index('h3index').join(fixed_df, how='left').reset_index()

    # Percentile rank normalisation for dynamic bands (current + baseline separately)
    for band_idx, col_name, weight, invert in dynamic_bands:
        for suffix in ('current', 'baseline'):
            raw_col = f'{col_name}_raw_{suffix}'
            out_col = f'{col_name}_{suffix}' if suffix == 'baseline' else col_name
            raw = df[raw_col].astype(float)
            if invert:
                raw = -raw
            df[out_col] = percentile_rank(raw).round(1)

        # Delta as difference of percentile-ranked values
        df[f'{col_name}_delta'] = (df[col_name] - df[f'{col_name}_baseline']).round(1)

    # Percentile rank for fixed bands (same as original)
    for col_name, weight, invert in fixed_bands:
        if col_name in df.columns:
            raw = df[col_name].astype(float)
            if invert:
                raw = -raw
            df[col_name] = percentile_rank(raw).round(1)

    # Compute composite scores (current + baseline)
    all_components = [(col, w, inv) for _, col, w, inv in dynamic_bands] + \
                     [(col, w, inv) for col, w, inv in fixed_bands]

    for score_suffix, col_suffix in [('score', ''), ('score_baseline', '_baseline')]:
        score = pd.Series(0.0, index=df.index)
        total_w = 0.0
        for col_name, weight, invert in all_components:
            src_col = f'{col_name}{col_suffix}' if col_suffix and f'{col_name}{col_suffix}' in df.columns else col_name
            if src_col in df.columns:
                valid = df[src_col].notna()
                score[valid] += df.loc[valid, src_col] * weight
                total_w += weight
        if total_w > 0:
            df[score_suffix] = (score / total_w).round(1)

    df['delta_score'] = (df['score'] - df['score_baseline']).round(1)

    # Select output columns
    out_cols = ['h3index', 'score', 'score_baseline', 'delta_score']
    for _, col_name, _, _ in dynamic_bands:
        out_cols.extend([col_name, f'{col_name}_baseline', f'{col_name}_delta'])
    for col_name, _, _ in fixed_bands:
        if col_name in df.columns:
            out_cols.append(col_name)

    # Drop raw columns and rows without scores
    result = df[[c for c in out_cols if c in df.columns]].dropna(subset=['score'])

    result.to_parquet(output_path, index=False)
    elapsed = time.time() - t0
    size_kb = os.path.getsize(output_path) / 1024

    print(f"  Output: {output_path}")
    print(f"  Rows: {len(result):,}, Size: {size_kb:.0f} KB")
    print(f"  Score current: mean={result['score'].mean():.1f}, median={result['score'].median():.1f}")
    print(f"  Score baseline: mean={result['score_baseline'].mean():.1f}")
    print(f"  Delta score: mean={result['delta_score'].mean():.2f}, "
          f"std={result['delta_score'].std():.2f}, "
          f"min={result['delta_score'].min():.1f}, max={result['delta_score'].max():.1f}")
    print(f"  Time: {elapsed:.0f}s")

    return len(result)


def main():
    parser = argparse.ArgumentParser(description="Process temporal rasters to H3 with deltas")
    parser.add_argument("--analysis", required=True, help="Analysis ID or 'all'")
    parser.add_argument("--input-dir", default=OUTPUT_DIR, help="Directory with GeoTIFFs")
    parser.add_argument("--territory", default="misiones",
                        choices=list(TERRITORY_CONFIGS.keys()),
                        help="Territory ID (defaults to misiones for backward compat)")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    output_prefix = territory['output_prefix']  # 'corrientes/', 'itapua_py/', or ''
    territory_dir = os.path.join(args.input_dir, output_prefix.rstrip("/")) if output_prefix else args.input_dir
    territory_out_dir = os.path.join(OUTPUT_DIR, output_prefix.rstrip("/")) if output_prefix else OUTPUT_DIR
    os.makedirs(territory_out_dir, exist_ok=True)

    if args.analysis == 'all':
        analyses = list(TEMPORAL_COMPONENTS.keys())
    else:
        analyses = [a.strip() for a in args.analysis.split(',')]

    hexgrid_path = resolve_hexgrid_path(output_prefix)
    print(f"Loading hexagon grid from {hexgrid_path}...")
    with open(hexgrid_path, 'r') as f:
        hexgrid = json.load(f)
    features = hexgrid['features']
    print(f"  {len(features):,} hexagons")

    t0 = time.time()
    results = {}

    for aid in analyses:
        if aid not in TEMPORAL_COMPONENTS:
            print(f"  SKIP {aid}: no temporal config")
            continue

        baseline_path = os.path.join(territory_dir, f"sat_{aid}_baseline.tif")
        current_path = os.path.join(territory_dir, f"sat_{aid}_current.tif")
        original_parquet = os.path.join(territory_dir, f"sat_{aid}.parquet")
        output_path = os.path.join(territory_out_dir, f"sat_{aid}.parquet")

        if not validate_raster(baseline_path):
            print(f"  SKIP {aid}: baseline raster invalid or not found")
            continue
        if not validate_raster(current_path):
            print(f"  SKIP {aid}: current raster invalid or not found")
            continue

        n = process_temporal(aid, baseline_path, current_path, original_parquet, features, output_path)
        results[aid] = n

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Processed {len(results)} analyses in {elapsed:.0f}s")
    for aid, n in results.items():
        print(f"    {aid}: {n:,} hexagons")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
