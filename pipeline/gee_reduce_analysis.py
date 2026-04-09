"""
Direct GEE reduceRegions pipeline: build composite → H3 zonal stats → scoring → parquet.

Replaces the 3-step raster pipeline (gee_export_analysis → download → process_raster_to_h3)
with a single script that runs reduceRegions server-side in GEE, eliminating GeoTIFF intermediates.

Output is identical: sat_{aid}.parquet with h3index, score, and component columns.

Usage:
  python pipeline/gee_reduce_analysis.py --analysis green_capital
  python pipeline/gee_reduce_analysis.py --analysis all
  python pipeline/gee_reduce_analysis.py --analysis environmental_risk,agri_potential
"""

import argparse
import json
import os
import sys
import tempfile
import time

import ee
import numpy as np
import pandas as pd

from config import MISIONES_BBOX, OUTPUT_DIR, GCS_BUCKET
from scoring import run_full_diagnostics, geometric_mean_score
from gee_export_analysis import ANALYSIS_BUILDERS, authenticate

ASSET_ID = 'projects/amiable-reducer-398015/assets/h3_misiones_r9'
EXPORT_SCALE = 100

# ── Component definitions (from process_raster_to_h3.py) ──

ANALYSIS_COMPONENTS = {
    'environmental_risk': [
        ('c_fire', 'c_fire', 0.25, False),
        ('c_deforest', 'c_deforest', 0.25, False),
        ('c_thermal_amp', 'c_thermal_amp', 0.20, False),
        ('c_slope', 'c_slope', 0.15, False),
        ('c_hand', 'c_hand', 0.15, True),
    ],
    'climate_comfort': [
        ('c_heat_day', 'c_heat_day', 0.25, True),
        ('c_heat_night', 'c_heat_night', 0.20, True),
        ('c_precipitation', 'c_precipitation', 0.20, False),
        ('c_frost', 'c_frost', 0.15, True),
        ('c_water_stress', 'c_water_stress', 0.20, False),
    ],
    'green_capital': [
        ('c_ndvi', 'c_ndvi', 0.25, False),
        ('c_treecover', 'c_treecover', 0.20, False),
        ('c_npp', 'c_npp', 0.20, False),
        ('c_lai', 'c_lai', 0.15, False),
        ('c_vcf', 'c_vcf', 0.20, False),
    ],
    'change_pressure': [
        ('c_viirs_trend', 'c_viirs_trend', 0.25, False),
        ('c_ghsl_change', 'c_ghsl_change', 0.25, False),
        ('c_hansen_loss', 'c_hansen_loss', 0.20, False),
        ('c_ndvi_trend', 'c_ndvi_trend', 0.15, True),
        ('c_fire_count', 'c_fire_count', 0.15, False),
    ],
    'agri_potential': [
        ('c_soc', 'c_soc', 0.20, False),
        ('c_ph_optimal', 'c_ph_optimal', 0.15, False),
        ('c_clay', 'c_clay', 0.15, False),
        ('c_precipitation', 'c_precipitation', 0.20, False),
        ('c_gdd', 'c_gdd', 0.15, False),
        ('c_slope', 'c_slope', 0.15, True),
    ],
    'forest_health': [
        ('c_ndvi_trend', 'c_ndvi_trend', 0.25, False),
        ('c_loss_ratio', 'c_loss_ratio', 0.25, True),
        ('c_fire', 'c_fire', 0.20, True),
        ('c_gpp', 'c_gpp', 0.15, False),
        ('c_et', 'c_et', 0.15, False),
    ],
    'air_quality': [
        ('c_pm25', 'c_pm25', 0.40, False),
        ('c_no2', 'c_no2', 0.35, False),
        ('c_aod', 'c_aod', 0.25, False),
    ],
}

# Radio-level fallback for 100% NaN bands
RADIO_FALLBACK = {
    'c_fire': {
        'table': 'fire_annual',
        'sql': "SELECT redcode, AVG(burned_fraction) AS value FROM fire_annual WHERE year >= 2019 GROUP BY redcode",
    },
    'c_fire_count': {
        'table': 'fire_annual',
        'sql': "SELECT redcode, SUM(burn_count) AS value FROM fire_annual WHERE year >= 2019 GROUP BY redcode",
    },
}

AREAL_CROSSWALK_PATH = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk_areal.parquet")
RADIO_DATA_DIR = os.path.join(OUTPUT_DIR, "radio_data")


def percentile_rank(series):
    """Percentile rank 0-100."""
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result


