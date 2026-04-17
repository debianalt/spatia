"""
Forestry aptitude via species distribution model (SDM).

Reemplaza el pipeline PCA+geomean de forestry_aptitude con un modelo de
distribucion de especie entrenado sobre las plantaciones existentes en
Misiones (MapBiomas clase silvicultura, via sat_land_use.parquet) como
presencias, usando covariables biofisicas/satelitales.

Score 0-100 = probabilidad de condiciones analogas a donde ya prospera
una plantacion forestal. Hexes enmascarados (agua, urbano, bosque nativo
maduro) se emiten con score=NULL para no renderizarse en el mapa.

Usage:
  python pipeline/compute_forestry_sdm.py
  python pipeline/compute_forestry_sdm.py --no-diagnostics
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import duckdb
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import OUTPUT_DIR, get_territory

# Set by main() after --territory parse; functions read these globals.
_T_OUT_DIR: str = OUTPUT_DIR
_T_ID: str = 'misiones'


def _t_path(filename: str) -> str:
    """Resolve a covariate filename to the territory output directory."""
    return os.path.join(_T_OUT_DIR, filename)


def _terrain_parquet() -> str:
    """Return terrain parquet path — fabdem for Misiones, srtm for others."""
    if _T_ID == 'misiones':
        p = _t_path('fabdem_terrain_h3.parquet')
        if os.path.exists(p):
            return p
    return _t_path('srtm_terrain_h3.parquet')


OUT_PARQUET = os.path.join(OUTPUT_DIR, "sat_forestry_aptitude.parquet")
DIAG_JSON = os.path.join(OUTPUT_DIR, "forestry_sdm_diagnostics.json")

PRESENCE_THRESHOLD = 50.0
NATIVE_FOREST_MASK_THRESHOLD = 70.0
WATER_MASK_THRESHOLD = 50.0
URBAN_MASK_THRESHOLD = 0.30
BACKGROUND_RATIO = 3

RF_PARAMS = dict(
    n_estimators=400,
    max_depth=None,
    min_samples_leaf=20,
    class_weight="balanced",
    n_jobs=-1,
    random_state=42,
)


def build_prediction_frame(con: duckdb.DuckDBPyConnection, t_out_dir: str) -> pd.DataFrame:
    """Load covariates for non-Misiones territory (no lulc needed for prediction).

    Uses era5_annual_h3.parquet as the primary hex set (all hexes with climate data).
    Returns a DataFrame with the same feature columns as build_feature_frame but
    with frac_* columns set to 0 (no training presence) and water/urban derived
    from JRC + GHSL.
    """
    out = os.path.abspath(t_out_dir).replace("\\", "/")
    terrain_file = _terrain_parquet()
    # Use srtm_terrain_h3 if fabdem not available
    if not os.path.exists(terrain_file):
        terrain_file = os.path.join(t_out_dir, 'srtm_terrain_h3.parquet')
    terrain_path = os.path.abspath(terrain_file).replace("\\", "/")

    hwsd_path = os.path.join(t_out_dir, 'hwsd_v2_h3.parquet')
    has_hwsd = os.path.exists(hwsd_path)
    hwsd_cte = f"""
    hwsd AS (
        SELECT h3index, awc, drainage_code, texture_code, root_depth_code
        FROM read_parquet('{os.path.abspath(hwsd_path).replace(chr(92), "/")}')
    ),""" if has_hwsd else ""
    hwsd_select = "hwsd.awc, hwsd.drainage_code, hwsd.texture_code, hwsd.root_depth_code," if has_hwsd else \
                  "NULL::DOUBLE AS awc, NULL::DOUBLE AS drainage_code, NULL::DOUBLE AS texture_code, NULL::DOUBLE AS root_depth_code,"
    hwsd_join = "LEFT JOIN hwsd USING (h3index)" if has_hwsd else ""

    ghsl_path = os.path.join(t_out_dir, 'ghsl_smod_h3.parquet')
    has_ghsl = os.path.exists(ghsl_path)
    ghsl_cte = f"""
    ghsl AS (
        SELECT h3index, smod_urban_frac, smod_suburban_frac
        FROM read_parquet('{os.path.abspath(ghsl_path).replace(chr(92), "/")}')
    ),""" if has_ghsl else ""
    ghsl_select = "ghsl.smod_urban_frac, ghsl.smod_suburban_frac," if has_ghsl else \
                  "NULL::DOUBLE AS smod_urban_frac, NULL::DOUBLE AS smod_suburban_frac,"
    ghsl_frac_urban = "COALESCE(ghsl.smod_urban_frac * 100, 0)" if has_ghsl else "0.0"
    ghsl_join = "LEFT JOIN ghsl USING (h3index)" if has_ghsl else ""

    sql = f"""
    WITH base AS (
        SELECT h3index FROM read_parquet('{out}/era5_annual_h3.parquet')
    ),
    jrc AS (
        SELECT h3index, AVG(water_fraction) AS water_jrc
        FROM read_parquet('{out}/jrc_water_annual_h3.parquet')
        GROUP BY h3index
    ),
    {ghsl_cte}
    era5 AS (
        SELECT h3index,
               AVG(temp_mean) AS temp_mean, AVG(temp_min) AS temp_min,
               AVG(frost_days) AS frost_days, AVG(gdd_base10) AS gdd,
               AVG(solar_radiation) AS solar
        FROM read_parquet('{out}/era5_annual_h3.parquet')
        GROUP BY h3index
    ),
    chirps AS (
        SELECT h3index,
               AVG(total_mm) AS precip_total, AVG(mean_daily) AS precip_mean_daily,
               AVG(days_gt_20mm) AS precip_days_20mm, AVG(days_gt_50mm) AS precip_days_50mm
        FROM read_parquet('{out}/chirps_annual_h3.parquet')
        GROUP BY h3index
    ),
    terra AS (
        SELECT h3index,
               AVG(water_deficit) AS water_deficit, AVG(soil_moisture) AS soil_moisture,
               AVG(vpd) AS vpd, AVG(pdsi_min) AS pdsi_min
        FROM read_parquet('{out}/terraclimate_annual_h3.parquet')
        GROUP BY h3index
    ),
    soil AS (
        SELECT h3index, ph, clay, sand, silt, soc, bulk_density
        FROM read_parquet('{out}/soilgrids_h3.parquet')
    ),
    {hwsd_cte}
    terrain AS (
        SELECT h3index,
               slope_mean, slope_p90, elev_mean, elev_range,
               twi_mean, ruggedness_mean
        FROM read_parquet('{terrain_path}')
    ),
    ndvi AS (
        SELECT h3index, AVG(mean_ndvi) AS ndvi_mean
        FROM read_parquet('{out}/ndvi_annual_mean_h3.parquet')
        GROUP BY h3index
    ),
    access AS (
        SELECT h3index, tt_cities_50k_min AS tt_city_50k
        FROM read_parquet('{out}/nelson_accessibility_h3.parquet')
    )
    SELECT base.h3index,
           -- Dummy lulc columns (no training presence for this territory)
           0.0 AS frac_plantation, 0.0 AS frac_native_forest,
           COALESCE(jrc.water_jrc * 100, 0) AS frac_water,
           {ghsl_frac_urban} AS frac_urban,
           0.0 AS frac_pasture, 0.0 AS frac_agriculture, 0.0 AS frac_mosaic,
           0.0 AS frac_wetland, 0.0 AS frac_grassland, 0.0 AS frac_bare,
           jrc.water_jrc,
           {ghsl_select}
           era5.temp_mean, era5.temp_min, era5.frost_days, era5.gdd, era5.solar,
           chirps.precip_total, chirps.precip_mean_daily,
           chirps.precip_days_20mm, chirps.precip_days_50mm,
           terra.water_deficit, terra.soil_moisture, terra.vpd, terra.pdsi_min,
           soil.ph, soil.clay, soil.sand, soil.silt, soil.soc, soil.bulk_density,
           {hwsd_select}
           terrain.slope_mean, terrain.slope_p90, terrain.elev_mean,
           terrain.elev_range, terrain.twi_mean, terrain.ruggedness_mean,
           ndvi.ndvi_mean,
           access.tt_city_50k
    FROM base
    INNER JOIN era5    USING (h3index)
    INNER JOIN chirps  USING (h3index)
    INNER JOIN soil    USING (h3index)
    INNER JOIN terrain USING (h3index)
    LEFT JOIN jrc      USING (h3index)
    {ghsl_join}
    LEFT JOIN terra    USING (h3index)
    {hwsd_join}
    LEFT JOIN ndvi     USING (h3index)
    LEFT JOIN access   USING (h3index)
    """
    return con.execute(sql).fetchdf()


def build_feature_frame(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Join covariates at H3 level from existing parquets."""
    out = os.path.abspath(_T_OUT_DIR).replace("\\", "/")
    terrain_path = os.path.abspath(_terrain_parquet()).replace("\\", "/")

    # HWSD is optional — skip if parquet not present (LEFT JOIN still works but
    # DuckDB errors on missing file, so we conditionally include the CTE)
    hwsd_path = os.path.join(_T_OUT_DIR, 'hwsd_v2_h3.parquet')
    has_hwsd = os.path.exists(hwsd_path)
    hwsd_cte = f"""
    hwsd AS (
        SELECT h3index, awc, drainage_code, texture_code, root_depth_code
        FROM read_parquet('{os.path.abspath(hwsd_path).replace(chr(92), '/')}')
    ),""" if has_hwsd else ""
    hwsd_select = "hwsd.awc, hwsd.drainage_code, hwsd.texture_code, hwsd.root_depth_code," if has_hwsd else \
                  "NULL::DOUBLE AS awc, NULL::DOUBLE AS drainage_code, NULL::DOUBLE AS texture_code, NULL::DOUBLE AS root_depth_code,"
    hwsd_join = "LEFT JOIN hwsd USING (h3index)" if has_hwsd else ""

    # era5/chirps/terraclimate single-row composites (year=2021) from Itapúa;
    # multi-year from Misiones. WHERE clause is compatible with both.
    sql = f"""
    WITH lulc AS (
        SELECT h3index,
               frac_plantation, frac_native_forest, frac_water,
               frac_urban, frac_pasture, frac_agriculture, frac_mosaic,
               frac_wetland, frac_grassland, frac_bare
        FROM read_parquet('{out}/sat_land_use.parquet')
    ),
    jrc AS (
        SELECT h3index, AVG(water_fraction) AS water_jrc
        FROM read_parquet('{out}/jrc_water_annual_h3.parquet')
        GROUP BY h3index
    ),
    ghsl AS (
        SELECT h3index, smod_urban_frac, smod_suburban_frac
        FROM read_parquet('{out}/ghsl_smod_h3.parquet')
    ),
    era5 AS (
        SELECT h3index,
               AVG(temp_mean) AS temp_mean,
               AVG(temp_min) AS temp_min,
               AVG(frost_days) AS frost_days,
               AVG(gdd_base10) AS gdd,
               AVG(solar_radiation) AS solar
        FROM read_parquet('{out}/era5_annual_h3.parquet')
        GROUP BY h3index
    ),
    chirps AS (
        SELECT h3index,
               AVG(total_mm) AS precip_total,
               AVG(mean_daily) AS precip_mean_daily,
               AVG(days_gt_20mm) AS precip_days_20mm,
               AVG(days_gt_50mm) AS precip_days_50mm
        FROM read_parquet('{out}/chirps_annual_h3.parquet')
        GROUP BY h3index
    ),
    terra AS (
        SELECT h3index,
               AVG(water_deficit) AS water_deficit,
               AVG(soil_moisture) AS soil_moisture,
               AVG(vpd) AS vpd,
               AVG(pdsi_min) AS pdsi_min
        FROM read_parquet('{out}/terraclimate_annual_h3.parquet')
        GROUP BY h3index
    ),
    soil AS (
        SELECT h3index, ph, clay, sand, silt, soc, bulk_density
        FROM read_parquet('{out}/soilgrids_h3.parquet')
    ),
    {hwsd_cte}
    terrain AS (
        SELECT h3index,
               slope_mean, slope_p90, elev_mean, elev_range,
               twi_mean, ruggedness_mean
        FROM read_parquet('{terrain_path}')
    ),
    ndvi AS (
        SELECT h3index, AVG(mean_ndvi) AS ndvi_mean
        FROM read_parquet('{out}/ndvi_annual_mean_h3.parquet')
        GROUP BY h3index
    ),
    access AS (
        SELECT h3index, tt_cities_50k_min AS tt_city_50k
        FROM read_parquet('{out}/nelson_accessibility_h3.parquet')
    )
    SELECT lulc.*,
           jrc.water_jrc,
           ghsl.smod_urban_frac, ghsl.smod_suburban_frac,
           era5.temp_mean, era5.temp_min, era5.frost_days, era5.gdd, era5.solar,
           chirps.precip_total, chirps.precip_mean_daily,
           chirps.precip_days_20mm, chirps.precip_days_50mm,
           terra.water_deficit, terra.soil_moisture, terra.vpd, terra.pdsi_min,
           soil.ph, soil.clay, soil.sand, soil.silt, soil.soc, soil.bulk_density,
           {hwsd_select}
           terrain.slope_mean, terrain.slope_p90, terrain.elev_mean,
           terrain.elev_range, terrain.twi_mean, terrain.ruggedness_mean,
           ndvi.ndvi_mean,
           access.tt_city_50k
    FROM lulc
    INNER JOIN era5    USING (h3index)
    INNER JOIN chirps  USING (h3index)
    INNER JOIN soil    USING (h3index)
    INNER JOIN terrain USING (h3index)
    LEFT JOIN jrc     USING (h3index)
    LEFT JOIN ghsl    USING (h3index)
    LEFT JOIN terra   USING (h3index)
    {hwsd_join}
    LEFT JOIN ndvi    USING (h3index)
    LEFT JOIN access  USING (h3index)
    """
    df = con.execute(sql).fetchdf()
    return df


