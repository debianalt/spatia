"""Local orchestrator for temporal pipeline (after GEE exports complete).

Runs: Drive download -> H3 processing -> dept split -> R2 upload.
Assumes GEE exports already completed to Drive folder 'spatia-satellite'.

Usage:
  python pipeline/run_temporal_local.py
  python pipeline/run_temporal_local.py --skip-download
  python pipeline/run_temporal_local.py --skip-upload
"""
import argparse
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR

TEMPORAL_ANALYSES = [
    'environmental_risk', 'climate_comfort', 'green_capital',
    'change_pressure', 'agri_potential', 'forest_health',
]


def run(desc, cmd):
    print(f"\n{'=' * 60}\n  {desc}\n{'=' * 60}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode})")
        return False
    return True


def upload_to_r2(analyses):
    """Upload main + dept parquets to R2."""
    count = 0
    for aid in analyses:
        main = os.path.join(OUTPUT_DIR, f'sat_{aid}.parquet')
        if os.path.exists(main):
            print(f'  Uploading sat_{aid}.parquet...')
            subprocess.run(
                ['npx', 'wrangler', 'r2', 'object', 'put',
                 f'neahub/data/sat_{aid}.parquet', '--file', main, '--remote'],
                capture_output=True)
            count += 1

        dpto_dir = os.path.join(OUTPUT_DIR, 'sat_dpto')
        if os.path.isdir(dpto_dir):
            for f in os.listdir(dpto_dir):
                if f.startswith(f'sat_{aid}_') and f.endswith('.parquet'):
                    fpath = os.path.join(dpto_dir, f)
                    print(f'  Uploading sat_dpto/{f}...')
                    subprocess.run(
                        ['npx', 'wrangler', 'r2', 'object', 'put',
                         f'neahub/data/sat_dpto/{f}', '--file', fpath, '--remote'],
                        capture_output=True)
                    count += 1

    print(f'  Uploaded {count} files to R2')


def main():
    parser = argparse.ArgumentParser(description='Local temporal pipeline (post-GEE)')
    parser.add_argument('--skip-download', action='store_true')
    parser.add_argument('--skip-upload', action='store_true')
    parser.add_argument('--only', default=None, help='Comma-separated analysis IDs')
    args = parser.parse_args()

    analyses = TEMPORAL_ANALYSES
    if args.only:
        analyses = [a.strip() for a in args.only.split(',')]

    t0 = time.time()
    print(f"Temporal Local Pipeline")
    print(f"Analyses: {', '.join(analyses)}")

    # Step 1: Download from Drive
    if not args.skip_download:
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, 'download_temporal_from_drive.py')]
        if args.only:
            cmd.extend(['--only', args.only])
        if not run('Step 1: Download temporal rasters from Drive', cmd):
            print('  WARN: some downloads may have failed, continuing...')

    # Verify rasters exist
    missing = []
    for aid in analyses:
        for suffix in ['baseline', 'current']:
            path = os.path.join(OUTPUT_DIR, f'sat_{aid}_{suffix}.tif')
            if not os.path.exists(path):
                missing.append(f'sat_{aid}_{suffix}.tif')
    if missing:
        print(f'\nERROR: Missing rasters: {missing}')
        print('Run GEE exports first or check Drive downloads.')
        return 1

    # Step 2: Process to H3 with deltas
    if not run('Step 2: Process temporal rasters to H3',
               [sys.executable, os.path.join(SCRIPT_DIR, 'process_raster_temporal.py'),
                '--analysis', ','.join(analyses)]):
        return 1

    # Step 3: Split by department
    radios_path = os.path.join(OUTPUT_DIR, 'radios_misiones.parquet')
    if os.path.exists(radios_path):
        if not run('Step 3: Split by department',
                   [sys.executable, os.path.join(SCRIPT_DIR, 'split_satellite_by_dpto.py'),
                    '--only', ','.join(analyses)]):
            print('  WARN: split failed, continuing')
    else:
        print(f'\n  SKIP Step 3: radios_misiones.parquet not found')

    # Step 4: Upload to R2
    if not args.skip_upload:
        print(f"\n{'=' * 60}\n  Step 4: Upload to R2\n{'=' * 60}")
        upload_to_r2(analyses)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete in {elapsed:.0f}s")
    print(f"  Next: bump cache-buster in config.ts and deploy")
    print(f"{'=' * 60}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
