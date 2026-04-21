"""
Spatial ML model for PM2.5 prediction (GEE-direct, no radio dependencies).

Panel model at H3 res-7 (~1.2km, matching ACAG PM2.5 resolution).
Reads covariates from H3-direct parquets (bilinear-interpolated from GEE
rasters), not from radio censales.  Supports multiple territories.

Usage:
  python pipeline/model_pm25_spatial.py --territory misiones --phase all
  python pipeline/model_pm25_spatial.py --territory itapua_py --phase all
  python pipeline/model_pm25_spatial.py --phase build
"""

import argparse
import json
import os
import sys
import time
import warnings

import h3
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.preprocessing import StandardScaler

from config import OUTPUT_DIR, get_territory

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Feature groups (for ablation) ────────────────────────────────────────
FEATURE_GROUPS = {
    "autoregressive": ["pm25_lag1"],
    "fire": ["burned_fraction", "fire_lag1", "fire_neighbors", "fire_regional"],
    "climate": ["temp_mean", "frost_days", "solar_radiation",
                "dewpoint_mean", "total_mm"],
    "vegetation": ["mean_ndvi", "mean_lst_day", "mean_lst_night",
                    "lst_amplitude", "mean_npp", "tree_cover",
                    "delta_tree_cover"],
    "land_use": ["frac_native_forest", "frac_plantation", "frac_agriculture",
                 "frac_urban", "frac_pasture", "frac_mosaic", "frac_wetland"],
    "terrain": ["elev_mean", "slope_mean", "hand_mean", "twi_merit_mean"],
    "soil": ["ph", "clay", "sand", "soc"],
}

SPATIAL_FEATURES = (
    FEATURE_GROUPS["land_use"] + FEATURE_GROUPS["terrain"] +
    FEATURE_GROUPS["soil"] + ["jrc_occurrence"]
)

TEMPORAL_FEATURES = (
    FEATURE_GROUPS["fire"] + FEATURE_GROUPS["climate"] +
    ["mean_ndvi", "mean_npp", "tree_cover"]
)


# ══════════════════════════════════════════════════════════════════════════
# PHASE 1: BUILD PANEL
# ══════════════════════════════════════════════════════════════════════════