def inject_radio_fallback(df, nan_cols, components):
    """Fill 100% NaN columns from radio-level data via areal crosswalk."""
    if not os.path.exists(AREAL_CROSSWALK_PATH):
        print(f"    No areal crosswalk found — skipping fallback")
        return df

    import duckdb
    xw = pd.read_parquet(AREAL_CROSSWALK_PATH)
    conn = duckdb.connect()

    for col in nan_cols:
        fb = RADIO_FALLBACK.get(col)
        if not fb:
            print(f"    No fallback defined for {col}")
            continue

        table_path = os.path.join(RADIO_DATA_DIR, f"{fb['table']}.parquet")
        if not os.path.exists(table_path):
            print(f"    Missing {table_path} — skipping {col}")
            continue

        conn.execute(f"CREATE OR REPLACE TABLE {fb['table']} AS SELECT * FROM read_parquet('{table_path}')")
        radio_df = conn.execute(fb['sql']).fetchdf()
        print(f"    Radio fallback {col}: {len(radio_df)} radios with data")

        merged = xw.merge(radio_df, on="redcode", how="inner")
        idx = merged.groupby("h3index")["weight"].idxmax()
        h3_vals = merged.loc[idx][["h3index", "value"]].set_index("h3index")

        raw = df["h3index"].map(h3_vals["value"]).astype(float)
        invert = any(c[3] for c in components if c[1] == col)
        if invert:
            raw = -raw
        df[col] = percentile_rank(raw).round(1)
        injected = df[col].notna().sum()
        print(f"    Injected {col}: {injected:,} hexagons with data")

    conn.close()
    return df


def get_gcs_client():
    """Build GCS client from service account or default credentials."""
    from google.cloud import storage
    key_env = os.environ.get('GEE_SERVICE_ACCOUNT_KEY', '')
    if key_env:
        from google.oauth2 import service_account as sa
        if os.path.isfile(key_env):
            with open(key_env) as f:
                key_data = json.load(f)
        else:
            key_data = json.loads(key_env)
        creds = sa.Credentials.from_service_account_info(key_data)
        return storage.Client(credentials=creds, project=key_data.get('project_id'))
    else:
        creds = ee.data.get_persistent_credentials()
        return storage.Client(credentials=creds, project='amiable-reducer-398015')


def reduce_to_h3(composite, analysis_id, scale=100):
    """Run reduceRegions on H3 asset, export CSV to GCS, download, return DataFrame."""
    h3_fc = ee.FeatureCollection(ASSET_ID)
    reducer = ee.Reducer.mean()

    print(f"    Running reduceRegions (scale={scale}m)...")
    result = composite.reduceRegions(
        collection=h3_fc,
        reducer=reducer,
        scale=scale,
        crs='EPSG:4326',
    )

    # Export to GCS as CSV
    gcs_prefix = f'pipeline/reduce/{analysis_id}'
    print(f"    Exporting to gs://{GCS_BUCKET}/{gcs_prefix}...")

    task = ee.batch.Export.table.toCloudStorage(
        collection=result,
        description=f'reduce-{analysis_id}'[:60],
        bucket=GCS_BUCKET,
        fileNamePrefix=gcs_prefix,
        fileFormat='CSV',
    )
    task.start()

    # Poll for completion
    while True:
        status = task.status()
        state = status['state']
        if state in ('COMPLETED', 'SUCCEEDED'):
            print(f"    GEE export complete")
            break
        elif state in ('FAILED', 'CANCEL_REQUESTED', 'CANCELLED'):
            error_msg = status.get('error_message', 'Unknown error')
            print(f"    GEE task failed: {error_msg}")
            return None
        time.sleep(15)

    # Download CSV from GCS
    print(f"    Downloading from GCS...")
    client = get_gcs_client()
    bucket = client.bucket(GCS_BUCKET)

    blobs = list(bucket.list_blobs(prefix=gcs_prefix))
    csv_blobs = [b for b in blobs if b.name.endswith('.csv')]
    if not csv_blobs:
        print(f"    ERROR: No CSV found at gs://{GCS_BUCKET}/{gcs_prefix}*")
        return None

    tmp_dir = tempfile.mkdtemp()
    all_dfs = []
    for blob in csv_blobs:
        local_path = os.path.join(tmp_dir, os.path.basename(blob.name))
        blob.download_to_filename(local_path)
        df = pd.read_csv(local_path)
        all_dfs.append(df)
        os.remove(local_path)

    result_df = pd.concat(all_dfs, ignore_index=True) if len(all_dfs) > 1 else all_dfs[0]

    # Cleanup GCS
    for blob in blobs:
        blob.delete()

    # Drop GEE system columns
    drop_cols = [c for c in result_df.columns if c.startswith('.') or c in ('system:index', 'geo')]
    result_df = result_df.drop(columns=drop_cols, errors='ignore')

    print(f"    Downloaded {len(result_df):,} rows, {len(result_df.columns)} columns")
    return result_df


