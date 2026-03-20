"""
Export radios_misiones from PostGIS to GeoParquet.

One-time script; output is a static input for the weighted crosswalk.

Outputs:
  - pipeline/output/radios_misiones.parquet  (GeoParquet with geometry)

Usage:
  python pipeline/export_radios.py
"""

import os

import geopandas as gpd
import psycopg2
from shapely import wkb

DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("PGDATABASE", "ndvi_misiones")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASS = os.getenv("PGPASSWORD", "")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "radios_misiones.parquet")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Connecting to PostGIS...")
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS,
    )

    try:
        cur = conn.cursor()
        cur.execute("SELECT redcode, ST_AsBinary(geom) FROM radios_misiones WHERE redcode IS NOT NULL")
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    print(f"  -> {len(rows)} radios fetched")

    records = []
    for redcode, geom_wkb in rows:
        geometry = wkb.loads(bytes(geom_wkb))
        records.append({"redcode": redcode, "geometry": geometry})

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    gdf.to_parquet(OUTPUT_PATH, index=False)

    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"  -> Saved {OUTPUT_PATH} ({size_mb:.1f} MB, {len(gdf)} radios)")


if __name__ == "__main__":
    main()
