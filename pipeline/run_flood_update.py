"""
Orchestrator: end-to-end flood risk layer update.

Runs the full pipeline:
  1. Authenticate to GEE
  2. Launch Sentinel-1 flood export to GCS
  3. Poll GEE tasks until completion
  4. Download GeoTIFFs from GCS
  5. Aggregate to H3 hexagons (zonal stats -> parquet)
  6. Upload parquet to Cloudflare R2
  7. Print summary

Usage:
  python pipeline/run_flood_update.py                    # current extent (default)
  python pipeline/run_flood_update.py --historical       # also recompute recurrence (~4h)
  python pipeline/run_flood_update.py --skip-gee         # use existing local GeoTIFFs
  python pipeline/run_flood_update.py --dry-run          # show steps without executing
"""

import argparse
import glob
import os
import sys
import time

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PIPELINE_DIR, "output")
GRID_PATH = os.path.join(OUTPUT_DIR, "hexagons.geojson")
PARQUET_PATH = os.path.join(OUTPUT_DIR, "hex_flood_risk.parquet")


def step(n, msg):
    """Print a step header."""
    print(f"\n{'='*60}")
    print(f"  Step {n}: {msg}")
    print(f"{'='*60}\n")


def find_local_geotiffs():
    """Find existing GeoTIFFs in the output directory."""
    files = {}
    for f in glob.glob(os.path.join(OUTPUT_DIR, "*.tif")):
        name = os.path.basename(f).lower()
        if "recurrence" in name:
            files["recurrence"] = f
        elif "current" in name:
            files["current"] = f
    return files


def run(args):
    start_time = time.time()
    downloaded = {}

    # ── Step 1-3: GEE export + poll ────────────────────────────────
    if not args.skip_gee:
        step(1, "Authenticate to Google Earth Engine")
        from gee_flood_detection import authenticate
        authenticate()
        print("  Authenticated.")

        step(2, "Launch flood export to GCS")
        from gee_flood_detection import launch_exports
        tasks = launch_exports(
            historical=args.historical,
            current=True,
            drive=False,
            days=args.days,
        )

        if not tasks:
            print("  No tasks launched. Exiting.")
            return 1

        step(3, "Poll GEE tasks until completion")
        from gee_flood_detection import wait_for_tasks
        results = wait_for_tasks(tasks, poll_interval=60, timeout=14400)
        print(f"  {len(results)} task(s) completed.")

        # ── Step 4: Download from GCS ──────────────────────────────
        step(4, "Download GeoTIFFs from GCS")
        from download_gcs import download_latest_flood
        downloaded = download_latest_flood(OUTPUT_DIR)

        if not downloaded:
            print("  ERROR: No GeoTIFFs downloaded from GCS.")
            return 1
    else:
        step("1-4", "SKIPPED (--skip-gee): using local GeoTIFFs")
        downloaded = find_local_geotiffs()
        if downloaded:
            for kind, path in downloaded.items():
                print(f"  Found {kind}: {path}")
        else:
            print("  ERROR: No local GeoTIFFs found in pipeline/output/")
            return 1

    # ── Step 5: H3 zonal stats ─────────────────────────────────────
    step(5, "Aggregate to H3 hexagons (zonal stats)")

    if not os.path.exists(GRID_PATH):
        print(f"  ERROR: hex grid not found at {GRID_PATH}")
        print("  Run `python pipeline/generate_h3_grid.py` first.")
        return 1

    from process_to_h3 import load_hex_grid, zonal_stats_sampling, compute_flood_risk_score
    import pandas as pd

    gdf = load_hex_grid(GRID_PATH)

    recurrence_path = downloaded.get("recurrence")
    current_path = downloaded.get("current")

    if recurrence_path and current_path:
        print("  Computing zonal stats for recurrence...")
        recurrence = zonal_stats_sampling(gdf, recurrence_path)
        print("  Computing zonal stats for current extent...")
        extent = zonal_stats_sampling(gdf, current_path)
        score = compute_flood_risk_score(recurrence, extent)

        df = pd.DataFrame({
            "h3index": gdf["h3index"],
            "flood_recurrence_mean": recurrence.round(4),
            "flood_extent_pct": (extent * 100).round(2),
            "flood_risk_score": score,
        })
    elif current_path:
        print("  Only current extent available (no recurrence raster).")
        print("  Computing zonal stats for current extent...")
        import numpy as np
        extent = zonal_stats_sampling(gdf, current_path)
        # Without recurrence, score = extent * 100
        df = pd.DataFrame({
            "h3index": gdf["h3index"],
            "flood_recurrence_mean": np.nan,
            "flood_extent_pct": (extent * 100).round(2),
            "flood_risk_score": (extent * 100).round(1),
        })
    else:
        print("  ERROR: No raster files to process.")
        return 1

    df = df.dropna(subset=["flood_risk_score"])
    os.makedirs(os.path.dirname(PARQUET_PATH), exist_ok=True)
    df.to_parquet(PARQUET_PATH, index=False)
    print(f"  Saved {len(df):,} hexagons to {PARQUET_PATH}")
    print(f"  Score range: {df['flood_risk_score'].min():.1f} - {df['flood_risk_score'].max():.1f}")

    # ── Step 6: Upload to R2 ───────────────────────────────────────
    step(6, "Upload parquet to Cloudflare R2")
    from upload_to_r2 import upload_file
    success = upload_file(PARQUET_PATH, "data/hex_flood_risk.parquet")
    if not success:
        print("  WARNING: R2 upload failed. Parquet is available locally.")

    # ── Step 7: Summary ────────────────────────────────────────────
    elapsed = time.time() - start_time
    step(7, "Summary")
    print(f"  Total time: {int(elapsed // 60)}m {int(elapsed % 60)}s")
    print(f"  Hexagons processed: {len(df):,}")
    print(f"  Output: {PARQUET_PATH}")
    print(f"  R2 upload: {'OK' if success else 'FAILED'}")
    print(f"  GEE skipped: {args.skip_gee}")

    return 0


