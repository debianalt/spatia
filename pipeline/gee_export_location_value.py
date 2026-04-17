"""
Export location_value component rasters for a territory from GEE.

Rasters exported:
  1. lv_cities_access  — Oxford MAP accessibility to cities (Nelson 2019 methodology)
                         GEE: Oxford/MAP/accessibility_to_cities_2015_v1_0, band: accessibility
  2. lv_healthcare     — Healthcare accessibility (Oxford MAP methodology):
                         friction_surface_2015 + OSM hospital/clinic locations -> costDistance
  3. lv_viirs_annual   — VIIRS DNB 2022-2024 annual mean radiance (avg_rad)
  4. lv_slope          — Terrain slope from SRTM 30m (degrees)

Note on sources vs Misiones:
  - Cities: GEE Oxford MAP 2015 ≡ Nelson 2019 figshare (same Oxford MAP team + model)
  - Healthcare: same Oxford MAP methodology (friction + facilities), applied directly in GEE
  - VIIRS: same GEE collection
  - Slope: SRTM (Misiones used FABDEM = SRTM minus buildings/vegetation — same terrain in Paraná plateau)
  Road distance (5th component) is computed locally from OSM Geofabrik in process_location_value_h3.py.

Output: gs://spatia-satellite/satellite/{territory}/lv_{name}.tif
"""

import argparse
import json
import os
import sys
import time

import ee
import requests

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


def get_osm_healthcare_points(bbox):
    """Fetch healthcare facilities in bbox from Overpass API."""
    west, south, east, north = bbox
    query = f"""
[out:json][timeout:30][bbox:{south},{west},{north},{east}];
(
  node[amenity=hospital];
  node[amenity=clinic];
  node[amenity=health_post];
  node[healthcare];
  way[amenity=hospital];
  way[amenity=clinic];
);
out center;
"""
    url = "https://overpass-api.de/api/interpreter"
    try:
        r = requests.post(url, data=query, timeout=30)
        r.raise_for_status()
        data = r.json()
        points = []
        for el in data.get("elements", []):
            if el["type"] == "node":
                points.append(ee.Geometry.Point([el["lon"], el["lat"]]))
            elif el["type"] == "way" and "center" in el:
                points.append(ee.Geometry.Point([el["center"]["lon"], el["center"]["lat"]]))
        print(f"  Found {len(points)} healthcare facilities from OSM")
        return points
    except Exception as e:
        print(f"  WARNING: Overpass API failed ({e}), using empty healthcare set")
        return []


def main():
    parser = argparse.ArgumentParser(description="Export location_value rasters from GEE")
    parser.add_argument("--territory", default="misiones")
    parser.add_argument("--gcs", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
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

    # ── 2. Healthcare accessibility (friction + OSM facilities) ─────────────
    friction = ee.Image('Oxford/MAP/friction_surface_2015_v1_0').select('friction').clip(ee_bbox)
    facility_points = get_osm_healthcare_points(bbox)

    if facility_points:
        facilities_fc = ee.FeatureCollection(
            [ee.Feature(pt) for pt in facility_points])
        # Compute cost distance: travel time to nearest healthcare facility
        sources = facilities_fc.geometry().coveringGrid(
            ee.Projection('EPSG:4326').atScale(1000), 1000)
        source_mask = ee.Image(1).clip(facilities_fc.geometry().buffer(2000))
        healthcare_img = friction.costDistance(source_mask).clip(ee_bbox)
    else:
        # Fallback: use cities accessibility as proxy
        print("  Using cities accessibility as healthcare proxy (no OSM facilities found)")
        healthcare_img = cities_img

    # ── 3. VIIRS DNB annual mean 2022-2024 ───────────────────────────────────
    viirs = (ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG')
             .filterDate('2022-01-01', '2025-01-01')
             .select('avg_rad')
             .mean()
             .clip(ee_bbox))

    # ── 4. SRTM slope ────────────────────────────────────────────────────────
    srtm = ee.Image('USGS/SRTMGL1_003')
    slope_img = ee.Terrain.slope(srtm).clip(ee_bbox)

    exports = [
        ('lv_cities_access', cities_img, EXPORT_SCALE),
        ('lv_healthcare',    healthcare_img, EXPORT_SCALE),
        ('lv_viirs_annual',  viirs, VIIRS_SCALE),
        ('lv_slope',         slope_img, SLOPE_SCALE),
    ]

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
