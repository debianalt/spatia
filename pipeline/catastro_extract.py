"""
Catastro Misiones: WFS extraction with change tracking (no PostgreSQL).

Source: Catastro Misiones WFS (https://www.servicios.catastro.misiones.gov.ar/ows)
  - mapa:parcela_rural (~105k polygons)
  - mapa:parcela_urbana (~340k polygons)

Paginated download (10k features per batch), CRS EPSG:22177 -> EPSG:4326.
Change tracking via parquet diff (first_seen/last_updated per parcel).
Spatial aggregation via GeoPandas sjoin (centroid-in-radio).

Outputs:
  catastro_state/catastro_rural.parquet    — rural parcels with tracking dates
  catastro_state/catastro_urbano.parquet   — urban parcels with tracking dates
  catastro_by_radio.parquet                — parcel counts/area per radio
  catastro_changes_summary.parquet         — change log (new/removed per run)

Usage standalone:  python catastro_extract.py [--output-dir DIR]
Usage as module:   from catastro_extract import run_extraction
"""

import os
import sys
import time
import warnings
from datetime import date, timedelta

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon
from shapely.validation import make_valid

try:
    import requests
except ImportError:
    requests = None

DATA_YEAR = 2026

WFS_BASE = "https://www.servicios.catastro.misiones.gov.ar/ows"
BATCH_SIZE = 10000

LAYERS = {
    "rural": "mapa:parcela_rural",
    "urbano": "mapa:parcela_urbana",
}


# ── WFS download ─────────────────────────────────────────────────────────────


def download_wfs_paginated(layer_name, label):
    """Download WFS with pagination for large layers."""
    print(f"  Downloading {label}...", end=" ", flush=True)
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    t0 = time.time()

    all_features = []
    offset = 0

    while True:
        url = (
            f"{WFS_BASE}?service=WFS&version=1.0.0&request=GetFeature"
            f"&typeName={layer_name}"
            f"&outputFormat=application/json"
            f"&maxFeatures={BATCH_SIZE}&startIndex={offset}"
        )
        try:
            resp = requests.get(url, verify=False, timeout=180)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            print(f"\n  Timeout at offset {offset}, retrying...", end=" ", flush=True)
            time.sleep(5)
            try:
                resp = requests.get(url, verify=False, timeout=300)
                resp.raise_for_status()
            except Exception as e:
                print(f"\n  Failed at offset {offset}: {e}")
                break
        except Exception as e:
            print(f"\n  Failed at offset {offset}: {e}")
            break

        data = resp.json()
        feats = data.get("features", [])
        if not feats:
            break
        all_features.extend(feats)
        offset += BATCH_SIZE

        if len(all_features) % 50000 < BATCH_SIZE:
            print(f"{len(all_features):,}...", end=" ", flush=True)

    elapsed = time.time() - t0
    print(f"{len(all_features):,} features in {elapsed:.0f}s")
    return {"type": "FeatureCollection", "features": all_features}


def parse_and_reproject(geojson, src_crs="EPSG:22177"):
    """Parse GeoJSON, fix geometry, set CRS and reproject to 4326."""
    if not geojson["features"]:
        return gpd.GeoDataFrame()

    gdf = gpd.GeoDataFrame.from_features(geojson["features"])

    if gdf.crs is None:
        bounds = gdf.total_bounds
        if bounds[0] > 1000:
            gdf = gdf.set_crs(src_crs)
        else:
            gdf = gdf.set_crs("EPSG:4326")

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        print(f"  Reprojecting from {gdf.crs} to EPSG:4326...", end=" ", flush=True)
        gdf = gdf.to_crs("EPSG:4326")
        print("done")

    gdf.columns = [c.lower() for c in gdf.columns]

    def fix_and_multi(g):
        if g is None or g.is_empty:
            return None
        if not g.is_valid:
            g = make_valid(g)
        if g.is_empty:
            return None
        if g.geom_type == "GeometryCollection":
            polys = [
                p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")
            ]
            if not polys:
                return None
            g = (
                polys[0]
                if len(polys) == 1
                else MultiPolygon(
                    [
                        p
                        for mp in polys
                        for p in (
                            mp.geoms if mp.geom_type == "MultiPolygon" else [mp]
                        )
                    ]
                )
            )
        if g.geom_type == "Polygon":
            return MultiPolygon([g])
        if g.geom_type == "MultiPolygon":
            return g
        return None

    gdf["geometry"] = gdf.geometry.apply(fix_and_multi)
    before = len(gdf)
    gdf = gdf[gdf.geometry.notnull()].copy()
    dropped = before - len(gdf)
    if dropped > 0:
        print(f"({dropped} invalid geom dropped)...", end=" ", flush=True)
    return gdf


