"""
Split hex_flood_risk.parquet (Itapúa) into per-district parquets + summary JSON.
Uses h3_admin_crosswalk.parquet to assign each hex to its distrito.

Usage:
  python pipeline/split_flood_itapua.py

Output:
  pipeline/output/itapua_py/flood_dpto/hex_flood_{DISTRITO}.parquet  (x30)
  src/lib/data/itapua_py_flood_dept_summary.json
"""

import json
import os

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output", "itapua_py", "flood_dpto")
SRC_DATA_DIR = os.path.join(SCRIPT_DIR, "..", "src", "lib", "data")

FLOOD_PATH = os.path.join(SCRIPT_DIR, "output", "itapua_py", "hex_flood_risk.parquet")
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "output", "itapua_py", "h3_admin_crosswalk.parquet")

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


def safe_name(distrito: str) -> str:
    return (
        distrito.lower()
        .replace(" ", "_")
        .replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
        .replace("ü", "u")
        .replace(".", "")
    )


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading flood data...")
    flood = pd.read_parquet(FLOOD_PATH)
    flood = flood[[c for c in FLOOD_COLS if c in flood.columns]]
    flood = flood[flood["flood_risk_score"].notna()]
    print(f"  {len(flood)} hexes with flood_risk_score")

    print("Loading crosswalk...")
    crosswalk = pd.read_parquet(CROSSWALK_PATH, columns=["h3index", "distrito"])
    print(f"  {len(crosswalk)} hex-to-distrito mappings")

    flood = flood.merge(crosswalk, on="h3index", how="left")
    unassigned = flood["distrito"].isna().sum()
    print(f"  Unassigned (no crosswalk match): {unassigned}")

    # Province-wide totals (all hexes)
    prov_total_hexes = len(flood)
    prov_high_risk = int((flood["jrc_occurrence"] > 10).sum())
    prov_avg_score = round(float(flood["flood_risk_score"].mean()), 2)

    flood_assigned = flood.dropna(subset=["distrito"])
    distritos = sorted(flood_assigned["distrito"].unique())
    print(f"\nSplitting into {len(distritos)} districts...")

    summary = []

    for distrito in distritos:
        subset = flood_assigned[flood_assigned["distrito"] == distrito]
        avail_cols = [c for c in FLOOD_COLS if c in subset.columns]
        hex_data = subset[avail_cols].drop_duplicates("h3index").reset_index(drop=True)

        parquet_key = safe_name(distrito)
        parquet_path = os.path.join(OUTPUT_DIR, f"hex_flood_{parquet_key}.parquet")
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

        avg_score = round(float(hex_data["flood_risk_score"].mean()), 2)
        high_risk = int((hex_data["jrc_occurrence"] > 10).sum())

        summary.append({
            "dpto": distrito,
            "parquetKey": parquet_key,
            "avg_score": avg_score,
            "hex_count": len(hex_data),
            "high_risk_count": high_risk,
            "centroid": centroid,
        })

        print(f"  {distrito}: {len(hex_data)} hexes, {size_kb:.0f}KB, avg={avg_score}")

    summary_with_totals = {
        "province": {
            "total_hexes": prov_total_hexes,
            "high_risk_count": prov_high_risk,
            "avg_score": prov_avg_score,
        },
        "departments": summary,
    }

    os.makedirs(SRC_DATA_DIR, exist_ok=True)
    summary_path = os.path.join(SRC_DATA_DIR, "itapua_py_flood_dept_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_with_totals, f, ensure_ascii=False, indent=2)

    print(f"\nSummary saved to {summary_path}")
    print(f"Province totals: {prov_total_hexes} hexes, {prov_high_risk} high risk, avg={prov_avg_score}")
    print(f"Districts: {len(distritos)}")


if __name__ == "__main__":
    main()
