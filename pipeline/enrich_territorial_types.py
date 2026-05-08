"""
Enriquece sat_territorial_types.parquet con:
  - score: PCA1 normalizado min-max a 0-100 (eje dominante de variación)
  - type:  alias de territorial_type (compatibilidad con UI)
  - type_label: nombre interpretable derivado de cluster profiles

Permite que la capa pase de coloreo categórico a coloreo escalar por percentil
y que el petal chart se renderice automáticamente.

Uso:
  python pipeline/enrich_territorial_types.py
"""

import os
import sys

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR

PARQUET = os.path.join(OUTPUT_DIR, "sat_territorial_types.parquet")

# Labels derivados de cluster profiles (territorial_types_metadata.json)
LABELS = {
    1: "Bosque maduro estable",
    2: "Selva densa lluviosa",
    3: "Periurbano en expansion",
    4: "Frente de deforestacion calido",
    5: "Nucleo urbano consolidado",
    6: "Mosaico productivo lluvioso",
    7: "Suelo descubierto calido",
}


def main():
    print(f"Reading {PARQUET}...")
    df = pd.read_parquet(PARQUET)
    print(f"  {len(df):,} rows, cols: {df.columns.tolist()}")

    # 1. score: PCA1 normalizado min-max a 0-100
    pca1 = df["pca_1"].astype(float)
    pmin, pmax = pca1.min(), pca1.max()
    df["score"] = ((pca1 - pmin) / (pmax - pmin) * 100).round(1)
    print(f"  score: min={df['score'].min()}, max={df['score'].max()}, mean={df['score'].mean():.1f}")

    # 2. type: alias de territorial_type
    df["type"] = df["territorial_type"].astype(int)

    # 3. type_label: mapeado desde LABELS
    df["type_label"] = df["type"].map(LABELS)
    nan_labels = df["type_label"].isna().sum()
    if nan_labels:
        print(f"  WARNING: {nan_labels} rows with no label (unknown type values)")
        df["type_label"] = df["type_label"].fillna("Sin clasificar")

    # Reorder cols: h3index, score, type, type_label, territorial_type, pca_*, m_*
    front = ["h3index", "score", "type", "type_label", "territorial_type", "pca_1", "pca_2", "pca_3"]
    rest = [c for c in df.columns if c not in front]
    df = df[front + rest]

    # Write back
    df.to_parquet(PARQUET, index=False)
    size_kb = os.path.getsize(PARQUET) / 1024
    print(f"\nWrote {PARQUET} ({size_kb:.0f} KB, {len(df):,} rows, {len(df.columns)} cols)")
    print("Distribution:")
    print(df["type_label"].value_counts())


if __name__ == "__main__":
    main()
