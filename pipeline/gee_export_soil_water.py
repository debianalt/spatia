"""
Google Earth Engine: Soil Water Balance export for Misiones and Itapúa.

Exports a 4-band GeoTIFF per territory to GCS. Bands:
  c_soil_moisture  — ERA5-Land annual mean root-zone soil water (0-100cm, depth-weighted)
  c_dry_season     — Same but Jun-Aug only (dry season stress)
  c_water_balance  — ERA5-Land annual P - |PET| (mm/yr, positive = surplus)
  c_awc            — SoilGrids v2 available water capacity = FC - PWP (depth-weighted, 0-100cm)

Date range: 2019-2024 (consistent with other satellite analyses).

Usage:
  python pipeline/gee_export_soil_water.py --territory misiones [--wait]
  python pipeline/gee_export_soil_water.py --territory itapua_py [--wait]

Environment:
  GEE_SERVICE_ACCOUNT_KEY  — path to JSON key or JSON string (optional, falls back to OAuth)
"""

import argparse
import json
import os
import sys
import time

import ee

from config import GCS_BUCKET, get_territory

DATE_START = '2019-01-01'
DATE_END   = '2024-12-31'
EXPORT_SCALE = 100    # Match other satellite analyses; ERA5/CHIRPS resampled to 100m for H3 res-9
EXPORT_PREFIX = 'soil_water'

# ERA5-Land volumetric soil water layer depths (cm)
ERA5_LAYER_DEPTHS = {
    'volumetric_soil_water_layer_1': 7,   # 0–7 cm
    'volumetric_soil_water_layer_2': 21,  # 7–28 cm
    'volumetric_soil_water_layer_3': 72,  # 28–100 cm
}
ERA5_ROOT_ZONE_TOTAL = sum(ERA5_LAYER_DEPTHS.values())  # 100 cm

DRY_MONTHS = [6, 7, 8]  # Jun-Aug (Southern Hemisphere dry season)


def authenticate():
    key_env = os.environ.get('GEE_SERVICE_ACCOUNT_KEY', '')
    if not key_env:
        ee.Initialize(opt_url='https://earthengine-highvolume.googleapis.com')
        return
    if os.path.isfile(key_env):
        with open(key_env) as f:
            key_data = json.load(f)
    else:
        key_data = json.loads(key_env)
    credentials = ee.ServiceAccountCredentials(
        key_data['client_email'],
        key_data=json.dumps(key_data),
    )
    ee.Initialize(credentials, opt_url='https://earthengine-highvolume.googleapis.com')


def depth_weighted_soil_water(col: ee.ImageCollection, months: list[int] | None = None) -> ee.Image:
    """Depth-weighted mean root-zone soil water from ERA5-Land layers 1-3 (0-100cm)."""
    if months:
        col = col.filter(ee.Filter.calendarRange(months[0], months[-1], 'month'))

    weighted = None
    for band, depth_cm in ERA5_LAYER_DEPTHS.items():
        w = depth_cm / ERA5_ROOT_ZONE_TOTAL
        layer = col.select(band).mean().multiply(w)
        weighted = layer if weighted is None else weighted.add(layer)
    return weighted


def compute_soil_moisture(aoi: ee.Geometry) -> ee.Image:
    """Annual mean root-zone soil water (m³/m³), ERA5-Land 2019-2024."""
    col = (ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
           .filterDate(DATE_START, DATE_END)
           .filterBounds(aoi)
           .select(list(ERA5_LAYER_DEPTHS.keys())))
    return depth_weighted_soil_water(col).rename('c_soil_moisture').toFloat()


def compute_dry_season(aoi: ee.Geometry) -> ee.Image:
    """Jun-Aug mean root-zone soil water (m³/m³), ERA5-Land 2019-2024."""
    col = (ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
           .filterDate(DATE_START, DATE_END)
           .filterBounds(aoi)
           .select(list(ERA5_LAYER_DEPTHS.keys())))
    return depth_weighted_soil_water(col, months=DRY_MONTHS).rename('c_dry_season').toFloat()


def compute_precipitation(aoi: ee.Geometry) -> ee.Image:
    """
    Annual mean precipitation (mm/yr) from CHIRPS daily, 2019-2024.
    Independent from ERA5 soil moisture — captures the water input signal.
    """
    precip = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
              .filterDate(DATE_START, DATE_END)
              .filterBounds(aoi)
              .select('precipitation')
              .sum()
              .divide(6))  # 6 years → annual mean (mm/yr)
    return precip.rename('c_precipitation').toFloat()


