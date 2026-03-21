"""
Google Earth Engine: Export Dynamic World LULC for Misiones.

Creates a monthly composite of the most frequent land cover class,
renders it as an RGB GeoTIFF with the official Dynamic World palette,
and exports to Google Cloud Storage.

Usage:
  python pipeline/gee_dynamic_world.py
  python pipeline/gee_dynamic_world.py --months 3  # last 3 months composite

Output:
  gs://spatia-satellite/lulc/lulc_YYYYMMDD.tif
  pipeline/output/lulc_misiones.tif (downloaded)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

import ee

from config import MISIONES_BBOX, GCS_BUCKET, OUTPUT_DIR

# Dynamic World class palette (official colors)
DW_PALETTE = [
    '419BDF',  # 0: water
    '397D49',  # 1: trees
    '88B053',  # 2: grass
    '7A87C6',  # 3: flooded vegetation
    'E49635',  # 4: crops
    'DFC35A',  # 5: shrub & scrub
    'C4281B',  # 6: built area
    'A59B8F',  # 7: bare ground
    'B39FE1',  # 8: snow & ice
]


def authenticate():
    """Authenticate to GEE using service account or default credentials."""
    key_env = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")

    if not key_env:
        ee.Initialize(opt_url="https://earthengine-highvolume.googleapis.com")
        return

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


def export_dynamic_world(months=1):
    """Export Dynamic World LULC composite for Misiones."""
    aoi = ee.Geometry.Rectangle(MISIONES_BBOX)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=months * 30)

    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    # Get Dynamic World collection
    dw = (ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
          .filterBounds(aoi)
          .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

    count = dw.size().getInfo()
    print(f"Found {count} Dynamic World scenes")

    if count == 0:
        print("ERROR: No scenes found. Try increasing --months")
        return None

    # Mode composite: most frequent class per pixel
    label = dw.select('label').mode().clip(aoi)

    # Visualize with palette
    vis = label.visualize(min=0, max=8, palette=DW_PALETTE)

    # Export as RGB GeoTIFF to GCS
    date_str = end_date.strftime('%Y%m%d')
    description = f'lulc_{date_str}'

    task = ee.batch.Export.image.toCloudStorage(
        image=vis,
        description=description,
        bucket=GCS_BUCKET,
        fileNamePrefix=f'lulc/{description}',
        region=aoi,
        scale=10,
        crs='EPSG:4326',
        maxPixels=1e9,
        fileFormat='GeoTIFF',
    )
    task.start()
    print(f"Export task started: {description}")
    return task


def wait_for_task(task, poll_interval=30, timeout=3600):
    """Poll GEE task until completion."""
    start = time.time()
    while True:
        status = task.status()
        state = status.get('state', 'UNKNOWN')
        elapsed = int(time.time() - start)

        if state == 'COMPLETED':
            print(f"  Task completed in {elapsed}s")
            return True
        elif state in ('FAILED', 'CANCELLED'):
            print(f"  Task {state}: {status.get('error_message', 'unknown error')}")
            return False
        elif elapsed > timeout:
            print(f"  Timeout after {elapsed}s")
            return False

        print(f"  [{elapsed}s] State: {state}...")
        time.sleep(poll_interval)


def download_from_gcs(date_str=None):
    """Download the LULC GeoTIFF from GCS."""
    from google.cloud import storage as gcs

    key_env = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")
    if key_env and os.path.isfile(key_env):
        client = gcs.Client.from_service_account_json(key_env)
    elif key_env:
        from google.oauth2 import service_account
        key_data = json.loads(key_env)
        credentials = service_account.Credentials.from_service_account_info(key_data)
        client = gcs.Client(credentials=credentials, project=key_data.get("project_id"))
    else:
        client = gcs.Client()

    bucket = client.bucket(GCS_BUCKET)
    blobs = list(bucket.list_blobs(prefix='lulc/'))
    tifs = sorted([b for b in blobs if b.name.endswith('.tif')],
                  key=lambda b: b.updated, reverse=True)

    if not tifs:
        print("No LULC GeoTIFFs found in GCS")
        return None

    blob = tifs[0]
    local_path = os.path.join(OUTPUT_DIR, 'lulc_misiones.tif')
    print(f"Downloading {blob.name} ({blob.size / 1e6:.1f} MB)...")
    blob.download_to_filename(local_path)
    print(f"  -> {local_path}")
    return local_path


def main():
    parser = argparse.ArgumentParser(description="Export Dynamic World LULC for Misiones")
    parser.add_argument("--months", type=int, default=1,
                        help="Number of months for composite (default: 1)")
    parser.add_argument("--skip-export", action="store_true",
                        help="Skip GEE export, only download")
    args = parser.parse_args()

    authenticate()
    print("Authenticated to GEE")

    if not args.skip_export:
        task = export_dynamic_world(months=args.months)
        if task is None:
            sys.exit(1)

        print("\nWaiting for export...")
        if not wait_for_task(task):
            sys.exit(1)

    print("\nDownloading from GCS...")
    local_path = download_from_gcs()
    if local_path:
        print(f"\nDone: {local_path}")
        print(f"Next: python pipeline/generate_lulc_tiles.py")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
