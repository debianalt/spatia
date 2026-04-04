"""
Air quality exposure analysis: pollution × demographic vulnerability.

Crosses satellite-derived multi-pollutant data (PM2.5, NO2, AOD) with
census 2022 vulnerability indicators via building-weighted dasymetric
crosswalk. Computes inequality metrics for the npj Clean Air Perspective.

Inputs:
  - sat_air_quality.parquet           (H3 res9, percentile-ranked pollution)
  - h3_radio_crosswalk.parquet        (dasymetric, building-weighted)
  - PostgreSQL ndvi_misiones:
    - censo2022_variables             (49 indicators × 2012 radios)
    - radios_misiones                 (geometry)

Outputs:
  - air_quality_exposure.parquet      (H3 × pollution × vulnerability, ~68K inhabited hex)
  - air_quality_by_radio.parquet      (radio-level aggregated, N=2012)
  - air_quality_inequality.json       (CI, Erreygers, Theil, Moran's I, cluster counts)
  - air_quality_scale_effect.csv      (PM2.5 stats at 4 scales)

Usage:
  python pipeline/compute_air_quality_exposure.py
"""

import json
import os
import sys
import time

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import psycopg2
from libpysal.weights import Queen
from esda.moran import Moran_BV, Moran_Local_BV
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from config import OUTPUT_DIR

# ── Database ─────────────────────────────────────────────────────────────
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")
DB_NAME = os.getenv("PGDATABASE", "ndvi_misiones")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASS = os.getenv("PGPASSWORD", "")

# ── Paths ────────────────────────────────────────────────────────────────
AQ_PARQUET = os.path.join(OUTPUT_DIR, "sat_air_quality.parquet")
CROSSWALK_PATH = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk.parquet")

# ── Vulnerability variables (censo2022_variables) ────────────────────────
VULN_VARS = [
    'pct_nbi',                   # % households with unsatisfied basic needs
    'pct_hacinamiento_critico',  # % households with critical crowding
    'pct_adultos_mayores',       # % population over 65
    'pct_sin_instruccion',       # % without formal education
]
# pct_cobertura_salud is inverted: lower = more vulnerable
VULN_VARS_INVERTED = ['pct_cobertura_salud']

POP_COL = 'total_personas'


def percentile_rank(series):
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result


def geometric_mean(df, columns, floor=1.0):
    vals = df[columns].clip(lower=floor)
    return np.exp(np.log(vals).sum(axis=1) / len(columns))


# ══════════════════════════════════════════════════════════════════════════
# STEP 1: Load and merge data
# ══════════════════════════════════════════════════════════════════════════

def load_data():
    """Load pollution (H3), crosswalk, and census (PG)."""
    print("Loading pollution data...")
    aq = pd.read_parquet(AQ_PARQUET)
    # Keep raw percentile-ranked values + score
    print(f"  {len(aq):,} hexagons, columns: {list(aq.columns)}")

    print("Loading dasymetric crosswalk...")
    xw = pd.read_parquet(CROSSWALK_PATH)
    print(f"  {len(xw):,} rows, {xw['redcode'].nunique():,} radios, {xw['h3index'].nunique():,} hexagons")

    print("Loading census from PostgreSQL...")
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS,
    )
    all_vars = [POP_COL] + VULN_VARS + VULN_VARS_INVERTED
    cols = ', '.join(all_vars)
    census = pd.read_sql(f"SELECT redcode, {cols} FROM censo2022_variables", conn)
    conn.close()
    print(f"  {len(census):,} radios, pop={census[POP_COL].sum():,.0f}")

    return aq, xw, census


