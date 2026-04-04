"""
Generate predictive PM2.5 layer with fire scenarios for Spatia.

Trains Model B (no lag) on full data and predicts PM2.5 in ug/m3
for three fire scenarios: actual (2022), fire-high (P90 year),
and fire-low (P10 year). Maps predictions to H3 res-9 and adds
WHO exceedance bands.

Output:
  sat_pm25_predicted.parquet  (H3 res-9, ~320K hexagons)

Usage:
  python pipeline/predict_pm25_scenarios.py
"""

import os
import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

from config import OUTPUT_DIR

OUTPUT_PATH = os.path.join(OUTPUT_DIR, "sat_pm25_predicted.parquet")

# Model B features (no autoregressive lag)
FEATURE_GROUPS = {
    "fire": ["burned_fraction", "fire_lag1", "fire_neighbors", "fire_regional"],
    "climate": ["temp_mean", "frost_days", "solar_radiation",
                "dewpoint_mean", "total_mm"],
    "vegetation": ["mean_ndvi", "mean_lst_day", "mean_lst_night",
                    "lst_amplitude", "mean_npp", "tree_cover",
                    "delta_tree_cover"],
    "land_use": ["frac_native_forest", "frac_plantation", "frac_agriculture",
                 "frac_urban", "frac_pasture", "frac_mosaic", "frac_wetland"],
    "terrain": ["elev_mean", "slope_mean", "hand_mean", "twi_merit_mean"],
    "soil": ["ph", "clay", "sand", "soc"],
}

WHO_GUIDELINE = 5.0
WHO_IT4 = 10.0
WHO_IT3 = 15.0

WHO_LABELS = {
    1: 'Below IT-4 (<10 ug/m3)',
    2: 'IT-4 to IT-3 (10-15 ug/m3)',
    3: 'Above IT-3 (>15 ug/m3)',
}

WHO_LABELS_ES = {
    1: 'Por debajo de OI-4 (<10 ug/m3)',
    2: 'Entre OI-4 y OI-3 (10-15 ug/m3)',
    3: 'Por encima de OI-3 (>15 ug/m3)',
}


def percentile_rank(series):
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result.round(1)


def who_band(pm25):
    if pm25 < WHO_IT4:
        return 1
    elif pm25 < WHO_IT3:
        return 2
    else:
        return 3