def build_panel(t_dir):
    """Construct (h3_res7, year) panel with target + features from H3-direct parquets."""
    t0 = time.time()

    panel_path = os.path.join(t_dir, "pm25_model_panel.parquet")
    pm25_path = os.path.join(t_dir, "pm25_annual_panel.parquet")
    parent_xw_path = os.path.join(t_dir, "h3_parent_crosswalk.parquet")
    admin_xw_path = os.path.join(t_dir, "h3_admin_crosswalk.parquet")
    cov_path = os.path.join(t_dir, "pm25_covariates_annual.parquet")

    # ── 1a. Aggregate PM2.5 to res-7 ────────────────────────────────────
    print("Loading PM2.5 panel and parent crosswalk...")
    pm25 = pd.read_parquet(pm25_path)
    parents = pd.read_parquet(parent_xw_path)[["h3index", "h3_res7"]]

    pm25 = pm25.merge(parents, on="h3index", how="inner")
    target = (pm25.groupby(["h3_res7", "year"])["pm25"]
              .mean().reset_index()
              .rename(columns={"h3_res7": "h3index"}))

    target = target[(target.year >= 2000) & (target.year <= 2022)]
    n_hex = target["h3index"].nunique()
    n_years = target["year"].nunique()
    print(f"  Target: {len(target):,} rows ({n_hex:,} hex x {n_years} years)")

    # ── 1b. Department mapping via admin crosswalk ──────────────────────
    print("Loading admin crosswalk for department mapping...")
    admin = pd.read_parquet(admin_xw_path)
    admin_col = [c for c in admin.columns if c != 'h3index'][0]
    admin = admin.rename(columns={admin_col: 'dpto'})
    admin = admin.merge(parents, on="h3index", how="inner")
    dept_map = (admin.groupby("h3_res7")["dpto"]
                .agg(lambda x: x.mode().iloc[0])
                .rename("dpto"))
    dept_map.index.name = "h3index"
    print(f"  Departments: {dept_map.nunique()} unique from {len(admin):,} hex")

    # ── 1c. Load annual H3-direct covariates ────────────────────────────
    print("Loading H3-direct annual covariates...")
    panel = target.copy()

    if os.path.exists(cov_path):
        cov = pd.read_parquet(cov_path)
        cov = cov[cov.year.between(2000, 2022)]
        cov = cov.merge(parents, on="h3index", how="inner")

        cov_cols = [c for c in cov.columns
                    if c not in ("h3index", "year", "h3_res7")]

        # Rename LST columns if needed
        if "lst_day" in cov.columns and "mean_lst_day" not in cov.columns:
            cov = cov.rename(columns={
                "lst_day": "mean_lst_day",
                "lst_night": "mean_lst_night",
            })
            cov_cols = [c.replace("lst_day", "mean_lst_day")
                           .replace("lst_night", "mean_lst_night")
                        for c in cov_cols]

        cov_r7 = (cov.groupby(["h3_res7", "year"])
                  .mean(numeric_only=True).reset_index()
                  .rename(columns={"h3_res7": "h3index"}))

        # Drop h3_res7 if still present after rename
        cov_r7 = cov_r7.drop(columns=["h3_res7"], errors="ignore")

        panel = panel.merge(cov_r7, on=["h3index", "year"], how="left")

        for col in cov_cols[:7]:
            if col in panel.columns:
                cov_pct = panel[col].notna().mean() * 100
                print(f"  {col:30s} coverage: {cov_pct:.1f}%")
        if len(cov_cols) > 7:
            print(f"  ... and {len(cov_cols) - 7} more columns")
    else:
        print(f"  WARNING: {cov_path} not found — running without annual covariates")

    # ── 1d. Static H3 features (res-9 -> mean to res-7) ─────────────────
    print("Loading static H3 features...")

    # Land use
    lu_path = os.path.join(t_dir, "sat_land_use.parquet")
    if os.path.exists(lu_path):
        lu = pd.read_parquet(lu_path)
        lu_cols = [c for c in lu.columns if c.startswith("frac_")
                   and c not in ("frac_bare", "frac_water", "frac_grassland")]
        lu = lu[["h3index"] + lu_cols].merge(parents, on="h3index", how="inner")
        lu_agg = lu.groupby("h3_res7")[lu_cols].mean().reset_index()
        lu_agg = lu_agg.rename(columns={"h3_res7": "h3index"})
        panel = panel.merge(lu_agg, on="h3index", how="left")
        print(f"  sat_land_use -> {len(lu_cols)} cols")

    # Flood risk
    flood_path = os.path.join(t_dir, "hex_flood_risk.parquet")
    if os.path.exists(flood_path):
        flood = pd.read_parquet(flood_path)
        flood = flood[["h3index", "jrc_occurrence"]].merge(parents, on="h3index", how="inner")
        flood_agg = flood.groupby("h3_res7")["jrc_occurrence"].mean().reset_index()
        flood_agg = flood_agg.rename(columns={"h3_res7": "h3index"})
        panel = panel.merge(flood_agg, on="h3index", how="left")
        print(f"  hex_flood_risk -> jrc_occurrence")

    # ── 1e. Static H3 terrain + soil + hydro ────────────────────────────
    print("Loading static terrain/soil/hydro H3 features...")

    static_h3_specs = [
        # (preferred_file, fallback_file, columns_to_extract_with_renames)
        ("fabdem_terrain_h3.parquet", "srtm_terrain_h3.parquet",
         {"elev_mean": "elev_mean", "slope_mean": "slope_mean"}),
        ("merit_hydro_h3.parquet", "srtm_terrain_h3.parquet",
         {"hand_mean": "hand_mean", "twi_merit_mean": "twi_merit_mean",
          "twi_mean": "twi_merit_mean"}),
        ("soilgrids_h3.parquet", None,
         {"ph": "ph", "clay": "clay", "sand": "sand", "soc": "soc"}),
    ]

    for preferred, fallback, col_map in static_h3_specs:
        path = os.path.join(t_dir, preferred)
        if not os.path.exists(path) and fallback:
            path = os.path.join(t_dir, fallback)
        if not os.path.exists(path):
            print(f"  SKIP {preferred} (not found)")
            continue

        df = pd.read_parquet(path)
        df = df.merge(parents, on="h3index", how="inner")

        loaded_cols = []
        for src_col, dst_col in col_map.items():
            if src_col in df.columns and dst_col not in panel.columns:
                agg = df.groupby("h3_res7")[src_col].mean().reset_index()
                agg = agg.rename(columns={"h3_res7": "h3index", src_col: dst_col})
                panel = panel.merge(agg, on="h3index", how="left")
                loaded_cols.append(dst_col)

        if loaded_cols:
            print(f"  {os.path.basename(path)} -> {loaded_cols}")

    # ── 1f. Derived features ────────────────────────────────────────────
    print("Computing derived features...")
    panel = panel.sort_values(["h3index", "year"])

    panel["pm25_lag1"] = panel.groupby("h3index")["pm25"].shift(1)

    if "burned_fraction" in panel.columns:
        panel["fire_lag1"] = panel.groupby("h3index")["burned_fraction"].shift(1)

    if "tree_cover" in panel.columns:
        panel["delta_tree_cover"] = panel.groupby("h3index")["tree_cover"].diff()

    if "burned_fraction" in panel.columns:
        print("  Computing fire spatial lag (H3 ring-1 neighbors)...")
        panel = _compute_spatial_lag(panel, "burned_fraction", "fire_neighbors")

    if "burned_fraction" in panel.columns:
        fire_reg = (panel.groupby("year")["burned_fraction"]
                    .mean().rename("fire_regional").reset_index())
        panel = panel.merge(fire_reg, on="year", how="left")
        print("  fire_regional: mean burned_fraction per year")

    # ── 1g. Add department column ───────────────────────────────────────
    panel["dpto"] = panel["h3index"].map(dept_map)

    panel = panel[panel.year >= 2001].dropna(subset=["dpto"])

    # ── 1h. Summary ─────────────────────────────────────────────────────
    elapsed = time.time() - t0
    all_features = _get_feature_names(panel)
    print(f"\n{'=' * 60}")
    print(f"Panel built in {elapsed:.0f}s")
    print(f"  Shape: {panel.shape}")
    print(f"  Hexagons: {panel.h3index.nunique():,}")
    print(f"  Years: {panel.year.min()}-{panel.year.max()} ({panel.year.nunique()})")
    print(f"  Features: {len(all_features)}")
    print(f"\n  NaN counts:")
    for col in all_features:
        na = panel[col].isna().sum()
        if na > 0:
            print(f"    {col:30s} {na:>6,} ({na / len(panel) * 100:.1f}%)")
    print(f"\n  Target (pm25): mean={panel.pm25.mean():.2f}, "
          f"std={panel.pm25.std():.2f}, "
          f"range={panel.pm25.min():.2f}-{panel.pm25.max():.2f}")
    print(f"{'=' * 60}")

    panel.to_parquet(panel_path, index=False)
    print(f"  Saved: {panel_path} ({os.path.getsize(panel_path) / 1024 / 1024:.1f} MB)")
    return panel, panel_path