def build_h3_exposure(aq, xw, census):
    """Join pollution + vulnerability at H3 level via dasymetric crosswalk."""
    # Merge crosswalk with census
    xw_census = xw.merge(census, on='redcode', how='left')

    # For each H3, compute weighted vulnerability
    # weight = dasymetric weight (building-based fraction of radio)
    # Each H3 may overlap multiple radios → weighted average
    h3_groups = xw_census.groupby('h3index')

    records = []
    for h3id, group in h3_groups:
        w = group['weight'].values
        w_sum = w.sum()
        if w_sum == 0:
            continue

        row = {'h3index': h3id}
        # Population: sum of weighted pop
        row['pop'] = (group[POP_COL].fillna(0) * w).sum()

        # Vulnerability variables: weighted average
        for var in VULN_VARS + VULN_VARS_INVERTED:
            vals = group[var].fillna(0).values
            row[var] = np.average(vals, weights=w)

        # Department from redcode
        row['dpto'] = group['redcode'].iloc[0][:5]

        records.append(row)

    vuln_h3 = pd.DataFrame(records)

    # Merge with pollution
    exposure = aq.merge(vuln_h3, on='h3index', how='inner')
    print(f"  H3 exposure: {len(exposure):,} inhabited hexagons")

    # Compute vulnerability index
    rank_cols = []
    for var in VULN_VARS:
        col = f'{var}_rank'
        exposure[col] = percentile_rank(exposure[var]).round(1)
        rank_cols.append(col)
    for var in VULN_VARS_INVERTED:
        col = f'{var}_rank'
        exposure[col] = percentile_rank(-exposure[var]).round(1)  # invert
        rank_cols.append(col)

    exposure['vuln_index'] = geometric_mean(exposure, rank_cols, floor=1.0).round(1)

    return exposure


def build_radio_aggregated(aq, xw, census):
    """Aggregate pollution to radio level (weighted by dasymetric crosswalk)."""
    merged = xw.merge(aq[['h3index', 'score', 'c_pm25', 'c_no2', 'c_aod']], on='h3index', how='inner')

    # For each radio: weighted average of pollution across its hexagons
    radio_groups = merged.groupby('redcode')
    records = []
    for redcode, group in radio_groups:
        w = group['weight'].values
        w_sum = w.sum()
        if w_sum == 0:
            continue
        row = {'redcode': redcode}
        for col in ['score', 'c_pm25', 'c_no2', 'c_aod']:
            valid = group[col].notna()
            if valid.any():
                row[col] = np.average(group.loc[valid, col], weights=w[valid])
            else:
                row[col] = np.nan
        records.append(row)

    radio_poll = pd.DataFrame(records)

    # Merge with census
    radio = radio_poll.merge(census, on='redcode', how='inner')
    radio['dpto'] = radio['redcode'].str[:5]

    # Vulnerability index at radio level
    rank_cols = []
    for var in VULN_VARS:
        col = f'{var}_rank'
        radio[col] = percentile_rank(radio[var]).round(1)
        rank_cols.append(col)
    for var in VULN_VARS_INVERTED:
        col = f'{var}_rank'
        radio[col] = percentile_rank(-radio[var]).round(1)
        rank_cols.append(col)
    radio['vuln_index'] = geometric_mean(radio, rank_cols, floor=1.0).round(1)

    print(f"  Radio aggregated: {len(radio):,} radios")
    return radio


# ══════════════════════════════════════════════════════════════════════════
# STEP 2: Scale effect analysis
# ══════════════════════════════════════════════════════════════════════════

