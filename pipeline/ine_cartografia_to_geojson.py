"""
Convert an INE Paraguay 2022 census cartography "Distritos" shapefile into the
canonical admin GeoJSON consumed by build_admin_crosswalk.py (--source geojson)
and the per-territory district builder.

Why this exists: GAUL 2015 and GADM 4.1 both lag the DGEEC 2022 district
roster (e.g. Alto Paraná: 18 vs official 22 — missing Iruña, Santa Fe del
Paraná, Dr. Raúl Peña, Tavapy, all created post-2015). The INE 2022 census
cartography is the authoritative source and its district names/codes match the
DGEEC census tables used downstream (Phase 3).

Source rar: https://www.ine.gov.py/microdatos/cartografia-digital-2022.php
  -> CARTOGRAFIA CENSAL_SHP -> "<NN> <DEPTO>.rar" -> "Distritos_<Depto>.shp"

Columns in the INE shp: DPTO, DPTO_DESC, DISTRITO, DIST_DESC_, CLAVE
  CLAVE = DPTO*100 + DISTRITO (stable numeric district code, 1001..1022).

Output properties (mirrors GAUL/GADM convention so downstream is unchanged):
  ADM1_NAME (department), ADM2_NAME (district, INE official upper-case verbatim),
  DIST_CODE (CLAVE, for robust census joins in Phase 3).

Usage:
  python pipeline/ine_cartografia_to_geojson.py \
    --territory alto_parana_py \
    --shp "pipeline/data/ine_ap/10 ALTO PARANA/Distritos_Alto Parana.shp"
"""

import argparse
import json
import os
import sys

from config import OUTPUT_DIR, get_territory


def main() -> int:
    parser = argparse.ArgumentParser(description="INE 2022 Distritos shp -> canonical admin GeoJSON")
    parser.add_argument("--territory", required=True, help="Territory ID from config.py")
    parser.add_argument("--shp", required=True, help="Path to INE 'Distritos_<Depto>.shp'")
    parser.add_argument("--name-col", default="DIST_DESC_", help="District name column (default INE)")
    parser.add_argument("--dpto-col", default="DPTO_DESC", help="Department name column")
    parser.add_argument("--code-col", default="CLAVE", help="District numeric code column")
    args = parser.parse_args()

    import geopandas as gpd

    territory = get_territory(args.territory)
    tid = territory['id']

    # pyogrio honours the .cpg (UTF-8); names come through clean.
    gdf = gpd.read_file(args.shp, engine="pyogrio", encoding="UTF-8")
    for col in (args.name_col, args.dpto_col, args.code_col):
        if col not in gdf.columns:
            print(f"ERROR: column {col!r} not in {list(gdf.columns)}")
            return 1

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        print(f"  Reprojecting {gdf.crs} -> EPSG:4326")
        gdf = gdf.to_crs(4326)

    gdf = gdf.dropna(subset=["geometry"])
    n = len(gdf)
    from shapely.geometry import mapping

    features = []
    for _, row in gdf.iterrows():
        features.append({
            "type": "Feature",
            "properties": {
                "ADM1_NAME": str(row[args.dpto_col]).strip(),
                # INE official name, verbatim upper-case (authoritative, lossless).
                # Case-folding to match the DGEEC census CSV is done at the
                # Phase 3 join, not guessed here.
                "ADM2_NAME": str(row[args.name_col]).strip(),
                "DIST_CODE": int(row[args.code_col]),
            },
            "geometry": mapping(row.geometry),
        })

    out_path = os.path.join(OUTPUT_DIR, f"{tid}_ine_distritos.geojson")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f,
                  ensure_ascii=False)

    names = sorted(p["properties"]["ADM2_NAME"] for p in features)
    print(f"  {n} districts -> {out_path}")
    for nm in names:
        print(f"    {nm}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
