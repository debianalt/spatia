"""
Aggregate radio-level data to H3 hexagons via crosswalk, then PCA + k-means.

Creates H3 parquets for radio-based analyses (sociodemographic, economic_activity,
accessibility) so they can be displayed as hex layers instead of catastro parcels.

Usage:
  python pipeline/aggregate_radio_to_h3.py
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR

CROSSWALK_PATH = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk.parquet")
RADIO_STATS_PATH = os.path.join(OUTPUT_DIR, "radio_stats_master.parquet")

ANALYSES = {
    'sociodemographic': {
        'cols': ['densidad_hab_km2', 'pct_nbi', 'pct_hacinamiento', 'pct_propietario', 'tamano_medio_hogar', 'pct_computadora'],
        # Invert: high value = less deprived → flip so high score = more deprived
        'invert': ['densidad_hab_km2', 'pct_propietario', 'pct_computadora'],
    },
    'economic_activity': {
        'cols': ['tasa_empleo', 'tasa_actividad', 'pct_universitario', 'viirs_mean_radiance', 'building_density_per_km2'],
        'invert': [],  # all vars: high = more activity (correct direction)
    },
    'accessibility': {
        'cols': ['travel_min_posadas', 'travel_min_cabecera', 'dist_nearest_hospital_km', 'dist_nearest_secundaria_km', 'dist_primary_m'],
        'invert': [],  # all vars: high = more isolated (correct direction)
    },
}

# Corrientes: census-only variables (no satellite, no accessibility)
ANALYSES_CORRIENTES = {
    'sociodemographic': {
        'cols': ['densidad_hab_km2', 'pct_nbi', 'pct_hacinamiento', 'pct_propietario', 'tamano_medio_hogar', 'pct_computadora'],
        'invert': ['densidad_hab_km2', 'pct_propietario', 'pct_computadora'],
    },
    'economic_activity': {
        'cols': ['tasa_empleo', 'tasa_actividad', 'pct_universitario'],
        'invert': [],
    },
}


def auto_label(cluster_means, global_means, var_names, used_labels=None):
    deviation = cluster_means - global_means
    abs_dev = np.abs(deviation)
    sorted_idx = np.argsort(abs_dev)[::-1]

    def clean(v):
        return v.replace('pct_', '').replace('dist_nearest_', '').replace('travel_min_', '')

    top = sorted_idx[0]
    d1 = "alto" if deviation[top] > 0 else "bajo"
    label = f"{clean(var_names[top])} {d1}"

    if used_labels and label in used_labels and len(sorted_idx) > 1:
        sec = sorted_idx[1]
        d2 = "alto" if deviation[sec] > 0 else "bajo"
        label = f"{clean(var_names[top])} {d1}, {clean(var_names[sec])} {d2}"

    return label


def main():
    parser = argparse.ArgumentParser(description="Aggregate radio stats to H3 via crosswalk + PCA/k-means")
    parser.add_argument("--territory", default="misiones", choices=["misiones", "corrientes"],
                        help="Territory to process (default: misiones)")
    args = parser.parse_args()

    if args.territory == "corrientes":
        t_dir = os.path.join(OUTPUT_DIR, "corrientes")
        crosswalk_path = os.path.join(t_dir, "h3_radio_crosswalk_corrientes.parquet")
        stats_path = os.path.join(t_dir, "radio_stats_corrientes.parquet")
        analyses = ANALYSES_CORRIENTES
        out_dir = t_dir
    else:
        t_dir = OUTPUT_DIR
        crosswalk_path = CROSSWALK_PATH
        stats_path = RADIO_STATS_PATH
        analyses = ANALYSES
        out_dir = OUTPUT_DIR

    t0 = time.time()

    print("=" * 60)
    print(f"  Aggregate Radio -> H3 + PCA + k-means [{args.territory}]")
    print("=" * 60)

    # Load crosswalk and radio stats
    print("Loading crosswalk and radio stats...")
    xwalk = pd.read_parquet(crosswalk_path)
    radio = pd.read_parquet(stats_path)

    print(f"  Crosswalk: {len(xwalk):,} rows")
    print(f"  Radio stats: {len(radio):,} rows, {len(radio.columns)} cols")

    # Merge crosswalk with radio stats
    merged = xwalk.merge(radio, on='redcode', how='inner')
    print(f"  Merged: {len(merged):,} rows")

    for aid, cfg in analyses.items():
        print(f"\n{'=' * 60}")
        print(f"  {aid}")
        print(f"{'=' * 60}")

        cols = [c for c in cfg['cols'] if c in merged.columns]
        if not cols:
            print(f"  SKIP: no columns found")
            continue

        print(f"  Variables: {cols}")

        # Weighted aggregation to H3 (vectorized: avoids slow groupby.apply)
        agg_data = []
        for col in cols:
            valid = merged[['h3index', 'weight', col]].dropna(subset=[col])
            num = (valid['weight'] * valid[col]).groupby(valid['h3index']).sum()
            den = valid['weight'].groupby(valid['h3index']).sum()
            weighted = (num / den).rename(col)
            agg_data.append(weighted)

        df = pd.concat(agg_data, axis=1).reset_index()
        df = df.rename(columns={'index': 'h3index'}) if 'index' in df.columns else df
        print(f"  Aggregated: {len(df):,} hexagons")

        # Drop NaN
        n_before = len(df)
        df = df.dropna()
        print(f"  After dropna: {len(df):,} ({n_before - len(df)} dropped)")

        if len(df) < 100:
            print(f"  SKIP: too few hexagons")
            continue

        # Standardize + PCA
        X = df[cols].values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        pca = PCA()
        X_pca = pca.fit_transform(X_scaled)
        cumvar = np.cumsum(pca.explained_variance_ratio_)
        n_comp = max(2, int(np.argmax(cumvar >= 0.80)) + 1)
        n_comp = min(n_comp, len(cols))
        print(f"  PCA: {n_comp} components, {cumvar[n_comp-1]*100:.0f}% variance")

        # K-means
        best_sil = -1
        best_k = 3
        best_labels = None
        for k in [3, 4, 5]:
            km = KMeans(n_clusters=k, random_state=42, n_init=20)
            labels = km.fit_predict(X_pca[:, :n_comp])
            sil = silhouette_score(X_pca[:, :n_comp], labels)
            print(f"    k={k}: sil={sil:.4f}")
            if sil > best_sil:
                best_sil = sil
                best_k = k
                best_labels = labels

        print(f"  Selected k={best_k} (sil={best_sil:.4f})")

        # Auto-label
        global_means = df[cols].mean().values
        type_labels = {}
        used_labels = set()
        for c in range(best_k):
            mask = best_labels == c
            cluster_means = df.loc[mask, cols].mean().values
            label = auto_label(cluster_means, global_means, cols, used_labels)
            used_labels.add(label)
            type_labels[c + 1] = label
            count = mask.sum()
            print(f"    Type {c+1}: {label} ({count:,})")

        # Build output
        result = df[['h3index']].copy()
        result['type'] = best_labels + 1
        result['type_label'] = result['type'].map(type_labels)
        result['pca_1'] = X_pca[:, 0]
        result['pca_2'] = X_pca[:, 1] if X_pca.shape[1] > 1 else 0.0
        for col in cols:
            result[col] = df[col].values

        # Save raw values before percentile transformation
        for col in cols:
            result[f'{col}_raw'] = result[col].copy()
        # Convert dist_primary_m raw to km for display consistency
        if 'dist_primary_m_raw' in result.columns:
            result['dist_primary_m_raw'] = (result['dist_primary_m_raw'] / 1000.0).round(1)

        # Normalize component cols to 0-100 percentile for petal compatibility
        for col in cols:
            valid = result[col].notna()
            if valid.sum() > 1:
                result.loc[valid, col] = result.loc[valid, col].rank(pct=True) * 100.0

        # Compute continuous score (0-100) from percentile-ranked components
        invert_cols = set(cfg.get('invert', []))
        score_cols = []
        for col in cols:
            if col in invert_cols:
                score_cols.append(100.0 - result[col])
            else:
                score_cols.append(result[col])
        result['score'] = pd.concat(score_cols, axis=1).mean(axis=1).round(1)

        out_path = os.path.join(out_dir, f"sat_{aid}.parquet")
        result.to_parquet(out_path, index=False)
        size_kb = os.path.getsize(out_path) / 1024
        print(f"  Output: {out_path} ({size_kb:.0f} KB, {len(result):,} rows)")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s")


if __name__ == "__main__":
    main()
