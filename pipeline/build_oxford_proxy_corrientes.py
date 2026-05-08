"""
Build radio-level proxies for Corrientes census analyses.

Aggregates H3-level sat_accessibility.parquet -> radio level via h3_radio_crosswalk_corrientes.
Produces two tables used by compute_satellite_scores.py:
  - oxford_accessibility_corrientes.parquet: accessibility_cities_min, accessibility_healthcare_min
  - road_access_corrientes.parquet: dist_primary_m (road_density_km_per_km2 defaults to 0)
"""

import os
import sys

import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR

T_DIR = os.path.join(OUTPUT_DIR, "corrientes")
ACC_PATH = os.path.join(T_DIR, "sat_accessibility.parquet")
XW_PATH = os.path.join(T_DIR, "h3_radio_crosswalk_corrientes.parquet")
OXFORD_OUT = os.path.join(T_DIR, "oxford_accessibility_corrientes.parquet")
ROAD_OUT = os.path.join(T_DIR, "road_access_corrientes.parquet")

# km * 12 min/km ~ travel-time proxy
KM_TO_MIN = 12.0


def main():
    print("Loading accessibility parquet...")
    acc = pd.read_parquet(ACC_PATH, columns=[
        "h3index",
        "travel_min_cabecera",
        "dist_nearest_hospital_km",
        "dist_primary_m",
    ])
    print(f"  {len(acc):,} hexes")

    print("Loading crosswalk...")
    xw = pd.read_parquet(XW_PATH)
    print(f"  {len(xw):,} rows, {xw['redcode'].nunique():,} radios")

    merged = xw.merge(acc, on="h3index", how="inner")
    merged["w_norm"] = merged.groupby("redcode")["weight"].transform(
        lambda w: w / w.sum()
    )

    def wavg(grp, col):
        vals = grp[col].values
        w = grp["w_norm"].values
        valid = ~np.isnan(vals)
        if valid.sum() == 0:
            return np.nan
        return np.average(vals[valid], weights=w[valid])

    print("Aggregating H3 -> radio...")
    oxford_rows = []
    road_rows = []
    for redcode, grp in merged.groupby("redcode"):
        oxford_rows.append({
            "redcode": redcode,
            "accessibility_cities_min": round(wavg(grp, "travel_min_cabecera"), 1),
            "accessibility_healthcare_min": round(
                wavg(grp, "dist_nearest_hospital_km") * KM_TO_MIN, 1
            ),
        })
        road_rows.append({
            "redcode": redcode,
            "dist_primary_m": round(wavg(grp, "dist_primary_m"), 0),
            "road_density_km_per_km2": np.nan,  # not available; COALESCE defaults to 0
        })

    oxford = pd.DataFrame(oxford_rows)
    road = pd.DataFrame(road_rows)

    print(f"  Radios: {len(oxford):,}")
    print(f"  cities_min mean={oxford.accessibility_cities_min.mean():.1f}")
    print(f"  healthcare_min mean={oxford.accessibility_healthcare_min.mean():.1f}")
    print(f"  dist_primary_m mean={road.dist_primary_m.mean():.0f}")

    oxford.to_parquet(OXFORD_OUT, index=False)
    road.to_parquet(ROAD_OUT, index=False)
    print(f"Saved: {OXFORD_OUT}")
    print(f"Saved: {ROAD_OUT}")


if __name__ == "__main__":
    main()
