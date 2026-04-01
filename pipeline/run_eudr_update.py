"""
CI orchestrator: EUDR deforestation pipeline.

Steps:
  1. Generate H3 grid (if not exists)
  2. Export from GEE (Hansen GFC + MODIS fire)
  3. Download raster from Google Drive
  4. Process raster to H3 parquet
  5. Validate output
  6. Upload to R2

Usage:
  python pipeline/run_eudr_update.py
  python pipeline/run_eudr_update.py --skip-gee       # use local raster
  python pipeline/run_eudr_update.py --skip-upload     # don't upload to R2
"""

import argparse
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config_eudr import OUTPUT_DIR, GRID_PATH, PARQUET_PATH, R2_EUDR_PREFIX


GCS_BUCKET = "spatia-satellite"


def download_from_gcs():
    """Download EUDR raster from GCS after GEE export."""
    raster_name = "eudr_deforestation_combined.tif"
    local_path = os.path.join(OUTPUT_DIR, raster_name)
    if os.path.exists(local_path):
        print(f"  Raster already exists: {local_path}")
        return True
    try:
        from google.cloud import storage
        import json

        key_env = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")
        if key_env and not os.path.isfile(key_env):
            key_data = json.loads(key_env)
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(key_data)
            client = storage.Client(credentials=credentials, project=key_data.get("project_id"))
        else:
            client = storage.Client()

        bucket = client.bucket(GCS_BUCKET)
        blob_name = f"eudr/{raster_name}"
        print(f"  Downloading gs://{GCS_BUCKET}/{blob_name}...")
        blob = bucket.blob(blob_name)
        blob.download_to_filename(local_path)
        size_mb = os.path.getsize(local_path) / (1024 * 1024)
        print(f"    OK: {size_mb:.1f} MB")
        return True
    except Exception as e:
        print(f"  GCS download failed: {e}")
        return False


def run(desc, cmd):
    print(f"\n{'─' * 50}\n  {desc}\n{'─' * 50}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode})")
        return False
    return True


def upload_to_r2():
    """Upload EUDR parquets to R2."""
    count = 0

    # Main parquet
    if os.path.exists(PARQUET_PATH):
        subprocess.run(
            ["npx", "wrangler", "r2", "object", "put",
             f"neahub/{R2_EUDR_PREFIX}/eudr_deforestation.parquet",
             "--file", PARQUET_PATH, "--remote"],
            capture_output=True, shell=True,
        )
        count += 1
        print(f"  [ok] Uploaded eudr_deforestation.parquet")

    # Province parquets
    province_dir = os.path.join(OUTPUT_DIR, "by_province")
    if os.path.isdir(province_dir):
        for f in os.listdir(province_dir):
            if f.endswith(".parquet"):
                fpath = os.path.join(province_dir, f)
                subprocess.run(
                    ["npx", "wrangler", "r2", "object", "put",
                     f"neahub/{R2_EUDR_PREFIX}/by_province/{f}",
                     "--file", fpath, "--remote"],
                    capture_output=True, shell=True,
                )
                count += 1

    print(f"  Uploaded {count} files to R2")
    return True


def main():
    parser = argparse.ArgumentParser(description="EUDR deforestation pipeline orchestrator")
    parser.add_argument("--skip-gee", action="store_true", help="Skip GEE export, use local raster")
    parser.add_argument("--skip-upload", action="store_true", help="Skip R2 upload")
    args = parser.parse_args()

    t0 = time.time()
    print(f"{'=' * 60}")
    print(f"  EUDR Deforestation Pipeline")
    print(f"{'=' * 60}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Step 1: Generate H3 grid
    if not os.path.exists(GRID_PATH):
        if not run("Step 1: Generate EUDR H3 grid",
                    [sys.executable, os.path.join(SCRIPT_DIR, "generate_eudr_h3_grid.py")]):
            return 1
    else:
        print(f"\n  Step 1: EUDR H3 grid exists ({GRID_PATH}), skipping")

    # Step 2: GEE Export
    if not args.skip_gee:
        if not run("Step 2: Export from GEE",
                    [sys.executable, os.path.join(SCRIPT_DIR, "gee_deforestation_eudr.py")]):
            return 1

        # Step 3: Download from GCS
        print(f"\n{'─' * 50}")
        print(f"  Step 3: Download raster from GCS")
        print(f"{'─' * 50}")
        if not download_from_gcs():
            return 1
    else:
        print(f"\n  Steps 2-3: Skipped (--skip-gee)")

    # Step 4: Process raster to H3
    if not run("Step 4: Process deforestation raster to H3",
                [sys.executable, os.path.join(SCRIPT_DIR, "process_deforestation_to_h3.py")]):
        return 1

    # Step 5: Upload to R2
    if not args.skip_upload:
        print(f"\n{'─' * 50}\n  Step 5: Upload to R2\n{'─' * 50}")
        upload_to_r2()
    else:
        print(f"\n  Step 5: Skipped (--skip-upload)")

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete in {elapsed:.0f}s")
    print(f"  Output: {PARQUET_PATH}")
    print(f"{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