def _compute_spatial_lag(panel, col, new_col):
    """Compute mean of H3 ring-1 neighbors for a column."""
    hex_ids = panel["h3index"].unique()
    hex_set = set(hex_ids)

    neighbor_map = {}
    for hx in hex_ids:
        ring = h3.grid_ring(hx, 1)
        neighbor_map[hx] = [n for n in ring if n in hex_set]

    yearly = panel.groupby(["h3index", "year"])[col].first()

    records = []
    for hx in hex_ids:
        neighbors = neighbor_map[hx]
        if not neighbors:
            continue
        for year in panel[panel.h3index == hx]["year"].values:
            vals = [yearly.get((n, year), np.nan) for n in neighbors]
            vals = [v for v in vals if not np.isnan(v)]
            records.append({
                "h3index": hx,
                "year": year,
                new_col: np.mean(vals) if vals else np.nan,
            })

    if records:
        lag_df = pd.DataFrame(records)
        panel = panel.merge(lag_df, on=["h3index", "year"], how="left")

    return panel


def _get_feature_names(panel, exclude_groups=None):
    """Get feature column names, optionally excluding groups."""
    exclude_groups = exclude_groups or []
    all_feats = []
    for group_name, group_feats in FEATURE_GROUPS.items():
        if group_name not in exclude_groups:
            all_feats.extend(group_feats)
    seen = set()
    unique = []
    for f in all_feats:
        if f not in seen and f in panel.columns:
            seen.add(f)
            unique.append(f)
    return unique


