"""
Extract census variables from PostGIS for Corrientes (codprov='18').

Output: pipeline/output/corrientes/censo2022_variables_corrientes.parquet

Schema matches censo2022_variables (Misiones) for use by compute_satellite_scores.py.
"""

import os
import sys

import pandas as pd
import psycopg2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR

OUTPATH = os.path.join(OUTPUT_DIR, "corrientes", "censo2022_variables_corrientes.parquet")


def safe_pct(num, den):
    return (num / den.replace(0, float("nan")) * 100).round(2)


def main():
    conn = psycopg2.connect(dbname="posadas", user="postgres")

    # Household variables (NBI sub-criteria, h_piso = sin piso adecuado)
    hog = pd.read_sql(
        """
        SELECT redcode,
            h_total, h_nbi, h_cloaca, h_piso,
            h_hacinami, h_hacina_1, h_computad, h_agua_red
        FROM censo_2022.v_censo_nbi_2022
        WHERE codprov = '18'
        """,
        conn,
    )

    # Person variables — comprehensive view contains education, health, age groups
    per = pd.read_sql(
        """
        SELECT redcode,
            p_total, p_a17, p18a_sin_i, p18a_solos, p18a_terci, p18a_unive,
            p_18a, p_cobertur, p65_total
        FROM censo_2022.v_censo_niveducativo_2022
        WHERE redcode LIKE '18%%'
        """,
        conn,
    )

    # Non-attendance (sexo=0 → both sexes / total)
    inas = pd.read_sql(
        """
        SELECT redcode, nasiste6a1, total_6a12, nasiste_13, total13_18
        FROM censo_2022.v_censo_children_noasisten_2022
        WHERE redcode LIKE '18%%' AND sexo = 0
        """,
        conn,
    )

    # Adolescent fecundity
    fec = pd.read_sql(
        """
        SELECT redcode, ma_14a17, m_14a17
        FROM censo_2022.v_censo_fecundidad_2022
        WHERE redcode LIKE '18%%'
        """,
        conn,
    )

    conn.close()

    # Radio stats for densidad_hab_km2
    radio_stats = pd.read_parquet(
        os.path.join(OUTPUT_DIR, "corrientes", "radio_stats_corrientes.parquet"),
        columns=["redcode", "densidad_hab_km2"],
    )

    df = (
        hog.merge(per, on="redcode", how="outer")
        .merge(inas, on="redcode", how="left")
        .merge(fec, on="redcode", how="left")
        .merge(radio_stats, on="redcode", how="left")
    )

    result = pd.DataFrame()
    result["redcode"] = df["redcode"]
    result["densidad_hab_km2"] = df["densidad_hab_km2"].round(2)
    result["pct_nbi"] = safe_pct(df["h_nbi"], df["h_total"])
    result["pct_cloacas"] = safe_pct(df["h_cloaca"], df["h_total"])
    result["pct_sin_piso_adecuado"] = safe_pct(df["h_piso"], df["h_total"])
    result["pct_hacinamiento"] = safe_pct(df["h_hacinami"], df["h_total"])
    result["pct_hacinamiento_critico"] = safe_pct(df["h_hacina_1"], df["h_total"])
    result["pct_computadora"] = safe_pct(df["h_computad"], df["h_total"])
    result["pct_cobertura_salud"] = safe_pct(df["p_cobertur"], df["p_total"])
    result["pct_adultos_mayores"] = safe_pct(df["p65_total"], df["p_total"])
    result["pct_menores_18"] = safe_pct(df["p_a17"], df["p_total"])
    result["pct_sin_instruccion"] = safe_pct(df["p18a_sin_i"], df["p_18a"])
    result["pct_secundario_comp"] = safe_pct(
        df["p18a_solos"] + df["p18a_terci"] + df["p18a_unive"], df["p_18a"]
    )
    result["pct_terciario"] = safe_pct(df["p18a_terci"] + df["p18a_unive"], df["p_18a"])
    result["pct_universitario"] = safe_pct(df["p18a_unive"], df["p_18a"])
    result["tasa_inasistencia_6a12"] = safe_pct(df["nasiste6a1"], df["total_6a12"])
    result["tasa_inasistencia_13a18"] = safe_pct(df["nasiste_13"], df["total13_18"])
    result["tasa_maternidad_adolescente"] = safe_pct(df["ma_14a17"], df["m_14a17"])

    result = result.dropna(subset=["redcode"]).reset_index(drop=True)

    os.makedirs(os.path.dirname(OUTPATH), exist_ok=True)
    result.to_parquet(OUTPATH, index=False)
    print(f"Rows: {len(result)}")
    print(f"Columns: {list(result.columns)}")
    print(f"Saved: {OUTPATH}")
    print(result[["redcode", "pct_nbi", "pct_cloacas", "pct_sin_piso_adecuado",
                   "pct_cobertura_salud", "tasa_inasistencia_6a12"]].head(3).to_string())


if __name__ == "__main__":
    main()