FEATURES = [
    "temp_mean", "temp_min", "gdd", "solar",
    "precip_total", "precip_mean_daily", "precip_days_20mm", "precip_days_50mm",
    "water_deficit", "soil_moisture", "vpd", "pdsi_min",
    "ph", "clay", "sand", "silt", "soc", "bulk_density",
    "awc", "drainage_code", "texture_code", "root_depth_code",
    "slope_mean", "slope_p90", "elev_mean", "elev_range",
    "twi_mean", "ruggedness_mean",
    "ndvi_mean",
    "tt_city_50k",
]


def compute_mask(df: pd.DataFrame) -> pd.Series:
    """Return a Series of blocked_reason strings, or '' if ok.

    Enmascaramos agua (no hay suelo) y urbano (no se planta en ciudad).
    El bosque nativo NO se enmascara: score descriptivo biofisico en
    todo el territorio rural, con o sin cobertura forestal actual.
    """
    reason = pd.Series([""] * len(df), index=df.index, dtype=object)

    water_mask = (
        (df["frac_water"].fillna(0) >= WATER_MASK_THRESHOLD)
        | (df["water_jrc"].fillna(0) >= 0.30)
    )
    reason[water_mask] = "water"

    urban_mask = (
        (df["smod_urban_frac"].fillna(0) >= URBAN_MASK_THRESHOLD)
        & (reason == "")
    )
    reason[urban_mask] = "urban"

    return reason


