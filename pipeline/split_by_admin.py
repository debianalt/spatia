"""
Split satellite score parquets into per-admin-unit parquets + summary JSON.

Territory-aware version of split_satellite_by_dpto.py.
For Misiones: uses existing h3_radio_crosswalk_areal (dasymetric via census radios).
For other territories: uses h3_admin_crosswalk.parquet built by build_admin_crosswalk.py.

Usage:
  # Misiones (backwards compat):
  python pipeline/split_by_admin.py --territory misiones
  python pipeline/split_by_admin.py --territory misiones --only environmental_risk,green_capital

  # Itapúa (after build_admin_crosswalk.py is run):
  python pipeline/split_by_admin.py --territory itapua_py
  python pipeline/split_by_admin.py --territory itapua_py --only environmental_risk

Output:
  pipeline/output/{prefix}sat_dpto/sat_{ID}_{ADMIN}.parquet
  src/lib/data/{territory_id}_sat_{ID}_summary.json

The summary JSON is picked up by AnalysisView.svelte to populate the department menu.
For Itapúa, the summary is stored under territory_id prefix to avoid collision with Misiones.
"""

import json
import os
import sys
import time

import pandas as pd

from config import OUTPUT_DIR, get_territory

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DATA_DIR = os.path.join(SCRIPT_DIR, "..", "src", "lib", "data")

# Analyses that have GEE-based parquets (all territories)
SAT_ANALYSES = [
    "environmental_risk", "climate_comfort", "green_capital",
    "change_pressure", "agri_potential", "forest_health", "forestry_aptitude",
    "carbon_stock", "pm25_drivers", "deforestation_dynamics",
    "climate_vulnerability", "productive_activity", "location_value",
    "land_use", "accessibility",
]

# Analyses that only work for Misiones (AR census data)
MISIONES_ONLY = {
    "service_deprivation", "territorial_isolation",
    "health_access", "education_capital", "education_flow",
    "territorial_gap", "education_gap",
    "territorial_types", "sociodemographic", "economic_activity",
}


def h3_to_latlng(h3index: str) -> tuple[float, float]:
    try:
        from h3 import cell_to_latlng
        return cell_to_latlng(h3index)
    except ImportError:
        pass
    try:
        import h3
        return h3.h3_to_geo(h3index)
    except (ImportError, AttributeError):
        raise ImportError("h3 library required: pip install h3")


def build_crosswalk_misiones() -> dict[str, str]:
    """Build h3→dpto lookup for Misiones from the dasymetric areal crosswalk."""
    radio_stats_path = os.path.join(OUTPUT_DIR, "radio_stats_master.parquet")
    areal_path = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk_areal.parquet")

    areal = pd.read_parquet(areal_path)
    radio_stats = pd.read_parquet(radio_stats_path, columns=["redcode", "dpto"])
    areal = areal.merge(radio_stats, on="redcode", how="inner")

    hex_dpto = (areal.groupby(["h3index", "dpto"])["weight"].sum()
                     .reset_index()
                     .sort_values(["h3index", "weight"], ascending=[True, False])
                     .drop_duplicates("h3index", keep="first")
                     .set_index("h3index")["dpto"]
                     .to_dict())

    print(f"  Misiones: {len(hex_dpto):,} hexes -> {len(set(hex_dpto.values()))} dptos (dasymetric)")
    return hex_dpto


def build_crosswalk_territory(territory: dict) -> dict[str, str]:
    """Build h3→admin lookup for a non-Misiones territory from h3_admin_crosswalk.parquet."""
    t_prefix = territory['output_prefix']
    t_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/'))
    crosswalk_path = os.path.join(t_dir, 'h3_admin_crosswalk.parquet')

    if not os.path.exists(crosswalk_path):
        raise FileNotFoundError(
            f"Crosswalk not found: {crosswalk_path}\n"
            f"Run: python pipeline/build_admin_crosswalk.py --territory {territory['id']}"
        )

    admin_col = territory['admin_col']
    df = pd.read_parquet(crosswalk_path)
    lookup = df.set_index('h3index')[admin_col].to_dict()
    print(f"  {territory['label']}: {len(lookup):,} hexes -> "
          f"{len(set(lookup.values()))} {territory['admin_level']}s (polygon crosswalk)")
    return lookup


