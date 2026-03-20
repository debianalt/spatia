"""
Export Misiones province boundary from PostGIS as GeoJSON files.

Generates:
    src/lib/data/misiones_boundary.geojson  — dissolved province outline (white border)
    src/lib/data/misiones_mask.geojson      — inverted polygon: world rect with Misiones as hole (dark mask)

Usage:
    python db/export_province_boundary.py
"""

import os
import json
import psycopg2

DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("PGDATABASE", "ndvi_misiones")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASS = os.getenv("PGPASSWORD", "")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "src", "lib", "data")

BOUNDARY_FILE = os.path.join(OUT_DIR, "misiones_boundary.json")
MASK_FILE = os.path.join(OUT_DIR, "misiones_mask.json")

# Large bbox covering South America for the mask exterior ring
WORLD_BBOX = [[-80, -60], [-80, 10], [-30, 10], [-30, -60], [-80, -60]]

SQL = """
SELECT ST_AsGeoJSON(
    ST_SimplifyPreserveTopology(ST_Union(geom), 0.001)
) FROM radios_misiones WHERE geom IS NOT NULL;
"""


def main():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS
    )
    cur = conn.cursor()
    cur.execute(SQL)
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or not row[0]:
        raise RuntimeError("No geometry returned from query")

    geom = json.loads(row[0])

    # --- Boundary GeoJSON (dissolved outline) ---
    boundary_fc = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {},
            "geometry": geom
        }]
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(BOUNDARY_FILE, "w") as f:
        json.dump(boundary_fc, f)
    print(f"Wrote {BOUNDARY_FILE} ({os.path.getsize(BOUNDARY_FILE) // 1024} KB)")

    # --- Mask GeoJSON (world rect with Misiones as hole) ---
    # Extract exterior ring(s) from the dissolved geometry
    if geom["type"] == "Polygon":
        # Single polygon — exterior ring is coordinates[0]
        holes = [geom["coordinates"][0]]
    elif geom["type"] == "MultiPolygon":
        # Multiple polygons — each exterior ring becomes a hole
        holes = [poly[0] for poly in geom["coordinates"]]
    else:
        raise RuntimeError(f"Unexpected geometry type: {geom['type']}")

    # Reverse winding of each hole (GeoJSON holes must be CW)
    holes_reversed = [list(reversed(ring)) for ring in holes]

    mask_geom = {
        "type": "Polygon",
        "coordinates": [WORLD_BBOX] + holes_reversed
    }
    mask_fc = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {},
            "geometry": mask_geom
        }]
    }
    with open(MASK_FILE, "w") as f:
        json.dump(mask_fc, f)
    print(f"Wrote {MASK_FILE} ({os.path.getsize(MASK_FILE) // 1024} KB)")


if __name__ == "__main__":
    main()
