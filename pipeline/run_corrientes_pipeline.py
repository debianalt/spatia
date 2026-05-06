"""
Orchestrator: full satellite pipeline for Corrientes (AR).

Steps:
  0. [manual] Run build_admin_crosswalk.py to build hex grid + radio crosswalk
  1. GEE exports (batched) -> satellite/corrientes/sat_{id}_raster.tif in GCS
  2. Download rasters from GCS -> pipeline/output/corrientes/
  3. process_raster_to_h3 -> pipeline/output/corrientes/sat_{id}.parquet
  4. split_by_admin -> pipeline/output/corrientes/sat_dpto/sat_{id}_{dpto}.parquet
  5. R2 upload -> neahub/data/corrientes/... (requires --upload flag; uses wrangler --remote)
  6. [manual] Set available: true in TERRITORY_REGISTRY in config.ts

Usage:
  # Full run (skips already-done steps):
  python pipeline/run_corrientes_pipeline.py

  # Only specific analyses:
  python pipeline/run_corrientes_pipeline.py --only environmental_risk,forest_health

  # Skip GEE exports (rasters already downloaded):
  python pipeline/run_corrientes_pipeline.py --skip-gee

  # Also upload to R2 at the end:
  python pipeline/run_corrientes_pipeline.py --upload

  # Dry run (print commands without executing):
  python pipeline/run_corrientes_pipeline.py --dry-run

Pre-flight requirement:
  python pipeline/build_admin_crosswalk.py --territory corrientes --source gadm \\
    --shapefile pipeline/data/ARG_adm2.shp

Analyses NOT in this orchestrator (require separate scripts):
  carbon_stock         -> gee_export_carbon_stock.py --territory corrientes --gcs
  pm25_drivers         -> gee_export_pm25_annual.py --territory corrientes --gcs
  productive_activity  -> gee_export_activity_rasters.py --territory corrientes --gcs
  soil_water           -> gee_export_soil_water.py --territory corrientes --gcs
  deforestation_dynamics -> included in gee_export_analysis.py
  forestry_aptitude    -> compute_forestry_sdm.py --territory corrientes
  flood_risk           -> run_flood_update.py --territory corrientes

GEE analysis order (estimated export time at 100m, Corrientes bbox ~88k km²):
  Fast  (<5 min):  environmental_risk, climate_comfort, green_capital, change_pressure,
                   forest_health
  Medium (5-15m):  agri_potential, land_use (MapBiomas AR)
"""

import argparse
import os
import subprocess
import sys
import time

from config import OUTPUT_DIR, GCS_BUCKET, R2_BUCKET, get_territory

TERRITORY_ID = 'corrientes'

# Analyses routed through gee_export_analysis.py (ANALYSIS_BUILDERS must have them)
ALL_SAT_ANALYSES = [
    # Fast batch
    "environmental_risk", "climate_comfort", "green_capital",
    "change_pressure", "forest_health",
    # Medium batch
    "agri_potential",
    # MapBiomas AR covers all of Argentina including Corrientes
    "land_use",
    # NOT included — require separate scripts (see module docstring)
]

# GCS path template: gs://spatia-satellite/satellite/corrientes/sat_{id}_raster.tif
GCS_RASTER_PREFIX = f"satellite/{TERRITORY_ID}/"


def run(cmd: str, dry_run: bool = False) -> int:
    print(f"\n  $ {cmd}")
    if dry_run:
        return 0
    result = subprocess.run(cmd, shell=True)
    return result.returncode


def step_gee_export(analyses: list[str], dry_run: bool) -> bool:
    """Submit GEE export tasks in batches."""
    print("\n" + "=" * 60)
    print("  STEP 1: GEE Exports")
    print("=" * 60)
    fast = [a for a in analyses if a in {
        "environmental_risk", "climate_comfort", "green_capital",
        "change_pressure", "forest_health",
    }]
    medium = [a for a in analyses if a in {"agri_potential", "land_use"}]

    for batch_name, batch in [("fast", fast), ("medium", medium)]:
        if not batch:
            continue
        ids = ",".join(batch)
        rc = run(
            f"python pipeline/gee_export_analysis.py "
            f"--territory {TERRITORY_ID} --analysis {ids} --gcs",
            dry_run
        )
        if rc != 0:
            print(f"  ERROR in {batch_name} GEE batch (rc={rc})")
            return False
    return True


def step_download_gcs(analyses: list[str], out_dir: str, dry_run: bool) -> bool:
    """Download rasters from GCS to local output directory."""
    print("\n" + "=" * 60)
    print("  STEP 2: Download from GCS")
    print("=" * 60)
    os.makedirs(out_dir, exist_ok=True)
    for aid in analyses:
        gcs_path = f"gs://{GCS_BUCKET}/{GCS_RASTER_PREFIX}sat_{aid}_raster.tif"
        local_path = os.path.join(out_dir, f"sat_{aid}_raster.tif")
        if os.path.exists(local_path):
            print(f"  SKIP {aid}: already downloaded")
            continue
        rc = run(f"gcloud storage cp {gcs_path} {local_path}", dry_run)
        if rc != 0:
            print(f"  WARNING: failed to download {aid} (may not be done yet)")
    return True


