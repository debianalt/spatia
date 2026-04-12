"""
Split satellite score parquets into per-department parquets + summary JSON.

Reuses spatial assignment from split_scores_by_dpto.py pattern: dissolves
radio geometries into department polygons, assigns hex centroids via
point-in-polygon, splits each of the 10 satellite analyses.

Usage:
  python pipeline/split_satellite_by_dpto.py
  python pipeline/split_satellite_by_dpto.py --only environmental_risk,green_capital

Output:
  pipeline/output/sat_dpto/sat_{ID}_{DPTO}.parquet  (x17 per analysis)
  src/lib/data/sat_{ID}_dept_summary.json           (x10)
"""

import json
import os
import sys
import time

import pandas as pd

from config import OUTPUT_DIR

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DPTO_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "sat_dpto")
SRC_DATA_DIR = os.path.join(SCRIPT_DIR, "..", "src", "lib", "data")

RADIO_STATS_PATH = os.path.join(OUTPUT_DIR, "radio_stats_master.parquet")
AREAL_CROSSWALK_PATH = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk_areal.parquet")

ALL_ANALYSES = [
    "environmental_risk", "climate_comfort", "green_capital",
    "change_pressure", "location_value", "agri_potential",
    "forest_health", "forestry_aptitude",
    "service_deprivation", "territorial_isolation",
    "health_access", "education_capital", "education_flow",
    "territorial_gap", "education_gap", "land_use",
    "territorial_types", "sociodemographic", "economic_activity", "accessibility",
    "climate_vulnerability",
    "carbon_stock",
    "pm25_drivers",
    "pm25_predicted",
    "deforestation_dynamics",
    "productive_activity",
]


def build_h3_dpto_lookup() -> dict[str, str]:
    """Assign each hex to a department via the areal crosswalk (hex -> radio -> dpto).

    For each hex, picks the dpto whose radios hold the majority area share of the hex.
    Uses h3_radio_crosswalk_areal.parquet (full 319K coverage) rather than dissolving
    radio polygons — avoids geometric slivers and point-in-polygon imprecision.
    """
    print("Building hex->dpto lookup from areal crosswalk...")
    areal = pd.read_parquet(AREAL_CROSSWALK_PATH)
    radio_stats = pd.read_parquet(RADIO_STATS_PATH, columns=["redcode", "dpto"])
    areal = areal.merge(radio_stats, on="redcode", how="inner")

    # Aggregate weight per (hex, dpto), pick dpto with max weight per hex
    hex_dpto = (areal.groupby(["h3index", "dpto"])["weight"].sum()
                     .reset_index()
                     .sort_values(["h3index", "weight"], ascending=[True, False])
                     .drop_duplicates("h3index", keep="first")
                     .set_index("h3index")["dpto"]
                     .to_dict())

    print(f"  {len(hex_dpto):,} hexes mapped across {len(set(hex_dpto.values()))} dptos")
    return hex_dpto


def safe_filename(dpto: str) -> str:
    """Convert department name to safe filename."""
    return (dpto.lower()
            .replace(" ", "_")
            .replace("á", "a").replace("é", "e")
            .replace("í", "i").replace("ó", "o")
            .replace("ú", "u").replace("ñ", "n")
            .replace("ü", "u"))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Split satellite parquets by department")
    parser.add_argument("--only", default=None, help="Comma-separated analysis IDs")
    args = parser.parse_args()

    analyses = ALL_ANALYSES
    if args.only:
        analyses = [a for a in args.only.split(",") if a in ALL_ANALYSES]

    t0 = time.time()

    print("=" * 60)
    print("  Split Satellite Scores by Department")
    print(f"  Analyses: {len(analyses)}")
    print("=" * 60)

    os.makedirs(DPTO_OUTPUT_DIR, exist_ok=True)
    os.makedirs(SRC_DATA_DIR, exist_ok=True)

    # Build hex->dpto lookup once from areal crosswalk (full-coverage dasymetric assignment)
    h3_dpto = build_h3_dpto_lookup()

    # Process each analysis
    for analysis_id in analyses:
        parquet_path = os.path.join(OUTPUT_DIR, f"sat_{analysis_id}.parquet")
        if not os.path.exists(parquet_path):
            print(f"\n  SKIP {analysis_id}: {parquet_path} not found")
            continue

        print(f"\nSplitting {analysis_id}...")
        df = pd.read_parquet(parquet_path)
        df["dpto"] = df["h3index"].map(h3_dpto)

        no_dpto = df["dpto"].isna().sum()
        df_assigned = df.dropna(subset=["dpto"])

        # Province averages
        score_col = "score" if "score" in df.columns else "territorial_type"
        component_cols = [c for c in df.columns if c not in ("h3index", "score", "territorial_type", "dpto")]
        prov_avg = round(float(df[score_col].mean()), 1)

        dptos = sorted(df_assigned["dpto"].unique())
        summary_depts = []

        for dpto in dptos:
            subset = df_assigned[df_assigned["dpto"] == dpto]
            out_cols = ["h3index", score_col] + component_cols
            hex_data = subset[out_cols].reset_index(drop=True)

            safe_name = safe_filename(dpto)
            out_path = os.path.join(DPTO_OUTPUT_DIR, f"sat_{analysis_id}_{safe_name}.parquet")
            hex_data.to_parquet(out_path, index=False)

            # Centroid
            lats, lngs = [], []
            for h3idx in hex_data["h3index"].head(500):  # sample for speed
                try:
                    lat, lng = h3_to_latlng(h3idx)
                    lats.append(lat)
                    lngs.append(lng)
                except Exception:
                    pass
            centroid = [round(sum(lngs) / len(lngs), 4),
                        round(sum(lats) / len(lats), 4)] if lats else [0, 0]

            avg_score = round(float(hex_data[score_col].mean()), 1)
            summary_depts.append({
                "dpto": dpto,
                "parquetKey": safe_name,
                "avg_score": avg_score,
                "hex_count": len(hex_data),
                "centroid": centroid,
            })

        summary_data = {
            "province": {
                "total_hexes": len(df),
                "avg_score": prov_avg,
                "unassigned": int(no_dpto),
            },
            "departments": sorted(summary_depts, key=lambda d: d["avg_score"], reverse=True),
        }

        summary_path = os.path.join(SRC_DATA_DIR, f"sat_{analysis_id}_dept_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)

        print(f"  {len(dptos)} depts, {len(df_assigned):,} hexes, "
              f"unassigned={no_dpto}, avg_score={prov_avg}")

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Done in {elapsed:.0f}s")
    print(f"  Output: {DPTO_OUTPUT_DIR}")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
