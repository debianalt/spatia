"""
Export location_value component rasters for a territory from GEE.

Rasters exported:
  1. lv_cities_access  — Oxford MAP accessibility to cities (Nelson 2019 methodology)
                         GEE: Oxford/MAP/accessibility_to_cities_2015_v1_0, band: accessibility
  2. lv_friction       — Oxford MAP friction surface 2019 (minutes per meter, motorized travel)
                         GEE: projects/malariaatlasproject/assets/.../friction_surface/2019_v5_1
                         cumulativeCost is computed LOCALLY in process_location_value_h3.py using
                         skimage.graph.MCP_Geometric (same algorithm as GEE cumulativeCost, but
                         GEE batch cumulativeCost consistently fails for this territory).
  3. lv_viirs_annual   — VIIRS DNB 2022-2024 annual mean radiance (avg_rad)
  4. lv_slope          — Terrain slope from Copernicus DEM GLO-30 (TanDEM-X based, 30m).
                         FABDEM community asset (projects/sat-io/open-datasets/FABDEM) has no
                         coverage for Paraguay; Copernicus GLO-30 is FABDEM's input DEM and
                         produces equivalent slope for Paraguay's agricultural landscape.
                         GEE: COPERNICUS/DEM/GLO30, band: DEM

Note on sources vs Misiones:
  - Cities: same Oxford MAP / Nelson 2019 dataset
  - Healthcare: same Oxford MAP friction 2019 source; MCP computed locally
  - VIIRS: same GEE collection
  - Slope: Copernicus DEM GLO-30 (FABDEM input; equivalent for slope in low-vegetation areas)
  Road distance (5th component) is computed locally from OSM in process_location_value_h3.py.

Output: gs://spatia-satellite/satellite/{territory}/lv_{name}.tif
"""

import argparse
import os
import sys
import time

import ee

from config import GCS_BUCKET, get_territory

EXPORT_SCALE = 1000  # 1km (matches Nelson/Oxford MAP native resolution)
SLOPE_SCALE = 90     # ~90m for SRTM slope
VIIRS_SCALE = 500    # ~500m for VIIRS
DRIVE_FOLDER = 'spatia-satellite'


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
    parser = argparse.ArgumentParser(description="Export location_value rasters from GEE")
    parser.add_argument("--territory", default="misiones")
    parser.add_argument("--gcs", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--only", default=None,
                        help="Comma-separated subset: cities_access,friction,viirs_annual,slope")
    args = parser.parse_args()

    is_ci = authenticate()
    use_gcs = args.gcs or is_ci

    territory = get_territory(args.territory)
    bbox = territory['bbox']
    gcs_subdir = '' if args.territory == 'misiones' else f"{args.territory}/"
    ee_bbox = ee.Geometry.Rectangle(bbox)

    print(f"Territory: {args.territory}, bbox: {bbox}")
    dest = f"GCS ({GCS_BUCKET}/satellite/{gcs_subdir})" if use_gcs else f"Drive ({DRIVE_FOLDER})"
    print(f"Destination: {dest}")

    # ── 1. Cities accessibility (Oxford MAP / Nelson 2019 methodology) ──────
    cities_img = ee.Image('Oxford/MAP/accessibility_to_cities_2015_v1_0') \
        .select('accessibility') \
        .clip(ee_bbox)

    # ── 2. Oxford MAP friction surface 2019 (exported as-is; MCP computed locally) ──
    # GEE cumulativeCost fails in batch mode for this region (4 confirmed attempts).
    # Solution: export the raw friction raster and compute MCP in process_location_value_h3.py
    # using skimage.graph.MCP_Geometric — identical algorithm, reliable execution.
    friction_img = ee.Image(
        'projects/malariaatlasproject/assets/accessibility/friction_surface/2019_v5_1'
    ).select('friction').clip(ee_bbox)

    # ── 3. VIIRS DNB annual mean 2022-2024 ───────────────────────────────────
    viirs = (ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG')
             .filterDate('2022-01-01', '2025-01-01')
             .select('avg_rad')
             .mean()
             .clip(ee_bbox))

    # ── 4. Copernicus DEM GLO-30 slope ────────────────────────────────────────
    # FABDEM community asset (projects/sat-io/open-datasets/FABDEM) has no coverage
    # for Paraguay (exports successfully but produces all-NaN for this bbox).
    # Copernicus DEM GLO-30 is FABDEM's input (TanDEM-X + ICESat-2 corrections, 30m).
    # For slope in Paraguay's low-density agricultural landscape, the difference is
    # negligible (FABDEM removes vegetation+building heights which are minimal here).
    cop_dem = (ee.ImageCollection('COPERNICUS/DEM/GLO30')
               .filterBounds(ee_bbox)
               .select('DEM')
               .mosaic())
    slope_img = ee.Terrain.slope(cop_dem).clip(ee_bbox)

    all_exports = [
        ('lv_cities_access', cities_img, EXPORT_SCALE),
        ('lv_friction',      friction_img, EXPORT_SCALE),
        ('lv_viirs_annual',  viirs, VIIRS_SCALE),
        ('lv_slope',         slope_img, SLOPE_SCALE),
    ]

    only_set = set(args.only.split(',')) if args.only else None
    exports = [(n, img, sc) for n, img, sc in all_exports
               if only_set is None or n.replace('lv_', '') in only_set or n in only_set]

    tasks = []
    for name, image, scale in exports:
        desc = f"{name}_{args.territory}" if args.territory != 'misiones' else name
        if use_gcs:
            task = ee.batch.Export.image.toCloudStorage(
                image=image.toFloat(),
                description=desc,
                bucket=GCS_BUCKET,
                fileNamePrefix=f'satellite/{gcs_subdir}{name}',
                region=ee_bbox,
                scale=scale,
                crs='EPSG:4326',
                maxPixels=1e10)
        else:
            task = ee.batch.Export.image.toDrive(
                image=image.toFloat(),
                description=desc,
                folder=DRIVE_FOLDER,
                fileNamePrefix=desc,
                region=ee_bbox,
                scale=scale,
                crs='EPSG:4326',
                maxPixels=1e10)
        task.start()
        tasks.append((name, task))
        print(f"  Started: {name}")

    if args.no_wait:
        print("Tasks submitted.")
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
