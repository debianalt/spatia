"""
Validation utilities for the Spatia satellite pipeline.

Functions to validate raster files and parquet outputs before upload.
If validation fails, the pipeline halts and does NOT upload to R2.
"""

import os

import numpy as np

from config import MAX_NULL_FRACTION


def validate_raster(path: str) -> bool:
    """
    Validate a downloaded GeoTIFF raster.

    Checks:
      - File exists and size > 1 KB
      - Has at least 1 band
      - Dimensions > 0
      - Not 100% nodata

    Returns True if valid, False otherwise (with printed reason).
    """
    if not os.path.exists(path):
        print(f"  [VALIDATION FAIL] File not found: {path}")
        return False

    size_bytes = os.path.getsize(path)
    if size_bytes < 1024:
        print(f"  [VALIDATION FAIL] File too small ({size_bytes} bytes): {path}")
        return False

    try:
        import rasterio
    except ImportError:
        print("  [VALIDATION WARN] rasterio not installed, skipping raster validation")
        return True

    try:
        with rasterio.open(path) as src:
            if src.count < 1:
                print(f"  [VALIDATION FAIL] No bands in raster: {path}")
                return False

            if src.width == 0 or src.height == 0:
                print(f"  [VALIDATION FAIL] Zero dimensions ({src.width}x{src.height}): {path}")
                return False

            # Read first band and check it's not 100% nodata
            data = src.read(1)
            if src.nodata is not None:
                valid_count = np.sum(data != src.nodata)
            else:
                valid_count = np.sum(~np.isnan(data.astype(float)))

            if valid_count == 0:
                print(f"  [VALIDATION FAIL] 100% nodata in raster: {path}")
                return False

            total = data.size
            valid_pct = valid_count / total * 100
            print(f"  [VALIDATION OK] {path} — {src.width}x{src.height}, "
                  f"{src.count} band(s), {valid_pct:.1f}% valid pixels")
    except Exception as e:
        print(f"  [VALIDATION FAIL] Cannot open raster {path}: {e}")
        return False

    return True


def validate_parquet(path: str, min_rows: int, schema_cols: list,
                     value_ranges: dict = None) -> bool:
    """
    Validate a parquet output file.

    Checks:
      - File exists
      - Row count >= min_rows
      - Expected columns exist
      - Values within specified ranges
      - Null fraction < MAX_NULL_FRACTION

    Returns True if valid, False otherwise (with printed reason).
    """
    if not os.path.exists(path):
        print(f"  [VALIDATION FAIL] File not found: {path}")
        return False

    import pandas as pd

    try:
        df = pd.read_parquet(path)
    except Exception as e:
        print(f"  [VALIDATION FAIL] Cannot read parquet {path}: {e}")
        return False

    # Row count
    if len(df) < min_rows:
        print(f"  [VALIDATION FAIL] Only {len(df):,} rows (minimum: {min_rows:,}): {path}")
        return False

    # Schema check
    missing = [c for c in schema_cols if c not in df.columns]
    if missing:
        print(f"  [VALIDATION FAIL] Missing columns {missing}: {path}")
        return False

    # Null fraction
    for col in schema_cols:
        null_frac = df[col].isna().mean()
        if null_frac > MAX_NULL_FRACTION:
            print(f"  [VALIDATION FAIL] Column '{col}' has {null_frac:.1%} nulls "
                  f"(max: {MAX_NULL_FRACTION:.0%}): {path}")
            return False

    # Value ranges
    if value_ranges:
        for col, (vmin, vmax) in value_ranges.items():
            if col not in df.columns:
                continue
            col_min = df[col].min()
            col_max = df[col].max()
            if col_min < vmin or col_max > vmax:
                print(f"  [VALIDATION FAIL] Column '{col}' range [{col_min:.2f}, {col_max:.2f}] "
                      f"outside expected [{vmin}, {vmax}]: {path}")
                return False

    print(f"  [VALIDATION OK] {path} — {len(df):,} rows, "
          f"columns {schema_cols}")
    return True