def compute_scale_effect(radio):
    """PM2.5 statistics at 4 scales: provincial, departmental, radio, H3."""
    results = []

    # Provincial (1 value)
    pm = radio['c_pm25'].dropna()
    pop = radio[POP_COL].fillna(0)
    wmean = np.average(pm, weights=pop[pm.index]) if pop.sum() > 0 else pm.mean()
    results.append({
        'scale': 'Provincial', 'n_units': 1,
        'mean': wmean, 'std': 0, 'cv': 0,
        'p5': wmean, 'p95': wmean, 'range': 0,
    })

    # Departmental (17 dptos)
    dept = radio.groupby('dpto').apply(
        lambda g: np.average(g['c_pm25'].dropna(),
                             weights=g.loc[g['c_pm25'].notna(), POP_COL].fillna(1))
    )
    results.append({
        'scale': 'Departmental', 'n_units': len(dept),
        'mean': dept.mean(), 'std': dept.std(), 'cv': dept.std() / dept.mean(),
        'p5': dept.quantile(0.05), 'p95': dept.quantile(0.95),
        'range': dept.max() - dept.min(),
    })

    # Radio (2012)
    results.append({
        'scale': 'Radio censal', 'n_units': len(pm),
        'mean': pm.mean(), 'std': pm.std(), 'cv': pm.std() / pm.mean(),
        'p5': pm.quantile(0.05), 'p95': pm.quantile(0.95),
        'range': pm.max() - pm.min(),
    })

    # H3 res9 (from sat_air_quality.parquet)
    aq = pd.read_parquet(AQ_PARQUET)
    h3pm = aq['c_pm25'].dropna()
    results.append({
        'scale': 'H3 res9', 'n_units': len(h3pm),
        'mean': h3pm.mean(), 'std': h3pm.std(), 'cv': h3pm.std() / h3pm.mean(),
        'p5': h3pm.quantile(0.05), 'p95': h3pm.quantile(0.95),
        'range': h3pm.max() - h3pm.min(),
    })

    return pd.DataFrame(results)


# ══════════════════════════════════════════════════════════════════════════
# STEP 3: Concentration Index
# ══════════════════════════════════════════════════════════════════════════

def compute_concentration_index(radio):
    """Erreygers-corrected CI of PM2.5 exposure ranked by vulnerability."""
    df = radio.dropna(subset=['c_pm25', 'vuln_index', POP_COL])
    df = df[df[POP_COL] > 0]

    pm25 = df['c_pm25'].values
    vuln = df['vuln_index'].values
    pop = df[POP_COL].values

    # Fractional rank by vulnerability (ascending: least vulnerable → most)
    rank = pd.Series(vuln).rank(pct=True).values
    mu = np.average(pm25, weights=pop)

    # Standard CI
    ci = 2 / mu * np.cov(pm25, rank, aweights=pop)[0, 1]

    # Erreygers correction
    pm_range = pm25.max() - pm25.min()
    eci = 4 * mu / pm_range * ci if pm_range > 0 else 0

    # Concentration curve data
    sort_idx = np.argsort(vuln)
    cum_pop = np.cumsum(pop[sort_idx]) / pop.sum()
    pm_weighted = pm25[sort_idx] * pop[sort_idx]
    cum_pm = np.cumsum(pm_weighted) / pm_weighted.sum()
    # Downsample
    n = len(cum_pop)
    idx = np.linspace(0, n - 1, min(500, n), dtype=int)
    curve = pd.DataFrame({'cum_pop': cum_pop[idx], 'cum_pm25': cum_pm[idx]})

    return ci, eci, mu, curve


# ══════════════════════════════════════════════════════════════════════════
# STEP 4: Theil decomposition
# ══════════════════════════════════════════════════════════════════════════

def compute_theil(radio):
    """Theil T index of PM2.5, decomposed between/within departamento."""
    df = radio.dropna(subset=['c_pm25', POP_COL])
    df = df[df[POP_COL] > 0]

    pm25 = df['c_pm25'].values
    pop = df[POP_COL].values
    groups = df['dpto'].values

    total_pop = pop.sum()
    mu = np.average(pm25, weights=pop)

    # Overall Theil T
    shares = pop / total_pop
    ratios = pm25 / mu
    valid = ratios > 0
    theil_t = float(np.sum(shares[valid] * ratios[valid] * np.log(ratios[valid])))

    # Between-group
    gdf = pd.DataFrame({'pm25': pm25, 'pop': pop, 'group': groups})
    gstats = gdf.groupby('group').apply(
        lambda g: pd.Series({
            'pop_share': g['pop'].sum() / total_pop,
            'mean_pm25': np.average(g['pm25'], weights=g['pop']),
        }),
        include_groups=False,
    )
    between = 0.0
    for _, row in gstats.iterrows():
        r = row['mean_pm25'] / mu
        if r > 0:
            between += row['pop_share'] * r * np.log(r)

    within = theil_t - between

    return {
        'theil_t': theil_t,
        'between': between,
        'within': within,
        'between_pct': between / theil_t * 100 if theil_t > 0 else 0,
        'within_pct': within / theil_t * 100 if theil_t > 0 else 0,
    }


