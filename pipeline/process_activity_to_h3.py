"""
Process activity rasters to H3 res-9 via centroid sampling.

Samples 10 GeoTIFFs (5 variables x 2 periods) at H3 centroids,
producing sat_productive_activity.parquet with true per-hexagon values.

Input:
  pipeline/output/act_{var}_{period}.tif  (10 files)
  pipeline/output/hexagons-lite.geojson   (H3 grid)
  pipeline/output/hansen_h3_annual.parquet (Hansen at H3, already computed)

Output:
  pipeline/output/sat_productive_activity.parquet

Usage:
  python pipeline/process_activity_to_h3.py
"""

import json
import os
import time

import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import shape

from config import OUTPUT_DIR

HEXAGONS_PATH = os.path.join(OUTPUT_DIR, "hexagons-lite.geojson")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "sat_productive_activity.parquet")

RASTERS = [
    ('act_viirs_current.tif', 'c_viirs'),
    ('act_viirs_baseline.tif', 'c_viirs_baseline'),
    ('act_npp_current.tif', 'c_npp'),
    ('act_npp_baseline.tif', 'c_npp_baseline'),
    ('act_ndvi_current.tif', 'c_ndvi'),
    ('act_ndvi_baseline.tif', 'c_ndvi_baseline'),
    ('act_lst_current.tif', 'c_lst'),
    ('act_lst_baseline.tif', 'c_lst_baseline'),
    ('act_ghsl_current.tif', 'c_built'),
    ('act_ghsl_baseline.tif', 'c_built_baseline'),
]


def sample_raster(raster_path, features):
    values = []
    with rasterio.open(raster_path) as src:
        for feat in features:
            geom = shape(feat["geometry"])
            cx, cy = geom.centroid.x, geom.centroid.y
            try:
                r, c = src.index(cx, cy)
                if 0 <= r < src.height and 0 <= c < src.width:
                    val = float(src.read(1, window=((r, r + 1), (c, c + 1)))[0, 0])
                    values.append(val if not np.isnan(val) and val > -9999 else np.nan)
                else:
                    values.append(np.nan)
            except Exception:
                values.append(np.nan)
    return values


def pctile(s):
    v = s.notna()
    r = pd.Series(np.nan, index=s.index)
    if v.sum() > 1:
        r[v] = s[v].rank(pct=True) * 100.0
    return r.round(1)


def main():
    t0 = time.time()

    print("Loading hexagon grid...")
    with open(HEXAGONS_PATH) as f:
        gj = json.load(f)
    features = gj["features"]
    h3_ids = [feat["properties"]["h3index"] for feat in features]
    print(f"  {len(features):,} hexagons")

    result = pd.DataFrame({'h3index': h3_ids})

    # Sample each raster
    for fname, col in RASTERS:
        path = os.path.join(OUTPUT_DIR, fname)
        if not os.path.exists(path):
            print(f"  SKIP {fname} (not found)")
            result[col] = np.nan
            continue
        print(f"  Sampling {fname} -> {col}...")
        t1 = time.time()
        vals = sample_raster(path, features)
        valid = sum(1 for v in vals if not np.isnan(v))
        result[col] = vals
        mean = np.nanmean(vals)
        print(f"    {valid:,}/{len(vals):,} valid, mean={mean:.4f}, {time.time()-t1:.1f}s")

    # Add Hansen (already at H3 from process_hansen_to_h3.py)
    hansen_path = os.path.join(OUTPUT_DIR, "hansen_h3_annual.parquet")
    if os.path.exists(hansen_path):
        print("  Loading Hansen H3 annual...")
        ha = pd.read_parquet(hansen_path)
        loss_bl = ha[ha.year.between(2001, 2012)].groupby('h3index')['lost'].sum()
        loss_cur = ha[ha.year.between(2013, 2024)].groupby('h3index')['lost'].sum()
        result = result.merge(loss_bl.rename('c_forest_loss').reset_index(), on='h3index', how='left')
        result = result.merge(loss_cur.rename('c_forest_loss_baseline').reset_index(), on='h3index', how='left')
        # Swap: baseline = 2001-2012, current = 2013-2024
        result.rename(columns={
            'c_forest_loss': 'c_forest_loss_temp',
            'c_forest_loss_baseline': 'c_forest_loss',
        }, inplace=True)
        result.rename(columns={'c_forest_loss_temp': 'c_forest_loss_baseline'}, inplace=True)

    # Compute deltas
    for var in ['c_viirs', 'c_npp', 'c_ndvi', 'c_built', 'c_lst', 'c_forest_loss']:
        bl_col = f'{var}_baseline'
        if var in result.columns and bl_col in result.columns:
            result[f'{var}_delta'] = (result[var] - result[bl_col]).round(4)

    # Score = VIIRS percentile (primary choropleth)
    result['score'] = pctile(result['c_viirs'])
    result['score_baseline'] = pctile(result['c_viirs_baseline'])
    result['delta_score'] = (result['score'] - result['score_baseline']).round(1)

    # Round raw values
    for c in result.columns:
        if c.startswith('c_') and result[c].dtype == float:
            result[c] = result[c].round(4)

    # Type quintiles
    result['type'] = pd.cut(result['score'].fillna(0),
                             bins=[0, 20, 40, 60, 80, 100],
                             labels=[1, 2, 3, 4, 5],
                             include_lowest=True).astype(float).fillna(1).astype(int)
    labels = {1: 'Muy baja actividad', 2: 'Baja actividad',
              3: 'Actividad moderada', 4: 'Alta actividad', 5: 'Muy alta actividad'}
    result['type_label'] = result['type'].map(labels)

    result = result.dropna(subset=['score'])

    # Summary
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Rows: {len(result):,}")
    print(f"  Score: mean={result.score.mean():.1f}, delta_std={result.delta_score.std():.1f}")
    for var in ['c_viirs', 'c_npp', 'c_ndvi', 'c_built', 'c_forest_loss', 'c_lst']:
        if var in result.columns:
            d = f'{var}_delta'
            dm = result[d].mean() if d in result.columns else 0
            print(f"    {var:20s} mean={result[var].mean():.4f}  delta={dm:+.4f}")
    print(f"  Built in {elapsed:.0f}s")

    result.to_parquet(OUTPUT_PATH, index=False)
    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"  Saved: {OUTPUT_PATH} ({size_mb:.1f} MB)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