def assign_spatial_block(h3index: pd.Series, block_res: int = 5) -> pd.Series:
    """Use H3 parent at coarser resolution as spatial CV block id.

    res 5 -> ~250 km2 cells; ensures held-out blocks are genuinely separate.
    """
    import h3
    parent = h3index.map(lambda h: h3.cell_to_parent(h, block_res))
    return parent


def train_and_predict(df: pd.DataFrame, features: list[str]) -> dict:
    valid = df.loc[df["blocked_reason"] == ""].copy()
    presence = valid["frac_plantation"].fillna(0) >= PRESENCE_THRESHOLD

    feat_df = valid[features].copy()
    medians = feat_df.median(numeric_only=True)
    feat_df = feat_df.fillna(medians)

    rng = np.random.default_rng(42)
    pos_idx = valid.index[presence.values]
    neg_pool = valid.index[~presence.values]
    bg_size = min(len(pos_idx) * BACKGROUND_RATIO, len(neg_pool))
    bg_idx = rng.choice(neg_pool, size=bg_size, replace=False)
    train_idx = np.concatenate([pos_idx, bg_idx])

    y = np.zeros(len(train_idx), dtype=int)
    y[: len(pos_idx)] = 1

    X_train = feat_df.loc[train_idx].values
    groups = assign_spatial_block(valid.loc[train_idx, "h3index"]).values

    print(f"  Presencias: {len(pos_idx):,}")
    print(f"  Background: {len(bg_idx):,}")
    print(f"  Total training: {len(train_idx):,}")
    print(f"  Spatial blocks: {len(set(groups))}")

    # Spatial block CV
    gkf = GroupKFold(n_splits=5)
    auc_scores = []
    ap_scores = []
    for fold, (tr, te) in enumerate(gkf.split(X_train, y, groups)):
        clf = RandomForestClassifier(**RF_PARAMS)
        clf.fit(X_train[tr], y[tr])
        p = clf.predict_proba(X_train[te])[:, 1]
        auc = roc_auc_score(y[te], p)
        ap = average_precision_score(y[te], p)
        auc_scores.append(auc)
        ap_scores.append(ap)
        print(f"  Fold {fold+1}: AUC={auc:.3f}, AP={ap:.3f}, n_test={len(te)}")

    auc_mean = float(np.mean(auc_scores))
    ap_mean = float(np.mean(ap_scores))
    print(f"  Spatial CV: AUC={auc_mean:.3f} +/- {np.std(auc_scores):.3f}, AP={ap_mean:.3f}")

    # Final model on all training data
    clf = RandomForestClassifier(**RF_PARAMS)
    clf.fit(X_train, y)

    # Permutation importance on a sample
    sample_idx = rng.choice(len(train_idx), size=min(5000, len(train_idx)), replace=False)
    perm = permutation_importance(
        clf, X_train[sample_idx], y[sample_idx],
        n_repeats=5, random_state=42, n_jobs=-1,
    )
    fi_tree = dict(zip(features, clf.feature_importances_.tolist()))
    fi_perm = dict(zip(features, perm.importances_mean.tolist()))

    # Predict for all valid hexes
    X_all = feat_df.values
    proba_all = clf.predict_proba(X_all)[:, 1]
    score = np.round(proba_all * 100.0, 1)
    valid["score"] = score

    # Held-out plantation calibration: score distribution on presence
    presence_scores = valid.loc[presence, "score"]
    q50 = float(np.median(presence_scores))
    pct_above_p70 = float((valid["score"] >= np.percentile(valid["score"], 70)).mean() * 100.0)

    # kmeans typology on presence+high-score hexes (>=40 score) for interpretable labels
    high = valid.loc[valid["score"] >= 40].copy()
    if len(high) >= 500:
        kfeats = ["gdd", "precip_total", "water_deficit", "slope_mean", "clay", "ndvi_mean"]
        Xk = high[kfeats].fillna(high[kfeats].median()).values
        Xk = (Xk - Xk.mean(axis=0)) / (Xk.std(axis=0) + 1e-9)
        km = KMeans(n_clusters=4, random_state=42, n_init=20)
        labels = km.fit_predict(Xk)
        high["type"] = labels + 1
        # Label clusters by centroid signature
        centroids = km.cluster_centers_
        labels_map = label_clusters(centroids, kfeats)
        high["type_label"] = high["type"].map(labels_map)
    else:
        high["type"] = pd.NA
        high["type_label"] = pd.NA

    # Merge type/type_label back
    valid["type"] = pd.NA
    valid["type_label"] = pd.NA
    valid.loc[high.index, "type"] = high["type"].values
    valid.loc[high.index, "type_label"] = high["type_label"].values

    return {
        "valid": valid,
        "features": features,
        "clf": clf,          # trained model — used for transfer to other territories
        "cv_auc_mean": auc_mean,
        "cv_auc_folds": auc_scores,
        "cv_ap_mean": ap_mean,
        "cv_ap_folds": ap_scores,
        "feature_importance_tree": fi_tree,
        "feature_importance_permutation": fi_perm,
        "n_presence": int(len(pos_idx)),
        "n_background": int(len(bg_idx)),
        "presence_score_median": q50,
        "feature_medians": {f: float(valid[f].median()) for f in features if f in valid.columns},
    }


