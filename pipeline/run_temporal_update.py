"""
CI orchestrator: temporal baseline+current pipeline.

GEE export (current, optionally baseline) → download GCS → H3 temporal process
→ split by dept → generate PDFs → upload to R2.

Usage:
  python pipeline/run_temporal_update.py --analyses all
  python pipeline/run_temporal_update.py --analyses green_capital,forest_health
  python pipeline/run_temporal_update.py --analyses all --include-baseline   # first run
  python pipeline/run_temporal_update.py --analyses all --skip-gee           # reprocess local
"""

import argparse
import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR, GCS_BUCKET, TERRITORY_CONFIGS, get_territory

# change_pressure, forest_health, green_capital, agri_potential EXCLUDED
# from temporal: their temporal variants (dynamic_*) emit a DIFFERENT /
# FEWER component set than the canonical pixel build_* (what Misiones has
# + config petalVars + goalposts pca_variable_selection expect), and the
# temporal run OVERWRITES the canonical parquet. Verified breaks:
# change_pressure (trend→level), forest_health (c_ndvi_trend→c_ndvi_mean),
# green_capital (Cor/Ita lost scored c_treecover), agri_potential (Cor/Ita
# lost scored c_soc/c_ph_optimal/c_clay). RULE: temporal must NEVER clobber
# a pixel-canonical analysis with a divergent/reduced component set. These
# stay strictly on the pixel pipeline. Remaining temporal = env_risk
# (de-facto inactive: baseline 100% nodata) + climate_comfort (verified
# 4-territory consistent).
TEMPORAL_ANALYSES = [
    "environmental_risk", "climate_comfort",
]
GCS_PREFIX = "satellite"


def _run_npx(args, **kwargs):
    """subprocess.run for npx. On Windows npx is npx.cmd → needs shell=True
    (cmd.exe resolves via PATHEXT); list-form without shell raises WinError 2.
    POSIX/CI keeps shell=False so the list executes directly (unchanged)."""
    return subprocess.run(args, shell=(sys.platform == "win32"), **kwargs)


def baseline_r2_prefix(output_prefix):
    """R2 prefix for cached baselines. Empty output_prefix = Misiones legacy path."""
    return f"neahub/data/{output_prefix}temporal_baseline"


def territory_output_dir(output_prefix):
    """Local dir where rasters/parquets for this territory live."""
    if not output_prefix:
        return OUTPUT_DIR
    return os.path.join(OUTPUT_DIR, output_prefix.rstrip("/"))


def r2_data_path(output_prefix, *parts):
    """Build an R2 key under neahub/data/<output_prefix>/<parts>."""
    return f"neahub/data/{output_prefix}" + "/".join(parts)


def run(desc, cmd):
    print(f"\n{'─' * 50}\n  {desc}\n{'─' * 50}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode})")
        return False
    return True


def download_from_gcs(analyses, suffixes, output_prefix):
    """Download temporal GeoTIFFs from GCS bucket for the given territory prefix."""
    try:
        from google.cloud import storage

        key_env = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")
        if key_env and not os.path.isfile(key_env):
            key_data = json.loads(key_env)
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(key_data)
            client = storage.Client(credentials=credentials, project=key_data.get("project_id"))
        else:
            client = storage.Client()

        local_dir = territory_output_dir(output_prefix)
        os.makedirs(local_dir, exist_ok=True)
        bucket = client.bucket(GCS_BUCKET)
        for aid in analyses:
            for suffix in suffixes:
                blob_name = f"{GCS_PREFIX}/{output_prefix}sat_{aid}_{suffix}.tif"
                local_path = os.path.join(local_dir, f"sat_{aid}_{suffix}.tif")

                # Skip baseline download if already exists locally
                if suffix == 'baseline' and os.path.exists(local_path):
                    size_mb = os.path.getsize(local_path) / (1024 * 1024)
                    print(f"  Cached: sat_{aid}_{suffix}.tif ({size_mb:.1f} MB)")
                    continue

                print(f"  Downloading gs://{GCS_BUCKET}/{blob_name}...")
                blob = bucket.blob(blob_name)
                if not blob.exists():
                    print(f"    NOT FOUND — skipping")
                    continue
                blob.download_to_filename(local_path)
                size_mb = os.path.getsize(local_path) / (1024 * 1024)
                print(f"    OK: {size_mb:.1f} MB")
        return True
    except Exception as e:
        print(f"  GCS download failed: {e}")
        return False


