"""
Download Argentine province boundaries and produce simplified GeoJSONs
for the EUDR pipeline (Chaco, Salta, Santiago del Estero, Formosa).

Sources tried in order:
  1. IGN WFS endpoint
  2. datos.gob.ar GeoJSON download
  3. Natural Earth admin-1 (via geopandas built-in)

Outputs
-------
  - eudr_provinces_boundary.json   individual province polygons
  - eudr_provinces_dissolved.json  single merged polygon (for H3 grid generation)

Both files land in  src/lib/data/  relative to the project root.
"""

import json
import os
import sys
import urllib.request
import tempfile

# Allow OGR to read very large GeoJSON features (IGN provinces are detailed)
os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "200"

import geopandas as gpd
from shapely.geometry import mapping

# ── Paths ─────────────────────────────────────────────────────────────────
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(PIPELINE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "src", "lib", "data")

OUT_PROVINCES = os.path.join(DATA_DIR, "eudr_provinces_boundary.json")
OUT_DISSOLVED = os.path.join(DATA_DIR, "eudr_provinces_dissolved.json")

# ── Target provinces ──────────────────────────────────────────────────────
TARGET_NAMES = {
    # NOA
    "Salta":               {"name": "Salta",               "id": "salta"},
    "Jujuy":               {"name": "Jujuy",               "id": "jujuy"},
    "Tucumán":             {"name": "Tucumán",             "id": "tucuman"},
    "Catamarca":           {"name": "Catamarca",           "id": "catamarca"},
    "Santiago del Estero":  {"name": "Santiago del Estero", "id": "santiago_del_estero"},
    # NEA
    "Formosa":             {"name": "Formosa",             "id": "formosa"},
    "Chaco":               {"name": "Chaco",               "id": "chaco"},
    "Corrientes":          {"name": "Corrientes",          "id": "corrientes"},
    "Misiones":            {"name": "Misiones",            "id": "misiones"},
    "Entre Ríos":          {"name": "Entre Ríos",          "id": "entre_rios"},
}

SIMPLIFY_TOLERANCE = 0.01  # ~1 km at these latitudes


# ── Download helpers ──────────────────────────────────────────────────────

def try_ign_wfs() -> gpd.GeoDataFrame | None:
    """Attempt to fetch provinces from IGN WFS.

    The IGN response can be very large (~48 MB).  OGR/GDAL may refuse to
    parse it because it exceeds the default OGR_GEOJSON_MAX_OBJ_SIZE.
    We first try gpd.read_file with the env-var workaround; if that still
    fails we fall back to parsing the JSON with the stdlib ``json`` module
    and constructing the GeoDataFrame manually via shapely.
    """
    url = (
        "https://wms.ign.gob.ar/geoserver/ows?"
        "service=WFS&version=1.0.0&request=GetFeature"
        "&typeName=ign:provincia&outputFormat=application/json"
    )
    print(f"[1/3] Trying IGN WFS …  {url[:80]}…")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".geojson", delete=False)
        tmp.write(raw)
        tmp.close()

        # Attempt 1: let GDAL/OGR parse it (env var already set above)
        try:
            gdf = gpd.read_file(tmp.name, engine="pyogrio")
        except Exception:
            try:
                gdf = gpd.read_file(tmp.name, engine="fiona")
            except Exception:
                # Attempt 2: parse with stdlib json + shapely
                from shapely.geometry import shape
                fc = json.loads(raw)
                rows = []
                for feat in fc.get("features", []):
                    props = dict(feat.get("properties", {}))
                    props["geometry"] = shape(feat["geometry"])
                    rows.append(props)
                gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")

        os.unlink(tmp.name)
        if len(gdf) == 0:
            raise ValueError("Empty response")
        print(f"       OK — {len(gdf)} features")
        return gdf
    except Exception as e:
        print(f"       FAILED: {e}")
        return None


def try_datos_gob() -> gpd.GeoDataFrame | None:
    """Attempt datos.gob.ar bulk download."""
    url = (
        "https://infra.datos.gob.ar/catalog/ign/dataset/7"
        "/distribution/7.8/download/provincia.geojson"
    )
    print(f"[2/3] Trying datos.gob.ar …  {url[:80]}…")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".geojson", delete=False)
        tmp.write(raw)
        tmp.close()
        gdf = gpd.read_file(tmp.name)
        os.unlink(tmp.name)
        if len(gdf) == 0:
            raise ValueError("Empty response")
        print(f"       OK — {len(gdf)} features")
        return gdf
    except Exception as e:
        print(f"       FAILED: {e}")
        return None


