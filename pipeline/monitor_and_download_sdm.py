"""
Monitor GEE tasks and download completed composites from GCS.

Usage:
  python pipeline/monitor_and_download_sdm.py --territory itapua_py
"""
import os, sys, time, subprocess, platform

_GCLOUD = 'gcloud.cmd' if platform.system() == 'Windows' else 'gcloud'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import ee
from config import GCS_BUCKET, OUTPUT_DIR, get_territory

TASK_IDS = {
    'era5':        'RITMPFIMR7KBRDP5JP3ASMBB',
    'chirps':      '3ZWP5G2RG3ZWBT53DDONL76R',
    'terraclimate':'23JYWPUQD5VZRL7BAJLZPCWY',
    'soilgrids':   'TIB52S26TESHNWMVCCUHU6LH',
    'terrain_v1':  'WAWPUQMCXHLHBGWP3MQ2KOIN',
    'ndvi':        'VZK5BT33LUQ6WAEWQVWB5KHY',
    'jrc':         '5EL32OX5SBY2NULX3GT4NOHP',
    'mapbiomas':   'E223GKLYAN3JLUQZGJB3NJZL',
    'ghsl':        'N6IY5DV6GN6OAYFN26VS3R66',
    'terrain_v2':  'XMWH7IFRPXD4PGEPMJUCL3N4',
}

# Map task name → GCS filename
GCS_FILES = {
    'era5':         'sdm_era5_composite.tif',
    'chirps':       'sdm_chirps_composite.tif',
    'terraclimate': 'sdm_terraclimate_composite.tif',
    'soilgrids':    'sdm_soilgrids_composite.tif',
    'terrain_v1':   'sdm_terrain_composite.tif',
    'ndvi':         'sdm_ndvi_composite.tif',
    'jrc':          'sdm_jrc_water.tif',
    'mapbiomas':    'sdm_mapbiomas_py.tif',
    'ghsl':         'sdm_ghsl_smod.tif',
    'terrain_v2':   'sdm_terrain_v2.tif',
}


def download(t_id, name, gcs_file, t_dir):
    local = os.path.join(t_dir, gcs_file)
    if os.path.exists(local) and os.path.getsize(local) > 100_000:
        print(f'  {name}: already downloaded')
        return True
    gcs = f'gs://{GCS_BUCKET}/satellite/{t_id}/{gcs_file}'
    print(f'  Downloading {name} from {gcs} ...')
    ret = subprocess.run([_GCLOUD, 'storage', 'cp', gcs, local],
                         capture_output=True, text=True)
    if ret.returncode == 0 and os.path.exists(local):
        sz = os.path.getsize(local) // 1024
        print(f'  {name}: OK ({sz}KB)')
        return True
    print(f'  {name}: FAILED\n  {ret.stderr[:200]}')
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--territory', default='itapua_py')
    args = parser.parse_args()

    territory = get_territory(args.territory)
    t_id = territory['id']
    t_dir = os.path.join(OUTPUT_DIR, territory['output_prefix'].rstrip('/'))

    ee.Initialize()
    downloaded = set()

    # Attempt immediate download for already-completed tasks
    for name, tid in TASK_IDS.items():
        state = ee.data.getTaskStatus(tid)[0]['state']
        if state == 'COMPLETED':
            if download(t_id, name, GCS_FILES[name], t_dir):
                downloaded.add(name)

    pending = {k: v for k, v in TASK_IDS.items() if k not in downloaded}
    if not pending:
        print('All tasks already downloaded.')
        return

    print(f'\nWaiting for {len(pending)} tasks...')
    while pending:
        time.sleep(60)
        still_pending = {}
        for name, tid in list(pending.items()):
            state = ee.data.getTaskStatus(tid)[0]['state']
            if state == 'COMPLETED':
                if download(t_id, name, GCS_FILES[name], t_dir):
                    downloaded.add(name)
                else:
                    still_pending[name] = tid  # retry next round
            elif state in ('FAILED', 'CANCELLED'):
                print(f'  {name}: {state} — skipping')
            else:
                still_pending[name] = tid
                print(f'  {name}: {state}')
        pending = still_pending

    print(f'\nDone. Downloaded: {sorted(downloaded)}')


if __name__ == '__main__':
    main()
