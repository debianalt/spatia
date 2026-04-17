"""
Export Hansen Global Forest Change loss year raster for Misiones.

Exports a single GeoTIFF where pixel value = year of loss (0 = no loss,
1-24 = loss in 2001-2024). Also exports treecover2000 baseline.

Source: UMD/hansen/global_forest_change_2024_v1_12

Usage:
  python pipeline/gee_export_hansen_loss.py
  python pipeline/gee_export_hansen_loss.py --gcs
"""

import argparse
import ee
import json
import os
import sys
import time

from config import MISIONES_BBOX, get_territory

EXPORT_SCALE = 30  # Hansen native resolution
DRIVE_FOLDER = 'spatia-satellite'
GCS_BUCKET = 'spatia-satellite'
HANSEN = 'UMD/hansen/global_forest_change_2024_v1_12'


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


def main():
    parser = argparse.ArgumentParser(description="Export Hansen loss year raster")
    parser.add_argument("--gcs", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--territory", default="misiones",
                        help="Territory ID from config.py (default: misiones)")
    args = parser.parse_args()

    is_ci = authenticate()
    use_gcs = args.gcs or is_ci
    territory = get_territory(args.territory)
    bbox = ee.Geometry.Rectangle(territory['bbox'])
    gcs_subdir = '' if args.territory == 'misiones' else f"{args.territory}/"
    desc_suffix = '' if args.territory == 'misiones' else f"_{args.territory}"

    hansen = ee.Image(HANSEN)

    exports = [
        ('hansen_lossyear', hansen.select('lossyear').clip(bbox).toUint8()),
        ('hansen_treecover2000', hansen.select('treecover2000').clip(bbox).toUint8()),
    ]

    dest = f"GCS ({GCS_BUCKET}/satellite/{gcs_subdir})" if use_gcs else f"Drive ({DRIVE_FOLDER})"
    print(f"Exporting {len(exports)} rasters at {EXPORT_SCALE}m -> {dest} [territory={args.territory}]")

    tasks = []
    for name, image in exports:
        task_desc = f"{name}{desc_suffix}"
        if use_gcs:
            task = ee.batch.Export.image.toCloudStorage(
                image=image, description=task_desc, bucket=GCS_BUCKET,
                fileNamePrefix=f'satellite/{gcs_subdir}{name}', region=bbox,
                scale=EXPORT_SCALE, crs='EPSG:4326', maxPixels=1e10)
        else:
            task = ee.batch.Export.image.toDrive(
                image=image, description=task_desc, folder=DRIVE_FOLDER,
                fileNamePrefix=task_desc, region=bbox,
                scale=EXPORT_SCALE, crs='EPSG:4326', maxPixels=1e10)
        task.start()
        tasks.append((name, task))
        print(f"  Started: {name}")

    if args.no_wait:
        print("Tasks submitted. Monitor in GEE console.")
        return 0

    print(f"\nWaiting for {len(tasks)} exports...")
    while True:
        statuses = [(n, t.status()['state']) for n, t in tasks]
        running = sum(1 for _, s in statuses if s in ('READY', 'RUNNING'))
        if running == 0:
            break
        print(f"  [{running} running] " + ', '.join(f"{n}={s}" for n, s in statuses))
        time.sleep(30)

    for name, task in tasks:
        status = task.status()
        if status['state'] == 'COMPLETED':
            print(f"  DONE: {name}")
        else:
            print(f"  FAILED: {name} -- {status.get('error_message', 'unknown')}")

    print("\nNext: download TIFFs and run:")
    print("  python pipeline/process_hansen_to_h3.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
