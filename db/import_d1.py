"""
Import PostGIS data into D1 via wrangler.

Usage:
    python db/import_d1.py

Requires:
    pip install psycopg2-binary

Steps:
    1. Connects to PostGIS ndvi_misiones
    2. Exports 5 tables as SQL INSERTs into db/seed.sql
    3. Run: npx wrangler d1 execute spatia-db --file=db/seed.sql
"""

import os
import json
import unicodedata
import psycopg2

DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("PGDATABASE", "ndvi_misiones")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASS = os.getenv("PGPASSWORD", "")

OUTPUT = os.path.join(os.path.dirname(__file__), "seed.sql")

# Mapping: D1 column name -> PostGIS column name
RADIO_STATS_MAP = {
    "redcode": "redcode",
    "departamento": "dpto",
    "total_personas": "total_personas",
    "varones": "varones",
    "mujeres": "mujeres",
    "area_km2": "area_km2",
    "densidad_hab_km2": "densidad_hab_km2",
    "pct_nbi": "pct_nbi",
    "pct_hacinamiento": "pct_hacinamiento",
    "tasa_empleo": "tasa_empleo",
    "tasa_desocupacion": "tasa_desocupacion",
    "tasa_actividad": "tasa_actividad",
    "pct_agua_red": "pct_agua_red",
    "pct_cloacas": "pct_cloacas",
    "pct_universitario": "pct_universitario",
    "pct_secundario_comp": "pct_secundario_comp",
    "tamano_medio_hogar": "tamano_medio_hogar",
    "n_buildings": "n_buildings",
    "ndvi_mean": "ndvi_mean",
    "vulnerability_score": "vulnerability_score",
    "vulnerability_class": "vulnerability_class",
}

# Lens columns from lens_opportunities table (same column names in both)
LENS_COLS = [
    "inv_score", "inv_sub1", "inv_sub2", "inv_sub3", "inv_sub4", "inv_sub5", "inv_sub6",
    "prod_score", "prod_sub1", "prod_sub2", "prod_sub3", "prod_sub4", "prod_sub5", "prod_sub6",
    "serv_score", "serv_sub1", "serv_sub2", "serv_sub3", "serv_sub4", "serv_sub5", "serv_sub6",
    "viv_score", "viv_sub1", "viv_sub2", "viv_sub3", "viv_sub4", "viv_sub5", "viv_sub6",
]


