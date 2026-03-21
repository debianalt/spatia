"""
Aggregate flood raster data to H3 hexagons.

Reads GeoTIFF rasters (from GEE export) and computes zonal statistics
per H3 hexagon, producing hex_flood_risk.parquet.

Metrics per hexagon:
  - flood_recurrence_mean: average recurrence fraction (0–1) across pixels
  - flood_extent_pct: % of hexagon area currently flooded
  - flood_risk_score: composite score 0–100

Usage:
  python pipeline/process_to_h3.py \
    --recurrence pipeline/output/flood_recurrence_historical.tif \
    --current pipeline/output/flood_current_YYYYMMDD.tif \
    --grid pipeline/output/hexagons.geojson \
    --output pipeline/output/hex_flood_risk.parquet
"""

import argparse
import os
import sys

import geopandas as gpd
import h3
import numpy as np
import pandas as pd

try:
    import rasterio
    from rasterio.features import geometry_mask
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False
    print("Warning: rasterio not installed. Using simplified sampling method.")


def load_hex_grid(grid_path: str) -> gpd.GeoDataFrame:
    """Load H3 hexagon grid."""
    gdf = gpd.read_file(grid_path)
    print(f"  Loaded {len(gdf):,} hexagons from {grid_path}")
    return gdf


def zonal_stats_rasterio(gdf: gpd.GeoDataFrame, raster_path: str, stat: str = "mean",
                         ignore_src_nodata: bool = False) -> pd.Series:
    """
    Compute zonal statistics for each hexagon using rasterio.
    Returns a Series indexed like gdf with the computed statistic.
    """
    if not HAS_RASTERIO:
        return pd.Series(np.nan, index=gdf.index)

    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds

    values = []
    with rasterio.open(raster_path) as src:
        src_nodata = src.nodata
        for _, row in gdf.iterrows():
            try:
                # Compute window from geometry bounds (bypass rasterio nodata handling)
                window = from_bounds(*row.geometry.bounds, transform=src.transform)
                window = window.round_offsets().round_lengths()
                if window.width < 1 or window.height < 1:
                    values.append(np.nan)
                    continue
                data = src.read(1, window=window).astype(float)
                # Mark raster nodata (e.g. -32768) as NaN.
                # For binary masks (S1), nodata=0 conflicts with valid "dry"
                # pixels — pass ignore_src_nodata=True to skip this step.
                if src_nodata is not None and not ignore_src_nodata:
                    data[data == src_nodata] = np.nan
                # JRC encodes "not water" as -128 → treat as 0
                data[data < 0] = 0
                # Mask only by geometry, NOT by raster nodata
                gmask = geometry_mask(
                    [row.geometry],
                    transform=src.window_transform(window),
                    out_shape=data.shape,
                    invert=False,  # True where OUTSIDE geometry
                )
                data[gmask] = np.nan
                valid = data[~np.isnan(data)]
                if len(valid) == 0:
                    values.append(np.nan)
                elif stat == "mean":
                    values.append(float(np.mean(valid)))
                elif stat == "sum":
                    values.append(float(np.sum(valid)))
                elif stat == "max":
                    values.append(float(np.max(valid)))
                else:
                    values.append(float(np.mean(valid)))
            except (rasterio.errors.WindowError, IndexError, ValueError):
                # Expected: hexagon outside raster extent or empty window
                values.append(np.nan)

    valid_count = sum(1 for v in values if not (v != v))  # NaN != NaN
    print(f"  Zonal stats (masking): {valid_count}/{len(values)} hexagons with valid data "
          f"({valid_count/len(values)*100:.1f}%)")
    return pd.Series(values, index=gdf.index)


def zonal_stats_sampling(gdf: gpd.GeoDataFrame, raster_path: str) -> pd.Series:
    """
    Simplified zonal stats: sample raster at hexagon centroids.
    Fallback when rasterio zonal masking is too slow or unavailable.
    """
    if not HAS_RASTERIO:
        return pd.Series(np.nan, index=gdf.index)

    import rasterio

    centroids = gdf.geometry.centroid
    values = []

    with rasterio.open(raster_path) as src:
        for _, centroid in centroids.items():
            try:
                row_col = src.index(centroid.x, centroid.y)
                val = src.read(1, window=rasterio.windows.Window(
                    row_col[1], row_col[0], 1, 1
                ))[0, 0]
                if val == src.nodata:
                    values.append(np.nan)
                else:
                    values.append(float(val))
            except IndexError:
                # Expected: centroid falls outside raster extent
                values.append(np.nan)

    valid_count = sum(1 for v in values if not (v != v))  # NaN != NaN
    print(f"  Zonal stats (sampling): {valid_count}/{len(values)} hexagons with valid data "
          f"({valid_count/len(values)*100:.1f}%)")
    return pd.Series(values, index=gdf.index)


