"""
Export multi-band GEE composites for satellite analyses at pixel level.

Each analysis is a multi-band ee.Image exported as GeoTIFF to Google Drive.
This replaces the radio-level approach — each pixel contributes independently
to H3 zonal statistics, capturing sub-radio spatial variation.

Usage:
  python pipeline/gee_export_analysis.py --analysis green_capital
  python pipeline/gee_export_analysis.py --analysis all
  python pipeline/gee_export_analysis.py --analysis environmental_risk,agri_potential
"""

import argparse
import ee
import json
import os
import sys
import time

from config import MISIONES_BBOX, OUTPUT_DIR, get_territory

EXPORT_SCALE = 100  # metres — sweet spot for H3 res-9 (~174m hex side)
DRIVE_FOLDER = 'spatia-satellite'
GCS_BUCKET = 'spatia-satellite'
DATE_START = '2019-01-01'
DATE_END = '2024-12-31'


def authenticate():
    """Authenticate to GEE — service account in CI, user credentials locally."""
    key_env = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")
    if not key_env:
        ee.Initialize()
        return False  # local dev, use Drive

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
    return True  # CI mode, use GCS


def build_environmental_risk(bbox):
    """Fire frequency + deforestation + thermal amplitude + slope + HAND."""
    fire = (ee.ImageCollection('MODIS/061/MCD64A1')
            .filterDate(DATE_START, DATE_END)
            .filterBounds(bbox)
            .select('BurnDate')
            .map(lambda img: img.gt(0).unmask(0))
            .mean()
            .unmask(0))  # fill any gaps if collection is sparse for this region

    hansen = ee.Image('UMD/hansen/global_forest_change_2024_v1_12')
    deforest = hansen.select('loss').unmask(0)

    lst_col = (ee.ImageCollection('MODIS/061/MOD11A2')
               .filterDate(DATE_START, DATE_END)
               .filterBounds(bbox))
    lst_day = lst_col.select('LST_Day_1km').mean().multiply(0.02).subtract(273.15)
    lst_night = lst_col.select('LST_Night_1km').mean().multiply(0.02).subtract(273.15)
    thermal_amp = lst_day.subtract(lst_night).max(0)

    dem = ee.Image('USGS/SRTMGL1_003').select('elevation')
    slope = ee.Terrain.slope(dem)

    hand = ee.Image('MERIT/Hydro/v1_0_1').select('hnd')

    return (fire.rename('c_fire')
            .addBands(deforest.rename('c_deforest'))
            .addBands(thermal_amp.rename('c_thermal_amp'))
            .addBands(slope.rename('c_slope'))
            .addBands(hand.rename('c_hand'))
            .clip(bbox).toFloat())


def build_climate_comfort(bbox):
    """LST day/night + precipitation + frost + ET/PET."""
    lst_col = (ee.ImageCollection('MODIS/061/MOD11A2')
               .filterDate(DATE_START, DATE_END).filterBounds(bbox))
    heat_day = lst_col.select('LST_Day_1km').mean().multiply(0.02).subtract(273.15)
    heat_night = lst_col.select('LST_Night_1km').mean().multiply(0.02).subtract(273.15)

    precip = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
              .filterDate(DATE_START, DATE_END).filterBounds(bbox)
              .select('precipitation').sum()
              .divide(6))  # 6 years → annual avg

    # ERA5 frost: t2m < 273.15K
    era5 = (ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
            .filterDate(DATE_START, DATE_END).filterBounds(bbox))
    frost = era5.select('temperature_2m').map(
        lambda img: img.lt(273.15).unmask(0)
    ).sum().divide(6)

    et_col = (ee.ImageCollection('MODIS/061/MOD16A2GF')
              .filterDate(DATE_START, DATE_END).filterBounds(bbox))
    et = et_col.select('ET').mean().multiply(0.1)
    pet = et_col.select('PET').mean().multiply(0.1)
    et_pet = et.divide(pet.max(1))

    return (heat_day.rename('c_heat_day')
            .addBands(heat_night.rename('c_heat_night'))
            .addBands(precip.rename('c_precipitation'))
            .addBands(frost.rename('c_frost'))
            .addBands(et_pet.rename('c_water_stress'))
            .clip(bbox).toFloat())


