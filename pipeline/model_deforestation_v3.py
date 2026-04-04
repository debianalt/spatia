"""
Deforestation risk model v3 — Spatio-temporal panel with drought and SSP projections.

Panel model: (radio, year) predicting Hansen annual forest loss fraction
using drought/climate, fire, vegetation, land cover, socioeconomic,
institutional, and landscape contagion features.

Target: hansen_loss_year.loss_fraction (continuous, 0-1)
Panel: ~1,588 radios x 22 years (2001-2022) = ~35,000 obs
Features: ~55 (22 temporal + 33 static)

Usage:
  python pipeline/model_deforestation_v3.py --phase build
  python pipeline/model_deforestation_v3.py --phase train
  python pipeline/model_deforestation_v3.py --phase interpret
  python pipeline/model_deforestation_v3.py --phase project
  python pipeline/model_deforestation_v3.py --phase all
"""

import argparse
import json
import os
import sys
import time
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
import psycopg2
from sklearn.metrics import r2_score, mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import KFold

from config import OUTPUT_DIR

warnings.filterwarnings("ignore", category=FutureWarning)

DB = dict(dbname='ndvi_misiones', host='localhost', user='postgres', password='')
PANEL_PATH = os.path.join(OUTPUT_DIR, "deforestation_v3_panel.parquet")
RESULTS_PATH = os.path.join(OUTPUT_DIR, "deforestation_v3_results.json")
SHAP_PATH = os.path.join(OUTPUT_DIR, "deforestation_v3_shap.parquet")
PROJ_PATH = os.path.join(OUTPUT_DIR, "deforestation_v3_projections.parquet")

YEAR_MIN, YEAR_MAX = 2001, 2022  # analysis window

FEATURE_GROUPS = {
    "drought": ["pdsi", "water_deficit", "vpd", "soil_moisture", "precip"],
    "climate": ["temp_mean", "frost_days", "solar_radiation", "dewpoint"],
    "fire": ["burned_fraction", "burn_count"],
    "vegetation": ["mean_ndvi", "mean_npp", "mean_lai", "mean_evi"],
    "forest_state": ["mb_forest", "mb_plantation", "cumul_loss"],
    "landscape": ["neighbors_loss_lag", "loss_acceleration"],
    "biophysical": ["elev_mean", "slope_mean", "soil_ph", "clay", "sand",
                     "soc", "twi_mean", "hand_mean"],
    "socioeconomic": ["pct_nbi", "pct_sin_instruccion", "pct_hacinamiento_critico",
                       "tasa_empleo", "pct_cobertura_salud", "tamano_medio_hogar",
                       "pct_originarios", "densidad_hab_km2",
                       "pct_jefatura_femenina", "pct_combustible_precario"],
    "land_tenure": ["area_media_rural", "n_parcelas_rural", "pct_propietario"],
    "accessibility": ["dist_primary_m", "road_density", "travel_posadas", "travel_cabecera"],
    "institutional": ["otbn_frac_i", "otbn_frac_ii", "inside_anp",
                       "in_corredor_verde", "dist_mbya_km"],
    "plantations": ["frac_plantada", "pct_pinus", "pct_eucalyptus"],
    "economic_pressure": ["viirs_radiance"],
}


def get_features(panel, exclude=None):
    exclude = exclude or []
    feats = []
    for gn, gf in FEATURE_GROUPS.items():
        if gn not in exclude:
            feats.extend(gf)
    return [f for f in feats if f in panel.columns]


def _sql(query):
    conn = psycopg2.connect(**DB)
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def _run_lgbm_cv(X, y, folds):
    all_t, all_p = [], []
    for tr, te in folds:
        m = lgb.LGBMRegressor(
            n_estimators=500, max_depth=8, learning_rate=0.05,
            num_leaves=63, min_child_samples=10,
            subsample=0.8, colsample_bytree=0.8,
            reg_alpha=0.1, reg_lambda=0.1,
            n_jobs=-1, random_state=42, verbose=-1,
        )
        m.fit(X.iloc[tr], y[tr])
        all_t.extend(y[te])
        all_p.extend(m.predict(X.iloc[te]))
    t, p = np.array(all_t), np.array(all_p)
    return {"r2": float(r2_score(t, p)),
            "rmse": float(root_mean_squared_error(t, p)),
            "mae": float(mean_absolute_error(t, p))}


