"""
Compute district-level mean satellite scores for Itapua (Paraguay).

Joins h3_admin_crosswalk.parquet with 6 satellite analysis parquets,
groups by distrito, computes mean score for each analysis.

Output: pipeline/output/itapua_py/district_stats_itapua.parquet
  Columns: distrito, env_risk_score, climate_comfort_score, accessibility_score,
            agri_potential_score, forest_health_score, flood_risk_score, n_hexes

R2 upload:
  npx wrangler r2 object put neahub/data/itapua_py/district_stats_itapua.parquet \
    --file pipeline/output/itapua_py/district_stats_itapua.parquet --remote
"""

import os
import duckdb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output", "itapua_py")
CROSSWALK = os.path.join(OUTPUT_DIR, "h3_admin_crosswalk.parquet")

ANALYSES = {
    "env_risk_score":       ("sat_environmental_risk.parquet", "score"),
    "climate_comfort_score": ("sat_climate_comfort.parquet",   "score"),
    "accessibility_score":  ("sat_accessibility.parquet",      "score"),
    "agri_potential_score": ("sat_agri_potential.parquet",     "score"),
    "forest_health_score":  ("sat_forest_health.parquet",      "score"),
    "flood_risk_score":     ("hex_flood_risk.parquet",         "flood_risk_score"),
}

OUTPUT = os.path.join(OUTPUT_DIR, "district_stats_itapua.parquet")


def main():
    conn = duckdb.connect()

    # Register crosswalk
    conn.execute(f"CREATE VIEW crosswalk AS SELECT * FROM '{CROSSWALK}'")

    # Build SELECT clauses joining each analysis
    join_clauses = []
    select_cols = ["cw.distrito", "COUNT(cw.h3index) AS n_hexes"]

    for alias, (filename, col) in ANALYSES.items():
        path = os.path.join(OUTPUT_DIR, filename)
        view_name = alias.replace("_score", "")
        conn.execute(f"CREATE VIEW {view_name} AS SELECT * FROM '{path}'")
        join_clauses.append(
            f"LEFT JOIN {view_name} ON cw.h3index = {view_name}.h3index"
        )
        select_cols.append(f"AVG({view_name}.{col}) AS {alias}")

    sql = f"""
        SELECT {', '.join(select_cols)}
        FROM crosswalk cw
        {chr(10).join(join_clauses)}
        GROUP BY cw.distrito
        ORDER BY cw.distrito
    """

    print("Running DuckDB aggregation...")
    df = conn.execute(sql).df()
    print(df.to_string(index=False))
    print(f"\n{len(df)} districts")

    conn.execute(f"COPY ({sql}) TO '{OUTPUT}' (FORMAT PARQUET)")
    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"\nWritten: {OUTPUT} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
