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
from datetime import datetime, timedelta

import ee


# ── Configuration ──────────────────────────────────────────────────────────

MISIONES_BBOX = [-55.95, -28.17, -53.60, -25.47]  # [W, S, E, N]
VV_THRESHOLD_DB = -15  # dB threshold for water detection
EXPORT_SCALE = 30  # metres per pixel (S1 GRD native ~10m, 30m for efficiency)
GCS_BUCKET = "spatia-satellite"  # Google Cloud Storage bucket
EXPORT_PREFIX = "flood"


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


def get_misiones_aoi() -> ee.Geometry:
    """Return Misiones bounding box as EE geometry."""
    return ee.Geometry.Rectangle(MISIONES_BBOX)


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
        # Only process if there are images
        composite = col.median()
        water = compute_water_mask(composite)
        return water

    # Stack all monthly water masks
    water_images = [monthly_water(m) for m in months]
    stack = ee.ImageCollection(water_images)

    # Recurrence = mean across all months (fraction 0–1)
    recurrence = stack.mean().rename("flood_recurrence").toFloat()
    # Count of valid months
    count = stack.count().rename("valid_months").toUint16()

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


def export_to_gcs(image: ee.Image, description: str, aoi: ee.Geometry):
    """Export image to Google Cloud Storage."""
    task = ee.batch.Export.image.toCloudStorage(
        image=image,
        description=description,
        bucket=GCS_BUCKET,
        fileNamePrefix=f"{EXPORT_PREFIX}/{description}",
        region=aoi,
        scale=EXPORT_SCALE,
        crs="EPSG:4326",
        maxPixels=1e10,
        fileFormat="GeoTIFF",
    )
    task.start()
    print(f"  → Export started: {description} (task ID: {task.id})")
    return task


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
    print(f"  → Export started: {description} (task ID: {task.id})")
    return task


def main():
    parser = argparse.ArgumentParser(description="Sentinel-1 flood detection for Misiones")
    parser.add_argument("--historical", action="store_true", help="Compute historical recurrence (slow, one-time)")
    parser.add_argument("--current", action="store_true", help="Compute current flood extent (fast, biweekly)")
    parser.add_argument("--drive", action="store_true", help="Export to Google Drive instead of GCS")
    parser.add_argument("--days", type=int, default=12, help="Days to look back for current extent")
    args = parser.parse_args()

    if not args.historical and not args.current:
        args.current = True  # default to current

    print("Authenticating to Google Earth Engine...")
    authenticate()

    aoi = get_misiones_aoi()
    export_fn = export_to_drive if args.drive else export_to_gcs
    tasks = []

    if args.historical:
        print("Computing historical flood recurrence (2015–present)...")
        recurrence = compute_historical_recurrence(aoi)
        task = export_fn(recurrence, "flood_recurrence_historical", aoi)
        tasks.append(task)

    if args.current:
        date_str = datetime.now().strftime("%Y%m%d")
        print(f"Computing current flood extent (last {args.days} days)...")
        current = compute_current_extent(aoi, days_back=args.days)
        task = export_fn(current, f"flood_current_{date_str}", aoi)
        tasks.append(task)

    print(f"\n{len(tasks)} export task(s) started.")
    print("Monitor progress at: https://code.earthengine.google.com/tasks")


if __name__ == "__main__":
    main()