def build_green_capital(bbox):
    """NDVI + treecover + NPP + LAI + VCF."""
    ndvi = (ee.ImageCollection('MODIS/061/MOD13Q1')
            .filterDate(DATE_START, DATE_END).filterBounds(bbox)
            .select('NDVI').mean().multiply(0.0001))

    treecover = (ee.Image('UMD/hansen/global_forest_change_2024_v1_12')
                 .select('treecover2000').unmask(0).divide(100))

    npp = (ee.ImageCollection('MODIS/061/MOD17A3HGF')
           .filterDate(DATE_START, DATE_END).filterBounds(bbox)
           .select('Npp').mean().multiply(0.0001))

    lai = (ee.ImageCollection('MODIS/061/MOD15A2H')
           .filterDate(DATE_START, DATE_END).filterBounds(bbox)
           .select('Lai_500m').mean().multiply(0.1))

    vcf = (ee.ImageCollection('MODIS/061/MOD44B')
           .filterDate(DATE_START, DATE_END).filterBounds(bbox)
           .select('Percent_Tree_Cover').mean())

    return (ndvi.rename('c_ndvi')
            .addBands(treecover.rename('c_treecover'))
            .addBands(npp.rename('c_npp'))
            .addBands(lai.rename('c_lai'))
            .addBands(vcf.rename('c_vcf'))
            .clip(bbox).toFloat())


def build_change_pressure(bbox):
    """VIIRS trend proxy + GHSL change + Hansen loss + NDVI trend proxy + fire."""
    # VIIRS recent vs older as change proxy
    viirs_old = (ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG')
                 .filterDate('2016-01-01', '2018-12-31').filterBounds(bbox)
                 .select('avg_rad').mean())
    viirs_new = (ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG')
                 .filterDate('2022-01-01', '2024-12-31').filterBounds(bbox)
                 .select('avg_rad').mean())
    viirs_change = viirs_new.subtract(viirs_old)

    # GHSL built-up change
    ghsl_2000 = ee.Image('JRC/GHSL/P2023A/GHS_BUILT_S/2000').select('built_surface').unmask(0)
    ghsl_2020 = ee.Image('JRC/GHSL/P2023A/GHS_BUILT_S/2020').select('built_surface').unmask(0)
    ghsl_change = ghsl_2020.subtract(ghsl_2000)

    hansen = ee.Image('UMD/hansen/global_forest_change_2024_v1_12')
    hansen_loss = hansen.select('loss').unmask(0)

    # NDVI change (recent vs older)
    ndvi_old = (ee.ImageCollection('MODIS/061/MOD13Q1')
                .filterDate('2019-01-01', '2020-12-31').filterBounds(bbox)
                .select('NDVI').mean().multiply(0.0001))
    ndvi_new = (ee.ImageCollection('MODIS/061/MOD13Q1')
                .filterDate('2023-01-01', '2024-12-31').filterBounds(bbox)
                .select('NDVI').mean().multiply(0.0001))
    ndvi_change = ndvi_new.subtract(ndvi_old)

    fire = (ee.ImageCollection('MODIS/061/MCD64A1')
            .filterDate(DATE_START, DATE_END).filterBounds(bbox)
            .select('BurnDate').map(lambda img: img.gt(0).unmask(0))
            .sum()
            .unmask(0))

    return (viirs_change.rename('c_viirs_trend')
            .addBands(ghsl_change.rename('c_ghsl_change'))
            .addBands(hansen_loss.rename('c_hansen_loss'))
            .addBands(ndvi_change.rename('c_ndvi_trend'))
            .addBands(fire.rename('c_fire_count'))
            .clip(bbox).toFloat())


