"""Download temporal GeoTIFFs from Google Drive (spatia-satellite folder).

After gee_export_analysis_temporal.py finishes exporting, this script
downloads all sat_*_baseline.tif and sat_*_current.tif files from the
Drive folder to pipeline/output/.

Usage:
  python pipeline/download_temporal_from_drive.py
  python pipeline/download_temporal_from_drive.py --only green_capital,forest_health
"""
import argparse
import json
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')
DRIVE_FOLDER = 'spatia-satellite'

EE_CLIENT_ID = '517222506229-vsmmajv00ul0bs7p89v5m89ber09rb7r.apps.googleusercontent.com'
EE_CLIENT_SECRET = ''

TEMPORAL_ANALYSES = [
    'environmental_risk', 'climate_comfort', 'green_capital',
    'change_pressure', 'agri_potential', 'forest_health',
]


def get_drive_service():
    creds_path = os.path.expanduser('~/.config/earthengine/credentials')
    with open(creds_path) as f:
        cred_data = json.load(f)

    creds = Credentials(
        token=None,
        refresh_token=cred_data['refresh_token'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=EE_CLIENT_ID,
        client_secret=EE_CLIENT_SECRET,
        scopes=cred_data.get('scopes', [])
    )
    return build('drive', 'v3', credentials=creds)


def find_folder_id(service, folder_name):
    results = service.files().list(
        q=f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'",
        spaces='drive', fields='files(id, name)'
    ).execute()
    files = results.get('files', [])
    return files[0]['id'] if files else None


def download_file(service, file_info, out_path):
    request = service.files().get_media(fileId=file_info['id'])
    with open(out_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                pct = status.progress() * 100
                print(f'    {pct:.0f}%', end='\r')
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f'    OK: {size_mb:.1f} MB')


def main():
    parser = argparse.ArgumentParser(description='Download temporal TIFs from Drive')
    parser.add_argument('--only', default=None, help='Comma-separated analysis IDs')
    args = parser.parse_args()

    analyses = TEMPORAL_ANALYSES
    if args.only:
        analyses = [a.strip() for a in args.only.split(',')]

    service = get_drive_service()

    folder_id = find_folder_id(service, DRIVE_FOLDER)
    if not folder_id:
        print(f'ERROR: Drive folder "{DRIVE_FOLDER}" not found')
        return 1

    target_files = []
    for aid in analyses:
        for suffix in ['baseline', 'current']:
            target_files.append(f'sat_{aid}_{suffix}.tif')

    print(f'Looking for {len(target_files)} files in Drive/{DRIVE_FOLDER}...')

    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        spaces='drive', fields='files(id, name, size)',
        pageSize=100
    ).execute()
    drive_files = {f['name']: f for f in results.get('files', [])}

    downloaded = 0
    skipped = 0
    missing = 0

    for fname in target_files:
        out_path = os.path.join(OUTPUT_DIR, fname)

        if os.path.exists(out_path):
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            print(f'  CACHED: {fname} ({size_mb:.1f} MB)')
            skipped += 1
            continue

        if fname not in drive_files:
            print(f'  MISSING: {fname}')
            missing += 1
            continue

        finfo = drive_files[fname]
        size_mb = int(finfo.get('size', 0)) / (1024 * 1024)
        print(f'  Downloading {fname} ({size_mb:.1f} MB)...')
        download_file(service, finfo, out_path)
        downloaded += 1

    print(f'\nDone: {downloaded} downloaded, {skipped} cached, {missing} missing')
    return 0


if __name__ == '__main__':
    exit(main())