# ══════════════════════════════════════════════════════════════════════════
# PHASE 2: TRAIN AND EVALUATE
# ══════════════════════════════════════════════════════════════════════════

def _run_lgbm_cv(X, y, folds, params=None):
    """Run LightGBM across CV folds, return overall metrics."""
    if params is None:
        params = {
            "n_estimators": 500, "max_depth": 8, "learning_rate": 0.05,
            "num_leaves": 63, "min_child_samples": 20,
            "subsample": 0.8, "colsample_bytree": 0.8,
            "reg_alpha": 0.1, "reg_lambda": 0.1,
        }
    all_true, all_pred = [], []
    for train_idx, test_idx in folds:
        m = lgb.LGBMRegressor(**params, n_jobs=-1, random_state=42, verbose=-1)
        m.fit(X.iloc[train_idx], y[train_idx])
        all_true.extend(y[test_idx])
        all_pred.extend(m.predict(X.iloc[test_idx]))
    all_true, all_pred = np.array(all_true), np.array(all_pred)
    return {
        "r2": float(r2_score(all_true, all_pred)),
        "rmse": float(root_mean_squared_error(all_true, all_pred)),
        "mae": float(mean_absolute_error(all_true, all_pred)),
    }


def train_and_evaluate(panel=None, t_dir=None):
    """Train Model A (all features) and Model B (no lag) under 3 CV schemes."""
    panel_path = os.path.join(t_dir, "pm25_model_panel.parquet")
    results_path = os.path.join(t_dir, "pm25_model_results.json")

    if panel is None:
        print("Loading panel...")
        panel = pd.read_parquet(panel_path)

    features_a = _get_feature_names(panel)
    features_b = _get_feature_names(panel, exclude_groups=["autoregressive"])
    print(f"\nModel A features ({len(features_a)}): {features_a}")
    print(f"Model B features ({len(features_b)}): {features_b}")

    df = panel.dropna(subset=["pm25"] + features_a).copy()
    y = df["pm25"].values
    groups_dept = df["dpto"].values
    years = df["year"].values
    print(f"\n  Clean rows: {len(df):,} (dropped {len(panel) - len(df):,} with NaN)")

    dept_codes = np.unique(groups_dept)
    spatial_folds = [(np.where(groups_dept != d)[0], np.where(groups_dept == d)[0])
                     for d in dept_codes]
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    train_mask = years <= 2017
    test_mask = years >= 2018

    cv_schemes = {
        "random_5fold": list(kf.split(df)),
        "spatial_lodo": spatial_folds,
        "temporal": [(np.where(train_mask)[0], np.where(test_mask)[0])],
    }

    results = {}

    for model_label, feats in [("ModelA", features_a), ("ModelB", features_b)]:
        print(f"\n{'=' * 60}")
        print(f"{model_label}: LightGBM with {len(feats)} features")
        if model_label == "ModelB":
            print("  (no pm25_lag1 -- environmental drivers only)")
        print(f"{'=' * 60}")

        X = df[feats]

        for cv_name, folds in cv_schemes.items():
            metrics = _run_lgbm_cv(X, y, folds)
            key = f"{cv_name}__{model_label}"
            results[key] = metrics
            print(f"  {cv_name:20s}  R2={metrics['r2']:.4f}  "
                  f"RMSE={metrics['rmse']:.3f}  MAE={metrics['mae']:.3f}")

    print(f"\n{'=' * 60}")
    print("DECOMPOSITION: within-year (spatial) vs between-hex (temporal)")
    print(f"{'=' * 60}")

    decompose_variation(df, results)

    print(f"\n{'=' * 60}")
    print("SUMMARY -- R2 by model x CV scheme")
    print(f"{'=' * 60}")
    print(f"{'Model':<25s} {'Random':>8s} {'Spatial':>8s} {'Temporal':>8s}")
    print("-" * 52)
    for model_label in ["ModelA", "ModelB"]:
        row = f"{model_label:<25s}"
        for cv_name in ["random_5fold", "spatial_lodo", "temporal"]:
            key = f"{cv_name}__{model_label}"
            if key in results:
                row += f" {results[key]['r2']:>7.4f} "
            else:
                row += "     --  "
        print(row)
    print(f"{'=' * 60}")

    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved: {results_path}")

    return results, df, features_b


