"""
Export Corrientes radios from posadas PostGIS DB to GeoParquet.

Output: pipeline/output/corrientes/radios_corrientes.parquet
"""

import os

import geopandas as gpd
import psycopg2
from shapely import wkb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output", "corrientes")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "radios_corrientes.parquet")

PG_CENSUS = "dbname=posadas user=postgres"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Connecting to posadas DB...")
    conn = psycopg2.connect(PG_CENSUS)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT redcode,
                   ST_AsBinary(geom) AS geom_wkb,
                   codprov,
                   dpto,
                   radios_pob,
                   radios_hog,
                   COALESCE(radios_sup, 0) AS area_km2
            FROM censo_2022.radios_geom
            WHERE codprov = '18' AND geom IS NOT NULL AND redcode IS NOT NULL
        """)
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    print(f"  -> {len(rows)} radios fetched")

    records = []
    for redcode, geom_wkb, codprov, dpto, pob, hog, area_km2 in rows:
        geom = wkb.loads(bytes(geom_wkb))
        records.append({
            "redcode": redcode,
            "geometry": geom,
            "codprov": codprov,
            "dpto": dpto or "",
            "total_personas": int(pob) if pob else 0,
            "total_hogares": int(hog) if hog else 0,
            "area_km2": float(area_km2) if area_km2 else 0.0,
        })

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    gdf.to_parquet(OUTPUT_PATH, index=False)

    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"  -> Saved {OUTPUT_PATH} ({size_mb:.1f} MB, {len(gdf)} radios)")
    print(f"  -> Dptos: {gdf['dpto'].nunique()} unique")


if __name__ == "__main__":
    main()
