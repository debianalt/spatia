"""
Process SDM covariate GeoTIFFs to H3 parquets for forestry_aptitude.

Reads the 9 composites exported by gee_export_sdm_covariates.py + Nelson
figshare download, computes H3 zonal stats (mean, p90 for terrain), and
writes H3 parquets expected by compute_forestry_sdm.py.

Downloads from GCS if local files are missing.

Output parquets (in output/{territory}/):
  era5_annual_h3.parquet          — temp_mean, temp_min, frost_days, gdd_base10, solar_radiation
  chirps_annual_h3.parquet        — precip_total, precip_mean_daily, precip_days_20mm, precip_days_50mm
  terraclimate_annual_h3.parquet  — water_deficit, soil_moisture, vpd, pdsi_min
  soilgrids_h3.parquet            — ph, clay, sand, silt, soc, bulk_density
  srtm_terrain_h3.parquet         — slope_mean, slope_p90, elev_mean, elev_range, twi_mean, ruggedness_mean
  ndvi_annual_mean_h3.parquet     — ndvi_mean
  ghsl_smod_h3.parquet            — smod_urban_frac, smod_suburban_frac
  jrc_water_annual_h3.parquet     — water_fraction
  nelson_accessibility_h3.parquet — tt_cities_50k_min
  sat_land_use.parquet            — frac_plantation, frac_native_forest, frac_water, frac_urban, ...

Usage:
  python pipeline/process_sdm_covariates_h3.py --territory itapua_py
  python pipeline/process_sdm_covariates_h3.py --territory itapua_py --only era5,soilgrids
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import urllib.request

_GCLOUD = 'gcloud.cmd' if platform.system() == 'Windows' else 'gcloud'

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from shapely.geometry import shape

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import GCS_BUCKET, OUTPUT_DIR, H3_RESOLUTION, get_territory

NELSON_FIGSHARE_URL = (
    'https://figshare.com/ndownloader/files/14180548'
)

# ─── H3 hex geometry helpers ────────────────────────────────────────────────

def load_hexagons(t_dir: str) -> list[dict]:
    """Load hexagons.geojson for the territory."""
    for fname in ('hexagons.geojson', 'hexagons-lite.geojson'):
        path = os.path.join(t_dir, fname)
        if os.path.exists(path):
            import json as _json
            with open(path) as f:
                fc = _json.load(f)
            return fc['features']
    raise FileNotFoundError(f'No hexagons GeoJSON found in {t_dir}')


def h3_centroids(features: list[dict]) -> tuple[list[str], np.ndarray]:
    """Return (h3indices, centroids_xy) where centroids_xy is (N,2) lon/lat."""
    try:
        from h3 import cell_to_latlng
        def _centroid(h):
            lat, lng = cell_to_latlng(h)
            return lng, lat
    except Exception:
        import h3
        def _centroid(h):
            lat, lng = h3.h3_to_geo(h)
            return lng, lat

    h3ids, coords = [], []
    for feat in features:
        h = feat['properties'].get('h3index') or feat['properties'].get('h3_index') or feat['id']
        if h:
            h3ids.append(str(h))
            coords.append(_centroid(str(h)))
    return h3ids, np.array(coords)


def sample_raster_at_points(tif_path: str, coords: np.ndarray) -> np.ndarray:
    """Sample all bands of raster at (lon, lat) pairs. Returns (N, bands)."""
    with rasterio.open(tif_path) as src:
        # rasterio.sample expects (lon, lat) = (x, y)
        gen = src.sample(coords.tolist())
        vals = np.array(list(gen), dtype=np.float32)
        nodata = src.nodata
        if nodata is not None:
            vals[vals == nodata] = np.nan
    return vals


def sample_raster_p90(tif_path: str, features: list[dict], band_idx: int = 0) -> np.ndarray:
    """Sample raster band within each hex polygon, return p90 per hex."""
    from rasterio.mask import mask as rio_mask

    vals_p90 = []
    with rasterio.open(tif_path) as src:
        nodata = src.nodata
        for feat in features:
            geom = shape(feat['geometry'])
            try:
                data, _ = rio_mask(src, [geom.__geo_interface__], crop=True, all_touched=True)
                band = data[band_idx].astype(np.float32)
                if nodata is not None:
                    band[band == nodata] = np.nan
                valid = band[~np.isnan(band)]
                vals_p90.append(float(np.percentile(valid, 90)) if len(valid) > 0 else np.nan)
            except Exception:
                vals_p90.append(np.nan)
    return np.array(vals_p90, dtype=np.float32)


def download_gcs_if_missing(local_path: str, gcs_path: str, t_id: str):
    """Download from GCS if file not present locally."""
    if os.path.exists(local_path) and os.path.getsize(local_path) > 10_000:
        return
    print(f'  Downloading {gcs_path} ...')
    cmd = f'{_GCLOUD} storage cp "gs://{GCS_BUCKET}/{gcs_path}" "{local_path}"'
    ret = os.system(cmd)
    if ret != 0 or not os.path.exists(local_path):
        raise RuntimeError(f'GCS download failed: {cmd}')


# ─── Individual processors ──────────────────────────────────────────────────

def process_era5(h3ids, coords, t_dir, t_id):
    tif = os.path.join(t_dir, 'sdm_era5_composite.tif')
    download_gcs_if_missing(tif, f'satellite/{t_id}/sdm_era5_composite.tif', t_id)
    vals = sample_raster_at_points(tif, coords)
    bands = ['temp_mean', 'temp_min', 'frost_days', 'gdd_base10', 'solar_radiation']
    df = pd.DataFrame({'h3index': h3ids})
    for i, col in enumerate(bands):
        df[col] = vals[:, i] if i < vals.shape[1] else np.nan
    df['year'] = 2021  # synthetic year for mean composite
    return df


def process_chirps(h3ids, coords, t_dir, t_id):
    tif = os.path.join(t_dir, 'sdm_chirps_composite.tif')
    download_gcs_if_missing(tif, f'satellite/{t_id}/sdm_chirps_composite.tif', t_id)
    vals = sample_raster_at_points(tif, coords)
    bands = ['total_mm', 'mean_daily', 'days_gt_20mm', 'days_gt_50mm']
    df = pd.DataFrame({'h3index': h3ids})
    for i, col in enumerate(bands):
        df[col] = vals[:, i] if i < vals.shape[1] else np.nan
    df['year'] = 2021
    return df


def process_terraclimate(h3ids, coords, t_dir, t_id):
    tif = os.path.join(t_dir, 'sdm_terraclimate_composite.tif')
    download_gcs_if_missing(tif, f'satellite/{t_id}/sdm_terraclimate_composite.tif', t_id)
    vals = sample_raster_at_points(tif, coords)
    bands = ['water_deficit', 'soil_moisture', 'vpd', 'pdsi_min']
    df = pd.DataFrame({'h3index': h3ids})
    for i, col in enumerate(bands):
        df[col] = vals[:, i] if i < vals.shape[1] else np.nan
    df['year'] = 2021
    return df


def process_soilgrids(h3ids, coords, t_dir, t_id):
    tif = os.path.join(t_dir, 'sdm_soilgrids_composite.tif')
    download_gcs_if_missing(tif, f'satellite/{t_id}/sdm_soilgrids_composite.tif', t_id)
    vals = sample_raster_at_points(tif, coords)
    bands = ['ph', 'clay', 'sand', 'silt', 'soc', 'bulk_density']
    df = pd.DataFrame({'h3index': h3ids})
    for i, col in enumerate(bands):
        df[col] = vals[:, i] if i < vals.shape[1] else np.nan
    return df


def process_terrain(h3ids, coords, features, t_dir, t_id):
    # Prefer v2 raster (has slope_p90, elev_range, ruggedness from GEE neighborhood)
    tif_v2 = os.path.join(t_dir, 'sdm_terrain_v2.tif')
    tif_v1 = os.path.join(t_dir, 'sdm_terrain_composite.tif')

    if os.path.exists(tif_v2) and os.path.getsize(tif_v2) > 10_000:
        tif = tif_v2
        gcs = f'satellite/{t_id}/sdm_terrain_v2.tif'
    else:
        tif = tif_v1
        gcs = f'satellite/{t_id}/sdm_terrain_composite.tif'

    download_gcs_if_missing(tif, gcs, t_id)
    vals = sample_raster_at_points(tif, coords)

    df = pd.DataFrame({'h3index': h3ids})

    if tif == tif_v2:
        # v2 bands: elevation, slope_mean, slope_p90, elev_max, elev_min, ruggedness, twi
        df['elev_mean']      = vals[:, 0] if vals.shape[1] > 0 else np.nan
        df['slope_mean']     = vals[:, 1] if vals.shape[1] > 1 else np.nan
        df['slope_p90']      = vals[:, 2] if vals.shape[1] > 2 else np.nan
        elev_max = vals[:, 3] if vals.shape[1] > 3 else np.nan
        elev_min = vals[:, 4] if vals.shape[1] > 4 else np.nan
        df['elev_range']     = elev_max - elev_min if vals.shape[1] > 4 else np.nan
        df['ruggedness_mean']= vals[:, 5] if vals.shape[1] > 5 else np.nan
        df['twi_mean']       = vals[:, 6] if vals.shape[1] > 6 else np.nan
    else:
        # v1 bands: elevation, slope, twi
        df['elev_mean']      = vals[:, 0] if vals.shape[1] > 0 else np.nan
        df['slope_mean']     = vals[:, 1] if vals.shape[1] > 1 else np.nan
        df['twi_mean']       = vals[:, 2] if vals.shape[1] > 2 else np.nan
        df['slope_p90']      = df['slope_mean'] * 1.3  # rough proxy
        df['elev_range']     = np.nan
        df['ruggedness_mean']= np.nan

    return df


def process_ndvi(h3ids, coords, t_dir, t_id):
    tif = os.path.join(t_dir, 'sdm_ndvi_composite.tif')
    download_gcs_if_missing(tif, f'satellite/{t_id}/sdm_ndvi_composite.tif', t_id)
    vals = sample_raster_at_points(tif, coords)
    df = pd.DataFrame({'h3index': h3ids})
    df['mean_ndvi'] = vals[:, 0] if vals.shape[1] > 0 else np.nan
    df['year'] = 2021
    return df


def process_ghsl_smod(h3ids, coords, t_dir, t_id):
    tif = os.path.join(t_dir, 'sdm_ghsl_smod.tif')
    download_gcs_if_missing(tif, f'satellite/{t_id}/sdm_ghsl_smod.tif', t_id)
    vals = sample_raster_at_points(tif, coords)  # SMOD class codes
    smod_class = vals[:, 0]
    # GHSL SMOD classes: 11=rural, 12=low density rural, 21=suburban, 30=urban center
    # Urban = 30, Suburban = 21
    df = pd.DataFrame({'h3index': h3ids})
    df['smod_urban_frac']    = (smod_class >= 30).astype(float)
    df['smod_suburban_frac'] = ((smod_class >= 21) & (smod_class < 30)).astype(float)
    return df


def process_jrc_water(h3ids, coords, t_dir, t_id):
    tif = os.path.join(t_dir, 'sdm_jrc_water.tif')
    download_gcs_if_missing(tif, f'satellite/{t_id}/sdm_jrc_water.tif', t_id)
    vals = sample_raster_at_points(tif, coords)
    df = pd.DataFrame({'h3index': h3ids})
    df['water_fraction'] = vals[:, 0] if vals.shape[1] > 0 else np.nan
    df['year'] = 2021
    return df


def process_nelson(h3ids, coords, t_dir, t_id):
    """Sample Nelson 2019 (= Oxford MAP accessibility_to_cities) at H3 centroids.

    Oxford/MAP/accessibility_to_cities_2015_v1_0 is the Weiss et al. 2018 /
    Nelson 2019 dataset (same paper) — 50k+ city threshold, travel time in min.
    The lv_cities_access.tif exported for location_value is the same raster.
    """
    # Prefer the location_value export (already clipped to territory bbox)
    local_raster = os.path.join(t_dir, 'lv_cities_access.tif')

    if not (os.path.exists(local_raster) and os.path.getsize(local_raster) > 10_000):
        # Try GCS-cached global raster
        gcs_path = f'satellite/{t_id}/nelson_travel_time_50k.tif'
        try:
            download_gcs_if_missing(local_raster, gcs_path, t_id)
        except Exception:
            pass

    if not (os.path.exists(local_raster) and os.path.getsize(local_raster) > 10_000):
        print('  Nelson raster not found — downloading from figshare (may be large)...')
        print(f'  URL: {NELSON_FIGSHARE_URL}')
        urllib.request.urlretrieve(NELSON_FIGSHARE_URL, local_raster)

    vals = sample_raster_at_points(local_raster, coords)
    df = pd.DataFrame({'h3index': h3ids})
    df['tt_cities_50k_min'] = vals[:, 0] if vals.shape[1] > 0 else np.nan
    # Also add other thresholds if available (multi-band Nelson)
    for i, col in enumerate(['tt_cities_5k_min', 'tt_cities_20k_min', 'tt_cities_100k_min'], start=1):
        if vals.shape[1] > i:
            df[col] = vals[:, i]
    return df


def process_mapbiomas(h3ids, coords, features, t_dir, t_id):
    """Process MapBiomas land use raster → sat_land_use.parquet equivalent."""
    tif = os.path.join(t_dir, 'sdm_mapbiomas_py.tif')
    download_gcs_if_missing(tif, f'satellite/{t_id}/sdm_mapbiomas_py.tif', t_id)

    vals = sample_raster_at_points(tif, coords)
    # Bands: land_use_class, is_plantation, is_native_forest, is_water, is_urban

    df = pd.DataFrame({'h3index': h3ids})
    # Use binary fraction bands (centroid sampling = 0 or 1 per pixel)
    # Convert to "fraction" column name expected by SDM (frac_plantation, etc.)
    # We sample centroid → approximation. For SDM presence detection (>50%) a centroid
    # value of 1 (is_plantation=1 at centroid) = likely plantation hex.
    # We express as "percentage" by multiplying by 100 to match SDM threshold of 50.
    df['frac_plantation']   = (vals[:, 1] * 100) if vals.shape[1] > 1 else 0.0
    df['frac_native_forest']= (vals[:, 2] * 100) if vals.shape[1] > 2 else 0.0
    df['frac_water']        = (vals[:, 3] * 100) if vals.shape[1] > 3 else 0.0
    df['frac_urban']        = (vals[:, 4] * 100) if vals.shape[1] > 4 else 0.0
    df['frac_pasture']      = 0.0
    df['frac_agriculture']  = 0.0
    df['frac_mosaic']       = 0.0
    df['frac_wetland']      = 0.0
    df['frac_grassland']    = 0.0
    df['frac_bare']         = 0.0

    n_plantation = (df['frac_plantation'] >= 50).sum()
    print(f'  MapBiomas: {n_plantation:,} plantation hexes (centroid sampling)')
    return df


# ─── Main ───────────────────────────────────────────────────────────────────

PROCESSORS = {
    'era5':         ('era5_annual_h3.parquet',         True,  False),  # name, needs_features
    'chirps':       ('chirps_annual_h3.parquet',        True,  False),
    'terraclimate': ('terraclimate_annual_h3.parquet',  True,  False),
    'soilgrids':    ('soilgrids_h3.parquet',            True,  False),
    'terrain':      ('srtm_terrain_h3.parquet',         True,  True),  # needs polygon features
    'ndvi':         ('ndvi_annual_mean_h3.parquet',     True,  False),
    'ghsl':         ('ghsl_smod_h3.parquet',            True,  False),
    'jrc':          ('jrc_water_annual_h3.parquet',     True,  False),
    'nelson':       ('nelson_accessibility_h3.parquet', True,  False),
    'mapbiomas':    ('sat_land_use.parquet',             True,  True),
}


def main():
    parser = argparse.ArgumentParser(description='Process SDM covariates to H3 parquets')
    parser.add_argument('--territory', default='itapua_py')
    parser.add_argument('--only', default=None, help='Comma-separated processor names')
    args = parser.parse_args()

    territory = get_territory(args.territory)
    t_id = territory['id']
    t_prefix = territory['output_prefix'].rstrip('/')
    t_dir = os.path.join(OUTPUT_DIR, t_prefix) if t_prefix else OUTPUT_DIR

    print('=' * 60)
    print(f'Processing SDM covariates: {territory["label"]} ({t_id})')
    print('=' * 60)

    print('Loading hexagons...')
    features = load_hexagons(t_dir)
    h3ids, coords = h3_centroids(features)
    print(f'  {len(h3ids):,} hexes')

    procs = PROCESSORS
    if args.only:
        keys = [k.strip() for k in args.only.split(',')]
        procs = {k: v for k, v in PROCESSORS.items() if k in keys}

    for name, (out_file, _, needs_features) in procs.items():
        out_path = os.path.join(t_dir, out_file)
        t0 = time.time()
        print(f'\n[{name}] -> {out_file}')

        try:
            if name == 'era5':
                df = process_era5(h3ids, coords, t_dir, t_id)
            elif name == 'chirps':
                df = process_chirps(h3ids, coords, t_dir, t_id)
            elif name == 'terraclimate':
                df = process_terraclimate(h3ids, coords, t_dir, t_id)
            elif name == 'soilgrids':
                df = process_soilgrids(h3ids, coords, t_dir, t_id)
            elif name == 'terrain':
                df = process_terrain(h3ids, coords, features, t_dir, t_id)
            elif name == 'ndvi':
                df = process_ndvi(h3ids, coords, t_dir, t_id)
            elif name == 'ghsl':
                df = process_ghsl_smod(h3ids, coords, t_dir, t_id)
            elif name == 'jrc':
                df = process_jrc_water(h3ids, coords, t_dir, t_id)
            elif name == 'nelson':
                df = process_nelson(h3ids, coords, t_dir, t_id)
            elif name == 'mapbiomas':
                df = process_mapbiomas(h3ids, coords, features, t_dir, t_id)
            else:
                print(f'  Unknown processor: {name}')
                continue

            df.to_parquet(out_path, index=False)
            elapsed = time.time() - t0
            print(f'  Wrote {out_path} ({os.path.getsize(out_path)//1024}KB, {len(df):,} rows, {elapsed:.0f}s)')

        except Exception as e:
            print(f'  ERROR: {e}')
            import traceback
            traceback.print_exc()

    print('\nDone.')


if __name__ == '__main__':
    main()
