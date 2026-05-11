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

# WFS retry strategy: 3 attempts with increasing wait + timeout.
# Total worst case before falling back to cached snapshot: ~13 min.
WFS_RETRY_WAITS = [0, 30, 120, 600]     # seconds before each attempt
WFS_RETRY_TIMEOUTS = [180, 300, 600, 600]


# ── WFS download ─────────────────────────────────────────────────────────────


def download_wfs_paginated(layer_name, label):
    """Download WFS with pagination, retrying full passes on connection failure.

    Returns a FeatureCollection. Empty features list means either the upstream
    WFS returned 0 rows (endpoint up) or every retry exhausted (endpoint down).
    Callers must treat empty as "no update" and reuse the previous snapshot.
    """
    print(f"  Downloading {label}...", flush=True)
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")
    t0 = time.time()

    last_error = None
    for attempt, (wait, timeout) in enumerate(
        zip(WFS_RETRY_WAITS, WFS_RETRY_TIMEOUTS), start=1
    ):
        if wait > 0:
            print(
                f"  Backoff {wait}s before attempt {attempt}/{len(WFS_RETRY_TIMEOUTS)}...",
                flush=True,
            )
            time.sleep(wait)

        all_features = []
        offset = 0
        attempt_failed = False

        while True:
            url = (
                f"{WFS_BASE}?service=WFS&version=1.0.0&request=GetFeature"
                f"&typeName={layer_name}"
                f"&outputFormat=application/json"
                f"&maxFeatures={BATCH_SIZE}&startIndex={offset}"
            )
            try:
                resp = requests.get(url, verify=False, timeout=timeout)
                resp.raise_for_status()
            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError,
            ) as e:
                print(
                    f"  Attempt {attempt} failed at offset {offset}: "
                    f"{type(e).__name__}",
                    flush=True,
                )
                last_error = e
                attempt_failed = True
                break
            except Exception as e:
                print(f"  Attempt {attempt} unexpected error at offset {offset}: {e}", flush=True)
                last_error = e
                attempt_failed = True
                break

            data = resp.json()
            feats = data.get("features", [])
            if not feats:
                break
            all_features.extend(feats)
            offset += BATCH_SIZE

            if len(all_features) % 50000 < BATCH_SIZE:
                print(f"    {len(all_features):,} features so far...", flush=True)

        if not attempt_failed:
            elapsed = time.time() - t0
            if all_features:
                print(f"  {len(all_features):,} features in {elapsed:.0f}s")
            else:
                print(
                    f"  WFS endpoint up but returned 0 features in {elapsed:.0f}s "
                    f"— treating as no-update."
                )
            return {"type": "FeatureCollection", "features": all_features}

    elapsed = time.time() - t0
    print(
        f"  [ERR] All {len(WFS_RETRY_TIMEOUTS)} retries exhausted for {label} "
        f"in {elapsed:.0f}s. Last error: {last_error}"
    )
    return {"type": "FeatureCollection", "features": []}


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
    Returns (merged_gdf with first_seen/last_updated, changes_list, removed_gdf).
    removed_gdf contains parcels that were in existing but not in new — their
    full geometry is preserved so the ghost layer can keep showing them for a
    grace period.

    If new_gdf is empty (WFS failed) and existing_gdf has data, the previous
    snapshot is reused unchanged so the R2 state survives upstream outages.
    """
    today = pd.Timestamp(date.today())
    changes = []

    # WFS failed or returned empty → preserve last known good state.
    if new_gdf is None or len(new_gdf) == 0:
        if existing_gdf is not None and len(existing_gdf) > 0:
            print(
                f"  [warn] {parcel_type}: WFS returned 0 features. Reusing previous "
                f"snapshot ({len(existing_gdf):,} parcels) without changes."
            )
            return existing_gdf.copy(), [], None
        print(
            f"  [warn] {parcel_type}: WFS returned 0 features AND no previous "
            f"state. Skipping {parcel_type}."
        )
        empty = gpd.GeoDataFrame(
            columns=[
                "cca", "area_m2", "departamento", "municipio",
                "geometry", "first_seen", "last_updated",
            ],
            geometry="geometry",
            crs="EPSG:4326",
        )
        return empty, [], None

    if existing_gdf is None or len(existing_gdf) == 0:
        # First run: everything is new, no removed
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
        return new_gdf, changes, None

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

    # Build departamento lookup for change records
    new_dpto = new_gdf.set_index("cca")["departamento"].to_dict() if "departamento" in new_gdf.columns else {}
    old_dpto = existing_gdf.set_index("cca")["departamento"].to_dict() if "departamento" in existing_gdf.columns else {}

    # Log changes
    for cca in added:
        changes.append({
            "change_date": today,
            "parcel_type": parcel_type,
            "change_type": "new",
            "cca": cca,
            "departamento": new_dpto.get(cca, ""),
        })
    for cca in removed:
        changes.append({
            "change_date": today,
            "parcel_type": parcel_type,
            "change_type": "removed",
            "cca": cca,
            "departamento": old_dpto.get(cca, ""),
        })

    # Extract the removed parcels with their geometry so they can live in the
    # ghost layer until pruned. Tag each with the removed_date and parcel_type.
    removed_gdf = None
    if removed:
        removed_gdf = existing_gdf[existing_gdf["cca"].isin(removed)].copy()
        removed_gdf["removed_date"] = today
        if "parcel_type" not in removed_gdf.columns:
            removed_gdf["parcel_type"] = parcel_type
        else:
            removed_gdf["parcel_type"] = parcel_type

    print(
        f"  {parcel_type}: {len(added):,} new, {len(continued):,} continued, "
        f"{len(removed):,} removed"
    )
    return new_gdf, changes, removed_gdf


def save_state(gdf, state_dir, parcel_type):
    """Save parcel GeoParquet as persistent state."""
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, f"catastro_{parcel_type}.parquet")
    gdf.to_parquet(path, index=False, engine="pyarrow")
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {parcel_type} state: {len(gdf):,} rows ({size_kb:.0f} KB)")


# How many days a removed parcel keeps living in the ghost layer before
# the pipeline prunes it. Keeps the PMTiles size bounded while giving the
# frontend a visible window of "recently deleted" parcels to highlight.
REMOVED_GRACE_DAYS = 120


def update_removed_state(state_dir, removed_gdfs):
    """
    Accumulate the per-run removed parcels into catastro_removed.parquet.
    Loads any previous removed state, appends the new removals, drops dupes
    (by cca), and prunes anything older than REMOVED_GRACE_DAYS.
    """
    import pandas as _pd  # local alias to avoid global pollution

    path = os.path.join(state_dir, "catastro_removed.parquet")
    today = _pd.Timestamp(date.today())
    cutoff = today - _pd.Timedelta(days=REMOVED_GRACE_DAYS)

    pieces = []

    # Load previous state if any
    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            prev = gpd.read_parquet(path)
            if len(prev) > 0:
                pieces.append(prev)
                print(f"  Previous removed-state: {len(prev):,} parcels")
        except Exception as e:
            print(f"  [warn] Could not read previous removed state: {e}")

    # Append new removals from this run
    new_count = 0
    for g in removed_gdfs:
        if g is None or len(g) == 0:
            continue
        pieces.append(g)
        new_count += len(g)
    print(f"  New removals this run: {new_count:,}")

    if not pieces:
        # Nothing to save; keep previous file as-is (or create empty).
        if not os.path.exists(path):
            empty = gpd.GeoDataFrame(columns=["cca", "parcel_type", "removed_date", "geometry"], geometry="geometry", crs="EPSG:4326")
            empty.to_parquet(path, index=False, engine="pyarrow")
            print("  Created empty removed-state")
        return

    merged = gpd.GeoDataFrame(pd.concat(pieces, ignore_index=True), crs=pieces[0].crs)
    merged["removed_date"] = pd.to_datetime(merged["removed_date"], errors="coerce")

    # If the same parcel appears multiple times (removed, re-appeared, removed
    # again), keep the most recent record so the ghost shows the latest removal.
    merged = (
        merged.sort_values("removed_date")
        .drop_duplicates("cca", keep="last")
        .reset_index(drop=True)
    )

    # Prune anything older than the grace window
    before_prune = len(merged)
    merged = merged[merged["removed_date"] >= cutoff].reset_index(drop=True)
    pruned = before_prune - len(merged)
    if pruned > 0:
        print(f"  Pruned {pruned:,} removed-state entries older than {REMOVED_GRACE_DAYS}d")

    merged.to_parquet(path, index=False, engine="pyarrow")
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved removed-state: {len(merged):,} parcels ({size_kb:.0f} KB)")


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


def compute_catastro_by_h3(rural_gdf, urbano_gdf, state_dir, resolution=9):
    """
    H3-level parcel change aggregation.

    Returns DataFrame with columns:
      h3index, n_rural, n_urbano, n_total, n_added, n_removed,
      net_change, net_change_norm, extraction_date
    """
    try:
        import h3
    except ImportError:
        print("  [warn] h3 library not available — skipping catastro_by_h3")
        return pd.DataFrame()

    today = date.today()
    cutoff = pd.Timestamp(today - timedelta(days=90))
    h3_records = {}  # h3index -> {n_rural, n_urbano, n_added, n_removed}

    def assign_h3(gdf):
        """Add h3index column via centroid in EPSG:4326."""
        centroids_utm = gdf.to_crs("EPSG:32721")
        pts = centroids_utm.geometry.centroid.to_crs("EPSG:4326")
        return [h3.latlng_to_cell(p.y, p.x, resolution) for p in pts]

    for parcel_type, gdf in [("rural", rural_gdf), ("urbano", urbano_gdf)]:
        if gdf is None or len(gdf) == 0:
            continue
        gdf = gdf.copy()
        print(f"  H3 assign {parcel_type} ({len(gdf):,})...", end=" ", flush=True)
        gdf["h3index"] = assign_h3(gdf)
        for h3idx, grp in gdf.groupby("h3index"):
            r = h3_records.setdefault(h3idx, {"n_rural": 0, "n_urbano": 0, "n_added": 0, "n_removed": 0})
            r[f"n_{parcel_type}"] += len(grp)
            if "first_seen" in gdf.columns:
                r["n_added"] += int((grp["first_seen"] >= cutoff).sum())
        print("done")

    # Removed parcels (from persisted ghost state)
    removed_path = os.path.join(state_dir, "catastro_removed.parquet")
    if os.path.exists(removed_path):
        try:
            rem = gpd.read_parquet(removed_path)
            if "removed_date" in rem.columns:
                rem = rem[rem["removed_date"] >= cutoff]
            else:
                rem = rem.iloc[0:0]
            if len(rem) > 0:
                print(f"  H3 assign removed ({len(rem):,})...", end=" ", flush=True)
                rem["h3index"] = assign_h3(rem)
                for h3idx, grp in rem.groupby("h3index"):
                    h3_records.setdefault(h3idx, {"n_rural": 0, "n_urbano": 0, "n_added": 0, "n_removed": 0})
                    h3_records[h3idx]["n_removed"] += len(grp)
                print("done")
        except Exception as e:
            print(f"  [warn] Could not process removed parcels for H3: {e}")

    rows = []
    for h3idx, r in h3_records.items():
        n_total = r["n_rural"] + r["n_urbano"]
        if n_total == 0:
            continue
        net = r["n_added"] - r["n_removed"]
        rows.append({
            "h3index": h3idx,
            "n_rural": r["n_rural"],
            "n_urbano": r["n_urbano"],
            "n_total": n_total,
            "n_added": r["n_added"],
            "n_removed": r["n_removed"],
            "net_change": net,
            "extraction_date": today.isoformat(),
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    for col in ["n_rural", "n_urbano", "n_total", "n_added", "n_removed", "net_change"]:
        df[col] = df[col].astype("int32")

    # Normalize net_change to [-1, 1] for diverging color scale
    max_abs = int(df["net_change"].abs().max())
    df["net_change_norm"] = (
        (df["net_change"] / max_abs).clip(-1.0, 1.0).astype("float32")
        if max_abs > 0 else 0.0
    )
    return df


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
                columns=["change_date", "parcel_type", "change_type", "departamento", "n"]
            ).to_parquet(output_path, index=False)
            print("  No changes, created empty summary")
        return

    # Aggregate today's changes (including departamento)
    df_new = pd.DataFrame(all_changes)
    if "departamento" not in df_new.columns:
        df_new["departamento"] = ""
    summary = (
        df_new.groupby(["change_date", "parcel_type", "change_type", "departamento"])
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


def export_dept_summary_json(catastro_path, changes_path, output_json_path):
    """
    Generate catastro_dept_summary.json for the frontend department selector.
    Aggregates parcel counts + recent changes per department.
    """
    import json as _json
    from datetime import timedelta

    DPTO_INFO = {
        "54007": {"name": "Apostoles", "centroid": [-27.92, -55.75]},
        "54014": {"name": "Cainguas", "centroid": [-27.18, -54.73]},
        "54021": {"name": "Candelaria", "centroid": [-27.45, -55.73]},
        "54028": {"name": "Capital", "centroid": [-27.38, -55.90]},
        "54035": {"name": "Concepcion", "centroid": [-27.98, -55.52]},
        "54042": {"name": "Eldorado", "centroid": [-26.40, -54.63]},
        "54049": {"name": "G. M. Belgrano", "centroid": [-26.08, -53.78]},
        "54056": {"name": "Guarani", "centroid": [-27.18, -54.18]},
        "54063": {"name": "Iguazu", "centroid": [-25.95, -54.30]},
        "54070": {"name": "L.G. San Martin", "centroid": [-27.08, -54.95]},
        "54077": {"name": "L. N. Alem", "centroid": [-27.60, -55.32]},
        "54084": {"name": "Montecarlo", "centroid": [-26.58, -54.78]},
        "54091": {"name": "Obera", "centroid": [-27.48, -55.12]},
        "54098": {"name": "San Ignacio", "centroid": [-27.25, -55.53]},
        "54105": {"name": "San Javier", "centroid": [-27.77, -55.13]},
        "54112": {"name": "San Pedro", "centroid": [-26.62, -54.12]},
        "54119": {"name": "25 de Mayo", "centroid": [-27.37, -54.02]},
    }

    df = pd.read_parquet(catastro_path)
    today = date.today()
    cutoff_7d = pd.Timestamp(today - timedelta(days=7))

    # Aggregate catastro_by_radio per department
    df["dpto_code"] = df["redcode"].str[:5]
    dept_agg = df.groupby("dpto_code").agg(
        n_parcelas_urbano=("n_parcelas_urbano", "sum"),
        n_parcelas_rural=("n_parcelas_rural", "sum"),
        n_new_90d=("n_new_parcels_90d", "sum"),
    ).reset_index()

    # Load changes for 7d window
    n_new_7d_by_dpto = {}
    n_removed_7d_by_dpto = {}
    if os.path.exists(changes_path):
        df_ch = pd.read_parquet(changes_path)
        if "departamento" in df_ch.columns and len(df_ch) > 0:
            df_ch["change_date"] = pd.to_datetime(df_ch["change_date"])
            recent = df_ch[df_ch["change_date"] >= cutoff_7d]
            if len(recent) > 0:
                for dpto, grp in recent.groupby("departamento"):
                    n_new_7d_by_dpto[dpto] = int(grp[grp["change_type"] == "new"]["n"].sum())
                    n_removed_7d_by_dpto[dpto] = int(grp[grp["change_type"] == "removed"]["n"].sum())

    departments = []
    for _, row in dept_agg.iterrows():
        code = row["dpto_code"]
        info = DPTO_INFO.get(code)
        if not info:
            continue
        n_new_7d = n_new_7d_by_dpto.get(code, 0)
        n_removed_7d = n_removed_7d_by_dpto.get(code, 0)
        departments.append({
            "code": code,
            "name": info["name"],
            "parquetKey": code,
            "centroid": info["centroid"],
            "n_parcelas": int(row["n_parcelas_urbano"] + row["n_parcelas_rural"]),
            "n_urbano": int(row["n_parcelas_urbano"]),
            "n_rural": int(row["n_parcelas_rural"]),
            "n_new_7d": n_new_7d,
            "n_removed_7d": n_removed_7d,
            "n_new_90d": int(row["n_new_90d"]),
            "trend": "up" if n_new_7d > n_removed_7d else ("down" if n_removed_7d > n_new_7d else "stable"),
        })

    departments.sort(key=lambda d: d["n_parcelas"], reverse=True)
    result = {
        "updated": today.isoformat(),
        "total_parcelas": int(df["n_parcelas_urbano"].sum() + df["n_parcelas_rural"].sum()),
        "total_new_90d": int(df["n_new_parcels_90d"].sum()),
        "departments": departments,
    }

    with open(output_json_path, "w", encoding="utf-8") as f:
        _json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  Exported dept summary JSON: {len(departments)} departments -> {output_json_path}")


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

        rural_empty = len(gdf_rural) == 0
        urbano_empty = len(gdf_urbano) == 0
        degraded = rural_empty or urbano_empty

        # Bail out only if BOTH layers failed AND no prior snapshot exists.
        if rural_empty and urbano_empty and prev_rural is None and prev_urbano is None:
            print("  [x] Both WFS layers empty and no previous state — cannot proceed.")
            return None

        # Track changes (each returns the removed geometries too)
        rural_gdf, rural_changes, rural_removed = track_changes(gdf_rural, prev_rural, "rural")
        urbano_gdf, urbano_changes, urbano_removed = track_changes(gdf_urbano, prev_urbano, "urbano")
        all_changes = rural_changes + urbano_changes

        # Save updated state
        save_state(rural_gdf, state_dir, "rural")
        save_state(urbano_gdf, state_dir, "urbano")

        # Update ghost layer: merge removed-in-this-run with the previous
        # removed state, prune entries older than REMOVED_GRACE_DAYS.
        update_removed_state(state_dir, [rural_removed, urbano_removed])

        if degraded:
            print(
                f"\n  [WARN] Run degraded: rural_empty={rural_empty}, "
                f"urbano_empty={urbano_empty}. Reused previous snapshot for "
                f"missing layer(s); next run will retry WFS."
            )

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

    # H3-level aggregation
    h3_df = compute_catastro_by_h3(rural_gdf, urbano_gdf, state_dir)
    if len(h3_df) > 0:
        h3_path = os.path.join(output_dir, "catastro_by_h3.parquet")
        h3_df.to_parquet(h3_path, index=False, engine="pyarrow")
        size_kb = os.path.getsize(h3_path) / 1024
        print(f"  Exported catastro_by_h3: {len(h3_df):,} hexagons ({size_kb:.0f} KB)")
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
