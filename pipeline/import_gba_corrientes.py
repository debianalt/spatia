"""
Import building footprints for Corrientes (AR) using Overture Maps API.

Fetches buildings from Overture Maps (which integrates Google Buildings, Microsoft BF,
and OSM footprints), does a spatial join to Corrientes census radios, and computes
est_personas via volume-proportional allocation.

Outputs:
  - PostGIS table: ndvi_misiones.gba_buildings_corrientes
    (same schema used by build_corrientes_buildings.py and build_crosswalk_corrientes.py)

Usage:
  python pipeline/import_gba_corrientes.py
  python pipeline/import_gba_corrientes.py --drop    # drop table first
  python pipeline/import_gba_corrientes.py --dry-run # fetch + stats, no PostGIS write

Verification:
  psql -d ndvi_misiones -c "
    SELECT COUNT(*), COUNT(redcode), SUM(est_personas)::int
    FROM gba_buildings_corrientes;"
  -- est_personas sum should approx match total census population of Corrientes
"""

import argparse
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import geopandas as gpd
import pandas as pd
import psycopg2
import psycopg2.extras
from pyproj import Transformer
from shapely import wkb as shapely_wkb
from shapely.ops import transform as shapely_transform

try:
    import overturemaps
except ImportError:
    print("ERROR: overturemaps not installed. Run: pip install overturemaps")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PG_BUILDINGS = "dbname=ndvi_misiones user=postgres"
PG_CENSUS    = "dbname=posadas user=postgres"

# Corrientes province bbox (padded slightly)
BBOX = {"west": -59.8, "south": -30.8, "east": -56.0, "north": -27.3}

TABLE = "gba_buildings_corrientes"

_proj_utm20 = Transformer.from_crs("EPSG:4326", "EPSG:32720", always_xy=True)

def area_m2_from_geom(geom):
    try:
        return round(shapely_transform(_proj_utm20.transform, geom).area, 0)
    except Exception:
        return 0.0


# ── Step 1: Fetch from Overture ──────────────────────────────────────────────

def fetch_overture_buildings() -> list:
    """Stream buildings from Overture Maps for the Corrientes bbox."""
    west, south, east, north = BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"]
    print(f"  Querying Overture Maps bbox: {west},{south} to {east},{north}")

    reader = overturemaps.record_batch_reader(
        'building',
        bbox=(west, south, east, north),
    )
    if reader is None:
        print("  ERROR: overturemaps returned None — check internet access")
        return []

    features = []
    skipped = 0
    total_rows = 0
    t0 = time.time()

    for batch in reader:
        rows = batch.to_pydict()
        n = len(rows['geometry'])
        total_rows += n
        for i in range(n):
            geom_bytes = rows['geometry'][i]
            height = rows.get('height', [None] * n)[i]
            if geom_bytes is None:
                skipped += 1
                continue
            try:
                geom = shapely_wkb.loads(bytes(geom_bytes))
            except Exception:
                skipped += 1
                continue
            if geom is None or geom.is_empty:
                skipped += 1
                continue
            # Normalize to polygon
            if geom.geom_type == "MultiPolygon":
                geom = max(geom.geoms, key=lambda g: g.area)
            elif geom.geom_type != "Polygon":
                skipped += 1
                continue

            features.append({
                "geom":          geom,
                "area_m2":       area_m2_from_geom(geom),
                "best_height_m": round(float(height), 1) if height is not None else 5.0,
            })

        if total_rows % 200_000 == 0 and total_rows > 0:
            print(f"    {total_rows:,} rows processed, {len(features):,} valid ({time.time()-t0:.0f}s)...")

    print(f"  {total_rows:,} rows fetched → {len(features):,} valid buildings ({skipped} skipped, {time.time()-t0:.0f}s)")
    return features


# ── Step 2: PostGIS table ─────────────────────────────────────────────────────

