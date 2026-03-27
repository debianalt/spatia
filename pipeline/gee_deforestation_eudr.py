"""
Export EUDR deforestation rasters from Google Earth Engine.

Bands exported:
  1. treecover_2000   — Hansen treecover2000 (0-100%)
  2. loss_year        — Hansen lossyear (0=no loss, 1=2001 ... 24=2024)
  3. loss_post_2020   — Binary mask: lossyear >= 21 (i.e. 2021+)
  4. treecover_current — treecover2000 minus cumulative loss proxy
  5. fire_post_2020   — MODIS MCD64A1 burned area fraction post-2020

Exports to Google Drive (local dev) or GCS (CI).

Usage:
  python pipeline/gee_deforestation_eudr.py
  python pipeline/gee_deforestation_eudr.py --province chaco
  python pipeline/gee_deforestation_eudr.py --all-provinces
"""

import argparse
import ee
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_eudr import (
    EUDR_BBOX,
    EUDR_PROVINCES,
    EUDR_CUTOFF_YEAR,
    EXPORT_SCALE,
    DRIVE_FOLDER,
)


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
        key_data["client_email"],
        key_data=json.dumps(key_data),
    )
    ee.Initialize(credentials, opt_url="https://earthengine-highvolume.googleapis.com")
    return True


def build_eudr_deforestation(bbox):
    """
    Build a multi-band image with EUDR-relevant deforestation metrics.

    Uses Hansen Global Forest Change 2024 v1.12 (30m resolution, Landsat)
    and MODIS MCD64A1 burned area (500m, monthly).
    """
    hansen = ee.Image("UMD/hansen/global_forest_change_2024_v1_12")

    # Band 1: Tree cover in year 2000 (0-100%)
    treecover_2000 = hansen.select("treecover2000")

    # Band 2: Year of loss (1-24 where 1=2001, 24=2024; 0=no loss)
    loss_year = hansen.select("lossyear").unmask(0)

    # Band 3: Binary — loss after EUDR cutoff (2020)
    # lossyear 21 = 2021, 22 = 2022, etc.
    cutoff_code = EUDR_CUTOFF_YEAR - 2000  # 20
    loss_post_2020 = loss_year.gt(cutoff_code).And(loss_year.lte(24))

    # Band 4: Approximate current tree cover
    # treecover2000 minus pixels where loss occurred (binary loss mask)
    total_loss_mask = hansen.select("loss").unmask(0)
    treecover_current = treecover_2000.multiply(
        ee.Image(1).subtract(total_loss_mask)
    )

    # Band 5: Fire post-2020 (MODIS burned area)
    fire_post_2020 = (
        ee.ImageCollection("MODIS/061/MCD64A1")
        .filterDate("2021-01-01", "2025-01-01")
        .filterBounds(bbox)
        .select("BurnDate")
        .map(lambda img: img.gt(0).unmask(0))
        .mean()
    )

    composite = (
        treecover_2000.rename("treecover_2000")
        .addBands(loss_year.rename("loss_year"))
        .addBands(loss_post_2020.rename("loss_post_2020"))
        .addBands(treecover_current.rename("treecover_current"))
        .addBands(fire_post_2020.rename("fire_post_2020"))
        .clip(bbox)
        .toFloat()
    )

    return composite


def export_region(bbox_coords, description, is_ci):
    """Export a composite for a given bounding box."""
    bbox = ee.Geometry.Rectangle(bbox_coords)
    composite = build_eudr_deforestation(bbox)

    if is_ci:
        task = ee.batch.Export.image.toCloudStorage(
            image=composite,
            description=description,
            bucket="spatia-satellite",
            fileNamePrefix=f"eudr/{description}",
            region=bbox,
            scale=EXPORT_SCALE,
            crs="EPSG:4326",
            maxPixels=2e9,
        )
    else:
        task = ee.batch.Export.image.toDrive(
            image=composite,
            description=description,
            folder=DRIVE_FOLDER,
            fileNamePrefix=description,
            region=bbox,
            scale=EXPORT_SCALE,
            crs="EPSG:4326",
            maxPixels=2e9,
        )
    task.start()
    return task


def main():
    parser = argparse.ArgumentParser(description="Export EUDR deforestation rasters from GEE")
    parser.add_argument("--province", help="Single province to export (chaco, salta, etc.)")
    parser.add_argument("--all-provinces", action="store_true",
                        help="Export each province separately")
    parser.add_argument("--combined", action="store_true", default=True,
                        help="Export combined bounding box (default)")
    parser.add_argument("--scale", type=int, default=EXPORT_SCALE,
                        help=f"Export scale in metres (default: {EXPORT_SCALE})")
    args = parser.parse_args()

    is_ci = authenticate()
    dest = "GCS" if is_ci else f"Drive ({DRIVE_FOLDER})"
    tasks = []

    if args.province:
        if args.province not in EUDR_PROVINCES:
            print(f"Unknown province: {args.province}")
            print(f"Available: {', '.join(EUDR_PROVINCES.keys())}")
            return 1
        bbox = EUDR_PROVINCES[args.province]
        desc = f"eudr_deforestation_{args.province}"
        print(f"Exporting {args.province} at {args.scale}m -> {dest}")
        task = export_region(bbox, desc, is_ci)
        tasks.append((args.province, task))

    elif args.all_provinces:
        print(f"Exporting {len(EUDR_PROVINCES)} provinces at {args.scale}m -> {dest}")
        for prov_id, bbox in EUDR_PROVINCES.items():
            desc = f"eudr_deforestation_{prov_id}"
            print(f"  Starting {prov_id}...")
            task = export_region(bbox, desc, is_ci)
            tasks.append((prov_id, task))

    else:
        # Combined export
        print(f"Exporting combined EUDR area at {args.scale}m -> {dest}")
        task = export_region(EUDR_BBOX, "eudr_deforestation_combined", is_ci)
        tasks.append(("combined", task))

    if not tasks:
        print("No tasks to run")
        return 1

    # Poll for completion
    print(f"\nWaiting for {len(tasks)} exports...")
    while True:
        statuses = [(name, t.status()["state"]) for name, t in tasks]
        running = sum(1 for _, s in statuses if s in ("READY", "RUNNING"))
        if running == 0:
            break
        status_str = ", ".join(f"{n}={s}" for n, s in statuses)
        print(f"  [{running} running] {status_str}")
        time.sleep(30)

    # Report
    print(f"\n{'=' * 60}")
    all_ok = True
    for name, task in tasks:
        status = task.status()
        if status["state"] == "COMPLETED":
            print(f"  DONE: {name}")
        else:
            print(f"  FAILED: {name} -- {status.get('error_message', 'unknown')}")
            all_ok = False

    print(f"\nFiles in Google Drive folder '{DRIVE_FOLDER}'")
    print(f"Next: python pipeline/process_deforestation_to_h3.py")
    print(f"{'=' * 60}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
