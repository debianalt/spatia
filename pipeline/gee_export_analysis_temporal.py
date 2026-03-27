"""
Export baseline + current GEE composites for temporal change detection.

Each analysis exports TWO GeoTIFFs — one for the baseline period (2019-2021)
and one for the current period (last 6 months). Only dynamic bands are exported
in both windows; fixed bands (slope, HAND, soil) come from the original export.

Usage:
  python pipeline/gee_export_analysis_temporal.py --analysis green_capital --mode both
  python pipeline/gee_export_analysis_temporal.py --analysis all --mode current
  python pipeline/gee_export_analysis_temporal.py --analysis all --mode baseline
"""

import argparse
import ee
import json
import os
import sys
import time

from config import (MISIONES_BBOX, OUTPUT_DIR,
                    BASELINE_START, BASELINE_END, CURRENT_START, CURRENT_END)

EXPORT_SCALE = 100
DRIVE_FOLDER = 'spatia-satellite'
GCS_BUCKET = 'spatia-satellite'

# Fallback year for annual-only datasets (NPP, VCF) when current window has no data
ANNUAL_FALLBACK_YEAR = '2024'


def _safe_annual_mean(collection_id, band, bbox, date_start, date_end):
    """Get mean from collection, falling back to latest full year if window is empty."""
    col = (ee.ImageCollection(collection_id)
           .filterDate(date_start, date_end).filterBounds(bbox)
           .select(band))
    # Try the requested window first; if empty, fall back to latest full year
    fallback = (ee.ImageCollection(collection_id)
                .filterDate(f'{ANNUAL_FALLBACK_YEAR}-01-01', f'{ANNUAL_FALLBACK_YEAR}-12-31')
                .filterBounds(bbox).select(band))
    # Use ee.Algorithms.If to pick non-empty collection
    size = col.size()
    return ee.Image(ee.Algorithms.If(size.gt(0), col.mean(), fallback.mean()))


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
        key_data["client_email"], key_data=json.dumps(key_data))
    ee.Initialize(credentials, opt_url="https://earthengine-highvolume.googleapis.com")
    return True


# ── Dynamic band builders ────────────────────────────────────────────────
# Each returns an ee.Image with ONLY the dynamic bands for a given time window.
# Fixed bands (slope, HAND, soil, Hansen baseline) are NOT included here;
# they are exported once in the original gee_export_analysis.py.

def dynamic_environmental_risk(bbox, date_start, date_end):
    """Dynamic: fire frequency + thermal amplitude."""
    fire = (ee.ImageCollection('MODIS/061/MCD64A1')
            .filterDate(date_start, date_end).filterBounds(bbox)
            .select('BurnDate').map(lambda img: img.gt(0).unmask(0))
            .mean())

    lst_col = (ee.ImageCollection('MODIS/061/MOD11A2')
               .filterDate(date_start, date_end).filterBounds(bbox))
    lst_day = lst_col.select('LST_Day_1km').mean().multiply(0.02).subtract(273.15)
    lst_night = lst_col.select('LST_Night_1km').mean().multiply(0.02).subtract(273.15)
    thermal_amp = lst_day.subtract(lst_night).max(0)

    return (fire.rename('c_fire')
            .addBands(thermal_amp.rename('c_thermal_amp'))
            .clip(bbox).toFloat())


def dynamic_climate_comfort(bbox, date_start, date_end):
    """Dynamic: all 5 components are temporal."""
    lst_col = (ee.ImageCollection('MODIS/061/MOD11A2')
               .filterDate(date_start, date_end).filterBounds(bbox))
    heat_day = lst_col.select('LST_Day_1km').mean().multiply(0.02).subtract(273.15)
    heat_night = lst_col.select('LST_Night_1km').mean().multiply(0.02).subtract(273.15)

    # Compute number of years for annualising
    start_y = int(date_start[:4])
    end_y = int(date_end[:4])
    n_years = max(1, end_y - start_y + 1)

    precip = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
              .filterDate(date_start, date_end).filterBounds(bbox)
              .select('precipitation').sum()
              .divide(n_years))

    era5 = (ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
            .filterDate(date_start, date_end).filterBounds(bbox))
    frost = era5.select('temperature_2m').map(
        lambda img: img.lt(273.15).unmask(0)
    ).sum().divide(n_years)

    et_col = (ee.ImageCollection('MODIS/061/MOD16A2GF')
              .filterDate(date_start, date_end).filterBounds(bbox))
    et = et_col.select('ET').mean().multiply(0.1)
    pet = et_col.select('PET').mean().multiply(0.1)
    et_pet = et.divide(pet.max(1))

    return (heat_day.rename('c_heat_day')
            .addBands(heat_night.rename('c_heat_night'))
            .addBands(precip.rename('c_precipitation'))
            .addBands(frost.rename('c_frost'))
            .addBands(et_pet.rename('c_water_stress'))
            .clip(bbox).toFloat())


