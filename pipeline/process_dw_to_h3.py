"""
Process Dynamic World GeoTIFF to H3 res-9 parquet.

Reads the class probability raster (9 bands) and computes per-hexagon:
  - Mean fraction for each of the 9 DW classes
  - Shannon diversity index as composite score (0-100)

Usage:
  python pipeline/process_dw_to_h3.py
  python pipeline/process_dw_to_h3.py --input path/to/dw_probs_2024.tif
"""

import argparse
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HEXAGONS_PATH = os.path.join(OUTPUT_DIR, "hexagons-lite.geojson")
DEFAULT_INPUT = os.path.join(OUTPUT_DIR, "dw_probs_2024.tif")

CLASSES = ['water', 'trees', 'grass', 'flooded_vegetation', 'crops',
           'shrub_and_scrub', 'built', 'bare', 'snow_and_ice']

# Short names for parquet columns
COL_NAMES = ['frac_water', 'frac_trees', 'frac_grass', 'frac_flooded',
             'frac_crops', 'frac_shrub', 'frac_built', 'frac_bare', 'frac_snow']


def compute_shannon(fractions: np.ndarray) -> float:
    """Shannon diversity index normalized to 0-100."""
    fracs = fractions[fractions > 0.01]  # ignore negligible classes
    if len(fracs) < 2:
        return 0.0
    total = fracs.sum()
    if total <= 0:
        return 0.0
    p = fracs / total
    h = -np.sum(p * np.log(p))
    h_max = np.log(len(CLASSES))  # max diversity = all 9 classes equal
    return float(h / h_max * 100.0)


def main():
    parser = argparse.ArgumentParser(description="Process Dynamic World raster to H3")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to DW probs GeoTIFF")
    parser.add_argument("--output", default=os.path.join(OUTPUT_DIR, "sat_land_use.parquet"))
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input raster not found: {args.input}")
        print("Run gee_dynamic_world.py first, then download from Drive.")
        return 1

    print(f"Processing {args.input} -> H3 res-{H3_RESOLUTION}")

    # Load hexagon grid
    import json
    with open(HEXAGONS_PATH, "r") as f:
        hexgrid = json.load(f)

    features = hexgrid["features"]
    print(f"  Hexagons: {len(features):,}")

    t0 = time.time()
    results = []

    with rasterio.open(args.input) as src:
        print(f"  Raster: {src.width}x{src.height}, {src.count} bands, CRS={src.crs}")

        for i, feat in enumerate(features):
            if i % 50000 == 0 and i > 0:
                print(f"  {i:,}/{len(features):,}...")

            h3index = feat["properties"].get("h3index") or feat["properties"].get("h3_index") or feat["id"]
            geom = shape(feat["geometry"])
            bounds = geom.bounds  # minx, miny, maxx, maxy

            try:
                window = from_bounds(*bounds, transform=src.transform)
                window_data = src.read(window=window)  # shape: (bands, rows, cols)

                if window_data.size == 0:
                    continue

                # Create mask for hexagon
                transform = rasterio.windows.transform(window, src.transform)
                mask = geometry_mask([geom], out_shape=window_data.shape[1:],
                                    transform=transform, invert=True)

                # Mean fraction per class within hexagon
                fracs = []
                for band_idx in range(min(src.count, len(CLASSES))):
                    band = window_data[band_idx].astype(float)
                    band[~mask] = np.nan
                    nodata = src.nodata
                    if nodata is not None:
                        band[band == nodata] = np.nan
                    mean_val = np.nanmean(band)
                    fracs.append(mean_val if not np.isnan(mean_val) else 0.0)

                # Pad if fewer bands
                while len(fracs) < len(CLASSES):
                    fracs.append(0.0)

                fracs_arr = np.array(fracs)
                score = compute_shannon(fracs_arr)

                row = {"h3index": h3index, "score": round(score, 1)}
                for j, col in enumerate(COL_NAMES):
                    row[col] = round(fracs_arr[j], 4)
                results.append(row)

            except Exception:
                continue

    df = pd.DataFrame(results)
    df.to_parquet(args.output, index=False)

    elapsed = time.time() - t0
    size_kb = os.path.getsize(args.output) / 1024
    print(f"\n  Output: {args.output}")
    print(f"  Rows: {len(df):,}, Size: {size_kb:.0f} KB")
    print(f"  Score range: [{df['score'].min():.1f}, {df['score'].max():.1f}]")
    print(f"  Time: {elapsed:.0f}s")

    # Top classes by mean fraction
    for col in COL_NAMES:
        print(f"  {col}: mean={df[col].mean():.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
