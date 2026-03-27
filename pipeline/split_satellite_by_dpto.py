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
from shapely import wkb
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.prepared import prep

from config import OUTPUT_DIR

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DPTO_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "sat_dpto")
SRC_DATA_DIR = os.path.join(SCRIPT_DIR, "..", "src", "lib", "data")

RADIOS_PATH = os.path.join(OUTPUT_DIR, "radios_misiones.parquet")
RADIO_STATS_PATH = os.path.join(OUTPUT_DIR, "radio_stats_master.parquet")

ALL_ANALYSES = [
    "environmental_risk", "climate_comfort", "green_capital",
    "change_pressure", "location_value", "agri_potential",
    "forest_health", "forestry_aptitude", "isolation_index",
    "territorial_gap", "health_access", "education_gap", "land_use",
]


def h3_to_latlng(h3index: str) -> tuple[float, float]:
    """Convert H3 index to (lat, lng)."""
    try:
        from h3 import cell_to_latlng
        return cell_to_latlng(h3index)
    except ImportError:
        pass
    try:
        import h3
        return h3.h3_to_geo(h3index)
    except (ImportError, AttributeError):
        pass
    raise ImportError("h3 library required: pip install h3")


def build_dept_polygons() -> dict[str, any]:
    """Build department polygons by dissolving radio geometries."""
    print("Building department polygons from radio geometries...")
    radios = pd.read_parquet(RADIOS_PATH)
    radio_stats = pd.read_parquet(RADIO_STATS_PATH, columns=["redcode", "dpto"])

    radios["geom"] = radios["geometry"].apply(lambda b: wkb.loads(b))
    radios = radios.merge(radio_stats, on="redcode", how="inner")

    dept_polys = {}
    for dpto, group in radios.groupby("dpto"):
        geoms = [g for g in group["geom"] if g is not None and g.is_valid]
        if geoms:
            dept_polys[dpto] = unary_union(geoms)

    print(f"  Built {len(dept_polys)} department polygons")
    return dept_polys


def build_h3_dpto_lookup(h3_indices: list[str], dept_polys: dict) -> dict[str, str]:
    """Assign each hex to a department. Returns {h3index: dpto}."""
    print(f"Assigning {len(h3_indices):,} hexes to departments...")

    prepared = {dpto: prep(poly) for dpto, poly in dept_polys.items()}
    dpto_list = list(dept_polys.keys())

    assignments = {}
    unassigned_pts = {}

    for i, h3index in enumerate(h3_indices):
        if i % 50000 == 0 and i > 0:
            print(f"  Phase 1: {i:,}/{len(h3_indices):,} ({len(assignments):,} assigned)...")

        try:
            lat, lng = h3_to_latlng(h3index)
        except Exception:
            continue

        pt = Point(lng, lat)
        found = False
        for dpto in dpto_list:
            if prepared[dpto].contains(pt):
                assignments[h3index] = dpto
                found = True
                break
        if not found:
            unassigned_pts[h3index] = pt

    print(f"  Phase 1 (exact): {len(assignments):,}/{len(h3_indices):,}, "
          f"{len(unassigned_pts):,} unassigned")

    if unassigned_pts:
        print(f"  Phase 2: nearest for {len(unassigned_pts):,} hexes...")
        for h3index, pt in unassigned_pts.items():
            min_dist = float("inf")
            best_dpto = None
            for dpto, poly in dept_polys.items():
                d = poly.distance(pt)
                if d < min_dist:
                    min_dist = d
                    best_dpto = dpto
            if best_dpto:
                assignments[h3index] = best_dpto

    print(f"  Total assigned: {len(assignments):,}/{len(h3_indices):,}")
    return assignments


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

    # Load first parquet to get H3 index list
    first_path = os.path.join(OUTPUT_DIR, f"sat_{analyses[0]}.parquet")
    if not os.path.exists(first_path):
        print(f"ERROR: Missing {first_path}")
        return 1

    first_df = pd.read_parquet(first_path, columns=["h3index"])
    h3_list = first_df["h3index"].tolist()

    # Build department lookup once
    dept_polys = build_dept_polygons()
    h3_dpto = build_h3_dpto_lookup(h3_list, dept_polys)

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
        score_col = "score"
        component_cols = [c for c in df.columns if c.startswith("c_") or c.startswith("frac_")]
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