def dynamic_green_capital(bbox, date_start, date_end):
    """Dynamic: NDVI, NPP, LAI, VCF (treecover2000 is fixed).
    NPP (MOD17A3HGF) and VCF (MOD44B) are annual products — use safe fallback."""
    ndvi = (ee.ImageCollection('MODIS/061/MOD13Q1')
            .filterDate(date_start, date_end).filterBounds(bbox)
            .select('NDVI').mean().multiply(0.0001))

    npp = _safe_annual_mean('MODIS/061/MOD17A3HGF', 'Npp',
                            bbox, date_start, date_end).multiply(0.0001)

    lai = (ee.ImageCollection('MODIS/061/MOD15A2H')
           .filterDate(date_start, date_end).filterBounds(bbox)
           .select('Lai_500m').mean().multiply(0.1))

    vcf = _safe_annual_mean('MODIS/061/MOD44B', 'Percent_Tree_Cover',
                            bbox, date_start, date_end)

    return (ndvi.rename('c_ndvi')
            .addBands(npp.rename('c_npp'))
            .addBands(lai.rename('c_lai'))
            .addBands(vcf.rename('c_vcf'))
            .clip(bbox).toFloat())


def dynamic_change_pressure(bbox, date_start, date_end):
    """Dynamic: VIIRS level, NDVI level, fire count for the window."""
    viirs = (ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG')
             .filterDate(date_start, date_end).filterBounds(bbox)
             .select('avg_rad').mean())

    ndvi = (ee.ImageCollection('MODIS/061/MOD13Q1')
            .filterDate(date_start, date_end).filterBounds(bbox)
            .select('NDVI').mean().multiply(0.0001))

    start_y = int(date_start[:4])
    end_y = int(date_end[:4])
    n_years = max(1, end_y - start_y + 1)

    fire = (ee.ImageCollection('MODIS/061/MCD64A1')
            .filterDate(date_start, date_end).filterBounds(bbox)
            .select('BurnDate').map(lambda img: img.gt(0).unmask(0))
            .sum().divide(n_years))

    return (viirs.rename('c_viirs_level')
            .addBands(ndvi.rename('c_ndvi_level'))
            .addBands(fire.rename('c_fire_annual'))
            .clip(bbox).toFloat())


def dynamic_agri_potential(bbox, date_start, date_end):
    """Dynamic: precipitation + GDD (soil and slope are fixed)."""
    start_y = int(date_start[:4])
    end_y = int(date_end[:4])
    n_years = max(1, end_y - start_y + 1)

    precip = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
              .filterDate(date_start, date_end).filterBounds(bbox)
              .select('precipitation').sum()
              .divide(n_years))

    era5 = (ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
            .filterDate(date_start, date_end).filterBounds(bbox))
    gdd = era5.select('temperature_2m').map(
        lambda img: img.subtract(283.15).max(0).multiply(30)
    ).sum().divide(n_years)

    return (precip.rename('c_precipitation')
            .addBands(gdd.rename('c_gdd'))
            .clip(bbox).toFloat())


