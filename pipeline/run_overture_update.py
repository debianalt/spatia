"""
Orchestrator: end-to-end Overture Indices update.

Runs the pipeline:
  1. Ingest Overture data from Source Cooperative (filtered to Misiones)
  2. Validate each parquet output
  3. Upload to Cloudflare R2

Usage:
  python pipeline/run_overture_update.py                          # all themes
  python pipeline/run_overture_update.py --theme buildings        # single theme
  python pipeline/run_overture_update.py --release 2026-03-18.0   # override release
  python pipeline/run_overture_update.py --skip-upload            # local only
  python pipeline/run_overture_update.py --dry-run                # preview
"""

import argparse
import os
import sys
import time

from config import (
    OUTPUT_DIR,
    OVERTURE_RELEASE,
    OVERTURE_THEMES,
    MIN_OVERTURE_HEXAGONS,
)


# Expected columns per theme (h3index is always present)
THEME_SCHEMA = {
    "buildings": {
        "cols": ["h3index", "building_count", "n_residential", "n_commercial", "n_industrial"],
        "ranges": {"building_count": (0, 100_000)},
        "min_rows": 30_000,
    },
    "transportation": {
        "cols": ["h3index", "segment_count", "n_road", "n_paved", "n_unpaved"],
        "ranges": {"segment_count": (0, 100_000)},
        "min_rows": 20_000,
    },
    "places": {
        "cols": ["h3index", "place_count", "n_food_and_drink", "n_health_care", "n_education"],
        "ranges": {"place_count": (0, 100_000)},
        "min_rows": 1_000,  # POIs are sparse in rural provinces
    },
    "base": {
        "cols": ["h3index", "infra_count", "landuse_count", "water_count"],
        "ranges": {},
        "min_rows": 10_000,
    },
}


def step(n, msg):
    print(f"\n{'=' * 60}")
    print(f"  Step {n}: {msg}")
    print(f"{'=' * 60}\n")


def run(args):
    start_time = time.time()
    themes = [args.theme] if args.theme else OVERTURE_THEMES

    # ── Step 1: Ingest ────────────────────────────────────────────
    step(1, f"Ingest Overture data ({', '.join(themes)})")

    ingest_args = ["--release", args.release]
    if args.theme:
        ingest_args.extend(["--theme", args.theme])

    # Run ingest as a module import rather than subprocess
    from ingest_overture import main as ingest_main
    old_argv = sys.argv
    sys.argv = ["ingest_overture.py"] + ingest_args
    ingest_result = ingest_main()
    sys.argv = old_argv

    if ingest_result != 0:
        print("  ERROR: Ingestion failed.")
        return 1

    # ── Step 2: Validate ──────────────────────────────────────────
    step(2, "Validate parquet outputs")
    from validate import validate_parquet

    validated = []
    for theme in themes:
        path = os.path.join(OUTPUT_DIR, f"overture_{theme}.parquet")
        schema = THEME_SCHEMA.get(theme, {"cols": ["h3index"], "ranges": {}, "min_rows": MIN_OVERTURE_HEXAGONS})

        is_valid = validate_parquet(
            path,
            min_rows=schema.get("min_rows", MIN_OVERTURE_HEXAGONS),
            schema_cols=schema["cols"],
            value_ranges=schema["ranges"],
        )

        if not is_valid:
            print(f"  ERROR: Validation failed for {theme}. Stopping.")
            return 1

        validated.append((theme, path))

    # ── Step 2b: Compute territorial scores ──────────────────────
    step("2b", "Compute territorial scores (8 indicators)")
    from compute_overture_scores import main as compute_scores_main
    old_argv = sys.argv
    sys.argv = ["compute_overture_scores.py"]
    scores_result = compute_scores_main()
    sys.argv = old_argv

    if scores_result != 0:
        print("  ERROR: Score computation failed.")
        return 1

    scores_path = os.path.join(OUTPUT_DIR, "overture_scores.parquet")

    # ── Step 2c: Split scores by department ──────────────────────
    step("2c", "Split scores by department")
    from split_scores_by_dpto import main as split_scores_main
    old_argv = sys.argv
    sys.argv = ["split_scores_by_dpto.py"]
    split_result = split_scores_main()
    sys.argv = old_argv

    if split_result != 0:
        print("  ERROR: Score splitting failed.")
        return 1

    # ── Step 3: Upload to R2 ──────────────────────────────────────
    if args.skip_upload:
        step(3, "SKIPPED (--skip-upload)")
    else:
        step(3, "Upload to Cloudflare R2")
        from upload_to_r2 import upload_file

        for theme, path in validated:
            r2_key = f"data/overture_{theme}.parquet"
            success = upload_file(path, r2_key)
            if not success:
                print(f"  ERROR: Upload failed for {theme}.")
                return 1

        # Upload unified scores parquet
        if os.path.exists(scores_path):
            success = upload_file(scores_path, "data/overture_scores.parquet")
            if not success:
                print("  ERROR: Upload failed for overture_scores.")
                return 1

        # Upload per-department score parquets
        scores_dpto_dir = os.path.join(OUTPUT_DIR, "scores_dpto")
        if os.path.isdir(scores_dpto_dir):
            import glob
            for f in sorted(glob.glob(os.path.join(scores_dpto_dir, "*.parquet"))):
                r2_key = f"data/scores_dpto/{os.path.basename(f)}"
                success = upload_file(f, r2_key)
                if not success:
                    print(f"  ERROR: Upload failed for {os.path.basename(f)}.")
                    return 1

    # ── Summary ───────────────────────────────────────────────────
    elapsed = time.time() - start_time
    step("Done", "Summary")
    print(f"  Total time: {int(elapsed // 60)}m {int(elapsed % 60)}s")
    print(f"  Themes: {', '.join(themes)}")
    print(f"  Release: {args.release}")
    for theme, path in validated:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  -> {theme}: {size_mb:.1f} MB")
    if os.path.exists(scores_path):
        size_mb = os.path.getsize(scores_path) / (1024 * 1024)
        print(f"  -> overture_scores: {size_mb:.1f} MB")
    if not args.skip_upload:
        print("  R2 upload: OK")

    return 0


