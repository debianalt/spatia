"""
Targeted Phase 2 finisher for Alto Paraná: ONLY accessibility +
productive_activity (the 2 that didn't complete in run_phase2_pipeline.py).
Does NOT touch the 9 already on R2. Same --mode comparable + data/ R2 path.
"""
import glob, os, subprocess, sys, time
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR, GCS_BUCKET, R2_BUCKET, get_territory

TID = 'alto_parana_py'
T = get_territory(TID)
TDIR = os.path.join(OUTPUT_DIR, T['output_prefix'].rstrip('/'))
PREFIX = f"data/{T['output_prefix']}"          # data/alto_parana_py/
GCLOUD = r'C:\Users\ant\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' if sys.platform=='win32' else 'gcloud'
NPX = r'C:\Program Files\nodejs\npx.cmd' if sys.platform=='win32' else 'npx'
SH = sys.platform == 'win32'


def py(script, *a):
    print(f"  $ {script} {' '.join(a)}", flush=True)
    return subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, script), *a], cwd=ROOT).returncode == 0


def r2(local, key):
    assert key.startswith('data/'), key
    return subprocess.run([NPX,'wrangler','r2','object','put',f'{R2_BUCKET}/{key}',
        '--file',local,'--remote'], cwd=ROOT, capture_output=True, text=True, shell=SH).returncode == 0


def split_upload(aid):
    if not py('split_by_admin.py','--territory',TID,'--only',aid):
        print(f"  split FAIL {aid}"); return False
    g=os.path.join(TDIR,f'sat_{aid}.parquet')
    if os.path.exists(g): print('  global', r2(g,f'{PREFIX}sat_{aid}.parquet'))
    files=glob.glob(os.path.join(TDIR,'sat_dpto',f'sat_{aid}_*.parquet'))
    n=sum(r2(fp,f'{PREFIX}sat_dpto/{os.path.basename(fp)}') for fp in files)
    print(f"  {aid}: {n}/{len(files)} dpto uploaded"); return True


def gcs_dl(name):
    return subprocess.run([GCLOUD,'storage','cp',f'gs://{GCS_BUCKET}/satellite/{TID}/{name}',TDIR],
        cwd=ROOT, capture_output=True, text=True, shell=SH).returncode == 0


# ── accessibility (rasters lv_*.tif already local; fix for all-NaN OSM in place) ──
print("=== accessibility ===", flush=True)
if py('compute_accessibility_h3.py','--territory',TID,'--mode','comparable') \
   and os.path.exists(os.path.join(TDIR,'sat_accessibility.parquet')):
    split_upload('accessibility'); print("ACCESSIBILITY DONE", flush=True)
else:
    print("ACCESSIBILITY FAILED", flush=True)

# ── productive_activity: submit GEE export (async), poll, process ──
print("=== productive_activity ===", flush=True)
ar = os.path.join(TDIR,'sat_activity_raster.tif')
if not os.path.exists(ar):
    py('gee_export_activity_rasters.py','--territory',TID,'--gcs','--no-wait')
    import ee
    ee.Initialize()
    for _ in range(120):                       # up to ~2h
        st={t['description']:t['state'] for t in ee.data.getTaskList()}
        if any('activity' in d and s=='COMPLETED' for d,s in st.items()):
            if gcs_dl('sat_activity_raster.tif') and os.path.exists(ar): break
        time.sleep(60)
if os.path.exists(ar):
    if py('process_activity_to_h3.py','--territory',TID,'--mode','comparable') \
       and os.path.exists(os.path.join(TDIR,'sat_productive_activity.parquet')):
        split_upload('productive_activity'); print("PRODUCTIVE_ACTIVITY DONE", flush=True)
    else:
        print("PRODUCTIVE_ACTIVITY process FAILED", flush=True)
else:
    print("PRODUCTIVE_ACTIVITY raster never landed", flush=True)
print("=== finisher done ===", flush=True)
