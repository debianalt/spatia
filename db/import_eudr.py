"""
Import EUDR deforestation parquet into D1 seed SQL.

Reads eudr_deforestation.parquet and generates INSERT statements
for the eudr_deforestation table in Cloudflare D1.

Usage:
  python db/import_eudr.py
  python db/import_eudr.py --parquet path/to/eudr_deforestation.parquet

Then apply to D1:
  npx wrangler d1 execute spatia-db --remote --file db/seed_eudr.sql
"""

import argparse
import os
import sys

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PIPELINE_OUTPUT = os.path.join(PROJECT_ROOT, "pipeline", "output", "eudr")
DEFAULT_PARQUET = os.path.join(PIPELINE_OUTPUT, "eudr_deforestation.parquet")
OUTPUT_SQL = os.path.join(SCRIPT_DIR, "seed_eudr.sql")

COLUMNS = [
    "h3index", "province",
    "forest_cover_2020", "forest_cover_current",
    "loss_total_pct", "loss_post_2020_pct", "loss_pre_2020_pct",
    "fire_post_2020_pct", "risk_score", "deforestation_post_2020",
]


def sql_value(v):
    """Format a Python value for SQL INSERT."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "NULL"
    if isinstance(v, str):
        return f"'{v}'"
    if isinstance(v, (int, bool)):
        return str(int(v))
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def main():
    parser = argparse.ArgumentParser(description="Import EUDR parquet to D1 SQL")
    parser.add_argument("--parquet", default=DEFAULT_PARQUET, help="Input parquet path")
    parser.add_argument("--output", default=OUTPUT_SQL, help="Output SQL path")
    args = parser.parse_args()

    if not os.path.exists(args.parquet):
        print(f"Parquet not found: {args.parquet}")
        print(f"Run the EUDR pipeline first: python pipeline/run_eudr_update.py")
        return 1

    print(f"Reading {args.parquet}...")
    df = pd.read_parquet(args.parquet)
    print(f"  {len(df):,} rows, {len(df.columns)} columns")

    # Validate columns
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        print(f"  Missing columns: {missing}")
        return 1

    print(f"Writing SQL to {args.output}...")
    with open(args.output, "w", encoding="utf-8") as f:
        # Drop and recreate
        f.write("-- Auto-generated EUDR seed data. Do not edit manually.\n")
        f.write("DELETE FROM eudr_deforestation;\n\n")

        # Batch inserts (500 rows per statement for D1 efficiency)
        batch_size = 500
        col_names = ", ".join(COLUMNS)

        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i + batch_size]
            values = []
            for _, row in batch.iterrows():
                vals = ", ".join(sql_value(row[c]) for c in COLUMNS)
                values.append(f"({vals})")

            f.write(f"INSERT INTO eudr_deforestation ({col_names}) VALUES\n")
            f.write(",\n".join(values))
            f.write(";\n\n")

    size_kb = os.path.getsize(args.output) / 1024
    print(f"  Saved: {args.output} ({size_kb:.0f} KB)")
    print(f"\nApply to D1:")
    print(f"  npx wrangler d1 execute spatia-db --remote --file db/seed_eudr.sql")

    return 0


if __name__ == "__main__":
    sys.exit(main())