def expand_to_full_grid(scored_df: pd.DataFrame, k_neighbors: int = 5) -> pd.DataFrame:
    """Expand scored hexes (~68k) to full Misiones grid (~320k) via H3
    spatial interpolation. Missing hexes get the distance-weighted mean
    score of their k nearest scored neighbors. Water hexes (from
    sat_land_use.frac_water >= 50) remain blocked.
    """
    import h3
    from scipy.spatial import cKDTree

    out = os.path.abspath(OUTPUT_DIR).replace("\\", "/")
    full = duckdb.connect().execute(
        f"""SELECT h3index, frac_water
            FROM read_parquet('{out}/sat_land_use.parquet')"""
    ).fetchdf()

    scored_map = scored_df.set_index("h3index")
    merged = full.merge(scored_map, left_on="h3index", right_index=True, how="left")

    has_score = merged["score"].notna()
    missing = merged.loc[~has_score].copy()
    print(f"  Scored (native): {has_score.sum():,}; missing: {len(missing):,}")

    if len(missing) == 0:
        return merged.drop(columns=["frac_water"]).reset_index(drop=True)

    scored_valid = merged.loc[has_score].copy()
    scored_coords = np.array([h3.cell_to_latlng(h) for h in scored_valid["h3index"].values])
    scored_scores = scored_valid["score"].astype(float).values

    missing_coords = np.array([h3.cell_to_latlng(h) for h in missing["h3index"].values])
    tree = cKDTree(scored_coords)
    dist, idx = tree.query(missing_coords, k=k_neighbors)

    weights = 1.0 / (dist + 1e-6)
    weights /= weights.sum(axis=1, keepdims=True)
    interp_score = np.round((scored_scores[idx] * weights).sum(axis=1), 1)

    merged.loc[~has_score, "score"] = interp_score
    merged.loc[~has_score, "blocked_reason"] = ""

    # Water mask via sat_land_use.frac_water for the full 320k grid
    water_mask_full = merged["frac_water"].fillna(0) >= WATER_MASK_THRESHOLD
    merged.loc[water_mask_full, "score"] = np.nan
    merged.loc[water_mask_full, "blocked_reason"] = "water"

    # Fill tooltip columns for interpolated hexes using same KDTree
    for col in ["gdd", "precip_total", "water_deficit", "slope_mean", "clay", "soc"]:
        if col not in merged.columns:
            continue
        col_vals = scored_valid[col].astype(float).values
        interp_col = (col_vals[idx] * weights).sum(axis=1).round(2)
        merged.loc[~has_score, col] = interp_col

    return merged.drop(columns=["frac_water"]).reset_index(drop=True)


