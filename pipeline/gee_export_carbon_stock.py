"""
Export carbon stock & flux composite from GEE.

Bands:
  1. c_agb_cci    — ESA CCI Biomass v6 AGB (Mg/ha), 100m
  2. c_agb_gedi   — GEDI L4B gridded AGB mean (Mg/ha), 1km resampled
  3. c_gedi_se    — GEDI L4B standard error (Mg/ha)
  4. c_soc        — SoilGrids SOC 0-5cm (dg/kg)
  5. c_npp        — MODIS MOD17A3HGF NPP (gC/m2/yr, scaled)
  6. c_treecover  — Hansen treecover2000 (0-1)
  7. c_loss       — Hansen cumulative loss 2001-2024 (0/1)
  8. c_emissions  — GFW gross emissions (MgCO2/ha)
  9. c_removals   — GFW gross removals (MgCO2/ha)
  10. c_net_flux  — GFW net carbon flux (MgCO2/ha)

Usage:
  python pipeline/gee_export_carbon_stock.py
"""

import argparse
import ee
import json
import os
import sys
import time

from config import OUTPUT_DIR, get_territory

EXPORT_SCALE = 100
DRIVE_FOLDER = 'spatia-satellite'


def authenticate():
    key_env = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")
    if not key_env:
        ee.Initialize()
        return False
    key_data = json.loads(key_env) if not os.path.isfile(key_env) else json.load(open(key_env))
    credentials = ee.ServiceAccountCredentials(key_data["client_email"], key_data=json.dumps(key_data))
    ee.Initialize(credentials, opt_url="https://earthengine-highvolume.googleapis.com")
    return True


def build_carbon_stock(bbox):
    """Build 10-band carbon stock & flux composite."""

    # 1. ESA CCI Biomass — AGB in Mg/ha, 100m native
    # Use latest available year (2020)
    cci = (ee.ImageCollection('projects/sat-io/open-datasets/ESA/ESA_CCI_AGB')
           .filterBounds(bbox)
           .sort('system:time_start', False)
           .first()
           .select('AGB')
           .rename('c_agb_cci')
           .unmask(0)
           .clip(bbox).toFloat())

    # 2-3. GEDI L4B — Gridded AGB (Mg/ha) + SE, 1km native
    gedi = (ee.Image('LARSE/GEDI/GEDI04_B_002')
            .select(['MU', 'SE'])
            .rename(['c_agb_gedi', 'c_gedi_se'])
            .unmask(0)
            .clip(bbox).toFloat())

    # 4. SoilGrids SOC — 0-5cm mean in dg/kg
    soc = (ee.Image('projects/soilgrids-isric/ocd_mean')
           .select('ocd_0-5cm_mean')
           .rename('c_soc')
           .unmask(0)
           .clip(bbox).toFloat())

    # 5. MODIS NPP — 2019-2024 mean, scaled to gC/m2/yr
    npp = (ee.ImageCollection('MODIS/061/MOD17A3HGF')
           .filterDate('2019-01-01', '2024-12-31')
           .filterBounds(bbox)
           .select('Npp')
           .mean()
           .multiply(0.0001)
           .rename('c_npp')
           .clip(bbox).toFloat())

    # 6. Hansen tree cover 2000 (0-1 fraction)
    hansen = ee.Image('UMD/hansen/global_forest_change_2024_v1_12')
    treecover = (hansen.select('treecover2000')
                 .divide(100)
                 .rename('c_treecover')
                 .clip(bbox).toFloat())

    # 7. Hansen cumulative loss (binary 0/1)
    loss = (hansen.select('loss')
            .rename('c_loss')
            .clip(bbox).toFloat())

    # 8-10. GFW Carbon Flux (Harris et al. 2021) — MgCO2/ha cumulative
    try:
        emissions = (ee.Image('projects/sat-io/open-datasets/forest_carbon_fluxes/gross_emissions')
                     .rename('c_emissions')
                     .unmask(0)
                     .clip(bbox).toFloat())
        removals = (ee.Image('projects/sat-io/open-datasets/forest_carbon_fluxes/gross_removals')
                    .rename('c_removals')
                    .unmask(0)
                    .clip(bbox).toFloat())
        net_flux = (ee.Image('projects/sat-io/open-datasets/forest_carbon_fluxes/net_flux')
                    .rename('c_net_flux')
                    .unmask(0)
                    .clip(bbox).toFloat())
    except Exception as e:
        print(f"  WARN: GFW carbon flux not available ({e}), using zeros")
        zero = ee.Image.constant(0).rename('placeholder').clip(bbox).toFloat()
        emissions = zero.rename('c_emissions')
        removals = zero.rename('c_removals')
        net_flux = zero.rename('c_net_flux')

    composite = (cci
                 .addBands(gedi)
                 .addBands(soc)
                 .addBands(npp)
                 .addBands(treecover)
                 .addBands(loss)
                 .addBands(emissions)
                 .addBands(removals)
                 .addBands(net_flux))

    print(f"    Bands: {composite.bandNames().getInfo()}")
    return composite


def main():
    parser = argparse.ArgumentParser(description="Export carbon stock composite from GEE")
    parser.add_argument("--territory", default="misiones", help="Territory ID (default: misiones)")
    parser.add_argument("--gcs", action="store_true", help="Force export to GCS")
    parser.add_argument("--scale", type=int, default=EXPORT_SCALE)
    parser.add_argument("--no-wait", action="store_true", help="Submit task and exit without polling")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    territory_bbox = territory['bbox']  # [west, south, east, north]

    is_ci = authenticate()
    use_gcs = args.gcs or is_ci
    bbox = ee.Geometry.Rectangle(territory_bbox)

    print(f"Territory: {territory['label']} — bbox: {territory_bbox}")
    print("Building carbon stock composite...")
    composite = build_carbon_stock(bbox)

    file_name = 'sat_carbon_stock_raster'
    gcs_prefix = f"satellite/{args.territory}/{file_name}"
    if use_gcs:
        task = ee.batch.Export.image.toCloudStorage(
            image=composite,
            description=f"{args.territory}_{file_name}",
            bucket='spatia-satellite',
            fileNamePrefix=gcs_prefix,
            region=bbox, scale=args.scale,
            crs='EPSG:4326', maxPixels=1e9)
    else:
        task = ee.batch.Export.image.toDrive(
            image=composite,
            description=file_name,
            folder=DRIVE_FOLDER,
            fileNamePrefix=file_name,
            region=bbox, scale=args.scale,
            crs='EPSG:4326', maxPixels=1e9)
    task.start()
    print(f"  Export started: {file_name} -> {'GCS' if use_gcs else 'Drive'}")
    print(f"  Task ID: {task.id}")

    if args.no_wait:
        print("  --no-wait: exiting. Monitor at https://code.earthengine.google.com/tasks")
        return 0

    print("\nWaiting for export to complete...")
    while True:
        status = task.status()
        state = status['state']
        if state == 'COMPLETED':
            print("  DONE")
            break
        elif state == 'FAILED':
            print(f"  FAILED: {status.get('error_message', 'unknown')}")
            return 1
        print(f"  {state}...")
        time.sleep(30)

    return 0


if __name__ == '__main__':
    sys.exit(main())
