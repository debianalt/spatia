"""
Compute district-level statistics for Itapua (Paraguay).

1. Satellite scores: DuckDB join h3_admin_crosswalk + 6 analysis parquets → AVG by distrito
2. Census NBI: read itapua_nbi_2022.csv → merge NBI components by distrito

Output: pipeline/output/itapua_py/district_stats_itapua.parquet
  Columns: distrito, n_hexes,
            env_risk_score, climate_comfort_score, accessibility_score,
            agri_potential_score, forest_health_score, flood_risk_score,
            pct_nbi, pct_vivienda, pct_sanitario, pct_educacion, pct_subsistencia

R2 upload:
  npx wrangler r2 object put neahub/data/itapua_py/district_stats_itapua.parquet \
    --file pipeline/output/itapua_py/district_stats_itapua.parquet --remote
"""

import argparse
import os
import sys
import duckdb
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import get_territory


def _stem(tid: str) -> str:
    for suf in ("_py", "_br", "_ar"):
        if tid.endswith(suf):
            return tid[:-len(suf)]
    return tid


ANALYSES = {
    "env_risk_score":        ("sat_environmental_risk.parquet", "score"),
    "climate_comfort_score": ("sat_climate_comfort.parquet",    "score"),
    "accessibility_score":   ("sat_accessibility.parquet",      "score"),
    "agri_potential_score":  ("sat_agri_potential.parquet",     "score"),
    "forest_health_score":   ("sat_forest_health.parquet",      "score"),
    "flood_risk_score":      ("hex_flood_risk.parquet",         "flood_risk_score"),
}
NBI_COLS = ["pct_nbi", "pct_vivienda", "pct_sanitario", "pct_educacion", "pct_subsistencia"]


def main():
    ap = argparse.ArgumentParser(description="Compute district-level stats (any territory)")
    ap.add_argument("--territory", default="itapua_py", help="Territory ID (default: itapua_py)")
    args = ap.parse_args()
    terr = get_territory(args.territory)
    tid = terr["id"]
    stem = _stem(tid)

    out_dir = os.path.join(SCRIPT_DIR, "output", terr["output_prefix"].rstrip("/"))
    global OUTPUT_DIR, CROSSWALK, NBI_CSV, OUTPUT
    OUTPUT_DIR = out_dir
    CROSSWALK = os.path.join(out_dir, "h3_admin_crosswalk.parquet")
    NBI_CSV = os.path.join(SCRIPT_DIR, "data", f"{stem}_nbi_2022.csv")
    OUTPUT = os.path.join(out_dir, f"district_stats_{stem}.parquet")

    conn = duckdb.connect()

    conn.execute(f"CREATE VIEW crosswalk AS SELECT * FROM '{CROSSWALK}'")

    join_clauses = []
    select_cols = ["cw.distrito", "COUNT(cw.h3index) AS n_hexes"]

    for alias, (filename, col) in ANALYSES.items():
        path = os.path.join(OUTPUT_DIR, filename)
        view_name = alias.replace("_score", "")
        conn.execute(f"CREATE VIEW {view_name} AS SELECT * FROM '{path}'")
        join_clauses.append(f"LEFT JOIN {view_name} ON cw.h3index = {view_name}.h3index")
        select_cols.append(f"AVG({view_name}.{col}) AS {alias}")

    sql = f"""
        SELECT {', '.join(select_cols)}
        FROM crosswalk cw
        {chr(10).join(join_clauses)}
        GROUP BY cw.distrito
        ORDER BY cw.distrito
    """

    print("Running DuckDB satellite aggregation...")
    sat_df = conn.execute(sql).df()

    # Merge NBI census data (optional — DGEEC NBI may not be sourced yet)
    if os.path.exists(NBI_CSV):
        print(f"Merging NBI census data ({os.path.basename(NBI_CSV)})...")
        nbi_df = pd.read_csv(NBI_CSV)
        df = sat_df.merge(nbi_df, on="distrito", how="left")
        missing = df[df["pct_nbi"].isna()]["distrito"].tolist()
        if missing:
            print(f"  WARNING: no NBI data for: {missing}")
        print(f"  NBI matched: {df['pct_nbi'].notna().sum()}/{len(df)} districts")
        print(df[["distrito", "n_hexes", *NBI_COLS]].to_string(index=False))
    else:
        print(f"  NBI CSV not found ({NBI_CSV}) — district_stats without NBI "
              f"(graceful degrade; same as Itapúa audit: NBI optional).")
        df = sat_df.copy()
        for c in NBI_COLS:
            df[c] = pd.NA
        print(df[["distrito", "n_hexes"]].to_string(index=False))
    print(f"\n{len(df)} districts")

    df.to_parquet(OUTPUT, index=False)
    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"\nWritten: {OUTPUT} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