# ======================================================================
# BUILD
# ======================================================================

def build_panel():
    t0 = time.time()

    # --- TARGET: Hansen annual loss fraction ------------------------------
    print("Loading target: hansen_loss_year...")
    target = _sql(f"""SELECT year, redcode, loss_fraction as loss
                      FROM hansen_loss_year
                      WHERE year BETWEEN {YEAR_MIN} AND {YEAR_MAX}""")
    n_radios = target.redcode.nunique()
    n_years = target.year.nunique()
    print(f"  {len(target):,} obs ({n_radios} radios x {n_years} years)")
    print(f"  Mean loss: {target.loss.mean()*100:.3f}%/yr")

    panel = target.copy()

    # --- DROUGHT (TerraClimate, annual) -----------------------------------
    print("Loading drought (TerraClimate)...")
    tc = _sql(f"""SELECT year, redcode, pdsi_mean as pdsi, water_deficit, vpd,
                         soil_moisture
                  FROM terraclimate_annual
                  WHERE year BETWEEN {YEAR_MIN} AND {YEAR_MAX}""")
    panel = panel.merge(tc, on=['year', 'redcode'], how='left')
    print(f"  Merged: {panel.pdsi.notna().sum():,}/{len(panel):,} obs with drought data")

    # --- PRECIPITATION (CHIRPS, annual) -----------------------------------
    print("Loading precipitation (CHIRPS)...")
    ch = _sql(f"""SELECT year, redcode, total_mm as precip
                  FROM chirps_annual
                  WHERE year BETWEEN {YEAR_MIN} AND {YEAR_MAX}""")
    panel = panel.merge(ch, on=['year', 'redcode'], how='left')

    # --- CLIMATE (ERA5, annual) -------------------------------------------
    print("Loading climate (ERA5)...")
    era5 = _sql(f"""SELECT year, redcode, temp_mean, frost_days,
                           solar_radiation, dewpoint_mean as dewpoint
                    FROM era5_annual
                    WHERE year BETWEEN {YEAR_MIN} AND {YEAR_MAX}""")
    panel = panel.merge(era5, on=['year', 'redcode'], how='left')

    # --- FIRE (annual) ----------------------------------------------------
    print("Loading fire...")
    fire = _sql(f"""SELECT year, redcode, burned_fraction, burn_count
                    FROM fire_annual
                    WHERE year BETWEEN {YEAR_MIN} AND {YEAR_MAX}""")
    panel = panel.merge(fire, on=['year', 'redcode'], how='left')

    # --- VEGETATION (annual) ----------------------------------------------
    print("Loading vegetation indices...")
    for tbl, col in [('ndvi_annual_mean', 'mean_ndvi'), ('npp_annual', 'mean_npp'),
                      ('lai_annual', 'mean_lai'), ('evi_annual', 'mean_evi')]:
        df = _sql(f"""SELECT year, redcode, {col}
                      FROM {tbl}
                      WHERE year BETWEEN {YEAR_MIN} AND {YEAR_MAX}""")
        panel = panel.merge(df, on=['year', 'redcode'], how='left')

    # --- FOREST STATE (MapBiomas annual) ----------------------------------
    print("Loading forest state (MapBiomas annual)...")
    mb_forest = _sql(f"""SELECT year, redcode, fraction as mb_forest
                         FROM mapbiomas_lulc
                         WHERE class_name = 'forest'
                         AND year BETWEEN {YEAR_MIN} AND {YEAR_MAX}""")
    mb_plant = _sql(f"""SELECT year, redcode, fraction as mb_plantation
                        FROM mapbiomas_lulc
                        WHERE class_name = 'forest_plantation'
                        AND year BETWEEN {YEAR_MIN} AND {YEAR_MAX}""")
    panel = panel.merge(mb_forest, on=['year', 'redcode'], how='left')
    panel = panel.merge(mb_plant, on=['year', 'redcode'], how='left')

    # Cumulative prior Hansen loss (sum of loss up to t-1)
    panel = panel.sort_values(['redcode', 'year'])
    panel['cumul_loss'] = panel.groupby('redcode')['loss'].cumsum().shift(1)
    panel['cumul_loss'] = panel['cumul_loss'].fillna(0)

    # --- LANDSCAPE CONTAGION ----------------------------------------------
    print("Loading landscape contagion...")
    # Mean loss of radio's department neighbors in t-1
    panel['dpto'] = panel['redcode'].str[:5]
    dept_loss = panel.groupby(['dpto', 'year'])['loss'].mean().rename('dept_mean_loss').reset_index()
    dept_loss['year'] = dept_loss['year'] + 1  # lag by 1 year
    panel = panel.merge(dept_loss.rename(columns={'dept_mean_loss': 'neighbors_loss_lag'}),
                        on=['dpto', 'year'], how='left')

    # Acceleration: loss(t-1) - loss(t-2)
    panel['loss_lag1'] = panel.groupby('redcode')['loss'].shift(1)
    panel['loss_lag2'] = panel.groupby('redcode')['loss'].shift(2)
    panel['loss_acceleration'] = panel['loss_lag1'] - panel['loss_lag2']
    panel = panel.drop(columns=['loss_lag1', 'loss_lag2'])

    # --- VIIRS (2014+) ----------------------------------------------------
    print("Loading VIIRS...")
    viirs = _sql("""SELECT year, redcode, mean_radiance as viirs_radiance
                    FROM viirs_annual""")
    panel = panel.merge(viirs, on=['year', 'redcode'], how='left')

    # --- STATIC FEATURES --------------------------------------------------
    print("Loading static features...")

    # Biophysical
    terrain = _sql("SELECT redcode, elev_mean, slope_mean FROM fabdem_terrain")
    soil = _sql("SELECT redcode, ph as soil_ph, clay, sand, soc FROM soilgrids")
    hydro = _sql("SELECT redcode, twi_merit_mean as twi_mean, hand_mean FROM merit_hydro")
    for df in [terrain, soil, hydro]:
        panel = panel.merge(df, on='redcode', how='left')

    # Socioeconomic
    census = _sql("""SELECT redcode, pct_nbi, pct_sin_instruccion, pct_hacinamiento_critico,
                            tasa_empleo, pct_cobertura_salud, tamano_medio_hogar,
                            pct_originarios, densidad_hab_km2,
                            pct_jefatura_femenina, pct_combustible_precario, pct_propietario
                     FROM censo2022_variables""")
    panel = panel.merge(census, on='redcode', how='left')

    # Land tenure
    cat = _sql("SELECT redcode, area_media_rural_m2 as area_media_rural, n_parcelas_rural FROM catastro_by_radio")
    panel = panel.merge(cat, on='redcode', how='left')

    # Accessibility
    roads = _sql("SELECT redcode, dist_primary_m, road_density_km_per_km2 as road_density FROM road_access")
    acc = _sql("SELECT redcode, travel_min_posadas as travel_posadas, travel_min_cabecera as travel_cabecera FROM custom_accessibility")
    panel = panel.merge(roads, on='redcode', how='left')
    panel = panel.merge(acc, on='redcode', how='left')

    # Institutional
    rsm = _sql("""SELECT redcode, otbn_frac_i, otbn_frac_ii, inside_anp::int,
                         in_corredor_verde::int FROM radio_stats_master""")
    # Fill OTBN NaN with 0
    rsm['otbn_frac_i'] = rsm['otbn_frac_i'].fillna(0)
    rsm['otbn_frac_ii'] = rsm['otbn_frac_ii'].fillna(0)
    panel = panel.merge(rsm, on='redcode', how='left')

    mbya = _sql("SELECT redcode, dist_nearest_guarani_km as dist_mbya_km FROM guarani_by_radio")
    panel = panel.merge(mbya, on='redcode', how='left')

    # Plantations
    plant = _sql("""SELECT redcode, frac_plantada, pct_pinus, pct_eucalyptus
                    FROM plantaciones_forestales_by_radio_2020""")
    panel = panel.merge(plant, on='redcode', how='left')
    panel['frac_plantada'] = panel['frac_plantada'].fillna(0)
    panel['pct_pinus'] = panel['pct_pinus'].fillna(0)
    panel['pct_eucalyptus'] = panel['pct_eucalyptus'].fillna(0)

    # --- SUMMARY ----------------------------------------------------------
    features = get_features(panel)
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"Panel: {panel.shape}, {len(features)} features, built in {elapsed:.0f}s")
    print(f"  Radios: {panel.redcode.nunique():,}, Years: {panel.year.min()}-{panel.year.max()}")
    print(f"  Target (loss): mean={panel.loss.mean()*100:.3f}%, std={panel.loss.std()*100:.3f}%")
    print(f"  NaN features (LightGBM handles natively):")
    na = panel[features].isna().sum()
    for col in na[na > len(panel) * 0.1].index:
        print(f"    {col:30s} {na[col]:>6,} ({na[col]/len(panel)*100:.1f}%)")
    print(f"{'=' * 60}")

    panel.to_parquet(PANEL_PATH, index=False)
    print(f"  Saved: {PANEL_PATH}")
    return panel


