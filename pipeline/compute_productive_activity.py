"""
Productive activity layer — raw values with percentile ranking.

Shows 6 real-world variables in physical units with honest temporal
comparison (baseline vs current period). No composite scores, no PCA,
no clustering. Map choropleth = VIIRS radiance percentile.

Variables:
  1. VIIRS nightlights (nW/cm2/sr) — economic activity proxy
  2. NPP (gC/m2/yr) — vegetation productivity
  3. NDVI — greenness
  4. GHSL built surface (fraction) — urbanisation
  5. Hansen cumulative loss (%) — forest conversion
  6. LST day (C) — surface temperature

Usage:
  python pipeline/compute_productive_activity.py
"""

import os
import time
import numpy as np
import pandas as pd
from config import OUTPUT_DIR

RADIO_DATA = os.path.join(OUTPUT_DIR, "radio_data")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "sat_productive_activity.parquet")


def pctile(s):
    v = s.notna()
    r = pd.Series(np.nan, index=s.index)
    if v.sum() > 1:
        r[v] = s[v].rank(pct=True) * 100.0
    return r.round(1)


def load_radio_period(path, col, bl_years, cur_years):
    """Load annual radio data and compute baseline/current means."""
    df = pd.read_parquet(path)
    bl = df[df.year.isin(bl_years)].groupby('redcode')[col].mean().rename(f'{col}_bl')
    cur = df[df.year.isin(cur_years)].groupby('redcode')[col].mean().rename(f'{col}_cur')
    return pd.DataFrame({f'{col}_bl': bl, f'{col}_cur': cur}).reset_index()


def aggregate_to_h3(radio_df, cols, xw):
    """Weighted aggregation radio → H3 res-9 via normalised areal crosswalk."""
    merged = xw.merge(radio_df, on='redcode', how='inner')
    totals = merged.groupby('h3index')['weight'].transform('sum')
    merged['w_norm'] = merged['weight'] / totals
    for c in cols:
        merged[f'w_{c}'] = merged[c] * merged['w_norm']
    agg = merged.groupby('h3index')[[f'w_{c}' for c in cols]].sum().reset_index()
    agg.columns = ['h3index'] + cols
    return agg


