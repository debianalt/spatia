"""
Import parajes, picadas, colonias and other rural settlements into PostGIS dim_barrio.

Sources:
    1. BAHRA (Base de Asentamientos Humanos de la Rep. Argentina) via IGN WFS
    2. OSM Overpass API (hamlet, village, isolated_dwelling, locality)
    3. Mapa Educativo WFS (rural schools as validation layer)

Usage:
    python db/import_settlements.py [--dry-run]

Requires:
    pip install psycopg2-binary geopandas shapely requests
"""

import argparse
import json
import os
import sys
import unicodedata
from difflib import SequenceMatcher

import geopandas as gpd
import psycopg2
import requests
from shapely.geometry import Point

# ── DB connection ──────────────────────────────────────────────────
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("PGDATABASE", "ndvi_misiones")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASS = os.getenv("PGPASSWORD", "")

# ── Constants ──────────────────────────────────────────────────────
DEDUP_DISTANCE_M = 500
FUZZY_THRESHOLD_EXISTING = 80
FUZZY_THRESHOLD_CROSS = 70
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
BAHRA_URL = (
    "https://wms.ign.gob.ar/geoserver/idera/bahra/ows?"
    "service=WFS&version=1.0.0&request=GetFeature"
    "&typeName=idera:bahra&outputFormat=application/json"
    "&CQL_FILTER=nombre_provincia=%27Misiones%27"
)
MAPA_EDUCATIVO_URL = (
    "http://mapa.educacion.gob.ar/geoserver/ows?"
    "service=WFS&version=1.0.0&request=GetFeature"
    "&typeName=publico:establecimiento_educativo"
    "&outputFormat=application/json"
    "&CQL_FILTER=cue%20LIKE%20%2754%25%27%20AND%20amg=%27Rural%27"
)

BAHRA_TIPO_MAP = {
    "Paraje": "paraje",
    "Localidad simple": "localidad_simple",
    "Componente de localidad compuesta": "componente",
    "Entidad": "entidad",
}
OSM_TIPO_MAP = {
    "hamlet": "paraje",
    "village": "pueblo",
    "isolated_dwelling": "paraje",
    "locality": "paraje",
}


