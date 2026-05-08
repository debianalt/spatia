"""
Build building-weighted H3-radio crosswalk for Corrientes (AR).

Primary weights: buildings per H3 cell / buildings per radio
  (same method as build_dasymetric_crosswalk.py for Misiones)
Fallback: areal interpolation for radios with no buildings.

Pre-requisite: import_gba_corrientes.py must have run (gba_buildings_corrientes table populated).

Inputs:
  - PostGIS ndvi_misiones.gba_buildings_corrientes (building centroids + redcode)
  - pipeline/output/corrientes/radios_corrientes.parquet (for areal fallback)

Output:
  pipeline/output/corrientes/h3_radio_crosswalk_corrientes.parquet

Upload:
  npx wrangler r2 object put neahub/data/corrientes/h3_radio_crosswalk_corrientes.parquet \\
    --file pipeline/output/corrientes/h3_radio_crosswalk_corrientes.parquet --remote
"""

import os
import time

import geopandas as gpd
import h3
import pandas as pd
import psycopg2
from shapely.geometry import Polygon

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
T_DIR = os.path.join(SCRIPT_DIR, "output", "corrientes")
RADIOS_PATH = os.path.join(T_DIR, "radios_corrientes.parquet")
OUTPUT_PATH = os.path.join(T_DIR, "h3_radio_crosswalk_corrientes.parquet")

PG_BUILDINGS = "dbname=ndvi_misiones user=postgres"
H3_RESOLUTION = 9

BUILDING_QUERY = """
    SELECT redcode,
           ST_Y(ST_Centroid(geom)) AS lat,
           ST_X(ST_Centroid(geom)) AS lng
    FROM gba_buildings_corrientes
    WHERE redcode IS NOT NULL
"""


# ── Building-weighted functions (mirrors build_dasymetric_crosswalk.py) ──────

def fetch_building_centroids() -> pd.DataFrame:
    """Fetch building centroids from gba_buildings_corrientes."""
    print("  Querying gba_buildings_corrientes...")
    with psycopg2.connect(PG_BUILDINGS) as conn:
        df = pd.read_sql(BUILDING_QUERY, conn)
    print(f"    -> {len(df):,} buildings, {df['redcode'].nunique():,} radios")
    return df


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
    return counts[["h3index", "redcode", "weight"]].reset_index(drop=True)


# ── Areal fallback (preserved from previous version) ─────────────────────────

def cell_polygon(hid: str) -> Polygon:
    boundary = h3.cell_to_boundary(hid)
    coords = [(lng, lat) for lat, lng in boundary]
    coords.append(coords[0])
    return Polygon(coords)


def build_areal_fallback(radios_with_buildings: set) -> pd.DataFrame:
    """Areal crosswalk for radios with no buildings."""
    if not os.path.exists(RADIOS_PATH):
        print(f"  WARNING: {RADIOS_PATH} not found — skipping areal fallback")
        return pd.DataFrame(columns=["h3index", "redcode", "weight"])

    radios = gpd.read_parquet(RADIOS_PATH)
    missing = radios[~radios["redcode"].isin(radios_with_buildings)]

    if missing.empty:
        print("  Areal fallback: 0 radios (all have buildings)")
        return pd.DataFrame(columns=["h3index", "redcode", "weight"])

    print(f"  Areal fallback for {len(missing)} radios: {list(missing['redcode'])[:5]}{'...' if len(missing) > 5 else ''}")

    radios_utm = missing.to_crs(epsg=32720)  # UTM 20S — Corrientes area

    rows = []
    for _, radio in missing.iterrows():
        geojson = radio.geometry.__geo_interface__
        hex_ids = list(h3.geo_to_cells(geojson, res=H3_RESOLUTION))
        if not hex_ids:
            continue

        hex_records = [{"h3index": hid, "geometry": cell_polygon(hid)} for hid in hex_ids]
        hex_gdf = gpd.GeoDataFrame(hex_records, crs="EPSG:4326").to_crs(epsg=32720)
        radio_gdf = gpd.GeoDataFrame(
            [{"geometry": radio.geometry}], crs="EPSG:4326"
        ).to_crs(epsg=32720)
        radio_area = radio_gdf.geometry.area.iloc[0]
        if radio_area <= 0:
            continue

        overlay = gpd.overlay(hex_gdf, radio_gdf, how="intersection")
        intersection_area = overlay.geometry.area.sum()
        if intersection_area <= 0:
            continue
        overlay["weight"] = overlay.geometry.area / intersection_area

        for _, row in overlay.iterrows():
            rows.append({
                "h3index": row["h3index"],
                "redcode": radio.redcode,
                "weight":  float(row["weight"]),
            })

    return pd.DataFrame(rows)


# ── Validation ────────────────────────────────────────────────────────────────

def validate(df: pd.DataFrame):
    print("\n--- Validation ---")
    n_radios = df["redcode"].nunique()
    print(f"  Radios: {n_radios:,}")

    weight_sums = df.groupby("redcode")["weight"].sum()
    bad = weight_sums[~weight_sums.between(0.99, 1.01)]
    if len(bad) > 0:
        print(f"  WARNING: {len(bad)} radios with weight sum outside [0.99, 1.01]:")
        print(f"    {bad.head(10).to_dict()}")
    else:
        print(f"  Weight sums: all {n_radios:,} radios within [0.99, 1.01]")

    zeros = (df["weight"] == 0).sum()
    print(f"  Zero-weight rows: {zeros}")
    print(f"  Total rows: {len(df):,}")
    print(f"  Unique H3 cells: {df['h3index'].nunique():,}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    os.makedirs(T_DIR, exist_ok=True)

    print("=" * 60)
    print("BUILD DASYMETRIC CROSSWALK — CORRIENTES")
    print("=" * 60)

    # Step 1: Building-weighted primary crosswalk
    print("\nStep 1: Fetch building centroids from PostGIS")
    buildings = fetch_building_centroids()

    print("\nStep 2: Assign H3 cells")
    buildings = assign_h3(buildings)
    print(f"  Unique hexagons with buildings: {buildings['h3index'].nunique():,}")

    print("\nStep 3: Compute dasymetric weights")
    dasy = build_dasymetric_weights(buildings)

    # Step 2: Areal fallback for radios without buildings
    print("\nStep 4: Areal fallback")
    radios_with_buildings = set(dasy["redcode"].unique())
    fallback = build_areal_fallback(radios_with_buildings)

    if not fallback.empty:
        dasy = pd.concat([dasy, fallback], ignore_index=True)
        print(f"  After fallback: {len(dasy):,} rows, {dasy['redcode'].nunique():,} radios")

    # Step 3: Ensure correct dtypes and save
    print("\nStep 5: Save crosswalk")
    dasy["h3index"] = dasy["h3index"].astype(str)
    dasy["redcode"] = dasy["redcode"].astype(str)
    dasy["weight"]  = dasy["weight"].astype("float64")

    dasy.to_parquet(OUTPUT_PATH, index=False)
    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"  Saved {OUTPUT_PATH} ({size_mb:.1f} MB, {len(dasy):,} rows)")

    validate(dasy)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s")
    print("\nNext steps:")
    print("  1. Upload crosswalk:")
    print("     npx wrangler r2 object put neahub/data/corrientes/h3_radio_crosswalk_corrientes.parquet \\")
    print(f"       --file {OUTPUT_PATH} --remote")
    print("  2. Re-generate census parquets:")
    print("     python pipeline/aggregate_radio_to_h3.py --territory corrientes")


if __name__ == "__main__":
    main()