def step_process_h3(analyses: list[str], dry_run: bool) -> bool:
    """Run process_raster_to_h3 for each analysis."""
    print("\n" + "=" * 60)
    print("  STEP 3: Raster -> H3 parquets")
    print("=" * 60)
    ids = ",".join(analyses)
    rc = run(
        f"python pipeline/process_raster_to_h3.py "
        f"--territory {TERRITORY_ID} --analysis {ids}",
        dry_run
    )
    return rc == 0


def step_split_admin(analyses: list[str], dry_run: bool) -> bool:
    """Split parquets by departamento."""
    print("\n" + "=" * 60)
    print("  STEP 4: Split by Admin Unit (departamentos)")
    print("=" * 60)
    ids = ",".join(analyses)
    rc = run(
        f"python pipeline/split_by_admin.py "
        f"--territory {TERRITORY_ID} --only {ids}",
        dry_run
    )
    return rc == 0


def step_upload_r2(analyses: list[str], out_dir: str, dry_run: bool) -> bool:
    """Upload parquets to R2 under data/corrientes/ prefix."""
    print("\n" + "=" * 60)
    print("  STEP 5: Upload to R2")
    print("=" * 60)
    r2_prefix = f"data/{TERRITORY_ID}"

    # Global parquets
    for aid in analyses:
        local = os.path.join(out_dir, f"sat_{aid}.parquet")
        if not os.path.exists(local):
            print(f"  SKIP {aid} (global): file not found")
            continue
        r2_key = f"{R2_BUCKET}/{r2_prefix}/sat_{aid}.parquet"
        rc = run(
            f"npx wrangler r2 object put {r2_key} --file {local} --remote",
            dry_run
        )
        if rc != 0:
            print(f"  ERROR uploading {aid} (global)")
            return False

    # Per-admin parquets
    dpto_dir = os.path.join(out_dir, "sat_dpto")
    if not os.path.isdir(dpto_dir):
        print(f"  SKIP per-admin uploads: {dpto_dir} not found")
        return True

    for fname in sorted(os.listdir(dpto_dir)):
        if not fname.endswith(".parquet"):
            continue
        local = os.path.join(dpto_dir, fname)
        r2_key = f"{R2_BUCKET}/{r2_prefix}/sat_dpto/{fname}"
        rc = run(
            f"npx wrangler r2 object put {r2_key} --file {local} --remote",
            dry_run
        )
        if rc != 0:
            print(f"  ERROR uploading {fname}")
            return False

    print(f"\n  All uploads complete. R2 path: data/corrientes/")
    print(f"  Next: set available: true for corrientes in src/lib/config.ts")
    return True


def main():
    parser = argparse.ArgumentParser(description="Corrientes satellite pipeline orchestrator")
    parser.add_argument("--only", default=None,
                        help="Comma-separated analysis IDs (default: all)")
    parser.add_argument("--skip-gee", action="store_true",
                        help="Skip GEE exports (rasters already in GCS or downloaded)")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip GCS download (rasters already local)")
    parser.add_argument("--upload", action="store_true",
                        help="Upload results to R2 after processing")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without executing")
    args = parser.parse_args()

    territory = get_territory(TERRITORY_ID)
    t_prefix = territory['output_prefix']
    out_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/'))

    analyses = ALL_SAT_ANALYSES
    if args.only:
        analyses = [a.strip() for a in args.only.split(',') if a.strip() in ALL_SAT_ANALYSES]
        if not analyses:
            print(f"No valid analyses. Available: {ALL_SAT_ANALYSES}")
            return 1

    print("=" * 60)
    print(f"  Corrientes Pipeline — {len(analyses)} analyses")
    print(f"  Output dir: {out_dir}")
    print(f"  Dry run: {args.dry_run}")
    print("=" * 60)

    # ── Pre-flight check ──
    crosswalk_path = os.path.join(out_dir, 'h3_admin_crosswalk.parquet')
    hexgrid_path = os.path.join(out_dir, 'hexagons.geojson')
    if not os.path.exists(crosswalk_path) or not os.path.exists(hexgrid_path):
        print("\n  PRE-FLIGHT FAILED: Admin crosswalk or hex grid not found.")
        print("  Run first:")
        print(f"    python pipeline/build_admin_crosswalk.py --territory {TERRITORY_ID} --source gadm \\")
        print(f"      --shapefile pipeline/data/ARG_adm2.shp")
        if not args.dry_run:
            return 1

    t0 = time.time()

    if not args.skip_gee:
        if not step_gee_export(analyses, args.dry_run):
            return 1

    if not args.skip_download:
        if not step_download_gcs(analyses, out_dir, args.dry_run):
            return 1

    if not step_process_h3(analyses, args.dry_run):
        return 1

    if not step_split_admin(analyses, args.dry_run):
        return 1

    if args.upload:
        if not step_upload_r2(analyses, out_dir, args.dry_run):
            return 1

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete in {elapsed/60:.1f} min")
    if not args.upload:
        print(f"  Run with --upload to push to R2")
    print(f"  Then: set available: true for corrientes in src/lib/config.ts")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
