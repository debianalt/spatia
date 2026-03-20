"""
Upload pipeline outputs to Cloudflare R2.

Uses wrangler CLI for R2 uploads. Requires CLOUDFLARE_API_TOKEN in environment.

Usage:
  python pipeline/upload_to_r2.py --file pipeline/output/hex_flood_risk.parquet --dest data/hex_flood_risk.parquet
  python pipeline/upload_to_r2.py --all  # upload all outputs
"""

import argparse
import os
import subprocess
import sys

R2_BUCKET = "neahub"

UPLOAD_MAP = {
    "hex_flood_risk.parquet": "data/hex_flood_risk.parquet",
    "h3_radio_crosswalk.parquet": "data/h3_radio_crosswalk.parquet",
    "h3_parent_crosswalk.parquet": "data/h3_parent_crosswalk.parquet",
    "hexagons-v2.pmtiles": "tiles/hexagons-v2.pmtiles",
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def upload_file(local_path: str, r2_key: str):
    """Upload a single file to R2 using wrangler."""
    if not os.path.exists(local_path):
        print(f"  [x] File not found: {local_path}")
        return False

    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    print(f"  Uploading {local_path} -> {r2_key} ({size_mb:.1f} MB)...")

    result = subprocess.run(
        ["npx", "wrangler", "r2", "object", "put",
         f"{R2_BUCKET}/{r2_key}", "--file", local_path],
        capture_output=True,
        shell=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode == 0:
        print(f"  [ok] Uploaded {r2_key}")
        return True
    else:
        err = result.stderr.strip().encode("ascii", "replace").decode("ascii")
        print(f"  [x] Failed: {err}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Upload pipeline outputs to R2")
    parser.add_argument("--file", help="Specific file to upload")
    parser.add_argument("--dest", help="R2 destination key (used with --file)")
    parser.add_argument("--all", action="store_true", help="Upload all known outputs")
    args = parser.parse_args()

    if args.file:
        dest = args.dest or os.path.basename(args.file)
        success = upload_file(args.file, dest)
        sys.exit(0 if success else 1)

    if args.all:
        successes = 0
        failures = 0
        for filename, r2_key in UPLOAD_MAP.items():
            local_path = os.path.join(OUTPUT_DIR, filename)
            if os.path.exists(local_path):
                if upload_file(local_path, r2_key):
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
