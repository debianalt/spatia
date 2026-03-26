"""
Export Dynamic World annual composite for Misiones to Google Drive.

Dynamic World is a 10m near-real-time land use/land cover dataset from Google.
9 classes: water, trees, grass, flooded_vegetation, crops, shrub_and_scrub,
           built, bare, snow_and_ice

Usage:
  python pipeline/gee_dynamic_world.py
  python pipeline/gee_dynamic_world.py --year 2024
"""

import argparse
import ee
import sys
import time

from config import MISIONES_BBOX

ASSET = 'GOOGLE/DYNAMICWORLD/V1'
CLASSES = ['water', 'trees', 'grass', 'flooded_vegetation', 'crops',
           'shrub_and_scrub', 'built', 'bare', 'snow_and_ice']
SCALE = 100  # Export at 100m (aggregate from 10m — sufficient for H3 res-9)


def main():
    parser = argparse.ArgumentParser(description="Export Dynamic World composite to Drive")
    parser.add_argument("--year", type=int, default=2024, help="Year for composite")
    args = parser.parse_args()

    year = args.year
    print(f"Exporting Dynamic World {year} for Misiones...")

    ee.Initialize()

    bbox = ee.Geometry.Rectangle(MISIONES_BBOX)

    # Filter collection to year
    start = f"{year}-01-01"
    end = f"{year}-12-31"

    dw = (ee.ImageCollection(ASSET)
          .filterBounds(bbox)
          .filterDate(start, end))

    n_images = dw.size().getInfo()
    print(f"  Images in collection: {n_images}")

    if n_images == 0:
        print("ERROR: No images found for this year/region")
        return 1

    # Compute mode (most frequent class) per pixel
    label_mode = dw.select('label').mode().clip(bbox)

    # Also compute mean probability per class (more useful for H3 aggregation)
    class_probs = dw.select(CLASSES).mean().clip(bbox)

    # Export class probabilities (mean fraction per class)
    task_probs = ee.batch.Export.image.toDrive(
        image=class_probs,
        description=f'dw_probs_{year}',
        folder='spatia-satellite',
        fileNamePrefix=f'dw_probs_{year}',
        region=bbox,
        scale=SCALE,
        crs='EPSG:4326',
        maxPixels=1e9,
    )
    task_probs.start()
    print(f"  Started export: dw_probs_{year} (scale={SCALE}m)")

    # Export label mode
    task_label = ee.batch.Export.image.toDrive(
        image=label_mode.toInt8(),
        description=f'dw_label_{year}',
        folder='spatia-satellite',
        fileNamePrefix=f'dw_label_{year}',
        region=bbox,
        scale=SCALE,
        crs='EPSG:4326',
        maxPixels=1e9,
    )
    task_label.start()
    print(f"  Started export: dw_label_{year} (scale={SCALE}m)")

    # Poll for completion
    print("\n  Waiting for exports to complete...")
    tasks = [task_probs, task_label]
    while True:
        statuses = [t.status()['state'] for t in tasks]
        running = sum(1 for s in statuses if s in ('READY', 'RUNNING'))
        if running == 0:
            break
        print(f"    {statuses} ...")
        time.sleep(30)

    for t in tasks:
        status = t.status()
        if status['state'] == 'COMPLETED':
            print(f"  DONE: {status['description']}")
        else:
            print(f"  FAILED: {status['description']} — {status.get('error_message', 'unknown')}")
            return 1

    print("\n  Files exported to Google Drive folder 'spatia-satellite'")
    print("  Download them and run process_dw_to_h3.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