def decompose_variation(df, results):
    """Within-year spatial models + between-hex temporal models."""
    y_all = df["pm25"].values

    spatial_feats = [f for f in SPATIAL_FEATURES if f in df.columns]
    spatial_feats = list(dict.fromkeys(spatial_feats))
    print(f"\n  Within-year spatial features ({len(spatial_feats)}): {spatial_feats}")

    year_r2 = {}
    for yr in sorted(df["year"].unique()):
        mask = df["year"].values == yr
        sub = df[mask]
        if len(sub) < 100:
            continue
        X_yr = sub[spatial_feats]
        y_yr = sub["pm25"].values

        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        true_all, pred_all = [], []
        for tr, te in kf.split(X_yr):
            m = lgb.LGBMRegressor(
                n_estimators=200, max_depth=6, num_leaves=31,
                n_jobs=-1, random_state=42, verbose=-1,
            )
            m.fit(X_yr.iloc[tr], y_yr[tr])
            pred_all.extend(m.predict(X_yr.iloc[te]))
            true_all.extend(y_yr[te])

        r2 = r2_score(true_all, pred_all)
        year_r2[yr] = r2
        print(f"    {yr}: R2={r2:.4f} (n={len(sub):,})")

    mean_r2 = np.mean(list(year_r2.values()))
    print(f"\n  Within-year spatial mean R2: {mean_r2:.4f}")
    results["within_year_spatial"] = {
        "mean_r2": float(mean_r2),
        "by_year": {str(k): round(v, 4) for k, v in year_r2.items()},
    }

    temporal_feats = [f for f in TEMPORAL_FEATURES if f in df.columns]
    temporal_feats = list(dict.fromkeys(temporal_feats))
    print(f"\n  Between-hex temporal features ({len(temporal_feats)}): {temporal_feats}")

    hex_ids = df["h3index"].unique()
    rng = np.random.RandomState(42)
    sample_hex = rng.choice(hex_ids, min(500, len(hex_ids)), replace=False)

    hex_r2 = []
    for hx in sample_hex:
        sub = df[df["h3index"] == hx].dropna(subset=temporal_feats)
        if len(sub) < 10:
            continue
        X_hx = sub[temporal_feats].values
        y_hx = sub["pm25"].values
        scaler = StandardScaler()
        X_s = scaler.fit_transform(X_hx)
        model = LinearRegression()
        model.fit(X_s, y_hx)
        y_pred = model.predict(X_s)
        r2 = r2_score(y_hx, y_pred)
        hex_r2.append(r2)

    hex_r2 = np.array(hex_r2)
    print(f"\n  Between-hex temporal (OLS, {len(hex_r2)} hexagons):")
    print(f"    mean R2={hex_r2.mean():.4f}, median={np.median(hex_r2):.4f}")
    print(f"    R2 > 0.3: {(hex_r2 > 0.3).sum()}/{len(hex_r2)} "
          f"({(hex_r2 > 0.3).mean()*100:.1f}%)")
    print(f"    R2 > 0.5: {(hex_r2 > 0.5).sum()}/{len(hex_r2)} "
          f"({(hex_r2 > 0.5).mean()*100:.1f}%)")

    results["between_hex_temporal"] = {
        "mean_r2": float(hex_r2.mean()),
        "median_r2": float(np.median(hex_r2)),
        "pct_above_03": float((hex_r2 > 0.3).mean()),
        "pct_above_05": float((hex_r2 > 0.5).mean()),
        "n_hexagons": len(hex_r2),
    }


# ══════════════════════════════════════════════════════════════════════════
# PHASE 3: INTERPRET
# ══════════════════════════════════════════════════════════════════════════