def safe_filename(name: str) -> str:
    return (name.lower()
            .replace(" ", "_")
            .replace("á", "a").replace("é", "e").replace("í", "i")
            .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
            .replace("ü", "u").replace("'", "").replace(".", ""))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Split satellite parquets by admin unit")
    parser.add_argument("--territory", default="misiones",
                        help="Territory ID from config.py (default: misiones)")
    parser.add_argument("--only", default=None, help="Comma-separated analysis IDs")
    parser.add_argument("--sat-only", action="store_true",
                        help="Misiones: run only SAT_ANALYSES with polygon crosswalk + fill_missing")
    parser.add_argument("--fill-missing", dest="fill_missing", action="store_true", default=None,
                        help="Fill hexes missing from analysis with score=0 (default: True for non-Misiones)")
    parser.add_argument("--no-fill-missing", dest="fill_missing", action="store_false")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    t_id = territory['id']
    t_prefix = territory['output_prefix']
    admin_col = territory['admin_col']

    # Input/output directories
    if t_prefix:
        t_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/'))
        in_dir = t_dir
    else:
        t_dir = OUTPUT_DIR
        in_dir = OUTPUT_DIR

    dpto_out_dir = os.path.join(t_dir, "sat_dpto")
    os.makedirs(dpto_out_dir, exist_ok=True)
    os.makedirs(SRC_DATA_DIR, exist_ok=True)

    # Choose analyses
    if t_id == 'misiones' and args.sat_only:
        all_analyses = SAT_ANALYSES  # polygon crosswalk mode: comparable layers only
    elif t_id == 'misiones':
        all_analyses = SAT_ANALYSES + list(MISIONES_ONLY)
    else:
        all_analyses = SAT_ANALYSES  # GEE-only for non-AR territories

    analyses = all_analyses
    if args.only:
        analyses = [a for a in args.only.split(",") if a in all_analyses]
        if not analyses:
            print(f"No matching analyses. Available: {all_analyses}")
            return 1

    t0 = time.time()
    print("=" * 60)
    print(f"  Split by Admin Unit: {territory['label']} ({t_id})")
    print(f"  Admin level: {admin_col}")
    print(f"  Analyses: {len(analyses)}")
    print("=" * 60)

    # Crosswalk selection:
    # - Misiones --sat-only: polygon crosswalk (h3_admin_crosswalk.parquet) + fill_missing
    # - Misiones default: dasymetric census crosswalk (MISIONES_ONLY layers need census radios)
    # - Other territories: polygon crosswalk always
    crosswalk_path = os.path.join(t_dir, 'h3_admin_crosswalk.parquet')
    use_polygon = (t_id != 'misiones') or (args.sat_only and os.path.exists(crosswalk_path))

    if use_polygon:
        h3_admin = build_crosswalk_territory(territory)
        if t_id == 'misiones':
            print("  Using polygon crosswalk (comparable layers — parity with Itapua)")
    else:
        h3_admin = build_crosswalk_misiones()

    # Default fill_missing: True when using polygon crosswalk
    fill_missing = args.fill_missing if args.fill_missing is not None else use_polygon

    # Full hex DataFrame for fill-missing mode
    if fill_missing:
        full_hexes = pd.DataFrame({
            'h3index': list(h3_admin.keys()),
            admin_col: list(h3_admin.values()),
        })

    # Process each analysis
    for analysis_id in analyses:
        parquet_path = os.path.join(in_dir, f"sat_{analysis_id}.parquet")
        if not os.path.exists(parquet_path):
            print(f"\n  SKIP {analysis_id}: {parquet_path} not found")
            continue

        print(f"\nSplitting {analysis_id}...")
        df = pd.read_parquet(parquet_path)

        if fill_missing:
            # Left-join from full crosswalk: every territory hex gets a row
            df = full_hexes.merge(df.drop(columns=[admin_col], errors='ignore'),
                                  on='h3index', how='left')
            score_like = {'score', 'score_baseline', 'delta_score'}
            for col in df.columns:
                if col in ('h3index', admin_col):
                    continue
                if col in score_like or col.startswith('c_'):
                    continue  # NaN = no raster coverage
                if df[col].dtype == object:
                    df[col] = df[col].fillna('')
                else:
                    df[col] = df[col].fillna(0)
            no_admin = 0
            df_assigned = df
        else:
            df[admin_col] = df["h3index"].map(h3_admin)
            no_admin = df[admin_col].isna().sum()
            df_assigned = df.dropna(subset=[admin_col])

        score_col = "score" if "score" in df.columns else "territorial_type"
        component_cols = [c for c in df.columns
                          if c not in ("h3index", "score", "territorial_type", admin_col)]
        prov_avg = round(float(df[score_col].mean()), 1)

        admins = sorted(df_assigned[admin_col].unique())
        summary_units = []

        for admin_name in admins:
            subset = df_assigned[df_assigned[admin_col] == admin_name]
            out_cols = ["h3index", score_col] + component_cols
            hex_data = subset[[c for c in out_cols if c in subset.columns]].reset_index(drop=True)

            safe_name = safe_filename(admin_name)
            out_path = os.path.join(dpto_out_dir, f"sat_{analysis_id}_{safe_name}.parquet")
            hex_data.to_parquet(out_path, index=False)

            # Centroid
            lats, lngs = [], []
            for h3idx in hex_data["h3index"].head(500):
                try:
                    lat, lng = h3_to_latlng(h3idx)
                    lats.append(lat)
                    lngs.append(lng)
                except Exception:
                    pass
            centroid = ([round(sum(lngs) / len(lngs), 4), round(sum(lats) / len(lats), 4)]
                        if lats else [0, 0])

            raw_mean = hex_data[score_col].mean()
            avg_score = None if (raw_mean != raw_mean) else round(float(raw_mean), 1)  # NaN -> None -> JSON null
            summary_units.append({
                admin_col: admin_name,
                "parquetKey": safe_name,
                "avg_score": avg_score,
                "hex_count": len(hex_data),
                "centroid": centroid,
            })

        summary_data = {
            "territory": t_id,
            "province": {
                "total_hexes": len(df),
                "avg_score": prov_avg,
                "unassigned": int(no_admin),
            },
            # Keep "departments" key for backwards compat with Misiones UI
            "departments": sorted(summary_units, key=lambda d: d["avg_score"] or 0, reverse=True),
        }

        # Summary JSON: for misiones use legacy name, for others prefix with territory
        if t_id == 'misiones':
            summary_path = os.path.join(SRC_DATA_DIR, f"sat_{analysis_id}_dept_summary.json")
        else:
            summary_path = os.path.join(SRC_DATA_DIR, f"{t_id}_sat_{analysis_id}_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)

        print(f"  {len(admins)} {admin_col}s, {len(df_assigned):,} hexes, "
              f"unassigned={no_admin}, avg_score={prov_avg}")

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  Done in {elapsed:.0f}s -> {dpto_out_dir}")
    print(f"{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
