"""
CI orchestrator: GEE export → download GCS → H3 zonal stats → split → R2 upload → PDFs.

Usage:
  python pipeline/run_pixel_update.py --analyses environmental_risk,climate_comfort,green_capital
  python pipeline/run_pixel_update.py --analyses all
  python pipeline/run_pixel_update.py --analyses green_capital --skip-gee  # use local rasters
"""

import argparse
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR

PIXEL_ANALYSES = [
    "environmental_risk", "climate_comfort", "green_capital",
    "change_pressure", "agri_potential", "forest_health",
]
GCS_BUCKET = "spatia-satellite"
GCS_PREFIX = "satellite"


def run(desc, cmd, env=None):
    print(f"\n{'─' * 50}\n  {desc}\n{'─' * 50}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR, env={**os.environ, **(env or {})})
    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode})")
        return False
    return True


def download_from_gcs(analyses):
    """Download GeoTIFFs from GCS bucket."""
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
        for aid in analyses:
            blob_name = f"{GCS_PREFIX}/sat_{aid}_raster.tif"
            local_path = os.path.join(OUTPUT_DIR, f"sat_{aid}_raster.tif")
            print(f"  Downloading gs://{GCS_BUCKET}/{blob_name}...")
            blob = bucket.blob(blob_name)
            blob.download_to_filename(local_path)
            size_mb = os.path.getsize(local_path) / (1024 * 1024)
            print(f"    OK: {size_mb:.1f} MB")
        return True
    except Exception as e:
        print(f"  GCS download failed: {e}")
        return False


def download_static_from_gcs():
    """Download static reference files from GCS (needed for department split)."""
    STATIC_FILES = ["radios_misiones.parquet", "radio_stats_master.parquet"]
    needed = [f for f in STATIC_FILES if not os.path.exists(os.path.join(OUTPUT_DIR, f))]
    if not needed:
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
        for fname in needed:
            local_path = os.path.join(OUTPUT_DIR, fname)
            print(f"  Downloading gs://{GCS_BUCKET}/static/{fname}...")
            blob = bucket.blob(f"static/{fname}")
            blob.download_to_filename(local_path)
            size_mb = os.path.getsize(local_path) / (1024 * 1024)
            print(f"    OK: {size_mb:.1f} MB")
        return True
    except Exception as e:
        print(f"  Static files download failed: {e}")
        return False


def upload_to_r2(analyses):
    """Upload parquets + PDFs to R2."""
    count = 0
    for aid in analyses:
        # Main parquet
        main = os.path.join(OUTPUT_DIR, f"sat_{aid}.parquet")
        if os.path.exists(main):
            subprocess.run(["npx", "wrangler", "r2", "object", "put",
                          f"neahub/data/sat_{aid}.parquet", "--file", main, "--remote"],
                         capture_output=True)
            count += 1

        # Dept parquets
        dpto_dir = os.path.join(OUTPUT_DIR, "sat_dpto")
        for f in os.listdir(dpto_dir):
            if f.startswith(f"sat_{aid}_") and f.endswith(".parquet"):
                fpath = os.path.join(dpto_dir, f)
                subprocess.run(["npx", "wrangler", "r2", "object", "put",
                              f"neahub/data/sat_dpto/{f}", "--file", fpath, "--remote"],
                             capture_output=True)
                count += 1

        # PDFs
        report_dir = os.path.join(OUTPUT_DIR, "reports")
        if os.path.isdir(report_dir):
            for f in os.listdir(report_dir):
                if f.startswith(f"sat_{aid}_") and f.endswith(".pdf"):
                    fpath = os.path.join(report_dir, f)
                    subprocess.run(["npx", "wrangler", "r2", "object", "put",
                                  f"neahub/data/reports/{f}", "--file", fpath, "--remote"],
                                 capture_output=True)
                    count += 1

    print(f"  Uploaded {count} files to R2")
    return True


def main():
    parser = argparse.ArgumentParser(description="Pixel-level satellite update pipeline")
    parser.add_argument("--analyses", required=True, help="Comma-separated or 'all'")
    parser.add_argument("--skip-gee", action="store_true", help="Skip GEE export, use local rasters")
    parser.add_argument("--skip-upload", action="store_true", help="Skip R2 upload")
    args = parser.parse_args()

    if args.analyses == "all":
        analyses = PIXEL_ANALYSES
    else:
        analyses = [a.strip() for a in args.analyses.split(",")]

    t0 = time.time()
    print(f"{'=' * 60}")
    print(f"  Pixel-Level Satellite Update")
    print(f"  Analyses: {', '.join(analyses)}")
    print(f"{'=' * 60}")

    # Step 1: GEE Export
    if not args.skip_gee:
        if not run("Step 1: Export from GEE",
                   [sys.executable, os.path.join(SCRIPT_DIR, "gee_export_analysis.py"),
                    "--analysis", ",".join(analyses)]):
            return 1

        # Step 2: Download from GCS
        print(f"\n{'─' * 50}\n  Step 2: Download from GCS\n{'─' * 50}")
        if not download_from_gcs(analyses):
            return 1

    # Step 3: H3 zonal stats
    if not run("Step 3: Process rasters to H3",
               [sys.executable, os.path.join(SCRIPT_DIR, "process_raster_to_h3.py"),
                "--analysis", ",".join(analyses)]):
        return 1

    # Step 3b: Download static reference files (if in CI)
    if not download_static_from_gcs():
        return 1

    # Step 4: Split by department
    if not run("Step 4: Split by department",
               [sys.executable, os.path.join(SCRIPT_DIR, "split_satellite_by_dpto.py"),
                "--only", ",".join(analyses)]):
        return 1

    # Step 5: Generate PDFs
    run("Step 5: Generate PDF reports",
        [sys.executable, os.path.join(SCRIPT_DIR, "generate_dept_report.py"),
         "--only", ",".join(analyses)])

    # Step 6: Upload to R2
    if not args.skip_upload:
        print(f"\n{'─' * 50}\n  Step 6: Upload to R2\n{'─' * 50}")
        upload_to_r2(analyses)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete in {elapsed:.0f}s")
    print(f"{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