def build_agri_potential(bbox):
    """SOC + pH + clay + precipitation + GDD + slope."""
    soil = ee.Image('projects/soilgrids-isric/ocd_mean').select('ocd_0-5cm_mean')
    soc = soil.unmask(0)

    ph = ee.Image('projects/soilgrids-isric/phh2o_mean').select('phh2o_0-5cm_mean').unmask(50)
    ph_optimal = ee.Image(1).subtract(ph.divide(10).subtract(6.25).abs().divide(4)).max(0)

    clay = ee.Image('projects/soilgrids-isric/clay_mean').select('clay_0-5cm_mean').unmask(0)

    precip = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
              .filterDate(DATE_START, DATE_END).filterBounds(bbox)
              .select('precipitation').sum().divide(6))

    # GDD base 10: sum of (T - 10) where T > 10, over year
    era5 = (ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
            .filterDate(DATE_START, DATE_END).filterBounds(bbox))
    gdd = era5.select('temperature_2m').map(
        lambda img: img.subtract(283.15).max(0).multiply(30)  # ~days per month
    ).sum().divide(6)

    dem = ee.Image('USGS/SRTMGL1_003').select('elevation')
    slope = ee.Terrain.slope(dem)

    return (soc.rename('c_soc')
            .addBands(ph_optimal.rename('c_ph_optimal'))
            .addBands(clay.rename('c_clay'))
            .addBands(precip.rename('c_precipitation'))
            .addBands(gdd.rename('c_gdd'))
            .addBands(slope.rename('c_slope'))
            .clip(bbox).toFloat())


def build_forest_health(bbox):
    """NDVI trend + loss ratio + fire + GPP + ET."""
    ndvi_old = (ee.ImageCollection('MODIS/061/MOD13Q1')
                .filterDate('2019-01-01', '2020-12-31').filterBounds(bbox)
                .select('NDVI').mean().multiply(0.0001))
    ndvi_new = (ee.ImageCollection('MODIS/061/MOD13Q1')
                .filterDate('2023-01-01', '2024-12-31').filterBounds(bbox)
                .select('NDVI').mean().multiply(0.0001))
    ndvi_trend = ndvi_new.subtract(ndvi_old)

    hansen = ee.Image('UMD/hansen/global_forest_change_2024_v1_12')
    treecover = hansen.select('treecover2000').max(1)
    loss = hansen.select('loss').unmask(0)
    loss_ratio = loss.divide(treecover.divide(100))

    fire = (ee.ImageCollection('MODIS/061/MCD64A1')
            .filterDate(DATE_START, DATE_END).filterBounds(bbox)
            .select('BurnDate').map(lambda img: img.gt(0).unmask(0))
            .mean()
            .unmask(0))

    gpp = (ee.ImageCollection('MODIS/061/MOD17A2HGF')
           .filterDate(DATE_START, DATE_END).filterBounds(bbox)
           .select('Gpp').mean().multiply(0.0001))

    et = (ee.ImageCollection('MODIS/061/MOD16A2GF')
          .filterDate(DATE_START, DATE_END).filterBounds(bbox)
          .select('ET').mean().multiply(0.1))

    return (ndvi_trend.rename('c_ndvi_trend')
            .addBands(loss_ratio.rename('c_loss_ratio'))
            .addBands(fire.rename('c_fire'))
            .addBands(gpp.rename('c_gpp'))
            .addBands(et.rename('c_et'))
            .clip(bbox).toFloat())


def build_air_quality(bbox):
    """PM2.5 + NO2 + AOD — multi-pollutant air quality composite.

    Sources:
      - PM2.5: ACAG/Van Donkelaar V6 annual (0.01°, 2019-2021 mean)
      - NO2: TROPOMI OFFL tropospheric column (2019-2021 mean)
      - AOD: MODIS MAIAC MCD19A2 470nm (monthly composites, 2019-2021 mean)
    """
    # PM2.5 — satellite-derived annual surface concentration (µg/m³)
    pm25 = (ee.ImageCollection('projects/sat-io/open-datasets/GLOBAL-SATELLITE-PM25/ANNUAL')
            .filter(ee.Filter.calendarRange(2019, 2021, 'year'))
            .mean())

    # NO2 — tropospheric column (mol/m²)
    no2 = (ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_NO2')
           .filterDate(DATE_START, DATE_END)
           .filterBounds(bbox)
           .select('tropospheric_NO2_column_number_density')
           .mean())

    # AOD — monthly composites to reduce computation, then mean
    aod_months = []
    for year in [2019, 2020, 2021]:
        for month in range(1, 13):
            start = f'{year}-{month:02d}-01'
            end_month = month + 1 if month < 12 else 1
            end_year = year if month < 12 else year + 1
            end = f'{end_year}-{end_month:02d}-01'
            monthly = (ee.ImageCollection('MODIS/061/MCD19A2_GRANULES')
                       .filterDate(start, end)
                       .filterBounds(bbox)
                       .select('Optical_Depth_047')
                       .mean())
            aod_months.append(monthly)
    aod = ee.ImageCollection(aod_months).mean().multiply(0.001)

    return (pm25.rename('c_pm25')
            .addBands(no2.rename('c_no2'))
            .addBands(aod.rename('c_aod'))
            .clip(bbox).toFloat())