# ── Parcel preparation ───────────────────────────────────────────────────────


def prepare_parcels(gdf, area_unit="m2"):
    """Clean WFS download: deduplicate, compute area, normalise columns."""
    if len(gdf) == 0:
        return gdf

    # CCA as string primary key
    gdf["cca"] = (
        gdf["cca"].astype(str) if "cca" in gdf.columns else gdf.index.astype(str)
    )

    # Dedup
    dupes = gdf["cca"].duplicated().sum()
    if dupes > 0:
        print(f"({dupes} WFS dupes dropped)...", end=" ", flush=True)
        gdf = gdf.drop_duplicates(subset="cca", keep="first").copy()

    # Compute area in UTM
    gdf_utm = gdf.to_crs("EPSG:32721")
    if area_unit == "ha":
        gdf["area_m2"] = gdf_utm.geometry.area
    else:
        gdf["area_m2"] = gdf_utm.geometry.area

    # Normalise attribute names
    gdf["departamento"] = (
        gdf["departamen"].astype(str) if "departamen" in gdf.columns else None
    )
    gdf["municipio"] = (
        gdf["municipio"].astype(str) if "municipio" in gdf.columns else None
    )

    # Keep only needed columns
    keep = ["cca", "area_m2", "departamento", "municipio", "geometry"]
    return gdf[[c for c in keep if c in gdf.columns]].copy()


# ── Change tracking ──────────────────────────────────────────────────────────


def load_previous_state(state_dir, parcel_type):
    """Load previous parcel GeoParquet from local state dir (downloaded from R2)."""
    path = os.path.join(state_dir, f"catastro_{parcel_type}.parquet")
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        print(f"  No previous state for {parcel_type} (first run)")
        return None
    gdf = gpd.read_parquet(path)
    print(f"  Loaded previous {parcel_type}: {len(gdf):,} parcels")
    return gdf


def track_changes(new_gdf, existing_gdf, parcel_type):
    """
    Compare new WFS data against previous state.
    Returns (merged_gdf with first_seen/last_updated, changes_list).
    """
    today = pd.Timestamp(date.today())
    changes = []

    if existing_gdf is None or len(existing_gdf) == 0:
        # First run: everything is new
        new_gdf["first_seen"] = today
        new_gdf["last_updated"] = today
        for cca in new_gdf["cca"]:
            changes.append({
                "change_date": today,
                "parcel_type": parcel_type,
                "change_type": "new",
                "cca": cca,
            })
        print(f"  {parcel_type}: {len(new_gdf):,} new (first run)")
        return new_gdf, changes

    existing_ccas = set(existing_gdf["cca"])
    new_ccas = set(new_gdf["cca"])

    added = new_ccas - existing_ccas
    removed = existing_ccas - new_ccas
    continued = new_ccas & existing_ccas

    # Merge first_seen from existing for continued parcels
    first_seen_map = existing_gdf.set_index("cca")["first_seen"].to_dict()
    new_gdf["first_seen"] = new_gdf["cca"].map(
        lambda c: first_seen_map.get(c, today)
    )
    new_gdf["last_updated"] = today

    # Log changes
    for cca in added:
        changes.append({
            "change_date": today,
            "parcel_type": parcel_type,
            "change_type": "new",
            "cca": cca,
        })
    for cca in removed:
        changes.append({
            "change_date": today,
            "parcel_type": parcel_type,
            "change_type": "removed",
            "cca": cca,
        })

    print(
        f"  {parcel_type}: {len(added):,} new, {len(continued):,} continued, "
        f"{len(removed):,} removed"
    )
    return new_gdf, changes


def save_state(gdf, state_dir, parcel_type):
    """Save parcel GeoParquet as persistent state."""
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, f"catastro_{parcel_type}.parquet")
    gdf.to_parquet(path, index=False, engine="pyarrow")
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {parcel_type} state: {len(gdf):,} rows ({size_kb:.0f} KB)")


# ── Spatial aggregation (GeoPandas) ──────────────────────────────────────────