def label_clusters(centroids: np.ndarray, feat_names: list[str]) -> dict:
    """Heuristic labels based on z-score signatures."""
    labels = {}
    for i, c in enumerate(centroids):
        feats = dict(zip(feat_names, c))
        # Priority order
        if feats.get("water_deficit", 0) > 0.5:
            lbl = "Apto con limitacion hidrica"
        elif feats.get("slope_mean", 0) > 0.5:
            lbl = "Apto en terreno de ladera"
        elif feats.get("clay", 0) > 0.5:
            lbl = "Apto con suelo arcilloso"
        elif feats.get("gdd", 0) > 0.3 and feats.get("precip_total", 0) > 0.3:
            lbl = "Optimo templado-humedo"
        else:
            lbl = "Apto estandar"
        labels[i + 1] = lbl
    return labels


def main():
    global _T_OUT_DIR, _T_ID, OUT_PARQUET, DIAG_JSON

    parser = argparse.ArgumentParser(description="Forestry SDM")
    parser.add_argument("--no-diagnostics", action="store_true")
    parser.add_argument("--territory", default="misiones",
                        help="Territory ID from config.py (default: misiones)")
    args = parser.parse_args()

    if args.territory != 'misiones':
        territory = get_territory(args.territory)
        t_prefix = territory['output_prefix'].rstrip('/')
        _T_OUT_DIR = os.path.join(OUTPUT_DIR, t_prefix)
        _T_ID = args.territory
        OUT_PARQUET = os.path.join(_T_OUT_DIR, 'sat_forestry_aptitude.parquet')
        DIAG_JSON   = os.path.join(_T_OUT_DIR, 'forestry_sdm_diagnostics.json')
        print(f"Territory: {territory['label']} ({args.territory})")
        print(f"Output: {OUT_PARQUET}")

        # MODEL TRANSFER: MapBiomas Paraguay Collection 1 lacks plantation class (9).
        # Train SDM on Misiones, apply biophysical envelope to target territory.
        target_out_dir = _T_OUT_DIR
        target_t_id    = _T_ID
        # Temporarily point globals to Misiones for training
        _T_OUT_DIR = OUTPUT_DIR
        _T_ID      = 'misiones'

        con = duckdb.connect()
        print("[1/5] Loading Misiones covariates for SDM training...")
        df_train = build_feature_frame(con)
        print(f"  {len(df_train):,} Misiones hexes")

        print("[2/5] Training SDM on Misiones plantation presence...")
        df_train["blocked_reason"] = compute_mask(df_train)
        result_train = train_and_predict(df_train, FEATURES)
        clf = result_train["clf"]
        feat_medians = result_train["feature_medians"]
        print(f"  CV AUC: {result_train['cv_auc_mean']:.3f}")

        # Restore target territory globals
        _T_OUT_DIR = target_out_dir
        _T_ID      = target_t_id

        print("[3/5] Loading target territory covariates...")
        df_pred = build_prediction_frame(con, _T_OUT_DIR)
        df_pred["blocked_reason"] = compute_mask(df_pred)
        reasons = df_pred["blocked_reason"].value_counts(dropna=False).to_dict()
        print(f"  {len(df_pred):,} {_T_ID} hexes | mask: {reasons}")

        print("[4/5] Applying Misiones RF model to target territory...")
        valid_pred = df_pred.loc[df_pred["blocked_reason"] == ""].copy()
        feat_df = valid_pred[FEATURES].copy()
        # Impute NaNs using Misiones training medians
        for col in FEATURES:
            if feat_df[col].isna().any() and col in feat_medians:
                feat_df[col] = feat_df[col].fillna(feat_medians[col])
        feat_df = feat_df.fillna(feat_df.median(numeric_only=True))
        proba = clf.predict_proba(feat_df.values)[:, 1]
        raw_score = proba * 100.0
        # Rescale to 0-100 percentile rank within territory — model transfer produces
        # compressed probabilities when target region is uniformly "moderate" relative
        # to Misiones training distribution. Percentile rank preserves ranking while
        # giving actionable spatial signal, consistent with platform convention.
        from scipy.stats import rankdata
        pct_rank = rankdata(raw_score, method="average") / len(raw_score) * 100.0
        valid_pred["score_raw"] = np.round(raw_score, 1)
        valid_pred["score"]     = np.round(pct_rank, 1)
        raw_std = float(raw_score.std())
        print(f"  Raw proba score: mean={raw_score.mean():.1f}, std={raw_std:.2f}, range=[{raw_score.min():.1f},{raw_score.max():.1f}]")
        print(f"  Rescaled score:  mean={pct_rank.mean():.1f}, std={pct_rank.std():.2f}")

        # K-means typology on top tercile (score_pct >= 67) — Itapúa-local centroids
        kfeats = ["gdd", "precip_total", "water_deficit", "slope_mean", "clay", "ndvi_mean"]
        high = valid_pred.loc[valid_pred["score"] >= 67].copy()
        if len(high) >= 500:
            from sklearn.cluster import KMeans
            Xk_raw = high[kfeats].fillna(high[kfeats].median())
            Xk = (Xk_raw.values - Xk_raw.values.mean(axis=0)) / (Xk_raw.values.std(axis=0) + 1e-9)
            km = KMeans(n_clusters=4, random_state=42, n_init=20)
            high["type"] = km.fit_predict(Xk) + 1
            high["type_label"] = high["type"].map(label_clusters(km.cluster_centers_, kfeats))
        else:
            high["type"] = pd.NA
            high["type_label"] = pd.NA
        valid_pred["type"] = pd.NA
        valid_pred["type_label"] = pd.NA
        valid_pred.loc[high.index, "type"]       = high["type"].values
        valid_pred.loc[high.index, "type_label"] = high["type_label"].values

        print("[5/5] Writing output...")
        out_df = df_pred[["h3index"]].copy()
        out_df["score"]         = pd.NA
        out_df["score_raw"]     = pd.NA
        out_df["type"]          = pd.NA
        out_df["type_label"]    = pd.NA
        out_df.loc[valid_pred.index, "score"]      = valid_pred["score"].values
        out_df.loc[valid_pred.index, "score_raw"]  = valid_pred["score_raw"].values
        out_df.loc[valid_pred.index, "type"]       = valid_pred["type"].values
        out_df.loc[valid_pred.index, "type_label"] = valid_pred["type_label"].values
        for col in ["gdd", "precip_total", "water_deficit", "slope_mean", "clay", "soc"]:
            if col in df_pred.columns:
                out_df[col] = df_pred[col].round(2).values
        out_df["score"] = pd.to_numeric(out_df["score"], errors="coerce")
        out_df["type"]  = pd.to_numeric(out_df["type"],  errors="coerce").astype("Int32")
        out_df.to_parquet(OUT_PARQUET, index=False)

        n_scored  = out_df["score"].notna().sum()
        n_blocked = (df_pred["blocked_reason"] != "").sum()
        print(f"  Wrote {OUT_PARQUET} ({os.path.getsize(OUT_PARQUET)//1024}KB, {len(out_df):,} rows)")
        print(f"  Scored: {n_scored:,} | Blocked: {n_blocked:,}")

        if not args.no_diagnostics:
            diag = {
                "territory": _T_ID,
                "method": "model_transfer_from_misiones",
                "note": "MapBiomas Paraguay Collection 1 lacks plantation class (9); model trained on Misiones presence",
                "n_hexes_total": int(len(df_pred)),
                "n_scored": int(n_scored),
                "n_blocked": int(n_blocked),
                "blocked_breakdown": {str(k): int(v) for k, v in reasons.items()},
                "misiones_training": {
                    "cv_auc_mean":    result_train["cv_auc_mean"],
                    "cv_auc_folds":   result_train["cv_auc_folds"],
                    "cv_ap_mean":     result_train["cv_ap_mean"],
                    "n_presence":     result_train["n_presence"],
                    "n_background":   result_train["n_background"],
                },
                "feature_importance_tree": result_train["feature_importance_tree"],
            }
            with open(DIAG_JSON, "w") as f:
                json.dump(diag, f, indent=2)
            print(f"  Wrote {DIAG_JSON}")
        return

    # ── Misiones: standard train + predict + expand ──────────────────────────
    print("[1/4] Loading covariates at H3 level...")
    con = duckdb.connect()
    df = build_feature_frame(con)
    print(f"  {len(df):,} hexes")

    print("[2/4] Computing satellite mask...")
    df["blocked_reason"] = compute_mask(df)
    reasons = df["blocked_reason"].value_counts(dropna=False).to_dict()
    print(f"  Mask breakdown: {reasons}")

    print("[3/4] Training SDM (Random Forest, spatial block CV)...")
    result = train_and_predict(df, FEATURES)

    print("[4/4] Writing outputs...")
    out_df = df[["h3index"]].copy()
    out_df["score"] = pd.NA
    out_df["type"] = pd.NA
    out_df["type_label"] = pd.NA
    out_df["blocked_reason"] = df["blocked_reason"]

    valid = result["valid"]
    out_df.loc[valid.index, "score"] = valid["score"].values
    out_df.loc[valid.index, "type"] = valid["type"].values
    out_df.loc[valid.index, "type_label"] = valid["type_label"].values

    # Add top covariables for tooltip
    for col in ["gdd", "precip_total", "water_deficit", "slope_mean", "clay", "soc"]:
        out_df[col] = df[col].round(2).values

    out_df["score"] = pd.to_numeric(out_df["score"], errors="coerce")
    out_df["type"] = pd.to_numeric(out_df["type"], errors="coerce").astype("Int32")

    if _T_ID == 'misiones':
        print("[5/5] Expanding to full H3 grid via spatial interpolation...")
        out_df = expand_to_full_grid(out_df)
    else:
        # Itapúa uses raster-native coverage — already at full resolution, no expansion needed.
        # Drop water/urban blocked rows that have no score.
        print("[5/5] Skipping grid expansion (raster-native territory).")
        out_df = out_df.drop(columns=["blocked_reason"], errors="ignore")
    out_df.to_parquet(OUT_PARQUET, index=False)
    print(f"  Wrote {OUT_PARQUET} ({os.path.getsize(OUT_PARQUET)/1024:.0f} KB, {len(out_df):,} rows)")

    # Sanity checks
    n_scored = out_df["score"].notna().sum()
    n_blocked = (out_df["blocked_reason"] != "").sum()
    print(f"  Scored: {n_scored:,} | Blocked: {n_blocked:,}")

    if not args.no_diagnostics:
        diag = {
            "n_hexes_total": int(len(df)),
            "n_presence": result["n_presence"],
            "n_background": result["n_background"],
            "n_scored": int(n_scored),
            "n_blocked": int(n_blocked),
            "blocked_breakdown": {str(k): int(v) for k, v in reasons.items()},
            "spatial_cv_auc_mean": result["cv_auc_mean"],
            "spatial_cv_auc_folds": result["cv_auc_folds"],
            "spatial_cv_ap_mean": result["cv_ap_mean"],
            "spatial_cv_ap_folds": result["cv_ap_folds"],
            "feature_importance_tree": result["feature_importance_tree"],
            "feature_importance_permutation": result["feature_importance_permutation"],
            "presence_score_median": result["presence_score_median"],
            "thresholds": {
                "presence": PRESENCE_THRESHOLD,
                "native_forest_mask": NATIVE_FOREST_MASK_THRESHOLD,
                "water_mask": WATER_MASK_THRESHOLD,
                "urban_mask": URBAN_MASK_THRESHOLD,
                "background_ratio": BACKGROUND_RATIO,
            },
            "model": {"algo": "RandomForestClassifier", **{k: v for k, v in RF_PARAMS.items() if isinstance(v, (int, float, str))}},
        }
        with open(DIAG_JSON, "w") as f:
            json.dump(diag, f, indent=2)
        print(f"  Wrote {DIAG_JSON}")


if __name__ == "__main__":
    main()
