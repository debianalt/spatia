"""
Process air quality raster (PM2.5, NO2, AOD) to H3 res9 via centroid sampling.

The air quality rasters are ~1km resolution while H3 res9 hexagons are ~174m.
Multiple hexagons fall within a single pixel, so centroid sampling (not zonal
stats) is the appropriate method — it assigns each hexagon the value of the
pixel containing its centroid.

After sampling, PCA-validated geometric mean scoring is applied (OECD/HDI).

Input:
  pipeline/output/sat_air_quality_raster.tif  (3-band: c_pm25, c_no2, c_aod)

Output:
  pipeline/output/sat_air_quality.parquet  (h3index, score, c_pm25, c_no2, c_aod)

Usage:
  python pipeline/process_air_quality_to_h3.py
  python pipeline/process_air_quality_to_h3.py --diagnostics
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import shape

from config import OUTPUT_DIR
from scoring import run_full_diagnostics, geometric_mean_score

RASTER_PATH = os.path.join(OUTPUT_DIR, "sat_air_quality_raster.tif")
HEXAGONS_PATH = os.path.join(OUTPUT_DIR, "hexagons-lite.geojson")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "sat_air_quality.parquet")

BANDS = [
    # (band_idx, name, invert)
    (1, 'c_pm25', False),   # higher PM2.5 = worse air quality
    (2, 'c_no2', False),    # higher NO2 = worse
    (3, 'c_aod', False),    # higher AOD = worse
]


def percentile_rank(series):
    """Percentile rank 0-100."""
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result


def main():
    parser = argparse.ArgumentParser(description="Air quality raster to H3 (centroid)")
    parser.add_argument("--diagnostics", action="store_true", help="Emit diagnostics JSON")
    args = parser.parse_args()

    print("Loading hexagon grid...")
    with open(HEXAGONS_PATH) as f:
        gj = json.load(f)
    features = gj["features"]
    n = len(features)
    print(f"  {n:,} hexagons")

    print(f"Loading raster: {RASTER_PATH}")
    src = rasterio.open(RASTER_PATH)
    print(f"  {src.width}x{src.height}, {src.count} bands")

    # Centroid sampling
    print("Sampling via centroid...")
    t0 = time.time()
    results = []

    for i, feat in enumerate(features):
        if i % 50000 == 0 and i > 0:
            elapsed = time.time() - t0
            rate = i / elapsed
            eta = (n - i) / rate / 60
            print(f"    {i:,}/{n:,} ({rate:.0f} hex/s, ETA {eta:.1f} min)")

        h3index = feat["properties"]["h3index"]
        geom = shape(feat["geometry"])
        cx, cy = geom.centroid.x, geom.centroid.y

        row = {"h3index": h3index}
        try:
            r, c = src.index(cx, cy)
            if 0 <= r < src.height and 0 <= c < src.width:
                for band_idx, name, _ in BANDS:
                    val = float(src.read(band_idx, window=((r, r+1), (c, c+1)))[0, 0])
                    row[name] = val if not np.isnan(val) else np.nan
            else:
                for _, name, _ in BANDS:
                    row[name] = np.nan
        except Exception:
            for _, name, _ in BANDS:
                row[name] = np.nan

        results.append(row)

    src.close()
    df = pd.DataFrame(results)
    elapsed = time.time() - t0
    print(f"  Sampled {len(df):,} hexagons in {elapsed:.0f}s")

    # Coverage
    for _, name, _ in BANDS:
        valid = df[name].notna().sum()
        print(f"  {name}: {valid:,}/{n:,} ({valid/n*100:.1f}%)")

    # Percentile rank
    for _, name, invert in BANDS:
        raw = df[name].astype(float)
        if invert:
            raw = -raw
        df[name] = percentile_rank(raw).round(1)

    # PCA diagnostics + scoring
    comp_cols = [b[1] for b in BANDS]
    valid_mask = df[comp_cols].notna().all(axis=1)
    df_valid = df.loc[valid_mask]
    print(f"  Valid for PCA: {len(df_valid):,}")

    diagnostics = run_full_diagnostics(df_valid, comp_cols, corr_threshold=0.70)
    retained = diagnostics["variable_selection"]["retained"]
    dropped = diagnostics["variable_selection"]["dropped"]

    kmo = diagnostics["kmo_bartlett"].get("kmo_overall")
    if kmo is not None:
        print(f"  KMO: {kmo:.3f} {'OK' if kmo >= 0.60 else 'WARNING'}")
    if dropped:
        print(f"  Dropped (|r|>0.70): {dropped}")
    print(f"  Retained ({len(retained)}): {retained}")

    df['score'] = geometric_mean_score(df, retained, floor=1.0).round(1)

    # Output
    out_cols = ['h3index', 'score'] + comp_cols
    result = df[out_cols].dropna(subset=['score'])
    result.to_parquet(OUTPUT_PATH, index=False)

    size_kb = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"\n  Output: {OUTPUT_PATH}")
    print(f"  Rows: {len(result):,}, Size: {size_kb:.0f} KB")
    print(f"  Score: mean={result['score'].mean():.1f}, median={result['score'].median():.1f}")

    if args.diagnostics:
        diag_path = os.path.join(OUTPUT_DIR, "air_quality_diagnostics.json")
        with open(diag_path, "w") as f:
            json.dump(diagnostics, f, indent=2, default=str)
        print(f"  Diagnostics: {diag_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
