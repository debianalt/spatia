"""
Ingest walkthru.earth Overture Indices into Spatia H3 grid.

Downloads H3-indexed Overture data from Source Cooperative, filters to Misiones
using res-5 parent cells, converts h3_index BIGINT to h3index VARCHAR, and
writes Misiones-only parquets.

Source: https://source.coop/walkthru-earth/walkthru-indices
License: CC BY 4.0

Usage:
  python pipeline/ingest_overture.py                          # all themes
  python pipeline/ingest_overture.py --theme buildings        # single theme
  python pipeline/ingest_overture.py --release 2026-03-18.0   # specific release
"""

import json
import os
import sys
import time

import duckdb
import h3

from config import (
    OVERTURE_BASE_URL,
    OVERTURE_RELEASE,
    OVERTURE_THEMES,
    OUTPUT_DIR,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BOUNDARY_PATH = os.path.join(PROJECT_ROOT, "src", "lib", "data", "misiones_boundary.json")

PARENT_RES = 5


def load_boundary() -> dict:
    """Load Misiones boundary GeoJSON geometry."""
    with open(BOUNDARY_PATH, "r", encoding="utf-8") as f:
        geojson = json.load(f)
    if geojson.get("type") == "FeatureCollection":
        return geojson["features"][0]["geometry"]
    elif geojson.get("type") == "Feature":
        return geojson["geometry"]
    return geojson


def get_misiones_parent_cells() -> list[int]:
    """Generate H3 res-5 parent cell BIGINTs covering Misiones.

    Uses a ~15 km buffer around the boundary to ensure border cells
    (e.g. Posadas on the Paraná river) are fully included.
    """
    from shapely.geometry import shape

    boundary = load_boundary()
    buffered = shape(boundary).buffer(0.15)  # ~15 km in degrees
    parent_cells = list(h3.geo_to_cells(buffered.__geo_interface__, res=PARENT_RES))
    bigints = [int(c, 16) for c in parent_cells]
    print(f"  Misiones covered by {len(bigints)} H3 res-{PARENT_RES} parent cells (buffered)")
    return bigints


def ingest_theme(conn: duckdb.DuckDBPyConnection, theme: str,
                 parent_bigints: list[int], release: str) -> str | None:
    """
    Query remote Overture parquet for a single theme, filter to Misiones,
    convert h3_index BIGINT → h3index VARCHAR, save locally.

    Returns output path on success, None on failure.
    """
    url = OVERTURE_BASE_URL.format(theme=theme, release=release)
    output_path = os.path.join(OUTPUT_DIR, f"overture_{theme}.parquet")

    print(f"\n  Theme: {theme}")
    print(f"  Source: {url}")

    parent_list = ",".join(str(x) for x in parent_bigints)

    sql = f"""
        COPY (
            SELECT
                h3_h3_to_string(h3_index) AS h3index,
                * EXCLUDE (h3_index)
            FROM read_parquet('{url}')
            WHERE h3_cell_to_parent(h3_index, {PARENT_RES})
                  IN ({parent_list})
        ) TO '{output_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """

    t0 = time.time()
    try:
        conn.execute(sql)
    except duckdb.Error as e:
        print(f"  ERROR querying {theme}: {e}")
        return None

    elapsed = time.time() - t0

    if not os.path.exists(output_path):
        print(f"  ERROR: output file not created")
        return None

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    row_count = conn.execute(
        f"SELECT count(*) FROM read_parquet('{output_path}')"
    ).fetchone()[0]

    print(f"  -> {row_count:,} rows, {size_mb:.1f} MB, {elapsed:.1f}s")
    print(f"  -> Saved to {output_path}")

    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ingest Overture Indices for Misiones")
    parser.add_argument("--theme", choices=OVERTURE_THEMES,
                        help="Single theme to ingest (default: all)")
    parser.add_argument("--release", default=OVERTURE_RELEASE,
                        help=f"Overture release version (default: {OVERTURE_RELEASE})")
    args = parser.parse_args()

    themes = [args.theme] if args.theme else OVERTURE_THEMES

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  Overture Indices Ingestion")
    print(f"  Release: {args.release}")
    print(f"  Themes: {', '.join(themes)}")
    print("=" * 60)

    print("\nLoading Misiones boundary...")
    parent_bigints = get_misiones_parent_cells()

    print("\nInitialising DuckDB with H3 + httpfs extensions...")
    conn = duckdb.connect()
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    conn.execute("INSTALL h3 FROM community; LOAD h3;")

    results = {}
    start = time.time()

    for theme in themes:
        path = ingest_theme(conn, theme, parent_bigints, args.release)
        results[theme] = path

    conn.close()

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"  Summary ({elapsed:.0f}s total)")
    print(f"{'=' * 60}")

    ok = 0
    for theme, path in results.items():
        if path:
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"  [ok] {theme}: {size_mb:.1f} MB")
            ok += 1
        else:
            print(f"  [FAIL] {theme}")

    print(f"\n  {ok}/{len(themes)} themes ingested successfully")
    return 0 if ok == len(themes) else 1


if __name__ == "__main__":
    sys.exit(main())
