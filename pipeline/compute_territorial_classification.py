"""
Territorial classification via PCA + metabolic clustering.

Phase A: Assemble all satellite score parquets into a single matrix.
Phase B: Exploratory PCA on the full variable space (factorial structure).
Phase C: Select 15 metabolic variables and cluster via Ward + k-means.
Phase D: Evaluate clusters, characterise types, output parquet.

Usage:
  python pipeline/compute_territorial_classification.py
  python pipeline/compute_territorial_classification.py --k 7
  python pipeline/compute_territorial_classification.py --k-range 5,8
  python pipeline/compute_territorial_classification.py --territory corrientes
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
from sklearn.metrics import silhouette_score, calinski_harabasz_score
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR

# Set by main() for non-Misiones territories; load_and_merge() reads this.
_INPUT_DIR = OUTPUT_DIR

# ── Source definitions ────────────────────────────────────────────────────────
# Each entry: (parquet_stem, prefix, columns_to_load)
# prefix disambiguates duplicate column names across analyses.

SOURCES = [
    # Solo cargar las fuentes que alimentan METABOLIC_VARS — el inner-join
    # contra fuentes no-usadas (incluso si están a hex-level) introduce overhead
    # innecesario y, peor, fuerza el universo de hexes al mínimo común denominador
    # (ej: sat_health_access tiene 68K hex censal y reducía el output a 65K).
    ('sat_environmental_risk', 'envr', ['score', 'c_deforest', 'c_thermal_amp', 'c_slope', 'c_hand']),
    ('sat_climate_comfort', 'clim', ['score', 'c_heat_day', 'c_heat_night', 'c_precipitation', 'c_frost', 'c_water_stress']),
    ('sat_green_capital', 'gree', ['score', 'c_ndvi', 'c_treecover', 'c_npp', 'c_lai', 'c_vcf']),
    ('sat_change_pressure', 'chng', ['score', 'c_viirs_trend', 'c_ghsl_change', 'c_hansen_loss', 'c_ndvi_trend']),
    ('sat_agri_potential', 'agri', ['score', 'c_soc', 'c_ph_optimal', 'c_clay', 'c_precipitation', 'c_gdd', 'c_slope']),
    # Fuentes no usadas en METABOLIC_VARS — no cargar:
    # sat_forest_health, sat_forestry_aptitude, sat_territorial_gap,
    # sat_education_gap (todas hex-level pero innecesarias)
    # sat_health_access, sat_location_value, sat_land_use (censal-limited / sin raster)
]

# ── Metabolic variable selection (15 vars, canonical sources) ─────────────────
# (prefixed_col, short_name, description)
METABOLIC_VARS = [
    ('gree_c_npp', 'm_npp', 'Net Primary Productivity'),
    ('gree_c_ndvi', 'm_ndvi', 'Vegetation index'),
    ('gree_c_treecover', 'm_treecover', 'Tree cover (Hansen 2000)'),
    # DROP land_*: sat_land_use no es hex-level (sin raster local)
    # ('land_frac_trees', 'm_frac_trees', 'Tree cover fraction (DW)'),
    # ('land_frac_crops', 'm_frac_crops', 'Crop fraction'),
    # ('land_frac_built', 'm_frac_built', 'Built fraction'),
    # ('land_frac_grass', 'm_frac_grass', 'Grass/pasture fraction'),
    ('envr_c_deforest', 'm_deforest', 'Deforestation loss'),
    ('chng_c_hansen_loss', 'm_hansen_loss', 'Cumulative forest loss'),
    ('envr_c_thermal_amp', 'm_thermal_amp', 'Thermal amplitude'),
    ('chng_c_viirs_trend', 'm_viirs_trend', 'Urbanisation trend'),
    ('chng_c_ghsl_change', 'm_ghsl_change', 'Built-up expansion'),
    # DROP locv_*: sat_location_value es 68K rows (censal-limited)
    # ('locv_c_nightlights', 'm_nightlights', 'Night-time radiance'),
    ('agri_c_gdd', 'm_gdd', 'Growing degree days'),
    ('clim_c_precipitation', 'm_precipitation', 'Annual precipitation'),
]


def load_and_merge():
    """Load all satellite parquets and merge into a single matrix with prefixed columns."""
    print("=" * 70)
    print("  PHASE A: Data Assembly")
    print("=" * 70)

    base = None
    total_cols = 0

    for stem, prefix, cols in SOURCES:
        path = os.path.join(_INPUT_DIR, f"{stem}.parquet")
        if not os.path.exists(path):
            print(f"  SKIP {stem}: file not found")
            continue

        df = pd.read_parquet(path)
        available = [c for c in cols if c in df.columns]
        df = df[['h3index'] + available]

        # Rename with prefix to disambiguate
        rename = {}
        for c in available:
            rename[c] = f"{prefix}_{c}"
        df = df.rename(columns=rename)

        n_new = len(available)
        total_cols += n_new

        if base is None:
            base = df
        else:
            base = base.merge(df, on='h3index', how='inner')

        print(f"  {stem}: {len(df):,} rows, {n_new} cols ->merged: {len(base):,} rows")

    # Drop columns that are 100% NaN
    null_cols = [c for c in base.columns if c != 'h3index' and base[c].isna().all()]
    if null_cols:
        print(f"\n  Dropping {len(null_cols)} all-NaN columns: {null_cols}")
        base = base.drop(columns=null_cols)

    feature_cols = [c for c in base.columns if c != 'h3index']
    print(f"\n  Total: {len(base):,} hexagons, {len(feature_cols)} feature columns")

    # Impute NaN with 5th percentile per column (urban hexagons missing vegetation signal)
    n_nan_before = base[feature_cols].isna().sum().sum()
    nan_cols = {c: int(base[c].isna().sum()) for c in feature_cols if base[c].isna().any()}
    if nan_cols:
        print(f"\n  Imputing NaN ({n_nan_before:,} cells across {len(nan_cols)} columns):")
        for col, n in sorted(nan_cols.items(), key=lambda x: -x[1]):
            p5 = base[col].quantile(0.05)
            base[col] = base[col].fillna(p5)
            print(f"    {col}: {n:,} NaN -> filled with p5={p5:.1f}")
    print(f"  After imputation: {len(base):,} rows, 0 NaN")

    return base, feature_cols


def run_pca(base, feature_cols, n_components_target=0.80):
    """Exploratory PCA on the full variable space."""
    print("\n" + "=" * 70)
    print("  PHASE B: Exploratory PCA (full variable space)")
    print("=" * 70)

    X = base[feature_cols].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    pca = PCA()
    X_pca = pca.fit_transform(X_scaled)

    # Explained variance
    cumvar = np.cumsum(pca.explained_variance_ratio_)
    n_80 = int(np.argmax(cumvar >= n_components_target)) + 1

    print(f"\n  Total components: {len(pca.explained_variance_ratio_)}")
    print(f"  Components for {n_components_target*100:.0f}% variance: {n_80}")
    print(f"\n  Variance explained by first 10 axes:")
    for i in range(min(10, len(pca.explained_variance_ratio_))):
        bar = "#" * int(pca.explained_variance_ratio_[i] * 100)
        print(f"    PC{i+1:2d}: {pca.explained_variance_ratio_[i]*100:5.1f}%  cumul: {cumvar[i]*100:5.1f}%  {bar}")

    # Loadings: top variables per axis
    print(f"\n  Top loadings per axis (first 5 axes):")
    for ax in range(min(5, n_80)):
        loadings = pca.components_[ax]
        indices = np.argsort(np.abs(loadings))[::-1][:5]
        print(f"\n    PC{ax+1} ({pca.explained_variance_ratio_[ax]*100:.1f}%):")
        for idx in indices:
            sign = "+" if loadings[idx] > 0 else "-"
            print(f"      {sign}{abs(loadings[idx]):.3f}  {feature_cols[idx]}")

    return X_pca, pca, scaler, n_80


def run_metabolic_clustering(base, k_range=(5, 8), fixed_k=None):
    """Cluster hexagons using 15 metabolic variables."""
    print("\n" + "=" * 70)
    print("  PHASE C: Metabolic Clustering")
    print("=" * 70)

    # Extract metabolic variables
    meta_cols = []
    short_names = []
    descriptions = []
    for prefixed, short, desc in METABOLIC_VARS:
        if prefixed not in base.columns:
            print(f"  WARN: {prefixed} not found, skipping")
            continue
        meta_cols.append(prefixed)
        short_names.append(short)
        descriptions.append(desc)

    print(f"  Variables: {len(meta_cols)}")
    for pc, sn, desc in zip(meta_cols, short_names, descriptions):
        print(f"    {sn:16s} <-{pc:28s}  ({desc})")

    X_meta = base[meta_cols].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_meta)

    # Evaluate k range
    if fixed_k:
        k_values = [fixed_k]
    else:
        k_values = list(range(k_range[0], k_range[1] + 1))

    print(f"\n  Evaluating k = {k_values}")
    results = []

    for k in k_values:
        km = KMeans(n_clusters=k, random_state=42, n_init=20, max_iter=500)
        labels = km.fit_predict(X_scaled)
        sil = silhouette_score(X_scaled, labels, sample_size=min(50000, len(X_scaled)))
        ch = calinski_harabasz_score(X_scaled, labels)
        results.append({'k': k, 'silhouette': sil, 'calinski_harabasz': ch,
                        'model': km, 'labels': labels, 'inertia': km.inertia_})
        print(f"    k={k}: silhouette={sil:.4f}, CH={ch:.0f}, inertia={km.inertia_:.0f}")

    # Select best k by silhouette
    best = max(results, key=lambda r: r['silhouette'])
    k_opt = best['k']
    print(f"\n  Selected k={k_opt} (silhouette={best['silhouette']:.4f})")

    return best, meta_cols, short_names, descriptions, X_scaled


def characterise_clusters(base, labels, meta_cols, short_names, k):
    """Print mean profile of each cluster vs global mean."""
    print("\n" + "=" * 70)
    print("  PHASE D: Cluster Characterisation")
    print("=" * 70)

    df = base[meta_cols].copy()
    df['cluster'] = labels

    global_means = df[meta_cols].mean()
    profiles = []

    for c in range(k):
        mask = df['cluster'] == c
        count = mask.sum()
        pct = count / len(df) * 100
        cluster_means = df.loc[mask, meta_cols].mean()
        deviation = cluster_means - global_means

        print(f"\n  Cluster {c+1} ({count:,} hexagons, {pct:.1f}%)")
        print(f"  {'Variable':16s} {'Mean':>8s} {'Global':>8s} {'Dev':>8s}")
        print(f"  {'-'*44}")

        # Sort by absolute deviation
        sorted_idx = np.argsort(np.abs(deviation.values))[::-1]
        for idx in sorted_idx:
            col = meta_cols[idx]
            sn = short_names[idx]
            m = cluster_means.iloc[idx]
            g = global_means.iloc[idx]
            d = deviation.iloc[idx]
            marker = "^" if d > 10 else ("v" if d < -10 else " ")
            print(f"  {sn:16s} {m:8.1f} {g:8.1f} {d:+8.1f} {marker}")

        profiles.append({
            'cluster': c + 1,
            'count': int(count),
            'pct': round(pct, 1),
            'means': {short_names[i]: round(float(cluster_means.iloc[i]), 1)
                      for i in range(len(meta_cols))},
        })

    return profiles


def main():
    global _INPUT_DIR

    parser = argparse.ArgumentParser(description="Territorial classification: PCA + metabolic clustering")
    parser.add_argument("--k", type=int, default=None, help="Fixed number of clusters (skip evaluation)")
    parser.add_argument("--k-range", default="5,8", help="Range of k to evaluate (min,max)")
    parser.add_argument("--territory", default="misiones", help="Territory ID (default: misiones)")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    if args.territory != "misiones":
        t_dir = os.path.join(OUTPUT_DIR, args.territory)
        _INPUT_DIR = t_dir
        if args.output_dir is None:
            args.output_dir = t_dir
    else:
        if args.output_dir is None:
            args.output_dir = OUTPUT_DIR

    t0 = time.time()

    # Phase A: Data assembly
    base, feature_cols = load_and_merge()

    # Phase B: Exploratory PCA
    X_pca, pca_model, pca_scaler, n_80 = run_pca(base, feature_cols)

    # Phase C: Metabolic clustering
    k_range = tuple(int(x) for x in args.k_range.split(","))
    best, meta_cols, short_names, descriptions, X_meta_scaled = run_metabolic_clustering(
        base, k_range=k_range, fixed_k=args.k
    )

    # Phase D: Characterisation
    k_opt = best['k']
    labels = best['labels']
    profiles = characterise_clusters(base, labels, meta_cols, short_names, k_opt)

    # ── Output ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  OUTPUT")
    print("=" * 70)

    # Build result DataFrame
    result = base[['h3index']].copy()

    # Cluster label (1-indexed for human readability)
    result['territorial_type'] = labels + 1

    # PCA coordinates (first 3 axes from full PCA)
    for i in range(min(3, X_pca.shape[1])):
        result[f'pca_{i+1}'] = X_pca[:, i]

    # Metabolic variables with short names
    for prefixed, short, _ in METABOLIC_VARS:
        if prefixed in base.columns:
            result[short] = base[prefixed].values

    # Output parquet
    out_path = os.path.join(args.output_dir, "sat_territorial_types.parquet")
    result.to_parquet(out_path, index=False)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Parquet: {out_path} ({size_kb:.0f} KB, {len(result):,} rows)")

    # Output metadata JSON
    meta = {
        'k': k_opt,
        'silhouette': round(float(best['silhouette']), 4),
        'calinski_harabasz': round(float(best['calinski_harabasz']), 0),
        'n_hexagons': len(result),
        'n_metabolic_vars': len(meta_cols),
        'metabolic_vars': [{'col': sn, 'source': pc, 'desc': desc}
                           for pc, sn, desc in METABOLIC_VARS if pc in base.columns],
        'pca_explained_variance': [round(float(v), 4) for v in pca_model.explained_variance_ratio_[:10]],
        'pca_cumulative_80pct_components': n_80,
        'cluster_profiles': profiles,
    }

    meta_path = os.path.join(args.output_dir, "territorial_types_metadata.json")
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    print(f"  Metadata: {meta_path}")

    # Summary
    print(f"\n  Cluster distribution:")
    dist = pd.Series(labels + 1).value_counts().sort_index()
    for c, n in dist.items():
        bar = "#" * int(n / len(result) * 50)
        print(f"    Type {c}: {n:>7,} ({n/len(result)*100:5.1f}%) {bar}")

    elapsed = time.time() - t0
    print(f"\n  Completed in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
