"""
Socio-ecological deforestation risk model v2 — H3 res-7 with landscape features.

Predicts forest cover change rate (%/year) at H3 res-7 hexagons using
biophysical, socioeconomic, institutional, accessibility, and LANDSCAPE
STRUCTURE features (edge density, neighbor connectivity, proximity to
deforestation front).

Key question: how much do socioeconomic and landscape structure variables
add to deforestation prediction beyond biophysical aptitude?

Unit: H3 res-7 (N~6,800 forested hexagons)
Target: annual tree cover change rate (%/year), 2017-2023

Usage:
  python pipeline/model_deforestation_risk.py --phase all
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
from scipy.stats import linregress
from sklearn.metrics import r2_score, mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import KFold

from config import OUTPUT_DIR

warnings.filterwarnings("ignore", category=FutureWarning)

RADIO_DATA = os.path.join(OUTPUT_DIR, "radio_data")
PANEL_PATH = os.path.join(OUTPUT_DIR, "deforestation_risk_panel.parquet")
RESULTS_PATH = os.path.join(OUTPUT_DIR, "deforestation_risk_results.json")
SHAP_PATH = os.path.join(OUTPUT_DIR, "deforestation_risk_shap.parquet")

FEATURE_GROUPS = {
    "biophysical": ["elev_mean", "slope_mean", "soil_ph", "clay", "sand",
                     "soc", "twi_merit_mean", "hand_mean"],
    "forest_baseline": ["treecover2000", "ndvi_baseline", "npp_baseline",
                         "tree_cover_2017"],
    "fire_history": ["fire_mean", "fire_trend", "fire_max"],
    "climate": ["temp_mean_bl", "precip_bl", "frost_bl", "radiation_bl"],
    "socioeconomic": ["pct_nbi", "pct_sin_instruccion", "pct_hacinamiento_critico",
                       "tasa_empleo", "pct_cobertura_salud", "tamano_medio_hogar",
                       "pct_originarios", "densidad_hab_km2",
                       "pct_jefatura_femenina", "pct_combustible_precario"],
    "land_tenure": ["area_media_rural", "n_parcelas_rural", "pct_propietario"],
    "accessibility": ["dist_primary_m", "road_density", "travel_posadas",
                       "travel_cabecera"],
    "institutional": ["otbn_frac_i", "otbn_frac_ii", "inside_anp",
                       "in_corredor_verde"],
    "economic_pressure": ["viirs_bl", "building_density"],
    "landscape": ["forest_frac_neighbors", "edge_density",
                   "dist_deforest_front", "prior_loss_neighbors"],
}


def get_features(panel, exclude_groups=None):
    exclude_groups = exclude_groups or []
    feats = []
    for gname, gf in FEATURE_GROUPS.items():
        if gname not in exclude_groups:
            feats.extend(gf)
    return [f for f in feats if f in panel.columns]


def _aggregate_radio_to_r7(radio_df, cols, crosswalk, parents, agg='mean'):
    """Aggregate radio-level data to H3 res-7 via normalized areal crosswalk."""
    merged = crosswalk.merge(radio_df, on='redcode', how='inner')
    totals = merged.groupby('h3index')['weight'].transform('sum')
    merged['w_norm'] = merged['weight'] / totals

    for c in cols:
        merged[f'w_{c}'] = merged[c] * merged['w_norm']

    h3_agg = merged.groupby('h3index')[[f'w_{c}' for c in cols]].sum().reset_index()
    h3_agg.columns = ['h3index'] + cols
    h3_agg = h3_agg.merge(parents, on='h3index', how='inner')
    r7 = h3_agg.groupby('h3_res7')[cols].mean().reset_index()
    return r7.rename(columns={'h3_res7': 'h3index'})


def _run_lgbm_cv(X, y, folds):
    all_true, all_pred = [], []
    for tr, te in folds:
        m = lgb.LGBMRegressor(
            n_estimators=500, max_depth=8, learning_rate=0.05,
            num_leaves=63, min_child_samples=10,
            subsample=0.8, colsample_bytree=0.8,
            reg_alpha=0.1, reg_lambda=0.1,
            n_jobs=-1, random_state=42, verbose=-1,
        )
        m.fit(X.iloc[tr], y[tr])
        all_true.extend(y[te])
        all_pred.extend(m.predict(X.iloc[te]))
    t, p = np.array(all_true), np.array(all_pred)
    return {
        "r2": float(r2_score(t, p)),
        "rmse": float(root_mean_squared_error(t, p)),
        "mae": float(mean_absolute_error(t, p)),
    }


# ======================================================================
# BUILD
# ======================================================================

def build_panel():
    t0 = time.time()
    xw = pd.read_parquet(os.path.join(OUTPUT_DIR, "h3_radio_crosswalk_areal.parquet"))
    parents = pd.read_parquet(os.path.join(OUTPUT_DIR, "h3_parent_crosswalk.parquet"))[['h3index', 'h3_res7']]
    rsm = pd.read_parquet(os.path.join(OUTPUT_DIR, "radio_stats_master.parquet"))

    # --- TARGET: VCF 2017 & 2023 aggregated to res-7 ---------------------
    print("Building target (VCF 2017-2023 -> H3 res-7)...")
    vcf = pd.read_parquet(os.path.join(RADIO_DATA, "vcf_annual.parquet"))

    def vcf_to_r7(year, col_out):
        df = vcf[vcf.year == year][['redcode', 'tree_cover']]
        return _aggregate_radio_to_r7(df, ['tree_cover'], xw, parents).rename(
            columns={'tree_cover': col_out})

    panel = vcf_to_r7(2017, 'tree_cover_2017').merge(
        vcf_to_r7(2023, 'tree_cover_2023'), on='h3index', how='inner')
    panel['tc_change_annual'] = (panel.tree_cover_2023 - panel.tree_cover_2017) / 6.0
    panel = panel[panel.tree_cover_2017 > 10].copy()
    print(f"  Forested hex: {len(panel):,}")
    print(f"  Change: mean={panel.tc_change_annual.mean():.4f}, std={panel.tc_change_annual.std():.4f}")
    print(f"  Losing: {(panel.tc_change_annual < 0).sum()} ({(panel.tc_change_annual<0).mean()*100:.1f}%)")

    # --- BIOPHYSICAL (radio -> r7) ----------------------------------------
    print("\nBiophysical...")
    terrain = pd.read_parquet(os.path.join(RADIO_DATA, "fabdem_terrain.parquet"))
    soil = pd.read_parquet(os.path.join(RADIO_DATA, "soilgrids.parquet")).rename(columns={'ph': 'soil_ph'})
    hydro = pd.read_parquet(os.path.join(RADIO_DATA, "merit_hydro.parquet"))
    for df, cols in [(terrain, ['elev_mean', 'slope_mean']),
                      (soil, ['soil_ph', 'clay', 'sand', 'soc']),
                      (hydro, ['twi_merit_mean', 'hand_mean'])]:
        panel = panel.merge(_aggregate_radio_to_r7(df, cols, xw, parents),
                            on='h3index', how='left')

    # --- FOREST BASELINE --------------------------------------------------
    print("Forest baseline...")
    hansen = pd.read_parquet(os.path.join(RADIO_DATA, "hansen_baseline.parquet"))
    panel = panel.merge(_aggregate_radio_to_r7(hansen, ['treecover2000'], xw, parents),
                        on='h3index', how='left')

    ndvi = pd.read_parquet(os.path.join(RADIO_DATA, "ndvi_annual_mean.parquet"))
    ndvi_bl = ndvi[ndvi.year.between(2013, 2017)].groupby('redcode')['mean_ndvi'].mean().reset_index()
    ndvi_bl.columns = ['redcode', 'ndvi_baseline']
    panel = panel.merge(_aggregate_radio_to_r7(ndvi_bl, ['ndvi_baseline'], xw, parents),
                        on='h3index', how='left')

    npp = pd.read_parquet(os.path.join(RADIO_DATA, "npp_annual.parquet"))
    npp_bl = npp[npp.year.between(2013, 2017)].groupby('redcode')['mean_npp'].mean().reset_index()
    npp_bl.columns = ['redcode', 'npp_baseline']
    panel = panel.merge(_aggregate_radio_to_r7(npp_bl, ['npp_baseline'], xw, parents),
                        on='h3index', how='left')

    # --- FIRE HISTORY -----------------------------------------------------
    print("Fire history...")
    fire = pd.read_parquet(os.path.join(RADIO_DATA, "fire_annual.parquet"))
    fire_bl = fire[fire.year.between(2013, 2017)].groupby('redcode').agg(
        fire_mean=('burned_fraction', 'mean'),
        fire_max=('burned_fraction', 'max'),
    ).reset_index()
    panel = panel.merge(_aggregate_radio_to_r7(fire_bl, ['fire_mean', 'fire_max'], xw, parents),
                        on='h3index', how='left')

    # Fire trend (2000-2017)
    fire_pre = fire[fire.year.between(2000, 2017)]
    trends = []
    for rc, g in fire_pre.groupby('redcode'):
        if len(g) < 10:
            continue
        sl, _, _, _, _ = linregress(g['year'], g['burned_fraction'])
        trends.append({'redcode': rc, 'fire_trend': sl})
    ft = pd.DataFrame(trends)
    panel = panel.merge(_aggregate_radio_to_r7(ft, ['fire_trend'], xw, parents),
                        on='h3index', how='left')

    # --- CLIMATE BASELINE -------------------------------------------------
    print("Climate...")
    era5 = pd.read_parquet(os.path.join(RADIO_DATA, "era5_annual.parquet"))
    era5_bl = era5[era5.year.between(2013, 2017)].groupby('redcode').agg(
        temp_mean_bl=('temp_mean', 'mean'),
        frost_bl=('frost_days', 'mean'),
        radiation_bl=('solar_radiation', 'mean'),
    ).reset_index()
    panel = panel.merge(_aggregate_radio_to_r7(era5_bl, ['temp_mean_bl', 'frost_bl', 'radiation_bl'],
                                                xw, parents), on='h3index', how='left')

    chirps = pd.read_parquet(os.path.join(RADIO_DATA, "chirps_annual.parquet"))
    chirps_bl = chirps[chirps.year.between(2013, 2017)].groupby('redcode')['total_mm'].mean().reset_index()
    chirps_bl.columns = ['redcode', 'precip_bl']
    panel = panel.merge(_aggregate_radio_to_r7(chirps_bl, ['precip_bl'], xw, parents),
                        on='h3index', how='left')

    # --- SOCIOECONOMIC (census -> dasymetric -> r7) -----------------------
    print("Socioeconomic...")
    census = pd.read_parquet(os.path.join(RADIO_DATA, "censo2022_variables.parquet"))
    socio_cols = ['pct_nbi', 'pct_sin_instruccion', 'pct_hacinamiento_critico',
                  'tasa_empleo', 'pct_cobertura_salud', 'tamano_medio_hogar',
                  'pct_originarios', 'densidad_hab_km2', 'pct_jefatura_femenina',
                  'pct_combustible_precario', 'pct_propietario']
    panel = panel.merge(_aggregate_radio_to_r7(census, socio_cols, xw, parents),
                        on='h3index', how='left')

    # --- LAND TENURE ------------------------------------------------------
    print("Land tenure...")
    cat = pd.read_parquet(os.path.join(OUTPUT_DIR, "catastro_by_radio.parquet"))
    cat_cols = ['area_media_rural_m2', 'n_parcelas_rural']
    cat_r = cat[['redcode'] + cat_cols].rename(
        columns={'area_media_rural_m2': 'area_media_rural'})
    panel = panel.merge(_aggregate_radio_to_r7(cat_r, ['area_media_rural', 'n_parcelas_rural'],
                                                xw, parents), on='h3index', how='left')

    # --- ACCESSIBILITY ----------------------------------------------------
    print("Accessibility...")
    roads = pd.read_parquet(os.path.join(RADIO_DATA, "road_access.parquet"))
    roads_r = roads[['redcode', 'dist_primary_m', 'road_density_km_per_km2']].rename(
        columns={'road_density_km_per_km2': 'road_density'})
    panel = panel.merge(_aggregate_radio_to_r7(roads_r, ['dist_primary_m', 'road_density'],
                                                xw, parents), on='h3index', how='left')
    for c in ['travel_min_posadas', 'travel_min_cabecera']:
        if c in rsm.columns:
            short = c.replace('travel_min_', 'travel_')
            d = rsm[['redcode', c]].rename(columns={c: short})
            panel = panel.merge(_aggregate_radio_to_r7(d, [short], xw, parents),
                                on='h3index', how='left')

    # --- INSTITUTIONAL ----------------------------------------------------
    print("Institutional...")
    for c in ['otbn_frac_i', 'otbn_frac_ii', 'inside_anp', 'in_corredor_verde']:
        if c in rsm.columns:
            d = rsm[['redcode', c]].copy()
            d[c] = d[c].fillna(0).astype(float)
            panel = panel.merge(_aggregate_radio_to_r7(d, [c], xw, parents),
                                on='h3index', how='left')

    # --- ECONOMIC PRESSURE ------------------------------------------------
    print("Economic pressure...")
    viirs = pd.read_parquet(os.path.join(RADIO_DATA, "viirs_annual.parquet"))
    viirs_bl = viirs[viirs.year.between(2015, 2017)].groupby('redcode')['mean_radiance'].mean().reset_index()
    viirs_bl.columns = ['redcode', 'viirs_bl']
    panel = panel.merge(_aggregate_radio_to_r7(viirs_bl, ['viirs_bl'], xw, parents),
                        on='h3index', how='left')
    if 'building_density_per_km2' in rsm.columns:
        d = rsm[['redcode', 'building_density_per_km2']].rename(
            columns={'building_density_per_km2': 'building_density'})
        panel = panel.merge(_aggregate_radio_to_r7(d, ['building_density'], xw, parents),
                            on='h3index', how='left')

    # --- LANDSCAPE STRUCTURE (computed from H3 grid) ----------------------
    print("Landscape structure...")
    hex_set = set(panel.h3index.values)
    all_hex_tc = panel.set_index('h3index')['tree_cover_2017']

    # Prior loss (2010-2017): which hex already lost forest?
    tc10_r7 = vcf_to_r7(2010, 'tc_2010')
    prior = panel[['h3index']].merge(tc10_r7, on='h3index', how='left')
    prior = prior.merge(panel[['h3index', 'tree_cover_2017']], on='h3index')
    prior['prior_loss'] = prior['tc_2010'] - prior['tree_cover_2017']  # positive = loss
    prior_loss_map = prior.set_index('h3index')['prior_loss']

    records = []
    for hx in panel.h3index.values:
        ring = h3.grid_ring(hx, 1)
        neighbors_in = [n for n in ring if n in hex_set]
        if not neighbors_in:
            records.append({'h3index': hx, 'forest_frac_neighbors': np.nan,
                            'edge_density': np.nan, 'dist_deforest_front': np.nan,
                            'prior_loss_neighbors': np.nan})
            continue

        # Forest fraction of neighbors
        n_tc = [all_hex_tc.get(n, 0) for n in neighbors_in]
        forest_frac = sum(1 for tc in n_tc if tc > 30) / len(neighbors_in)

        # Edge density: fraction of neighbors that are non-forest (<10%)
        edge = sum(1 for tc in n_tc if tc < 10) / len(neighbors_in)

        # Prior loss in neighborhood
        n_prior = [prior_loss_map.get(n, 0) for n in neighbors_in]
        prior_loss_n = np.mean([p for p in n_prior if not np.isnan(p)]) if n_prior else 0

        # Distance to deforestation front (ring search up to 3)
        dist = np.nan
        for d in range(1, 4):
            ring_d = h3.grid_ring(hx, d)
            for n in ring_d:
                pl = prior_loss_map.get(n, 0)
                if not np.isnan(pl) and pl > 5:  # >5% loss = deforestation front
                    dist = float(d)
                    break
            if not np.isnan(dist):
                break

        records.append({
            'h3index': hx,
            'forest_frac_neighbors': forest_frac,
            'edge_density': edge,
            'dist_deforest_front': dist,
            'prior_loss_neighbors': prior_loss_n,
        })

    landscape = pd.DataFrame(records)
    panel = panel.merge(landscape, on='h3index', how='left')
    print(f"  Landscape features added for {len(records):,} hex")

    # --- DEPARTMENT -------------------------------------------------------
    dominant_xw = xw.sort_values('weight', ascending=False).drop_duplicates('h3index')
    dominant_xw['dpto'] = dominant_xw['redcode'].str[:5]
    dom_r7 = dominant_xw.merge(parents, on='h3index')[['h3_res7', 'dpto']]
    dom_r7 = dom_r7.drop_duplicates('h3_res7').rename(columns={'h3_res7': 'h3index'})
    panel = panel.merge(dom_r7, on='h3index', how='left')

    # --- SUMMARY ----------------------------------------------------------
    features = get_features(panel)
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"Panel: {panel.shape}, {len(features)} features, built in {elapsed:.0f}s")
    print(f"  Forested hex: {len(panel):,}")
    print(f"  Losing: {(panel.tc_change_annual < 0).sum()} ({(panel.tc_change_annual<0).mean()*100:.1f}%)")
    na = panel[features].isna().sum()
    na_cols = na[na > 0]
    if len(na_cols) > 0:
        print(f"  NaN features: {len(na_cols)} cols (LightGBM handles natively)")
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
    y = panel['tc_change_annual'].values
    groups = panel['dpto'].values
    print(f"\nFeatures: {len(features)}, N={len(X):,}")

    results = {}

    # Random 5-fold
    print(f"\n{'=' * 60}\nRandom 5-fold")
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    m = _run_lgbm_cv(X, y, list(kf.split(X)))
    results['random_5fold'] = m
    print(f"  R2={m['r2']:.4f}  RMSE={m['rmse']:.4f}")

    # Spatial LODO
    print(f"\n{'=' * 60}\nSpatial LODO")
    depts = np.unique(groups[~pd.isna(groups)])
    spatial_folds = [(np.where(groups != d)[0], np.where(groups == d)[0])
                     for d in depts if np.where(groups == d)[0].shape[0] >= 10]
    m = _run_lgbm_cv(X, y, spatial_folds)
    results['spatial_lodo'] = m
    print(f"  R2={m['r2']:.4f}  RMSE={m['rmse']:.4f}")

    # Ablation
    print(f"\n{'=' * 60}\nAblation (spatial LODO)")
    baseline = results['spatial_lodo']['r2']
    print(f"  Baseline: R2={baseline:.4f}\n")
    for gname in FEATURE_GROUPS:
        avail = [f for f in FEATURE_GROUPS[gname] if f in features]
        if not avail:
            continue
        remaining = [f for f in features if f not in avail]
        m_a = _run_lgbm_cv(panel[remaining], y, spatial_folds)
        delta = baseline - m_a['r2']
        print(f"  Drop {gname:20s} ({len(avail):2d}): R2={m_a['r2']:.4f}  dR2={delta:+.4f}")

    # Summary
    print(f"\n{'=' * 60}")
    for name, m in results.items():
        print(f"  {name:<25s} R2={m['r2']:.4f}  RMSE={m['rmse']:.4f}")

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
    y = panel['tc_change_annual'].values

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
            print(f"  {r['feature']:35s} {r['shap']:.4f}  {bar}")

        print("\n  SHAP by group:")
        for gn, gf in FEATURE_GROUPS.items():
            av = [f for f in gf if f in features]
            total = sum(imp.loc[imp.feature == f, 'shap'].values[0] for f in av if f in imp.feature.values)
            print(f"    {gn:20s}: {total:.4f}")

        shap_df = pd.DataFrame(sv, columns=[f'shap_{f}' for f in features])
        shap_df['h3index'] = panel['h3index'].values
        shap_df['tc_change_annual'] = y
        shap_df['predicted'] = model.predict(X)
        shap_df.to_parquet(SHAP_PATH, index=False)
        print(f"\n  Saved: {SHAP_PATH}")
    except ImportError:
        print("  shap not installed")

    # Profile
    print("\n=== Profile: worst vs best 20% ===")
    q20 = np.percentile(y, 20)
    q80 = np.percentile(y, 80)
    worst = panel[y <= q20]
    best = panel[y >= q80]
    print(f"  Worst 20% (n={len(worst)}): {worst.tc_change_annual.mean():.3f}%/yr")
    print(f"  Best 20% (n={len(best)}): {best.tc_change_annual.mean():.3f}%/yr\n")
    for c in ['pct_nbi', 'pct_sin_instruccion', 'pct_originarios', 'tasa_empleo',
              'pct_propietario', 'slope_mean', 'dist_primary_m', 'tree_cover_2017',
              'n_parcelas_rural', 'area_media_rural', 'travel_cabecera', 'road_density',
              'forest_frac_neighbors', 'edge_density', 'prior_loss_neighbors',
              'otbn_frac_ii']:
        if c not in panel.columns:
            continue
        w, b = worst[c].mean(), best[c].mean()
        print(f"  {c:30s}  worst={w:>10.2f}  best={b:>10.2f}  diff={w-b:>+10.2f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["build", "train", "interpret", "all"], default="all")
    args = parser.parse_args()
    panel = None
    if args.phase in ("build", "all"):
        panel = build_panel()
    if args.phase in ("train", "all"):
        train_and_evaluate(panel)
    if args.phase in ("interpret", "all"):
        interpret(panel)


if __name__ == "__main__":
    main()
