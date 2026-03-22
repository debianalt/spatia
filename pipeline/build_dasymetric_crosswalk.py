"""
Build dasymetric H3-radio crosswalk using building footprints.

Replaces the areal crosswalk (uniform distribution) with building-weighted
weights: weight = buildings_in_hex / buildings_in_radio. Hexagons with no
buildings are excluded, concentrating census data where people actually live.

Sources:
  - vida_buildings (161K, 183 radios) — Posadas & surroundings
  - gba_buildings  (2.7M, 1827 radios) — rest of Misiones
  - Fallback areal for 2 radios without buildings (540070000, 540350000)

Outputs:
  - pipeline/output/h3_radio_crosswalk.parquet  (h3index, redcode, weight)
  - pipeline/output/h3_radio_crosswalk_areal.parquet  (backup of previous)

Usage:
  python pipeline/build_dasymetric_crosswalk.py
"""

import os
import shutil

import geopandas as gpd
import h3
import pandas as pd
import psycopg2

# --- DB config (same convention as export_radios.py) ---
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("PGDATABASE", "ndvi_misiones")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASS = os.getenv("PGPASSWORD", "")

# --- Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
CROSSWALK_PATH = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk.parquet")
AREAL_BACKUP_PATH = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk_areal.parquet")
RADIOS_PATH = os.path.join(OUTPUT_DIR, "radios_misiones.parquet")

H3_RESOLUTION = 9

BUILDING_QUERY = """
    SELECT redcode,
           ST_Y(ST_Centroid(geom)) AS lat,
           ST_X(ST_Centroid(geom)) AS lng
    FROM {table}
    WHERE redcode IS NOT NULL
"""


def fetch_building_centroids(conn) -> pd.DataFrame:
    """Fetch centroids from vida_buildings and gba_buildings, concatenate."""
    frames = []
    for table in ("vida_buildings", "gba_buildings"):
        print(f"  Querying {table}...")
        df = pd.read_sql(BUILDING_QUERY.format(table=table), conn)
        print(f"    -> {len(df):,} rows, {df['redcode'].nunique():,} radios")
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    print(f"  Combined: {len(combined):,} buildings, {combined['redcode'].nunique():,} radios")
    return combined


def assign_h3(df: pd.DataFrame) -> pd.DataFrame:
    """Add h3index column from lat/lng centroids."""
    print("  Assigning H3 cells...")
    df["h3index"] = df.apply(
        lambda r: h3.latlng_to_cell(r["lat"], r["lng"], H3_RESOLUTION), axis=1
    )
    return df


