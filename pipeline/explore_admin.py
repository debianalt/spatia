"""
Compare GAUL (GEE built-in) vs GADM 4.1 admin boundaries for any territory.

Generalized from explore_itapua_admin.py — reads admin_collection / admin_filter
from TERRITORY_CONFIGS so it works for itapua_py, alto_parana_py, etc.

Usage:
  python pipeline/explore_admin.py --territory alto_parana_py
  python pipeline/explore_admin.py --territory alto_parana_py --gadm-path pipeline/data/PRY_adm2.shp
  python pipeline/explore_admin.py --territory alto_parana_py --export-geojson

What this checks:
  1. <admin_collection> filtered by <admin_filter> -> lists distrito names + count
  2. If the exact filter returns 0 features, lists all ADM1_NAME values for the
     country so the correct spelling can be discovered (GAUL accent quirks).
  3. If --gadm-path provided: loads GADM level-2, compares names.
  4. Prints recommendation: GAUL or GADM (gate on count vs official census).

GADM 4.1 download (if GAUL count != official):
  https://gadm.org/download_country.html -> Paraguay -> Shapefile
  Unzip, use PRY_adm2.shp (level 2 = distritos). NAME_1 = departamento.
"""

import json
import os
import sys
import argparse

from config import OUTPUT_DIR, get_territory

# ADM0_NAME in FAO/GAUL/2015 for each country code (for discovery fallback)
GAUL_ADM0 = {'py': 'Paraguay', 'ar': 'Argentina', 'br': 'Brazil'}


def check_gaul(territory: dict) -> list[dict]:
    """Query the territory's admin_collection with its admin_filter."""
    try:
        import ee
        ee.Initialize()
    except Exception as e:
        print(f"  GEE init failed: {e}")
        return []

    coll = territory['admin_collection']
    prop, val = territory['admin_filter']
    print(f"Querying {coll} for {prop} = '{val}'...")
    fc = ee.FeatureCollection(coll).filter(ee.Filter.eq(prop, val))
    info = fc.getInfo()
    features = info.get('features', [])

    if not features:
        print(f"  0 features for {prop}='{val}'. Listing all ADM1_NAME "
              f"for the country to discover the correct spelling...")
        _discover_adm1(coll, territory)
        return []

    records = []
    for f in features:
        p = f.get('properties', {})
        records.append({
            'name': p.get('ADM2_NAME', '?'),
            'adm1': p.get('ADM1_NAME', '?'),
            'adm0': p.get('ADM0_NAME', '?'),
            'gaul_code': p.get('ADM2_CODE', '?'),
        })
    records.sort(key=lambda r: r['name'])
    return records


def _discover_adm1(coll: str, territory: dict) -> None:
    """List distinct ADM1_NAME values for the territory's country."""
    try:
        import ee
        adm0 = GAUL_ADM0.get(territory['country'])
        if not adm0:
            return
        fc = ee.FeatureCollection(coll).filter(ee.Filter.eq('ADM0_NAME', adm0))
        names = sorted(set(fc.aggregate_array('ADM1_NAME').getInfo()))
        print(f"  ADM1_NAME values in {adm0}:")
        for n in names:
            print(f"    - {n!r}")
    except Exception as e:
        print(f"  discovery failed: {e}")


def check_gaul_geom(territory: dict) -> list[dict]:
    """Full GAUL features (with geometry) for GeoJSON export."""
    try:
        import ee
        ee.Initialize()
    except Exception:
        return []
    coll = territory['admin_collection']
    prop, val = territory['admin_filter']
    fc = ee.FeatureCollection(coll).filter(ee.Filter.eq(prop, val))
    return fc.getInfo().get('features', [])


def export_gaul_geojson(territory_id: str, features: list[dict]) -> None:
    out_path = os.path.join(OUTPUT_DIR, f'{territory_id}_gaul_distritos.geojson')
    geojson = {'type': 'FeatureCollection', 'features': features}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"  Saved GAUL polygons -> {out_path}")


