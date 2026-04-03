"""
Export ESA CCI Biomass for baseline (2018-2020) and current (2022) to GCS.

Only exports the dynamic band (AGB) — other carbon bands (SOC, GFW flux,
GEDI, treecover) are static and don't need temporal variants.

Usage:
  python pipeline/gee_export_carbon_temporal.py
"""

import argparse
import ee
import json
import os
import sys
import time

from config import MISIONES_BBOX

EXPORT_SCALE = 100
GCS_BUCKET = 'spatia-satellite'


def authenticate():
    key_env = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")
    if not key_env:
        ee.Initialize()
        return False
    key_data = json.loads(key_env) if not os.path.isfile(key_env) else json.load(open(key_env))
    credentials = ee.ServiceAccountCredentials(key_data["client_email"], key_data=json.dumps(key_data))
    ee.Initialize(credentials, opt_url="https://earthengine-highvolume.googleapis.com")
    return True


def main():
    authenticate()
    bbox = ee.Geometry.Rectangle(MISIONES_BBOX)

    cci = ee.ImageCollection('projects/sat-io/open-datasets/ESA/ESA_CCI_AGB').filterBounds(bbox)

    # Baseline: average 2018-2020
    baseline = (cci.filter(ee.Filter.calendarRange(2018, 2020, 'year'))
                .select('AGB').mean()
                .rename('c_agb_baseline')
                .unmask(0).clip(bbox).toFloat())

    # Current: 2022 (latest stable year)
    current = (cci.filter(ee.Filter.calendarRange(2022, 2022, 'year'))
               .select('AGB').first()
               .rename('c_agb_current')
               .unmask(0).clip(bbox).toFloat())

    composite = baseline.addBands(current)
    print(f"Bands: {composite.bandNames().getInfo()}")

    task = ee.batch.Export.image.toCloudStorage(
        image=composite,
        description='sat_carbon_temporal_raster',
        bucket=GCS_BUCKET,
        fileNamePrefix='satellite/sat_carbon_temporal_raster',
        region=bbox, scale=EXPORT_SCALE,
        crs='EPSG:4326', maxPixels=1e9)
    task.start()
    print("Export to GCS started")

    while True:
        state = task.status()['state']
        if state == 'COMPLETED':
            print("DONE")
            break
        elif state == 'FAILED':
            print(f"FAILED: {task.status().get('error_message')}")
            return 1
        print(f"  {state}...")
        time.sleep(30)
    return 0


if __name__ == '__main__':
    sys.exit(main())