def interpret(panel=None, t_dir=None):
    """SHAP analysis, ablation study, residual diagnostics."""
    panel_path = os.path.join(t_dir, "pm25_model_panel.parquet")
    results_path = os.path.join(t_dir, "pm25_model_results.json")
    shap_path = os.path.join(t_dir, "pm25_model_shap.parquet")

    if panel is None:
        print("Loading panel...")
        panel = pd.read_parquet(panel_path)

    features = _get_feature_names(panel, exclude_groups=["autoregressive"])
    features_a = _get_feature_names(panel)
    df = panel.dropna(subset=["pm25"] + features_a).copy()
    X = df[features]
    y = df["pm25"].values
    print(f"  Model B features ({len(features)}): {features}")

    if os.path.exists(results_path):
        with open(results_path) as f:
            results = json.load(f)
        best_params = results.get("optuna_best_params", {})
    else:
        best_params = {}

    if not best_params:
        best_params = {
            "n_estimators": 500, "max_depth": 8, "learning_rate": 0.05,
            "num_leaves": 63, "min_child_samples": 20,
            "subsample": 0.8, "colsample_bytree": 0.8,
            "reg_alpha": 0.1, "reg_lambda": 0.1,
        }

    print("Training final LightGBM on full data...")
    model = lgb.LGBMRegressor(
        **best_params, n_jobs=-1, random_state=42, verbose=-1,
    )
    model.fit(X, y)
    y_pred = model.predict(X)
    print(f"  In-sample R2={r2_score(y, y_pred):.4f}")

    print("\n=== Feature Importance (LightGBM gain) ===")
    importance = pd.DataFrame({
        "feature": features,
        "gain": model.feature_importances_,
    }).sort_values("gain", ascending=False)
    for _, row in importance.iterrows():
        bar = "#" * int(row["gain"] / importance["gain"].max() * 40)
        print(f"  {row['feature']:30s} {row['gain']:>8.0f}  {bar}")

    print("\n=== SHAP Analysis ===")
    try:
        import shap

        explainer = shap.TreeExplainer(model)

        n_shap = min(20000, len(X))
        rng = np.random.RandomState(42)
        shap_idx = rng.choice(len(X), n_shap, replace=False)
        X_shap = X.iloc[shap_idx]

        print(f"  Computing SHAP values for {n_shap:,} samples...")
        t0 = time.time()
        shap_values = explainer.shap_values(X_shap)
        elapsed = time.time() - t0
        print(f"  Done in {elapsed:.0f}s")

        shap_importance = pd.DataFrame({
            "feature": features,
            "mean_abs_shap": np.abs(shap_values).mean(axis=0),
        }).sort_values("mean_abs_shap", ascending=False)

        print("\n  SHAP importance (mean |SHAP|):")
        for _, row in shap_importance.iterrows():
            bar = "#" * int(row["mean_abs_shap"] / shap_importance["mean_abs_shap"].max() * 40)
            print(f"    {row['feature']:30s} {row['mean_abs_shap']:.4f}  {bar}")

        print("\n  Computing full SHAP for all observations...")
        shap_all = explainer.shap_values(X)
        shap_df = pd.DataFrame(shap_all, columns=[f"shap_{f}" for f in features])
        shap_df["h3index"] = df["h3index"].values
        shap_df["year"] = df["year"].values
        shap_df["pm25"] = y
        shap_df["pm25_pred"] = y_pred
        shap_df.to_parquet(shap_path, index=False)
        print(f"  Saved: {shap_path} ({os.path.getsize(shap_path) / 1024 / 1024:.1f} MB)")

    except ImportError:
        print("  shap not installed, skipping")

    print("\n=== Ablation Study -- Model B (spatial CV, no lag) ===")
    groups_dept = df["dpto"].values
    dept_sizes = pd.Series(groups_dept).value_counts()
    eval_depts = dept_sizes.head(5).index.tolist()

    spatial_folds_eval = [(np.where(groups_dept != d)[0],
                           np.where(groups_dept == d)[0])
                          for d in eval_depts]

    def eval_spatial(feat_subset):
        return _run_lgbm_cv(df[feat_subset], y, spatial_folds_eval,
                            params=best_params)["r2"]

    baseline_r2 = eval_spatial(features)
    print(f"  Baseline Model B (all env features): R2={baseline_r2:.4f}")
    print()

    ablation_groups = {k: v for k, v in FEATURE_GROUPS.items()
                       if k != "autoregressive"}
    for group_name, group_feats in ablation_groups.items():
        available = [f for f in group_feats if f in features]
        if not available:
            continue
        remaining = [f for f in features if f not in available]
        if not remaining:
            continue
        ablated_r2 = eval_spatial(remaining)
        delta = baseline_r2 - ablated_r2
        print(f"  Drop {group_name:15s} ({len(available):2d} feats): "
              f"R2={ablated_r2:.4f}  dR2={delta:+.4f}")

    print("\n=== Residual Diagnostics ===")
    residuals = y - y_pred
    print(f"  Mean residual: {residuals.mean():.4f}")
    print(f"  Std residual:  {residuals.std():.4f}")

    print("\n  R2 by department:")
    for dept in sorted(df["dpto"].unique()):
        mask = df["dpto"].values == dept
        if mask.sum() < 10:
            continue
        r2 = r2_score(y[mask], y_pred[mask])
        rmse = root_mean_squared_error(y[mask], y_pred[mask])
        print(f"    {dept}: R2={r2:.4f}, RMSE={rmse:.3f}, n={mask.sum():,}")

    print("\n  R2 by year:")
    for yr in sorted(df["year"].unique()):
        mask = df["year"].values == yr
        r2 = r2_score(y[mask], y_pred[mask])
        rmse = root_mean_squared_error(y[mask], y_pred[mask])
        print(f"    {yr}: R2={r2:.4f}, RMSE={rmse:.3f}")

    print("\n=== Spatial Autocorrelation of Residuals ===")
    try:
        _moran_residuals(df, residuals)
    except Exception as e:
        print(f"  Moran's I computation failed: {e}")