def dry_run(args):
    themes = [args.theme] if args.theme else OVERTURE_THEMES

    print("\n[DRY RUN] Overture update pipeline:\n")
    print(f"  Release: {args.release}")
    print(f"  Themes: {', '.join(themes)}")
    print(f"  Output dir: {OUTPUT_DIR}\n")

    for theme in themes:
        path = os.path.join(OUTPUT_DIR, f"overture_{theme}.parquet")
        exists = os.path.exists(path)
        size = f" ({os.path.getsize(path) / (1024*1024):.1f} MB)" if exists else ""
        print(f"  1. Ingest {theme} from Source Cooperative")
        print(f"     -> {path} {'[exists' + size + ']' if exists else '[not yet]'}")
        schema = THEME_SCHEMA.get(theme, {})
        print(f"  2. Validate (min {MIN_OVERTURE_HEXAGONS:,} rows, cols: {schema.get('cols', ['h3index'])})")
        if not args.skip_upload:
            print(f"  3. Upload to R2: data/overture_{theme}.parquet")
        print()

    cf_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    print("Environment check:")
    print(f"  CLOUDFLARE_API_TOKEN: {'SET' if cf_token else 'NOT SET'}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="End-to-end Overture Indices update pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline/run_overture_update.py                          # all themes
  python pipeline/run_overture_update.py --theme buildings        # single theme
  python pipeline/run_overture_update.py --skip-upload            # local test
  python pipeline/run_overture_update.py --dry-run                # preview
        """,
    )
    parser.add_argument("--theme", choices=OVERTURE_THEMES,
                        help="Single theme to process (default: all)")
    parser.add_argument("--release", default=OVERTURE_RELEASE,
                        help=f"Overture release version (default: {OVERTURE_RELEASE})")
    parser.add_argument("--skip-upload", action="store_true",
                        help="Skip R2 upload (local testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show planned steps without executing")
    args = parser.parse_args()

    if args.dry_run:
        sys.exit(dry_run(args))
    else:
        sys.exit(run(args))


if __name__ == "__main__":
    main()