def build_forestry_aptitude(bbox):
    """DEPRECATED — reemplazado por pipeline/compute_forestry_sdm.py.

    Este export ya no se ejecuta. El nuevo pipeline usa un SDM (Random Forest)
    entrenado sobre MapBiomas silvicultura como presencia y covariables
    biofisicas al nivel H3, con mascara satelital de agua/urbano/bosque nativo.
    Ver compute_forestry_sdm.py.
    """
    ph_raw = ee.Image('projects/soilgrids-isric/phh2o_mean').select('phh2o_0-5cm_mean').unmask(50)
    ph = ph_raw.divide(10)  # SoilGrids stores pH*10

    clay = ee.Image('projects/soilgrids-isric/clay_mean').select('clay_0-5cm_mean').unmask(0)

    precip = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
              .filterDate(DATE_START, DATE_END).filterBounds(bbox)
              .select('precipitation').sum().divide(6))  # mm/year average

    dem = ee.Image('USGS/SRTMGL1_003').select('elevation')
    slope = ee.Terrain.slope(dem)  # degrees

    # Road/infra distance: use GHSL built-up as proxy (villages + roads network).
    # GHSL GHS_BUILT_C 2018 class >= 2 (open + low-density + dense built-up).
    # fastDistanceTransform: squared distance in pixels -> sqrt * scale = metres.
    built = (ee.Image('JRC/GHSL/P2023A/GHS_BUILT_C/2018').select('built_characteristics')
             .gte(2).unmask(0))
    road_dist = (built.fastDistanceTransform(256).sqrt()
                 .multiply(100))  # metres at ~100m pixel scale

    # Oxford Global Accessibility to Cities (50k+): travel time in minutes
    access_50k = ee.Image('Oxford/MAP/accessibility_to_cities_2015_v1_0').select('accessibility')

    return (ph.rename('c_ph')
            .addBands(clay.rename('c_clay'))
            .addBands(precip.rename('c_precipitation'))
            .addBands(slope.rename('c_slope'))
            .addBands(road_dist.rename('c_road_dist'))
            .addBands(access_50k.rename('c_access_50k'))
            .clip(bbox).toFloat())


ANALYSIS_BUILDERS = {
    'environmental_risk': build_environmental_risk,
    'climate_comfort': build_climate_comfort,
    'green_capital': build_green_capital,
    'change_pressure': build_change_pressure,
    'agri_potential': build_agri_potential,
    'forest_health': build_forest_health,
    'air_quality': build_air_quality,
}


