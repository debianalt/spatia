"""
Fill limited-coverage satellite parquets to full H3 grid (319,871 hexagons).

For analyses with radio-only coverage (accessibility, economic_activity,
sociodemographic), this script extends the parquet to include ALL hexagons
from the provincial grid.  Missing rows get score=0 and type_label=
"Sin cobertura censal".

Usage:
  python pipeline/fill_h3_coverage.py
"""

import os
import sys

import pandas as pd

from config import OUTPUT_DIR

# Any full-coverage parquet to extract the complete H3 index
REFERENCE_PARQUET = os.path.join(OUTPUT_DIR, "sat_green_capital.parquet")

LIMITED_ANALYSES = ["accessibility", "economic_activity", "sociodemographic"]


def main():
    # Load full H3 index from a reference parquet (319,871 rows)
    print("Loading full H3 grid index...")
    full_h3 = pd.read_parquet(REFERENCE_PARQUET, columns=["h3index"])
    print(f"  Full grid: {len(full_h3):,} hexagons")

    for aid in LIMITED_ANALYSES:
        path = os.path.join(OUTPUT_DIR, f"sat_{aid}.parquet")
        if not os.path.exists(path):
            print(f"  SKIP {aid}: file not found")
            continue

        df = pd.read_parquet(path)
        n_before = len(df)
        print(f"\n{aid}: {n_before:,} rows -> ", end="")

        # LEFT JOIN with full grid
        merged = full_h3.merge(df, on="h3index", how="left")

        # Fill missing values per column type
        for col in merged.columns:
            if col == "h3index":
                continue
            if col == "type_label":
                merged[col] = merged[col].fillna("Sin cobertura censal")
            elif col in ("type", "territorial_type"):
                merged[col] = merged[col].fillna(0).astype(int)
            elif merged[col].dtype == "object":
                merged[col] = merged[col].fillna("")
            else:
                merged[col] = merged[col].fillna(0)

        # Overwrite parquet
        merged.to_parquet(path, index=False)
        print(f"{len(merged):,} rows (+{len(merged) - n_before:,})")

    print("\nDone. Now run:")
    print("  python pipeline/split_satellite_by_dpto.py "
          "--only accessibility,economic_activity,sociodemographic")


if __name__ == "__main__":
    main()
