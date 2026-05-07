"""
Export MapBiomas Argentina land cover for a territory via GEE.

Uses MapBiomas Argentina Collection 1 (30m, annual).
Exports per-pixel class as GeoTIFF, then processes to H3 fractions.

Classes of interest:
  3  = Bosque nativo (Forest Formation)
  9  = Silvicultura (Forest Plantation)
  15 = Pastizal (Grassland)
  18 = Agricultura (Agriculture)
  21 = Mosaico agro-pastizal
  24 = Area urbana (Urban)
  25 = Otra area no vegetada
  26 = Cuerpo de agua (Water)
  33 = Rio, lago, oceano

Usage:
  python pipeline/gee_export_mapbiomas.py
  python pipeline/gee_export_mapbiomas.py --year 2023 --drive
  python pipeline/gee_export_mapbiomas.py --territory corrientes --gcs --no-wait
"""

import argparse
import json
import os
import sys
import time

import ee

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR, get_territory

ASSET = 'projects/mapbiomas-public/assets/argentina/collection1/mapbiomas_argentina_collection1_integration_v1'

# Remap to simplified classes
CLASS_MAP = {
    3: 'native_forest',
    4: 'native_forest',   # Savanna Formation → group with native
    5: 'native_forest',   # Mangrove → group with native
    9: 'plantation',      # Silvicultura
    11: 'wetland',        # Wetland
    12: 'grassland',      # Grassland Formation
    13: 'grassland',      # Other non-forest formation
    15: 'pasture',        # Pasture
    18: 'agriculture',    # Agriculture
    19: 'agriculture',    # Annual crop
    20: 'agriculture',    # Semi-perennial
    21: 'mosaic',         # Agro-pastoral mosaic
    24: 'urban',          # Urban
    25: 'bare',           # Other non-vegetated
    26: 'water',          # Water
    29: 'rocky',          # Rocky outcrop
    30: 'mining',         # Mining
    33: 'water',          # River, lake, ocean
}

SIMPLIFIED_CLASSES = ['native_forest', 'plantation', 'pasture', 'agriculture',
                      'mosaic', 'wetland', 'grassland', 'urban', 'water', 'bare']


def authenticate():
    key_env = os.environ.get('GEE_SERVICE_ACCOUNT_KEY', '')
    if key_env and not os.path.isfile(key_env):
        key_data = json.loads(key_env)
        credentials = ee.ServiceAccountCredentials(key_data['client_email'], key_data=key_data)
        ee.Initialize(credentials)
    else:
        ee.Initialize()


def export_mapbiomas(territory_id='misiones', year=2023, to_drive=False, no_wait=False):
    authenticate()

    territory = get_territory(territory_id)
    bbox = ee.Geometry.Rectangle(territory['bbox'])

    # Load MapBiomas
    mb = ee.Image(ASSET)

    # Select band for the year
    band_name = f'classification_{year}'
    available = mb.bandNames().getInfo()

    if band_name not in available:
        print(f"Band {band_name} not found. Available: {available[-5:]}")
        band_name = sorted([b for b in available if b.startswith('classification_')])[-1]
        print(f"Using: {band_name}")

    classification = mb.select(band_name).clip(bbox)

    # GCS path: misiones uses legacy flat path, others use territory subdir
    if territory_id == 'misiones':
        desc = f'mapbiomas_misiones_{year}'
        gcs_prefix = f'satellite/{desc}'
    else:
        desc = f'mapbiomas_{territory_id}_{year}'
        gcs_prefix = f'satellite/{territory_id}/{desc}'

    export_params = {
        'image': classification,
        'description': desc,
        'scale': 30,
        'region': bbox,
        'maxPixels': 1e10,
        'fileFormat': 'GeoTIFF',
    }

    if to_drive:
        task = ee.batch.Export.image.toDrive(
            folder='spatia-satellite',
            fileNamePrefix=desc,
            **export_params
        )
    else:
        task = ee.batch.Export.image.toCloudStorage(
            bucket='spatia-satellite',
            fileNamePrefix=gcs_prefix,
            **export_params
        )

    task.start()
    print(f"Export started: {desc}")
    print(f"Task ID: {task.id}")
    if not to_drive:
        print(f"GCS destination: gs://spatia-satellite/{gcs_prefix}.tif")

    if no_wait:
        print("--no-wait: exiting. Monitor at https://code.earthengine.google.com/tasks")
        return True

    # Poll
    while True:
        status = task.status()
        state = status['state']
        print(f"  {state}")
        if state in ('COMPLETED', 'FAILED', 'CANCELLED'):
            break
        time.sleep(30)

    if state == 'COMPLETED':
        print(f"Export completed: {desc}")
    else:
        print(f"Export {state}: {status.get('error_message', '')}")

    return state == 'COMPLETED'


def main():
    parser = argparse.ArgumentParser(description='Export MapBiomas Argentina for a territory')
    parser.add_argument('--territory', default='misiones', help='Territory ID (default: misiones)')
    parser.add_argument('--year', type=int, default=2023, help='Classification year')
    parser.add_argument('--drive', action='store_true', help='Export to Google Drive')
    parser.add_argument('--gcs', action='store_true', help='Export to GCS (required for non-misiones CI)')
    parser.add_argument('--no-wait', action='store_true', help='Submit task and exit without polling')
    args = parser.parse_args()

    to_drive = args.drive and not args.gcs
    export_mapbiomas(
        territory_id=args.territory,
        year=args.year,
        to_drive=to_drive,
        no_wait=args.no_wait,
    )


if __name__ == '__main__':
    main()