def compute_actual_et(aoi: ee.Geometry) -> ee.Image:
    """
    Mean actual evapotranspiration (mm/8day) from MODIS MOD16A2GF, 2019-2024.
    High ET = vegetation actively transpiring = water available to the ecosystem.
    Scale factor 0.1 applied (MOD16 stores ET × 10).
    """
    et = (ee.ImageCollection('MODIS/061/MOD16A2GF')
          .filterDate(DATE_START, DATE_END)
          .filterBounds(aoi)
          .select('ET')
          .mean()
          .multiply(0.1))
    return et.rename('c_actual_et').toFloat()


def build_soil_water(aoi: ee.Geometry) -> ee.Image:
    """Assemble 4-band soil water composite."""
    print('  Computing c_soil_moisture (ERA5-Land annual mean)...')
    soil_moisture = compute_soil_moisture(aoi)

    print('  Computing c_dry_season (ERA5-Land Jun-Aug mean)...')
    dry_season = compute_dry_season(aoi)

    print('  Computing c_precipitation (CHIRPS annual mean, mm/yr)...')
    water_balance = compute_precipitation(aoi)

    print('  Computing c_actual_et (MODIS MOD16 mean ET)...')
    actual_et = compute_actual_et(aoi)

    return (soil_moisture
            .addBands(dry_season)
            .addBands(water_balance)   # c_precipitation
            .addBands(actual_et)
            .clip(aoi))


def export_to_gcs(image: ee.Image, description: str, aoi: ee.Geometry, territory_id: str) -> ee.batch.Task:
    task = ee.batch.Export.image.toCloudStorage(
        image=image,
        description=description,
        bucket=GCS_BUCKET,
        fileNamePrefix=f'{EXPORT_PREFIX}/{territory_id}/{description}',
        region=aoi,
        scale=EXPORT_SCALE,
        crs='EPSG:4326',
        maxPixels=1e10,
        fileFormat='GeoTIFF',
    )
    task.start()
    print(f'  -> Export started: {description} (task ID: {task.id})')
    return task


def wait_for_tasks(tasks: list, poll_interval: int = 60, timeout: int = 7200):
    if not tasks:
        return []
    start_time = time.time()
    completed = {}
    print(f'\nWaiting for {len(tasks)} GEE task(s)...')
    while len(completed) < len(tasks):
        elapsed = time.time() - start_time
        if elapsed > timeout:
            pending = [t.id for t in tasks if t.id not in completed]
            raise RuntimeError(f'Timeout after {timeout/3600:.1f}h. Pending: {pending}')
        statuses = ee.data.getTaskStatus([t.id for t in tasks])
        for status in statuses:
            tid = status['id']
            if tid in completed:
                continue
            state = status['state']
            if state == 'COMPLETED':
                desc = status.get('description', tid)
                uri = status.get('destination_uris', [''])[0]
                print(f'  [OK] {desc} — {uri}')
                completed[tid] = status
            elif state in ('FAILED', 'CANCELLED'):
                desc = status.get('description', tid)
                err = status.get('error_message', 'unknown error')
                raise RuntimeError(f'Task {desc} {state}: {err}')
        if len(completed) < len(tasks):
            mins = int(elapsed // 60)
            print(f'  [{mins}m] {len(tasks) - len(completed)} task(s) still running...', flush=True)
            time.sleep(poll_interval)
    print(f'All {len(tasks)} task(s) completed in {int((time.time() - start_time) // 60)}m.')
    return list(completed.values())


def launch_export(territory_id: str = 'misiones') -> list:
    territory = get_territory(territory_id)
    aoi = ee.Geometry.Rectangle(territory['bbox'])
    print(f'\nBuilding soil water composite [{territory["label"]}]...')
    image = build_soil_water(aoi)
    task = export_to_gcs(image, 'sat_soil_water_raster', aoi, territory_id)
    return [task]


def main():
    parser = argparse.ArgumentParser(description='Soil water balance GEE export')
    parser.add_argument('--territory', default='misiones',
                        help='Territory ID: misiones | itapua_py (default: misiones)')
    parser.add_argument('--wait', action='store_true',
                        help='Poll tasks until completion')
    args = parser.parse_args()

    print('Authenticating to Google Earth Engine...')
    authenticate()

    tasks = launch_export(territory_id=args.territory)

    if args.wait and tasks:
        wait_for_tasks(tasks)
    else:
        print('\nMonitor progress at: https://code.earthengine.google.com/tasks')
        print(f'Then download: gcloud storage cp gs://{GCS_BUCKET}/{EXPORT_PREFIX}/{args.territory}/sat_soil_water_raster.tif pipeline/output/')


if __name__ == '__main__':
    main()