# ======================================================================
# TRAIN
# ======================================================================

def train_and_evaluate(panel=None):
    if panel is None:
        panel = pd.read_parquet(PANEL_PATH)

    features = get_features(panel)
    X = panel[features]
    y = panel['loss'].values
    depts = panel['dpto'].values
    years = panel['year'].values
    print(f"\nFeatures: {len(features)}, N={len(X):,}")

    results = {}

    # 1. Random 5-fold
    print(f"\n{'=' * 60}\nRandom 5-fold")
    m = _run_lgbm_cv(X, y, list(KFold(5, shuffle=True, random_state=42).split(X)))
    results['random_5fold'] = m
    print(f"  R2={m['r2']:.4f}  RMSE={m['rmse']:.5f}")

    # 2. Spatial LODO
    print(f"\n{'=' * 60}\nSpatial LODO")
    dept_codes = np.unique(depts)
    spatial_folds = [(np.where(depts != d)[0], np.where(depts == d)[0]) for d in dept_codes]
    m = _run_lgbm_cv(X, y, spatial_folds)
    results['spatial_lodo'] = m
    print(f"  R2={m['r2']:.4f}  RMSE={m['rmse']:.5f}")

    # 3. Temporal holdout: train 2001-2018, test 2019-2022
    print(f"\n{'=' * 60}\nTemporal holdout (train 2001-2018, test 2019-2022)")
    tr = np.where(years <= 2018)[0]
    te = np.where(years >= 2019)[0]
    m = _run_lgbm_cv(X, y, [(tr, te)])
    results['temporal'] = m
    print(f"  R2={m['r2']:.4f}  RMSE={m['rmse']:.5f}")

    # 4. Spatio-temporal: spatial LODO on test years only
    print(f"\n{'=' * 60}\nSpatio-temporal (LODO on 2019-2022)")
    test_panel = panel[panel.year >= 2019]
    train_panel = panel[panel.year <= 2018]
    X_train_full = train_panel[features]
    y_train_full = train_panel['loss'].values
    test_depts = test_panel['dpto'].values
    X_test_full = test_panel[features]
    y_test_full = test_panel['loss'].values

    all_t, all_p = [], []
    for d in np.unique(test_depts):
        # Train on all pre-2019 data + 2019-2022 from OTHER departments
        other_test = test_panel[test_panel.dpto != d]
        X_tr = pd.concat([X_train_full, other_test[features]])
        y_tr = np.concatenate([y_train_full, other_test['loss'].values])
        X_te = test_panel[test_panel.dpto == d][features]
        y_te = test_panel[test_panel.dpto == d]['loss'].values
        if len(y_te) < 5:
            continue
        mdl = lgb.LGBMRegressor(n_estimators=500, max_depth=8, learning_rate=0.05,
                                 num_leaves=63, min_child_samples=10,
                                 n_jobs=-1, random_state=42, verbose=-1)
        mdl.fit(X_tr, y_tr)
        all_t.extend(y_te)
        all_p.extend(mdl.predict(X_te))
    t, p = np.array(all_t), np.array(all_p)
    results['spatiotemporal'] = {
        "r2": float(r2_score(t, p)),
        "rmse": float(root_mean_squared_error(t, p)),
        "mae": float(mean_absolute_error(t, p)),
    }
    print(f"  R2={results['spatiotemporal']['r2']:.4f}")

    # Ablation
    print(f"\n{'=' * 60}\nAblation (spatial LODO)")
    baseline = results['spatial_lodo']['r2']
    print(f"  Baseline: R2={baseline:.4f}\n")
    for gn in FEATURE_GROUPS:
        avail = [f for f in FEATURE_GROUPS[gn] if f in features]
        if not avail:
            continue
        remaining = [f for f in features if f not in avail]
        ma = _run_lgbm_cv(panel[remaining], y, spatial_folds)
        d = baseline - ma['r2']
        print(f"  Drop {gn:20s} ({len(avail):2d}): R2={ma['r2']:.4f}  dR2={d:+.4f}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"{'Scheme':<25s} {'R2':>8s} {'RMSE':>10s}")
    print("-" * 45)
    for name, m in results.items():
        print(f"{name:<25s} {m['r2']:>7.4f}  {m['rmse']:>9.5f}")

    with open(RESULTS_PATH, 'w') as f:
        json.dump(results, f, indent=2)
    return results


# ======================================================================
# INTERPRET
# ======================================================================

def interpret(panel=None):
    if panel is None:
        panel = pd.read_parquet(PANEL_PATH)

    features = get_features(panel)
    X = panel[features]
    y = panel['loss'].values

    print("Training final model...")
    model = lgb.LGBMRegressor(
        n_estimators=500, max_depth=8, learning_rate=0.05,
        num_leaves=63, min_child_samples=10,
        n_jobs=-1, random_state=42, verbose=-1,
    )
    model.fit(X, y)
    print(f"  In-sample R2: {r2_score(y, model.predict(X)):.4f}")

    # SHAP
    print("\n=== SHAP ===")
    try:
        import shap
        sv = shap.TreeExplainer(model).shap_values(X)
        imp = pd.DataFrame({'feature': features,
                             'shap': np.abs(sv).mean(axis=0)}).sort_values('shap', ascending=False)
        for _, r in imp.iterrows():
            bar = "#" * int(r['shap'] / imp['shap'].max() * 40)
            print(f"  {r['feature']:30s} {r['shap']:.6f}  {bar}")

        print("\n  SHAP by group:")
        for gn, gf in FEATURE_GROUPS.items():
            av = [f for f in gf if f in features]
            total = sum(imp.loc[imp.feature == f, 'shap'].values[0]
                        for f in av if f in imp.feature.values)
            print(f"    {gn:20s}: {total:.6f}")

        shap_df = pd.DataFrame(sv, columns=[f'shap_{f}' for f in features])
        shap_df['redcode'] = panel['redcode'].values
        shap_df['year'] = panel['year'].values
        shap_df['loss'] = y
        shap_df['predicted'] = model.predict(X)
        shap_df.to_parquet(SHAP_PATH, index=False)
        print(f"\n  Saved: {SHAP_PATH}")
    except ImportError:
        print("  shap not installed")


# ======================================================================
# PROJECT (SSP scenarios)
# ======================================================================

def project(panel=None):
    if panel is None:
        panel = pd.read_parquet(PANEL_PATH)

    features = get_features(panel)
    X = panel[features]
    y = panel['loss'].values

    print("Training model for projection...")
    model = lgb.LGBMRegressor(
        n_estimators=500, max_depth=8, learning_rate=0.05,
        num_leaves=63, min_child_samples=10,
        n_jobs=-1, random_state=42, verbose=-1,
    )
    model.fit(X, y)

    # Load ISIMIP projections
    print("\nLoading ISIMIP3b projections...")
    isimip = _sql("""SELECT year, scenario, redcode, tas_mean, pr_total, hurs_mean
                     FROM isimip3b_annual WHERE year BETWEEN 2025 AND 2030""")
    print(f"  {len(isimip):,} projection rows")

    # Get latest static features for each radio
    latest = panel[panel.year == panel.year.max()].drop_duplicates('redcode')
    static_cols = [f for f in features if f not in
                   ['pdsi', 'water_deficit', 'vpd', 'soil_moisture', 'precip',
                    'temp_mean', 'frost_days', 'solar_radiation', 'dewpoint',
                    'burned_fraction', 'burn_count', 'mean_ndvi', 'mean_npp',
                    'mean_lai', 'mean_evi', 'mb_forest', 'mb_plantation',
                    'neighbors_loss_lag', 'loss_acceleration', 'viirs_radiance',
                    'cumul_loss']]

    projections = []
    for scenario in ['ssp126', 'ssp370', 'ssp585']:
        sc_data = isimip[isimip.scenario == scenario]
        for proj_year in range(2025, 2031):
            yr_data = sc_data[sc_data.year == proj_year]
            if yr_data.empty:
                continue

            proj_panel = latest[['redcode'] + static_cols].merge(
                yr_data[['redcode', 'tas_mean', 'pr_total']], on='redcode', how='inner')

            # Map ISIMIP vars to model features
            proj_panel['temp_mean'] = proj_panel['tas_mean']
            proj_panel['precip'] = proj_panel['pr_total']
            # Use last known values for features we can't project
            for c in features:
                if c not in proj_panel.columns:
                    if c in latest.columns:
                        proj_panel[c] = latest.set_index('redcode').loc[
                            proj_panel.redcode, c].values

            # Fill remaining NaN with panel median
            for c in features:
                if c in proj_panel.columns and proj_panel[c].isna().any():
                    proj_panel[c] = proj_panel[c].fillna(panel[c].median())

            X_proj = proj_panel[features]
            pred = model.predict(X_proj)
            proj_panel['predicted_loss'] = pred
            proj_panel['scenario'] = scenario
            proj_panel['year'] = proj_year
            projections.append(proj_panel[['redcode', 'year', 'scenario', 'predicted_loss']])

    proj_df = pd.concat(projections, ignore_index=True)

    # Summary
    print(f"\n{'=' * 60}")
    print("SSP Projections: Mean annual loss rate (%)")
    print(f"{'=' * 60}")
    for sc in ['ssp126', 'ssp370', 'ssp585']:
        for yr in range(2025, 2031):
            subset = proj_df[(proj_df.scenario == sc) & (proj_df.year == yr)]
            if len(subset) > 0:
                ml = subset.predicted_loss.mean() * 100
                print(f"  {sc} {yr}: {ml:.3f}%")

    # Historical comparison
    hist_mean = panel[panel.year.between(2019, 2022)].loss.mean() * 100
    print(f"\n  Historical 2019-2022 mean: {hist_mean:.3f}%")

    proj_df.to_parquet(PROJ_PATH, index=False)
    print(f"  Saved: {PROJ_PATH}")


# ======================================================================
# MAIN
# ======================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["build", "train", "interpret", "project", "all"],
                        default="all")
    args = parser.parse_args()
    panel = None
    if args.phase in ("build", "all"):
        panel = build_panel()
    if args.phase in ("train", "all"):
        train_and_evaluate(panel)
    if args.phase in ("interpret", "all"):
        interpret(panel)
    if args.phase in ("project", "all"):
        project(panel)


if __name__ == "__main__":
    main()
