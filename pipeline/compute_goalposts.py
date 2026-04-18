"""
Compute and lock Tier 2 goalpost values (P2/P98) from pooled territory data.

Run once after adding a new territory or re-generating source parquets.
Overwrites only Tier 2 lo/hi entries in goalposts.json; Tier 1 (physical scale)
entries are never modified. Also re-runs PCA variable selection on pooled
goalpost-normalized data and updates pca_variable_selection.

Usage:
    python pipeline/compute_goalposts.py [--dry-run]
    python pipeline/compute_goalposts.py --dry-run   # print changes, don't write
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from config import TERRITORY_CONFIGS, OUTPUT_DIR
from scoring import score_with_goalposts, select_variables

GOALPOSTS_PATH = os.path.join(os.path.dirname(__file__), 'config', 'goalposts.json')

# Comparable analyses: parquet filename stem → list of c_* columns to pool
# Maps sat_*.parquet columns that appear in goalposts.json indicators
COMPARABLE_PARQUETS = {
    'sat_environmental_risk':    ['c_fire', 'c_deforest', 'c_thermal_amp', 'c_slope', 'c_hand'],
    'sat_climate_comfort':       ['c_heat_day', 'c_heat_night', 'c_precipitation', 'c_frost', 'c_water_stress'],
    'sat_green_capital':         ['c_ndvi', 'c_treecover', 'c_npp', 'c_lai', 'c_vcf'],
    'sat_change_pressure':       ['c_viirs_trend', 'c_ghsl_change', 'c_hansen_loss', 'c_ndvi_trend', 'c_fire_count'],
    'sat_location_value':        ['c_access_20k', 'c_healthcare', 'c_nightlights', 'c_slope', 'c_road_dist'],
    'sat_agri_potential':        ['c_soc', 'c_ph_optimal', 'c_clay', 'c_precipitation', 'c_gdd'],
    'sat_forest_health':         ['c_ndvi_trend', 'c_loss_ratio', 'c_gpp', 'c_et'],
    'sat_carbon_stock':          ['c_agb_cci', 'c_total_carbon', 'c_soc', 'c_net_flux'],
    'sat_productive_activity':   ['c_viirs', 'c_npp', 'c_ndvi', 'c_built', 'c_forest_loss', 'c_lst'],
    'sat_deforestation_dynamics':['c_loss_rate', 'c_cumulative'],
    'sat_pm25_drivers':          ['c_pm25_mean', 'c_fire', 'c_climate'],
}

# Mapping from parquet stem to analysis ID (for pca_variable_selection key)
PARQUET_TO_ANALYSIS = {k: k.replace('sat_', '') for k in COMPARABLE_PARQUETS}

# PCA variable selection analysis-to-component mapping (for re-validation)
ANALYSIS_COMPONENTS = {
    'environmental_risk':     ['c_fire', 'c_deforest', 'c_thermal_amp', 'c_slope', 'c_hand'],
    'climate_comfort':        ['c_heat_day', 'c_heat_night', 'c_precipitation', 'c_frost', 'c_water_stress'],
    'green_capital':          ['c_ndvi', 'c_treecover', 'c_npp', 'c_lai', 'c_vcf'],
    'change_pressure':        ['c_viirs_trend', 'c_ghsl_change', 'c_hansen_loss', 'c_ndvi_trend', 'c_fire_count'],
    'location_value':         ['c_access_20k', 'c_healthcare', 'c_nightlights', 'c_slope', 'c_road_dist'],
    'agri_potential':         ['c_soc', 'c_ph_optimal', 'c_clay', 'c_precipitation', 'c_gdd'],
    'forest_health':          ['c_ndvi_trend', 'c_loss_ratio', 'c_gpp', 'c_et'],
    'carbon_stock':           ['c_agb_cci', 'c_total_carbon', 'c_soc', 'c_net_flux'],
    'productive_activity':    ['c_viirs', 'c_npp', 'c_ndvi', 'c_built', 'c_forest_loss', 'c_lst'],
    'deforestation_dynamics': ['c_loss_rate', 'c_cumulative'],
    'pm25_drivers':           ['c_pm25_mean', 'c_fire', 'c_climate'],
}


def get_output_dirs() -> list[str]:
    """Return all territory output directories that exist."""
    dirs = []
    for tid, cfg in TERRITORY_CONFIGS.items():
        prefix = cfg.get('output_prefix', '')
        if prefix:
            d = os.path.join(OUTPUT_DIR, prefix.rstrip('/'))
        else:
            d = OUTPUT_DIR
        if os.path.isdir(d):
            dirs.append(d)
        else:
            print(f"  [WARN] Output dir not found for {tid}: {d}")
    return dirs


def pool_indicator_data(output_dirs: list[str]) -> dict[str, pd.Series]:
    """Pool raw c_* columns from all territories for each comparable parquet."""
    pooled: dict[str, list[pd.Series]] = {}

    for parquet_stem, cols in COMPARABLE_PARQUETS.items():
        filename = f"{parquet_stem}.parquet"
        series_list: dict[str, list] = {c: [] for c in cols}

        for d in output_dirs:
            path = os.path.join(d, filename)
            if not os.path.exists(path):
                continue
            try:
                df = pd.read_parquet(path, columns=[c for c in cols if c in
                                     pd.read_parquet(path, columns=['h3index']).columns or True])
                # Re-read with available cols only
                available = [c for c in cols if c in pd.read_parquet(path).columns]
                if not available:
                    continue
                df = pd.read_parquet(path, columns=available)
                for col in available:
                    series_list[col].append(df[col].dropna())
                print(f"  Loaded {filename} from {os.path.basename(d)}: "
                      f"{len(df):,} rows, cols: {available}")
            except Exception as e:
                print(f"  [WARN] Could not read {path}: {e}")

        for col, series_parts in series_list.items():
            if series_parts:
                combined = pd.concat(series_parts, ignore_index=True)
                pooled.setdefault(col, []).append(combined)

    # Flatten: each indicator gets one pooled Series
    result = {}
    for col, parts in pooled.items():
        result[col] = pd.concat(parts, ignore_index=True) if parts else pd.Series(dtype=float)
    return result


def compute_tier2_goalposts(pooled: dict[str, pd.Series]) -> dict[str, tuple[float, float]]:
    """Compute P2/P98 for each Tier 2 indicator from pooled data."""
    new_bounds: dict[str, tuple[float, float]] = {}
    for col, series in pooled.items():
        if series.empty:
            continue
        lo = float(series.quantile(0.02))
        hi = float(series.quantile(0.98))
        if hi > lo:
            new_bounds[col] = (lo, hi)
    return new_bounds


def rerun_pca_selection(pooled: dict[str, pd.Series],
                        goalposts: dict) -> dict[str, list[str]]:
    """Re-run variable selection on pooled goalpost-normalized data."""
    new_selections: dict[str, list[str]] = {}

    for analysis_id, comp_cols in ANALYSIS_COMPONENTS.items():
        available = [c for c in comp_cols if c in pooled and not pooled[c].empty]
        if len(available) < 2:
            print(f"  [SKIP] {analysis_id}: insufficient pooled data for PCA")
            continue

        # Align all series to common index
        dfs = {}
        for c in available:
            s = pooled[c].copy()
            s.index = range(len(s))
            dfs[c] = s

        min_len = min(len(v) for v in dfs.values())
        df = pd.DataFrame({c: dfs[c].iloc[:min_len].values for c in available})

        # Normalize with current goalposts before running variable selection
        df_norm = pd.DataFrame()
        for c in available:
            if c in goalposts['indicators']:
                gp = goalposts['indicators'][c]
                df_norm[c] = score_with_goalposts(df[c], gp['lo'], gp['hi'],
                                                   invert=gp.get('invert', False))
            else:
                df_norm[c] = df[c]

        retained = select_variables(df_norm.dropna(), available, threshold=0.70)
        new_selections[analysis_id] = retained
        dropped = [c for c in available if c not in retained]
        if dropped:
            print(f"  {analysis_id}: retained={retained}, dropped={dropped}")
        else:
            print(f"  {analysis_id}: all {len(retained)} retained")

    return new_selections


def main():
    parser = argparse.ArgumentParser(description="Compute Tier 2 goalpost P2/P98 from pooled territory data")
    parser.add_argument('--dry-run', action='store_true',
                        help="Print computed bounds but do not write goalposts.json")
    args = parser.parse_args()

    print("=" * 60)
    print("  Compute Goalposts v1.0")
    print("=" * 60)

    # Load existing goalposts
    with open(GOALPOSTS_PATH) as f:
        goalposts = json.load(f)

    # Discover output directories
    print("\nDiscovering territory output directories...")
    output_dirs = get_output_dirs()
    if not output_dirs:
        print("ERROR: No territory output directories found.")
        return 1
    for d in output_dirs:
        print(f"  {d}")

    # Pool raw indicator data
    print("\nPooling indicator data across territories...")
    pooled = pool_indicator_data(output_dirs)
    total_rows = sum(len(s) for s in pooled.values())
    print(f"  Pooled {len(pooled)} indicators, {total_rows:,} total values")

    # Compute new Tier 2 bounds
    print("\nComputing P2/P98 for Tier 2 indicators...")
    new_bounds = compute_tier2_goalposts(pooled)

    # Print diff
    changed = []
    for col, (lo_new, hi_new) in new_bounds.items():
        if col not in goalposts['indicators']:
            continue
        entry = goalposts['indicators'][col]
        if entry.get('tier', 2) == 1:
            continue  # Never touch Tier 1
        lo_old = entry['lo']
        hi_old = entry['hi']
        if abs(lo_new - lo_old) > 0.01 or abs(hi_new - hi_old) > 0.01:
            changed.append((col, lo_old, hi_old, lo_new, hi_new))
            print(f"  {col}: lo {lo_old:.3f}->{lo_new:.3f}, hi {hi_old:.3f}->{hi_new:.3f}")
        else:
            print(f"  {col}: unchanged ({lo_old:.3f}, {hi_old:.3f})")

    # Re-run PCA variable selection on pooled normalized data
    print("\nRe-running PCA variable selection on pooled data...")
    new_pca = rerun_pca_selection(pooled, goalposts)

    if args.dry_run:
        print(f"\n[DRY RUN] Would update {len(changed)} Tier 2 entries and "
              f"{len(new_pca)} PCA selections. Not writing.")
        return 0

    # Apply updates to goalposts
    for col, (lo_new, hi_new) in new_bounds.items():
        if col in goalposts['indicators'] and goalposts['indicators'][col].get('tier', 2) != 1:
            goalposts['indicators'][col]['lo'] = round(lo_new, 4)
            goalposts['indicators'][col]['hi'] = round(hi_new, 4)

    # Update PCA selections
    for analysis_id, retained in new_pca.items():
        goalposts['pca_variable_selection'][analysis_id] = retained

    # Write back
    with open(GOALPOSTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(goalposts, f, indent=2, ensure_ascii=False)

    print(f"\nUpdated goalposts.json: {len(changed)} Tier 2 entries changed, "
          f"{len(new_pca)} PCA selections updated.")
    print(f"Path: {GOALPOSTS_PATH}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
