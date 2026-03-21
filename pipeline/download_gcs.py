"""
Download flood GeoTIFFs from Google Cloud Storage.

Uses the same service account credentials as GEE (GEE_SERVICE_ACCOUNT_KEY).
Includes retry with exponential backoff and raster validation.

Usage:
  python pipeline/download_gcs.py
  python pipeline/download_gcs.py --prefix flood/flood_current_20260301
"""

import argparse
import json
import os

from google.cloud import storage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import GCS_BUCKET, FLOOD_GCS_PREFIX, OUTPUT_DIR
from validate import validate_raster


def get_gcs_client():
    """Create GCS client using GEE_SERVICE_ACCOUNT_KEY."""
    key_env = os.environ.get("GEE_SERVICE_ACCOUNT_KEY", "")

    if not key_env:
        # Default credentials (local dev with gcloud auth)
        return storage.Client()

    if os.path.isfile(key_env):
        return storage.Client.from_service_account_json(key_env)

    # JSON string in env var
    key_data = json.loads(key_env)
    from google.oauth2 import service_account
    credentials = service_account.Credentials.from_service_account_info(key_data)
    return storage.Client(credentials=credentials, project=key_data.get("project_id"))


def list_flood_files(client, prefix=FLOOD_GCS_PREFIX):
    """List GeoTIFF files in the flood prefix."""
    bucket = client.bucket(GCS_BUCKET)
    blobs = list(bucket.list_blobs(prefix=prefix))
    tifs = [b for b in blobs if b.name.endswith(".tif")]
    return sorted(tifs, key=lambda b: b.updated, reverse=True)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=45),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
    reraise=True,
)
def _download_with_retry(blob, local_path):
    """Download a blob with retry and size verification."""
    blob.download_to_filename(local_path)

    # Verify downloaded size matches remote
    if blob.size is not None:
        local_size = os.path.getsize(local_path)
        if local_size != blob.size:
            os.remove(local_path)
            raise IOError(
                f"Size mismatch: expected {blob.size} bytes, got {local_size} bytes"
            )


def download_blob(client, blob_name, output_dir=OUTPUT_DIR):
    """Download a single blob to output directory with retry and validation."""
    os.makedirs(output_dir, exist_ok=True)
    local_name = os.path.basename(blob_name)
    local_path = os.path.join(output_dir, local_name)

    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(blob_name)
    blob.reload()  # ensure metadata (size) is loaded

    size_mb = blob.size / (1024 * 1024) if blob.size else 0
    print(f"  Downloading {blob_name} ({size_mb:.1f} MB)...")

    _download_with_retry(blob, local_path)
    print(f"  -> {local_path}")

    # Validate the downloaded raster
    if not validate_raster(local_path):
        raise ValueError(f"Downloaded raster failed validation: {local_path}")

    return local_path


def download_latest_flood(output_dir=OUTPUT_DIR, prefix=FLOOD_GCS_PREFIX):
    """
    Download the most recent flood GeoTIFFs from GCS.

    Returns dict mapping description type to local path:
      {"recurrence": "/path/to/recurrence.tif", "current": "/path/to/current.tif"}
    """
    client = get_gcs_client()
    blobs = list_flood_files(client, prefix)

    if not blobs:
        print(f"  No GeoTIFF files found in gs://{GCS_BUCKET}/{prefix}")
        return {}

    print(f"  Found {len(blobs)} GeoTIFF(s) in gs://{GCS_BUCKET}/{prefix}")

    downloaded = {}
    for blob in blobs:
        name = blob.name.lower()
        if "recurrence" in name and "recurrence" not in downloaded:
            local = download_blob(client, blob.name, output_dir)
            downloaded["recurrence"] = local
        elif "current" in name and "current" not in downloaded:
            local = download_blob(client, blob.name, output_dir)
            downloaded["current"] = local

        if len(downloaded) == 2:
            break

    return downloaded


def download_by_prefix(prefix, output_dir=OUTPUT_DIR):
    """Download all GeoTIFFs matching a specific prefix."""
    client = get_gcs_client()
    blobs = list_flood_files(client, prefix)
    paths = []
    for blob in blobs:
        local = download_blob(client, blob.name, output_dir)
        paths.append(local)
    return paths


def main():
    parser = argparse.ArgumentParser(description="Download flood GeoTIFFs from GCS")
    parser.add_argument("--prefix", default=FLOOD_GCS_PREFIX,
                        help="GCS prefix to search (default: flood/)")
    parser.add_argument("--output", default=OUTPUT_DIR,
                        help="Local output directory")
    args = parser.parse_args()

    downloaded = download_latest_flood(args.output, args.prefix)

    if downloaded:
        print(f"\nDownloaded {len(downloaded)} file(s):")
        for kind, path in downloaded.items():
            print(f"  {kind}: {path}")
    else:
        print("No files downloaded.")


if __name__ == "__main__":
    main()