def normalize(text):
    """Remove accents and lowercase."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def fuzzy_ratio(a, b):
    """Return 0-100 similarity score using SequenceMatcher."""
    return int(SequenceMatcher(None, normalize(a), normalize(b)).ratio() * 100)


# ── Step 1: Download BAHRA ─────────────────────────────────────────
def download_bahra():
    print("Downloading BAHRA from IGN WFS...")
    resp = requests.get(BAHRA_URL, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    features = data.get("features", [])
    print(f"  BAHRA raw features: {len(features)}")

    rows = []
    for feat in features:
        props = feat.get("properties", {})
        geom = feat.get("geometry")
        if not geom:
            continue
        # BAHRA returns MultiPoint; extract first coordinate pair
        if geom["type"] == "MultiPoint":
            lon, lat = geom["coordinates"][0][:2]
        elif geom["type"] == "Point":
            lon, lat = geom["coordinates"][:2]
        else:
            continue
        tipo_raw = props.get("tipo_asentamiento", "")
        tipo = BAHRA_TIPO_MAP.get(tipo_raw, tipo_raw.lower().replace(" ", "_"))
        nombre = (props.get("nombre_geografico") or props.get("nombre", "")).strip()
        if not nombre:
            continue
        dpto = (props.get("nombre_departamento") or "").strip()
        rows.append({
            "nombre": nombre,
            "tipo": tipo,
            "fuente": "bahra",
            "departamento": dpto,
            "lat": lat,
            "lon": lon,
        })

    gdf = gpd.GeoDataFrame(
        rows, geometry=[Point(r["lon"], r["lat"]) for r in rows], crs="EPSG:4326"
    )
    print(f"  BAHRA parsed: {len(gdf)} settlements")
    return gdf


# ── Step 2: Download OSM ──────────────────────────────────────────
def download_osm():
    print("Downloading OSM from Overpass API...")
    query = """
    [out:json][timeout:60];
    area["ISO3166-2"="AR-N"]->.searchArea;
    (
      node["place"="hamlet"](area.searchArea);
      node["place"="village"](area.searchArea);
      node["place"="isolated_dwelling"](area.searchArea);
      node["place"="locality"](area.searchArea);
    );
    out body;
    """
    resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=120)
    resp.raise_for_status()
    elements = resp.json().get("elements", [])
    print(f"  OSM raw elements: {len(elements)}")

    rows = []
    for el in elements:
        if el.get("type") != "node":
            continue
        tags = el.get("tags", {})
        place = tags.get("place", "")
        tipo = OSM_TIPO_MAP.get(place, "paraje")
        nombre = (tags.get("name") or "").strip()
        if not nombre:
            continue
        lat = el["lat"]
        lon = el["lon"]
        rows.append({
            "nombre": nombre,
            "tipo": tipo,
            "fuente": "osm",
            "departamento": "",  # will be assigned via spatial join
            "lat": lat,
            "lon": lon,
        })

    gdf = gpd.GeoDataFrame(
        rows, geometry=[Point(r["lon"], r["lat"]) for r in rows], crs="EPSG:4326"
    )
    print(f"  OSM parsed: {len(gdf)} settlements")
    return gdf


# ── Step 3: Download Mapa Educativo ───────────────────────────────
def download_mapa_educativo():
    print("Downloading Mapa Educativo (rural schools)...")
    try:
        resp = requests.get(MAPA_EDUCATIVO_URL, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        print(f"  Mapa Educativo raw features: {len(features)}")

        rows = []
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not geom or geom["type"] != "Point":
                continue
            lon, lat = geom["coordinates"][:2]
            nombre = (props.get("fna") or props.get("nam") or "").strip()
            if not nombre:
                continue
            rows.append({
                "nombre": nombre,
                "tipo": "escuela_rural",
                "fuente": "mapa_educativo",
                "departamento": "",
                "lat": lat,
                "lon": lon,
            })

        gdf = gpd.GeoDataFrame(
            rows, geometry=[Point(r["lon"], r["lat"]) for r in rows], crs="EPSG:4326"
        )
        print(f"  Mapa Educativo parsed: {len(gdf)} schools")
        return gdf

    except Exception as e:
        print(f"  WARNING: Mapa Educativo download failed: {e}")
        print("  Continuing without school data (validation layer only).")
        return gpd.GeoDataFrame(
            columns=["nombre", "tipo", "fuente", "departamento", "lat", "lon"],
            geometry=[], crs="EPSG:4326"
        )


# ── Step 4: Load existing dim_barrio ──────────────────────────────
def load_existing_barrios(conn):
    print("Loading existing dim_barrio from PostGIS...")
    cur = conn.cursor()
    cur.execute("""
        SELECT nombre, departamento, tipo, fuente,
               ST_Y(ST_Centroid(geom)) as lat, ST_X(ST_Centroid(geom)) as lon
        FROM dim_barrio
        WHERE geom IS NOT NULL
    """)
    rows = []
    for nombre, dpto, tipo, fuente, lat, lon in cur:
        rows.append({
            "nombre": nombre or "",
            "departamento": dpto or "",
            "tipo": tipo or "",
            "fuente": fuente or "",
            "lat": lat,
            "lon": lon,
        })
    cur.close()

    if not rows:
        return gpd.GeoDataFrame(
            columns=["nombre", "departamento", "tipo", "fuente", "lat", "lon"],
            geometry=[], crs="EPSG:4326"
        )

    gdf = gpd.GeoDataFrame(
        rows, geometry=[Point(r["lon"], r["lat"]) for r in rows], crs="EPSG:4326"
    )
    print(f"  Existing barrios: {len(gdf)}")
    return gdf


# ── Step 5: Load radios_misiones ──────────────────────────────────
def load_radios(conn):
    print("Loading radios_misiones from PostGIS...")
    cur = conn.cursor()
    cur.execute("""
        SELECT redcode, dpto, ST_AsText(geom) as wkt
        FROM radios_misiones
        WHERE redcode IS NOT NULL AND geom IS NOT NULL
    """)
    from shapely import wkt as shapely_wkt
    rows = []
    geoms = []
    for redcode, dpto, wkt_str in cur:
        rows.append({"redcode": redcode, "dpto": dpto})
        geoms.append(shapely_wkt.loads(wkt_str))
    cur.close()

    gdf = gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:4326")
    print(f"  Radios loaded: {len(gdf)}")
    return gdf


# ── Dedup helpers ─────────────────────────────────────────────────
def dedup_against_existing(new_gdf, existing_gdf, distance_m, fuzzy_threshold):
    """Remove settlements from new_gdf that match existing_gdf by name+dept or proximity+name."""
    if existing_gdf.empty or new_gdf.empty:
        return new_gdf

    # Project to metric CRS for distance calculations (UTM 21S for Misiones)
    new_proj = new_gdf.to_crs("EPSG:32721")
    exist_proj = existing_gdf.to_crs("EPSG:32721")

    existing_names = {}
    for _, row in existing_gdf.iterrows():
        key = (normalize(row["nombre"]), normalize(row["departamento"]))
        existing_names[key] = True

    keep = []
    for idx, row in new_gdf.iterrows():
        name_norm = normalize(row["nombre"])
        dpto_norm = normalize(row["departamento"])

        # Exact name+dept match → skip
        if (name_norm, dpto_norm) in existing_names:
            continue

        # Spatial proximity + fuzzy name match
        pt = new_proj.loc[idx, "geometry"]
        dists = exist_proj.geometry.distance(pt)
        nearby = dists[dists < distance_m]
        matched = False
        for near_idx in nearby.index:
            exist_name = existing_gdf.loc[near_idx, "nombre"]
            if fuzzy_ratio(row["nombre"], exist_name) >= fuzzy_threshold:
                matched = True
                break
        if not matched:
            keep.append(idx)

    result = new_gdf.loc[keep].copy()
    dropped = len(new_gdf) - len(result)
    print(f"  Dedup vs existing: {dropped} duplicates removed, {len(result)} remain")
    return result


def dedup_bahra_vs_osm(bahra_gdf, osm_gdf, distance_m, fuzzy_threshold):
    """Remove OSM entries that duplicate BAHRA entries. BAHRA takes priority."""
    if bahra_gdf.empty or osm_gdf.empty:
        return osm_gdf

    bahra_proj = bahra_gdf.to_crs("EPSG:32721")
    osm_proj = osm_gdf.to_crs("EPSG:32721")

    keep = []
    for idx, row in osm_gdf.iterrows():
        pt = osm_proj.loc[idx, "geometry"]
        dists = bahra_proj.geometry.distance(pt)
        nearby = dists[dists < distance_m]
        matched = False
        for near_idx in nearby.index:
            bahra_name = bahra_gdf.loc[near_idx, "nombre"]
            if fuzzy_ratio(row["nombre"], bahra_name) >= fuzzy_threshold:
                matched = True
                break
        if not matched:
            keep.append(idx)

    result = osm_gdf.loc[keep].copy()
    dropped = len(osm_gdf) - len(result)
    print(f"  Dedup BAHRA vs OSM: {dropped} OSM duplicates removed, {len(result)} remain")
    return result


# ── Step 6: Assign redcodes via spatial join ──────────────────────
def assign_redcodes(settlements_gdf, radios_gdf):
    """Assign redcodes to each settlement via spatial containment or nearest radio."""
    print("Assigning redcodes via spatial join...")
    if settlements_gdf.empty:
        settlements_gdf["redcodes"] = []
        settlements_gdf["departamento_radio"] = ""
        return settlements_gdf

    # Spatial join: point in polygon
    joined = gpd.sjoin(
        settlements_gdf, radios_gdf, how="left", predicate="within"
    )

    # For points that didn't fall in any radio, find nearest
    no_match = joined[joined["redcode"].isna()]
    if len(no_match) > 0:
        print(f"  {len(no_match)} points outside radio polygons, assigning nearest...")
        settlements_proj = settlements_gdf.to_crs("EPSG:32721")
        radios_proj = radios_gdf.to_crs("EPSG:32721")
        for idx in no_match.index:
            if idx not in settlements_proj.index:
                continue
            pt = settlements_proj.loc[idx, "geometry"]
            dists = radios_proj.geometry.distance(pt)
            nearest_idx = dists.idxmin()
            joined.loc[idx, "redcode"] = radios_gdf.loc[nearest_idx, "redcode"]
            joined.loc[idx, "dpto"] = radios_gdf.loc[nearest_idx, "dpto"]

    # Handle duplicate indices from sjoin (point in overlapping polygons)
    # Keep first match per settlement
    joined = joined[~joined.index.duplicated(keep="first")]

    settlements_gdf = settlements_gdf.copy()
    settlements_gdf["redcodes"] = joined["redcode"].apply(
        lambda x: [x] if isinstance(x, str) and x else []
    )
    # Fill departamento from radio if missing
    settlements_gdf["departamento_radio"] = joined["dpto"].fillna("")

    assigned = settlements_gdf["redcodes"].apply(len).sum()
    print(f"  Redcodes assigned: {assigned}/{len(settlements_gdf)} settlements")
    return settlements_gdf


# ── Step 7: Insert into dim_barrio ────────────────────────────────
def insert_into_dim_barrio(conn, settlements_gdf, dry_run=False):
    """Insert new settlements into PostGIS dim_barrio."""
    print("Inserting into dim_barrio...")
    cur = conn.cursor()

    inserted = 0
    skipped_no_redcode = 0

    for _, row in settlements_gdf.iterrows():
        redcodes = row.get("redcodes", [])
        if not redcodes:
            skipped_no_redcode += 1
            continue

        nombre = row["nombre"]
        dpto = row["departamento"] if row["departamento"] else row.get("departamento_radio", "")
        tipo = row["tipo"]
        fuente = row["fuente"]
        lat = row["lat"]
        lon = row["lon"]
        redcodes_pg = "{" + ",".join(redcodes) + "}"

        if dry_run:
            inserted += 1
            continue

        cur.execute("""
            INSERT INTO dim_barrio (nombre, localidad, departamento, tipo, fuente, redcodes, geom)
            VALUES (%s, NULL, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
        """, (nombre, dpto, tipo, fuente, redcodes_pg, lon, lat))
        inserted += 1

    if not dry_run:
        conn.commit()

    print(f"  Inserted: {inserted}")
    print(f"  Skipped (no redcode): {skipped_no_redcode}")
    cur.close()
    return inserted


# ── Summary ───────────────────────────────────────────────────────
def print_summary(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT tipo, fuente, COUNT(*)
        FROM dim_barrio
        GROUP BY tipo, fuente
        ORDER BY tipo, fuente
    """)
    print("\n=== dim_barrio summary ===")
    print(f"{'tipo':<25} {'fuente':<20} {'count':>6}")
    print("-" * 55)
    total = 0
    for tipo, fuente, count in cur:
        print(f"{tipo or '(null)':<25} {fuente or '(null)':<20} {count:>6}")
        total += count
    print("-" * 55)
    print(f"{'TOTAL':<46} {total:>6}")
    cur.close()


