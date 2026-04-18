"""
Split hex_flood_risk.parquet into per-department parquets + summary JSON.
Uses spatial assignment: dissolves radio geometries into department polygons,
then assigns each hex centroid to a department via point-in-polygon.

Usage:
  python pipeline/split_flood_by_dpto.py

Output:
  pipeline/output/flood_dpto/hex_flood_{DPTO}.parquet  (x17)
  src/lib/data/flood_dept_summary.json
"""

import json
import math
import os

import pandas as pd
from shapely import wkb
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.prepared import prep

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output", "flood_dpto")
SRC_DATA_DIR = os.path.join(SCRIPT_DIR, "..", "src", "lib", "data")

FLOOD_PATH = os.path.join(SCRIPT_DIR, "output", "hex_flood_risk.parquet")
RADIOS_PATH = os.path.join(SCRIPT_DIR, "output", "radios_misiones.parquet")
RADIO_STATS_PATH = os.path.join(SCRIPT_DIR, "output", "radio_stats_master.parquet")

FLOOD_COLS = ["h3index", "jrc_occurrence", "jrc_recurrence", "jrc_seasonality",
              "flood_extent_pct", "flood_risk_score"]


def h3_to_latlng(h3index: str) -> tuple[float, float]:
    """Convert H3 index to (lat, lng) without h3 library — decode from hex string."""
    # Use h3 library if available, otherwise fall back to approximation
    try:
        from h3 import cell_to_latlng
        return cell_to_latlng(h3index)
    except ImportError:
        pass
    # Fallback: use h3-py
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

    # Parse WKB geometries
    radios["geom"] = radios["geometry"].apply(lambda b: wkb.loads(b))
    radios = radios.merge(radio_stats, on="redcode", how="inner")

    # Dissolve by department (no buffer — exact boundaries)
    dept_polys = {}
    for dpto, group in radios.groupby("dpto"):
        geoms = [g for g in group["geom"] if g is not None and g.is_valid]
        if geoms:
            dept_polys[dpto] = unary_union(geoms)

    print(f"  Built {len(dept_polys)} department polygons")
    return dept_polys


def assign_hexes_to_depts(flood: pd.DataFrame, dept_polys: dict) -> pd.DataFrame:
    """Assign each hex to a department via point-in-polygon, then nearest for unmatched."""
    print("Assigning hexes to departments spatially...")

    # Phase 1: exact containment (no buffer)
    prepared = {dpto: prep(poly) for dpto, poly in dept_polys.items()}
    dpto_list = list(dept_polys.keys())

    assignments = {}
    unassigned_pts = {}  # h3index → Point
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

    # Phase 2: assign unmatched hexes to nearest department polygon
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


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading flood data...")
    flood = pd.read_parquet(FLOOD_PATH)
    flood = flood[[c for c in FLOOD_COLS if c in flood.columns]]
    flood = flood[flood["flood_risk_score"].notna()]
    print(f"  {len(flood)} hexes with flood_risk_score")

    # Build department polygons and assign spatially
    dept_polys = build_dept_polygons()
    flood = assign_hexes_to_depts(flood, dept_polys)

    # Stats
    no_dpto = flood["dpto"].isna().sum()
    print(f"  Unassigned hexes (outside all departments): {no_dpto}")
    flood_assigned = flood.dropna(subset=["dpto"])

    # Province-wide totals (from ALL hexes, not just assigned)
    prov_total_hexes = len(flood)
    prov_high_risk = int((flood["jrc_occurrence"] > 10).sum())
    prov_avg_score = round(float(flood["flood_risk_score"].mean()), 1)

    dptos = sorted(flood_assigned["dpto"].unique())
    print(f"\nSplitting into {len(dptos)} departments...")

    summary = []

    for dpto in dptos:
        subset = flood_assigned[flood_assigned["dpto"] == dpto]
        avail_cols = [c for c in FLOOD_COLS if c in subset.columns]
        hex_data = subset[avail_cols].drop_duplicates("h3index").reset_index(drop=True)

        # Safe filename
        safe_name = dpto.lower().replace(" ", "_").replace("á", "a").replace("é", "e") \
            .replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n") \
            .replace("ü", "u")
        parquet_path = os.path.join(OUTPUT_DIR, f"hex_flood_{safe_name}.parquet")
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

        avg_score = round(float(hex_data["flood_risk_score"].mean()), 1)
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

    # Add province-wide totals to summary
    summary_with_totals = {
        "province": {
            "total_hexes": prov_total_hexes,
            "high_risk_count": prov_high_risk,
            "avg_score": prov_avg_score,
        },
        "departments": summary,
    }

    os.makedirs(SRC_DATA_DIR, exist_ok=True)
    summary_path = os.path.join(SRC_DATA_DIR, "flood_dept_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_with_totals, f, ensure_ascii=False, indent=2)

    print(f"\nSummary saved to {summary_path}")
    print(f"Province totals: {prov_total_hexes} hexes, {prov_high_risk} high risk, avg={prov_avg_score}")
    print(f"Assigned to departments: {len(flood_assigned)} hexes across {len(dptos)} depts")


if __name__ == "__main__":
    main()
