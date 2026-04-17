"""
Google Earth Engine: Sentinel-1 SAR flood detection for Misiones.

Two products:
  1. Historical flood recurrence (2015–present): monthly S1 composites,
     VV < -15 dB threshold → binary water mask, sum → recurrence per pixel.
  2. Current flood extent: last 12 days S1 → extent of inundation.

Exports GeoTIFFs to Google Cloud Storage for downstream H3 aggregation.

Usage:
  python pipeline/gee_flood_detection.py [--historical] [--current]

Environment:
  GEE_SERVICE_ACCOUNT_KEY  — path to JSON key or JSON string
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

import ee

from config import VV_THRESHOLD_DB, EXPORT_SCALE, GCS_BUCKET, EXPORT_PREFIX, get_territory


def authenticate():
    """Authenticate to GEE using service account key."""
    key_env = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")

    if not key_env:
        # Try default credentials (local dev)
        ee.Initialize(opt_url="https://earthengine-highvolume.googleapis.com")
        return

    # Parse JSON key
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


def get_territory_aoi(territory_id: str) -> ee.Geometry:
    """Return territory bounding box as EE geometry."""
    return ee.Geometry.Rectangle(get_territory(territory_id)['bbox'])


def get_s1_collection(aoi: ee.Geometry, start: str, end: str) -> ee.ImageCollection:
    """
    Get Sentinel-1 GRD collection filtered to Misiones AOI.
    VV polarisation, IW mode, descending orbit.
    """
    return (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
        .select("VV")
    )


def compute_water_mask(image: ee.Image) -> ee.Image:
    """Binary water mask: 1 where VV < threshold (dB)."""
    return image.lt(VV_THRESHOLD_DB).rename("water").toUint8()


def compute_historical_recurrence(aoi: ee.Geometry) -> ee.Image:
    """
    Historical flood recurrence: fraction of months with water detected.
    Uses monthly median composites from 2015 to present.
    """
    start_year = 2015
    end_year = datetime.now().year
    months = []

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            start = f"{year}-{month:02d}-01"
            if month == 12:
                end = f"{year + 1}-01-01"
            else:
                end = f"{year}-{month + 1:02d}-01"

            # Skip future months
            if datetime(year, month, 1) > datetime.now():
                break

            months.append((start, end))

    def monthly_water(period):
        start, end = period
        col = get_s1_collection(aoi, start, end)
        # Fully-masked fallback when no S1 images exist for this month
        empty = ee.Image.constant(0).rename('water').toUint8().updateMask(ee.Image.constant(0))
        water = ee.Image(ee.Algorithms.If(
            col.size().gt(0),
            compute_water_mask(col.median()),
            empty,
        ))
        return water

    # Stack all monthly water masks
    water_images = [monthly_water(m) for m in months]
    stack = ee.ImageCollection(water_images)

    # Recurrence = mean across all months (fraction 0–1)
    recurrence = stack.mean().rename("flood_recurrence").toFloat()
    # Count of valid months
    count = stack.count().rename("valid_months").toFloat()

    return recurrence.addBands(count)


def compute_current_extent(aoi: ee.Geometry, days_back: int = 12) -> ee.Image:
    """
    Current flood extent: water detected in the last N days.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    col = get_s1_collection(
        aoi,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )

    # Median composite of recent images
    composite = col.median()
    water = compute_water_mask(composite)

    return water.rename("current_flood").toUint8()


def export_to_gcs(image: ee.Image, description: str, aoi: ee.Geometry, territory_id: str = 'misiones'):
    """Export image to Google Cloud Storage."""
    task = ee.batch.Export.image.toCloudStorage(
        image=image,
        description=description,
        bucket=GCS_BUCKET,
        fileNamePrefix=f"{EXPORT_PREFIX}/{territory_id}/{description}",
        region=aoi,
        scale=EXPORT_SCALE,
        crs="EPSG:4326",
        maxPixels=1e10,
        fileFormat="GeoTIFF",
    )
    task.start()
    print(f"  -> Export started: {description} (task ID: {task.id})")
    return task