def dry_run(args):
    """Show what would be executed without running anything."""
    print("\n[DRY RUN] Pipeline steps:\n")

    if not args.skip_gee:
        print("  1. Authenticate to GEE (GEE_SERVICE_ACCOUNT_KEY)")
        products = []
        if args.historical:
            products.append("historical recurrence (~4h)")
        products.append(f"current extent (last {args.days} days, ~15min)")
        print(f"  2. Launch GEE exports: {', '.join(products)}")
        print("  3. Poll GEE tasks every 60s (timeout: 4h)")
        print("  4. Download GeoTIFFs from gs://spatia-satellite/flood/")
    else:
        print("  1-4. SKIP (--skip-gee): use local GeoTIFFs from pipeline/output/")
        local = find_local_geotiffs()
        if local:
            for kind, path in local.items():
                print(f"       Found: {kind} -> {path}")
        else:
            print("       WARNING: no local GeoTIFFs found")

    print(f"  5. H3 zonal stats -> {PARQUET_PATH}")
    print(f"     Grid: {GRID_PATH}")
    print(f"     Grid exists: {os.path.exists(GRID_PATH)}")
    print("  6. Upload parquet to R2 (neahub-public/data/hex_flood_risk.parquet)")
    print("  7. Print summary\n")

    # Check env vars
    print("Environment check:")
    gee_key = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")
    cf_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    print(f"  GEE_SERVICE_ACCOUNT_KEY: {'SET' if gee_key else 'NOT SET'}")
    print(f"  CLOUDFLARE_API_TOKEN:    {'SET' if cf_token else 'NOT SET'}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="End-to-end flood risk layer update pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline/run_flood_update.py --current          # update current extent
  python pipeline/run_flood_update.py --historical       # also recompute recurrence
  python pipeline/run_flood_update.py --skip-gee         # reprocess local GeoTIFFs
  python pipeline/run_flood_update.py --dry-run          # preview steps
        """,
    )
    parser.add_argument("--historical", action="store_true",
                        help="Also regenerate historical recurrence (slow, ~4h)")
    parser.add_argument("--current", action="store_true", default=True,
                        help="Update current flood extent (default)")
    parser.add_argument("--skip-gee", action="store_true",
                        help="Skip GEE export/download, use local GeoTIFFs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show planned steps without executing")
    parser.add_argument("--days", type=int, default=12,
                        help="Days to look back for current extent (default: 12)")
    args = parser.parse_args()

    if args.dry_run:
        sys.exit(dry_run(args))
    else:
        sys.exit(run(args))


if __name__ == "__main__":
    main()
