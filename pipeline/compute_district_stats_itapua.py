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

import os
import duckdb
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output", "itapua_py")
CROSSWALK = os.path.join(OUTPUT_DIR, "h3_admin_crosswalk.parquet")
NBI_CSV = os.path.join(SCRIPT_DIR, "data", "itapua_nbi_2022.csv")

ANALYSES = {
    "env_risk_score":        ("sat_environmental_risk.parquet", "score"),
    "climate_comfort_score": ("sat_climate_comfort.parquet",    "score"),
    "accessibility_score":   ("sat_accessibility.parquet",      "score"),
    "agri_potential_score":  ("sat_agri_potential.parquet",     "score"),
    "forest_health_score":   ("sat_forest_health.parquet",      "score"),
    "flood_risk_score":      ("hex_flood_risk.parquet",         "flood_risk_score"),
}

OUTPUT = os.path.join(OUTPUT_DIR, "district_stats_itapua.parquet")


def main():
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

    # Merge NBI census data
    print("Merging NBI census data...")
    nbi_df = pd.read_csv(NBI_CSV)
    df = sat_df.merge(nbi_df, on="distrito", how="left")

    # Verify NBI coverage
    missing = df[df["pct_nbi"].isna()]["distrito"].tolist()
    if missing:
        print(f"  WARNING: no NBI data for: {missing}")
    matched = df["pct_nbi"].notna().sum()
    print(f"  NBI matched: {matched}/{len(df)} districts")

    print(df[["distrito", "n_hexes", "pct_nbi", "pct_vivienda", "pct_sanitario", "pct_educacion", "pct_subsistencia"]].to_string(index=False))
    print(f"\n{len(df)} districts")

    df.to_parquet(OUTPUT, index=False)
    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"\nWritten: {OUTPUT} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
