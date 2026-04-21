"""
Split hex_flood_risk.parquet into per-department parquets + summary JSON.

For Misiones: dissolves radio geometries into department polygons,
then assigns each hex centroid to a department via point-in-polygon.
For other territories: uses h3_admin_crosswalk.parquet (fast lookup).

Usage:
  python pipeline/split_flood_by_dpto.py                          # Misiones (default)
  python pipeline/split_flood_by_dpto.py --territory itapua_py    # Itapúa

Output:
  pipeline/output/{prefix}flood_dpto/hex_flood_{ADMIN}.parquet
  src/lib/data/{territory_id}_flood_dept_summary.json  (non-Misiones)
  src/lib/data/flood_dept_summary.json                 (Misiones)
"""

import argparse
import json
import math
import os

import pandas as pd
from shapely import wkb
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.prepared import prep

from config import get_territory

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
SRC_DATA_DIR = os.path.join(SCRIPT_DIR, "..", "src", "lib", "data")

RADIOS_PATH = os.path.join(SCRIPT_DIR, "output", "radios_misiones.parquet")
RADIO_STATS_PATH = os.path.join(SCRIPT_DIR, "output", "radio_stats_master.parquet")

FLOOD_COLS = ["h3index", "jrc_occurrence", "jrc_recurrence", "jrc_seasonality",
              "flood_extent_pct", "flood_risk_score"]


def h3_to_latlng(h3index: str) -> tuple[float, float]:
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


def safe_filename(name: str) -> str:
    return (name.lower()
            .replace(" ", "_")
            .replace("á", "a").replace("é", "e").replace("í", "i")
            .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
            .replace("ü", "u").replace("'", "").replace(".", ""))


def build_dept_polygons() -> dict[str, any]:
    """Build department polygons by dissolving radio geometries (Misiones only)."""
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


def assign_hexes_to_depts(flood: pd.DataFrame, dept_polys: dict) -> pd.DataFrame:
    """Assign each hex to a department via point-in-polygon (Misiones only)."""
    print("Assigning hexes to departments spatially...")

    prepared = {dpto: prep(poly) for dpto, poly in dept_polys.items()}
    dpto_list = list(dept_polys.keys())

    assignments = {}
    unassigned_pts = {}
    total = len(flood)

    for i, h3index in enumerate(flood["h3index"]):
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
    flood = flood.copy()
    flood["dpto"] = flood["h3index"].map(assignments)
    return flood


def assign_hexes_crosswalk(flood: pd.DataFrame, territory: dict) -> pd.DataFrame:
    """Assign hexes via h3_admin_crosswalk.parquet (non-Misiones territories)."""
    t_prefix = territory['output_prefix']
    t_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/'))
    crosswalk_path = os.path.join(t_dir, 'h3_admin_crosswalk.parquet')

    if not os.path.exists(crosswalk_path):
        raise FileNotFoundError(
            f"Crosswalk not found: {crosswalk_path}\n"
            f"Run: python pipeline/build_admin_crosswalk.py --territory {territory['id']}"
        )

    admin_col = territory['admin_col']
    cw = pd.read_parquet(crosswalk_path, columns=['h3index', admin_col])
    lookup = cw.set_index('h3index')[admin_col].to_dict()
    print(f"  Crosswalk: {len(lookup):,} hexes -> {len(set(lookup.values()))} {territory['admin_level']}s")

    flood = flood.copy()
    flood["dpto"] = flood["h3index"].map(lookup)
    assigned = flood["dpto"].notna().sum()
    print(f"  Assigned {assigned:,}/{len(flood):,} hexes via crosswalk")
    return flood


def compute_centroid(hex_data: pd.DataFrame) -> list[float]:
    lats, lngs = [], []
    for h3idx in hex_data["h3index"]:
        try:
            lat, lng = h3_to_latlng(h3idx)
            lats.append(lat)
            lngs.append(lng)
        except Exception:
            pass
    if lats:
        return [round(sum(lngs) / len(lngs), 4), round(sum(lats) / len(lats), 4)]
    return [0, 0]


def main():
    parser = argparse.ArgumentParser(description="Split flood parquets by admin unit")
    parser.add_argument("--territory", default="misiones",
                        help="Territory ID from config.py (default: misiones)")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    t_prefix = territory['output_prefix']
    territory_id = territory['id']

    flood_path = os.path.join(OUTPUT_DIR, f"{t_prefix}hex_flood_risk.parquet")
    output_dir = os.path.join(OUTPUT_DIR, f"{t_prefix}flood_dpto")
    os.makedirs(output_dir, exist_ok=True)

    if territory_id == 'misiones':
        summary_name = "flood_dept_summary.json"
    else:
        summary_name = f"{territory_id}_flood_dept_summary.json"

    print(f"Loading flood data from {flood_path}...")
    flood = pd.read_parquet(flood_path)
    flood = flood[[c for c in FLOOD_COLS if c in flood.columns]]
    flood = flood[flood["flood_risk_score"].notna()]
    print(f"  {len(flood):,} hexes with flood_risk_score")

    if territory_id == 'misiones':
        dept_polys = build_dept_polygons()
        flood = assign_hexes_to_depts(flood, dept_polys)
    else:
        flood = assign_hexes_crosswalk(flood, territory)

    no_dpto = flood["dpto"].isna().sum()
    print(f"  Unassigned hexes: {no_dpto}")
    flood_assigned = flood.dropna(subset=["dpto"])

    prov_total_hexes = len(flood)
    prov_high_risk = int((flood["jrc_occurrence"] > 10).sum())
    prov_avg_score = round(float(flood["flood_risk_score"].mean()), 1)

    dptos = sorted(flood_assigned["dpto"].unique())
    print(f"\nSplitting into {len(dptos)} {territory['admin_level']}s...")

    summary = []

    for dpto in dptos:
        subset = flood_assigned[flood_assigned["dpto"] == dpto]
        avail_cols = [c for c in FLOOD_COLS if c in subset.columns]
        hex_data = subset[avail_cols].drop_duplicates("h3index").reset_index(drop=True)

        safe_name = safe_filename(dpto)
        parquet_path = os.path.join(output_dir, f"hex_flood_{safe_name}.parquet")
        hex_data.to_parquet(parquet_path, index=False)
        size_kb = os.path.getsize(parquet_path) / 1024

        centroid = compute_centroid(hex_data)
        avg_score = round(float(hex_data["flood_risk_score"].mean()), 1)
        if math.isnan(avg_score):
            avg_score = None
        high_risk = int((hex_data["jrc_occurrence"] > 10).sum())

        summary.append({
            "dpto": dpto,
            "parquetKey": safe_name,
            "avg_score": avg_score,
            "hex_count": len(hex_data),
            "high_risk_count": high_risk,
            "centroid": centroid,
        })

        print(f"  {dpto}: {len(hex_data)} hexes, {size_kb:.0f}KB, avg={avg_score}")

    summary_with_totals = {
        "province": {
            "total_hexes": prov_total_hexes,
            "high_risk_count": prov_high_risk,
            "avg_score": prov_avg_score,
        },
        "departments": summary,
    }

    os.makedirs(SRC_DATA_DIR, exist_ok=True)
    summary_path = os.path.join(SRC_DATA_DIR, summary_name)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_with_totals, f, ensure_ascii=False, indent=2)

    print(f"\nSummary saved to {summary_path}")
    print(f"Territory totals: {prov_total_hexes} hexes, {prov_high_risk} high risk, avg={prov_avg_score}")
    print(f"Assigned: {len(flood_assigned)} hexes across {len(dptos)} {territory['admin_level']}s")


if __name__ == "__main__":
    main()