def create_table(conn, drop: bool):
    with conn.cursor() as cur:
        if drop:
            cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
            print(f"  Dropped existing {TABLE}")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                gid           SERIAL PRIMARY KEY,
                geom          GEOMETRY(Polygon, 4326),
                area_m2       FLOAT,
                best_height_m FLOAT DEFAULT 5.0,
                building_type VARCHAR,
                redcode       VARCHAR,
                codprov       VARCHAR DEFAULT '18',
                est_personas  FLOAT DEFAULT 0
            )
        """)
        conn.commit()
    print(f"  Table {TABLE} ready")


def insert_buildings(conn, features: list, batch_size: int = 5000) -> int:
    """Bulk-insert using execute_values with WKB hex."""
    total = 0
    buf = []
    with conn.cursor() as cur:
        for feat in features:
            buf.append((
                feat["geom"].wkb_hex,
                float(feat["area_m2"]),
                float(feat["best_height_m"]),
            ))
            if len(buf) >= batch_size:
                psycopg2.extras.execute_values(
                    cur,
                    f"INSERT INTO {TABLE} (geom, area_m2, best_height_m) VALUES %s",
                    buf,
                    template="(ST_GeomFromWKB(decode(%s,'hex'),4326), %s, %s)",
                    page_size=batch_size,
                )
                total += len(buf)
                buf = []
        if buf:
            psycopg2.extras.execute_values(
                cur,
                f"INSERT INTO {TABLE} (geom, area_m2, best_height_m) VALUES %s",
                buf,
                template="(ST_GeomFromWKB(decode(%s,'hex'),4326), %s, %s)",
                page_size=batch_size,
            )
            total += len(buf)
    conn.commit()
    return total


def create_indexes(conn):
    with conn.cursor() as cur:
        cur.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_geom_idx   ON {TABLE} USING GIST(geom)")
        cur.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_redcode_idx ON {TABLE}(redcode)")
        conn.commit()
    print("  Spatial indexes created")


# ── Step 3: Spatial join (Python-side using geopandas) ───────────────────────

def load_corrientes_radios() -> gpd.GeoDataFrame:
    """Load Corrientes census radios from posadas DB."""
    conn = psycopg2.connect(PG_CENSUS)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT redcode, ST_AsBinary(geom) AS geom_wkb,
                   COALESCE(radios_pob, 0) AS personas
            FROM censo_2022.radios_geom
            WHERE codprov = '18' AND redcode IS NOT NULL AND geom IS NOT NULL
        """)
        rows = cur.fetchall()
    conn.close()

    geoms = [shapely_wkb.loads(bytes(r[1])) for r in rows]
    return gpd.GeoDataFrame(
        {"redcode": [r[0] for r in rows], "personas": [int(r[2]) for r in rows]},
        geometry=geoms,
        crs="EPSG:4326",
    )


def spatial_join_and_est_personas(conn_bldg, radios: gpd.GeoDataFrame):
    """Assign redcode and compute est_personas in Python then batch-update PostGIS."""
    print("  Loading building centroids from PostGIS...")
    with conn_bldg.cursor() as cur:
        cur.execute(f"""
            SELECT gid,
                   ST_X(ST_Centroid(geom)) AS lng,
                   ST_Y(ST_Centroid(geom)) AS lat,
                   area_m2,
                   best_height_m
            FROM {TABLE}
            WHERE geom IS NOT NULL
        """)
        rows = cur.fetchall()

    df = pd.DataFrame(rows, columns=["gid", "lng", "lat", "area_m2", "height"])
    df["area_m2"]  = df["area_m2"].fillna(0).clip(lower=0)
    df["height"]   = df["height"].fillna(3.0).clip(lower=1.5)
    df["volume"]   = df["area_m2"] * df["height"]

    bldg_gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.lng, df.lat),
        crs="EPSG:4326",
    )

    print(f"  Spatial join: {len(bldg_gdf):,} buildings → {len(radios):,} radios...")
    t0 = time.time()
    joined = gpd.sjoin(bldg_gdf, radios[["redcode", "personas", "geometry"]],
                       how="left", predicate="within")
    matched = joined["redcode"].notna().sum()
    print(f"  Matched: {matched:,} / {len(bldg_gdf):,} ({time.time()-t0:.0f}s)")

    # Volume-proportional est_personas
    joined["personas"] = joined["personas"].fillna(0)
    radio_vol = joined.groupby("redcode")["volume"].sum().rename("total_vol")
    joined = joined.join(radio_vol, on="redcode")
    joined["est_personas"] = 0.0
    mask = (joined["total_vol"] > 0) & joined["redcode"].notna()
    joined.loc[mask, "est_personas"] = (
        joined.loc[mask, "volume"] / joined.loc[mask, "total_vol"] * joined.loc[mask, "personas"]
    )

    # Batch UPDATE: redcode
    redcode_rows = [
        (int(r.gid), str(r.redcode))
        for r in joined[joined["redcode"].notna()].itertuples()
    ]
    # Batch UPDATE: est_personas
    pers_rows = [
        (int(r.gid), float(r.est_personas))
        for r in joined.itertuples()
    ]

    print(f"  Updating {len(redcode_rows):,} redcodes and {len(pers_rows):,} est_personas in PostGIS...")
    with conn_bldg.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            f"UPDATE {TABLE} t SET redcode = d.redcode "
            f"FROM (VALUES %s) AS d(gid, redcode) WHERE t.gid = d.gid::int",
            redcode_rows, page_size=5000,
        )
        psycopg2.extras.execute_values(
            cur,
            f"UPDATE {TABLE} t SET est_personas = d.ep "
            f"FROM (VALUES %s) AS d(gid, ep) WHERE t.gid = d.gid::int",
            pers_rows, template="(%s, %s::float)", page_size=5000,
        )
    conn_bldg.commit()
    print(f"  Done")