def wait_for_tasks(tasks, poll_interval=60, timeout=14400):
    """
    Poll GEE task status until all tasks complete or fail.

    Args:
        tasks: list of ee.batch.Task objects
        poll_interval: seconds between status checks (default 60)
        timeout: max wait time in seconds (default 4 hours)

    Returns:
        list of dicts with task metadata (id, state, description, output_uri)

    Raises:
        RuntimeError: if any task fails or timeout is reached
    """
    if not tasks:
        return []

    task_ids = {t.id: t for t in tasks}
    start_time = time.time()
    completed = {}

    print(f"\nWaiting for {len(tasks)} GEE task(s)...")

    while len(completed) < len(tasks):
        elapsed = time.time() - start_time
        if elapsed > timeout:
            pending = [tid for tid in task_ids if tid not in completed]
            raise RuntimeError(
                f"Timeout after {timeout/3600:.1f}h. "
                f"Pending tasks: {pending}"
            )

        statuses = ee.data.getTaskStatus([t.id for t in tasks])

        for status in statuses:
            tid = status["id"]
            state = status["state"]

            if tid in completed:
                continue

            if state == "COMPLETED":
                desc = status.get("description", tid)
                output_uri = status.get("destination_uris", [""])[0]
                print(f"  [OK] {desc} — {output_uri}")
                completed[tid] = {
                    "id": tid,
                    "state": state,
                    "description": desc,
                    "output_uri": output_uri,
                }
            elif state in ("FAILED", "CANCELLED"):
                desc = status.get("description", tid)
                error = status.get("error_message", "unknown error")
                raise RuntimeError(f"Task {desc} {state}: {error}")

        if len(completed) < len(tasks):
            remaining = len(tasks) - len(completed)
            mins = int(elapsed // 60)
            print(f"  [{mins}m] {remaining} task(s) still running...", flush=True)
            time.sleep(poll_interval)

    print(f"All {len(tasks)} task(s) completed in {int(elapsed // 60)}m.")
    return list(completed.values())


def export_to_drive(image: ee.Image, description: str, aoi: ee.Geometry):
    """Export image to Google Drive (fallback for no GCS)."""
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder="spatia_flood",
        region=aoi,
        scale=EXPORT_SCALE,
        crs="EPSG:4326",
        maxPixels=1e10,
        fileFormat="GeoTIFF",
    )
    task.start()
    print(f"  -> Export started: {description} (task ID: {task.id})")
    return task


def launch_exports(territory_id='misiones', historical=False, current=True, drive=False, days=12):
    """
    Launch GEE export tasks. Returns list of (task, description) tuples.
    Called by orchestrator or CLI.
    """
    aoi = get_territory_aoi(territory_id)
    export_fn = export_to_drive if drive else lambda img, desc, a: export_to_gcs(img, desc, a, territory_id)
    tasks = []

    if historical:
        print("Computing historical flood recurrence (2015-present)...")
        recurrence = compute_historical_recurrence(aoi)
        task = export_fn(recurrence, "flood_recurrence_historical", aoi)
        tasks.append(task)

    if current:
        date_str = datetime.now().strftime("%Y%m%d")
        print(f"Computing current flood extent (last {days} days)...")
        extent = compute_current_extent(aoi, days_back=days)
        task = export_fn(extent, f"flood_current_{date_str}", aoi)
        tasks.append(task)

    print(f"\n{len(tasks)} export task(s) started.")
    return tasks


def main():
    parser = argparse.ArgumentParser(description="Sentinel-1 flood detection")
    parser.add_argument("--territory", default="misiones", help="Territory ID (default: misiones)")
    parser.add_argument("--historical", action="store_true", help="Compute historical recurrence (slow, one-time)")
    parser.add_argument("--current", action="store_true", help="Compute current flood extent (fast, biweekly)")
    parser.add_argument("--drive", action="store_true", help="Export to Google Drive instead of GCS")
    parser.add_argument("--days", type=int, default=12, help="Days to look back for current extent")
    parser.add_argument("--wait", action="store_true", help="Poll tasks until completion (for automation)")
    args = parser.parse_args()

    if not args.historical and not args.current:
        args.current = True  # default to current

    print("Authenticating to Google Earth Engine...")
    authenticate()

    tasks = launch_exports(
        territory_id=args.territory,
        historical=args.historical,
        current=args.current,
        drive=args.drive,
        days=args.days,
    )

    if args.wait and tasks:
        results = wait_for_tasks(tasks)
        for r in results:
            print(f"  {r['description']}: {r['output_uri']}")
    else:
        print("Monitor progress at: https://code.earthengine.google.com/tasks")


if __name__ == "__main__":
    main()
