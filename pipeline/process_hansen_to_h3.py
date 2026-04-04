"""
Process Hansen loss year and treecover2000 rasters to H3 hexagonal grid.

Samples rasters at H3 res-9 centroids, then computes per-hexagon metrics:
- treecover2000: baseline forest cover (%)
- Annual loss fractions for each year (2001-2024)
- Cumulative loss, baseline vs current rates, acceleration

Input:
  pipeline/output/hansen_lossyear.tif     (pixel = year of loss, 0-24)
  pipeline/output/hansen_treecover2000.tif (pixel = % tree cover)
  pipeline/output/hexagons-lite.geojson   (H3 res-9 grid)

Output:
  pipeline/output/hansen_h3_annual.parquet (h3index, year, loss_pct)
  pipeline/output/sat_deforestation_dynamics.parquet (Spatia layer, H3 res-9)

Usage:
  python pipeline/process_hansen_to_h3.py
"""

import json
import os
import sys
import time

import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import shape

from config import OUTPUT_DIR

LOSSYEAR_PATH = os.path.join(OUTPUT_DIR, "hansen_lossyear.tif")
TREECOVER_PATH = os.path.join(OUTPUT_DIR, "hansen_treecover2000.tif")
HEXAGONS_PATH = os.path.join(OUTPUT_DIR, "hexagons-lite.geojson")
ANNUAL_PATH = os.path.join(OUTPUT_DIR, "hansen_h3_annual.parquet")
SPATIA_PATH = os.path.join(OUTPUT_DIR, "sat_deforestation_dynamics.parquet")

BASELINE_YEARS = range(2001, 2011)
CURRENT_YEARS = range(2015, 2025)


def sample_raster(raster_path, features):
    """Sample raster at hexagon centroids."""
    values = []
    with rasterio.open(raster_path) as src:
        for feat in features:
            geom = shape(feat["geometry"])
            cx, cy = geom.centroid.x, geom.centroid.y
            try:
                r, c = src.index(cx, cy)
                if 0 <= r < src.height and 0 <= c < src.width:
                    val = float(src.read(1, window=((r, r + 1), (c, c + 1)))[0, 0])
                    values.append(val)
                else:
                    values.append(np.nan)
            except Exception:
                values.append(np.nan)
    return values


def percentile_rank(series):
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result.round(1)


def main():
    t0 = time.time()

    # Load hexagon grid
    print("Loading hexagon grid...")
    with open(HEXAGONS_PATH) as f:
        gj = json.load(f)
    features = gj["features"]
    h3_ids = [feat["properties"]["h3index"] for feat in features]
    print(f"  {len(features):,} hexagons")

    # Sample treecover2000
    print("\nSampling treecover2000...")
    tc = sample_raster(TREECOVER_PATH, features)
    print(f"  Mean: {np.nanmean(tc):.1f}%, valid: {sum(1 for v in tc if not np.isnan(v)):,}")

    # Sample lossyear
    print("Sampling lossyear...")
    ly = sample_raster(LOSSYEAR_PATH, features)
    valid_loss = sum(1 for v in ly if not np.isnan(v) and v > 0)
    print(f"  Pixels with loss: {valid_loss:,}")

    # Build annual panel: for each hex, for each year, did it lose forest?
    print("\nBuilding annual panel...")
    records = []
    for i, h3id in enumerate(h3_ids):
        tc_val = tc[i]
        ly_val = ly[i]
        loss_year = int(ly_val) if not np.isnan(ly_val) and ly_val > 0 else 0

        for year in range(2001, 2025):
            yr_code = year - 2000  # 1-24
            lost = 1 if yr_code == loss_year else 0
            records.append({
                'h3index': h3id,
                'year': year,
                'lost': lost,
                'treecover2000': tc_val if not np.isnan(tc_val) else 0,
            })

    panel = pd.DataFrame(records)
    print(f"  Panel: {len(panel):,} rows ({len(h3_ids):,} hex x 24 years)")

    # Save annual panel
    panel.to_parquet(ANNUAL_PATH, index=False)
    print(f"  Saved: {ANNUAL_PATH}")

    # --- Build Spatia layer -----------------------------------------------
    print("\nBuilding Spatia layer...")

    # Per-hex: loss rate baseline, current, cumulative
    bl = panel[panel.year.isin(BASELINE_YEARS)].groupby('h3index')['lost'].mean()
    cur = panel[panel.year.isin(CURRENT_YEARS)].groupby('h3index')['lost'].mean()
    cumul = panel.groupby('h3index')['lost'].sum()
    tc_base = panel.drop_duplicates('h3index').set_index('h3index')['treecover2000']

    result = pd.DataFrame({
        'loss_baseline': bl,
        'loss_current': cur,
        'loss_cumulative': cumul,
        'treecover2000': tc_base,
    }).reset_index()

    result['loss_delta'] = result['loss_current'] - result['loss_baseline']

    # Only hexagons with some forest
    result = result[result.treecover2000 > 5].copy()

    # Scores (higher loss = higher score)
    result['score'] = percentile_rank(result['loss_current'])
    result['score_baseline'] = percentile_rank(result['loss_baseline'])
    result['delta_score'] = (result['score'] - result['score_baseline']).round(1)

    # Display values (convert to % — loss_current is fraction of years with loss)
    # This is probability of losing this pixel in any given year
    result['c_loss_rate'] = (result['loss_current'] * 100).round(2)
    result['c_loss_rate_baseline'] = (result['loss_baseline'] * 100).round(2)
    result['c_loss_rate_delta'] = (result['loss_delta'] * 100).round(2)
    result['c_cumulative'] = result['loss_cumulative'].astype(int)
    result['c_treecover'] = result['treecover2000'].round(0)

    # Type labels
    try:
        result['type'] = pd.qcut(result['score'], 4, labels=[1, 2, 3, 4]).astype(int)
    except ValueError:
        result['type'] = pd.cut(result['score'], bins=[0, 25, 50, 75, 100],
                                 labels=[1, 2, 3, 4], include_lowest=True).astype(int)
    type_map = {1: 'Baja presion', 2: 'Presion moderada',
                3: 'Alta presion', 4: 'Presion critica'}
    result['type_label'] = result['type'].map(type_map)

    out_cols = ['h3index', 'score', 'score_baseline', 'delta_score',
                'c_loss_rate', 'c_loss_rate_baseline', 'c_loss_rate_delta',
                'c_cumulative', 'c_treecover', 'type', 'type_label']
    result = result[out_cols]

    # Summary
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Hexagons (forested): {len(result):,}")
    print(f"  Loss rate current: mean={result.c_loss_rate.mean():.3f}%/yr")
    print(f"  Loss rate baseline: mean={result.c_loss_rate_baseline.mean():.3f}%/yr")
    print(f"  Delta: mean={result.c_loss_rate_delta.mean():.3f}%/yr")
    print(f"  Tree cover 2000: mean={result.c_treecover.mean():.0f}%")
    print(f"  Types: {result.type.value_counts().sort_index().to_dict()}")
    print(f"  Built in {elapsed:.0f}s")

    result.to_parquet(SPATIA_PATH, index=False)
    size_mb = os.path.getsize(SPATIA_PATH) / (1024 * 1024)
    print(f"  Saved: {SPATIA_PATH} ({size_mb:.1f} MB)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
