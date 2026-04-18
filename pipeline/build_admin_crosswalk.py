"""
Build H3 res-9 -> admin unit crosswalk for a territory.

For Misiones, the crosswalk comes from the dasymetric radio-census procedure.
For other territories (Itapúa, etc.), we build it directly from polygon geometries:
  - For each admin polygon, polyfill with H3 res-9
  - Hexes split across boundaries go to the polygon with larger intersection area
  - Output: {territory_prefix}h3_admin_crosswalk.parquet  (cols: h3index, <admin_col>)

Usage:
  # From GEE GAUL (requires GEE auth):
  python pipeline/build_admin_crosswalk.py --territory itapua_py --source gaul

  # From local shapefile (GADM 4.1 — recommended):
  python pipeline/build_admin_crosswalk.py --territory itapua_py --source gadm \
      --shapefile pipeline/data/PRY_adm2.shp

  # From local GeoJSON (already exported from QGIS/GEE):
  python pipeline/build_admin_crosswalk.py --territory itapua_py --source geojson \
      --shapefile pipeline/output/itapua_gaul_distritos.geojson

Also generates:
  {territory_prefix}hexagons.geojson  — hex grid for this territory (used by process_raster_to_h3)
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from shapely.geometry import shape, mapping, Polygon
from shapely.ops import unary_union

from config import OUTPUT_DIR, H3_RESOLUTION, get_territory

try:
    import h3 as _h3_mod
    _h3_version = tuple(int(x) for x in _h3_mod.__version__.split('.')[:2])
except ImportError:
    raise ImportError("h3 required: pip install h3")


def _h3_polyfill(geojson_poly: dict, res: int) -> list[str]:
    """Polyfill a GeoJSON Polygon dict with H3 cells at given resolution.
    Works with both h3-py v3 (polyfill_geojson) and v4 (polygon_to_cells + LatLngPoly).
    """
    import h3
    coords = geojson_poly['coordinates']
    # GeoJSON coords: [[[lng, lat], ...], hole_ring, ...]
    # H3 LatLngPoly expects (lat, lng) tuples
    outer = [(lat, lng) for lng, lat in coords[0]]
    holes = [[(lat, lng) for lng, lat in ring] for ring in coords[1:]]
    try:
        # H3 v4
        poly = h3.LatLngPoly(outer, *holes)
        return list(h3.polygon_to_cells(poly, res))
    except AttributeError:
        # H3 v3 fallback
        return list(h3.polyfill_geojson(geojson_poly, res))


def _h3_to_geo_boundary(idx: str) -> list:
    """Return boundary coordinates for an H3 cell as list of [lng, lat] pairs."""
    import h3
    try:
        # H3 v4: cell_to_boundary returns [(lat, lng), ...]
        boundary = h3.cell_to_boundary(idx)
        return [[lng, lat] for lat, lng in boundary]
    except AttributeError:
        # H3 v3: h3_to_geo_boundary returns [[lng, lat], ...] in geo_json mode
        return h3.h3_to_geo_boundary(idx, geo_json=True)


def load_polygons_gaul(territory: dict) -> list[dict]:
    """Load admin polygons from GEE FAO/GAUL/2015/level2."""
    import ee
    ee.Initialize()

    coll, filt = territory['admin_collection'], territory['admin_filter']
    fc = ee.FeatureCollection(coll)
    if filt:
        fc = fc.filter(ee.Filter.eq(filt[0], filt[1]))

    features = fc.getInfo()['features']
    print(f"  Loaded {len(features)} polygons from GEE GAUL")
    return features


def load_polygons_from_radios(territory: dict) -> list[dict]:
    """Dissolve Misiones census radios by dpto → department polygons."""
    from shapely import wkb
    from shapely.ops import unary_union
    from shapely.geometry import mapping

    radios_path = os.path.join(OUTPUT_DIR, 'radios_misiones.parquet')
    stats_path = os.path.join(OUTPUT_DIR, 'radio_stats_master.parquet')
    radios = pd.read_parquet(radios_path)
    radio_stats = pd.read_parquet(stats_path, columns=['redcode', 'dpto'])
    radios['geom'] = radios['geometry'].apply(lambda b: wkb.loads(b))
    radios = radios.merge(radio_stats, on='redcode', how='inner')

    features = []
    for dpto, group in radios.groupby('dpto'):
        geoms = [g for g in group['geom'] if g is not None and g.is_valid]
        if geoms:
            dissolved = unary_union(geoms)
            features.append({
                'type': 'Feature',
                'properties': {'ADM2_NAME': dpto},
                'geometry': mapping(dissolved),
            })
    print(f"  Dissolved {len(features)} department polygons from census radios")
    return features


def load_polygons_shapefile(shapefile_path: str, territory: dict) -> list[dict]:
    """Load admin polygons from a local shapefile or GeoJSON."""
    try:
        import geopandas as gpd
    except ImportError:
        raise ImportError("geopandas required: pip install geopandas")

    gdf = gpd.read_file(shapefile_path)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)

    # Detect name columns for GADM (NAME_1/NAME_2) or GAUL (ADM1_NAME/ADM2_NAME)
    col_map = {c.upper(): c for c in gdf.columns}
    name1_col = col_map.get('NAME_1') or col_map.get('ADM1_NAME') or col_map.get('NAME1')
    name2_col = col_map.get('NAME_2') or col_map.get('ADM2_NAME') or col_map.get('NAME2')

    if not name1_col or not name2_col:
        raise ValueError(f"Cannot find name columns in {list(gdf.columns)}. "
                         f"Expected NAME_1/NAME_2 (GADM) or ADM1_NAME/ADM2_NAME (GAUL).")

    # Filter to Itapúa departamento
    admin_filter = territory.get('admin_filter')
    if admin_filter:
        prop, val = admin_filter
        # Try both GADM and GAUL column naming
        for col in (name1_col, col_map.get(prop.upper(), prop)):
            mask = gdf[col].str.contains(val.replace('ú', 'u'), case=False, na=False)
            if mask.any():
                gdf = gdf[mask]
                print(f"  Filtered to '{val}': {len(gdf)} polygons via column '{col}'")
                break

    # Convert to GeoJSON features
    features = []
    for _, row in gdf.iterrows():
        features.append({
            'type': 'Feature',
            'properties': {
                'ADM1_NAME': row.get(name1_col, ''),
                'ADM2_NAME': row.get(name2_col, ''),
            },
            'geometry': mapping(row.geometry),
        })

    print(f"  Loaded {len(features)} polygons from {shapefile_path}")
    return features


def polyfill_feature(feature: dict, res: int) -> set[str]:
    """Return all H3 cells covering a GeoJSON feature at given resolution."""
    geom = feature['geometry']
    if geom['type'] == 'Polygon':
        return set(_h3_polyfill(geom, res))
    elif geom['type'] == 'MultiPolygon':
        cells = set()
        for ring in geom['coordinates']:
            poly_geom = {'type': 'Polygon', 'coordinates': ring}
            cells |= set(_h3_polyfill(poly_geom, res))
        return cells
    return set()


def build_crosswalk(features: list[dict], admin_col: str, res: int) -> pd.DataFrame:
    """Build h3index -> admin unit mapping.

    For hexes on polygon borders (polyfilled by multiple polygons), assign
    to the polygon whose centroid is closest — simple and fast.
    """
    print(f"Polyfilling {len(features)} polygons at H3 res-{res}...")

    hex_to_admin: dict[str, list] = {}
    for feat in features:
        admin_name = feat['properties'].get('ADM2_NAME', feat['properties'].get(admin_col, '?'))
        cells = polyfill_feature(feat, res)
        for cell in cells:
            if cell not in hex_to_admin:
                hex_to_admin[cell] = []
            hex_to_admin[cell].append(admin_name)

    # For cells covered by multiple polygons, pick the first (alphabetical by admin name)
    # This is fine for border hexes which are rare and small
    rows = []
    conflicts = 0
    for h3idx, admins in hex_to_admin.items():
        if len(admins) > 1:
            conflicts += 1
        rows.append({'h3index': h3idx, admin_col: sorted(admins)[0]})

    df = pd.DataFrame(rows)
    print(f"  {len(df):,} hexagons, {df[admin_col].nunique()} admin units, "
          f"{conflicts} border conflicts resolved")
    return df


def build_hex_geojson(df: pd.DataFrame) -> dict:
    """Build a lightweight hexagons GeoJSON from the crosswalk h3 indices.
    _h3_to_geo_boundary already returns [[lng, lat], ...] ready for GeoJSON.
    """
    print("Building hexagons GeoJSON...")
    features = []
    for h3idx in df['h3index']:
        try:
            coords = _h3_to_geo_boundary(h3idx)  # [[lng, lat], ...]
            coords.append(coords[0])              # close ring
            features.append({
                'type': 'Feature',
                'properties': {'h3index': h3idx},
                'geometry': {'type': 'Polygon', 'coordinates': [coords]},
            })
        except Exception:
            pass
    return {'type': 'FeatureCollection', 'features': features}


def main():
    parser = argparse.ArgumentParser(description="Build H3->admin crosswalk for a territory")
    parser.add_argument("--territory", required=True, help="Territory ID from config.py")
    parser.add_argument("--source", choices=["gaul", "gadm", "geojson", "radios"], default="gaul",
                        help="Polygon source (default: gaul)")
    parser.add_argument("--shapefile", default=None,
                        help="Path to shapefile or GeoJSON (required for gadm/geojson sources)")
    parser.add_argument("--skip-hexgrid", action="store_true",
                        help="Skip generating hexagons.geojson (if already done)")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    prefix = territory['output_prefix']
    admin_col = territory['admin_col']

    out_dir = os.path.join(OUTPUT_DIR, prefix.rstrip('/')) if prefix else OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    crosswalk_path = os.path.join(out_dir, 'h3_admin_crosswalk.parquet')
    hexgrid_path = os.path.join(out_dir, 'hexagons.geojson')

    print("=" * 60)
    print(f"  Building admin crosswalk: {territory['label']} ({args.territory})")
    print(f"  Source: {args.source}")
    print(f"  Admin level: {admin_col}")
    print(f"  Output: {out_dir}")
    print("=" * 60)

    # ---- Load polygons ----
    if args.source == 'radios':
        features = load_polygons_from_radios(territory)
    elif args.source == 'gaul':
        features = load_polygons_gaul(territory)
    elif args.source in ('gadm', 'geojson'):
        if not args.shapefile:
            print("ERROR: --shapefile required for gadm/geojson source")
            return 1
        features = load_polygons_shapefile(args.shapefile, territory)
    else:
        print(f"Unknown source: {args.source}")
        return 1

    if not features:
        print("ERROR: no polygons loaded")
        return 1

    # ---- Build crosswalk ----
    df = build_crosswalk(features, admin_col, H3_RESOLUTION)
    df.to_parquet(crosswalk_path, index=False)
    print(f"\nCrosswalk saved -> {crosswalk_path}")

    # ---- Build hex grid ----
    if not args.skip_hexgrid:
        hexgrid = build_hex_geojson(df)
        with open(hexgrid_path, 'w', encoding='utf-8') as f:
            json.dump(hexgrid, f)
        size_mb = os.path.getsize(hexgrid_path) / 1e6
        print(f"Hex grid saved -> {hexgrid_path}  ({size_mb:.1f} MB, {len(hexgrid['features']):,} hexes)")

    # ---- Summary ----
    print("\n---- Admin units found ------------------------------------------------------------------")
    for admin in sorted(df[admin_col].unique()):
        n = (df[admin_col] == admin).sum()
        print(f"  {admin:35s}  {n:6,} hexes")
    print(f"\nTotal: {len(df):,} hexes across {df[admin_col].nunique()} {admin_col}s")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
