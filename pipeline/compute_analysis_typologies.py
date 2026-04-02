"""
PCA + k-means typology for each satellite analysis.

Same methodology as compute_territorial_classification.py but applied
per-analysis: each of the 13 satellite analyses gets its own PCA + k-means
clustering on its 5-9 component variables.

Replaces score (0-100) with type (categorical 1-k) + type_label (string).

Usage:
  python pipeline/compute_analysis_typologies.py
  python pipeline/compute_analysis_typologies.py --only environmental_risk,green_capital
  python pipeline/compute_analysis_typologies.py --k 4
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

ALL_ANALYSES = [
    "environmental_risk", "climate_comfort", "green_capital",
    "change_pressure", "location_value", "agri_potential",
    "forest_health", "forestry_aptitude",
    "territorial_gap", "health_access", "education_gap", "land_use",
    "territorial_scores",
]


def auto_label(cluster_means, global_means, var_names, analysis_id, used_labels=None):
    """Generate an interpretive label based on the top 2 most deviated variables."""
    deviation = cluster_means - global_means
    abs_dev = np.abs(deviation)
    sorted_idx = np.argsort(abs_dev)[::-1]

    def clean(v):
        return v.replace("c_", "").replace("frac_", "")

    top = sorted_idx[0]
    d1 = "alto" if deviation[top] > 0 else "bajo"
    label = f"{clean(var_names[top])} {d1}"

    # If label already used, add second variable to disambiguate
    if used_labels and label in used_labels and len(sorted_idx) > 1:
        sec = sorted_idx[1]
        d2 = "alto" if deviation[sec] > 0 else "bajo"
        label = f"{clean(var_names[top])} {d1}, {clean(var_names[sec])} {d2}"

    return label


PARQUET_NAMES = {
    'territorial_scores': 'overture_scores',
}

def process_analysis(analysis_id, fixed_k=None, k_range=(3, 5)):
    """Run PCA + k-means on a single analysis."""
    parquet_name = PARQUET_NAMES.get(analysis_id, f"sat_{analysis_id}")
    path = os.path.join(OUTPUT_DIR, f"{parquet_name}.parquet")
    if not os.path.exists(path):
        print(f"  SKIP {analysis_id}: file not found")
        return None

    print(f"\n{'=' * 60}")
    print(f"  {analysis_id}")
    print(f"{'=' * 60}")

    df = pd.read_parquet(path)
    n_total = len(df)

    # Extract component columns (exclude metadata and temporal)
    skip = {'h3index', 'score', 'score_baseline', 'delta_score',
            'type', 'type_label', 'pca_1', 'pca_2', 'pca_3',
            'territorial_type'}
    comp_cols = [c for c in df.columns
                 if c not in skip
                 and not c.endswith('_baseline')
                 and not c.endswith('_delta')]

    # Exclude 100% NaN columns
    valid_cols = [c for c in comp_cols if not df[c].isna().all()]
    dropped = set(comp_cols) - set(valid_cols)
    if dropped:
        print(f"  Excluded (100% NaN): {dropped}")

    print(f"  Variables ({len(valid_cols)}): {valid_cols}")

    # Impute remaining NaN with percentile 5
    nan_counts = {c: int(df[c].isna().sum()) for c in valid_cols if df[c].isna().any()}
    if nan_counts:
        for col, n in nan_counts.items():
            p5 = df[col].quantile(0.05)
            df[col] = df[col].fillna(p5)
        print(f"  Imputed NaN: {nan_counts}")

    # Standardize
    X = df[valid_cols].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # PCA
    pca = PCA()
    X_pca = pca.fit_transform(X_scaled)
    cumvar = np.cumsum(pca.explained_variance_ratio_)
    n_comp = max(2, int(np.argmax(cumvar >= 0.80)) + 1)
    n_comp = min(n_comp, len(valid_cols))

    print(f"  PCA: {n_comp} components for {cumvar[n_comp-1]*100:.0f}% variance")
    for i in range(min(3, len(pca.explained_variance_ratio_))):
        print(f"    PC{i+1}: {pca.explained_variance_ratio_[i]*100:.1f}%")

    X_pca_reduced = X_pca[:, :n_comp]

    # K-means evaluation
    k_values = [fixed_k] if fixed_k else list(range(k_range[0], k_range[1] + 1))
    results = []

    for k in k_values:
        km = KMeans(n_clusters=k, random_state=42, n_init=20, max_iter=500)
        labels = km.fit_predict(X_pca_reduced)
        sil = silhouette_score(X_pca_reduced, labels, sample_size=min(50000, len(X_pca_reduced)))
        ch = calinski_harabasz_score(X_pca_reduced, labels)
        results.append({'k': k, 'silhouette': sil, 'calinski_harabasz': ch,
                        'labels': labels, 'inertia': km.inertia_})
        print(f"    k={k}: silhouette={sil:.4f}, CH={ch:.0f}")

    best = max(results, key=lambda r: r['silhouette'])
    k_opt = best['k']
    labels = best['labels']
    print(f"  Selected k={k_opt} (silhouette={best['silhouette']:.4f})")

    # Characterize clusters and generate labels
    global_means = df[valid_cols].mean().values
    type_labels = {}

    print(f"\n  Cluster profiles:")
    used_labels = set()
    for c in range(k_opt):
        mask = labels == c
        count = mask.sum()
        pct = count / n_total * 100
        cluster_means = df.loc[mask, valid_cols].mean().values
        label = auto_label(cluster_means, global_means, valid_cols, analysis_id, used_labels)
        used_labels.add(label)
        type_labels[c + 1] = label

        print(f"    Type {c+1} ({count:,}, {pct:.0f}%): {label}")
        deviation = cluster_means - global_means
        sorted_idx = np.argsort(np.abs(deviation))[::-1][:3]
        for idx in sorted_idx:
            d = deviation[idx]
            print(f"      {valid_cols[idx]}: {cluster_means[idx]:.1f} ({d:+.1f})")

    # Build output dataframe — preserve original continuous score (0-100)
    score_col = 'score' if 'score' in df.columns else None
    result = df[['h3index', score_col]].copy() if score_col else df[['h3index']].copy()
    result['type'] = labels + 1
    result['type_label'] = result['type'].map(type_labels)
    result['pca_1'] = X_pca[:, 0]
    result['pca_2'] = X_pca[:, 1] if X_pca.shape[1] > 1 else 0.0

    for col in valid_cols:
        result[col] = df[col].values

    # Overwrite parquet
    result.to_parquet(path, index=False)
    size_kb = os.path.getsize(path) / 1024
    print(f"\n  Output: {path} ({size_kb:.0f} KB, {len(result):,} rows)")

    return {
        'analysis': analysis_id,
        'k': k_opt,
        'silhouette': round(float(best['silhouette']), 4),
        'calinski_harabasz': round(float(best['calinski_harabasz']), 0),
        'n_hexagons': len(result),
        'n_vars': len(valid_cols),
        'variables': valid_cols,
        'pca_variance': [round(float(v), 4) for v in pca.explained_variance_ratio_[:5]],
        'type_labels': type_labels,
        'type_distribution': {str(t): int((labels == (t-1)).sum()) for t in range(1, k_opt+1)},
    }


def main():
    parser = argparse.ArgumentParser(description="PCA + k-means typology per analysis")
    parser.add_argument("--only", default=None, help="Comma-separated analysis IDs")
    parser.add_argument("--k", type=int, default=None, help="Fixed k for all analyses")
    parser.add_argument("--k-range", default="3,5", help="Range of k to evaluate")
    args = parser.parse_args()

    analyses = ALL_ANALYSES
    if args.only:
        analyses = [a.strip() for a in args.only.split(",")]

    k_range = tuple(int(x) for x in args.k_range.split(","))
    t0 = time.time()

    print("=" * 60)
    print(f"  PCA + k-means Typology Pipeline")
    print(f"  Analyses: {len(analyses)}")
    print("=" * 60)

    all_meta = []
    for aid in analyses:
        meta = process_analysis(aid, fixed_k=args.k, k_range=k_range)
        if meta:
            all_meta.append(meta)

    # Save metadata
    meta_path = os.path.join(OUTPUT_DIR, "analysis_typologies_metadata.json")
    with open(meta_path, 'w') as f:
        json.dump(all_meta, f, indent=2)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Processed {len(all_meta)} analyses in {elapsed:.0f}s")
    for m in all_meta:
        print(f"    {m['analysis']}: k={m['k']}, sil={m['silhouette']:.3f}, vars={m['n_vars']}")
    print(f"  Metadata: {meta_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    sys.exit(main() or 0)
