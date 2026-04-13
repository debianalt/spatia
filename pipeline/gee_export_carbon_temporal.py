"""
Export temporal carbon stock composite for baseline vs current comparison.

Bands (8):
  1. c_agb_baseline      — ESA CCI Biomass AGB 2018-2020 mean (Mg/ha)
  2. c_agb_current       — ESA CCI Biomass AGB 2022 (Mg/ha)
  3. c_npp_baseline      — MODIS MOD17A3HGF NPP 2018-2020 mean (gC/m2/yr)
  4. c_npp_current       — MODIS MOD17A3HGF NPP 2022-2024 mean (gC/m2/yr)
  5. c_standing_tc_bl    — Standing tree cover fraction at end of 2020
  6. c_standing_tc_cur   — Standing tree cover fraction at end of 2024
  7. c_loss_rate_bl      — Annual loss fraction 2001-2020 (fraction/year)
  8. c_loss_rate_cur     — Annual loss fraction 2021-2024 (fraction/year)

Other carbon bands (SOC, GFW flux, GEDI) are genuinely static and don't
need temporal variants; they keep their single value in both tabs.

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

    # ── 1-2. ESA CCI AGB baseline (2018-2020 mean) vs current (2022) ────────
    cci = ee.ImageCollection('projects/sat-io/open-datasets/ESA/ESA_CCI_AGB').filterBounds(bbox)
    agb_bl = (cci.filter(ee.Filter.calendarRange(2018, 2020, 'year'))
              .select('AGB').mean()
              .rename('c_agb_baseline')
              .unmask(0).clip(bbox).toFloat())
    agb_cur = (cci.filter(ee.Filter.calendarRange(2022, 2022, 'year'))
               .select('AGB').first()
               .rename('c_agb_current')
               .unmask(0).clip(bbox).toFloat())

    # ── 3-4. MODIS NPP baseline (2018-2020 mean) vs current (2022-2024 mean) ─
    npp_coll = ee.ImageCollection('MODIS/061/MOD17A3HGF').filterBounds(bbox).select('Npp')
    npp_bl = (npp_coll.filter(ee.Filter.calendarRange(2018, 2020, 'year'))
              .mean().multiply(0.0001)
              .rename('c_npp_baseline')
              .unmask(0).clip(bbox).toFloat())
    npp_cur = (npp_coll.filter(ee.Filter.calendarRange(2022, 2024, 'year'))
               .mean().multiply(0.0001)
               .rename('c_npp_current')
               .unmask(0).clip(bbox).toFloat())

    # ── 5-6. Standing tree cover: treecover2000 × (1 − cumulative_loss_by_Y) ─
    hansen = ee.Image('UMD/hansen/global_forest_change_2024_v1_12')
    tc2000 = hansen.select('treecover2000').divide(100)  # 0-1 fraction
    lossyear = hansen.select('lossyear')  # 0 = no loss; 1..24 = year of loss (2001..2024)

    loss_by_2020 = lossyear.gt(0).And(lossyear.lte(20)).unmask(0).toFloat()
    loss_by_2024 = lossyear.gt(0).And(lossyear.lte(24)).unmask(0).toFloat()
    standing_tc_bl = (tc2000.multiply(ee.Image.constant(1).subtract(loss_by_2020))
                      .rename('c_standing_tc_bl')
                      .clip(bbox).toFloat())
    standing_tc_cur = (tc2000.multiply(ee.Image.constant(1).subtract(loss_by_2024))
                       .rename('c_standing_tc_cur')
                       .clip(bbox).toFloat())

    # ── 7-8. Annual loss rate: baseline 2001-2020, current 2021-2024 ────────
    loss_bl_period = lossyear.gte(1).And(lossyear.lte(20)).unmask(0).toFloat()
    loss_cur_period = lossyear.gte(21).And(lossyear.lte(24)).unmask(0).toFloat()
    loss_rate_bl = (loss_bl_period.divide(20)
                    .rename('c_loss_rate_bl')
                    .clip(bbox).toFloat())
    loss_rate_cur = (loss_cur_period.divide(4)
                     .rename('c_loss_rate_cur')
                     .clip(bbox).toFloat())

    composite = (agb_bl.addBands(agb_cur)
                 .addBands(npp_bl).addBands(npp_cur)
                 .addBands(standing_tc_bl).addBands(standing_tc_cur)
                 .addBands(loss_rate_bl).addBands(loss_rate_cur))
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
