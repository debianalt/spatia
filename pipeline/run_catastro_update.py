"""
Orchestrator: end-to-end catastro layer update (no PostgreSQL).

Pipeline:
  1. Download previous state from Cloudflare R2
  2. Download WFS parcels + compute changes (GeoPandas)
  3. Spatial aggregation: catastro_by_radio
  4. Validate parquets
  5. Upload to Cloudflare R2 (state + outputs)
  6. Summary + log

Usage:
  python pipeline/run_catastro_update.py                    # full run
  python pipeline/run_catastro_update.py --skip-wfs         # skip WFS, reprocess existing state
  python pipeline/run_catastro_update.py --skip-upload      # no R2 upload
  python pipeline/run_catastro_update.py --dry-run          # show steps only
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import pandas as pd

from config import OUTPUT_DIR, R2_BUCKET, MIN_RADIOS_CATASTRO

RADIOS_PATH = os.path.join(OUTPUT_DIR, "radios_misiones.parquet")
STATE_DIR = os.path.join(OUTPUT_DIR, "catastro_state")
CATASTRO_PARQUET = os.path.join(OUTPUT_DIR, "catastro_by_radio.parquet")
CHANGES_PARQUET = os.path.join(OUTPUT_DIR, "catastro_changes_summary.parquet")
RUN_LOG = os.path.join(OUTPUT_DIR, "catastro_run_log.jsonl")

# R2 keys for state persistence
R2_STATE_FILES = {
    "catastro_rural.parquet": "data/catastro_state/catastro_rural.parquet",
    "catastro_urbano.parquet": "data/catastro_state/catastro_urbano.parquet",
    "catastro_changes_history.parquet": "data/catastro_state/catastro_changes_history.parquet",
}
R2_OUTPUT_FILES = {
    CATASTRO_PARQUET: "data/catastro_by_radio.parquet",
    CHANGES_PARQUET: "data/catastro_changes_summary.parquet",
}


def step(n, msg):
    print(f"\n{'=' * 60}")
    print(f"  Step {n}: {msg}")
    print(f"{'=' * 60}\n")


# ── Step 1: Download state from R2 ──────────────────────────────────────────


def download_state_from_r2():
    """Download previous catastro state + radios from R2."""
    from upload_to_r2 import download_file

    os.makedirs(STATE_DIR, exist_ok=True)
    downloaded = 0

    # Download radios_misiones.parquet if not present locally
    if not os.path.exists(RADIOS_PATH):
        print("  Downloading radios_misiones.parquet from R2...")
        if download_file("data/radios_misiones.parquet", RADIOS_PATH):
            downloaded += 1
        else:
            print("  [x] CRITICAL: radios_misiones.parquet not found in R2")

    # Download catastro state files
    for filename, r2_key in R2_STATE_FILES.items():
        local_path = os.path.join(STATE_DIR, filename)
        if download_file(r2_key, local_path):
            downloaded += 1
    print(f"  Downloaded {downloaded} files from R2")
    return downloaded


# ── Step 4: Validate ─────────────────────────────────────────────────────────


def validate_parquets():
    """Validate exported parquets before upload."""
    print("  Validating parquets...")
    ok = True

    if not os.path.exists(CATASTRO_PARQUET):
        print(f"  [x] Missing: {CATASTRO_PARQUET}")
        return False

    df = pd.read_parquet(CATASTRO_PARQUET)
    if len(df) < MIN_RADIOS_CATASTRO:
        print(f"  [x] catastro_by_radio: {len(df)} rows < {MIN_RADIOS_CATASTRO} minimum")
        ok = False
    required = ["redcode", "n_parcelas_rural", "n_parcelas_urbano"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"  [x] catastro_by_radio: missing columns {missing}")
        ok = False
    if df["redcode"].isna().any():
        print(f"  [x] catastro_by_radio: null redcodes found")
        ok = False

    if os.path.exists(CHANGES_PARQUET):
        df_ch = pd.read_parquet(CHANGES_PARQUET)
        required_ch = ["change_date", "parcel_type", "change_type", "n"]
        missing_ch = [c for c in required_ch if c not in df_ch.columns]
        if missing_ch:
            print(f"  [x] catastro_changes: missing columns {missing_ch}")
            ok = False

    if ok:
        print("  [ok] All parquets valid")
    return ok


# ── Main ─────────────────────────────────────────────────────────────────────


def run(args):
    start_time = time.time()
    extraction_stats = None

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Step 1: Download state from R2 ────────────────────────────
    if not args.skip_wfs:
        step(1, "Download previous state from R2")
        if args.dry_run:
            print("  [dry-run] Would download catastro state parquets from R2")
        else:
            download_state_from_r2()
    else:
        step(1, "Download state from R2 [SKIPPED — using local state]")

    # ── Step 2: WFS download + processing ─────────────────────────
    step(2, "WFS Catastro -> GeoParquet + spatial aggregation")
    if args.dry_run:
        print("  [dry-run] Would download ~445K parcels from WFS, compute changes, spatial join")
    else:
        from catastro_extract import run_extraction

        extraction_stats = run_extraction(
            output_dir=OUTPUT_DIR,
            radios_path=RADIOS_PATH,
            state_dir=STATE_DIR,
            skip_wfs=args.skip_wfs,
        )
        if extraction_stats is None:
            print("\n  [x] Extraction failed.")
            return 1

        print(f"\n  Rural: {extraction_stats['rural_count']:,}")
        print(f"  Urban: {extraction_stats['urban_count']:,}")
        print(f"  New: {extraction_stats['new_parcels']:,}, "
              f"Removed: {extraction_stats['removed_parcels']:,}")

    # ── Step 3: Validate ──────────────────────────────────────────
    step(3, "Validate parquets")
    if args.dry_run:
        print("  [dry-run] Would validate min rows, columns, nulls")
    else:
        if not validate_parquets():
            print("\n  [x] Validation failed. Aborting upload.")
            return 1

    # ── Step 4: Upload to R2 ──────────────────────────────────────
    if not args.skip_upload:
        step(4, "Upload to Cloudflare R2")
        if args.dry_run:
            print("  [dry-run] Would upload state + output parquets to R2")
        else:
            from upload_to_r2 import upload_file

            # Upload state files (for next run)
            for filename, r2_key in R2_STATE_FILES.items():
                local = os.path.join(STATE_DIR, filename)
                if os.path.exists(local):
                    upload_file(local, r2_key, versioned=False)

            # Upload output files (for frontend)
            for local, r2_key in R2_OUTPUT_FILES.items():
                if os.path.exists(local):
                    upload_file(local, r2_key, versioned=True)
                else:
                    print(f"  [warn] Skipping {local} (not found)")
    else:
        step(4, "Upload to Cloudflare R2 [SKIPPED]")

    # ── Step 5: Summary ───────────────────────────────────────────
    step(5, "Summary")
    elapsed = time.time() - start_time

    if not args.dry_run and extraction_stats:
        print(f"  Rural parcels: {extraction_stats['rural_count']:,}")
        print(f"  Urban parcels: {extraction_stats['urban_count']:,}")
        print(f"  Changes today: {extraction_stats['changes_today']}")
        print(f"  Elapsed: {elapsed:.0f}s ({elapsed / 60:.1f} min)")

        log_entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "duration_s": round(elapsed),
            "rural_count": extraction_stats["rural_count"],
            "urban_count": extraction_stats["urban_count"],
            "new_parcels": extraction_stats["new_parcels"],
            "removed_parcels": extraction_stats["removed_parcels"],
            "r2_upload": not args.skip_upload,
        }

        with open(RUN_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
        print(f"  Log appended to {RUN_LOG}")
    else:
        print(f"  [dry-run] Would log run stats. Elapsed: {elapsed:.0f}s")

    print("\nDone.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Catastro pipeline: WFS -> GeoParquet -> R2 (no PostgreSQL)"
    )
    parser.add_argument(
        "--skip-wfs", action="store_true", help="Skip WFS download, reprocess existing state"
    )
    parser.add_argument(
        "--skip-upload", action="store_true", help="Skip R2 upload"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show steps without executing"
    )
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(run(args))


if __name__ == "__main__":
    main()
