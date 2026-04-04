"""
Process MapBiomas GeoTIFF to H3 hexagon fractions.

Reads the exported MapBiomas classification raster and computes
per-hexagon fraction of each simplified land cover class.

Output replaces sat_land_use.parquet with MapBiomas-derived fractions
that distinguish native forest from plantation forestry.

Usage:
  python pipeline/process_mapbiomas_to_h3.py
  python pipeline/process_mapbiomas_to_h3.py --input mapbiomas_misiones_2023.tif
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

from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR

HEXAGONS_PATH = os.path.join(OUTPUT_DIR, "hexagons-lite.geojson")

# MapBiomas class remapping
REMAP = {
    3: 'native_forest', 4: 'native_forest', 5: 'native_forest',
    9: 'plantation',
    11: 'wetland', 12: 'grassland', 13: 'grassland',
    15: 'pasture',
    18: 'agriculture', 19: 'agriculture', 20: 'agriculture',
    21: 'mosaic',
    24: 'urban', 25: 'bare', 29: 'bare', 30: 'bare',
    26: 'water', 33: 'water',
}

CLASSES = ['native_forest', 'plantation', 'pasture', 'agriculture',
           'mosaic', 'wetland', 'grassland', 'urban', 'water', 'bare']


def compute_fractions(src, geom):
    """Compute fraction of each MapBiomas class within a polygon."""
    bounds = geom.bounds
    try:
        window = from_bounds(*bounds, transform=src.transform)
        data = src.read(1, window=window)
        if data.size == 0:
            return None
        transform = rasterio.windows.transform(window, src.transform)
        mask = geometry_mask([geom], out_shape=data.shape, transform=transform, invert=True)
        pixels = data[mask]
        if len(pixels) == 0:
            return None

        total = len(pixels)
        fractions = {}
        for cls in CLASSES:
            # Count pixels that map to this class
            count = sum(1 for p in pixels if REMAP.get(int(p), 'other') == cls)
            fractions[f'frac_{cls}'] = round(count / total, 4)

        return fractions
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description='Process MapBiomas to H3')
    parser.add_argument('--input', default=None, help='Input GeoTIFF path')
    args = parser.parse_args()

    # Find input raster
    if args.input:
        raster_path = args.input
    else:
        # Look for mapbiomas_misiones_*.tif in output
        candidates = [f for f in os.listdir(OUTPUT_DIR) if f.startswith('mapbiomas_misiones') and f.endswith('.tif')]
        if not candidates:
            print("No MapBiomas raster found. Run gee_export_mapbiomas.py first.")
            return
        raster_path = os.path.join(OUTPUT_DIR, sorted(candidates)[-1])

    print(f"Input: {raster_path}")

    # Load hexagons
    print("Loading hexagon grid...")
    with open(HEXAGONS_PATH, 'r') as f:
        hexgrid = json.load(f)
    features = hexgrid['features']
    print(f"  {len(features):,} hexagons")

    # Process
    t0 = time.time()
    results = []

    with rasterio.open(raster_path) as src:
        print(f"Raster: {src.width}x{src.height}, CRS={src.crs}")

        for fi, feat in enumerate(features):
            if fi % 50000 == 0 and fi > 0:
                elapsed = time.time() - t0
                rate = fi / elapsed
                eta = (len(features) - fi) / rate / 60
                print(f"  {fi:,}/{len(features):,} ({rate:.0f} hex/s, ETA {eta:.1f} min)")

            h3index = (feat.get("properties", {}).get("h3index")
                       or feat.get("properties", {}).get("h3_index")
                       or feat.get("id"))
            geom = shape(feat["geometry"])
            fracs = compute_fractions(src, geom)

            if fracs:
                fracs['h3index'] = h3index
                results.append(fracs)

    df = pd.DataFrame(results)
    print(f"Processed: {len(df):,} hexagons with fractions")

    # Fill missing fraction columns
    for cls in CLASSES:
        col = f'frac_{cls}'
        if col not in df.columns:
            df[col] = 0.0

    frac_cols = [f'frac_{cls}' for cls in CLASSES]

    # PCA + k-means (same pattern as other analyses)
    print("Running PCA + k-means...")
    X = df[frac_cols].values
    X_scaled = StandardScaler().fit_transform(X)

    pca = PCA()
    X_pca = pca.fit_transform(X_scaled)
    n_comp = max(2, int(np.argmax(np.cumsum(pca.explained_variance_ratio_) >= 0.80)) + 1)
    n_comp = min(n_comp, len(frac_cols))
    print(f"  PCA: {n_comp} components, {np.cumsum(pca.explained_variance_ratio_)[n_comp-1]*100:.0f}%")

    best_sil = -1
    best_k = 4
    best_labels = None
    for k in [4, 5, 6]:
        labels = KMeans(n_clusters=k, random_state=42, n_init=20).fit_predict(X_pca[:, :n_comp])
        sil = silhouette_score(X_pca[:, :n_comp], labels, sample_size=min(50000, len(X_pca)))
        print(f"  k={k}: sil={sil:.4f}")
        if sil > best_sil:
            best_sil = sil
            best_k = k
            best_labels = labels

    print(f"  Selected k={best_k}")

    # Auto-label based on dominant fraction
    global_means = df[frac_cols].mean().values
    type_labels = {}
    for c in range(best_k):
        mask = best_labels == c
        cluster_means = df.loc[mask, frac_cols].mean().values
        # Find dominant class
        dominant_idx = np.argmax(cluster_means)
        dominant_class = CLASSES[dominant_idx]
        dominant_frac = cluster_means[dominant_idx]

        READABLE = {
            'native_forest': 'Selva nativa',
            'plantation': 'Plantacion forestal',
            'pasture': 'Pastizal',
            'agriculture': 'Cultivos',
            'mosaic': 'Mosaico agropecuario',
            'wetland': 'Humedal',
            'grassland': 'Pastizal natural',
            'urban': 'Urbano',
            'water': 'Agua',
            'bare': 'Suelo desnudo',
        }
        label = READABLE.get(dominant_class, dominant_class)
        if dominant_frac < 0.4:
            label = f'Mosaico ({label})'
        type_labels[c + 1] = label
        print(f"  Type {c+1}: {label} ({mask.sum():,}, {dominant_class}={dominant_frac:.2f})")

    # Build output
    result = df[['h3index']].copy()
    result['type'] = best_labels + 1
    result['type_label'] = result['type'].map(type_labels)
    result['score'] = result['type'].astype(float)
    result['pca_1'] = X_pca[:, 0]
    result['pca_2'] = X_pca[:, 1]
    for col in frac_cols:
        # Scale to 0-100 for petal compatibility
        result[col] = (df[col] * 100).round(1)

    out_path = os.path.join(OUTPUT_DIR, "sat_land_use.parquet")
    result.to_parquet(out_path, index=False)
    print(f"Output: {out_path} ({os.path.getsize(out_path)/1024:.0f} KB, {len(result):,} rows)")


if __name__ == '__main__':
    main()
