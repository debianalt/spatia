"""
Process activity rasters to H3 res-9 via bilinear interpolation at centroids.

For each hexagon, samples the raster at its centroid using bilinear
interpolation (scipy map_coordinates).  This avoids grid artifacts from
polygon masking at coarse resolution (250m pixels vs 350m hex diameter).

Input:
  pipeline/output/act_{var}_{period}.tif  (10 files)
  pipeline/output/hexagons-lite.geojson   (H3 grid, 320K polygons)
  pipeline/output/hansen_h3_annual.parquet (Hansen at H3, already computed)

Output:
  pipeline/output/sat_productive_activity.parquet

Usage:
  python pipeline/process_activity_to_h3.py
"""

import json
import os
import sys
import time

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import map_coordinates

import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from config import OUTPUT_DIR, get_territory

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


def sample_raster_bilinear(raster_path, lngs, lats):
    """Sample raster at (lng, lat) points using bilinear interpolation.

    Reads the entire raster once, converts coordinates to fractional
    pixel positions, then uses scipy map_coordinates (order=1) for
    bilinear interpolation.  Vectorised — handles all points at once.
    """
    with rasterio.open(raster_path) as src:
        data = src.read(1).astype(np.float64)
        # Replace nodata with NaN
        if src.nodata is not None:
            data[data == src.nodata] = np.nan

        # Convert geographic coords to fractional pixel coords
        inv_transform = ~src.transform
        cols, rows = inv_transform * (np.array(lngs), np.array(lats))

        # Mask points outside raster bounds
        rows = np.asarray(rows, dtype=np.float64)
        cols = np.asarray(cols, dtype=np.float64)
        outside = (rows < 0) | (rows >= src.height) | (cols < 0) | (cols >= src.width)

        # Bilinear interpolation (order=1), NaN-safe via prefilter=False
        values = map_coordinates(data, [rows, cols], order=1,
                                 mode='constant', cval=np.nan,
                                 prefilter=False)
        values[outside] = np.nan

    valid = np.count_nonzero(~np.isnan(values))
    print(f"  Bilinear sample: {valid:,}/{len(values):,} valid "
          f"({valid/len(values)*100:.1f}%)")
    return values


def pctile(s):
    v = s.notna()
    r = pd.Series(np.nan, index=s.index)
    if v.sum() > 1:
        r[v] = s[v].rank(pct=True) * 100.0
    return r.round(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--territory", default="misiones", help="Territory ID (default: misiones)")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    t_prefix = territory['output_prefix']
    if t_prefix:
        t_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/'))
        hexagons_path = os.path.join(t_dir, 'hexagons.geojson')
        output_path = os.path.join(t_dir, 'sat_productive_activity.parquet')
        raster_dir = t_dir
    else:
        t_dir = OUTPUT_DIR
        hexagons_path = HEXAGONS_PATH
        output_path = OUTPUT_PATH
        raster_dir = OUTPUT_DIR

    t0 = time.time()

    # Load hexagon centroids from geojson
    print("Loading hexagon grid...")
    with open(hexagons_path) as f:
        gj = json.load(f)
    features = gj["features"]

    from shapely.geometry import shape
    h3_ids = []
    lngs = []
    lats = []
    for feat in features:
        h3_ids.append(feat["properties"]["h3index"])
        centroid = shape(feat["geometry"]).centroid
        lngs.append(centroid.x)
        lats.append(centroid.y)

    lngs = np.array(lngs, dtype=np.float64)
    lats = np.array(lats, dtype=np.float64)
    print(f"  {len(h3_ids):,} hexagons")

    result = pd.DataFrame({'h3index': h3_ids})

    # Bilinear sample each raster at hex centroids
    for fname, col in RASTERS:
        path = os.path.join(raster_dir, fname)
        if not os.path.exists(path):
            print(f"  SKIP {fname} (not found)")
            result[col] = np.nan
            continue
        print(f"  Sampling {fname} -> {col}...")
        t1 = time.time()
        vals = sample_raster_bilinear(path, lngs, lats)
        if fname.startswith('act_ghsl_'):
            vals = vals / 10000.0
        result[col] = vals
        mean = np.nanmean(vals)
        print(f"    mean={mean:.4f}, {time.time()-t1:.1f}s")

    # Add Hansen (already at H3 from process_hansen_to_h3.py)
    hansen_path = os.path.join(t_dir, "hansen_h3_annual.parquet")
    if os.path.exists(hansen_path):
        print("  Loading Hansen H3 annual...")
        ha = pd.read_parquet(hansen_path)
        bl_px = ha[ha.year.between(2001, 2012)].groupby('h3index')['lost'].sum()
        cur_px = ha[ha.year.between(2013, 2024)].groupby('h3index')['lost'].sum()
        hex_px = ha.drop_duplicates('h3index').set_index('h3index')['hex_pixel_count']
        hansen = pd.DataFrame({
            'loss_bl_px': bl_px, 'loss_cur_px': cur_px, 'hex_pixel_count': hex_px,
        }).reset_index()
        hansen['c_forest_loss'] = (
            hansen['loss_cur_px'] / hansen['hex_pixel_count'].replace(0, np.nan) * 100
        ).fillna(0).round(3)
        hansen['c_forest_loss_baseline'] = (
            hansen['loss_bl_px'] / hansen['hex_pixel_count'].replace(0, np.nan) * 100
        ).fillna(0).round(3)
        result = result.merge(
            hansen[['h3index', 'c_forest_loss', 'c_forest_loss_baseline']],
            on='h3index', how='left',
        )
    else:
        result['c_forest_loss'] = 0
        result['c_forest_loss_baseline'] = 0

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
    result['type'] = pd.cut(
        result['score'].fillna(0),
        bins=[0, 20, 40, 60, 80, 100],
        labels=[1, 2, 3, 4, 5],
        include_lowest=True,
    ).astype(float).fillna(1).astype(int)
    labels = {
        1: 'Muy baja actividad', 2: 'Baja actividad',
        3: 'Actividad moderada', 4: 'Alta actividad', 5: 'Muy alta actividad',
    }
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
    print(f"  Types: {result.type.value_counts().sort_index().to_dict()}")
    print(f"  Built in {elapsed:.0f}s")

    os.makedirs(t_dir, exist_ok=True)
    result.to_parquet(output_path, index=False)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Saved: {output_path} ({size_mb:.1f} MB)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