def dynamic_forest_health(bbox, date_start, date_end):
    """Dynamic: NDVI mean, fire, GPP, ET (loss_ratio is fixed/cumulative)."""
    ndvi = (ee.ImageCollection('MODIS/061/MOD13Q1')
            .filterDate(date_start, date_end).filterBounds(bbox)
            .select('NDVI').mean().multiply(0.0001))

    start_y = int(date_start[:4])
    end_y = int(date_end[:4])
    n_years = max(1, end_y - start_y + 1)

    fire = (ee.ImageCollection('MODIS/061/MCD64A1')
            .filterDate(date_start, date_end).filterBounds(bbox)
            .select('BurnDate').map(lambda img: img.gt(0).unmask(0))
            .mean())

    gpp = (ee.ImageCollection('MODIS/061/MOD17A2HGF')
           .filterDate(date_start, date_end).filterBounds(bbox)
           .select('Gpp').mean().multiply(0.0001))

    et = (ee.ImageCollection('MODIS/061/MOD16A2GF')
          .filterDate(date_start, date_end).filterBounds(bbox)
          .select('ET').mean().multiply(0.1))

    return (ndvi.rename('c_ndvi_mean')
            .addBands(fire.rename('c_fire'))
            .addBands(gpp.rename('c_gpp'))
            .addBands(et.rename('c_et'))
            .clip(bbox).toFloat())


# ── Registry ─────────────────────────────────────────────────────────────

TEMPORAL_BUILDERS = {
    'environmental_risk': dynamic_environmental_risk,
    'climate_comfort': dynamic_climate_comfort,
    'green_capital': dynamic_green_capital,
    'change_pressure': dynamic_change_pressure,
    'agri_potential': dynamic_agri_potential,
    'forest_health': dynamic_forest_health,
}


def main():
    parser = argparse.ArgumentParser(description="Export temporal GEE composites (baseline + current)")
    parser.add_argument("--analysis", required=True, help="Analysis ID or 'all'")
    parser.add_argument("--mode", choices=['baseline', 'current', 'both'], default='both',
                        help="Which temporal window to export")
    parser.add_argument("--scale", type=int, default=EXPORT_SCALE)
    parser.add_argument("--baseline-start", default=BASELINE_START)
    parser.add_argument("--baseline-end", default=BASELINE_END)
    parser.add_argument("--current-start", default=CURRENT_START)
    parser.add_argument("--current-end", default=CURRENT_END)
    args = parser.parse_args()

    is_ci = authenticate()
    use_gcs = is_ci
    bbox = ee.Geometry.Rectangle(MISIONES_BBOX)

    if args.analysis == 'all':
        analyses = list(TEMPORAL_BUILDERS.keys())
    else:
        analyses = [a.strip() for a in args.analysis.split(',')]

    windows = []
    if args.mode in ('baseline', 'both'):
        windows.append(('baseline', args.baseline_start, args.baseline_end))
    if args.mode in ('current', 'both'):
        windows.append(('current', args.current_start, args.current_end))

    dest = f"GCS ({GCS_BUCKET})" if use_gcs else f"Drive ({DRIVE_FOLDER})"
    print(f"Exporting {len(analyses)} analyses × {len(windows)} windows at {args.scale}m -> {dest}")
    tasks = []

    for aid in analyses:
        if aid not in TEMPORAL_BUILDERS:
            print(f"  SKIP {aid}: no temporal builder")
            continue

        builder = TEMPORAL_BUILDERS[aid]

        for window_name, ds, de in windows:
            print(f"\n  Building {aid} [{window_name}] ({ds} → {de})...")
            composite = builder(bbox, ds, de)
            file_name = f'sat_{aid}_{window_name}'

            if use_gcs:
                task = ee.batch.Export.image.toCloudStorage(
                    image=composite,
                    description=file_name,
                    bucket=GCS_BUCKET,
                    fileNamePrefix=f'satellite/{file_name}',
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
            tasks.append((f"{aid}/{window_name}", task))
            print(f"    Export started: {file_name}")

    if not tasks:
        print("No tasks to run")
        return 1

    print(f"\nWaiting for {len(tasks)} exports...")
    while True:
        statuses = [(name, t.status()['state']) for name, t in tasks]
        running = sum(1 for _, s in statuses if s in ('READY', 'RUNNING'))
        if running == 0:
            break
        status_str = ', '.join(f"{n}={s}" for n, s in statuses)
        print(f"  [{running} running] {status_str}")
        time.sleep(30)

    print(f"\n{'=' * 60}")
    all_ok = True
    for name, task in tasks:
        status = task.status()
        if status['state'] == 'COMPLETED':
            print(f"  DONE: {name}")
        else:
            print(f"  FAILED: {name} — {status.get('error_message', 'unknown')}")
            all_ok = False

    print(f"\nFiles exported. Download and run:")
    print(f"  python pipeline/process_raster_temporal.py --analysis <id>")
    print(f"{'=' * 60}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
