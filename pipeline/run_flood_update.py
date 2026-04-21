"""
Orchestrator: end-to-end flood risk layer update.

Runs the full pipeline:
  1. Authenticate to GEE
  2. Launch Sentinel-1 flood export to GCS
  3. Poll GEE tasks until completion
  4. Download GeoTIFFs from GCS
  5. Aggregate to H3 hexagons (zonal stats -> parquet)
  6. Validate parquet output
  7. Upload parquet to Cloudflare R2
  8. Print summary

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

from config import (
    PIPELINE_DIR, OUTPUT_DIR, GRID_PATH, PARQUET_PATH,
    GCS_BUCKET, R2_BUCKET, MIN_HEXAGONS, SCORE_RANGE, get_territory,
)


def step(n, msg):
    """Print a step header."""
    print(f"\n{'='*60}")
    print(f"  Step {n}: {msg}")
    print(f"{'='*60}\n")


def find_local_geotiffs(directory=None):
    """Find existing GeoTIFFs in the output directory."""
    if directory is None:
        directory = OUTPUT_DIR
    files = {}
    for f in glob.glob(os.path.join(directory, "*.tif")):
        name = os.path.basename(f).lower()
        if "jrc_occurrence" in name:
            files["jrc_occurrence"] = f
        elif "jrc_recurrence" in name:
            files["jrc_recurrence"] = f
        elif "jrc_seasonality" in name:
            files["jrc_seasonality"] = f
        elif name.startswith("flood_current") or name.startswith("sentinel1_flood"):
            files["current"] = f
        elif "recurrence" in name:
            files["recurrence"] = f
    return files


def run(args):
    start_time = time.time()
    downloaded = {}

    # Territory-aware paths
    territory = get_territory(args.territory)
    t_prefix = territory['output_prefix']                    # '' or 'itapua_py/'
    t_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/')) if t_prefix else OUTPUT_DIR
    grid_path = os.path.join(t_dir, 'hexagons.geojson') if t_prefix else GRID_PATH
    parquet_path = os.path.join(t_dir, 'hex_flood_risk.parquet') if t_prefix else PARQUET_PATH
    r2_key = f"data/{t_prefix}hex_flood_risk.parquet"
    r2_dpto_prefix = f"data/{t_prefix}flood_dpto/"

    # ── Step 1-3: GEE export + poll ────────────────────────────────
    if not args.skip_gee:
        step(1, "Authenticate to Google Earth Engine")
        from gee_flood_detection import authenticate
        authenticate()
        print("  Authenticated.")

        step(2, "Launch flood export to GCS")
        from gee_flood_detection import launch_exports
        tasks = launch_exports(
            territory_id=args.territory,
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
        downloaded = find_local_geotiffs(t_dir)
        if downloaded:
            for kind, path in downloaded.items():
                print(f"  Found {kind}: {path}")
        else:
            print(f"  ERROR: No local GeoTIFFs found in {t_dir}")
            return 1

    # ── Step 5: H3 zonal stats ─────────────────────────────────────
    step(5, "Aggregate to H3 hexagons (zonal stats)")

    if not os.path.exists(grid_path):
        print(f"  ERROR: hex grid not found at {grid_path}")
        print("  Run `python pipeline/generate_h3_grid.py` first.")
        return 1

    from process_to_h3 import load_hex_grid, zonal_stats_rasterio, compute_flood_risk_score
    import pandas as pd
    import numpy as np

    gdf = load_hex_grid(grid_path)

    jrc_occ_path = downloaded.get("jrc_occurrence")
    jrc_rec_path = downloaded.get("jrc_recurrence")
    jrc_sea_path = downloaded.get("jrc_seasonality")
    current_path = downloaded.get("current")

    if not current_path and not jrc_occ_path:
        print("  ERROR: No raster files to process.")
        return 1

    # JRC Global Surface Water (historical, 1984-2021)
    if jrc_occ_path:
        print("  Computing zonal stats for JRC occurrence...")
        jrc_occurrence = zonal_stats_rasterio(gdf, jrc_occ_path)
    else:
        jrc_occurrence = pd.Series(np.nan, index=gdf.index)

    if jrc_rec_path:
        print("  Computing zonal stats for JRC recurrence...")
        jrc_recurrence = zonal_stats_rasterio(gdf, jrc_rec_path)
    else:
        jrc_recurrence = pd.Series(np.nan, index=gdf.index)

    if jrc_sea_path:
        print("  Computing zonal stats for JRC seasonality...")
        jrc_seasonality = zonal_stats_rasterio(gdf, jrc_sea_path)
    else:
        jrc_seasonality = pd.Series(np.nan, index=gdf.index)

    # Sentinel-1 current extent (binary mask: 0=dry, 1=water, nodata=0 conflicts)
    if current_path:
        print("  Computing zonal stats for S1 current extent...")
        s1_extent = zonal_stats_rasterio(gdf, current_path, ignore_src_nodata=True)
    else:
        s1_extent = pd.Series(0.0, index=gdf.index)

    # Composite score
    score = compute_flood_risk_score(
        jrc_occurrence.fillna(0), jrc_recurrence.fillna(0), (s1_extent * 100).fillna(0)
    )

    df = pd.DataFrame({
        "h3index": gdf["h3index"],
        "jrc_occurrence": jrc_occurrence.round(2),
        "jrc_recurrence": jrc_recurrence.round(2),
        "jrc_seasonality": jrc_seasonality.round(1),
        "flood_extent_pct": (s1_extent * 100).round(2),
        "flood_risk_score": score,
    })

    df = df.dropna(subset=["flood_risk_score"])
    os.makedirs(t_dir, exist_ok=True)
    df.to_parquet(parquet_path, index=False)
    print(f"  Saved {len(df):,} hexagons to {parquet_path}")
    print(f"  Score range: {df['flood_risk_score'].min():.1f} - {df['flood_risk_score'].max():.1f}")

    # ── Step 6: Validate parquet before upload ─────────────────────
    step(6, "Validate parquet output")
    from validate import validate_parquet

    is_valid = validate_parquet(
        parquet_path,
        min_rows=MIN_HEXAGONS,
        schema_cols=["h3index", "flood_risk_score"],
        value_ranges={"flood_risk_score": SCORE_RANGE},
    )

    if not is_valid:
        print("  ERROR: Parquet validation failed. NOT uploading to R2.")
        return 1

    # ── Step 7: Upload to R2 ───────────────────────────────────────
    step(7, "Upload parquet to Cloudflare R2")
    from upload_to_r2 import upload_file
    success = upload_file(parquet_path, r2_key)
    if not success:
        print("  ERROR: R2 upload failed after retries.")
        return 1

    # ── Step 8: Split by department + upload ──────────────────────
    step(8, "Split by department and upload to R2")
    try:
        import subprocess as _sp
        split_script = os.path.join(PIPELINE_DIR, "split_flood_by_dpto.py")
        result = _sp.run([sys.executable, split_script, '--territory', args.territory], cwd=PIPELINE_DIR)
        if result.returncode != 0:
            print("  WARNING: Department splitting failed, continuing...")
        else:
            # Upload department parquets to R2
            dept_dir = os.path.join(t_dir, "flood_dpto")
            if os.path.isdir(dept_dir):
                dept_files = [f for f in os.listdir(dept_dir) if f.endswith(".parquet")]
                uploaded = 0
                for fname in dept_files:
                    fpath = os.path.join(dept_dir, fname)
                    r2_dpto_key = f"{r2_dpto_prefix}{fname}"
                    if upload_file(fpath, r2_dpto_key, versioned=False):
                        uploaded += 1
                print(f"  Uploaded {uploaded}/{len(dept_files)} department parquets to R2")
    except Exception as e:
        print(f"  WARNING: Department split/upload failed: {e}")

    # ── Step 9: Summary ────────────────────────────────────────────
    elapsed = time.time() - start_time
    step(9, "Summary")
    print(f"  Total time: {int(elapsed // 60)}m {int(elapsed % 60)}s")
    print(f"  Hexagons processed: {len(df):,}")
    print(f"  Output: {parquet_path}")
    print(f"  R2 upload: OK")
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
        print(f"  4. Download GeoTIFFs from gs://{GCS_BUCKET}/flood/")
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
    print(f"  6. Validate parquet (min {MIN_HEXAGONS:,} rows, score {SCORE_RANGE})")
    print(f"  7. Upload parquet to R2 ({R2_BUCKET}/data/hex_flood_risk.parquet)")
    print("  8. Split by department + upload department parquets to R2")
    print("  9. Print summary\n")

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
    parser.add_argument("--territory", default="misiones",
                        help="Territory ID (default: misiones)")
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
