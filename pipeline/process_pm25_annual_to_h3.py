"""
Process annual PM2.5 GeoTIFFs to H3 res-9 panel via centroid sampling.

Reads one GeoTIFF per year (sat_pm25_{year}.tif) and produces a single
long-format parquet with columns: h3index, year, pm25.

The PM2.5 rasters are ~1 km resolution while H3 res-9 hexagons are ~174 m,
so centroid sampling is used (same approach as process_air_quality_to_h3.py).

Input:
  pipeline/output/sat_pm25_{year}.tif  (one per year)

Output:
  pipeline/output/pm25_annual_panel.parquet  (h3index, year, pm25)

Usage:
  python pipeline/process_pm25_annual_to_h3.py
  python pipeline/process_pm25_annual_to_h3.py --years 2019 2020 2021
"""

import argparse
import glob
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import shape

from config import OUTPUT_DIR, get_territory

HEXAGONS_PATH = os.path.join(OUTPUT_DIR, "hexagons-lite.geojson")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "pm25_annual_panel.parquet")

_tif_dir = OUTPUT_DIR  # overridden in main() for non-misiones territories


def discover_years():
    """Find available sat_pm25_{year}.tif files in output directory."""
    pattern = os.path.join(_tif_dir, "sat_pm25_*.tif")
    files = sorted(glob.glob(pattern))
    years = []
    for f in files:
        basename = os.path.basename(f)
        # sat_pm25_2019.tif -> 2019
        try:
            year = int(basename.replace("sat_pm25_", "").replace(".tif", ""))
            years.append(year)
        except ValueError:
            continue
    return years


def sample_raster_centroids(raster_path, features):
    """Sample single-band raster at hexagon centroids. Returns list of values."""
    values = []
    with rasterio.open(raster_path) as src:
        for feat in features:
            geom = shape(feat["geometry"])
            cx, cy = geom.centroid.x, geom.centroid.y
            try:
                r, c = src.index(cx, cy)
                if 0 <= r < src.height and 0 <= c < src.width:
                    val = float(src.read(1, window=((r, r + 1), (c, c + 1)))[0, 0])
                    values.append(val if not np.isnan(val) else np.nan)
                else:
                    values.append(np.nan)
            except Exception:
                values.append(np.nan)
    return values


def main():
    global _tif_dir
    parser = argparse.ArgumentParser(description="Annual PM2.5 rasters to H3 panel")
    parser.add_argument("--territory", default="misiones", help="Territory ID (default: misiones)")
    parser.add_argument("--years", type=int, nargs="+", default=None,
                        help="Specific years to process (default: all found TIFFs)")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    t_prefix = territory['output_prefix']
    if t_prefix:
        t_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/'))
        hexagons_path = os.path.join(t_dir, 'hexagons.geojson')
        output_path = os.path.join(t_dir, 'pm25_annual_panel.parquet')
        _tif_dir = t_dir
    else:
        t_dir = OUTPUT_DIR
        hexagons_path = HEXAGONS_PATH
        output_path = OUTPUT_PATH

    # Load hexagon grid
    print("Loading hexagon grid...")
    with open(hexagons_path) as f:
        gj = json.load(f)
    features = gj["features"]
    h3_ids = [feat["properties"]["h3index"] for feat in features]
    n_hex = len(features)
    print(f"  {n_hex:,} hexagons")

    # Discover or filter years
    available = discover_years()
    if not available:
        print(f"ERROR: No sat_pm25_*.tif files in {OUTPUT_DIR}")
        return 1
    print(f"  Available TIFFs: {available[0]}–{available[-1]} ({len(available)} years)")

    years = args.years if args.years else available
    missing = [y for y in years if y not in available]
    if missing:
        print(f"  WARNING: TIFFs not found for years: {missing}")
        years = [y for y in years if y in available]

    if not years:
        print("No valid years to process.")
        return 1

    # Process each year
    all_rows = []
    t0 = time.time()

    for year in sorted(years):
        raster_path = os.path.join(t_dir, f"sat_pm25_{year}.tif")
        print(f"\n  Processing {year}...")
        ty = time.time()

        values = sample_raster_centroids(raster_path, features)
        valid = sum(1 for v in values if not np.isnan(v))
        coverage = valid / n_hex * 100

        print(f"    Coverage: {valid:,}/{n_hex:,} ({coverage:.1f}%)")

        for h3, val in zip(h3_ids, values):
            all_rows.append({"h3index": h3, "year": year, "pm25": val})

        vals = [v for v in values if not np.isnan(v)]
        if vals:
            print(f"    PM2.5 range: {min(vals):.2f}–{max(vals):.2f} µg/m³, "
                  f"mean: {np.mean(vals):.2f}, median: {np.median(vals):.2f}")
        print(f"    Done in {time.time() - ty:.1f}s")

    df = pd.DataFrame(all_rows)
    elapsed = time.time() - t0

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  Total rows: {len(df):,} ({n_hex:,} hex × {len(years)} years)")
    print(f"  Elapsed: {elapsed:.0f}s")

    # Drop rows where pm25 is NaN across all years for a hex
    valid_per_hex = df.groupby('h3index')['pm25'].apply(lambda x: x.notna().sum())
    full_coverage = (valid_per_hex == len(years)).sum()
    partial = ((valid_per_hex > 0) & (valid_per_hex < len(years))).sum()
    no_data = (valid_per_hex == 0).sum()
    print(f"  Hexagons: {full_coverage:,} full, {partial:,} partial, {no_data:,} no data")

    # Year-level stats
    print(f"\n  Year-level statistics:")
    for year in sorted(years):
        subset = df[df.year == year]['pm25']
        v = subset.notna().sum()
        print(f"    {year}: n={v:,}, mean={subset.mean():.2f}, "
              f"std={subset.std():.2f}, min={subset.min():.2f}, max={subset.max():.2f}")

    # Save
    os.makedirs(t_dir, exist_ok=True)
    df.to_parquet(output_path, index=False)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n  Output: {output_path}")
    print(f"  Size: {size_mb:.1f} MB")
    print(f"\nNext step: python pipeline/compute_pm25_trends.py")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