def try_natural_earth() -> gpd.GeoDataFrame | None:
    """Fall back to Natural Earth admin-1 via geopandas built-in dataset
    or a direct download from naturalearthdata.com."""
    url = (
        "https://naciscdn.org/naturalearth/10m/cultural/"
        "ne_10m_admin_1_states_provinces.zip"
    )
    print(f"[3/3] Trying Natural Earth 10m …  {url[:60]}…")
    try:
        gdf = gpd.read_file(url)
        gdf = gdf[gdf["admin"] == "Argentina"]
        if len(gdf) == 0:
            raise ValueError("No Argentina features")
        print(f"       OK — {len(gdf)} Argentine provinces")
        return gdf
    except Exception as e:
        print(f"       FAILED: {e}")
        return None


# ── Name matching ─────────────────────────────────────────────────────────

def find_name_column(gdf: gpd.GeoDataFrame) -> str:
    """Heuristically pick the column that holds province names."""
    candidates = ["nam", "nombre", "name", "NAM", "NOMBRE", "NAME",
                  "gna", "GNA", "fna", "FNA"]
    for c in candidates:
        if c in gdf.columns:
            return c
    # Try columns whose values contain one of our target names
    for col in gdf.columns:
        if gdf[col].dtype == object:
            vals = gdf[col].dropna().str.strip().tolist()
            if any("Chaco" in str(v) for v in vals):
                return col
    raise ValueError(
        f"Cannot identify name column among: {list(gdf.columns)}"
    )


def filter_provinces(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return only the four target provinces."""
    name_col = find_name_column(gdf)
    print(f"  Using name column: '{name_col}'")

    # Normalise for matching (strip, title-case)
    gdf = gdf.copy()
    gdf["_match"] = gdf[name_col].astype(str).str.strip()

    # Build a lookup that handles accent variations
    matches = []
    for idx, row in gdf.iterrows():
        raw = row["_match"]
        for target in TARGET_NAMES:
            if target.lower() in raw.lower():
                matches.append(idx)
                break

    filtered = gdf.loc[matches].copy()
    if len(filtered) == 0:
        # Print available names for debugging
        print(f"  Available names: {gdf['_match'].unique().tolist()}")
        raise ValueError("No target provinces matched")

    print(f"  Matched {len(filtered)} provinces: "
          f"{filtered['_match'].tolist()}")
    return filtered


# ── GeoJSON output ────────────────────────────────────────────────────────

def build_feature_collection(gdf: gpd.GeoDataFrame) -> dict:
    """Build a clean GeoJSON FeatureCollection with simplified geometries."""
    name_col = find_name_column(gdf)
    features = []
    for _, row in gdf.iterrows():
        raw_name = str(row[name_col]).strip()
        # Find matching target
        props = None
        for target, p in TARGET_NAMES.items():
            if target.lower() in raw_name.lower():
                props = p
                break
        if props is None:
            continue

        geom = row.geometry
        # Ensure EPSG:4326
        # (gdf should already be in 4326 but just in case)
        simplified = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": mapping(simplified),
        })

    return {"type": "FeatureCollection", "features": features}


def build_dissolved(gdf: gpd.GeoDataFrame) -> dict:
    """Merge all provinces into a single polygon, simplify, and return
    a GeoJSON FeatureCollection with one feature."""
    dissolved = gdf.dissolve()
    geom = dissolved.geometry.iloc[0]
    simplified = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"name": "EUDR Study Area", "id": "eudr_area"},
            "geometry": mapping(simplified),
        }],
    }


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Download & simplify Argentine province boundaries")
    print("=" * 60)

    # Try sources in order
    gdf = try_ign_wfs()
    if gdf is None:
        gdf = try_datos_gob()
    if gdf is None:
        gdf = try_natural_earth()
    if gdf is None:
        print("\nERROR: All download sources failed.")
        sys.exit(1)

    # Ensure CRS is EPSG:4326
    if gdf.crs and not gdf.crs.equals("EPSG:4326"):
        gdf = gdf.to_crs("EPSG:4326")

    # Filter to target provinces
    print("\nFiltering to target provinces …")
    filtered = filter_provinces(gdf)

    # Build province boundaries
    print("\nBuilding province boundaries (simplified) …")
    fc = build_feature_collection(filtered)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PROVINCES, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
    size_kb = os.path.getsize(OUT_PROVINCES) / 1024
    print(f"  Wrote {OUT_PROVINCES}")
    print(f"  {len(fc['features'])} features, {size_kb:.1f} KB")

    # Build dissolved boundary
    print("\nBuilding dissolved boundary …")
    dissolved_fc = build_dissolved(filtered)
    with open(OUT_DISSOLVED, "w", encoding="utf-8") as f:
        json.dump(dissolved_fc, f, ensure_ascii=False)
    size_kb2 = os.path.getsize(OUT_DISSOLVED) / 1024
    print(f"  Wrote {OUT_DISSOLVED}")
    print(f"  {size_kb2:.1f} KB")

    print("\nDone.")


if __name__ == "__main__":
    main()