def download_baseline_from_r2(analyses, output_prefix):
    """Download baseline rasters from R2 if not locally cached."""
    local_dir = territory_output_dir(output_prefix)
    os.makedirs(local_dir, exist_ok=True)
    prefix = baseline_r2_prefix(output_prefix)
    for aid in analyses:
        local_path = os.path.join(local_dir, f"sat_{aid}_baseline.tif")
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            continue
        r2_key = f"{prefix}/sat_{aid}_baseline.tif"
        print(f"  Downloading baseline from R2: {r2_key}...")
        result = _run_npx(
            ["npx", "wrangler", "r2", "object", "get", r2_key,
             "--file", local_path, "--remote"],
            capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    WARN: baseline not in R2 — will need --include-baseline on first run")
            if os.path.exists(local_path):
                os.remove(local_path)
        elif os.path.exists(local_path) and os.path.getsize(local_path) == 0:
            print(f"    WARN: downloaded baseline is 0 bytes, removing")
            os.remove(local_path)


def upload_baseline_to_r2(analyses, output_prefix):
    """Upload baseline rasters to R2 for future runs."""
    local_dir = territory_output_dir(output_prefix)
    prefix = baseline_r2_prefix(output_prefix)
    for aid in analyses:
        local_path = os.path.join(local_dir, f"sat_{aid}_baseline.tif")
        if not os.path.exists(local_path):
            continue
        r2_key = f"{prefix}/sat_{aid}_baseline.tif"
        print(f"  Uploading baseline: {r2_key}")
        _run_npx(
            ["npx", "wrangler", "r2", "object", "put", r2_key,
             "--file", local_path, "--remote"],
            capture_output=True)


def upload_outputs_to_r2(analyses, output_prefix):
    """Upload parquets + PDFs to R2 under neahub/data/<prefix>."""
    count = 0
    local_dir = territory_output_dir(output_prefix)
    for aid in analyses:
        main = os.path.join(local_dir, f"sat_{aid}.parquet")
        if os.path.exists(main):
            r2_key = f"neahub/data/{output_prefix}sat_{aid}.parquet"
            _run_npx(["npx", "wrangler", "r2", "object", "put",
                          r2_key, "--file", main, "--remote"],
                         capture_output=True)
            count += 1

        dpto_dir = os.path.join(local_dir, "sat_dpto")
        if os.path.isdir(dpto_dir):
            for f in os.listdir(dpto_dir):
                if f.startswith(f"sat_{aid}_") and f.endswith(".parquet"):
                    fpath = os.path.join(dpto_dir, f)
                    r2_key = f"neahub/data/{output_prefix}sat_dpto/{f}"
                    _run_npx(["npx", "wrangler", "r2", "object", "put",
                                  r2_key, "--file", fpath, "--remote"],
                                 capture_output=True)
                    count += 1

        report_dir = os.path.join(local_dir, "reports")
        if os.path.isdir(report_dir):
            for f in os.listdir(report_dir):
                if f.startswith(f"sat_{aid}_") and f.endswith(".pdf"):
                    fpath = os.path.join(report_dir, f)
                    r2_key = f"neahub/data/{output_prefix}reports/{f}"
                    _run_npx(["npx", "wrangler", "r2", "object", "put",
                                  r2_key, "--file", fpath, "--remote"],
                                 capture_output=True)
                    count += 1

    print(f"  Uploaded {count} files to R2")
    return True


def main():
    parser = argparse.ArgumentParser(description="Temporal baseline+current satellite pipeline")
    parser.add_argument("--analyses", required=True, help="Comma-separated or 'all'")
    parser.add_argument("--include-baseline", action="store_true",
                        help="Also export baseline from GEE (first run or re-calibration)")
    parser.add_argument("--skip-gee", action="store_true", help="Skip GEE export, use local rasters")
    parser.add_argument("--skip-upload", action="store_true", help="Skip R2 upload")
    parser.add_argument("--territory", default="misiones",
                        choices=list(TERRITORY_CONFIGS.keys()),
                        help="Territory ID (defaults to misiones for backward compat)")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    output_prefix = territory['output_prefix']  # '' for misiones, 'corrientes/', 'itapua_py/'

    if args.analyses == "all":
        analyses = TEMPORAL_ANALYSES
    else:
        analyses = [a.strip() for a in args.analyses.split(",")]

    mode = "both" if args.include_baseline else "current"

    t0 = time.time()
    print(f"{'=' * 60}")
    print(f"  Temporal Satellite Update")
    print(f"  Territory: {territory['label']} ({args.territory})")
    print(f"  Analyses: {', '.join(analyses)}")
    print(f"  Mode: {mode}")
    print(f"{'=' * 60}")

    # Step 1: GEE Export
    if not args.skip_gee:
        if not run("Step 1: Export temporal composites from GEE",
                   [sys.executable, os.path.join(SCRIPT_DIR, "gee_export_analysis_temporal.py"),
                    "--analysis", ",".join(analyses), "--mode", mode,
                    "--territory", args.territory, "--gcs"]):
            return 1

        # Step 2: Download from GCS (always fetch baseline too — cached if exists)
        suffixes = ['current', 'baseline']
        print(f"\n{'─' * 50}\n  Step 2: Download from GCS\n{'─' * 50}")
        if not download_from_gcs(analyses, suffixes, output_prefix):
            return 1

        # Upload baseline to R2 for future runs
        if args.include_baseline:
            print(f"\n{'─' * 50}\n  Step 2b: Cache baseline in R2\n{'─' * 50}")
            upload_baseline_to_r2(analyses, output_prefix)

    # Ensure baseline rasters exist (download from R2 if needed)
    print(f"\n{'─' * 50}\n  Ensure baselines available\n{'─' * 50}")
    download_baseline_from_r2(analyses, output_prefix)

    # Step 3: H3 temporal processing (baseline + current → deltas)
    if not run("Step 3: Process temporal rasters to H3 with deltas",
               [sys.executable, os.path.join(SCRIPT_DIR, "process_raster_temporal.py"),
                "--analysis", ",".join(analyses),
                "--territory", args.territory]):
        return 1

    # Step 4: Split by admin (Misiones-only for now — Cor/Itapua use their own splitters)
    if args.territory == "misiones":
        radios_path = os.path.join(OUTPUT_DIR, "radios_misiones.parquet")
        if os.path.exists(radios_path):
            if not run("Step 4: Split by department",
                       [sys.executable, os.path.join(SCRIPT_DIR, "split_satellite_by_dpto.py"),
                        "--only", ",".join(analyses)]):
                print("  WARN: split failed, continuing with main parquets only")
        else:
            print(f"\n{'─' * 50}\n  Step 4: SKIP split (radios_misiones.parquet not available)\n{'─' * 50}")
    else:
        # split_by_admin.py supports --territory for non-Misiones territories
        split_by_admin = os.path.join(SCRIPT_DIR, "split_by_admin.py")
        if os.path.exists(split_by_admin):
            run(f"Step 4: Split by admin ({args.territory})",
                [sys.executable, split_by_admin,
                 "--territory", args.territory,
                 "--only", ",".join(analyses)])
        else:
            print(f"\n{'─' * 50}\n  Step 4: SKIP split (split_by_admin.py not found)\n{'─' * 50}")

    # Step 5: Generate PDFs (Misiones-only — non-fatal for other territories)
    if args.territory == "misiones":
        run("Step 5: Generate PDF reports",
            [sys.executable, os.path.join(SCRIPT_DIR, "generate_dept_report.py"),
             "--only", ",".join(analyses)])

    # Step 6: Upload to R2
    if not args.skip_upload:
        print(f"\n{'─' * 50}\n  Step 6: Upload to R2\n{'─' * 50}")
        upload_outputs_to_r2(analyses, output_prefix)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Temporal pipeline complete in {elapsed:.0f}s")
    print(f"{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