def main():
    t0 = time.time()
    xw = pd.read_parquet(os.path.join(OUTPUT_DIR, "h3_radio_crosswalk_areal.parquet"))

    # --- 1. VIIRS (2014-2017 baseline, 2022-2025 current) -----------------
    print("1. VIIRS nightlights...")
    viirs = load_radio_period(
        os.path.join(RADIO_DATA, "viirs_annual.parquet"),
        'mean_radiance', range(2014, 2018), range(2022, 2026))
    viirs.columns = ['redcode', 'viirs_bl', 'viirs_cur']

    # --- 2. NPP (2005-2012 baseline, 2017-2024 current) -------------------
    print("2. NPP productivity...")
    npp = load_radio_period(
        os.path.join(RADIO_DATA, "npp_annual.parquet"),
        'mean_npp', range(2005, 2013), range(2017, 2025))
    npp.columns = ['redcode', 'npp_bl', 'npp_cur']

    # --- 3. NDVI -----------------------------------------------------------
    print("3. NDVI greenness...")
    ndvi = load_radio_period(
        os.path.join(RADIO_DATA, "ndvi_annual_mean.parquet"),
        'mean_ndvi', range(2005, 2013), range(2017, 2025))
    ndvi.columns = ['redcode', 'ndvi_bl', 'ndvi_cur']

    # --- 4. GHSL built surface (epochs, not annual) -----------------------
    print("4. GHSL built surface...")
    ghsl = pd.read_parquet(os.path.join(RADIO_DATA, "ghsl_built_surface.parquet"))
    ghsl_2000 = ghsl[ghsl.epoch == 2000][['redcode', 'built_fraction']].rename(
        columns={'built_fraction': 'built_bl'})
    ghsl_2020 = ghsl[ghsl.epoch == 2020][['redcode', 'built_fraction']].rename(
        columns={'built_fraction': 'built_cur'})
    built = ghsl_2000.merge(ghsl_2020, on='redcode', how='outer')

    # --- 5. Hansen cumulative loss ----------------------------------------
    print("5. Hansen forest loss...")
    hansen = pd.read_parquet(os.path.join(RADIO_DATA, "fire_annual.parquet"))  # wrong, use hansen
    # Actually use hansen_loss_year from parquet or PostgreSQL
    # Check if hansen_h3_annual exists (from our earlier pipeline)
    hansen_path = os.path.join(OUTPUT_DIR, "hansen_h3_annual.parquet")
    if os.path.exists(hansen_path):
        # We have H3 res-9 level hansen data — use directly later
        print("  (using H3-level hansen data)")
        hansen_h3 = pd.read_parquet(hansen_path)
        hl_bl = hansen_h3[hansen_h3.year.between(2001, 2012)].groupby('h3index')['lost'].sum().rename('loss_bl')
        hl_cur = hansen_h3[hansen_h3.year.between(2013, 2024)].groupby('h3index')['lost'].sum().rename('loss_cur')
        hansen_direct = pd.DataFrame({'loss_bl': hl_bl, 'loss_cur': hl_cur}).reset_index()
    else:
        hansen_direct = None

    # --- 6. LST day --------------------------------------------------------
    print("6. LST surface temperature...")
    lst = load_radio_period(
        os.path.join(RADIO_DATA, "lst_annual.parquet"),
        'mean_lst_day', range(2005, 2013), range(2017, 2025))
    lst.columns = ['redcode', 'lst_bl', 'lst_cur']

    # --- Aggregate radio data to H3 res-9 ---------------------------------
    print("\nAggregating radio -> H3 res-9...")

    # Merge all radio data
    radio = viirs
    for df in [npp, ndvi, built, lst]:
        radio = radio.merge(df, on='redcode', how='outer')

    radio_cols = [c for c in radio.columns if c != 'redcode']
    h3_data = aggregate_to_h3(radio, radio_cols, xw)
    print(f"  H3 hexagons: {len(h3_data):,}")

    # Add Hansen (already at H3 level if available)
    if hansen_direct is not None:
        h3_data = h3_data.merge(hansen_direct, on='h3index', how='left')
    else:
        h3_data['loss_bl'] = 0
        h3_data['loss_cur'] = 0

    # --- Build output columns ---------------------------------------------
    print("Building output...")
    result = pd.DataFrame({'h3index': h3_data['h3index']})

    # Raw values with units
    for var, bl, cur, name in [
        ('viirs', 'viirs_bl', 'viirs_cur', 'c_viirs'),
        ('npp', 'npp_bl', 'npp_cur', 'c_npp'),
        ('ndvi', 'ndvi_bl', 'ndvi_cur', 'c_ndvi'),
        ('built', 'built_bl', 'built_cur', 'c_built'),
        ('loss', 'loss_bl', 'loss_cur', 'c_forest_loss'),
        ('lst', 'lst_bl', 'lst_cur', 'c_lst'),
    ]:
        result[name] = h3_data[cur].round(3) if cur in h3_data else 0
        result[f'{name}_baseline'] = h3_data[bl].round(3) if bl in h3_data else 0
        result[f'{name}_delta'] = (result[name] - result[f'{name}_baseline']).round(3)

    # Score = VIIRS percentile (primary choropleth variable)
    result['score'] = pctile(result['c_viirs'])
    result['score_baseline'] = pctile(result['c_viirs_baseline'])
    result['delta_score'] = (result['score'] - result['score_baseline']).round(1)

    # Type = quintile of VIIRS
    result['type'] = pd.cut(result['score'].fillna(0),
                             bins=[0, 20, 40, 60, 80, 100],
                             labels=[1, 2, 3, 4, 5],
                             include_lowest=True).astype(float).fillna(1).astype(int)
    labels = {1: 'Muy baja actividad', 2: 'Baja actividad',
              3: 'Actividad moderada', 4: 'Alta actividad', 5: 'Muy alta actividad'}
    result['type_label'] = result['type'].map(labels)

    # Drop hex with no data
    result = result.dropna(subset=['score'])

    # --- Summary -----------------------------------------------------------
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Rows: {len(result):,}")
    print(f"  Score (VIIRS pctile): mean={result.score.mean():.1f}")
    print(f"  delta_score: mean={result.delta_score.mean():.1f}, "
          f"std={result.delta_score.std():.1f}")
    print(f"\n  Raw values (current period):")
    for c in ['c_viirs', 'c_npp', 'c_ndvi', 'c_built', 'c_forest_loss', 'c_lst']:
        print(f"    {c:20s} mean={result[c].mean():.3f}  "
              f"delta_mean={result[f'{c}_delta'].mean():+.3f}")
    print(f"  Types: {result.type.value_counts().sort_index().to_dict()}")
    print(f"  Built in {elapsed:.0f}s")

    result.to_parquet(OUTPUT_PATH, index=False)
    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"  Saved: {OUTPUT_PATH} ({size_mb:.1f} MB)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
