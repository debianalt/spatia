"""
Process Hansen loss year and treecover2000 rasters to H3 hexagonal grid.

Uses true zonal statistics (geometry mask over the hex polygon) instead of
centroid sampling, so each H3 res-9 cell now reports:
  - hex_pixel_count: number of Hansen 30 m pixels covered by the hex polygon
  - loss_count per year (2001-2024): how many pixels lost forest in that year
  - treecover_mean: mean of treecover2000 (%) over the polygon

This replaces the previous centroid-only sample which gave a 0/1 binary for
the entire hex, severely undersampling actual loss area.

Input:
  pipeline/output/hansen_lossyear.tif     (pixel = year of loss, 0-24)
  pipeline/output/hansen_treecover2000.tif (pixel = % tree cover)
  pipeline/output/hexagons-lite.geojson   (H3 res-9 grid)

Output:
  pipeline/output/hansen_h3_annual.parquet  (h3index, year, lost, hex_pixel_count, treecover2000)
  pipeline/output/sat_deforestation_dynamics.parquet (Spatia layer, H3 res-9)

Usage:
  python pipeline/process_hansen_to_h3.py
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

from config import OUTPUT_DIR

LOSSYEAR_PATH = os.path.join(OUTPUT_DIR, "hansen_lossyear.tif")
TREECOVER_PATH = os.path.join(OUTPUT_DIR, "hansen_treecover2000.tif")
HEXAGONS_PATH = os.path.join(OUTPUT_DIR, "hexagons-lite.geojson")
ANNUAL_PATH = os.path.join(OUTPUT_DIR, "hansen_h3_annual.parquet")
SPATIA_PATH = os.path.join(OUTPUT_DIR, "sat_deforestation_dynamics.parquet")


def set_territory_paths(territory_id: str) -> None:
    """Redirect module-level paths to a per-territory output subdirectory.

    Misiones uses the flat output/ tree; other territories use output/<id>/.
    Falls back from hexagons-lite.geojson to hexagons.geojson if the lite
    file is missing (non-Misiones territories only ship the full grid).
    """
    global LOSSYEAR_PATH, TREECOVER_PATH, HEXAGONS_PATH, ANNUAL_PATH, SPATIA_PATH
    if territory_id == 'misiones':
        return
    t_dir = os.path.join(OUTPUT_DIR, territory_id)
    LOSSYEAR_PATH = os.path.join(t_dir, "hansen_lossyear.tif")
    TREECOVER_PATH = os.path.join(t_dir, "hansen_treecover2000.tif")
    lite = os.path.join(t_dir, "hexagons-lite.geojson")
    HEXAGONS_PATH = lite if os.path.exists(lite) else os.path.join(t_dir, "hexagons.geojson")
    ANNUAL_PATH = os.path.join(t_dir, "hansen_h3_annual.parquet")
    SPATIA_PATH = os.path.join(t_dir, "sat_deforestation_dynamics.parquet")


BASELINE_YEARS = range(2001, 2011)
CURRENT_YEARS = range(2015, 2025)
LOSS_YEAR_CODES = list(range(1, 25))  # 1..24 -> 2001..2024


def hex_zonal_hansen(features):
    """
    Single-pass zonal statistics over the Hansen lossyear and treecover rasters
    for every hex polygon.

    Returns a DataFrame with one row per hex, columns:
      h3index, hex_pixel_count, treecover_mean,
      loss_y01, loss_y02, ..., loss_y24

    Each loss_yNN column is the count of Hansen 30 m pixels inside the hex
    polygon whose lossyear == NN (i.e. lost forest in 2000+NN).
    """
    n = len(features)
    print(f"  Zonal stats over {n:,} hexagons...")
    t0 = time.time()
    rows = []

    with rasterio.open(LOSSYEAR_PATH) as ly_src, rasterio.open(TREECOVER_PATH) as tc_src:
        # Sanity: both rasters should be in EPSG:4326 since gee_export uses crs='EPSG:4326'
        for i, feat in enumerate(features):
            h3id = feat["properties"]["h3index"]
            geom = shape(feat["geometry"])
            try:
                window = from_bounds(*geom.bounds, transform=ly_src.transform)
                window = window.round_offsets().round_lengths()
                if window.width < 1 or window.height < 1:
                    rows.append({"h3index": h3id, "hex_pixel_count": 0, "treecover_mean": 0.0,
                                 **{f"loss_y{y:02d}": 0 for y in LOSS_YEAR_CODES}})
                    continue

                ly_data = ly_src.read(1, window=window)
                # treecover raster: same scale/CRS, same window math
                tc_window = from_bounds(*geom.bounds, transform=tc_src.transform)
                tc_window = tc_window.round_offsets().round_lengths()
                tc_data = tc_src.read(1, window=tc_window) if tc_window.width >= 1 and tc_window.height >= 1 else np.zeros_like(ly_data)

                # Polygon mask in lossyear-window space (rasters share grid)
                gmask = geometry_mask(
                    [geom],
                    transform=ly_src.window_transform(window),
                    out_shape=ly_data.shape,
                    invert=True,  # True INSIDE the polygon
                )

                inside_loss = ly_data[gmask]
                # Match treecover shape if it differs (defensive)
                if tc_data.shape != ly_data.shape:
                    inside_tc = np.array([], dtype=tc_data.dtype)
                else:
                    inside_tc = tc_data[gmask]

                rec = {
                    "h3index": h3id,
                    "hex_pixel_count": int(inside_loss.size),
                    "treecover_mean": float(np.mean(inside_tc)) if inside_tc.size > 0 else 0.0,
                }
                for y in LOSS_YEAR_CODES:
                    rec[f"loss_y{y:02d}"] = int(np.count_nonzero(inside_loss == y))
                rows.append(rec)
            except Exception:
                rows.append({"h3index": h3id, "hex_pixel_count": 0, "treecover_mean": 0.0,
                             **{f"loss_y{y:02d}": 0 for y in LOSS_YEAR_CODES}})

            if (i + 1) % 25000 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (n - i - 1) / rate if rate > 0 else 0
                print(f"    {i + 1:,}/{n:,} hexagons ({elapsed:.0f}s elapsed, ~{eta:.0f}s ETA)")

    df = pd.DataFrame(rows)
    elapsed = time.time() - t0
    total_loss = df[[f"loss_y{y:02d}" for y in LOSS_YEAR_CODES]].sum().sum()
    print(f"  Done in {elapsed:.0f}s. Total loss pixels across all hexes: {int(total_loss):,}")
    return df


def percentile_rank(series):
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result.round(1)


def main():
    parser = argparse.ArgumentParser(description="Hansen -> H3 zonal stats")
    parser.add_argument("--territory", default="misiones",
                        help="Territory ID (default: misiones)")
    args = parser.parse_args()
    set_territory_paths(args.territory)

    t0 = time.time()
    print(f"Territory: {args.territory}")
    print(f"  lossyear:  {LOSSYEAR_PATH}")
    print(f"  treecover: {TREECOVER_PATH}")
    print(f"  hexagons:  {HEXAGONS_PATH}")
    print(f"  output:    {SPATIA_PATH}")

    # Load hexagon grid
    print("Loading hexagon grid...")
    with open(HEXAGONS_PATH) as f:
        gj = json.load(f)
    features = gj["features"]
    print(f"  {len(features):,} hexagons")

    # ── Single-pass true zonal stats ───────────────────────────────────────
    print("\nComputing zonal statistics (polygon mask, not centroid)...")
    counts = hex_zonal_hansen(features)
    print(f"  Hexagons with raster coverage: "
          f"{(counts['hex_pixel_count'] > 0).sum():,}/{len(counts):,}")
    print(f"  Mean Hansen pixels per hex: {counts['hex_pixel_count'].mean():.1f}")
    print(f"  Mean treecover2000: {counts['treecover_mean'].mean():.1f}%")

    # ── Build annual panel with proper pixel counts ────────────────────────
    print("\nBuilding annual panel from per-year counts...")
    long_rows = []
    for _, row in counts.iterrows():
        h3id = row["h3index"]
        hex_px = int(row["hex_pixel_count"])
        tc = float(row["treecover_mean"])
        for y in LOSS_YEAR_CODES:
            long_rows.append({
                "h3index": h3id,
                "year": 2000 + y,
                "lost": int(row[f"loss_y{y:02d}"]),  # NOW: count of pixels lost that year
                "hex_pixel_count": hex_px,
                "treecover2000": tc,
            })
    panel = pd.DataFrame(long_rows)
    print(f"  Panel: {len(panel):,} rows ({len(counts):,} hex x 24 years)")
    panel.to_parquet(ANNUAL_PATH, index=False)
    print(f"  Saved: {ANNUAL_PATH}")

    # ── Build Spatia deforestation_dynamics layer ──────────────────────────
    print("\nBuilding Spatia layer (sat_deforestation_dynamics)...")

    # Per-hex aggregations from the annual panel.
    # NOTE: 'lost' is now a pixel count (≥0), not a 0/1 flag.
    bl_count = panel[panel.year.isin(BASELINE_YEARS)].groupby("h3index")["lost"].sum()
    cur_count = panel[panel.year.isin(CURRENT_YEARS)].groupby("h3index")["lost"].sum()
    cumul_count = panel.groupby("h3index")["lost"].sum()
    hex_px_map = panel.drop_duplicates("h3index").set_index("h3index")["hex_pixel_count"]
    tc_map = panel.drop_duplicates("h3index").set_index("h3index")["treecover2000"]

    result = pd.DataFrame({
        "loss_baseline_px": bl_count,
        "loss_current_px": cur_count,
        "loss_cumulative_px": cumul_count,
        "hex_pixel_count": hex_px_map,
        "treecover2000": tc_map,
    }).reset_index()

    # Convert pixel counts to fractions of hex area (% of the hex polygon)
    safe_px = result["hex_pixel_count"].replace(0, np.nan)
    n_baseline_years = len(list(BASELINE_YEARS))
    n_current_years = len(list(CURRENT_YEARS))

    # Annual rate: average % of hex area lost per year in the period
    result["loss_rate_baseline"] = (result["loss_baseline_px"] / safe_px / n_baseline_years * 100).fillna(0)
    result["loss_rate_current"] = (result["loss_current_px"] / safe_px / n_current_years * 100).fillna(0)
    result["loss_delta"] = result["loss_rate_current"] - result["loss_rate_baseline"]

    # Cumulative loss as % of hex area (2001-2024)
    result["loss_cumulative_pct"] = (result["loss_cumulative_px"] / safe_px * 100).fillna(0)

    # Only hexagons with some baseline forest
    result = result[result.treecover2000 > 5].copy()

    # Scores (higher loss rate = higher score = more deforestation pressure)
    result["score"] = percentile_rank(result["loss_rate_current"])
    result["score_baseline"] = percentile_rank(result["loss_rate_baseline"])
    result["delta_score"] = (result["score"] - result["score_baseline"]).round(1)

    # Display values
    result["c_loss_rate"] = result["loss_rate_current"].round(3)
    result["c_loss_rate_baseline"] = result["loss_rate_baseline"].round(3)
    result["c_loss_rate_delta"] = result["loss_delta"].round(3)
    result["c_cumulative"] = result["loss_cumulative_pct"].round(2)
    result["c_treecover"] = result["treecover2000"].round(0)

    # Type labels
    try:
        result["type"] = pd.qcut(result["score"], 4, labels=[1, 2, 3, 4]).astype(int)
    except ValueError:
        result["type"] = pd.cut(result["score"], bins=[0, 25, 50, 75, 100],
                                labels=[1, 2, 3, 4], include_lowest=True).astype(int)
    type_map = {1: "Baja presion", 2: "Presion moderada",
                3: "Alta presion", 4: "Presion critica"}
    result["type_label"] = result["type"].map(type_map)

    out_cols = ["h3index", "score", "score_baseline", "delta_score",
                "c_loss_rate", "c_loss_rate_baseline", "c_loss_rate_delta",
                "c_cumulative", "c_treecover", "type", "type_label"]
    result = result[out_cols]

    # Summary
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Hexagons (forested, treecover>5%): {len(result):,}")
    print(f"  Loss rate current: mean={result.c_loss_rate.mean():.3f} %/yr")
    print(f"  Loss rate baseline: mean={result.c_loss_rate_baseline.mean():.3f} %/yr")
    print(f"  Delta: mean={result.c_loss_rate_delta.mean():.3f} %/yr")
    print(f"  Cumulative loss: mean={result.c_cumulative.mean():.2f} % of hex area")
    print(f"  Tree cover 2000: mean={result.c_treecover.mean():.0f}%")
    print(f"  Types: {result.type.value_counts().sort_index().to_dict()}")
    print(f"  Built in {elapsed:.0f}s")

    result.to_parquet(SPATIA_PATH, index=False)
    size_mb = os.path.getsize(SPATIA_PATH) / (1024 * 1024)
    print(f"  Saved: {SPATIA_PATH} ({size_mb:.1f} MB)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