def compute_flood_risk_score(jrc_occurrence: pd.Series, jrc_recurrence: pd.Series,
                             s1_extent: pd.Series) -> pd.Series:
    """
    Composite flood risk score (0–100).

    Combines JRC Global Surface Water (1984–2021) historical data with
    Sentinel-1 SAR current flood extent.

    Weights: 50% JRC occurrence + 20% JRC recurrence + 30% S1 current extent.
    """
    occ_norm = (jrc_occurrence / 100).clip(0, 1)
    rec_norm = (jrc_recurrence / 100).clip(0, 1)
    ext_norm = s1_extent.clip(0, 1)

    score = (0.5 * occ_norm + 0.2 * rec_norm + 0.3 * ext_norm) * 100
    return score.round(1)


def generate_synthetic_data(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Generate synthetic flood risk data for development/testing.
    Uses latitude as a proxy: lower areas (further south, closer to rivers) have higher risk.
    """
    np.random.seed(42)
    n = len(gdf)

    # Latitude-based base risk (southern Misiones = lower lat = more rivers)
    lats = gdf.geometry.centroid.y
    lat_norm = (lats - lats.min()) / (lats.max() - lats.min())
    # Invert: lower lat = higher risk
    base_risk = 1 - lat_norm

    # Add some noise
    recurrence = (base_risk * 0.4 + np.random.beta(2, 5, n) * 0.3).clip(0, 1)
    extent = (np.random.beta(1.5, 10, n) * recurrence).clip(0, 1)
    score = compute_flood_risk_score(
        pd.Series(recurrence, index=gdf.index),
        pd.Series(extent, index=gdf.index),
    )

    return pd.DataFrame({
        "h3index": gdf["h3index"],
        "flood_recurrence_mean": recurrence.round(4),
        "flood_extent_pct": (extent * 100).round(2),
        "flood_risk_score": score,
    })


def main():
    parser = argparse.ArgumentParser(description="Aggregate flood data to H3 hexagons")
    parser.add_argument("--recurrence", help="Path to historical recurrence GeoTIFF")
    parser.add_argument("--current", help="Path to current flood extent GeoTIFF")
    parser.add_argument("--grid", required=True, help="Path to hexagons GeoJSON")
    parser.add_argument("--output", default="pipeline/output/hex_flood_risk.parquet",
                        help="Output parquet path")
    parser.add_argument("--synthetic", action="store_true",
                        help="Generate synthetic data for testing (no rasters needed)")
    args = parser.parse_args()

    print("Loading H3 grid...")
    gdf = load_hex_grid(args.grid)

    if args.synthetic:
        print("Generating synthetic flood risk data...")
        df = generate_synthetic_data(gdf)
    else:
        if not args.recurrence or not args.current:
            print("Error: --recurrence and --current required (or use --synthetic)")
            sys.exit(1)

        print("Computing zonal statistics for recurrence...")
        recurrence = zonal_stats_rasterio(gdf, args.recurrence)

        print("Computing zonal statistics for current extent...")
        extent = zonal_stats_rasterio(gdf, args.current)

        score = compute_flood_risk_score(recurrence, extent)

        df = pd.DataFrame({
            "h3index": gdf["h3index"],
            "flood_recurrence_mean": recurrence.round(4),
            "flood_extent_pct": (extent * 100).round(2),
            "flood_risk_score": score,
        })

    # Drop hexagons with no data
    df = df.dropna(subset=["flood_risk_score"])

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df.to_parquet(args.output, index=False)
    print(f"\nSaved {len(df):,} hexagons to {args.output}")
    print(f"  Score range: {df['flood_risk_score'].min():.1f} – {df['flood_risk_score'].max():.1f}")
    print(f"  Mean score: {df['flood_risk_score'].mean():.1f}")
    print(f"  Hexagons with recurrence > 0.1: {(df['flood_recurrence_mean'] > 0.1).sum():,}")


if __name__ == "__main__":
    main()