def process_analysis(analysis_id, df):
    """Percentile rank normalization + PCA diagnostics + geometric mean scoring."""
    components = ANALYSIS_COMPONENTS[analysis_id]
    band_names = [c[0] for c in components]

    print(f"\n  Scoring {analysis_id}: {len(band_names)} components")

    # Rename 'mean' suffix columns if present (from reduceRegions)
    for col in list(df.columns):
        for bn in band_names:
            if col == f'{bn}_mean' and bn not in df.columns:
                df = df.rename(columns={col: bn})

    # Percentile rank per component
    for band_name, out_col, weight, invert in components:
        if band_name not in df.columns:
            df[out_col] = np.nan
            continue
        raw = df[band_name].astype(float)
        if invert:
            raw = -raw
        df[out_col] = percentile_rank(raw).round(1)

    # Radio fallback for 100% NaN columns
    comp_cols = [c[1] for c in components]
    nan_cols = [c for c in comp_cols if df[c].isna().all()]
    if nan_cols:
        print(f"    100% NaN columns: {nan_cols} — attempting radio fallback")
        df = inject_radio_fallback(df, nan_cols, components)

    # Exclude remaining 100% NaN columns
    valid_cols = [c for c in comp_cols if not df[c].isna().all()]
    dropped_nan = set(comp_cols) - set(valid_cols)
    if dropped_nan:
        print(f"    Excluded (no data): {dropped_nan}")

    # PCA diagnostics
    valid_mask = df[valid_cols].notna().all(axis=1)
    df_valid = df.loc[valid_mask]
    print(f"    Valid hexagons for PCA: {len(df_valid):,} / {len(df):,}")

    diagnostics = run_full_diagnostics(df_valid, valid_cols, corr_threshold=0.70)
    retained = diagnostics["variable_selection"]["retained"]
    dropped = diagnostics["variable_selection"]["dropped"]

    kmo = diagnostics["kmo_bartlett"].get("kmo_overall")
    if kmo is not None:
        print(f"    KMO: {kmo:.3f} {'OK' if kmo >= 0.60 else 'WARNING < 0.60'}")
    if dropped:
        print(f"    Dropped (|r|>0.70): {dropped}")
    print(f"    Retained ({len(retained)}): {retained}")

    # Geometric mean score
    df['score'] = geometric_mean_score(df, retained, floor=1.0).round(1)

    # Output columns
    out_cols = ['h3index', 'score'] + [c[1] for c in components]
    existing = [c for c in out_cols if c in df.columns]
    result = df[existing].dropna(subset=['score'])

    return result


def main():
    parser = argparse.ArgumentParser(description="Direct GEE reduceRegions → H3 parquet pipeline")
    parser.add_argument("--analysis", required=True, help="Analysis ID or 'all'")
    parser.add_argument("--scale", type=int, default=EXPORT_SCALE,
                        help=f"reduceRegions scale in metres (default: {EXPORT_SCALE})")
    args = parser.parse_args()

    is_ci = authenticate()
    bbox = ee.Geometry.Rectangle(MISIONES_BBOX)

    if args.analysis == 'all':
        analyses = list(ANALYSIS_COMPONENTS.keys())
    else:
        analyses = [a.strip() for a in args.analysis.split(',')]

    # Verify H3 asset exists
    try:
        size = ee.FeatureCollection(ASSET_ID).size().getInfo()
        print(f"  H3 asset ready ({size:,} features)")
    except Exception as e:
        print(f"  ERROR: H3 asset not found: {e}")
        return 1

    t0 = time.time()
    print(f"{'=' * 60}")
    print(f"  Direct reduceRegions Pipeline")
    print(f"  Analyses: {', '.join(analyses)}")
    print(f"  Scale: {args.scale}m")
    print(f"{'=' * 60}")

    results = {}
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for aid in analyses:
        if aid not in ANALYSIS_BUILDERS:
            print(f"\n  SKIP {aid}: no builder defined")
            continue
        if aid not in ANALYSIS_COMPONENTS:
            print(f"\n  SKIP {aid}: no component definition")
            continue

        print(f"\n{'─' * 50}")
        print(f"  {aid}")
        print(f"{'─' * 50}")

        # Step 1: Build composite in GEE
        print(f"    Building composite...")
        composite = ANALYSIS_BUILDERS[aid](bbox)

        # Step 2: reduceRegions → CSV → DataFrame
        df = reduce_to_h3(composite, aid, scale=args.scale)
        if df is None:
            print(f"    FAILED: {aid}")
            continue

        # Step 3: Score and save
        result = process_analysis(aid, df)
        output_path = os.path.join(OUTPUT_DIR, f"sat_{aid}.parquet")
        result.to_parquet(output_path, index=False)

        size_kb = os.path.getsize(output_path) / 1024
        print(f"    Output: {output_path}")
        print(f"    Rows: {len(result):,}, Size: {size_kb:.0f} KB")
        print(f"    Score: mean={result['score'].mean():.1f}, median={result['score'].median():.1f}")
        results[aid] = len(result)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Pipeline complete in {elapsed:.0f}s")
    for aid, n in results.items():
        print(f"    {aid}: {n:,} hexagons")
    print(f"{'=' * 60}")

    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
