"""
Process multi-band GeoTIFF rasters to H3 res-9 parquets with pixel-level zonal stats.

Each band becomes a component column. Percentile rank normalisation (0-100)
is applied per band, then a PCA-validated geometric mean score is computed
(OECD Handbook / UNDP HDI methodology, consistent with compute_satellite_scores.py).

This REPLACES the radio-level crosswalk approach for analyses where
GEE rasters are available — each hexagon gets its own pixel-averaged value.

Usage:
  python pipeline/process_raster_to_h3.py --analysis green_capital
  python pipeline/process_raster_to_h3.py --analysis all
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import shape

from config import OUTPUT_DIR, H3_RESOLUTION
from scoring import run_full_diagnostics, geometric_mean_score

HEXAGONS_PATH = os.path.join(OUTPUT_DIR, "hexagons-lite.geojson")

# Component definitions per analysis: (band_name, output_col, weight, invert)
ANALYSIS_COMPONENTS = {
    'environmental_risk': [
        ('c_fire', 'c_fire', 0.25, False),
        ('c_deforest', 'c_deforest', 0.25, False),
        ('c_thermal_amp', 'c_thermal_amp', 0.20, False),
        ('c_slope', 'c_slope', 0.15, False),
        ('c_hand', 'c_hand', 0.15, True),       # low HAND = more risk
    ],
    'climate_comfort': [
        ('c_heat_day', 'c_heat_day', 0.25, True),       # less heat = more comfort
        ('c_heat_night', 'c_heat_night', 0.20, True),
        ('c_precipitation', 'c_precipitation', 0.20, False),
        ('c_frost', 'c_frost', 0.15, True),              # less frost = more comfort
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
        ('c_ndvi_trend', 'c_ndvi_trend', 0.15, True),   # declining = more change
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
}

PIXEL_ANALYSES = list(ANALYSIS_COMPONENTS.keys())


def zonal_stats_band(src, band_idx, geom, nodata=None):
    """Compute mean of a raster band within a polygon."""
    bounds = geom.bounds
    try:
        window = from_bounds(*bounds, transform=src.transform)
        data = src.read(band_idx, window=window).astype(float)
        if data.size == 0:
            return np.nan

        transform = rasterio.windows.transform(window, src.transform)
        mask = geometry_mask([geom], out_shape=data.shape, transform=transform, invert=True)

        data[~mask] = np.nan
        if nodata is not None:
            data[data == nodata] = np.nan

        valid = data[~np.isnan(data)]
        return float(np.mean(valid)) if len(valid) > 0 else np.nan
    except Exception:
        return np.nan


def percentile_rank(series):
    """Percentile rank 0-100."""
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result


def process_analysis(analysis_id, raster_path, hexgrid_features, output_path):
    """Process a single analysis raster to H3 parquet."""
    components = ANALYSIS_COMPONENTS[analysis_id]
    band_names = [c[0] for c in components]

    print(f"\n  Processing {analysis_id}: {len(band_names)} bands")
    print(f"  Raster: {raster_path}")

    t0 = time.time()
    results = []

    with rasterio.open(raster_path) as src:
        print(f"  Size: {src.width}x{src.height}, {src.count} bands, CRS={src.crs}")
        nodata = src.nodata

        # Build band index mapping
        # GEE exports band names as descriptions; fall back to ordinal
        band_map = {}
        for i, bname in enumerate(band_names):
            band_map[bname] = i + 1  # rasterio is 1-indexed

        n_features = len(hexgrid_features)
        for fi, feat in enumerate(hexgrid_features):
            if fi % 50000 == 0 and fi > 0:
                elapsed = time.time() - t0
                rate = fi / elapsed
                eta = (n_features - fi) / rate / 60
                print(f"    {fi:,}/{n_features:,} ({rate:.0f} hex/s, ETA {eta:.1f} min)")

            h3index = (feat.get("properties", {}).get("h3index")
                       or feat.get("properties", {}).get("h3_index")
                       or feat.get("id"))
            geom = shape(feat["geometry"])

            row = {"h3index": h3index}
            for bname, band_idx in band_map.items():
                if band_idx <= src.count:
                    row[bname] = zonal_stats_band(src, band_idx, geom, nodata)
                else:
                    row[bname] = np.nan
            results.append(row)

    df = pd.DataFrame(results)
    print(f"  Raw hexagons: {len(df):,}")

    # Normalise via percentile rank
    for band_name, out_col, weight, invert in components:
        raw = df[band_name].astype(float)
        if invert:
            raw = -raw
        df[out_col] = percentile_rank(raw).round(1)

    # PCA-validated geometric mean score (OECD/HDI methodology)
    comp_cols = [c[1] for c in components]

    # Exclude 100% NaN columns (e.g. fire bands with no data)
    valid_cols = [c for c in comp_cols if not df[c].isna().all()]
    dropped_nan = set(comp_cols) - set(valid_cols)
    if dropped_nan:
        print(f"  Excluded (100% NaN): {dropped_nan}")

    # Run diagnostics on non-NaN subset
    valid_mask = df[valid_cols].notna().all(axis=1)
    df_valid = df.loc[valid_mask]
    print(f"  Valid hexagons for PCA: {len(df_valid):,} / {len(df):,}")

    diagnostics = run_full_diagnostics(df_valid, valid_cols, corr_threshold=0.70)
    retained = diagnostics["variable_selection"]["retained"]
    dropped = diagnostics["variable_selection"]["dropped"]

    kmo = diagnostics["kmo_bartlett"].get("kmo_overall")
    if kmo is not None:
        print(f"    KMO: {kmo:.3f} {'OK' if kmo >= 0.60 else 'WARNING < 0.60'}")
    if dropped:
        print(f"    Dropped (|r|>0.70): {dropped}")
    print(f"    Retained ({len(retained)}): {retained}")

    df['score'] = geometric_mean_score(df, retained, floor=1.0).round(1)

    # Output columns
    out_cols = ['h3index', 'score'] + [c[1] for c in components]
    result = df[out_cols].dropna(subset=['score'])

    result.to_parquet(output_path, index=False)
    elapsed = time.time() - t0
    size_kb = os.path.getsize(output_path) / 1024

    print(f"  Output: {output_path}")
    print(f"  Rows: {len(result):,}, Size: {size_kb:.0f} KB")
    print(f"  Score: mean={result['score'].mean():.1f}, median={result['score'].median():.1f}")
    print(f"  Time: {elapsed:.0f}s")

    return len(result)


def main():
    parser = argparse.ArgumentParser(description="Process GEE rasters to H3 parquets")
    parser.add_argument("--analysis", required=True, help="Analysis ID or 'all'")
    parser.add_argument("--input-dir", default=OUTPUT_DIR, help="Directory with GeoTIFFs")
    args = parser.parse_args()

    if args.analysis == 'all':
        analyses = PIXEL_ANALYSES
    else:
        analyses = [a.strip() for a in args.analysis.split(',')]

    # Load hex grid once
    print("Loading hexagon grid...")
    with open(HEXAGONS_PATH, 'r') as f:
        hexgrid = json.load(f)
    features = hexgrid['features']
    print(f"  {len(features):,} hexagons")

    t0 = time.time()
    results = {}

    for aid in analyses:
        if aid not in ANALYSIS_COMPONENTS:
            print(f"  SKIP {aid}: no component definition")
            continue

        raster_path = os.path.join(args.input_dir, f"sat_{aid}_raster.tif")
        if not os.path.exists(raster_path):
            print(f"  SKIP {aid}: raster not found at {raster_path}")
            continue

        output_path = os.path.join(OUTPUT_DIR, f"sat_{aid}.parquet")
        n = process_analysis(aid, raster_path, features, output_path)
        results[aid] = n

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Processed {len(results)} analyses in {elapsed:.0f}s")
    for aid, n in results.items():
        print(f"    {aid}: {n:,} hexagons")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
