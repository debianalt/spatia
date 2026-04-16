"""
Process carbon stock GeoTIFF to H3 parquet with raw physical units + scores.

Reads sat_carbon_stock_raster.tif (10 bands from gee_export_carbon_stock.py),
computes zonal stats per hexagon, derives total carbon stock, BGB, economic
value, and produces both raw values (tC/ha, MgCO2/ha/yr, USD/ha) and
percentile-ranked scores (0-100).

Output schema:
  h3index | score | type | type_label |
  c_agb_cci | c_agb_cci_raw | c_agb_gedi | c_agb_gedi_raw |
  c_total_carbon | c_total_carbon_raw | c_soc | c_soc_raw |
  c_gross_emissions | c_gross_emissions_raw | c_gross_removals | c_gross_removals_raw |
  c_net_flux | c_net_flux_raw | c_npp | c_npp_raw |
  c_economic_value | ...

Usage:
  python pipeline/process_carbon_to_h3.py
  python pipeline/process_carbon_to_h3.py --carbon-price 12
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
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR, get_territory

HEXAGONS_PATH = os.path.join(OUTPUT_DIR, "hexagons-lite.geojson")
RASTER_PATH = os.path.join(OUTPUT_DIR, "sat_carbon_stock_raster.tif")

# Band order must match gee_export_carbon_stock.py
# (band_idx, col_name, zero_is_nodata)
BANDS = [
    (1,  'c_agb_cci',       True),   # ESA CCI AGB, Mg/ha — 0 = no biomass data
    (2,  'c_agb_gedi',      True),   # GEDI L4B AGB mean, Mg/ha
    (3,  'c_gedi_se',       True),   # GEDI L4B SE, Mg/ha
    (4,  'c_soc_raw_dgkg',  True),   # SoilGrids SOC 0-5cm, dg/kg
    (5,  'c_npp_raw',       True),   # MODIS NPP, gC/m2/yr
    (6,  'c_treecover',     False),  # Hansen treecover 2000, 0-1 — 0% = real value
    (7,  'c_loss',          False),  # Hansen cumulative loss, 0/1 — 0 = no loss (real)
    (8,  'c_emissions_raw', False),  # GFW gross emissions — 0 = no emissions (real)
    (9,  'c_removals_raw',  False),  # GFW gross removals — 0 = no removals (real)
    (10, 'c_net_flux_raw',  False),  # GFW net flux — 0 = balanced (real)
]

# Conversion constants
CARBON_FRACTION = 0.47      # AGB -> carbon (IPCC default for tropical forests)
BULK_DENSITY = 1.3          # t/m3 typical for Misiones lateritic soils
SOC_DEPTH = 0.30            # metres (0-30cm layer, extrapolated from 0-5cm)
SOC_DEPTH_FACTOR = 6.0      # 30cm / 5cm layers (conservative, actual profile may differ)
DEFAULT_CARBON_PRICE = 10.0 # USD/tCO2e (voluntary market median 2024)


def zonal_stats_band(src, band_idx, geom, nodata=None, zero_is_nodata=True):
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
        if zero_is_nodata:
            data[data == 0] = np.nan
        valid = data[~np.isnan(data)]
        return float(np.mean(valid)) if len(valid) > 0 else np.nan
    except Exception:
        return np.nan


def percentile_rank(series):
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result


def main():
    parser = argparse.ArgumentParser(description="Process carbon stock raster to H3")
    parser.add_argument("--territory", default="misiones", help="Territory ID (default: misiones)")
    parser.add_argument("--carbon-price", type=float, default=DEFAULT_CARBON_PRICE,
                        help=f"Carbon price in USD/tCO2e (default: {DEFAULT_CARBON_PRICE})")
    parser.add_argument("--k-range", default="4,6", help="k-means range")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    t_prefix = territory['output_prefix']
    if t_prefix:
        t_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/'))
    else:
        t_dir = OUTPUT_DIR
    hexagons_path = os.path.join(t_dir, 'hexagons.geojson') if t_prefix else HEXAGONS_PATH
    raster_path = os.path.join(t_dir, 'sat_carbon_stock_raster.tif')
    output_path = os.path.join(t_dir, 'sat_carbon_stock.parquet')
    temporal_raster = os.path.join(t_dir, 'sat_carbon_temporal_raster.tif')

    t0 = time.time()
    print("=" * 60)
    print("  Carbon Stock & Balance -> H3")
    print(f"  Carbon price: ${args.carbon_price}/tCO2e")
    print("=" * 60)

    # Load hexagon grid
    print("\nLoading hexagon grid...")
    with open(hexagons_path) as f:
        hexgrid = json.load(f)
    features = hexgrid['features']
    print(f"  {len(features):,} hexagons")

    # Process raster
    print(f"\nProcessing {raster_path}...")
    results = []
    n = len(features)

    with rasterio.open(raster_path) as src:
        print(f"  Raster: {src.width}x{src.height}, {src.count} bands")

        for i, feat in enumerate(features):
            if i % 50000 == 0 and i > 0:
                elapsed = time.time() - t0
                rate = i / elapsed
                eta = (n - i) / rate / 60
                print(f"    {i:,}/{n:,} ({rate:.0f} hex/s, ETA {eta:.1f} min)")

            h3index = (feat.get("properties", {}).get("h3index")
                       or feat.get("properties", {}).get("h3_index")
                       or feat.get("id"))
            geom = shape(feat["geometry"])

            row = {"h3index": h3index}
            for band_idx, col_name, zero_nodata in BANDS:
                row[col_name] = zonal_stats_band(src, band_idx, geom, src.nodata, zero_is_nodata=zero_nodata)
            results.append(row)

    df = pd.DataFrame(results)
    print(f"  Raw hexagons: {len(df):,}")

    # ── Derived physical variables ─────────────────────────────────────
    print("\nComputing derived carbon variables...")

    # AGB: use ESA CCI as primary, GEDI as validation column
    df['c_agb_raw'] = df['c_agb_cci']  # Mg/ha

    # Below-ground biomass (Cairns et al. 1997)
    df['c_bgb_raw'] = 0.489 * (df['c_agb_raw'].clip(lower=0.1) ** 0.89)  # Mg/ha

    # SOC: convert from dg/kg to tC/ha (0-30cm, extrapolated)
    # SOC (tC/ha) = ocd (dg/kg) / 10 (g/kg) * bulk_density (t/m3) * depth (m) * 10
    df['c_soc_tcha'] = (df['c_soc_raw_dgkg'] / 10.0) * BULK_DENSITY * SOC_DEPTH * 10.0

    # Total carbon stock: AGB_carbon + BGB_carbon + SOC
    df['c_total_carbon_raw'] = (
        df['c_agb_raw'] * CARBON_FRACTION +
        df['c_bgb_raw'] * CARBON_FRACTION +
        df['c_soc_tcha']
    )  # tC/ha

    # Economic value: total_carbon * 3.67 (C to CO2) * price
    df['c_economic_value'] = (
        df['c_total_carbon_raw'] * 3.67 * args.carbon_price
    ).round(0)  # USD/ha

    # Report validation stats
    valid_agb = df['c_agb_raw'].dropna()
    if len(valid_agb) > 0:
        print(f"  AGB (ESA CCI): mean={valid_agb.mean():.1f} Mg/ha, "
              f"median={valid_agb.median():.1f}, max={valid_agb.max():.1f}")
    valid_gedi = df['c_agb_gedi'].dropna()
    if len(valid_gedi) > 0:
        print(f"  AGB (GEDI):    mean={valid_gedi.mean():.1f} Mg/ha, "
              f"median={valid_gedi.median():.1f}, max={valid_gedi.max():.1f}")
    valid_tc = df['c_total_carbon_raw'].dropna()
    if len(valid_tc) > 0:
        print(f"  Total carbon:  mean={valid_tc.mean():.1f} tC/ha, "
              f"median={valid_tc.median():.1f}, max={valid_tc.max():.1f}")
    valid_econ = df['c_economic_value'].dropna()
    if len(valid_econ) > 0:
        print(f"  Economic value: mean=${valid_econ.mean():.0f}/ha, "
              f"max=${valid_econ.max():.0f}/ha at ${args.carbon_price}/tCO2e")

    # ── Percentile rank scoring ───────────────────────────────────────
    print("\nPercentile rank scoring...")

    score_vars = [
        ('c_agb_raw',           'c_agb_cci',        False),
        ('c_agb_gedi',          'c_agb_gedi',       False),
        ('c_total_carbon_raw',  'c_total_carbon',   False),
        ('c_soc_tcha',          'c_soc',            False),
        ('c_emissions_raw',     'c_gross_emissions', False),  # high emissions = high score
        ('c_removals_raw',      'c_gross_removals', False),
        ('c_net_flux_raw',      'c_net_flux',       False),
        ('c_npp_raw',           'c_npp',            False),
    ]

    for raw_col, score_col, invert in score_vars:
        raw = df[raw_col].astype(float)
        if invert:
            raw = -raw
        df[score_col] = percentile_rank(raw).round(1)

    # Overall score: geometric mean of key carbon dimensions
    key_cols = ['c_total_carbon', 'c_npp', 'c_agb_cci']
    vals = df[key_cols].clip(lower=1.0)
    df['score'] = np.exp(np.log(vals).mean(axis=1)).round(1)

    # ── Temporal baseline ─────────────────────────────────────────────
    # Reads 8-band sat_carbon_temporal_raster.tif:
    #  1-2: c_agb_baseline, c_agb_current (ESA CCI 2018-2020 mean vs 2022)
    #  3-4: c_npp_baseline, c_npp_current (MODIS NPP 2018-2020 vs 2022-2024 mean)
    #  5-6: c_standing_tc_bl, c_standing_tc_cur (Hansen treecover2000 × (1 - cum loss by YYYY))
    #  7-8: c_loss_rate_bl, c_loss_rate_cur (annual Hansen loss rate 2001-2020 vs 2021-2024)
    if os.path.exists(temporal_raster):
        print("\nComputing temporal baseline (8-band: AGB + NPP + standing tc + loss rate)...")
        import rasterio as rio_tmp
        with rio_tmp.open(temporal_raster) as src_t:
            n_bands = src_t.count
            print(f"  Temporal raster: {n_bands} bands")
            rows = []
            for i, feat in enumerate(json.load(open(hexagons_path))['features']):
                h3index = (feat.get("properties", {}).get("h3index")
                           or feat.get("properties", {}).get("h3_index")
                           or feat.get("id"))
                geom = shape(feat["geometry"])
                vals = [zonal_stats_band(src_t, b, geom, src_t.nodata,
                                         zero_is_nodata=(b <= 4))  # AGB/NPP can be legit 0, but prefer NaN outside
                        for b in range(1, min(n_bands, 8) + 1)]
                rows.append((h3index, *vals))
                if i % 100000 == 0 and i > 0:
                    print(f"    {i:,}...")

        tmp_cols = ['h3index', 'c_agb_bl', 'c_agb_cur',
                    'c_npp_bl_raw', 'c_npp_cur_raw',
                    'c_standing_tc_bl_raw', 'c_standing_tc_cur_raw',
                    'c_loss_rate_bl_raw', 'c_loss_rate_cur_raw'][:1 + n_bands]
        temporal_df = pd.DataFrame(rows, columns=tmp_cols)
        df = df.merge(temporal_df, on='h3index', how='left')

        # Baseline total carbon (AGB_bl + BGB(AGB_bl) + static SOC)
        bgb_bl = 0.489 * (df['c_agb_bl'].clip(lower=0.1) ** 0.89)
        df['c_total_carbon_raw_baseline'] = (
            df['c_agb_bl'] * CARBON_FRACTION + bgb_bl * CARBON_FRACTION + df['c_soc_tcha']
        )

        # Baseline percentile ranks (per-component)
        df['c_agb_cci_baseline'] = percentile_rank(df['c_agb_bl']).round(1)
        df['c_total_carbon_baseline'] = percentile_rank(df['c_total_carbon_raw_baseline']).round(1)
        df['c_npp_baseline'] = percentile_rank(df['c_npp_bl_raw'].astype(float)).round(1)

        # Standing tree cover (higher = better, direct rank)
        if 'c_standing_tc_bl_raw' in df.columns:
            df['c_standing_tc_baseline'] = percentile_rank(df['c_standing_tc_bl_raw'].astype(float)).round(1)
            df['c_standing_tc_current'] = percentile_rank(df['c_standing_tc_cur_raw'].astype(float)).round(1)
            df['c_standing_tc_delta'] = (df['c_standing_tc_current'] - df['c_standing_tc_baseline']).round(1)

        # Loss rate (higher loss = worse, so invert before ranking for a "carbon health" view)
        if 'c_loss_rate_bl_raw' in df.columns:
            df['c_loss_rate_baseline'] = percentile_rank(-df['c_loss_rate_bl_raw'].astype(float)).round(1)
            df['c_loss_rate_current'] = percentile_rank(-df['c_loss_rate_cur_raw'].astype(float)).round(1)
            df['c_loss_rate_delta'] = (df['c_loss_rate_current'] - df['c_loss_rate_baseline']).round(1)

        # For other variables without temporal data, baseline = current
        for _, score_col, _ in score_vars:
            bl = f'{score_col}_baseline'
            if bl not in df.columns:
                df[bl] = df[score_col]

        # Baseline overall score — same 3 key cols as current score
        bl_key = ['c_total_carbon_baseline', 'c_npp_baseline', 'c_agb_cci_baseline']
        vals_bl = df[bl_key].clip(lower=1.0)
        df['score_baseline'] = np.exp(np.log(vals_bl).mean(axis=1)).round(1)
        df['delta_score'] = (df['score'] - df['score_baseline']).round(1)

        # Deltas for key variables
        df['c_agb_cci_delta'] = (df['c_agb_cci'] - df['c_agb_cci_baseline']).round(1)
        df['c_total_carbon_delta'] = (df['c_total_carbon'] - df['c_total_carbon_baseline']).round(1)
        df['c_npp_delta'] = (df['c_npp'] - df['c_npp_baseline']).round(1)

        print(f"  Baseline score: mean={df['score_baseline'].mean():.1f}")
        print(f"  Delta score: mean={df['delta_score'].mean():.2f}, std={df['delta_score'].std():.2f}")
        for col in ['c_agb_cci_delta', 'c_npp_delta', 'c_standing_tc_delta', 'c_loss_rate_delta']:
            if col in df.columns:
                print(f"  {col}: mean={df[col].mean():.2f}, std={df[col].std():.2f}")
    else:
        print(f"\n  SKIP temporal: {temporal_raster} not found")

    # ── PCA + k-means typology ────────────────────────────────────────
    print("\nPCA + k-means clustering...")

    cluster_cols = ['c_agb_cci', 'c_total_carbon', 'c_npp', 'c_gross_emissions', 'c_net_flux']
    available = [c for c in cluster_cols if c in df.columns and df[c].notna().sum() > 100]

    X = df[available].dropna()
    valid_idx = X.index

    if len(X) > 100:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        pca = PCA(n_components=min(3, len(available)))
        X_pca = pca.fit_transform(X_scaled)
        print(f"  PCA variance: {pca.explained_variance_ratio_.round(3)}")

        k_min, k_max = [int(x) for x in args.k_range.split(',')]
        best_k, best_sil = 4, -1
        for k in range(k_min, k_max + 1):
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = km.fit_predict(X_pca)
            sil = silhouette_score(X_pca, labels, sample_size=min(10000, len(X_pca)), random_state=42)
            print(f"    k={k}: silhouette={sil:.3f}")
            if sil > best_sil:
                best_sil = sil
                best_k = k

        km_final = KMeans(n_clusters=best_k, n_init=10, random_state=42)
        labels = km_final.fit_predict(X_pca)
        df.loc[valid_idx, 'type'] = labels + 1

        # Generate labels
        type_labels = {}
        for t in sorted(df['type'].dropna().unique()):
            mask = df['type'] == t
            agb_mean = df.loc[mask, 'c_agb_raw'].mean()
            tc_mean = df.loc[mask, 'c_total_carbon_raw'].mean()
            flux_mean = df.loc[mask, 'c_net_flux_raw'].mean()
            n_type = mask.sum()

            if agb_mean > 150:
                base = 'Selva alta, alto stock de carbono'
            elif agb_mean > 80:
                base = 'Bosque secundario o plantacion'
            elif agb_mean > 30:
                base = 'Mosaico agro-forestal'
            else:
                base = 'Bajo stock, uso agropecuario'

            if base in type_labels.values():
                if flux_mean > 5:
                    base += ', emisor neto'
                elif flux_mean < -5:
                    base += ', sumidero neto'
                else:
                    base += f' ({tc_mean:.0f} tC/ha)'

            type_labels[t] = base
            print(f"    Type {int(t)}: {base} (n={n_type:,}, "
                  f"AGB={agb_mean:.0f} Mg/ha, TC={tc_mean:.0f} tC/ha)")

        df['type_label'] = df['type'].map(type_labels)

        pca_df = pd.DataFrame(X_pca[:, :2], index=valid_idx, columns=['pca_1', 'pca_2'])
        df = df.join(pca_df)

    # ── Output ────────────────────────────────────────────────────────
    out_cols = [
        'h3index', 'score', 'score_baseline', 'delta_score',
        'type', 'type_label', 'pca_1', 'pca_2',
        # Scored (percentile rank 0-100)
        'c_agb_cci', 'c_agb_cci_baseline', 'c_agb_cci_delta',
        'c_agb_gedi', 'c_total_carbon', 'c_total_carbon_baseline', 'c_total_carbon_delta',
        'c_soc', 'c_gross_emissions', 'c_gross_removals', 'c_net_flux',
        'c_npp', 'c_npp_baseline', 'c_npp_delta',
        'c_standing_tc_current', 'c_standing_tc_baseline', 'c_standing_tc_delta',
        'c_loss_rate_current', 'c_loss_rate_baseline', 'c_loss_rate_delta',
        # Raw physical units
        'c_agb_raw', 'c_agb_raw_baseline', 'c_agb_gedi',
        'c_total_carbon_raw', 'c_total_carbon_raw_baseline',
        'c_soc_tcha', 'c_emissions_raw', 'c_removals_raw',
        'c_net_flux_raw', 'c_npp_raw',
        'c_economic_value', 'c_gedi_se',
    ]
    # Deduplicate and filter to existing columns
    seen = set()
    final_cols = []
    for c in out_cols:
        if c not in seen and c in df.columns:
            final_cols.append(c)
            seen.add(c)

    output = df[final_cols].dropna(subset=['score'])
    os.makedirs(t_dir, exist_ok=True)
    output.to_parquet(output_path, index=False)

    elapsed = time.time() - t0
    size_kb = os.path.getsize(output_path) / 1024
    print(f"\n{'=' * 60}")
    print(f"  Output: {output_path}")
    print(f"  Rows: {len(output):,}, Size: {size_kb:.0f} KB, Columns: {len(final_cols)}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"{'=' * 60}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