def build_dasymetric_weights(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate building counts per (h3index, redcode) and compute weights."""
    print("  Aggregating building counts...")
    counts = (
        df.groupby(["h3index", "redcode"])
        .size()
        .reset_index(name="n_buildings")
    )

    radio_totals = counts.groupby("redcode")["n_buildings"].transform("sum")
    counts["weight"] = counts["n_buildings"] / radio_totals

    result = counts[["h3index", "redcode", "weight"]].reset_index(drop=True)
    return result


def build_areal_fallback(radios_with_buildings: set) -> pd.DataFrame:
    """Areal crosswalk for radios that have no buildings (same logic as generate_h3_grid.py)."""
    if not os.path.exists(RADIOS_PATH):
        print(f"  WARNING: {RADIOS_PATH} not found — cannot compute areal fallback")
        return pd.DataFrame(columns=["h3index", "redcode", "weight"])

    radios = gpd.read_parquet(RADIOS_PATH)
    missing = radios[~radios["redcode"].isin(radios_with_buildings)]

    if missing.empty:
        return pd.DataFrame(columns=["h3index", "redcode", "weight"])

    print(f"  Areal fallback for {len(missing)} radios: {list(missing['redcode'])}")

    # Polyfill each radio with H3 cells and compute areal weights
    radios_utm = missing.to_crs(epsg=32721)
    radios_utm["radio_area"] = radios_utm.geometry.area

    rows = []
    for _, radio in missing.iterrows():
        geojson = radio.geometry.__geo_interface__
        hex_ids = list(h3.geo_to_cells(geojson, res=H3_RESOLUTION))
        if not hex_ids:
            continue

        # Build hex geometries for intersection
        from shapely.geometry import Polygon
        hex_records = []
        for hid in hex_ids:
            boundary = h3.cell_to_boundary(hid)
            coords = [(lng, lat) for lat, lng in boundary]
            coords.append(coords[0])
            hex_records.append({"h3index": hid, "geometry": Polygon(coords)})

        hex_gdf = gpd.GeoDataFrame(hex_records, crs="EPSG:4326").to_crs(epsg=32721)
        radio_gdf = gpd.GeoDataFrame([radio], crs="EPSG:4326").to_crs(epsg=32721)
        radio_area = radio_gdf.geometry.area.iloc[0]

        overlay = gpd.overlay(hex_gdf, radio_gdf, how="intersection")
        overlay["intersection_area"] = overlay.geometry.area
        overlay["weight"] = overlay["intersection_area"] / radio_area

        for _, row in overlay.iterrows():
            rows.append({
                "h3index": row["h3index"],
                "redcode": radio["redcode"],
                "weight": row["weight"],
            })

    return pd.DataFrame(rows)


def backup_areal_crosswalk():
    """Backup existing areal crosswalk before overwriting."""
    if os.path.exists(CROSSWALK_PATH) and not os.path.exists(AREAL_BACKUP_PATH):
        shutil.copy2(CROSSWALK_PATH, AREAL_BACKUP_PATH)
        size_mb = os.path.getsize(AREAL_BACKUP_PATH) / (1024 * 1024)
        print(f"  Backed up areal crosswalk -> {AREAL_BACKUP_PATH} ({size_mb:.1f} MB)")
    elif os.path.exists(AREAL_BACKUP_PATH):
        print(f"  Areal backup already exists, skipping")


def validate(df: pd.DataFrame):
    """Run verification checks on the final crosswalk."""
    print("\n--- Validation ---")

    n_radios = df["redcode"].nunique()
    print(f"  Radios: {n_radios}")

    weight_sums = df.groupby("redcode")["weight"].sum()
    bad = weight_sums[~weight_sums.between(0.99, 1.01)]
    if len(bad) > 0:
        print(f"  WARNING: {len(bad)} radios with weight sum outside [0.99, 1.01]:")
        print(f"    {bad.head(10)}")
    else:
        print(f"  Weight sums: all {n_radios} radios within [0.99, 1.01]")

    zeros = (df["weight"] == 0).sum()
    print(f"  Zero-weight rows: {zeros}")

    print(f"  Total rows: {len(df):,}")

    # Spot check: largest radio by row count vs smallest
    radio_counts = df.groupby("redcode").size()
    largest = radio_counts.idxmax()
    smallest = radio_counts.idxmin()
    print(f"  Most hexagons: {largest} ({radio_counts[largest]} hex)")
    print(f"  Fewest hexagons: {smallest} ({radio_counts[smallest]} hex)")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Step 1: Backup existing areal crosswalk
    print("Step 1: Backup areal crosswalk")
    backup_areal_crosswalk()

    # Step 2: Fetch building centroids from PostGIS
    print("\nStep 2: Fetch building centroids from PostGIS")
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS,
    )
    try:
        buildings = fetch_building_centroids(conn)
    finally:
        conn.close()

    # Step 3: Assign H3 cells
    print("\nStep 3: Assign H3 cells")
    buildings = assign_h3(buildings)
    print(f"  Unique hexagons with buildings: {buildings['h3index'].nunique():,}")

    # Step 4: Compute dasymetric weights
    print("\nStep 4: Compute dasymetric weights")
    dasy = build_dasymetric_weights(buildings)

    # Step 5: Areal fallback for radios without buildings
    print("\nStep 5: Areal fallback")
    radios_with_buildings = set(dasy["redcode"].unique())
    fallback = build_areal_fallback(radios_with_buildings)

    if not fallback.empty:
        dasy = pd.concat([dasy, fallback], ignore_index=True)
        print(f"  After fallback: {len(dasy):,} rows, {dasy['redcode'].nunique():,} radios")

    # Step 6: Ensure correct dtypes and save
    print("\nStep 6: Save crosswalk")
    dasy["h3index"] = dasy["h3index"].astype(str)
    dasy["redcode"] = dasy["redcode"].astype(str)
    dasy["weight"] = dasy["weight"].astype("float64")

    dasy.to_parquet(CROSSWALK_PATH, index=False)
    size_mb = os.path.getsize(CROSSWALK_PATH) / (1024 * 1024)
    print(f"  Saved {CROSSWALK_PATH} ({size_mb:.1f} MB, {len(dasy):,} rows)")

    # Step 7: Validate
    validate(dasy)

    print("\nDone! Next steps:")
    print("  python pipeline/upload_to_r2.py --file pipeline/output/h3_radio_crosswalk.parquet --dest data/h3_radio_crosswalk.parquet")


if __name__ == "__main__":
    main()
