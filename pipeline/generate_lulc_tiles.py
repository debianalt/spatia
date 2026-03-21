"""
Generate raster tiles from LULC GeoTIFF for MapLibre display.

Uses gdal2tiles to create a z5-z14 tile pyramid from the Dynamic World
RGB GeoTIFF. Tiles are uploaded to R2 for direct serving.

Usage:
  python pipeline/generate_lulc_tiles.py
  python pipeline/generate_lulc_tiles.py --upload  # also upload to R2

Prerequisites:
  pip install gdal  (or conda install gdal)
  Input: pipeline/output/lulc_misiones.tif
"""

import argparse
import os
import subprocess
import sys

from config import OUTPUT_DIR, R2_BUCKET

INPUT_TIF = os.path.join(OUTPUT_DIR, "lulc_misiones.tif")
TILES_DIR = os.path.join(OUTPUT_DIR, "lulc_tiles")
MIN_ZOOM = 5
MAX_ZOOM = 14


def generate_tiles():
    """Generate tile pyramid from LULC GeoTIFF."""
    if not os.path.exists(INPUT_TIF):
        print(f"ERROR: Input not found: {INPUT_TIF}")
        print("Run `python pipeline/gee_dynamic_world.py` first.")
        return False

    size_mb = os.path.getsize(INPUT_TIF) / (1024 * 1024)
    print(f"Input: {INPUT_TIF} ({size_mb:.1f} MB)")
    print(f"Output: {TILES_DIR}")
    print(f"Zoom levels: {MIN_ZOOM}-{MAX_ZOOM}")

    os.makedirs(TILES_DIR, exist_ok=True)

    # Use gdal2tiles.py
    cmd = [
        sys.executable, "-m", "osgeo_utils.gdal2tiles",
        "--zoom", f"{MIN_ZOOM}-{MAX_ZOOM}",
        "--processes", "4",
        "--resampling", "near",
        "--tmscompatible",
        "--webviewer", "none",
        "--xyz",
        INPUT_TIF,
        TILES_DIR,
    ]

    print(f"\nRunning gdal2tiles...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            # Try alternative invocation
            print("  Trying alternative gdal2tiles invocation...")
            cmd2 = [
                "gdal2tiles.py",
                "--zoom", f"{MIN_ZOOM}-{MAX_ZOOM}",
                "--processes", "4",
                "--resampling", "near",
                "--tmscompatible",
                "--webviewer", "none",
                "--xyz",
                INPUT_TIF,
                TILES_DIR,
            ]
            result = subprocess.run(cmd2, capture_output=True, text=True, timeout=1800)
            if result.returncode != 0:
                print(f"  ERROR: {result.stderr[:500]}")
                return False

    except FileNotFoundError:
        print("  ERROR: gdal2tiles not found. Install GDAL:")
        print("    pip install gdal")
        print("    or: conda install -c conda-forge gdal")
        return False

    # Count generated tiles
    tile_count = 0
    total_size = 0
    for root, dirs, files in os.walk(TILES_DIR):
        for f in files:
            if f.endswith('.png'):
                tile_count += 1
                total_size += os.path.getsize(os.path.join(root, f))

    print(f"\nGenerated {tile_count:,} tiles ({total_size / (1024*1024):.1f} MB)")
    return True


def upload_tiles():
    """Upload tile directory to R2."""
    if not os.path.isdir(TILES_DIR):
        print("ERROR: No tiles to upload")
        return False

    print(f"\nUploading tiles to R2...")
    uploaded = 0
    errors = 0

    for root, dirs, files in os.walk(TILES_DIR):
        for f in files:
            if not f.endswith('.png'):
                continue
            local_path = os.path.join(root, f)
            # Convert path to R2 key: tiles/lulc/{z}/{x}/{y}.png
            rel_path = os.path.relpath(local_path, TILES_DIR).replace('\\', '/')
            r2_key = f"tiles/lulc/{rel_path}"

            result = subprocess.run(
                ["npx", "wrangler", "r2", "object", "put",
                 f"{R2_BUCKET}/{r2_key}", "--file", local_path, "--remote"],
                capture_output=True, shell=True, encoding="utf-8", errors="replace"
            )

            if result.returncode == 0:
                uploaded += 1
                if uploaded % 100 == 0:
                    print(f"  Uploaded {uploaded} tiles...")
            else:
                errors += 1

    print(f"\nUploaded {uploaded} tiles, {errors} errors")
    return errors == 0


def main():
    parser = argparse.ArgumentParser(description="Generate LULC tiles from GeoTIFF")
    parser.add_argument("--upload", action="store_true", help="Upload tiles to R2")
    args = parser.parse_args()

    if not generate_tiles():
        sys.exit(1)

    if args.upload:
        if not upload_tiles():
            sys.exit(1)

    print("\nDone!")


if __name__ == "__main__":
    main()
