"""
Upload pipeline outputs to Cloudflare R2.

Uses wrangler CLI for R2 uploads. Requires CLOUDFLARE_API_TOKEN in environment.
Uploads with versioning: archive/{date}/ + latest path.

Usage:
  python pipeline/upload_to_r2.py --file pipeline/output/hex_flood_risk.parquet --dest data/hex_flood_risk.parquet
  python pipeline/upload_to_r2.py --all  # upload all outputs
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime

from config import R2_BUCKET, OUTPUT_DIR


UPLOAD_MAP = {
    "hex_flood_risk.parquet": "data/hex_flood_risk.parquet",
    "h3_radio_crosswalk.parquet": "data/h3_radio_crosswalk.parquet",
    "h3_parent_crosswalk.parquet": "data/h3_parent_crosswalk.parquet",
    "hexagons-v2.pmtiles": "tiles/hexagons-v2.pmtiles",
}


def _run_wrangler_upload(local_path: str, r2_key: str) -> bool:
    """Execute a single wrangler R2 upload, return True on success."""
    result = subprocess.run(
        ["npx", "wrangler", "r2", "object", "put",
         f"{R2_BUCKET}/{r2_key}", "--file", local_path, "--remote"],
        capture_output=True,
        shell=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode == 0:
        return True
    else:
        err = result.stderr.strip().encode("ascii", "replace").decode("ascii")
        print(f"  [x] wrangler failed for {r2_key}: {err}")
        return False


def upload_file(local_path: str, r2_key: str, versioned: bool = True) -> bool:
    """
    Upload a single file to R2 using wrangler.

    If versioned=True, uploads to data/archive/{YYYY-MM-DD}/{filename} first,
    then to the latest path (r2_key).
    Retries up to 2 attempts with a brief pause between.
    """
    if not os.path.exists(local_path):
        print(f"  [x] File not found: {local_path}")
        return False

    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    print(f"  Uploading {local_path} -> {r2_key} ({size_mb:.1f} MB)...")

    # Versioned archive upload
    if versioned:
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = os.path.basename(r2_key)
        # Derive archive prefix from the r2_key directory
        key_dir = os.path.dirname(r2_key)
        archive_key = f"{key_dir}/archive/{date_str}/{filename}"
        print(f"  Archiving to {archive_key}...")

        # Archive upload (best-effort, don't block on failure)
        for attempt in range(2):
            if _run_wrangler_upload(local_path, archive_key):
                print(f"  [ok] Archived {archive_key}")
                break
            if attempt == 0:
                print(f"  Retrying archive upload...")
        else:
            print(f"  [warn] Archive upload failed, continuing with latest...")

    # Latest upload (this is the critical one)
    for attempt in range(2):
        if _run_wrangler_upload(local_path, r2_key):
            print(f"  [ok] Uploaded {r2_key}")
            return True
        if attempt == 0:
            print(f"  Retrying upload...")

    print(f"  [x] Upload failed after 2 attempts: {r2_key}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Upload pipeline outputs to R2")
    parser.add_argument("--file", help="Specific file to upload")
    parser.add_argument("--dest", help="R2 destination key (used with --file)")
    parser.add_argument("--all", action="store_true", help="Upload all known outputs")
    parser.add_argument("--no-version", action="store_true",
                        help="Skip archive versioning")
    args = parser.parse_args()

    if args.file:
        dest = args.dest or os.path.basename(args.file)
        success = upload_file(args.file, dest, versioned=not args.no_version)
        sys.exit(0 if success else 1)

    if args.all:
        successes = 0
        failures = 0
        for filename, r2_key in UPLOAD_MAP.items():
            local_path = os.path.join(OUTPUT_DIR, filename)
            if os.path.exists(local_path):
                if upload_file(local_path, r2_key, versioned=not args.no_version):
                    successes += 1
                else:
                    failures += 1
            else:
                print(f"  - Skipping {filename} (not found)")

        print(f"\nDone: {successes} uploaded, {failures} failed")
        sys.exit(0 if failures == 0 else 1)

    parser.print_help()


if __name__ == "__main__":
    main()
