"""
Download satellite rasters from Google Drive (spatia-satellite folder).

Uses Earth Engine OAuth credentials for Drive API access.
Skips files that already exist locally with the same size.

Usage:
  python pipeline/download_from_drive.py                          # all sat_pm25_*.tif
  python pipeline/download_from_drive.py --pattern "sat_pm25_*.tif"
  python pipeline/download_from_drive.py --pattern "mapbiomas_*.tif"
  python pipeline/download_from_drive.py --list                   # list files without downloading
"""

import argparse
import fnmatch
import json
import os
import sys

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

try:
    from ee.oauth import CLIENT_ID as EE_CLIENT_ID, CLIENT_SECRET as EE_CLIENT_SECRET
except ImportError:
    EE_CLIENT_ID = '517222506229-vsmmajv00ul0bs7p89v5m89qs8eb9359.apps.googleusercontent.com'
    EE_CLIENT_SECRET = 'RUP0RZ6e0pPhDzsqIJ7KlNd1'
DRIVE_FOLDER = 'spatia-satellite'
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')


def get_drive_service():
    creds_path = os.path.expanduser('~/.config/earthengine/credentials')
    with open(creds_path) as f:
        cred_data = json.load(f)

    creds = Credentials(
        token=None,
        refresh_token=cred_data['refresh_token'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=EE_CLIENT_ID,
        client_secret=EE_CLIENT_SECRET or None,
        scopes=cred_data.get('scopes', []),
    )
    return build('drive', 'v3', credentials=creds)


def find_folder_id(service, folder_name):
    """Find the Drive folder ID by name."""
    resp = service.files().list(
        q=f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        spaces='drive',
        fields='files(id, name)',
    ).execute()
    files = resp.get('files', [])
    if not files:
        return None
    return files[0]['id']


def list_files_in_folder(service, folder_id, pattern):
    """List files matching glob pattern inside a Drive folder."""
    matched = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            spaces='drive',
            fields='nextPageToken, files(id, name, size)',
            pageToken=page_token,
            pageSize=100,
        ).execute()
        for f in resp.get('files', []):
            if fnmatch.fnmatch(f['name'], pattern):
                matched.append(f)
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return sorted(matched, key=lambda f: f['name'])


def download_file(service, file_info, dest_path):
    """Download a single file from Drive with progress."""
    request = service.files().get_media(fileId=file_info['id'])
    with open(dest_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"    {status.progress() * 100:.0f}%", end='\r')
    print()


def main():
    parser = argparse.ArgumentParser(description="Download rasters from Google Drive")
    parser.add_argument("--pattern", default="sat_pm25_*.tif",
                        help="Glob pattern to match files (default: sat_pm25_*.tif)")
    parser.add_argument("--list", action="store_true",
                        help="List matching files without downloading")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if local file exists with same size")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Authenticating with Google Drive...")
    service = get_drive_service()

    print(f"Looking for folder '{DRIVE_FOLDER}'...")
    folder_id = find_folder_id(service, DRIVE_FOLDER)
    if not folder_id:
        print(f"ERROR: Folder '{DRIVE_FOLDER}' not found in Drive.")
        return 1

    print(f"Searching for '{args.pattern}'...")
    files = list_files_in_folder(service, folder_id, args.pattern)

    if not files:
        print(f"No files matching '{args.pattern}' in '{DRIVE_FOLDER}'.")
        return 1

    total_mb = sum(int(f.get('size', 0)) for f in files) / (1024 * 1024)
    print(f"Found {len(files)} files ({total_mb:.1f} MB total):\n")

    for f in files:
        size_mb = int(f.get('size', 0)) / (1024 * 1024)
        print(f"  {f['name']:40s} {size_mb:6.1f} MB")

    if args.list:
        return 0

    print()
    downloaded = 0
    skipped = 0

    for f in files:
        dest = os.path.join(OUTPUT_DIR, f['name'])
        remote_size = int(f.get('size', 0))

        if not args.force and os.path.exists(dest):
            local_size = os.path.getsize(dest)
            if local_size == remote_size:
                print(f"  SKIP {f['name']} (already exists, {remote_size / 1024 / 1024:.1f} MB)")
                skipped += 1
                continue

        size_mb = remote_size / (1024 * 1024)
        print(f"  Downloading {f['name']} ({size_mb:.1f} MB)...")
        download_file(service, f, dest)
        downloaded += 1

    print(f"\nDone: {downloaded} downloaded, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