def compute_catastro_by_radio(radios_gdf, rural_gdf, urbano_gdf):
    """
    Compute parcel counts and areas per radio via GeoPandas spatial join.
    Replicates the PostGIS query: ST_Contains(radio.geom, ST_Centroid(parcel.geom))
    """
    print("  Computing catastro_by_radio via GeoPandas...", end=" ", flush=True)
    t0 = time.time()
    today = date.today()
    cutoff_90d = pd.Timestamp(today - timedelta(days=90))

    all_redcodes = sorted(radios_gdf["redcode"].tolist())
    records = {rc: {
        "n_parcelas_rural": 0, "n_parcelas_urbano": 0,
        "area_rural_m2": 0.0, "area_urbano_m2": 0.0,
        "area_media_rural_m2": None, "area_media_urbano_m2": None,
        "n_new_parcels_90d": 0,
    } for rc in all_redcodes}

    for parcel_type, parcel_gdf in [("rural", rural_gdf), ("urbano", urbano_gdf)]:
        if parcel_gdf is None or len(parcel_gdf) == 0:
            print(f"{parcel_type} empty...", end=" ", flush=True)
            continue

        # Create centroid GeoDataFrame for spatial join (project to UTM for accuracy)
        centroids = parcel_gdf.copy()
        centroids_utm = centroids.to_crs("EPSG:32721")
        centroids["centroid_geom"] = centroids_utm.geometry.centroid.to_crs("EPSG:4326")
        centroids = centroids.set_geometry("centroid_geom")

        # Spatial join: centroid within radio
        joined = gpd.sjoin(centroids, radios_gdf, how="inner", predicate="within")

        # Aggregate by redcode
        n_col = f"n_parcelas_{parcel_type}"
        area_col = f"area_{parcel_type}_m2"
        media_col = f"area_media_{parcel_type}_m2"

        for rc, group in joined.groupby("redcode"):
            if rc not in records:
                continue
            n = len(group)
            area_sum = group["area_m2"].sum()
            records[rc][n_col] = n
            records[rc][area_col] = round(float(area_sum), 1)
            records[rc][media_col] = round(float(area_sum / n), 1) if n > 0 else None

        # Count new parcels (last 90 days)
        if "first_seen" in parcel_gdf.columns:
            new_parcels = centroids[centroids["first_seen"] >= cutoff_90d]
            if len(new_parcels) > 0:
                new_joined = gpd.sjoin(
                    new_parcels, radios_gdf, how="inner", predicate="within"
                )
                for rc, group in new_joined.groupby("redcode"):
                    if rc in records:
                        records[rc]["n_new_parcels_90d"] += len(group)

        print(f"{parcel_type} done...", end=" ", flush=True)

    print(f"done in {time.time() - t0:.0f}s")
    return records


def export_catastro_by_radio(records, output_path):
    """Convert aggregation records to parquet for frontend consumption."""
    rows = []
    for rc, rec in sorted(records.items()):
        rows.append({
            "redcode": rc,
            "n_parcelas_rural": rec["n_parcelas_rural"],
            "n_parcelas_urbano": rec["n_parcelas_urbano"],
            "area_rural_m2": rec["area_rural_m2"],
            "area_urbano_m2": rec["area_urbano_m2"],
            "area_media_rural_m2": rec["area_media_rural_m2"],
            "area_media_urbano_m2": rec["area_media_urbano_m2"],
            "n_new_parcels_90d": rec["n_new_parcels_90d"],
            "data_year": DATA_YEAR,
        })

    df = pd.DataFrame(rows)

    # Cast int64 → int32 for DuckDB-WASM browser compatibility
    for col in ["n_parcelas_rural", "n_parcelas_urbano", "n_new_parcels_90d", "data_year"]:
        df[col] = df[col].astype("int32")

    df.to_parquet(output_path, index=False, engine="pyarrow")
    size_kb = os.path.getsize(output_path) / 1024
    print(f"  Exported catastro_by_radio: {len(df):,} rows ({size_kb:.0f} KB)")
    return len(df)


def export_changes_summary(all_changes, existing_changes_path, output_path):
    """
    Aggregate change log and append to existing history.
    Output: change_date, parcel_type, change_type, n
    """
    if not all_changes:
        # No changes this run; copy existing if available
        if os.path.exists(existing_changes_path):
            import shutil
            shutil.copy2(existing_changes_path, output_path)
            print("  No new changes, kept existing summary")
        else:
            pd.DataFrame(
                columns=["change_date", "parcel_type", "change_type", "n"]
            ).to_parquet(output_path, index=False)
            print("  No changes, created empty summary")
        return

    # Aggregate today's changes
    df_new = pd.DataFrame(all_changes)
    summary = (
        df_new.groupby(["change_date", "parcel_type", "change_type"])
        .size()
        .reset_index(name="n")
    )

    # Append to existing history
    if os.path.exists(existing_changes_path):
        df_existing = pd.read_parquet(existing_changes_path)
        summary = pd.concat([df_existing, summary], ignore_index=True)

    summary = summary.sort_values("change_date", ascending=False).reset_index(drop=True)
    summary.to_parquet(output_path, index=False, engine="pyarrow")
    print(f"  Exported changes summary: {len(summary):,} rows")


