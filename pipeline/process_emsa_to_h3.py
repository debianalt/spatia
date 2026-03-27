"""
Convert EMSA powerline shapefile (vector lines) to H3-indexed parquet.

Downloads the medium/high-voltage network shapefile from datos.energia.gob.ar,
intersects with the Misiones H3 res-9 grid, and computes line length per hexagon.

Output: pipeline/output/emsa_powerlines.parquet
Columns: h3index, line_length_m, line_count, score (percentile rank 0-100)

Usage:
    python pipeline/process_emsa_to_h3.py
    python pipeline/process_emsa_to_h3.py --local path/to/shapefile.shp
"""

import argparse
import os
import sys
import tempfile
import urllib.request
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd

from config import (
    EMSA_PARQUET,
    EMSA_URL,
    MIN_EMSA_HEXAGONS,
    OUTPUT_DIR,
    GRID_PATH,
)

UTM_21S = "EPSG:32721"


def download_emsa(cache_dir: str | None = None) -> str:
    """Download and extract the EMSA shapefile. Returns path to .shp file."""
    cache_dir = cache_dir or os.path.join(OUTPUT_DIR, "emsa_cache")
    os.makedirs(cache_dir, exist_ok=True)
    zip_path = os.path.join(cache_dir, "emsa_misiones.zip")

    # Check for cached shapefile
    for f in os.listdir(cache_dir):
        if f.endswith(".shp"):
            shp_path = os.path.join(cache_dir, f)
            print(f"  [cache] Using cached shapefile: {shp_path}")
            return shp_path

    print(f"  Downloading EMSA shapefile from datos.energia.gob.ar...")
    req = urllib.request.Request(EMSA_URL, headers={"User-Agent": "spatia-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(zip_path, "wb") as f:
        f.write(resp.read())
    print(f"  [ok] Downloaded {os.path.getsize(zip_path) / 1024:.0f} KB")

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(cache_dir)
    os.remove(zip_path)

    for f in os.listdir(cache_dir):
        if f.endswith(".shp"):
            return os.path.join(cache_dir, f)

    raise FileNotFoundError("No .shp file found in downloaded archive")


def percentile_rank(series: pd.Series) -> pd.Series:
    """Rank values as percentiles 0-100, matching existing pipeline pattern."""
    ranked = series.rank(method="average", pct=True) * 100
    return ranked.round(1)


def process(shp_path: str) -> pd.DataFrame:
    """Intersect powerlines with H3 grid and compute metrics per hexagon."""

    # Load powerlines
    print("  Loading powerlines...")
    lines = gpd.read_file(shp_path)
    if lines.crs is None:
        lines = lines.set_crs("EPSG:4326")
    elif lines.crs.to_epsg() != 4326:
        lines = lines.to_crs("EPSG:4326")
    print(f"  [ok] {len(lines)} line features loaded")

    # Load H3 grid
    print("  Loading H3 grid (this may take a moment)...")
    hexagons = gpd.read_file(GRID_PATH)
    print(f"  [ok] {len(hexagons)} hexagons loaded")

    # Project both to UTM for metric calculations
    print("  Projecting to UTM 21S...")
    lines_utm = lines.to_crs(UTM_21S)
    hex_utm = hexagons[["h3index", "geometry"]].to_crs(UTM_21S)

    # Spatial intersection: clip lines to hexagon boundaries
    print("  Computing spatial intersection (lines x hexagons)...")
    intersected = gpd.overlay(hex_utm, lines_utm, how="intersection", keep_geom_type=False)
    print(f"  [ok] {len(intersected)} intersected segments")

    if len(intersected) == 0:
        print("  [ERROR] No intersections found. Check CRS and data extent.")
        sys.exit(1)

    # Compute line length for each clipped segment
    intersected["seg_length_m"] = intersected.geometry.length

    # Aggregate per hexagon
    print("  Aggregating per hexagon...")
    agg = intersected.groupby("h3index").agg(
        line_length_m=("seg_length_m", "sum"),
        line_count=("seg_length_m", "count"),
    ).reset_index()

    agg["line_length_m"] = agg["line_length_m"].round(1)
    agg["score"] = percentile_rank(agg["line_length_m"])

    return agg


def validate(df: pd.DataFrame) -> bool:
    """Basic validation of the output dataframe."""
    n = len(df)
    print(f"\n  === Validation ===")
    print(f"  Hexagons with powerlines: {n:,}")
    print(f"  line_length_m: min={df['line_length_m'].min():.1f}, "
          f"max={df['line_length_m'].max():.1f}, "
          f"mean={df['line_length_m'].mean():.1f}")
    print(f"  line_count: min={df['line_count'].min()}, "
          f"max={df['line_count'].max()}, "
          f"mean={df['line_count'].mean():.1f}")
    print(f"  score: min={df['score'].min()}, max={df['score'].max()}")

    if n < MIN_EMSA_HEXAGONS:
        print(f"  [WARN] Only {n} hexagons, expected >= {MIN_EMSA_HEXAGONS}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="EMSA powerlines to H3 parquet")
    parser.add_argument("--local", help="Path to local .shp file (skip download)")
    args = parser.parse_args()

    print("=" * 60)
    print("EMSA Powerlines -> H3 Pipeline")
    print("=" * 60)

    # Step 1: Get shapefile
    if args.local:
        shp_path = args.local
        if not os.path.exists(shp_path):
            print(f"  [ERROR] File not found: {shp_path}")
            sys.exit(1)
    else:
        shp_path = download_emsa()

    # Step 2: Process
    df = process(shp_path)

    # Step 3: Validate
    ok = validate(df)

    # Step 4: Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df.to_parquet(EMSA_PARQUET, index=False)
    size_mb = os.path.getsize(EMSA_PARQUET) / (1024 * 1024)
    print(f"\n  [ok] Saved {EMSA_PARQUET} ({size_mb:.2f} MB, {len(df):,} rows)")

    if not ok:
        print("  [WARN] Validation warnings detected — review output before uploading")
        sys.exit(1)

    print("\nDone. Next: upload to R2 with:")
    print(f"  npx wrangler r2 object put neahub/data/emsa_powerlines.parquet "
          f"--file {EMSA_PARQUET} --remote")


if __name__ == "__main__":
    main()
