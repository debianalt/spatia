"""
Split overture_scores.parquet into per-department parquets + summary JSON.

Usage:
  python pipeline/split_scores_by_dpto.py                   # Misiones
  python pipeline/split_scores_by_dpto.py --territory itapua_py

For Misiones: dissolves radio geometries into department polygons, assigns
each hex centroid to a department via point-in-polygon.

For Itapúa: uses h3_admin_crosswalk.parquet (already has distrito column).

Output (Misiones):
  pipeline/output/scores_dpto/overture_scores_{DPTO}.parquet  (x17)
  src/lib/data/scores_dept_summary.json

Output (Itapúa):
  pipeline/output/itapua_py/scores_dpto/overture_scores_{distrito}.parquet
  src/lib/data/itapua_py_scores_dept_summary.json
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

from config import OUTPUT_DIR, get_territory

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DATA_DIR = os.path.join(SCRIPT_DIR, "..", "src", "lib", "data")

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

META_COLS = ["score", "type", "type_label", "pca_1", "pca_2"]


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


def assign_hexes_itapua(scores: pd.DataFrame, crosswalk_path: str) -> tuple[pd.DataFrame, str]:
    """Assign each hex to an admin unit using the prebuilt crosswalk parquet.
    Returns (merged_df, admin_col_name) — col is 'distrito' or 'dpto' depending on crosswalk."""
    import pyarrow.parquet as pq
    schema_cols = pq.read_schema(crosswalk_path).names
    admin_col = "distrito" if "distrito" in schema_cols else "dpto"
    print(f"Assigning hexes to {admin_col}s via crosswalk...")
    crosswalk = pd.read_parquet(crosswalk_path, columns=["h3index", admin_col])
    scores = scores.merge(crosswalk, on="h3index", how="left")
    no_match = scores[admin_col].isna().sum()
    print(f"  Matched: {len(scores) - no_match:,}/{len(scores):,}, unmatched: {no_match:,}")
    return scores, admin_col


def split_and_save(scores: pd.DataFrame, admin_col: str, output_dir: str,
                   summary_path: str, dpto_key: str) -> int:
    """Split scores by admin_col, save per-unit parquets, write summary JSON."""
    os.makedirs(output_dir, exist_ok=True)

    prov_avgs = {col: round(float(scores[col].mean()), 1) for col in SCORE_COLS}

    units = sorted(scores[admin_col].dropna().unique())
    print(f"\nSplitting into {len(units)} units...")

    summary = []
    output_cols = ["h3index"] + META_COLS + SCORE_COLS + COMPONENT_COLS

    for unit in units:
        subset = scores[scores[admin_col] == unit]
        hex_data = subset[[c for c in output_cols if c in subset.columns]].drop_duplicates("h3index").reset_index(drop=True)

        safe_name = safe_filename(unit)
        parquet_path = os.path.join(output_dir, f"overture_scores_{safe_name}.parquet")
        hex_data.to_parquet(parquet_path, index=False)
        size_kb = os.path.getsize(parquet_path) / 1024

        lats, lngs = [], []
        for h3idx in hex_data["h3index"]:
            try:
                lat, lng = h3_to_latlng(h3idx)
                lats.append(lat)
                lngs.append(lng)
            except Exception:
                pass
        centroid = [round(sum(lngs) / len(lngs), 4), round(sum(lats) / len(lats), 4)] if lats else [0, 0]

        avg_scores = {col: round(float(hex_data[col].mean()), 1) for col in SCORE_COLS}
        overall = round(sum(avg_scores.values()) / len(SCORE_COLS), 1)

        summary.append({
            dpto_key: unit,
            "parquetKey": safe_name,
            "avg_scores": avg_scores,
            "overall_score": overall,
            "hex_count": len(hex_data),
            "centroid": centroid,
        })
        print(f"  {unit}: {len(hex_data):,} hexes, {size_kb:.0f}KB, overall={overall}")

    summary_data = {
        "province": {"total_hexes": len(scores), "avg_scores": prov_avgs},
        "departments": sorted(summary, key=lambda d: d["overall_score"], reverse=True),
    }
    os.makedirs(SRC_DATA_DIR, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    return len(units)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Split Overture scores by department")
    parser.add_argument("--territory", default="misiones", help="Territory ID (default: misiones)")
    args = parser.parse_args()

    t0 = time.time()

    territory = get_territory(args.territory)
    out_prefix = territory['output_prefix'].rstrip('/')
    t_dir = os.path.join(OUTPUT_DIR, out_prefix) if out_prefix else OUTPUT_DIR

    scores_path = os.path.join(t_dir, "overture_scores.parquet")
    dpto_output_dir = os.path.join(t_dir, "scores_dpto")

    if not os.path.exists(scores_path):
        print(f"ERROR: Missing scores parquet: {scores_path}")
        print("Run `python pipeline/compute_overture_scores.py` first.")
        return 1

    print("=" * 60)
    print(f"  Split Overture Scores by Department — {args.territory}")
    print("=" * 60)

    print("\nLoading scores data...")
    scores = pd.read_parquet(scores_path)
    all_cols = ["h3index"] + META_COLS + SCORE_COLS + COMPONENT_COLS
    scores = scores[[c for c in all_cols if c in scores.columns]]
    print(f"  {len(scores):,} hexes loaded")

    if args.territory == "misiones":
        dept_polys = build_dept_polygons()
        scores = assign_hexes_to_depts(scores, dept_polys)
        scores_assigned = scores.dropna(subset=["dpto"])
        summary_path = os.path.join(SRC_DATA_DIR, "scores_dept_summary.json")
        n_units = split_and_save(scores_assigned, "dpto", dpto_output_dir, summary_path, "dpto")
    else:
        crosswalk_path = os.path.join(t_dir, "h3_admin_crosswalk.parquet")
        if not os.path.exists(crosswalk_path):
            print(f"ERROR: Missing crosswalk: {crosswalk_path}")
            return 1
        scores, admin_col = assign_hexes_itapua(scores, crosswalk_path)
        scores_assigned = scores.dropna(subset=[admin_col])
        summary_path = os.path.join(SRC_DATA_DIR, f"{args.territory}_scores_dept_summary.json")
        n_units = split_and_save(scores_assigned, admin_col, dpto_output_dir, summary_path, admin_col)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Summary saved to {summary_path}")
    print(f"  {n_units} unit parquets in {dpto_output_dir}")
    print(f"  Total time: {elapsed:.0f}s")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