def main():
    t0 = time.time()

    # -- 1. Load panel and train Model B on full data ----------------------
    print("Loading panel...")
    panel = pd.read_parquet(os.path.join(OUTPUT_DIR, "pm25_model_panel.parquet"))

    features = []
    for group_feats in FEATURE_GROUPS.values():
        features.extend(group_feats)
    features = [f for f in features if f in panel.columns]

    df = panel.dropna(subset=["pm25"] + features).copy()
    X = df[features]
    y = df["pm25"].values
    print(f"  {len(df):,} obs, {len(features)} features")

    print("Training Model B on full data...")
    model = lgb.LGBMRegressor(
        n_estimators=500, max_depth=8, learning_rate=0.05,
        num_leaves=63, min_child_samples=20,
        subsample=0.8, colsample_bytree=0.8,
        reg_alpha=0.1, reg_lambda=0.1,
        n_jobs=-1, random_state=42, verbose=-1,
    )
    model.fit(X, y)
    print(f"  In-sample R2: {model.score(X, y):.4f}")

    # -- 2. Prepare 2022 features as base for prediction -------------------
    print("\nPreparing 2022 features...")
    latest = df[df.year == 2022].copy()
    if len(latest) == 0:
        latest = df[df.year == df.year.max()].copy()
    print(f"  {len(latest):,} hexagons for year {latest.year.iloc[0]}")

    # Compute fire_regional quantiles from full history
    fire_reg_by_year = df.groupby('year')['fire_regional'].first()
    fire_p10 = fire_reg_by_year.quantile(0.10)
    fire_p50 = fire_reg_by_year.quantile(0.50)
    fire_p90 = fire_reg_by_year.quantile(0.90)
    print(f"  fire_regional quantiles: P10={fire_p10:.6f}, P50={fire_p50:.6f}, P90={fire_p90:.6f}")

    # -- 3. Predict for 3 scenarios ----------------------------------------
    scenarios = {}

    # Scenario 1: Actual (2022 conditions)
    X_actual = latest[features]
    scenarios['actual'] = model.predict(X_actual)
    print(f"\n  Actual: mean={scenarios['actual'].mean():.2f}, "
          f"range={scenarios['actual'].min():.2f}-{scenarios['actual'].max():.2f}")

    # Scenario 2: Fire-high (P90 year — simulates 2007-type event)
    X_fire_high = latest[features].copy()
    X_fire_high['fire_regional'] = fire_p90
    scenarios['fire_high'] = model.predict(X_fire_high)
    print(f"  Fire-high (P90): mean={scenarios['fire_high'].mean():.2f}, "
          f"range={scenarios['fire_high'].min():.2f}-{scenarios['fire_high'].max():.2f}")

    # Scenario 3: Fire-low (P10 year — simulates clean year)
    X_fire_low = latest[features].copy()
    X_fire_low['fire_regional'] = fire_p10
    scenarios['fire_low'] = model.predict(X_fire_low)
    print(f"  Fire-low (P10): mean={scenarios['fire_low'].mean():.2f}, "
          f"range={scenarios['fire_low'].min():.2f}-{scenarios['fire_low'].max():.2f}")

    # -- 4. Build result DataFrame at res-7 --------------------------------
    result_r7 = pd.DataFrame({
        'h3index': latest['h3index'].values,
        'pm25_actual': scenarios['actual'],
        'pm25_fire_high': scenarios['fire_high'],
        'pm25_fire_low': scenarios['fire_low'],
    })

    # -- 5. Map res-7 -> res-9 via parent crosswalk ------------------------
    print("\nMapping res-7 predictions -> res-9...")
    parents = pd.read_parquet(
        os.path.join(OUTPUT_DIR, "h3_parent_crosswalk.parquet")
    )[['h3index', 'h3_res7']]

    result_r7_renamed = result_r7.rename(columns={'h3index': 'h3_res7'})
    result = parents.merge(result_r7_renamed, on='h3_res7', how='left')
    result = result.dropna(subset=['pm25_actual'])
    print(f"  {len(result):,} res-9 hexagons")

    # -- 6. Compute scores, WHO bands, and output columns ------------------
    print("Computing scores and WHO bands...")

    # Score: percentile rank of actual PM2.5 (higher PM2.5 = higher score)
    result['score'] = percentile_rank(result['pm25_actual'])
    result['score_baseline'] = percentile_rank(result['pm25_fire_low'])
    result['delta_score'] = (result['score'] - result['score_baseline']).round(1)

    # Raw values rounded
    result['c_pm25'] = result['pm25_actual'].round(2)
    result['c_pm25_baseline'] = result['pm25_fire_low'].round(2)
    result['c_pm25_delta'] = (result['pm25_actual'] - result['pm25_fire_low']).round(2)
    result['c_pm25_fire_high'] = result['pm25_fire_high'].round(2)

    # WHO bands
    result['type'] = result['pm25_actual'].apply(who_band)
    result['type_label'] = result['type'].map(WHO_LABELS_ES)

    # WHO band as percentile for choropleth display
    result['c_who_band'] = result['type'].map({1: 25.0, 2: 60.0, 3: 90.0})

    # Select output columns
    out_cols = [
        'h3index', 'score', 'score_baseline', 'delta_score',
        'c_pm25', 'c_pm25_baseline', 'c_pm25_delta', 'c_pm25_fire_high',
        'c_who_band', 'type', 'type_label',
    ]
    result = result[out_cols]

    # -- 7. Summary and save -----------------------------------------------
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Rows: {len(result):,}")
    print(f"  PM2.5 actual: mean={result.c_pm25.mean():.2f}, "
          f"range={result.c_pm25.min():.2f}-{result.c_pm25.max():.2f}")
    print(f"  PM2.5 fire-low: mean={result.c_pm25_baseline.mean():.2f}")
    print(f"  PM2.5 fire-high: mean={result.c_pm25_fire_high.mean():.2f}")
    print(f"  Delta (actual - fire-low): mean={result.c_pm25_delta.mean():.2f}")
    print(f"\n  WHO exceedance bands:")
    for band, label in WHO_LABELS.items():
        n = (result.type == band).sum()
        pct = n / len(result) * 100
        print(f"    {label}: {n:,} ({pct:.1f}%)")
    print(f"\n  Built in {elapsed:.0f}s")

    result.to_parquet(OUTPUT_PATH, index=False)
    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"  Saved: {OUTPUT_PATH} ({size_mb:.1f} MB)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
