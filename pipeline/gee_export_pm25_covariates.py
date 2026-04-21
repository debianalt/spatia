"""
Export annual PM2.5 covariate rasters from GEE for the spatial model.

Exports 7 covariate groups × 23 years (2000-2022) as GeoTIFFs to GCS.
Combined bbox covers Misiones + Itapúa.  Each territory clips its own
hexagons downstream in process_pm25_covariates_to_h3.py.

Covariate groups:
  fire   — MODIS MCD64A1 burned area fraction (1 band, 500m)
  era5   — ERA5-Land temp, frost, solar, dewpoint (4 bands, 11132m)
  chirps — CHIRPS daily → annual total mm (1 band, 5566m)
  ndvi   — MODIS MOD13A2 NDVI (1 band, 1000m)
  lst    — MODIS MOD11A1 LST day/night/amplitude (3 bands, 1000m)
  npp    — MODIS MOD17A3HGF net primary productivity (1 band, 500m)
  vcf    — MODIS MOD44B tree cover (1 band, 250m)

Usage:
  python pipeline/gee_export_pm25_covariates.py --wait
  python pipeline/gee_export_pm25_covariates.py --only fire,era5 --years 2020 2021
  python pipeline/gee_export_pm25_covariates.py --no-wait
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import ee

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import GCS_BUCKET

COMBINED_BBOX = [-57.40, -28.20, -53.55, -25.44]
YEARS = list(range(2000, 2023))
GCS_PREFIX = 'pipeline/pm25_covariates'


def authenticate():
    key_env = os.environ.get('GEE_SERVICE_ACCOUNT_KEY', '')
    if not key_env:
        ee.Initialize()
        return False
    if os.path.isfile(key_env):
        with open(key_env) as f:
            key_data = json.load(f)
    else:
        key_data = json.loads(key_env)
    credentials = ee.ServiceAccountCredentials(
        key_data['client_email'], key_data=json.dumps(key_data))
    ee.Initialize(credentials, opt_url='https://earthengine-highvolume.googleapis.com')
    return True


# ─── Builder functions (one per covariate group) ─────────────────────────

def build_fire(bbox, year):
    """Annual burned area fraction from MODIS MCD64A1."""
    col = (ee.ImageCollection('MODIS/061/MCD64A1')
           .filter(ee.Filter.calendarRange(year, year, 'year'))
           .filterBounds(bbox))
    burned = col.map(lambda img: img.select('BurnDate').gt(0))
    fraction = burned.mean().unmask(0)
    return fraction.rename('burned_fraction').clip(bbox).toFloat()


def build_era5(bbox, year):
    """4-band ERA5-Land annual climate summary."""
    col = (ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
           .filter(ee.Filter.calendarRange(year, year, 'year'))
           .filterBounds(bbox))

    temp_mean = col.select('temperature_2m').mean().subtract(273.15)

    frost_months = col.map(
        lambda img: img.select('temperature_2m').subtract(273.15).lt(5))
    frost_days = frost_months.sum().multiply(30)

    solar = (col.select('surface_solar_radiation_downwards_sum')
             .sum().multiply(1e-6))

    dewpoint = col.select('dewpoint_temperature_2m').mean().subtract(273.15)

    return (temp_mean.rename('temp_mean')
            .addBands(frost_days.rename('frost_days'))
            .addBands(solar.rename('solar_radiation'))
            .addBands(dewpoint.rename('dewpoint_mean'))
            .clip(bbox).toFloat())


def build_chirps(bbox, year):
    """Annual total precipitation from CHIRPS daily."""
    col = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
           .filter(ee.Filter.calendarRange(year, year, 'year'))
           .filterBounds(bbox)
           .select('precipitation'))
    total = col.sum()
    return total.rename('total_mm').clip(bbox).toFloat()


def build_ndvi(bbox, year):
    """Annual mean NDVI from MODIS MOD13A2 (16-day, 1km)."""
    col = (ee.ImageCollection('MODIS/061/MOD13A2')
           .filter(ee.Filter.calendarRange(year, year, 'year'))
           .filterBounds(bbox)
           .select('NDVI'))
    mean_ndvi = col.mean().multiply(0.0001)
    return mean_ndvi.rename('mean_ndvi').clip(bbox).toFloat()


def build_lst(bbox, year):
    """3-band LST: day mean, night mean, amplitude from MOD11A1."""
    col = (ee.ImageCollection('MODIS/061/MOD11A1')
           .filter(ee.Filter.calendarRange(year, year, 'year'))
           .filterBounds(bbox))

    lst_day = col.select('LST_Day_1km').mean().multiply(0.02).subtract(273.15)
    lst_night = col.select('LST_Night_1km').mean().multiply(0.02).subtract(273.15)
    amplitude = lst_day.subtract(lst_night)

    return (lst_day.rename('lst_day')
            .addBands(lst_night.rename('lst_night'))
            .addBands(amplitude.rename('lst_amplitude'))
            .clip(bbox).toFloat())


def build_npp(bbox, year):
    """Annual NPP from MODIS MOD17A3HGF."""
    col = (ee.ImageCollection('MODIS/061/MOD17A3HGF')
           .filter(ee.Filter.calendarRange(year, year, 'year'))
           .filterBounds(bbox))
    count = col.size().getInfo()
    if count == 0:
        return None
    npp = col.first().select('Npp').multiply(0.0001)
    # MOD17A3HGF uses sinusoidal CRS — reproject before clip to avoid transform errors
    return npp.rename('mean_npp').reproject(crs='EPSG:4326', scale=500).clip(bbox).toFloat()


def build_vcf(bbox, year):
    """Tree cover % from MODIS MOD44B VCF."""
    col = (ee.ImageCollection('MODIS/061/MOD44B')
           .filter(ee.Filter.calendarRange(year, year, 'year'))
           .filterBounds(bbox))
    count = col.size().getInfo()
    if count == 0:
        return None
    tree = col.first().select('Percent_Tree_Cover')
    return tree.rename('tree_cover').clip(bbox).toFloat()


# ─── Export registry ─────────────────────────────────────────────────────

COVARIATE_GROUPS = {
    'fire':   (build_fire,   500),
    'era5':   (build_era5,   11132),
    'chirps': (build_chirps, 5566),
    'ndvi':   (build_ndvi,   1000),
    'lst':    (build_lst,    1000),
    'npp':    (build_npp,    500),
    'vcf':    (build_vcf,    250),
}


def main():
    parser = argparse.ArgumentParser(
        description='Export annual PM2.5 covariate rasters to GCS')
    parser.add_argument('--only', default=None,
                        help='Comma-separated group names (fire,era5,...)')
    parser.add_argument('--years', type=int, nargs='+', default=None,
                        help=f'Specific years (default: {YEARS[0]}-{YEARS[-1]})')
    parser.add_argument('--scale', type=int, default=None,
                        help='Override export scale (m)')
    parser.add_argument('--wait', action='store_true',
                        help='Poll until all tasks complete')
    parser.add_argument('--no-wait', action='store_true',
                        help='Submit and exit immediately')
    args = parser.parse_args()

    authenticate()
    bbox = ee.Geometry.Rectangle(COMBINED_BBOX)
    years = args.years or YEARS

    groups = COVARIATE_GROUPS
    if args.only:
        keys = [k.strip() for k in args.only.split(',')]
        groups = {k: v for k, v in COVARIATE_GROUPS.items() if k in keys}
        unknown = [k for k in keys if k not in COVARIATE_GROUPS]
        if unknown:
            print(f"WARNING: unknown groups ignored: {unknown}")

    total = len(groups) * len(years)
    print(f"Combined bbox: {COMBINED_BBOX}")
    print(f"Groups: {list(groups.keys())}")
    print(f"Years: {years[0]}-{years[-1]} ({len(years)} years)")
    print(f"Total exports: {total}")
    print('=' * 60)

    tasks = []
    for group_name, (builder_fn, default_scale) in groups.items():
        scale = args.scale or default_scale
        for year in sorted(years):
            desc = f'pm25cov_{group_name}_{year}'
            gcs_path = f'{GCS_PREFIX}/{group_name}_{year}'
            try:
                image = builder_fn(bbox, year)
                if image is None:
                    print(f'  SKIP  {group_name}_{year} (no data)')
                    continue
                task = ee.batch.Export.image.toCloudStorage(
                    image=image,
                    description=desc,
                    bucket=GCS_BUCKET,
                    fileNamePrefix=gcs_path,
                    region=bbox,
                    scale=scale,
                    crs='EPSG:4326',
                    maxPixels=1e10,
                    fileFormat='GeoTIFF',
                    formatOptions={'cloudOptimized': True},
                )
                task.start()
                tasks.append((f'{group_name}_{year}', task))
                print(f'  STARTED {group_name}_{year} @ {scale}m')
            except Exception as e:
                print(f'  FAILED  {group_name}_{year}: {e}')

    print(f'\nSubmitted {len(tasks)} tasks.')

    if args.no_wait or not args.wait:
        if not args.wait:
            print('Run with --wait to poll, or monitor at '
                  'https://code.earthengine.google.com/tasks')
            print(f'\nDownload when done:')
            print(f'  gcloud storage cp -r gs://{GCS_BUCKET}/{GCS_PREFIX}/ '
                  f'pipeline/output/pm25_covariates/')
        return 0

    print(f'\nPolling {len(tasks)} tasks...')
    while True:
        statuses = [(n, t.status()['state']) for n, t in tasks]
        running = sum(1 for _, s in statuses if s in ('READY', 'RUNNING'))
        if running == 0:
            break
        completed = sum(1 for _, s in statuses if s == 'COMPLETED')
        failed = sum(1 for _, s in statuses if s == 'FAILED')
        print(f'  running={running}  completed={completed}  failed={failed}')
        time.sleep(30)

    all_ok = True
    for name, task in tasks:
        status = task.status()
        if status['state'] != 'COMPLETED':
            print(f'  FAILED: {name} -- {status.get("error_message", "?")}')
            all_ok = False

    ok_count = sum(1 for _, t in tasks if t.status()['state'] == 'COMPLETED')
    print(f'\n{ok_count}/{len(tasks)} exports completed.')
    if all_ok:
        print(f'\nDownload:')
        print(f'  gcloud storage cp -r gs://{GCS_BUCKET}/{GCS_PREFIX}/ '
              f'pipeline/output/pm25_covariates/')

    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