def main():
    parser = argparse.ArgumentParser(description="Export GEE analysis composites to Drive/GCS")
    parser.add_argument("--analysis", required=True, help="Analysis ID or 'all'")
    parser.add_argument("--territory", default="misiones",
                        help="Territory ID from config.py (default: misiones)")
    parser.add_argument("--scale", type=int, default=None,
                        help="Export scale in metres (default: from territory config)")
    parser.add_argument("--gcs", action="store_true", help="Force export to GCS (default: auto-detect CI)")
    parser.add_argument("--batch-size", type=int, default=6,
                        help="Max concurrent GEE tasks (default: 6; GEE Partner limit ~25)")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    scale = args.scale or territory['export_scale']
    t_prefix = territory['output_prefix']  # '' for misiones, 'itapua_py/' for itapua

    is_ci = authenticate()
    use_gcs = args.gcs or is_ci
    bbox = ee.Geometry.Rectangle(territory['bbox'])

    if args.analysis == 'all':
        analyses = list(ANALYSIS_BUILDERS.keys())
    else:
        analyses = [a.strip() for a in args.analysis.split(',')]

    dest = f"GCS ({GCS_BUCKET})" if use_gcs else f"Drive ({DRIVE_FOLDER})"
    print(f"Territory: {territory['label']} ({args.territory})")
    print(f"Exporting {len(analyses)} analyses at {scale}m scale -> {dest}")
    if t_prefix:
        print(f"Output prefix: satellite/{t_prefix}")
    tasks = []

    # Process in batches to stay within GEE concurrent task limits
    for i in range(0, len(analyses), args.batch_size):
        batch = analyses[i:i + args.batch_size]
        batch_tasks = []

        for aid in batch:
            if aid not in ANALYSIS_BUILDERS:
                print(f"  SKIP {aid}: no builder defined")
                continue

            print(f"\n  Building {aid}...")
            composite = ANALYSIS_BUILDERS[aid](bbox)

            # GCS prefix: satellite/{t_prefix}sat_{aid}_raster
            # e.g. satellite/sat_env_risk_raster  (misiones)
            # e.g. satellite/itapua_py/sat_env_risk_raster  (itapua)
            gcs_prefix = f'satellite/{t_prefix}sat_{aid}_raster'
            description = f'{args.territory}_{aid}_raster' if args.territory != 'misiones' else f'sat_{aid}_raster'

            if use_gcs:
                task = ee.batch.Export.image.toCloudStorage(
                    image=composite,
                    description=description,
                    bucket=GCS_BUCKET,
                    fileNamePrefix=gcs_prefix,
                    region=bbox,
                    scale=scale,
                    crs='EPSG:4326',
                    maxPixels=1e9,
                )
            else:
                task = ee.batch.Export.image.toDrive(
                    image=composite,
                    description=description,
                    folder=DRIVE_FOLDER,
                    fileNamePrefix=f'{t_prefix}sat_{aid}_raster' if t_prefix else f'sat_{aid}_raster',
                    region=bbox,
                    scale=scale,
                    crs='EPSG:4326',
                    maxPixels=1e9,
                )
            task.start()
            batch_tasks.append((aid, task))
            tasks.append((aid, task))
            print(f"    Export started: {description}")

        # Wait for this batch before starting the next (avoid overloading GEE queue)
        if i + args.batch_size < len(analyses):
            print(f"\n  Waiting for batch {i // args.batch_size + 1} ({len(batch_tasks)} tasks)...")
            while True:
                statuses = [(aid, t.status()['state']) for aid, t in batch_tasks]
                running = sum(1 for _, s in statuses if s in ('READY', 'RUNNING'))
                if running == 0:
                    break
                print(f"    [{running} running] " + ', '.join(f"{a}={s}" for a, s in statuses))
                time.sleep(30)

    if not tasks:
        print("No tasks to run")
        return 1

    # Poll for completion
    print(f"\nWaiting for {len(tasks)} exports...")
    while True:
        statuses = [(aid, t.status()['state']) for aid, t in tasks]
        running = sum(1 for _, s in statuses if s in ('READY', 'RUNNING'))
        if running == 0:
            break
        status_str = ', '.join(f"{a}={s}" for a, s in statuses)
        print(f"  [{running} running] {status_str}")
        time.sleep(30)

    # Report results
    print(f"\n{'=' * 60}")
    all_ok = True
    for aid, task in tasks:
        status = task.status()
        if status['state'] == 'COMPLETED':
            print(f"  DONE: {aid}")
        else:
            print(f"  FAILED: {aid} — {status.get('error_message', 'unknown')}")
            all_ok = False

    print(f"\nFiles in Google Drive folder '{DRIVE_FOLDER}'")
    print(f"Download and run: python pipeline/process_raster_to_h3.py --analysis <id>")
    print(f"{'=' * 60}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
