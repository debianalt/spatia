"""
Split overture_scores.parquet into per-department parquets + summary JSON.

Uses the same spatial assignment logic as split_flood_by_dpto.py:
dissolves radio geometries into department polygons, then assigns each
hex centroid to a department via point-in-polygon.

Usage:
  python pipeline/split_scores_by_dpto.py

Output:
  pipeline/output/scores_dpto/overture_scores_{DPTO}.parquet  (x17)
  src/lib/data/scores_dept_summary.json
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
DPTO_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "scores_dpto")
SRC_DATA_DIR = os.path.join(SCRIPT_DIR, "..", "src", "lib", "data")

SCORES_PATH = os.path.join(OUTPUT_DIR, "overture_scores.parquet")
RADIOS_PATH = os.path.join(OUTPUT_DIR, "radios_misiones.parquet")
RADIO_STATS_PATH = os.path.join(OUTPUT_DIR, "radio_stats_master.parquet")

SCORE_COLS = [
    "paving_index", "urban_consolidation", "service_access",
    "commercial_vitality", "road_connectivity", "building_mix",
    "urbanization", "water_exposure",
]

COMPONENT_COLS = [
    "building_count", "n_paved", "n_unpaved", "place_count",
    "segment_count", "water_kring_total",
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


def assign_hexes_to_depts(scores: pd.DataFrame, dept_polys: dict) -> pd.DataFrame:
    """Assign each hex to a department via point-in-polygon, then nearest for unmatched."""
    print("Assigning hexes to departments spatially...")

    prepared = {dpto: prep(poly) for dpto, poly in dept_polys.items()}
    dpto_list = list(dept_polys.keys())

    assignments = {}
    unassigned_pts = {}
    total = len(scores)

    for i, h3index in enumerate(scores["h3index"]):
        if i % 50000 == 0 and i > 0:
            print(f"  Phase 1: {i}/{total} ({len(assignments)} assigned)...")

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

    print(f"  Phase 1 (exact): {len(assignments)}/{total} assigned, {len(unassigned_pts)} unassigned")

    if unassigned_pts:
        print(f"  Phase 2: assigning {len(unassigned_pts)} hexes to nearest department...")
        for i, (h3index, pt) in enumerate(unassigned_pts.items()):
            if i % 10000 == 0 and i > 0:
                print(f"    {i}/{len(unassigned_pts)}...")
            min_dist = float("inf")
            best_dpto = None
            for dpto, poly in dept_polys.items():
                d = poly.distance(pt)
                if d < min_dist:
                    min_dist = d
                    best_dpto = dpto
            if best_dpto:
                assignments[h3index] = best_dpto

    print(f"  Total assigned: {len(assignments)}/{total}")
    scores = scores.copy()
    scores["dpto"] = scores["h3index"].map(assignments)
    return scores


def safe_filename(dpto: str) -> str:
    """Convert department name to safe filename."""
    return (dpto.lower()
            .replace(" ", "_")
            .replace("á", "a").replace("é", "e")
            .replace("í", "i").replace("ó", "o")
            .replace("ú", "u").replace("ñ", "n")
            .replace("ü", "u"))


def main():
    t0 = time.time()

    if not os.path.exists(SCORES_PATH):
        print(f"ERROR: Missing scores parquet: {SCORES_PATH}")
        print("Run `python pipeline/compute_overture_scores.py` first.")
        return 1

    os.makedirs(DPTO_OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  Split Overture Scores by Department")
    print("=" * 60)

    print("\nLoading scores data...")
    scores = pd.read_parquet(SCORES_PATH)
    all_cols = ["h3index"] + SCORE_COLS + COMPONENT_COLS
    scores = scores[[c for c in all_cols if c in scores.columns]]
    print(f"  {len(scores):,} hexes loaded")

    dept_polys = build_dept_polygons()
    scores = assign_hexes_to_depts(scores, dept_polys)

    no_dpto = scores["dpto"].isna().sum()
    print(f"  Unassigned hexes: {no_dpto}")
    scores_assigned = scores.dropna(subset=["dpto"])

    # Province-wide averages
    prov_avgs = {}
    for col in SCORE_COLS:
        prov_avgs[col] = round(float(scores[col].mean()), 1)

    dptos = sorted(scores_assigned["dpto"].unique())
    print(f"\nSplitting into {len(dptos)} departments...")

    summary = []
    output_cols = ["h3index"] + SCORE_COLS + COMPONENT_COLS

    for dpto in dptos:
        subset = scores_assigned[scores_assigned["dpto"] == dpto]
        hex_data = subset[[c for c in output_cols if c in subset.columns]].drop_duplicates("h3index").reset_index(drop=True)

        safe_name = safe_filename(dpto)
        parquet_path = os.path.join(DPTO_OUTPUT_DIR, f"overture_scores_{safe_name}.parquet")
        hex_data.to_parquet(parquet_path, index=False)
        size_kb = os.path.getsize(parquet_path) / 1024

        # Compute centroid
        lats, lngs = [], []
        for h3idx in hex_data["h3index"]:
            try:
                lat, lng = h3_to_latlng(h3idx)
                lats.append(lat)
                lngs.append(lng)
            except Exception:
                pass

        centroid = [round(sum(lngs) / len(lngs), 4), round(sum(lats) / len(lats), 4)] if lats else [0, 0]

        avg_scores = {}
        for col in SCORE_COLS:
            avg_scores[col] = round(float(hex_data[col].mean()), 1)

        # Overall average of all 8 scores
        overall = round(sum(avg_scores.values()) / len(SCORE_COLS), 1)

        summary.append({
            "dpto": dpto,
            "parquetKey": safe_name,
            "avg_scores": avg_scores,
            "overall_score": overall,
            "hex_count": len(hex_data),
            "centroid": centroid,
        })

        print(f"  {dpto}: {len(hex_data):,} hexes, {size_kb:.0f}KB, overall={overall}")

    summary_data = {
        "province": {
            "total_hexes": len(scores),
            "avg_scores": prov_avgs,
        },
        "departments": sorted(summary, key=lambda d: d["overall_score"], reverse=True),
    }

    os.makedirs(SRC_DATA_DIR, exist_ok=True)
    summary_path = os.path.join(SRC_DATA_DIR, "scores_dept_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Summary saved to {summary_path}")
    print(f"  {len(dptos)} department parquets in {DPTO_OUTPUT_DIR}")
    print(f"  Total time: {elapsed:.0f}s")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
