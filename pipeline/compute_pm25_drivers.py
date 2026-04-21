"""
Compute PM2.5 drivers layer for Spatia (sat_pm25_drivers.parquet).

Combines 25-year PM2.5 panel with SHAP-based driver attributions from
the spatial ML model (Model B). Produces temporal layer with baseline
(2001-2010) vs current (2013-2022) periods and four SHAP-derived
driver components (fire, climate, terrain, vegetation).

Input:
  - pm25_annual_panel.parquet   (H3 res-9, 1998-2022)
  - pm25_model_shap.parquet     (H3 res-7, Model B SHAP values)
  - h3_parent_crosswalk.parquet (res-9 -> res-7 mapping)

Output:
  - sat_pm25_drivers.parquet    (H3 res-9, ~320K hexagons)

Usage:
  python pipeline/compute_pm25_drivers.py
"""

import os
import sys
import time

import numpy as np
import pandas as pd

from config import OUTPUT_DIR, get_territory
from scoring import load_goalposts, score_with_goalposts

OUTPUT_PATH = os.path.join(OUTPUT_DIR, "sat_pm25_drivers.parquet")

BASELINE_YEARS = range(2001, 2011)  # 2001-2010
CURRENT_YEARS = range(2013, 2023)   # 2013-2022

# SHAP column -> driver group mapping
SHAP_GROUPS = {
    'fire': ['shap_burned_fraction', 'shap_fire_lag1', 'shap_fire_neighbors',
             'shap_fire_regional'],
    'climate': ['shap_temp_mean', 'shap_frost_days', 'shap_solar_radiation',
                'shap_dewpoint_mean', 'shap_total_mm'],
    'terrain': ['shap_elev_mean', 'shap_slope_mean', 'shap_hand_mean',
                'shap_twi_merit_mean',
                'shap_ph', 'shap_clay', 'shap_sand', 'shap_soc'],
    'vegetation': ['shap_mean_ndvi', 'shap_mean_lst_day', 'shap_mean_lst_night',
                   'shap_lst_amplitude', 'shap_mean_npp', 'shap_tree_cover',
                   'shap_delta_tree_cover',
                   'shap_frac_native_forest', 'shap_frac_plantation',
                   'shap_frac_agriculture', 'shap_frac_urban',
                   'shap_frac_pasture', 'shap_frac_mosaic', 'shap_frac_wetland'],
}

QUINTILE_LABELS = {
    1: 'Muy baja exposicion',
    2: 'Baja exposicion',
    3: 'Exposicion moderada',
    4: 'Alta exposicion',
    5: 'Muy alta exposicion',
}


