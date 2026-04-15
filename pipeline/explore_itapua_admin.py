"""
Compare GAUL (GEE built-in) vs GADM 4.1 (local shapefile) admin boundaries for Itapúa.

Usage:
  python pipeline/explore_itapua_admin.py               # GAUL only (no GADM file needed)
  python pipeline/explore_itapua_admin.py --gadm-path pipeline/data/gadm_itapua.shp

What this checks:
  1. FAO/GAUL/2015/level2 filtered to ADM1_NAME = 'Itapúa' -> lists all distrito names + count
  2. If --gadm-path provided: loads GADM level-2 for Itapúa, compares names
  3. Exports GAUL polygons to pipeline/output/itapua_gaul_distritos.geojson for visual inspection
  4. Prints recommendation: GAUL or GADM

GADM 4.1 download:
  https://gadm.org/download_country.html -> Paraguay -> Shapefile
  Unzip, use PRY_adm2.shp (level 2 = distritos)
  Filter to NAME_1 = 'Itapúa'
"""

import json
import os
import sys
import argparse

from config import OUTPUT_DIR, TERRITORY_CONFIGS

ITAPUA_BBOX = TERRITORY_CONFIGS['itapua_py']['bbox']  # [W, S, E, N]


def check_gaul() -> list[dict]:
    """Query GEE GAUL/2015/level2 for Itapúa and return list of district records."""
    try:
        import ee
        ee.Initialize()
    except Exception as e:
        print(f"  GEE init failed: {e}")
        return []

    print("Querying FAO/GAUL/2015/level2 for ADM1_NAME = 'Itapúa'...")
    gaul = (ee.FeatureCollection('FAO/GAUL/2015/level2')
              .filter(ee.Filter.eq('ADM1_NAME', 'Itapúa')))

    info = gaul.getInfo()
    features = info.get('features', [])
    records = []
    for f in features:
        props = f.get('properties', {})
        records.append({
            'name': props.get('ADM2_NAME', '?'),
            'adm1': props.get('ADM1_NAME', '?'),
            'adm0': props.get('ADM0_NAME', '?'),
            'gaul_code': props.get('ADM2_CODE', '?'),
        })
    records.sort(key=lambda r: r['name'])
    return records


def export_gaul_geojson(records_with_geom: list[dict]) -> None:
    """Write GAUL polygons to GeoJSON for visual inspection in QGIS."""
    out_path = os.path.join(OUTPUT_DIR, 'itapua_gaul_distritos.geojson')
    geojson = {'type': 'FeatureCollection', 'features': records_with_geom}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"  Saved GAUL polygons -> {out_path}")


def check_gaul_geom() -> list[dict]:
    """Full GAUL features (with geometry) for GeoJSON export."""
    try:
        import ee
        ee.Initialize()
    except Exception:
        return []

    gaul = (ee.FeatureCollection('FAO/GAUL/2015/level2')
              .filter(ee.Filter.eq('ADM1_NAME', 'Itapúa')))
    return gaul.getInfo().get('features', [])


def check_gadm(gadm_path: str) -> list[dict]:
    """Load local GADM 4.1 shapefile for Itapúa and return district records.

    Expects PRY_adm2.shp (GADM level 2 for Paraguay).
    NAME_1 = departamento, NAME_2 = distrito.
    """
    try:
        import geopandas as gpd
    except ImportError:
        print("  geopandas required: pip install geopandas")
        return []

    print(f"Loading GADM from {gadm_path}...")
    gdf = gpd.read_file(gadm_path)

    # Try different column patterns (GADM 3.x vs 4.x)
    name1_col = next((c for c in gdf.columns if c.upper() in ('NAME_1', 'NAME1')), None)
    name2_col = next((c for c in gdf.columns if c.upper() in ('NAME_2', 'NAME2')), None)

    if not name1_col or not name2_col:
        print(f"  Unexpected columns: {list(gdf.columns)}")
        return []

    itapua = gdf[gdf[name1_col].str.contains('Itap', case=False, na=False)]
    records = []
    for _, row in itapua.iterrows():
        records.append({
            'name': row[name2_col],
            'adm1': row[name1_col],
        })
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
    parser = argparse.ArgumentParser(description="Explore Itapúa admin boundaries: GAUL vs GADM")
    parser.add_argument("--gadm-path", default=None,
                        help="Path to GADM level-2 shapefile (PRY_adm2.shp)")
    parser.add_argument("--export-geojson", action="store_true",
                        help="Export GAUL polygons to GeoJSON for QGIS inspection")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  Itapúa Admin Boundary Explorer")
    print("=" * 60)

    # ── GAUL ──
    gaul_records = check_gaul()
    print(f"\nGAUL level2 — Itapúa: {len(gaul_records)} features")
    for r in gaul_records:
        print(f"  {r['name']:30s}  (GAUL code: {r['gaul_code']})")

    if args.export_geojson:
        features_with_geom = check_gaul_geom()
        export_gaul_geojson(features_with_geom)

    # ── GADM ──
    if args.gadm_path:
        gadm_records = check_gadm(args.gadm_path)
        print(f"\nGADM 4.1 — Itapúa: {len(gadm_records)} features")
        for r in gadm_records:
            print(f"  {r['name']}")

        print("\n── Comparison ─────────────────────────────────────────")
        compare(gaul_records, gadm_records)
    else:
        print("\nNo --gadm-path provided. Download from:")
        print("  https://gadm.org/download_country.html -> Paraguay -> Shapefile")
        print("  Then: python explore_itapua_admin.py --gadm-path pipeline/data/PRY_adm2.shp")

    print("\n── Recommendation ─────────────────────────────────────")
    if len(gaul_records) == 0:
        print("  GAUL query failed. Use GADM 4.1.")
    elif len(gaul_records) < 25:
        print(f"  GAUL only has {len(gaul_records)} units — likely missing some distritos. Use GADM 4.1.")
    else:
        print(f"  GAUL has {len(gaul_records)} distritos. Run with --gadm-path to compare names.")

    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
