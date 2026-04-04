"""
Compute per-hexagon PM2.5 trends and linear projections.

Reads the annual panel parquet and fits a linear trend per H3 hexagon.
Outputs trend statistics and a naive linear projection to 2031.

This provides the baseline for the two modelling branches:
  - Branch A: time-series models (ARIMA/Prophet) per hexagon
  - Branch B: spatial ML (XGBoost/RF) with trend features

Input:
  pipeline/output/pm25_annual_panel.parquet  (h3index, year, pm25)

Output:
  pipeline/output/pm25_trends.parquet  (h3index, pm25_mean, pm25_latest, ...)

Usage:
  python pipeline/compute_pm25_trends.py
  python pipeline/compute_pm25_trends.py --target-year 2035
"""

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import linregress

from config import OUTPUT_DIR

INPUT_PATH = os.path.join(OUTPUT_DIR, "pm25_annual_panel.parquet")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "pm25_trends.parquet")

DEFAULT_TARGET_YEAR = 2031
MIN_YEARS = 5  # minimum data points for trend fitting


def fit_trend(group, target_year):
    """Fit linear trend for a single hexagon's time series."""
    valid = group.dropna(subset=['pm25'])
    n_years = len(valid)

    result = {
        'n_years': n_years,
        'pm25_mean': valid['pm25'].mean(),
        'pm25_std': valid['pm25'].std(),
        'pm25_first': valid.iloc[0]['pm25'] if n_years > 0 else np.nan,
        'pm25_latest': valid.iloc[-1]['pm25'] if n_years > 0 else np.nan,
        'year_first': int(valid.iloc[0]['year']) if n_years > 0 else np.nan,
        'year_latest': int(valid.iloc[-1]['year']) if n_years > 0 else np.nan,
    }

    if n_years < MIN_YEARS:
        result.update({
            'trend_slope': np.nan,
            'trend_intercept': np.nan,
            'trend_r2': np.nan,
            'trend_pvalue': np.nan,
            'trend_stderr': np.nan,
            'pm25_projected': np.nan,
            'delta_projected': np.nan,
        })
        return result

    slope, intercept, r_value, p_value, std_err = linregress(
        valid['year'].values, valid['pm25'].values
    )

    projected = intercept + slope * target_year
    projected = max(projected, 0.0)  # PM2.5 cannot be negative

    result.update({
        'trend_slope': round(slope, 4),
        'trend_intercept': round(intercept, 2),
        'trend_r2': round(r_value ** 2, 4),
        'trend_pvalue': round(p_value, 6),
        'trend_stderr': round(std_err, 4),
        'pm25_projected': round(projected, 2),
        'delta_projected': round(projected - result['pm25_latest'], 2),
    })
    return result


def main():
    parser = argparse.ArgumentParser(description="Compute PM2.5 trends per hexagon")
    parser.add_argument("--target-year", type=int, default=DEFAULT_TARGET_YEAR,
                        help=f"Projection target year (default: {DEFAULT_TARGET_YEAR})")
    args = parser.parse_args()

    print(f"Loading panel data from {INPUT_PATH}...")
    df = pd.read_parquet(INPUT_PATH)
    n_hex = df['h3index'].nunique()
    n_years = df['year'].nunique()
    year_range = f"{df['year'].min()}–{df['year'].max()}"
    print(f"  {len(df):,} rows, {n_hex:,} hexagons, {n_years} years ({year_range})")

    print(f"\nFitting trends (target year: {args.target_year})...")
    t0 = time.time()

    trends = []
    grouped = df.sort_values('year').groupby('h3index')

    for i, (h3, group) in enumerate(grouped):
        if i % 20000 == 0 and i > 0:
            elapsed = time.time() - t0
            rate = i / elapsed
            eta = (n_hex - i) / rate / 60
            print(f"    {i:,}/{n_hex:,} ({rate:.0f} hex/s, ETA {eta:.1f} min)")

        result = fit_trend(group, args.target_year)
        result['h3index'] = h3
        trends.append(result)

    trends_df = pd.DataFrame(trends)
    elapsed = time.time() - t0
    print(f"  Fitted {len(trends_df):,} hexagons in {elapsed:.0f}s")

    # Summary statistics
    print(f"\n{'=' * 60}")
    valid_trends = trends_df[trends_df['trend_slope'].notna()]
    n_valid = len(valid_trends)
    n_skipped = len(trends_df) - n_valid
    print(f"  Valid trends: {n_valid:,} ({n_skipped:,} skipped, <{MIN_YEARS} years)")

    if n_valid > 0:
        slope = valid_trends['trend_slope']
        print(f"\n  Trend slope (µg/m³ per year):")
        print(f"    mean={slope.mean():.4f}, median={slope.median():.4f}")
        print(f"    min={slope.min():.4f}, max={slope.max():.4f}")
        print(f"    improving (slope < 0): {(slope < 0).sum():,} ({(slope < 0).mean()*100:.1f}%)")
        print(f"    worsening (slope > 0): {(slope > 0).sum():,} ({(slope > 0).mean()*100:.1f}%)")

        sig = valid_trends[valid_trends['trend_pvalue'] < 0.05]
        print(f"\n  Significant trends (p < 0.05): {len(sig):,} ({len(sig)/n_valid*100:.1f}%)")

        r2 = valid_trends['trend_r2']
        print(f"\n  R² distribution:")
        print(f"    mean={r2.mean():.3f}, median={r2.median():.3f}")
        print(f"    R² > 0.5: {(r2 > 0.5).sum():,}, R² > 0.7: {(r2 > 0.7).sum():,}")

        proj = valid_trends['pm25_projected']
        print(f"\n  Projection to {args.target_year}:")
        print(f"    mean={proj.mean():.2f}, median={proj.median():.2f}")
        print(f"    min={proj.min():.2f}, max={proj.max():.2f}")

        delta = valid_trends['delta_projected']
        print(f"\n  Delta (projected - latest):")
        print(f"    mean={delta.mean():.2f}, median={delta.median():.2f}")

    # Save
    trends_df.to_parquet(OUTPUT_PATH, index=False)
    size_kb = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"\n  Output: {OUTPUT_PATH}")
    print(f"  Rows: {len(trends_df):,}, Size: {size_kb:.0f} KB")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