# ══════════════════════════════════════════════════════════════════════════
# STEP 5: Bivariate LISA
# ══════════════════════════════════════════════════════════════════════════

def compute_lisa(radio):
    """Bivariate LISA: PM2.5 × vulnerability at radio level."""
    print("  Loading radio geometries...")
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS,
    )
    radios_gdf = gpd.read_postgis(
        "SELECT redcode, geom FROM radios_misiones", conn, geom_col='geom'
    )
    conn.close()

    # Merge with radio-level data
    gdf = radios_gdf.merge(radio[['redcode', 'c_pm25', 'vuln_index']], on='redcode', how='inner')
    gdf = gdf.dropna(subset=['c_pm25', 'vuln_index']).reset_index(drop=True)
    print(f"  Radios with data: {len(gdf):,}")

    # Standardise
    gdf['pm25_z'] = (gdf['c_pm25'] - gdf['c_pm25'].mean()) / gdf['c_pm25'].std()
    gdf['vuln_z'] = (gdf['vuln_index'] - gdf['vuln_index'].mean()) / gdf['vuln_index'].std()

    # Spatial weights
    print("  Computing Queen contiguity weights...")
    w = Queen.from_dataframe(gdf, geom_col='geom', use_index=False)
    w.transform = 'r'
    print(f"  Mean neighbours: {w.mean_neighbors:.1f}")

    # Global bivariate Moran's I
    print("  Global Bivariate Moran's I...")
    moran_bv = Moran_BV(gdf['pm25_z'].values, gdf['vuln_z'].values, w, permutations=999)
    print(f"  I = {moran_bv.I:.4f}, p = {moran_bv.p_sim:.4f}")

    # Local LISA
    print("  Local Bivariate LISA (999 permutations)...")
    lisa = Moran_Local_BV(gdf['pm25_z'].values, gdf['vuln_z'].values, w, permutations=999)

    # Classify
    labels = []
    for i in range(len(lisa.Is)):
        if lisa.p_sim[i] > 0.05:
            labels.append('Not significant')
        else:
            q = lisa.q[i]
            labels.append({1: 'High-High', 2: 'Low-High', 3: 'Low-Low', 4: 'High-Low'}.get(q, 'NS'))

    gdf['lisa_cluster'] = labels
    gdf['lisa_I'] = lisa.Is
    gdf['lisa_p'] = lisa.p_sim

    counts = gdf['lisa_cluster'].value_counts()
    print("  Cluster counts:")
    for cluster, count in counts.items():
        print(f"    {cluster}: {count} ({count/len(gdf)*100:.1f}%)")

    return {
        'moran_I': float(moran_bv.I),
        'moran_p': float(moran_bv.p_sim),
        'clusters': counts.to_dict(),
        'n_radios': len(gdf),
    }, gdf


# ══════════════════════════════════════════════════════════════════════════
# STEP 6: Multi-pollutant clustering
# ══════════════════════════════════════════════════════════════════════════

