"""
Corrientes pipeline runner: polls GEE and processes analyses as they complete.
Handles pm25, accessibility, soil_water, flood, plus split+upload to R2.
Run from neahub/ directory.
"""
import os
import sys
import subprocess
import time
import json
import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
T_DIR = os.path.join(SCRIPT_DIR, 'output', 'corrientes')

# On Windows, gcloud is a .cmd file — use shell=True or the .cmd path
GCLOUD = r'C:\Users\ant\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
NPX = r'C:\Program Files\nodejs\npx.cmd'
DPTO_DIR = os.path.join(T_DIR, 'sat_dpto')

sys.path.insert(0, SCRIPT_DIR)


def gee_init():
    import ee
    key_env = os.environ.get('GEE_SERVICE_ACCOUNT_KEY', '')
    if key_env and not os.path.isfile(key_env):
        key_data = json.loads(key_env)
        creds = ee.ServiceAccountCredentials(key_data['client_email'], key_data=key_data)
        ee.Initialize(creds)
    else:
        ee.Initialize()
    return ee


def get_gee_status(ee):
    tasks = ee.data.getTaskList()
    running = {t['description'] for t in tasks if t['state'] == 'RUNNING'}
    done = {t['description'] for t in tasks if t['state'] == 'COMPLETED'}
    return running, done


def gcs_download(src_url, dest_dir):
    print(f"  DL {os.path.basename(src_url)}...")
    r = subprocess.run([GCLOUD, 'storage', 'cp', src_url, dest_dir],
                       cwd=ROOT_DIR, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  FAIL: {r.stderr.strip()}")
        return False
    return True


def run(script, *args):
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script)] + list(args)
    print(f"  RUN: {script} {' '.join(args)}")
    r = subprocess.run(cmd, cwd=ROOT_DIR)
    return r.returncode == 0


def r2_upload(local_path, r2_key):
    r = subprocess.run(
        [NPX, 'wrangler', 'r2', 'object', 'put', f'neahub/{r2_key}',
         '--file', local_path, '--remote'],
        cwd=ROOT_DIR, capture_output=True, text=True, shell=True
    )
    if r.returncode != 0:
        print(f"  R2 FAIL {r2_key}: {r.stderr[-200:]}")
        return False
    return True


def split_and_upload(analysis_id):
    print(f"  Splitting {analysis_id} by dpto...")
    ok = run('split_by_admin.py', '--territory', 'corrientes', '--only', analysis_id)
    if not ok:
        print(f"  split failed for {analysis_id}")
        return False

    # Upload global parquet
    global_path = os.path.join(T_DIR, f'sat_{analysis_id}.parquet')
    r2_upload(global_path, f'data/corrientes/sat_{analysis_id}.parquet')

    # Upload dpto splits
    dpto_files = glob.glob(os.path.join(DPTO_DIR, f'sat_{analysis_id}_*.parquet'))
    uploaded = 0
    for fpath in dpto_files:
        fname = os.path.basename(fpath)
        if r2_upload(fpath, f'data/corrientes/sat_dpto/{fname}'):
            uploaded += 1
    print(f"  Uploaded {uploaded}/{len(dpto_files)} dpto parquets for {analysis_id}")
    return True


def exists(path):
    return os.path.exists(os.path.join(T_DIR, path) if not os.path.isabs(path) else path)


