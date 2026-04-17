"""
Export SDM covariate composites for forestry_aptitude as GeoTIFFs to GCS.

Exports 9 multi-band composites needed by compute_forestry_sdm.py for any
territory. Designed for Itapúa (PY) — Misiones uses pre-existing parquets.

GCS output: gs://spatia-satellite/satellite/{territory_id}/sdm_{name}.tif

Usage:
  python pipeline/gee_export_sdm_covariates.py --territory itapua_py
  python pipeline/gee_export_sdm_covariates.py --territory itapua_py --wait
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
from config import GCS_BUCKET, get_territory

CLIMATE_START = '2019-01-01'
CLIMATE_END   = '2024-01-01'   # 5 years 2019-2023
EXPORT_SCALE  = 100            # metres

MAPBIOMAS_PY_ASSET = (
    'projects/mapbiomas-public/assets/paraguay/collection1/'
    'mapbiomas_paraguay_collection1_integration_v1'
)
MAPBIOMAS_YEAR = 2022


def authenticate():
    key_env = os.environ.get('GEE_SERVICE_ACCOUNT_KEY', '')
    if key_env and not os.path.isfile(key_env):
        key_data = json.loads(key_env)
        credentials = ee.ServiceAccountCredentials(
            key_data['client_email'], key_data=json.dumps(key_data))
        ee.Initialize(credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        return True
    ee.Initialize()
    return False


# ─── Individual composite builders ─────────────────────────────────────────

def build_era5_composite(bbox):
    """5-band ERA5 annual climate means (2019-2023)."""
    col = (ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
           .filterDate(CLIMATE_START, CLIMATE_END)
           .filterBounds(bbox))

    temp = col.select('temperature_2m').mean().subtract(273.15)

    # Cold season proxy: mean of June-Aug (SH winter) as temp_min analogue
    col_winter = (ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
                  .filter(ee.Filter.calendarRange(6, 8, 'month'))
                  .filterDate(CLIMATE_START, CLIMATE_END)
                  .filterBounds(bbox))
    temp_min = col_winter.select('temperature_2m').mean().subtract(273.15)

    # Frost proxy: months with mean temp < 5°C → frost_days ≈ count × 30
    frost_months = col.map(lambda img: img.select('temperature_2m').subtract(273.15).lt(5))
    frost_days = frost_months.sum().multiply(30).divide(5)  # normalize over 5 years

    # GDD base 10 from monthly means
    gdd = (col.map(lambda img: img.select('temperature_2m').subtract(283.15).max(0).multiply(30))
           .sum().divide(5))

    solar = (col.select('surface_solar_radiation_downwards_sum')
             .sum().divide(5).multiply(1e-6))  # J/m² → MJ/m²

    return (temp.rename('temp_mean')
            .addBands(temp_min.rename('temp_min'))
            .addBands(frost_days.rename('frost_days'))
            .addBands(gdd.rename('gdd_base10'))
            .addBands(solar.rename('solar_radiation'))
            .clip(bbox).toFloat())


def build_chirps_composite(bbox):
    """4-band CHIRPS annual precipitation stats (2019-2023 mean)."""
    col = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
           .filterDate(CLIMATE_START, CLIMATE_END)
           .filterBounds(bbox)
           .select('precipitation'))

    total_per_year = col.sum().divide(5)           # mean annual total mm
    mean_daily     = total_per_year.divide(365.0)
    days_gt_20mm   = (col.map(lambda img: img.gt(20)).sum()).divide(5)
    days_gt_50mm   = (col.map(lambda img: img.gt(50)).sum()).divide(5)

    return (total_per_year.rename('precip_total')
            .addBands(mean_daily.rename('precip_mean_daily'))
            .addBands(days_gt_20mm.rename('precip_days_20mm'))
            .addBands(days_gt_50mm.rename('precip_days_50mm'))
            .clip(bbox).toFloat())


def build_terraclimate_composite(bbox):
    """4-band TerraClimate annual stress indices (2019-2023 mean)."""
    col = (ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE')
           .filterDate(CLIMATE_START, CLIMATE_END)
           .filterBounds(bbox))

    water_def = col.select('def').mean().multiply(0.1)  # mm*10 → mm
    soil_mst  = col.select('soil').mean().multiply(0.1) # mm*10 → mm
    vpd       = col.select('vpd').mean().multiply(0.01) # Pa*100 → kPa
    # pdsi: keep raw, min per year then average
    pdsi_min  = (col.map(lambda img: img.select('pdsi').multiply(0.01))
                 .min())  # worst drought in period

    return (water_def.rename('water_deficit')
            .addBands(soil_mst.rename('soil_moisture'))
            .addBands(vpd.rename('vpd'))
            .addBands(pdsi_min.rename('pdsi_min'))
            .clip(bbox).toFloat())


def build_soilgrids_composite(bbox):
    """6-band SoilGrids static soil properties (0-5cm layer)."""
    ph   = ee.Image('projects/soilgrids-isric/phh2o_mean').select('phh2o_0-5cm_mean').multiply(0.1)
    clay = ee.Image('projects/soilgrids-isric/clay_mean').select('clay_0-5cm_mean').multiply(0.1)
    sand = ee.Image('projects/soilgrids-isric/sand_mean').select('sand_0-5cm_mean').multiply(0.1)
    silt = ee.Image('projects/soilgrids-isric/silt_mean').select('silt_0-5cm_mean').multiply(0.1)
    soc  = ee.Image('projects/soilgrids-isric/soc_mean').select('soc_0-5cm_mean').multiply(0.1)
    bdod = ee.Image('projects/soilgrids-isric/bdod_mean').select('bdod_0-5cm_mean').multiply(0.01)

    return (ph.rename('ph')
            .addBands(clay.rename('clay'))
            .addBands(sand.rename('sand'))
            .addBands(silt.rename('silt'))
            .addBands(soc.rename('soc'))
            .addBands(bdod.rename('bulk_density'))
            .clip(bbox).toFloat())


def build_terrain_composite(bbox):
    """3-band terrain composite from SRTM + MERIT Hydro."""
    dem   = ee.Image('USGS/SRTMGL1_003').select('elevation')
    slope = ee.Terrain.slope(dem)

    # Topographic Wetness Index proxy from MERIT Hydro upstream area
    merit = ee.Image('MERIT/Hydro/v1_0_1')
    upa   = merit.select('upa').max(0.001)  # km², avoid log(0)
    slope_rad  = slope.multiply(3.14159 / 180.0)
    tan_slope  = slope_rad.tan().max(0.001)
    twi        = upa.log().subtract(tan_slope.log())

    return (dem.rename('elevation')
            .addBands(slope.rename('slope'))
            .addBands(twi.rename('twi'))
            .clip(bbox).toFloat())


def build_ndvi_composite(bbox):
    """1-band MODIS NDVI annual mean (2019-2023)."""
    ndvi = (ee.ImageCollection('MODIS/061/MOD13A3')
            .filterDate(CLIMATE_START, CLIMATE_END)
            .filterBounds(bbox)
            .select('NDVI')
            .mean()
            .multiply(0.0001))
    return ndvi.rename('ndvi_mean').clip(bbox).toFloat()


def build_ghsl_smod(bbox):
    """1-band GHSL Settlement Model 2020 class."""
    smod = ee.Image('JRC/GHSL/P2023A/GHS_SMOD_E2020_GLOBE_R2023A_4326_1000_V1_0').select('smod_code')
    return smod.rename('smod_class').clip(bbox).toFloat()


def build_jrc_water(bbox):
    """1-band JRC surface water annual mean fraction (2018-2023)."""
    water = (ee.ImageCollection('JRC/GSW1_4/YearlyHistory')
             .filterDate('2018-01-01', '2024-01-01')
             .filterBounds(bbox)
             .map(lambda img: img.select('waterClass').gt(1).unmask(0))  # 2=seasonal, 3=permanent
             .mean())
    return water.rename('water_fraction').clip(bbox).toFloat()


def build_mapbiomas_py(bbox):
    """2-band MapBiomas Paraguay 2022: land use class + plantation mask."""
    mb   = ee.Image(MAPBIOMAS_PY_ASSET)
    year = mb.select(f'classification_{MAPBIOMAS_YEAR}')
    # Plantation (silvicultura) = class 9 in MapBiomas standard legend
    plantation = year.eq(9).unmask(0)
    native_forest = year.eq(3).Or(year.eq(4)).unmask(0)
    water = year.eq(26).Or(year.eq(33)).unmask(0)
    urban = year.eq(24).unmask(0)

    return (year.rename('land_use_class')
            .addBands(plantation.rename('is_plantation'))
            .addBands(native_forest.rename('is_native_forest'))
            .addBands(water.rename('is_water'))
            .addBands(urban.rename('is_urban'))
            .clip(bbox).toFloat())


# ─── Export registry ────────────────────────────────────────────────────────

EXPORTS = {
    'era5_composite':         (build_era5_composite,         100),
    'chirps_composite':       (build_chirps_composite,        100),
    'terraclimate_composite': (build_terraclimate_composite,  1000),  # TerraClimate ~4km native
    'soilgrids_composite':    (build_soilgrids_composite,     250),   # SoilGrids 250m native
    'terrain_composite':      (build_terrain_composite,        90),   # SRTM 30m → 90m for stability
    'ndvi_composite':         (build_ndvi_composite,          100),
    'ghsl_smod':              (build_ghsl_smod,               100),
    'jrc_water':              (build_jrc_water,               100),
    'mapbiomas_py':           (build_mapbiomas_py,             30),   # MapBiomas 30m native
}


def wait_for_tasks(task_ids: list[str], poll_seconds: int = 30):
    print(f"\nWaiting on {len(task_ids)} GEE tasks...")
    while True:
        statuses = [ee.data.getTaskStatus(tid)[0]['state'] for tid in task_ids]
        counts = {s: statuses.count(s) for s in set(statuses)}
        print(f"  {counts}", flush=True)
        if all(s in ('COMPLETED', 'FAILED', 'CANCELLED') for s in statuses):
            failed = [tid for tid, s in zip(task_ids, statuses) if s != 'COMPLETED']
            if failed:
                print(f"  WARNING: {len(failed)} tasks failed: {failed}")
            else:
                print("  All tasks COMPLETED.")
            break
        time.sleep(poll_seconds)


def main():
    parser = argparse.ArgumentParser(description='Export SDM covariate GeoTIFFs')
    parser.add_argument('--territory', default='itapua_py')
    parser.add_argument('--only', default=None, help='Comma-separated export names')
    parser.add_argument('--wait', action='store_true', help='Poll until all tasks complete')
    parser.add_argument('--scale', type=int, default=None, help='Override export scale (m)')
    args = parser.parse_args()

    territory = get_territory(args.territory)
    t_id = territory['id']
    authenticate()

    bbox = ee.Geometry.Rectangle(territory['bbox'])
    gcs_prefix = f"satellite/{t_id}"

    exports_to_run = EXPORTS
    if args.only:
        keys = [k.strip() for k in args.only.split(',')]
        exports_to_run = {k: v for k, v in EXPORTS.items() if k in keys}

    print(f"Territory: {territory['label']} ({t_id})")
    print(f"GCS: gs://{gcs_prefix}/ — {len(exports_to_run)} composites")
    print("=" * 60)

    task_ids = []
    for name, (builder_fn, default_scale) in exports_to_run.items():
        scale = args.scale or default_scale
        try:
            image = builder_fn(bbox)
            gcs_path = f"{gcs_prefix}/sdm_{name}"
            task = ee.batch.Export.image.toCloudStorage(
                image=image,
                description=f'sdm_{name}_{t_id}',
                bucket=GCS_BUCKET,
                fileNamePrefix=gcs_path,
                region=bbox,
                scale=scale,
                maxPixels=1e10,
                fileFormat='GeoTIFF',
                formatOptions={'cloudOptimized': True},
            )
            task.start()
            task_ids.append(task.id)
            print(f"  STARTED {name} @ {scale}m  → gs://{GCS_BUCKET}/{gcs_path}.tif")
        except Exception as e:
            print(f"  FAILED  {name}: {e}")

    print(f"\nSubmitted {len(task_ids)} tasks.")
    print(f"Task IDs: {task_ids}")

    if args.wait:
        wait_for_tasks(task_ids)
    else:
        print("Run with --wait to poll until completion.")
        print("\nTo download once tasks complete:")
        t_dir = f"pipeline/output/{t_id}"
        for name in exports_to_run:
            print(f"  gcloud storage cp gs://{GCS_BUCKET}/{gcs_prefix}/sdm_{name}.tif {t_dir}/sdm_{name}.tif")


if __name__ == '__main__':
    main()