def percentile_rank(series):
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result.round(1)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--territory", default="misiones", help="Territory ID (default: misiones)")
    parser.add_argument("--mode", choices=['comparable', 'local'], default='local',
                        help="comparable: goalpost normalization (cross-territory). local: percentile rank (default).")
    args = parser.parse_args()

    goalposts = load_goalposts() if args.mode == 'comparable' else None

    territory = get_territory(args.territory)
    t_prefix = territory['output_prefix']
    if t_prefix:
        t_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/'))
        output_path = os.path.join(t_dir, 'sat_pm25_drivers.parquet')
    else:
        t_dir = OUTPUT_DIR
        output_path = OUTPUT_PATH

    t0 = time.time()

    # -- 1. Load PM2.5 panel (res-9) and compute period means ---------------
    print("Loading PM2.5 annual panel (res-9)...")
    panel = pd.read_parquet(os.path.join(t_dir, "pm25_annual_panel.parquet"))
    print(f"  {len(panel):,} rows, {panel.h3index.nunique():,} hexagons")

    baseline = (panel[panel.year.isin(BASELINE_YEARS)]
                .groupby('h3index')['pm25'].mean()
                .rename('pm25_baseline'))
    current = (panel[panel.year.isin(CURRENT_YEARS)]
               .groupby('h3index')['pm25'].mean()
               .rename('pm25_current'))

    pm25 = pd.DataFrame({'pm25_baseline': baseline, 'pm25_current': current})
    pm25['pm25_delta'] = pm25['pm25_current'] - pm25['pm25_baseline']
    print(f"  Baseline ({list(BASELINE_YEARS)[0]}-{list(BASELINE_YEARS)[-1]}): "
          f"mean={pm25.pm25_baseline.mean():.2f}")
    print(f"  Current  ({list(CURRENT_YEARS)[0]}-{list(CURRENT_YEARS)[-1]}): "
          f"mean={pm25.pm25_current.mean():.2f}")
    print(f"  Delta: mean={pm25.pm25_delta.mean():.2f}")

    # Score: higher PM2.5 = higher score = worse exposure
    if args.mode == 'comparable' and goalposts:
        gp = goalposts['indicators'].get('c_pm25_mean', {'lo': 5, 'hi': 30})
        pm25['score'] = score_with_goalposts(pm25['pm25_current'], gp['lo'], gp['hi']).round(1)
        pm25['score_baseline'] = score_with_goalposts(pm25['pm25_baseline'], gp['lo'], gp['hi']).round(1)
    else:
        pm25['score'] = percentile_rank(pm25['pm25_current'])
        pm25['score_baseline'] = percentile_rank(pm25['pm25_baseline'])
    pm25['delta_score'] = (pm25['score'] - pm25['score_baseline']).round(1)

    # Raw values for display
    pm25['c_pm25_mean'] = pm25['pm25_current'].round(2)
    pm25['c_pm25_mean_baseline'] = pm25['pm25_baseline'].round(2)
    pm25['c_pm25_mean_delta'] = pm25['pm25_delta'].round(2)

    pm25 = pm25.reset_index()

    # -- 2. Load SHAP (res-7) and aggregate by group (Misiones-only, skip if missing) --
    shap_path = os.path.join(t_dir, "pm25_model_shap.parquet")
    has_shap = os.path.exists(shap_path)

    if has_shap:
        print("\nLoading SHAP values (res-7, Model B)...")
        shap = pd.read_parquet(shap_path)
        shap_cols = [c for c in shap.columns if c.startswith('shap_')]
        print(f"  {len(shap):,} rows, {len(shap_cols)} SHAP columns")

        hex_shap = shap.groupby('h3index')[shap_cols].apply(
            lambda g: g.abs().mean()
        ).reset_index()

        for group, cols in SHAP_GROUPS.items():
            available = [c for c in cols if c in hex_shap.columns]
            if available:
                hex_shap[f'raw_{group}'] = hex_shap[available].sum(axis=1)
            else:
                hex_shap[f'raw_{group}'] = 0.0

        print(f"  SHAP group means: " + ", ".join(
            f"{g}={hex_shap[f'raw_{g}'].mean():.4f}" for g in SHAP_GROUPS
        ))

        # -- 3. Map res-7 SHAP -> res-9 via parent crosswalk ----------------
        print("\nMapping SHAP (res-7) -> res-9 via parent crosswalk...")
        parents = pd.read_parquet(
            os.path.join(t_dir, "h3_parent_crosswalk.parquet")
        )[['h3index', 'h3_res7']]

        shap_cols_keep = ['h3index'] + [f'raw_{g}' for g in SHAP_GROUPS]
        hex_shap_slim = hex_shap[shap_cols_keep].rename(columns={'h3index': 'h3_res7'})

        res9_shap = parents.merge(hex_shap_slim, on='h3_res7', how='left')
        raw_total = sum(res9_shap[f'raw_{g}'] for g in SHAP_GROUPS)
        raw_total = raw_total.replace(0, np.nan)
        for group in SHAP_GROUPS:
            res9_shap[f'c_{group}'] = (res9_shap[f'raw_{group}'] / raw_total * 100).round(1)
        res9_shap = res9_shap[['h3index'] + [f'c_{group}' for group in SHAP_GROUPS]]
        print(f"  Mapped {len(res9_shap):,} res-9 hexagons")
    else:
        print(f"\n  SKIP SHAP: pm25_model_shap.parquet not found in {t_dir}")
        print("  Driver components (c_fire/climate/terrain/vegetation) will be NaN")
        res9_shap = pm25[['h3index']].copy()
        for group in SHAP_GROUPS:
            res9_shap[f'c_{group}'] = np.nan

    # -- 4. Merge PM2.5 + SHAP + typology ----------------------------------
    print("\nMerging...")
    result = pm25.merge(res9_shap, on='h3index', how='left' if not has_shap else 'inner')

    # Typology on current score — absolute quintiles on 0-100 scale
    result = result.dropna(subset=['score'])
    bins = [0, 20, 40, 60, 80, 100]
    result['type'] = pd.cut(result['score'], bins=bins, labels=[1, 2, 3, 4, 5],
                            include_lowest=True).astype(int)
    result['type_label'] = result['type'].map(QUINTILE_LABELS)

    # Select final columns
    out_cols = [
        'h3index', 'score', 'score_baseline', 'delta_score',
        'c_pm25_mean', 'c_pm25_mean_baseline', 'c_pm25_mean_delta',
        'c_fire', 'c_climate', 'c_terrain', 'c_vegetation',
        'type', 'type_label',
    ]
    result = result[out_cols]

    # -- 5. Summary and save ------------------------------------------------
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Rows: {len(result):,}")
    print(f"  Score: mean={result.score.mean():.1f}, "
          f"std={result.score.std():.1f}")
    print(f"  PM2.5 current: mean={result.c_pm25_mean.mean():.2f}, "
          f"range={result.c_pm25_mean.min():.2f}-{result.c_pm25_mean.max():.2f}")
    print(f"  PM2.5 baseline: mean={result.c_pm25_mean_baseline.mean():.2f}")
    print(f"  Delta PM2.5: mean={result.c_pm25_mean_delta.mean():.2f}")
    if has_shap:
        print(f"  Driver components (mean percentile):")
        for g in SHAP_GROUPS:
            print(f"    c_{g}: {result[f'c_{g}'].mean():.1f}")
    print(f"  Types: {result.type.value_counts().sort_index().to_dict()}")
    print(f"\n  Built in {elapsed:.0f}s")

    os.makedirs(t_dir, exist_ok=True)
    result.to_parquet(output_path, index=False)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Saved: {output_path} ({size_mb:.1f} MB)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
