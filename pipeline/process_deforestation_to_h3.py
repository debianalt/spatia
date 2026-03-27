"""
Process EUDR deforestation rasters to H3 res-7 parquets.

Unlike the Misiones pipeline, this does NOT use percentile rank normalisation.
Values are absolute (forest cover %, loss %, fire frequency) because EUDR
compliance requires physical-unit evidence, not relative rankings.

Risk score formula:
  70% * loss_post_2020_pct + 20% * fire_post_2020_pct + 10% * (1 - forest_cover_2020/100)

Usage:
  python pipeline/process_deforestation_to_h3.py
  python pipeline/process_deforestation_to_h3.py --raster path/to/eudr_deforestation_combined.tif
  python pipeline/process_deforestation_to_h3.py --province chaco
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_eudr import (
    OUTPUT_DIR,
    GRID_PATH,
    PARQUET_PATH,
    MIN_EUDR_HEXAGONS,
    MAX_NULL_FRACTION,
    SCORE_RANGE,
    WEIGHT_LOSS_POST_2020,
    WEIGHT_FIRE_POST_2020,
    WEIGHT_NO_FOREST_2020,
    EUDR_PROVINCES,
)

# Band mapping (must match gee_deforestation_eudr.py export order)
BANDS = {
    "treecover_2000": 1,
    "loss_year": 2,
    "loss_post_2020": 3,
    "treecover_current": 4,
    "fire_post_2020": 5,
}


def zonal_stats_band(src, band_idx, geom, nodata=None):
    """Compute mean of a raster band within a polygon (polygon masking)."""
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


def compute_risk_score(row):
    """
    EUDR risk score 0-100.

    High score = high risk of non-compliance.
    """
    import math
    loss = row.get("loss_post_2020_pct", 0)
    loss = 0 if (loss is None or (isinstance(loss, float) and math.isnan(loss))) else loss
    fire = row.get("fire_post_2020_pct", 0)
    fire = 0 if (fire is None or (isinstance(fire, float) and math.isnan(fire))) else fire
    fc2020 = row.get("forest_cover_2020", 0)
    fc2020 = 0 if (fc2020 is None or (isinstance(fc2020, float) and math.isnan(fc2020))) else fc2020

    # Normalise loss_post_2020 to 0-100 scale
    # loss_post_2020 from GEE is 0 or 1 (binary), averaged over pixels → 0-1 fraction
    loss_norm = min(loss * 100, 100)

    # fire_post_2020 is 0-1 mean frequency → scale to 0-100
    fire_norm = min(fire * 100, 100)

    # No-forest component: areas with no forest in 2020 have lower EUDR relevance
    # but if there WAS forest and it was lost, that's the concern
    no_forest = max(0, 100 - fc2020)  # fc2020 is 0-100%

    score = (
        WEIGHT_LOSS_POST_2020 * loss_norm
        + WEIGHT_FIRE_POST_2020 * fire_norm
        + WEIGHT_NO_FOREST_2020 * no_forest
    )

    return round(min(max(score, 0), 100), 1)


def process_raster(raster_path, hex_features, province_map=None):
    """Process a deforestation raster to H3 dataframe."""
    print(f"  Processing: {raster_path}")

    t0 = time.time()
    results = []
    n_features = len(hex_features)

    with rasterio.open(raster_path) as src:
        print(f"  Size: {src.width}x{src.height}, {src.count} bands, CRS={src.crs}")
        nodata = src.nodata

        for fi, feat in enumerate(hex_features):
            if fi % 20000 == 0 and fi > 0:
                elapsed = time.time() - t0
                rate = fi / elapsed
                eta = (n_features - fi) / rate / 60
                print(f"    {fi:,}/{n_features:,} ({rate:.0f} hex/s, ETA {eta:.1f} min)")

            h3index = (feat.get("properties", {}).get("h3index")
                       or feat.get("properties", {}).get("h3_index")
                       or feat.get("id"))
            geom = shape(feat["geometry"])

            row = {"h3index": h3index}

            # Extract each band
            for band_name, band_idx in BANDS.items():
                if band_idx <= src.count:
                    row[band_name] = zonal_stats_band(src, band_idx, geom, nodata)
                else:
                    row[band_name] = np.nan

            # Province assignment from hex grid
            props = feat.get("properties", {})
            row["province"] = props.get("province_id", props.get("province_name", ""))

            results.append(row)

    df = pd.DataFrame(results)
    elapsed = time.time() - t0
    print(f"  Raw hexagons: {len(df):,} in {elapsed:.0f}s")

    return df


def post_process(df):
    """Compute derived columns and risk score."""
    # Rename raw bands to output columns
    df["forest_cover_2020"] = df["treecover_2000"].round(1)
    df["forest_cover_current"] = df["treecover_current"].round(1)

    # Loss percentages (loss_post_2020 is 0-1 mean of binary pixels)
    df["loss_post_2020_pct"] = (df["loss_post_2020"] * 100).round(2)

    # Total loss: fraction of pixels with any loss year > 0
    # We use treecover_2000 - treecover_current as proxy
    df["loss_total_pct"] = (df["treecover_2000"] - df["treecover_current"]).clip(lower=0).round(2)

    # Pre-2020 loss = total loss - post-2020 loss
    df["loss_pre_2020_pct"] = (df["loss_total_pct"] - df["loss_post_2020_pct"]).clip(lower=0).round(2)

    # Fire (MODIS MCD64A1 may be all-NaN for areas with no burns — fill with 0)
    df["fire_post_2020_pct"] = (df["fire_post_2020"].fillna(0) * 100).round(2)

    # Risk score
    df["risk_score"] = df.apply(compute_risk_score, axis=1)

    # Boolean: any deforestation detected post-2020
    df["deforestation_post_2020"] = (df["loss_post_2020_pct"] > 0).astype(int)

    # Output columns
    out_cols = [
        "h3index", "province",
        "forest_cover_2020", "forest_cover_current",
        "loss_total_pct", "loss_post_2020_pct", "loss_pre_2020_pct",
        "fire_post_2020_pct", "risk_score", "deforestation_post_2020",
    ]

    result = df[out_cols].dropna(subset=["forest_cover_2020"])
    return result


def validate(df):
    """Validate the output dataframe."""
    n = len(df)
    print(f"\n  Validation:")
    print(f"    Rows: {n:,}")

    if n < MIN_EUDR_HEXAGONS:
        print(f"    WARNING: only {n:,} rows, expected >= {MIN_EUDR_HEXAGONS:,}")

    null_frac = df.isnull().any(axis=1).mean()
    print(f"    Null fraction: {null_frac:.1%}")
    if null_frac > MAX_NULL_FRACTION:
        print(f"    WARNING: null fraction {null_frac:.1%} > {MAX_NULL_FRACTION:.0%}")

    score = df["risk_score"]
    print(f"    Risk score: mean={score.mean():.1f}, median={score.median():.1f}, "
          f"min={score.min():.1f}, max={score.max():.1f}")

    n_deforested = df["deforestation_post_2020"].sum()
    print(f"    Hexagons with post-2020 deforestation: {n_deforested:,} ({n_deforested/n:.1%})")

    by_province = df.groupby("province").size()
    print(f"    By province:")
    for prov, count in by_province.items():
        print(f"      {prov}: {count:,}")


def main():
    parser = argparse.ArgumentParser(description="Process EUDR deforestation rasters to H3")
    parser.add_argument("--raster", help="Path to GeoTIFF (default: auto-detect in output/eudr/)")
    parser.add_argument("--province", help="Process single province raster")
    parser.add_argument("--output", default=PARQUET_PATH, help="Output parquet path")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Find raster
    if args.raster:
        raster_path = args.raster
    elif args.province:
        raster_path = os.path.join(OUTPUT_DIR, f"eudr_deforestation_{args.province}.tif")
    else:
        raster_path = os.path.join(OUTPUT_DIR, "eudr_deforestation_combined.tif")

    if not os.path.exists(raster_path):
        print(f"Raster not found: {raster_path}")
        print(f"Run gee_deforestation_eudr.py first, then download from Drive.")
        return 1

    # Load hex grid
    print("Loading EUDR hexagon grid...")
    if not os.path.exists(GRID_PATH):
        print(f"Grid not found: {GRID_PATH}")
        print(f"Run generate_eudr_h3_grid.py first.")
        return 1

    with open(GRID_PATH, "r") as f:
        hexgrid = json.load(f)
    features = hexgrid["features"]
    print(f"  {len(features):,} hexagons")

    # Process
    df = process_raster(raster_path, features)
    result = post_process(df)
    validate(result)

    # Save
    result.to_parquet(args.output, index=False)
    size_kb = os.path.getsize(args.output) / 1024
    print(f"\n  Saved: {args.output} ({size_kb:.0f} KB, {len(result):,} rows)")

    # Also split by province
    province_dir = os.path.join(OUTPUT_DIR, "by_province")
    os.makedirs(province_dir, exist_ok=True)
    for prov, prov_df in result.groupby("province"):
        prov_path = os.path.join(province_dir, f"eudr_{prov}.parquet")
        prov_df.to_parquet(prov_path, index=False)
        print(f"    {prov}: {len(prov_df):,} rows -> {prov_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
