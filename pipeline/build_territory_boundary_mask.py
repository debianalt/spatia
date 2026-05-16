"""
Generate <territory>_boundary.json + <territory>_mask.json for the frontend
from an admin district GeoJSON (dissolve of all districts).

- boundary: single Feature. Geometry is the dissolved department outline,
  simplified. Reduced to the largest exterior ring (Polygon) so the existing
  point-in-polygon util pattern (boundary.geometry.coordinates[0]) works
  unchanged. River islets are negligible for territory detection.
- mask: FeatureCollection, one Polygon whose OUTER ring is a regional box
  (NOT the world bbox — a 360x180 hole breaks earcut/WebGL; see Corrientes
  lesson) and whose hole is the department outline → "fog" outside territory.

Also prints the padded bbox so config.py can be refined from real extent.

Usage:
  python pipeline/build_territory_boundary_mask.py \
    --territory alto_parana_py \
    --admin-geojson pipeline/output/alto_parana_py_ine_distritos.geojson \
    --name "Alto Parana"
"""

import argparse
import json
import os
import sys

# Generous regional outer ring covering the whole NEA + PY/BR working area.
# Mirrors the Corrientes-safe approach (regional, not world bbox).
REGIONAL_RING = [[-80, -60], [80, -60], [80, 10], [-80, 10], [-80, -60]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--territory", required=True)
    ap.add_argument("--admin-geojson", required=True,
                    help="District GeoJSON (e.g. <tid>_ine_distritos.geojson)")
    ap.add_argument("--name", required=True, help="boundary properties.name")
    ap.add_argument("--simplify", type=float, default=0.002,
                    help="Douglas-Peucker tolerance in degrees (~200m)")
    ap.add_argument("--out-dir", default="src/lib/data")
    args = ap.parse_args()

    import geopandas as gpd
    from shapely.ops import unary_union
    from shapely.geometry import mapping, Polygon

    gdf = gpd.read_file(args.admin_geojson)
    dissolved = unary_union(gdf.geometry.values)
    dissolved = dissolved.simplify(args.simplify, preserve_topology=True)

    # Largest polygon's exterior ring (department is one contiguous landmass)
    if dissolved.geom_type == "MultiPolygon":
        polys = sorted(dissolved.geoms, key=lambda p: p.area, reverse=True)
        dropped = len(polys) - 1
        main_poly = polys[0]
        if dropped:
            print(f"  NOTE: dropped {dropped} small polygon(s) (river islets) "
                  f"from boundary; kept largest (area share "
                  f"{main_poly.area / dissolved.area:.4%}).")
    else:
        main_poly = dissolved

    ring = [[round(x, 6), round(y, 6)] for x, y in main_poly.exterior.coords]
    minx, miny, maxx, maxy = main_poly.bounds

    os.makedirs(args.out_dir, exist_ok=True)
    tid = args.territory

    boundary = {
        "type": "Feature",
        "properties": {"name": args.name},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }
    b_path = os.path.join(args.out_dir, f"{_stem(tid)}_boundary.json")
    with open(b_path, "w", encoding="utf-8") as f:
        json.dump(boundary, f, ensure_ascii=False)

    mask = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [REGIONAL_RING, ring]},
        }],
    }
    m_path = os.path.join(args.out_dir, f"{_stem(tid)}_mask.json")
    with open(m_path, "w", encoding="utf-8") as f:
        json.dump(mask, f, ensure_ascii=False)

    pad = 0.10
    bbox = [round(minx - pad, 2), round(miny - pad, 2),
            round(maxx + pad, 2), round(maxy + pad, 2)]
    print(f"  boundary -> {b_path}  ({len(ring)} pts)")
    print(f"  mask     -> {m_path}")
    print(f"  raw bounds [W,S,E,N]: "
          f"[{minx:.4f}, {miny:.4f}, {maxx:.4f}, {maxy:.4f}]")
    print(f"  CONFIG bbox (padded {pad}): {bbox}")
    return 0


def _stem(tid: str) -> str:
    """alto_parana_py -> alto_parana (matches itapua_boundary.json convention)."""
    for suf in ("_py", "_br", "_ar"):
        if tid.endswith(suf):
            return tid[: -len(suf)]
    return tid


if __name__ == "__main__":
    sys.exit(main())
