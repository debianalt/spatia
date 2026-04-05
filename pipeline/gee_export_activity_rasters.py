"""
Export activity indicator rasters from GEE for H3 centroid sampling.

Exports 5 composites (baseline + current period each):
  1. VIIRS nightlights (DNB annual composite)
  2. MODIS NPP (MOD17A3HGF)
  3. MODIS NDVI (MOD13Q1 annual mean)
  4. GHSL built surface (JRC)
  5. MODIS LST day (MOD11A2 annual mean)

Hansen already exported separately.

Usage:
  python pipeline/gee_export_activity_rasters.py
  python pipeline/gee_export_activity_rasters.py --no-wait
"""

import argparse
import ee
import json
import os
import sys
import time

from config import MISIONES_BBOX

DRIVE_FOLDER = 'spatia-satellite'
SCALE = 250  # compromise: NDVI=250m, others coarser but resampled


def authenticate():
    key_env = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")
    if not key_env:
        ee.Initialize()
        return False
    if os.path.isfile(key_env):
        with open(key_env) as f:
            key_data = json.load(f)
    else:
        key_data = json.loads(key_env)
    credentials = ee.ServiceAccountCredentials(
        key_data["client_email"], key_data=json.dumps(key_data))
    ee.Initialize(credentials, opt_url="https://earthengine-highvolume.googleapis.com")
    return True


def viirs_composite(years):
    """VIIRS DNB annual composite mean radiance."""
    imgs = []
    for y in years:
        img = (ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG')
               .filter(ee.Filter.calendarRange(y, y, 'year'))
               .select('avg_rad')
               .mean())
        imgs.append(img)
    return ee.ImageCollection(imgs).mean().rename('viirs').toFloat()


def npp_composite(years):
    """MODIS NPP annual (MOD17A3HGF)."""
    imgs = []
    for y in years:
        img = (ee.ImageCollection('MODIS/061/MOD17A3HGF')
               .filter(ee.Filter.calendarRange(y, y, 'year'))
               .select('Npp')
               .first())
        if img:
            imgs.append(img.multiply(0.0001))  # scale factor
    return ee.ImageCollection(imgs).mean().rename('npp').toFloat()


def ndvi_composite(years):
    """MODIS NDVI annual mean (MOD13Q1, 250m)."""
    imgs = []
    for y in years:
        img = (ee.ImageCollection('MODIS/061/MOD13Q1')
               .filter(ee.Filter.calendarRange(y, y, 'year'))
               .select('NDVI')
               .mean()
               .multiply(0.0001))  # scale factor
        imgs.append(img)
    return ee.ImageCollection(imgs).mean().rename('ndvi').toFloat()


def lst_composite(years):
    """MODIS LST day annual mean (MOD11A2, 1km)."""
    imgs = []
    for y in years:
        img = (ee.ImageCollection('MODIS/061/MOD11A2')
               .filter(ee.Filter.calendarRange(y, y, 'year'))
               .select('LST_Day_1km')
               .mean()
               .multiply(0.02)
               .subtract(273.15))  # Kelvin to Celsius
        imgs.append(img)
    return ee.ImageCollection(imgs).mean().rename('lst').toFloat()


def ghsl_built(epoch):
    """GHSL built surface fraction for a given epoch."""
    return (ee.Image('JRC/GHSL/P2023A/GHS_BUILT_S/2030')
            .select(f'built_surface_{epoch}')
            .rename('built')
            .toFloat())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args()

    authenticate()
    bbox = ee.Geometry.Rectangle(MISIONES_BBOX)

    # Define periods
    baseline_years = list(range(2014, 2018))  # VIIRS starts 2014
    current_years = list(range(2021, 2025))
    baseline_years_long = list(range(2005, 2013))
    current_years_long = list(range(2017, 2025))

    exports = [
        ('act_viirs_current', viirs_composite(current_years).clip(bbox)),
        ('act_viirs_baseline', viirs_composite(baseline_years).clip(bbox)),
        ('act_npp_current', npp_composite(current_years_long).clip(bbox)),
        ('act_npp_baseline', npp_composite(baseline_years_long).clip(bbox)),
        ('act_ndvi_current', ndvi_composite(current_years_long).clip(bbox)),
        ('act_ndvi_baseline', ndvi_composite(baseline_years_long).clip(bbox)),
        ('act_lst_current', lst_composite(current_years_long).clip(bbox)),
        ('act_lst_baseline', lst_composite(baseline_years_long).clip(bbox)),
        ('act_ghsl_current', ghsl_built(2020).clip(bbox)),
        ('act_ghsl_baseline', ghsl_built(2000).clip(bbox)),
    ]

    print(f"Exporting {len(exports)} rasters at {SCALE}m -> Drive ({DRIVE_FOLDER})")

    tasks = []
    for name, image in exports:
        task = ee.batch.Export.image.toDrive(
            image=image, description=name, folder=DRIVE_FOLDER,
            fileNamePrefix=name, region=bbox,
            scale=SCALE, crs='EPSG:4326', maxPixels=1e9)
        task.start()
        tasks.append((name, task))
        print(f"  Started: {name}")

    if args.no_wait:
        print("Tasks submitted.")
        return 0

    print(f"\nWaiting for {len(tasks)} exports...")
    while True:
        statuses = [(n, t.status()['state']) for n, t in tasks]
        running = sum(1 for _, s in statuses if s in ('READY', 'RUNNING'))
        if running == 0:
            break
        print(f"  [{running} running]")
        time.sleep(30)

    for name, task in tasks:
        s = task.status()
        state = 'DONE' if s['state'] == 'COMPLETED' else f"FAILED: {s.get('error_message', '')}"
        print(f"  {name}: {state}")

    print("\nNext: python pipeline/download_from_drive.py --pattern 'act_*.tif'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
