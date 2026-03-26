"""
Orchestrator: compute satellite scores → split by dept → validate → upload to R2.

Usage:
  python pipeline/run_satellite_update.py                    # Full pipeline
  python pipeline/run_satellite_update.py --skip-upload      # Local only
  python pipeline/run_satellite_update.py --skip-compute     # Split + upload only
  python pipeline/run_satellite_update.py --only env,green   # Subset of analyses
"""

import argparse
import os
import subprocess
import sys
import time

from config import OUTPUT_DIR

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DPTO_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "sat_dpto")

ALL_ANALYSES = [
    "environmental_risk", "climate_comfort", "green_capital",
    "change_pressure", "location_value", "agri_potential",
    "forest_health", "forestry_aptitude", "isolation_index",
    "territorial_gap",
]

MIN_HEXAGONS = 200_000


def run_step(description: str, cmd: list[str]) -> bool:
    """Run a subprocess step."""
    print(f"\n{'─' * 50}")
    print(f"  {description}")
    print(f"  cmd: {' '.join(cmd)}")
    print(f"{'─' * 50}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print(f"  FAILED (exit code {result.returncode})")
        return False
    return True


def validate_parquets(analyses: list[str]) -> bool:
    """Validate output parquets exist and have expected row counts."""
    import pandas as pd

    print(f"\n{'─' * 50}")
    print("  Validating parquets")
    print(f"{'─' * 50}")

    ok = True
    for aid in analyses:
        path = os.path.join(OUTPUT_DIR, f"sat_{aid}.parquet")
        if not os.path.exists(path):
            print(f"  FAIL {aid}: file missing")
            ok = False
            continue

        df = pd.read_parquet(path)
        n = len(df)
        if n < MIN_HEXAGONS:
            print(f"  FAIL {aid}: {n:,} hexes < {MIN_HEXAGONS:,}")
            ok = False
            continue

        null_frac = df["score"].isna().mean()
        if null_frac > 0.20:
            print(f"  FAIL {aid}: {null_frac:.1%} null scores")
            ok = False
            continue

        score_min = df["score"].min()
        score_max = df["score"].max()
        if score_min < 0 or score_max > 100:
            print(f"  FAIL {aid}: score range [{score_min}, {score_max}]")
            ok = False
            continue

        size_kb = os.path.getsize(path) / 1024
        print(f"  OK   {aid}: {n:,} hexes, {size_kb:.0f}KB, "
              f"score=[{score_min:.0f}, {score_max:.0f}]")

    # Check dept parquets
    for aid in analyses:
        dpto_count = len([f for f in os.listdir(DPTO_OUTPUT_DIR)
                         if f.startswith(f"sat_{aid}_") and f.endswith(".parquet")])
        if dpto_count < 15:
            print(f"  WARN {aid}: only {dpto_count} dept parquets (expected 17)")

    return ok


def upload_to_r2(analyses: list[str]) -> bool:
    """Upload parquets to R2 (reminder only — manual upload with --remote)."""
    print(f"\n{'─' * 50}")
    print("  Upload to R2")
    print(f"{'─' * 50}")

    print("  Run these commands to upload:")
    for aid in analyses:
        # Main parquet
        src = os.path.join(OUTPUT_DIR, f"sat_{aid}.parquet")
        print(f"  npx wrangler r2 object put neahub/data/sat_{aid}.parquet --file {src} --remote")

    print()
    print("  For department parquets:")
    print(f"  for f in {DPTO_OUTPUT_DIR}/sat_*.parquet; do")
    print(f"    name=$(basename $f)")
    print(f"    npx wrangler r2 object put neahub/data/sat_dpto/$name --file $f --remote")
    print(f"  done")

    # Also upload summary JSONs
    src_data = os.path.join(SCRIPT_DIR, "..", "src", "lib", "data")
    print()
    print("  For summary JSONs:")
    for aid in analyses:
        src = os.path.join(src_data, f"sat_{aid}_dept_summary.json")
        if os.path.exists(src):
            print(f"  (already in src/lib/data/ — bundled with frontend)")

    return True


def main():
    parser = argparse.ArgumentParser(description="Satellite scores pipeline orchestrator")
    parser.add_argument("--skip-compute", action="store_true", help="Skip score computation")
    parser.add_argument("--skip-split", action="store_true", help="Skip department split")
    parser.add_argument("--skip-upload", action="store_true", help="Skip R2 upload")
    parser.add_argument("--only", default=None, help="Comma-separated analysis IDs")
    args = parser.parse_args()

    t0 = time.time()

    analyses = ALL_ANALYSES
    only_flag = ""
    if args.only:
        analyses = [a for a in args.only.split(",") if a in ALL_ANALYSES]
        only_flag = f"--only {args.only}"

    print("=" * 60)
    print("  Satellite Scores Pipeline")
    print(f"  Analyses: {len(analyses)}")
    print("=" * 60)

    # Step 1: Compute scores
    if not args.skip_compute:
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, "compute_satellite_scores.py")]
        if only_flag:
            cmd += ["--only", args.only]
        if not run_step("Step 1: Compute satellite scores", cmd):
            return 1

    # Step 2: Split by department
    if not args.skip_split:
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, "split_satellite_by_dpto.py")]
        if only_flag:
            cmd += ["--only", args.only]
        if not run_step("Step 2: Split by department", cmd):
            return 1

    # Step 3: Validate
    if not validate_parquets(analyses):
        print("\nValidation FAILED — aborting upload.")
        return 1

    # Step 4: Upload
    if not args.skip_upload:
        upload_to_r2(analyses)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete in {elapsed:.0f}s")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
