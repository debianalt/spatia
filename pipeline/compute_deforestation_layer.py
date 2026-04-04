"""
Compute deforestation dynamics layer for Spatia.

Shows observed deforestation patterns (not predictions):
- Baseline period (2001-2010) vs current (2015-2024) loss rates
- Cumulative loss since 2001
- Acceleration/deceleration
- Driver attribution (drought, contagion, accessibility) from v3 SHAP

Data: Hansen Global Forest Change annual loss by radio (2001-2024)
Output: sat_deforestation_dynamics.parquet (H3 res-9)

Usage:
  python pipeline/compute_deforestation_layer.py
"""

import os
import sys
import time

import numpy as np
import pandas as pd
import psycopg2

from config import OUTPUT_DIR

DB = dict(dbname='ndvi_misiones', host='localhost', user='postgres', password='')
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "sat_deforestation_dynamics.parquet")

BASELINE_YEARS = range(2001, 2011)  # 2001-2010
CURRENT_YEARS = range(2015, 2025)   # 2015-2024


def percentile_rank(series):
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result.round(1)


def main():
    t0 = time.time()
    conn = psycopg2.connect(**DB)

    # --- Hansen annual loss by radio --------------------------------------
    print("Loading Hansen annual loss...")
    hl = pd.read_sql("SELECT year, redcode, loss_fraction FROM hansen_loss_year", conn)
    print(f"  {len(hl):,} obs ({hl.redcode.nunique()} radios x {hl.year.nunique()} years)")

    # Baseline and current period means
    baseline = hl[hl.year.isin(BASELINE_YEARS)].groupby('redcode')['loss_fraction'].mean()
    current = hl[hl.year.isin(CURRENT_YEARS)].groupby('redcode')['loss_fraction'].mean()
    cumul = hl.groupby('redcode')['loss_fraction'].sum()
    peak_year = hl.loc[hl.groupby('redcode')['loss_fraction'].idxmax()].set_index('redcode')['year']

    radio = pd.DataFrame({
        'loss_baseline': baseline,
        'loss_current': current,
        'loss_cumulative': cumul,
        'peak_loss_year': peak_year,
    }).reset_index()

    radio['loss_delta'] = radio['loss_current'] - radio['loss_baseline']
    radio['accelerating'] = (radio['loss_delta'] > 0).astype(int)

    print(f"  Baseline: {radio.loss_baseline.mean()*100:.3f}%/yr")
    print(f"  Current:  {radio.loss_current.mean()*100:.3f}%/yr")
    print(f"  Accelerating: {radio.accelerating.sum()} ({radio.accelerating.mean()*100:.1f}%)")

    # --- SHAP-based driver attribution (from v3 model) --------------------
    shap_path = os.path.join(OUTPUT_DIR, "deforestation_v3_shap.parquet")
    if os.path.exists(shap_path):
        print("\nLoading SHAP attributions from v3 model...")
        shap = pd.read_parquet(shap_path)

        # Group SHAP by driver category (mean |SHAP| per radio across years)
        drought_cols = [c for c in shap.columns if c.startswith('shap_') and
                        any(v in c for v in ['pdsi', 'water_deficit', 'vpd', 'soil_moisture', 'precip'])]
        landscape_cols = [c for c in shap.columns if 'neighbors' in c or 'acceleration' in c]
        access_cols = [c for c in shap.columns if any(v in c for v in ['dist_primary', 'road_density', 'travel'])]
        fire_cols = [c for c in shap.columns if 'burned' in c or 'burn_count' in c]

        for name, cols in [('shap_drought', drought_cols), ('shap_landscape', landscape_cols),
                            ('shap_access', access_cols), ('shap_fire', fire_cols)]:
            if cols:
                vals = shap.groupby('redcode')[cols].apply(lambda g: g.abs().sum(axis=1).mean())
                radio = radio.merge(vals.rename(name).reset_index(), on='redcode', how='left')

    # --- Percentile scores ------------------------------------------------
    # Score = current loss rate percentiled (higher = more deforestation)
    radio['score'] = percentile_rank(radio['loss_current'])
    radio['score_baseline'] = percentile_rank(radio['loss_baseline'])
    radio['delta_score'] = (radio['score'] - radio['score_baseline']).round(1)

    # Raw values for display (convert to %/yr)
    radio['c_loss_rate'] = (radio['loss_current'] * 100).round(3)
    radio['c_loss_rate_baseline'] = (radio['loss_baseline'] * 100).round(3)
    radio['c_loss_rate_delta'] = (radio['loss_delta'] * 100).round(3)
    radio['c_cumulative'] = (radio['loss_cumulative'] * 100).round(1)

    # SHAP drivers percentiled
    for col in ['shap_drought', 'shap_landscape', 'shap_access', 'shap_fire']:
        if col in radio.columns:
            radio[f'c_{col.replace("shap_", "")}'] = percentile_rank(radio[col])

    # Type labels
    try:
        radio['type'] = pd.qcut(radio['score'], 4, labels=[1, 2, 3, 4]).astype(int)
    except ValueError:
        radio['type'] = pd.cut(radio['score'], bins=[0, 25, 50, 75, 100],
                                labels=[1, 2, 3, 4], include_lowest=True).astype(int)
    type_labels = {1: 'Baja presion', 2: 'Presion moderada',
                   3: 'Alta presion', 4: 'Presion critica'}
    radio['type_label'] = radio['type'].map(type_labels)

    # --- Map radio -> H3 res-9 via crosswalk ------------------------------
    print("\nMapping radio -> H3 res-9...")
    xw = pd.read_parquet(os.path.join(OUTPUT_DIR, "h3_radio_crosswalk_areal.parquet"))

    # For each H3 hex, use dominant radio (highest weight)
    dominant = xw.sort_values('weight', ascending=False).drop_duplicates('h3index')

    out_cols = ['score', 'score_baseline', 'delta_score',
                'c_loss_rate', 'c_loss_rate_baseline', 'c_loss_rate_delta',
                'c_cumulative', 'type', 'type_label']
    # Add SHAP driver columns if available
    for c in ['c_drought', 'c_landscape', 'c_access', 'c_fire']:
        if c in radio.columns:
            out_cols.append(c)

    result = dominant[['h3index', 'redcode']].merge(
        radio[['redcode'] + out_cols], on='redcode', how='left')
    result = result.drop(columns=['redcode']).dropna(subset=['score'])

    # --- Summary ----------------------------------------------------------
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Rows: {len(result):,}")
    print(f"  Loss rate current: mean={result.c_loss_rate.mean():.3f}%/yr")
    print(f"  Loss rate baseline: mean={result.c_loss_rate_baseline.mean():.3f}%/yr")
    print(f"  Delta: mean={result.c_loss_rate_delta.mean():.3f}%/yr")
    print(f"  Cumulative: mean={result.c_cumulative.mean():.1f}%")
    print(f"  Types: {result.type.value_counts().sort_index().to_dict()}")
    print(f"  Built in {elapsed:.0f}s")

    result.to_parquet(OUTPUT_PATH, index=False)
    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"  Saved: {OUTPUT_PATH} ({size_mb:.1f} MB)")
    print(f"{'=' * 60}")

    conn.close()


if __name__ == "__main__":
    main()