def _moran_residuals(df, residuals):
    """Compute Moran's I on mean residuals per hexagon."""
    df_copy = df.copy()
    df_copy["residual"] = residuals

    hex_resid = df_copy.groupby("h3index")["residual"].mean()

    hex_ids = hex_resid.index.tolist()
    hex_set = set(hex_ids)
    n = len(hex_ids)

    hex_to_idx = {h: i for i, h in enumerate(hex_ids)}
    vals = hex_resid.values

    mean_r = vals.mean()
    diffs = vals - mean_r
    numerator = 0.0
    denominator = np.sum(diffs ** 2)
    n_pairs = 0

    for hx in hex_ids:
        i = hex_to_idx[hx]
        neighbors = [n for n in h3.grid_ring(hx, 1) if n in hex_set]
        for nb in neighbors:
            j = hex_to_idx[nb]
            numerator += diffs[i] * diffs[j]
            n_pairs += 1

    if n_pairs > 0 and denominator > 0:
        I = (n / n_pairs) * (numerator / denominator)
        E_I = -1 / (n - 1)
        print(f"  Moran's I (mean residuals): {I:.4f}")
        print(f"  Expected under null: {E_I:.4f}")
        if abs(I) < 0.05:
            print("  -> Weak spatial autocorrelation in residuals (good)")
        elif I > 0.05:
            print("  -> Positive spatial autocorrelation remains (model misses spatial structure)")
        else:
            print("  -> Negative spatial autocorrelation (unusual)")
    else:
        print("  Could not compute Moran's I")


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="PM2.5 spatial ML model")
    parser.add_argument("--territory", default="misiones",
                        help="Territory ID (default: misiones)")
    parser.add_argument("--phase", choices=["build", "train", "interpret", "all"],
                        default="all")
    args = parser.parse_args()

    territory = get_territory(args.territory)
    t_prefix = territory['output_prefix']
    t_dir = os.path.join(OUTPUT_DIR, t_prefix.rstrip('/')) if t_prefix else OUTPUT_DIR

    print(f"Territory: {territory['label']} ({territory['id']})")
    print(f"Output dir: {t_dir}")
    print(f"Phase: {args.phase}")
    print(f"{'=' * 60}")

    panel = None
    panel_path = os.path.join(t_dir, "pm25_model_panel.parquet")

    if args.phase in ("build", "all"):
        panel, panel_path = build_panel(t_dir)

    if args.phase in ("train", "all"):
        train_and_evaluate(panel, t_dir)

    if args.phase in ("interpret", "all"):
        interpret(panel, t_dir)


if __name__ == "__main__":
    main()