def check_gadm(gadm_path: str, territory: dict) -> list[dict]:
    """Load local GADM 4.1 shapefile and return district records.

    Filters NAME_1 by the substring of the territory's admin_filter value.
    """
    try:
        import geopandas as gpd
    except ImportError:
        print("  geopandas required: pip install geopandas")
        return []

    print(f"Loading GADM from {gadm_path}...")
    gdf = gpd.read_file(gadm_path)
    name1_col = next((c for c in gdf.columns if c.upper() in ('NAME_1', 'NAME1')), None)
    name2_col = next((c for c in gdf.columns if c.upper() in ('NAME_2', 'NAME2')), None)
    if not name1_col or not name2_col:
        print(f"  Unexpected columns: {list(gdf.columns)}")
        return []

    # Match on the first significant token of the admin_filter value
    needle = territory['admin_filter'][1].split()[0][:4]
    sub = gdf[gdf[name1_col].str.contains(needle, case=False, na=False)]
    records = [{'name': r[name2_col], 'adm1': r[name1_col]} for _, r in sub.iterrows()]
    records.sort(key=lambda r: r['name'])
    return records


def compare(gaul: list[dict], gadm: list[dict]) -> None:
    gaul_names = {r['name'] for r in gaul}
    gadm_names = {r['name'] for r in gadm}
    only_gaul = gaul_names - gadm_names
    only_gadm = gadm_names - gaul_names
    both = gaul_names & gadm_names
    print(f"\n  Shared: {len(both)}")
    print(f"  Only in GAUL ({len(only_gaul)}): {sorted(only_gaul)}")
    print(f"  Only in GADM ({len(only_gadm)}): {sorted(only_gadm)}")
    if not only_gaul and not only_gadm:
        print("  OK Names match exactly — either source is fine")
    else:
        print("  WARNING Differences found — use GADM 4.1 for consistency")


def main():
    parser = argparse.ArgumentParser(description="Explore admin boundaries: GAUL vs GADM")
    parser.add_argument("--territory", required=True, help="Territory ID from config.py")
    parser.add_argument("--gadm-path", default=None,
                        help="Path to GADM level-2 shapefile (e.g. PRY_adm2.shp)")
    parser.add_argument("--official-count", type=int, default=None,
                        help="Official district count (e.g. 22 for Alto Paraná DGEEC 2022) to gate against")
    parser.add_argument("--export-geojson", action="store_true",
                        help="Export GAUL polygons to GeoJSON for QGIS inspection")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    territory = get_territory(args.territory)
    tid = territory['id']

    print("=" * 60)
    print(f"  Admin Boundary Explorer — {territory['label']} ({tid})")
    print("=" * 60)

    gaul_records = check_gaul(territory)
    print(f"\nGAUL — {territory['label']}: {len(gaul_records)} features")
    for r in gaul_records:
        print(f"  {r['name']:30s}  (GAUL code: {r['gaul_code']}, ADM1: {r['adm1']!r})")

    if args.export_geojson and gaul_records:
        export_gaul_geojson(tid, check_gaul_geom(territory))

    if args.gadm_path:
        gadm_records = check_gadm(args.gadm_path, territory)
        print(f"\nGADM 4.1 — {territory['label']}: {len(gadm_records)} features")
        for r in gadm_records:
            print(f"  {r['name']}")
        print("\n-- Comparison -------------------------------------------")
        compare(gaul_records, gadm_records)
    else:
        print("\nNo --gadm-path provided. If GAUL count != official, download:")
        print("  https://gadm.org/download_country.html -> Paraguay -> Shapefile")

    print("\n-- Recommendation ---------------------------------------")
    n = len(gaul_records)
    official = args.official_count
    if n == 0:
        print("  GAUL query failed / wrong ADM1_NAME. Fix admin_filter or use GADM.")
    elif official is not None and n != official:
        print(f"  GAUL has {n} distritos but official is {official}. "
              f"MISMATCH -> use GADM 4.1 (--source gadm in build_admin_crosswalk).")
    elif official is not None and n == official:
        print(f"  GAUL has {n} distritos == official {official}. OK -> proceed with GAUL.")
    else:
        print(f"  GAUL has {n} distritos. Pass --official-count to gate, "
              f"or --gadm-path to compare names.")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