def print_stats(conn):
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT COUNT(*), COUNT(redcode),
                   COUNT(*) - COUNT(redcode) AS unmatched,
                   SUM(est_personas)::bigint
            FROM {TABLE}
        """)
        r = cur.fetchone()
    print(f"\n  Summary:")
    print(f"    Total buildings:   {r[0]:,}")
    print(f"    With redcode:      {r[1]:,}")
    print(f"    Unmatched:         {r[2]:,}  (outside Corrientes radios — expected)")
    print(f"    Sum est_personas:  {r[3]:,}" if r[3] else "    Sum est_personas:  0 (check pipeline)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop",    action="store_true", help="Drop table before importing")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + print stats, no PostGIS write")
    args = parser.parse_args()

    t_total = time.time()
    print("=" * 60)
    print("IMPORT BUILDINGS — CORRIENTES (Overture Maps)")
    print("=" * 60)

    # Step 1: Fetch from Overture
    print("\nStep 1: Fetch from Overture Maps")
    features = fetch_overture_buildings()
    if not features:
        print("ERROR: no buildings fetched")
        sys.exit(1)

    if args.dry_run:
        areas = [f["area_m2"] for f in features]
        heights = [f["best_height_m"] for f in features]
        print(f"\nDry run stats:")
        print(f"  Buildings:     {len(features):,}")
        print(f"  Median area:   {sorted(areas)[len(areas)//2]:.0f} m²")
        print(f"  Median height: {sorted(heights)[len(heights)//2]:.1f} m")
        print("  (no PostGIS writes — remove --dry-run to proceed)")
        return

    # Step 2: PostGIS insert
    conn_bldg = psycopg2.connect(PG_BUILDINGS)
    print("\nStep 2: Create table")
    create_table(conn_bldg, args.drop)

    print(f"\nStep 3: Insert {len(features):,} buildings...")
    t0 = time.time()
    n = insert_buildings(conn_bldg, features)
    print(f"  Inserted {n:,} rows ({time.time()-t0:.0f}s)")

    print("\nStep 4: Create spatial indexes")
    create_indexes(conn_bldg)

    # Step 3: Spatial join + est_personas
    print("\nStep 5: Load Corrientes radios")
    radios = load_corrientes_radios()
    print(f"  {len(radios):,} radios loaded")

    print("\nStep 6: Spatial join + est_personas")
    spatial_join_and_est_personas(conn_bldg, radios)

    print_stats(conn_bldg)
    conn_bldg.close()

    print(f"\nDone in {time.time()-t_total:.0f}s")
    print("\nNext:")
    print("  python pipeline/build_corrientes_buildings.py")
    print("  python pipeline/build_crosswalk_corrientes.py")


if __name__ == "__main__":
    main()