# ── Main ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Import rural settlements into dim_barrio")
    parser.add_argument("--dry-run", action="store_true", help="Download and dedup but don't insert")
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS
    )

    try:
        # Step 1-3: Download sources
        bahra = download_bahra()
        osm = download_osm()
        schools = download_mapa_educativo()

        # Step 4: Load existing
        existing = load_existing_barrios(conn)

        # Step 5: Cross-source dedup (BAHRA > OSM)
        osm = dedup_bahra_vs_osm(bahra, osm, DEDUP_DISTANCE_M, FUZZY_THRESHOLD_CROSS)

        # Merge BAHRA + OSM
        import pandas as pd
        combined = gpd.GeoDataFrame(
            pd.concat([bahra, osm], ignore_index=True),
            crs="EPSG:4326"
        )
        print(f"\nCombined BAHRA+OSM: {len(combined)} settlements")

        # Step 4 continued: Dedup against existing dim_barrio
        combined = dedup_against_existing(
            combined, existing, DEDUP_DISTANCE_M, FUZZY_THRESHOLD_EXISTING
        )

        # Load radios for spatial join
        radios = load_radios(conn)

        # Step 6: Assign redcodes
        combined = assign_redcodes(combined, radios)

        # Assign departamento from radio data where missing
        for idx, row in combined.iterrows():
            if not row["departamento"] and row.get("departamento_radio"):
                combined.at[idx, "departamento"] = row["departamento_radio"]

        # Summary before insert
        print(f"\n=== Ready to insert ===")
        by_source = combined.groupby(["fuente", "tipo"]).size()
        for (fuente, tipo), count in by_source.items():
            print(f"  {fuente:>10} / {tipo:<20} : {count}")
        print(f"  {'TOTAL':>33}: {len(combined)}")

        # Mapa Educativo summary (validation only, not inserted)
        if not schools.empty:
            print(f"\n  Mapa Educativo (validation only): {len(schools)} rural schools downloaded")

        # Step 7: Insert
        if args.dry_run:
            print("\n[DRY RUN] No changes made to database.")
            insert_into_dim_barrio(conn, combined, dry_run=True)
        else:
            insert_into_dim_barrio(conn, combined, dry_run=False)

        # Step 8: Summary
        if not args.dry_run:
            print_summary(conn)
            print("\nNext step: re-run import_d1.py to regenerate seed.sql")
            print("  python db/import_d1.py")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
