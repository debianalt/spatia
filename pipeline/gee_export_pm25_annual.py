"""
Export annual PM2.5 rasters from ACAG V6 for time-series analysis.

Exports one GeoTIFF per year (single band: PM2.5 µg/m³) to Google Drive
or GCS.  These annual rasters feed the predictive modelling pipeline.

Source:
  ACAG / Van Donkelaar V6 annual surface PM2.5 (0.01°, ~1 km)
  Collection: projects/sat-io/open-datasets/GLOBAL-SATELLITE-PM25/ANNUAL

Usage:
  python pipeline/gee_export_pm25_annual.py
  python pipeline/gee_export_pm25_annual.py --years 2019 2020 2021
  python pipeline/gee_export_pm25_annual.py --gcs
"""

import argparse
import ee
import json
import os
import sys
import time

from config import MISIONES_BBOX

EXPORT_SCALE = 100  # metres — match existing pipeline resolution
DRIVE_FOLDER = 'spatia-satellite'
GCS_BUCKET = 'spatia-satellite'
COLLECTION = 'projects/sat-io/open-datasets/GLOBAL-SATELLITE-PM25/ANNUAL'


def authenticate():
    """Authenticate to GEE — service account in CI, user credentials locally."""
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
        key_data["client_email"],
        key_data=json.dumps(key_data),
    )
    ee.Initialize(credentials, opt_url="https://earthengine-highvolume.googleapis.com")
    return True


def list_available_years(bbox):
    """Query GEE for available years in the ACAG PM2.5 collection."""
    col = ee.ImageCollection(COLLECTION).filterBounds(bbox)
    dates = col.aggregate_array('system:time_start').getInfo()
    if not dates:
        return []
    from datetime import datetime, timezone
    years = sorted(set(datetime.fromtimestamp(d / 1000, tz=timezone.utc).year for d in dates))
    return years


def main():
    parser = argparse.ArgumentParser(description="Export annual PM2.5 rasters from ACAG V6")
    parser.add_argument("--years", type=int, nargs="+", default=None,
                        help="Specific years to export (default: all available)")
    parser.add_argument("--scale", type=int, default=EXPORT_SCALE,
                        help=f"Export scale in metres (default: {EXPORT_SCALE})")
    parser.add_argument("--gcs", action="store_true",
                        help="Force export to GCS (default: auto-detect CI)")
    parser.add_argument("--no-wait", action="store_true",
                        help="Submit tasks and exit without waiting")
    args = parser.parse_args()

    is_ci = authenticate()
    use_gcs = args.gcs or is_ci
    bbox = ee.Geometry.Rectangle(MISIONES_BBOX)

    # Discover available years
    print("Querying ACAG V6 collection for available years...")
    available = list_available_years(bbox)
    if not available:
        print("ERROR: No images found in ACAG collection.")
        return 1
    print(f"  Available years: {available[0]}–{available[-1]} ({len(available)} images)")

    years = args.years if args.years else available
    missing = [y for y in years if y not in available]
    if missing:
        print(f"  WARNING: requested years not in collection: {missing}")
        years = [y for y in years if y in available]

    if not years:
        print("No valid years to export.")
        return 1

    dest = f"GCS ({GCS_BUCKET})" if use_gcs else f"Drive ({DRIVE_FOLDER})"
    print(f"\nExporting {len(years)} annual PM2.5 rasters at {args.scale}m -> {dest}")

    tasks = []
    for year in sorted(years):
        pm25 = (ee.ImageCollection(COLLECTION)
                .filter(ee.Filter.calendarRange(year, year, 'year'))
                .first()
                .rename('pm25')
                .clip(bbox)
                .toFloat())

        file_name = f'sat_pm25_{year}'

        if use_gcs:
            task = ee.batch.Export.image.toCloudStorage(
                image=pm25,
                description=file_name,
                bucket=GCS_BUCKET,
                fileNamePrefix=f'satellite/{file_name}',
                region=bbox,
                scale=args.scale,
                crs='EPSG:4326',
                maxPixels=1e9,
            )
        else:
            task = ee.batch.Export.image.toDrive(
                image=pm25,
                description=file_name,
                folder=DRIVE_FOLDER,
                fileNamePrefix=file_name,
                region=bbox,
                scale=args.scale,
                crs='EPSG:4326',
                maxPixels=1e9,
            )
        task.start()
        tasks.append((year, task))
        print(f"  Started: {file_name}")

    if args.no_wait:
        print(f"\n{len(tasks)} tasks submitted. Use GEE console to monitor.")
        return 0

    # Poll for completion
    print(f"\nWaiting for {len(tasks)} exports...")
    while True:
        statuses = [(y, t.status()['state']) for y, t in tasks]
        running = sum(1 for _, s in statuses if s in ('READY', 'RUNNING'))
        if running == 0:
            break
        status_str = ', '.join(f"{y}={s}" for y, s in statuses)
        print(f"  [{running} running] {status_str}")
        time.sleep(30)

    # Report
    print(f"\n{'=' * 60}")
    all_ok = True
    for year, task in tasks:
        status = task.status()
        if status['state'] == 'COMPLETED':
            print(f"  DONE: sat_pm25_{year}")
        else:
            print(f"  FAILED: sat_pm25_{year} — {status.get('error_message', 'unknown')}")
            all_ok = False

    print(f"\nNext step: download TIFFs and run:")
    print(f"  python pipeline/process_pm25_annual_to_h3.py")
    print(f"{'=' * 60}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