def main():
    ee = gee_init()

    downloaded_pm25 = set()
    pm25_processed = False
    accessibility_done = False
    soil_water_done = False
    flood_done = False
    climate_vuln_done = False

    # Track already-downloaded pm25 years
    for f in glob.glob(os.path.join(T_DIR, 'sat_pm25_*.tif')):
        year = os.path.basename(f).replace('sat_pm25_', '').replace('.tif', '')
        try:
            downloaded_pm25.add(int(year))
        except ValueError:
            pass

    print(f"Starting. pm25 already on disk: {sorted(downloaded_pm25)}")

    while True:
        running, done = get_gee_status(ee)
        print(f"\n[{time.strftime('%H:%M:%S')}] GEE running: {[d for d in running if 'corrientes' in d or 'jrc' in d or 'lv_' in d or 'flood' in d or 'soil' in d]}")

        # ── pm25: download completed years ─────────────────────────────────
        for year in range(1998, 2023):
            if year not in downloaded_pm25:
                if f'corrientes_sat_pm25_{year}' in done:
                    src = f'gs://spatia-satellite/satellite/corrientes/sat_pm25_{year}.tif'
                    if gcs_download(src, T_DIR):
                        downloaded_pm25.add(year)

        # ── pm25: process when all 25 years present ────────────────────────
        if not pm25_processed and set(range(1998, 2023)) <= downloaded_pm25:
            print("  All 25 pm25 years ready. Processing...")
            ok1 = run('process_pm25_annual_to_h3.py', '--territory', 'corrientes')
            ok2 = ok1 and run('compute_pm25_drivers.py', '--territory', 'corrientes')
            panel_done = os.path.exists(os.path.join(T_DIR, 'pm25_annual_panel.parquet'))
            if ok2 and os.path.exists(os.path.join(T_DIR, 'sat_pm25_drivers.parquet')):
                pm25_processed = True
                split_and_upload('pm25_drivers')
                print("  PM25 DONE")

        # ── Accessibility: need lv_friction + lv_cities_access ─────────────
        if not accessibility_done:
            lv_f = os.path.join(T_DIR, 'lv_friction.tif')
            lv_c = os.path.join(T_DIR, 'lv_cities_access.tif')
            if not os.path.exists(lv_f) and 'lv_friction_corrientes' in done:
                gcs_download('gs://spatia-satellite/satellite/corrientes/lv_friction.tif', T_DIR)
            if not os.path.exists(lv_c) and 'lv_cities_access_corrientes' in done:
                gcs_download('gs://spatia-satellite/satellite/corrientes/lv_cities_access.tif', T_DIR)
            if os.path.exists(lv_f) and os.path.exists(lv_c):
                ok = run('compute_accessibility_h3.py', '--territory', 'corrientes')
                if ok and os.path.exists(os.path.join(T_DIR, 'sat_accessibility.parquet')):
                    accessibility_done = True
                    split_and_upload('accessibility')
                    print("  ACCESSIBILITY DONE")

        # ── Soil water ─────────────────────────────────────────────────────
        if not soil_water_done:
            sw = os.path.join(T_DIR, 'sat_soil_water_raster.tif')
            if not os.path.exists(sw) and 'sat_soil_water_raster' in done:
                gcs_download('gs://spatia-satellite/soil_water/corrientes/sat_soil_water_raster.tif', T_DIR)
            if os.path.exists(sw):
                ok = run('process_raster_to_h3.py', '--territory', 'corrientes', '--analysis', 'soil_water')
                if ok and os.path.exists(os.path.join(T_DIR, 'sat_soil_water.parquet')):
                    soil_water_done = True
                    split_and_upload('soil_water')
                    print("  SOIL_WATER DONE")

        # ── Flood: need JRC × 3 + S1 current ──────────────────────────────
        if not flood_done:
            jrc_o = os.path.join(T_DIR, 'jrc_occurrence.tif')
            jrc_r = os.path.join(T_DIR, 'jrc_recurrence.tif')
            jrc_s = os.path.join(T_DIR, 'jrc_seasonality.tif')
            flood_cur = glob.glob(os.path.join(T_DIR, 'flood_current_*.tif'))
            if not os.path.exists(jrc_o) and 'jrc_occurrence' in done:
                gcs_download('gs://spatia-satellite/flood/corrientes/jrc_occurrence.tif', T_DIR)
            if not os.path.exists(jrc_r) and 'jrc_recurrence' in done:
                gcs_download('gs://spatia-satellite/flood/corrientes/jrc_recurrence.tif', T_DIR)
            if not os.path.exists(jrc_s) and 'jrc_seasonality' in done:
                gcs_download('gs://spatia-satellite/flood/corrientes/jrc_seasonality.tif', T_DIR)
            if not flood_cur and 'flood_current_20260507' in done:
                gcs_download('gs://spatia-satellite/flood/corrientes/flood_current_20260507.tif', T_DIR)
            flood_cur = glob.glob(os.path.join(T_DIR, 'flood_current_*.tif'))
            if os.path.exists(jrc_o) and os.path.exists(jrc_r) and os.path.exists(jrc_s) and flood_cur:
                ok = run('run_flood_update.py', '--territory', 'corrientes', '--skip-gee')
                # run_flood_update auto-uploads to R2
                if ok and os.path.exists(os.path.join(T_DIR, 'hex_flood_risk.parquet')):
                    flood_done = True
                    print("  FLOOD DONE (R2 uploaded by run_flood_update)")

        # ── Climate vulnerability (needs flood done) ───────────────────────
        if flood_done and not climate_vuln_done:
            ok = run('compute_climate_vulnerability.py', '--territory', 'corrientes')
            if ok and os.path.exists(os.path.join(T_DIR, 'sat_climate_vulnerability.parquet')):
                climate_vuln_done = True
                split_and_upload('climate_vulnerability')
                print("  CLIMATE_VULNERABILITY DONE")

        # ── Exit when all done ─────────────────────────────────────────────
        if pm25_processed and accessibility_done and soil_water_done and flood_done and climate_vuln_done:
            print("\n=== ALL ANALYSES COMPLETE ===")
            print("Remaining steps: carbon_stock split+upload, config.ts update, deploy")
            break

        # ── Show what's still pending ──────────────────────────────────────
        pending = []
        if not pm25_processed:
            pending.append(f'pm25({len(downloaded_pm25)}/25 dl)')
        if not accessibility_done:
            pending.append('accessibility')
        if not soil_water_done:
            pending.append('soil_water')
        if not flood_done:
            pending.append('flood')
        elif not climate_vuln_done:
            pending.append('climate_vuln')
        print(f"  Still pending: {pending}")

        time.sleep(60)


if __name__ == '__main__':
    main()