def compute_pollution_profiles(exposure):
    """K-means clustering on [pm25, no2, aod] for inhabited hexagons."""
    poll_cols = ['c_pm25', 'c_no2', 'c_aod']
    df = exposure.dropna(subset=poll_cols).copy()
    print(f"  Clustering {len(df):,} inhabited hexagons...")

    X = df[poll_cols].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Optimal k
    scores = {}
    for k in range(3, 7):
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = km.fit_predict(X_scaled)
        s = silhouette_score(X_scaled, labels, sample_size=min(10000, len(X_scaled)))
        scores[k] = s
    best_k = max(scores, key=scores.get)
    print(f"  Best k={best_k} (silhouette={scores[best_k]:.3f})")

    km = KMeans(n_clusters=best_k, n_init=20, random_state=42)
    df['cluster'] = km.fit_predict(X_scaled)

    centers = scaler.inverse_transform(km.cluster_centers_)
    cluster_info = []
    for i in range(best_k):
        subset = df[df['cluster'] == i]
        c = centers[i]
        info = {
            'cluster': i,
            'pm25_pctile': c[0], 'no2_pctile': c[1], 'aod_pctile': c[2],
            'n_hexagons': len(subset),
            'mean_vuln': subset['vuln_index'].mean(),
            'mean_pop': subset['pop'].mean(),
        }
        cluster_info.append(info)
        print(f"    Cluster {i}: PM2.5={c[0]:.1f}, NO2={c[1]:.1f}, AOD={c[2]:.1f} | "
              f"n={len(subset):,} | vuln={info['mean_vuln']:.1f}")

    return df, cluster_info


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()

    # Load
    aq, xw, census = load_data()

    # Build exposure datasets
    print("\n=== Building H3 exposure dataset ===")
    exposure = build_h3_exposure(aq, xw, census)

    print("\n=== Building radio-level aggregated dataset ===")
    radio = build_radio_aggregated(aq, xw, census)

    # Save intermediate parquets
    exposure_path = os.path.join(OUTPUT_DIR, "air_quality_exposure.parquet")
    exposure.to_parquet(exposure_path, index=False)
    print(f"  Saved: {exposure_path} ({os.path.getsize(exposure_path)/1024:.0f} KB)")

    radio_path = os.path.join(OUTPUT_DIR, "air_quality_by_radio.parquet")
    radio.to_parquet(radio_path, index=False)
    print(f"  Saved: {radio_path} ({os.path.getsize(radio_path)/1024:.0f} KB)")

    # Analyses
    print("\n=== Scale Effect ===")
    scale = compute_scale_effect(radio)
    print(scale.to_string(index=False))
    scale_path = os.path.join(OUTPUT_DIR, "air_quality_scale_effect.csv")
    scale.to_csv(scale_path, index=False)

    print("\n=== Concentration Index ===")
    ci, eci, mu, curve = compute_concentration_index(radio)
    direction = "pro-vulnerable" if ci > 0 else "pro-affluent"
    print(f"  Mean PM2.5 (percentile): {mu:.1f}")
    print(f"  CI = {ci:.4f} ({direction})")
    print(f"  Erreygers CI = {eci:.4f}")
    curve.to_csv(os.path.join(OUTPUT_DIR, "air_quality_concentration_curve.csv"), index=False)

    print("\n=== Theil Decomposition ===")
    theil = compute_theil(radio)
    print(f"  Theil T = {theil['theil_t']:.4f}")
    print(f"  Between-dept: {theil['between']:.4f} ({theil['between_pct']:.1f}%)")
    print(f"  Within-dept:  {theil['within']:.4f} ({theil['within_pct']:.1f}%)")

    print("\n=== Bivariate LISA ===")
    lisa_metrics, lisa_gdf = compute_lisa(radio)
    lisa_gdf.to_parquet(os.path.join(OUTPUT_DIR, "air_quality_lisa_radios.parquet"), index=False)

    print("\n=== Multi-pollutant Profiles ===")
    profiles, cluster_info = compute_pollution_profiles(exposure)
    profiles.to_parquet(os.path.join(OUTPUT_DIR, "air_quality_profiles.parquet"), index=False)

    # Save all metrics to JSON
    metrics = {
        'concentration_index': {'ci': ci, 'erreygers_ci': eci, 'mean_pm25_pctile': mu},
        'theil': theil,
        'lisa': lisa_metrics,
        'clusters': cluster_info,
        'scale_effect': scale.to_dict(orient='records'),
        'metadata': {
            'n_radios': len(radio),
            'n_h3_inhabited': len(exposure),
            'n_h3_total': len(aq),
            'total_population': int(census[POP_COL].sum()),
            'vuln_vars': VULN_VARS + VULN_VARS_INVERTED,
        },
    }
    metrics_path = os.path.join(OUTPUT_DIR, "air_quality_inequality.json")
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"\n  All metrics: {metrics_path}")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s")


if __name__ == "__main__":
    main()