def remove_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def sql_val(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def export_radio_stats(cur, f):
    pg_base = ", ".join(f"m.{v}" for v in RADIO_STATS_MAP.values())
    pg_lens = ", ".join(f"l.{c}" for c in LENS_COLS)
    d1_cols = ", ".join(list(RADIO_STATS_MAP.keys()) + LENS_COLS)
    cur.execute(f"""
        SELECT {pg_base}, {pg_lens}
        FROM radio_stats_master m
        LEFT JOIN lens_opportunities l USING (redcode)
        WHERE m.redcode IS NOT NULL
        ORDER BY m.redcode
    """)
    for row in cur:
        vals = ", ".join(sql_val(v) for v in row)
        f.write(f"INSERT INTO radio_stats ({d1_cols}) VALUES ({vals});\n")


def export_barrios(cur, f):
    cur.execute("""
        SELECT nombre, localidad, departamento, tipo, fuente, redcodes
        FROM dim_barrio
        WHERE array_length(redcodes, 1) > 0
        ORDER BY nombre
    """)
    for row in cur:
        nombre, localidad, dpto, tipo, fuente, redcodes = row
        nombre_lower = remove_accents(nombre) if nombre else ""
        redcodes_json = json.dumps(redcodes if redcodes else [])
        vals = ", ".join([
            sql_val(nombre), sql_val(nombre_lower), sql_val(localidad),
            sql_val(dpto), sql_val(tipo), sql_val(fuente), sql_val(redcodes_json)
        ])
        f.write(f"INSERT INTO barrios_lookup (nombre, nombre_lower, localidad, departamento, tipo, fuente, redcodes) VALUES ({vals});\n")


def export_centroids(cur, f):
    cur.execute("""
        SELECT redcode,
               ST_Y(ST_Centroid(geom)) as lat,
               ST_X(ST_Centroid(geom)) as lng
        FROM radios_misiones
        WHERE redcode IS NOT NULL
        ORDER BY redcode
    """)
    for row in cur:
        vals = ", ".join(sql_val(v) for v in row)
        f.write(f"INSERT INTO radio_centroids (redcode, lat, lng) VALUES ({vals});\n")


def export_indicator_catalog(f):
    """Static catalog of key indicators available in radio_stats."""
    indicators = [
        ("total_personas", "Poblacion total", "demografia", "personas", "Total de personas segun Censo 2022"),
        ("varones", "Varones", "demografia", "personas", "Total de varones segun Censo 2022"),
        ("mujeres", "Mujeres", "demografia", "personas", "Total de mujeres segun Censo 2022"),
        ("area_km2", "Area", "geografia", "km2", "Superficie del radio censal"),
        ("densidad_hab_km2", "Densidad poblacional", "demografia", "hab/km2", "Habitantes por km2"),
        ("pct_nbi", "NBI", "vulnerabilidad", "%", "Porcentaje de hogares con necesidades basicas insatisfechas"),
        ("pct_hacinamiento", "Hacinamiento", "vulnerabilidad", "%", "Porcentaje de hogares con hacinamiento critico"),
        ("tasa_empleo", "Tasa de empleo", "economia", "%", "Tasa de empleo de la poblacion en edad de trabajar"),
        ("tasa_desocupacion", "Tasa de desocupacion", "economia", "%", "Tasa de desocupacion abierta"),
        ("tasa_actividad", "Tasa de actividad", "economia", "%", "Tasa de actividad economica"),
        ("pct_agua_red", "Agua de red", "servicios", "%", "Porcentaje de hogares con agua de red publica"),
        ("pct_cloacas", "Cloacas", "servicios", "%", "Porcentaje de hogares conectados a red cloacal"),
        ("pct_universitario", "Nivel universitario", "educacion", "%", "Porcentaje de poblacion con nivel universitario completo"),
        ("pct_secundario_comp", "Secundario completo", "educacion", "%", "Porcentaje de poblacion con secundario completo"),
        ("tamano_medio_hogar", "Tamano medio del hogar", "habitat", "personas", "Promedio de personas por hogar"),
        ("n_buildings", "Edificaciones", "infraestructura", "unidades", "Cantidad de edificaciones detectadas por IA satelital"),
        ("ndvi_mean", "NDVI medio", "ambiente", "indice", "Indice de vegetacion normalizado promedio anual"),
        ("vulnerability_score", "Indice de vulnerabilidad", "vulnerabilidad", "indice", "Score compuesto de vulnerabilidad socioeconomica"),
        ("vulnerability_class", "Clase de vulnerabilidad", "vulnerabilidad", "categoria", "Clasificacion de vulnerabilidad (baja/media/alta/muy alta)"),
        # Lens opportunity scores
        ("inv_score", "Score Invertir", "oportunidad", "percentil", "Score de oportunidad de inversion inmobiliaria (0-100)"),
        ("prod_score", "Score Producir", "oportunidad", "percentil", "Score de oportunidad productiva agropecuaria (0-100)"),
        ("serv_score", "Score Servir", "oportunidad", "percentil", "Score de oportunidad para servicios (salud, educacion, comercio) (0-100)"),
        ("viv_score", "Score Vivir", "oportunidad", "percentil", "Score de calidad de vida y habitabilidad (0-100)"),
    ]
    for ind in indicators:
        vals = ", ".join(sql_val(v) for v in ind)
        f.write(f"INSERT INTO indicator_catalog (id, nombre, tema, unidad, descripcion) VALUES ({vals});\n")


def export_ndvi(cur, f):
    cur.execute("""
        SELECT redcode, year, mean_ndvi
        FROM ndvi_annual_mean
        WHERE redcode IS NOT NULL
        ORDER BY redcode, year
    """)
    for row in cur:
        vals = ", ".join(sql_val(v) for v in row)
        f.write(f"INSERT INTO ndvi_annual (redcode, year, mean_ndvi) VALUES ({vals});\n")


def main():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS
    )
    try:
        cur = conn.cursor()

        print(f"Exporting to {OUTPUT}...")
        with open(OUTPUT, "w", encoding="utf-8") as f:
            f.write("-- Auto-generated seed data for Spatia D1\n")
            f.write("-- Generated by import_d1.py\n\n")

            print("  radio_stats...")
            export_radio_stats(cur, f)

            print("  barrios_lookup...")
            export_barrios(cur, f)

            print("  radio_centroids...")
            export_centroids(cur, f)

            print("  indicator_catalog...")
            export_indicator_catalog(f)

            print("  ndvi_annual...")
            export_ndvi(cur, f)

        cur.close()
    finally:
        conn.close()

    size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
    print(f"Done. seed.sql = {size_mb:.1f} MB")
    print(f"Now run:\n  npx wrangler d1 execute spatia-db --file=db/seed.sql")


if __name__ == "__main__":
    main()