# ── High-level entry point ───────────────────────────────────────────────────


def run_extraction(output_dir, radios_path, state_dir=None, skip_wfs=False):
    """
    Full WFS -> GeoParquet extraction with change tracking.
    No PostgreSQL required.

    Args:
        output_dir: directory for output parquets
        radios_path: path to radios_misiones.parquet (GeoParquet)
        state_dir: directory with previous state parquets (from R2)
        skip_wfs: if True, reuse existing state without WFS download

    Returns dict with summary stats.
    """
    if state_dir is None:
        state_dir = os.path.join(output_dir, "catastro_state")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(state_dir, exist_ok=True)

    all_changes = []

    if skip_wfs:
        # Reuse existing state (no WFS download)
        print("  Skipping WFS download, using existing state")
        rural_gdf = load_previous_state(state_dir, "rural")
        urbano_gdf = load_previous_state(state_dir, "urbano")
        if rural_gdf is None and urbano_gdf is None:
            print("  [x] No existing state found. Cannot skip WFS.")
            return None
    else:
        # Download WFS
        geojson_rural = download_wfs_paginated(LAYERS["rural"], "parcelas rurales")
        gdf_rural = parse_and_reproject(geojson_rural)
        gdf_rural = prepare_parcels(gdf_rural, area_unit="ha")

        geojson_urbano = download_wfs_paginated(LAYERS["urbano"], "parcelas urbanas")
        gdf_urbano = parse_and_reproject(geojson_urbano)
        gdf_urbano = prepare_parcels(gdf_urbano, area_unit="m2")

        # Load previous state for change tracking
        prev_rural = load_previous_state(state_dir, "rural")
        prev_urbano = load_previous_state(state_dir, "urbano")

        # Track changes
        rural_gdf, rural_changes = track_changes(gdf_rural, prev_rural, "rural")
        urbano_gdf, urbano_changes = track_changes(gdf_urbano, prev_urbano, "urbano")
        all_changes = rural_changes + urbano_changes

        # Save updated state
        save_state(rural_gdf, state_dir, "rural")
        save_state(urbano_gdf, state_dir, "urbano")

    # Load radios for spatial join
    print(f"  Loading radios from {radios_path}...")
    radios_gdf = gpd.read_parquet(radios_path)
    print(f"  Loaded {len(radios_gdf)} radios")

    # Spatial aggregation
    records = compute_catastro_by_radio(radios_gdf, rural_gdf, urbano_gdf)

    # Export outputs
    catastro_path = os.path.join(output_dir, "catastro_by_radio.parquet")
    export_catastro_by_radio(records, catastro_path)

    changes_state_path = os.path.join(state_dir, "catastro_changes_history.parquet")
    changes_output_path = os.path.join(output_dir, "catastro_changes_summary.parquet")
    export_changes_summary(all_changes, changes_state_path, changes_output_path)
    # Also save history to state dir for next run
    if os.path.exists(changes_output_path):
        import shutil
        shutil.copy2(changes_output_path, changes_state_path)

    # Summary
    n_rural = len(rural_gdf) if rural_gdf is not None else 0
    n_urbano = len(urbano_gdf) if urbano_gdf is not None else 0
    n_new = sum(1 for c in all_changes if c["change_type"] == "new")
    n_removed = sum(1 for c in all_changes if c["change_type"] == "removed")

    return {
        "rural_count": n_rural,
        "urban_count": n_urbano,
        "new_parcels": n_new,
        "removed_parcels": n_removed,
        "changes_today": len(all_changes),
        "radios": len(radios_gdf),
    }


# ── Standalone ───────────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Catastro Misiones WFS extraction (no PostgreSQL)"
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"),
        help="Output directory for parquets",
    )
    parser.add_argument(
        "--radios-path",
        default=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "output", "radios_misiones.parquet"
        ),
        help="Path to radios_misiones.parquet",
    )
    parser.add_argument(
        "--skip-wfs",
        action="store_true",
        help="Skip WFS download, reprocess existing state",
    )
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 60)
    print("Catastro Misiones Extraction (GeoPandas)")
    print("=" * 60)

    stats = run_extraction(
        output_dir=args.output_dir,
        radios_path=args.radios_path,
        skip_wfs=args.skip_wfs,
    )

    if stats:
        print(f"\n  Summary:")
        print(f"    Rural: {stats['rural_count']:,}")
        print(f"    Urban: {stats['urban_count']:,}")
        print(f"    New: {stats['new_parcels']:,}, Removed: {stats['removed_parcels']:,}")
        print(f"    Radios: {stats['radios']}")
    print("\nDone.")


if __name__ == "__main__":
    main()
