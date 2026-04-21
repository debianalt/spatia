"""
Process annual PM2.5 covariate GeoTIFFs to H3 res-9 parquets.

Reads rasters exported by gee_export_pm25_covariates.py (downloaded to
pipeline/output/pm25_covariates/) and samples each hexagon centroid using
bilinear interpolation.  All covariates >=250m resolution — bilinear avoids
grid artifacts from polygon masking at coarse pixel sizes.

Output:
  {territory_dir}/pm25_covariates_annual.parquet
    Long-format panel: (h3index, year, burned_fraction, temp_mean, ...)

Usage:
  python pipeline/process_pm25_covariates_to_h3.py --territory misiones
  python pipeline/process_pm25_covariates_to_h3.py --territory itapua_py
  python pipeline/process_pm25_covariates_to_h3.py --territory misiones --only fire,era5
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import re
import sys
import time

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import map_coordinates
from shapely.geometry import shape

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import GCS_BUCKET, OUTPUT_DIR, get_territory

_GCLOUD = 'gcloud.cmd' if platform.system() == 'Windows' else 'gcloud'

RASTERS_DIR = os.path.join(OUTPUT_DIR, 'pm25_covariates')

COVARIATE_GROUPS = {
    'fire':   {'bands': ['burned_fraction'],                   'multi': False},
    'era5':   {'bands': ['temp_mean', 'frost_days',
                         'solar_radiation', 'dewpoint_mean'],  'multi': True},
    'chirps': {'bands': ['total_mm'],                          'multi': False},
    'ndvi':   {'bands': ['mean_ndvi'],                         'multi': False},
    'lst':    {'bands': ['lst_day', 'lst_night',
                         'lst_amplitude'],                     'multi': True},
    'npp':    {'bands': ['mean_npp'],                          'multi': False},
    'vcf':    {'bands': ['tree_cover'],                        'multi': False},
}

YEARS = list(range(2000, 2023))


# ─── Sampling ────────────────────────────────────────────────────────────

def sample_raster_bilinear(raster_path, lngs, lats, band_idx=0):
    """Sample a single raster band at (lng, lat) using bilinear interpolation."""
    with rasterio.open(raster_path) as src:
        data = src.read(band_idx + 1).astype(np.float64)
        if src.nodata is not None:
            data[data == src.nodata] = np.nan

        inv_transform = ~src.transform
        cols, rows = inv_transform * (np.array(lngs), np.array(lats))

        rows = np.asarray(rows, dtype=np.float64)
        cols = np.asarray(cols, dtype=np.float64)
        outside = (rows < 0) | (rows >= src.height) | (cols < 0) | (cols >= src.width)

        values = map_coordinates(data, [rows, cols], order=1,
                                 mode='constant', cval=np.nan, prefilter=False)
        values[outside] = np.nan

    return values


def sample_multiband_bilinear(raster_path, lngs, lats, n_bands):
    """Sample all bands of a multi-band raster via bilinear interpolation."""
    results = []
    for b in range(n_bands):
        results.append(sample_raster_bilinear(raster_path, lngs, lats, band_idx=b))
    return results


# ─── Hex loading ─────────────────────────────────────────────────────────

def load_hex_centroids(t_dir):
    """Load H3 centroids from hexagons.geojson. Returns (h3ids, lngs, lats)."""
    for fname in ('hexagons.geojson', 'hexagons-lite.geojson'):
        path = os.path.join(t_dir, fname)
        if os.path.exists(path):
            break
    else:
        raise FileNotFoundError(f'No hexagons GeoJSON in {t_dir}')

    with open(path) as f:
        gj = json.load(f)

    h3ids, lngs, lats = [], [], []
    for feat in gj['features']:
        h3ids.append(feat['properties']['h3index'])
        c = shape(feat['geometry']).centroid
        lngs.append(c.x)
        lats.append(c.y)

    return h3ids, np.array(lngs, dtype=np.float64), np.array(lats, dtype=np.float64)


# ─── GCS download helper ────────────────────────────────────────────────

def download_if_missing(local_path, gcs_path):
    if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
        return True
    print(f'  Downloading {gcs_path} ...')
    cmd = f'{_GCLOUD} storage cp "gs://{GCS_BUCKET}/{gcs_path}" "{local_path}"'
    ret = os.system(cmd)
    return ret == 0 and os.path.exists(local_path)


# ─── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Process PM2.5 covariate rasters to H3 res-9')
    parser.add_argument('--territory', default='misiones',
                        help='Territory ID')
    parser.add_argument('--only', default=None,
                        help='Comma-separated group names (fire,era5,...)')
    parser.add_argument('--years', type=int, nargs='+', default=None,
                        help=f'Specific years (default: {YEARS[0]}-{YEARS[-1]})')
    parser.add_argument('--download', action='store_true',
                        help='Auto-download missing rasters from GCS')
    args = parser.parse_args()

    territory = get_territory(args.territory)
    t_prefix = territory['output_prefix']
    t_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/')) if t_prefix else OUTPUT_DIR
    output_path = os.path.join(t_dir, 'pm25_covariates_annual.parquet')
    years = args.years or YEARS

    groups = COVARIATE_GROUPS
    if args.only:
        keys = [k.strip() for k in args.only.split(',')]
        groups = {k: v for k, v in COVARIATE_GROUPS.items() if k in keys}

    t0 = time.time()

    # Load hex centroids
    print(f"Loading hexagons for {territory['label']}...")
    h3ids, lngs, lats = load_hex_centroids(t_dir)
    n_hex = len(h3ids)
    print(f"  {n_hex:,} hexagons")

    # Ensure raster directory exists
    os.makedirs(RASTERS_DIR, exist_ok=True)

    # Process each group × year
    all_frames = []

    for group_name, spec in groups.items():
        bands = spec['bands']
        multi = spec['multi']
        print(f"\n{'='*50}")
        print(f"Processing {group_name} ({len(bands)} band{'s' if len(bands)>1 else ''})...")

        for year in sorted(years):
            tif_name = f'{group_name}_{year}.tif'
            tif_path = os.path.join(RASTERS_DIR, tif_name)

            if not os.path.exists(tif_path):
                if args.download:
                    gcs_path = f'pipeline/pm25_covariates/{tif_name}'
                    if not download_if_missing(tif_path, gcs_path):
                        print(f'  SKIP {tif_name} (download failed)')
                        continue
                else:
                    print(f'  SKIP {tif_name} (not found)')
                    continue

            if multi:
                vals_list = sample_multiband_bilinear(tif_path, lngs, lats, len(bands))
                row = {'year': year}
                valid_counts = []
                for band_name, vals in zip(bands, vals_list):
                    row[band_name] = vals
                    valid_counts.append(np.count_nonzero(~np.isnan(vals)))
                coverage = min(valid_counts) / n_hex * 100
            else:
                vals = sample_raster_bilinear(tif_path, lngs, lats)
                row = {'year': year, bands[0]: vals}
                coverage = np.count_nonzero(~np.isnan(vals)) / n_hex * 100

            # Build per-year frame
            frame = pd.DataFrame({'h3index': h3ids, 'year': year})
            for band_name in bands:
                frame[band_name] = row[band_name] if isinstance(row[band_name], np.ndarray) else row[band_name]

            all_frames.append((group_name, year, frame))
            print(f'  {group_name}_{year}: coverage={coverage:.1f}%')

    if not all_frames:
        print('\nNo rasters processed. Nothing to write.')
        return 1

    # Merge all groups into a single panel
    print(f'\nMerging {len(all_frames)} group-year frames...')

    # Group frames by (year) and merge across covariate groups
    from collections import defaultdict
    year_groups = defaultdict(list)
    for group_name, year, frame in all_frames:
        year_groups[year].append(frame)

    merged_frames = []
    for year in sorted(year_groups.keys()):
        frames = year_groups[year]
        result = frames[0]
        for f in frames[1:]:
            cols_to_add = [c for c in f.columns if c not in ('h3index', 'year')]
            result = result.merge(f[['h3index'] + cols_to_add], on='h3index', how='inner')
        merged_frames.append(result)

    panel = pd.concat(merged_frames, ignore_index=True)

    # Sort and save
    panel = panel.sort_values(['h3index', 'year']).reset_index(drop=True)
    panel.to_parquet(output_path, index=False)

    elapsed = time.time() - t0
    print(f'\nWrote {output_path}')
    print(f'  {len(panel):,} rows ({panel["h3index"].nunique():,} hex x '
          f'{panel["year"].nunique()} years)')
    print(f'  Columns: {list(panel.columns)}')
    print(f'  Elapsed: {elapsed:.0f}s')

    return 0


if __name__ == '__main__':
    sys.exit(main())
