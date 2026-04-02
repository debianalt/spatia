"""
Compute 11 composite satellite/census scores at H3 res-9 for Spatia.

Methodology: PCA-validated geometric mean (OECD Handbook / UNDP HDI).
  1. Reads radio-level data from PostGIS, projects onto H3 via areal crosswalk
  2. Normalizes each component via percentile rank (0-100)
  3. Runs PCA diagnostics (correlation matrix, KMO, Bartlett's, varimax)
  4. Selects variables by dropping redundant pairs (|r| > 0.70)
  5. Computes geometric mean of retained components (floor=1.0, HDI-style)

Analyses:
  1. environmental_risk  — Fire, deforestation, thermal amplitude, slope, HAND
  2. climate_comfort     — LST day/night, precipitation, frost, water stress
  3. green_capital       — NDVI, tree cover, NPP, LAI, VCF
  4. change_pressure     — VIIRS trend, GHSL change, Hansen loss, NDVI trend, fire
  5. location_value      — Accessibility, healthcare, nightlights, slope, roads
  6. agri_potential      — SOC, pH, clay, precipitation, GDD, slope
  7. forest_health       — NDVI trend, loss ratio, fire, GPP, ET
  8. forestry_aptitude   — pH, clay, precipitation, slope, road dist, accessibility
  9. territorial_gap     — Nightlights vs NBI, water access, sewage, isolation
 10. health_access       — Healthcare time, walk, population, coverage, NBI
 11. education_gap       — No instruction, dropout, primary only, university, isolation

Usage:
  python pipeline/compute_satellite_scores.py
  python pipeline/compute_satellite_scores.py --only environmental_risk,green_capital
  python pipeline/compute_satellite_scores.py --diagnostics --legacy
"""

import argparse
import os
import sys
import time

import duckdb
import numpy as np
import pandas as pd

from config import OUTPUT_DIR
from scoring import (
    geometric_mean_score,
    run_full_diagnostics,
    generate_report,
)

CROSSWALK_PATH = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk.parquet")
AREAL_CROSSWALK_PATH = os.path.join(OUTPUT_DIR, "h3_radio_crosswalk_areal.parquet")
RADIO_DATA_DIR = os.path.join(OUTPUT_DIR, "radio_data")

# Tables used by analysis queries — loaded from parquets
RADIO_TABLES = [
    "radios_misiones", "fire_annual", "hansen_baseline", "lst_annual",
    "fabdem_terrain", "merit_hydro", "chirps_annual", "era5_annual",
    "et_annual", "ndvi_annual_mean", "npp_annual", "lai_annual", "vcf_annual",
    "viirs_annual", "ghsl_built_surface", "gpp_annual", "soilgrids",
    "nelson_accessibility", "oxford_accessibility", "road_access",
    "censo2022_variables",
]

# ── Analysis definitions ─────────────────────────────────────────────────────
# Each analysis: id, sql (returns redcode + component columns), components
# Components: (output_col, sql_col, weight, invert)
#   invert=True means lower raw value = higher score

ANALYSIS_DEFS = [
    # ── VIVIR ─────────────────────────────────────────────────────────────
    {
        "id": "environmental_risk",
        "sql": """
            SELECT r.redcode,
                COALESCE(f.burned_fraction, 0) AS c_fire,
                COALESCE(h.total_loss, 0) AS c_deforest,
                COALESCE(l.amplitude, 0) AS c_thermal_amp,
                COALESCE(t.slope_mean, 0) AS c_slope,
                COALESCE(m.hand_mean, 100) AS c_hand
            FROM radios_misiones r
            LEFT JOIN (
                SELECT redcode, AVG(burned_fraction) AS burned_fraction
                FROM fire_annual WHERE year >= 2019 GROUP BY redcode
            ) f ON r.redcode = f.redcode
            LEFT JOIN hansen_baseline h ON r.redcode = h.redcode
            LEFT JOIN (
                SELECT redcode, AVG(amplitude) AS amplitude
                FROM lst_annual WHERE year >= 2019 GROUP BY redcode
            ) l ON r.redcode = l.redcode
            LEFT JOIN fabdem_terrain t ON r.redcode = t.redcode
            LEFT JOIN merit_hydro m ON r.redcode = m.redcode
        """,
        "components": [
            ("c_fire", "c_fire", 0.25, False),
            ("c_deforest", "c_deforest", 0.25, False),
            ("c_thermal_amp", "c_thermal_amp", 0.20, False),
            ("c_slope", "c_slope", 0.15, False),
            ("c_hand", "c_hand", 0.15, True),  # low HAND = more flood risk
        ],
    },
    {
        "id": "climate_comfort",
        "sql": """
            SELECT r.redcode,
                COALESCE(l.mean_lst_day, 25) AS c_heat_day,
                COALESCE(l.mean_lst_night, 15) AS c_heat_night,
                COALESCE(c.total_mm, 1500) AS c_precipitation,
                COALESCE(e.frost_days, 0) AS c_frost,
                COALESCE(et.et_pet_ratio, 0.7) AS c_water_stress
            FROM radios_misiones r
            LEFT JOIN (
                SELECT redcode, AVG(mean_lst_day) AS mean_lst_day,
                       AVG(mean_lst_night) AS mean_lst_night
                FROM lst_annual WHERE year >= 2019 GROUP BY redcode
            ) l ON r.redcode = l.redcode
            LEFT JOIN (
                SELECT redcode, AVG(total_mm) AS total_mm
                FROM chirps_annual WHERE year >= 2019 GROUP BY redcode
            ) c ON r.redcode = c.redcode
            LEFT JOIN (
                SELECT redcode, AVG(frost_days) AS frost_days
                FROM era5_annual WHERE year >= 2019 GROUP BY redcode
            ) e ON r.redcode = e.redcode
            LEFT JOIN (
                SELECT redcode, AVG(et_pet_ratio) AS et_pet_ratio
                FROM et_annual WHERE year >= 2019 GROUP BY redcode
            ) et ON r.redcode = et.redcode
        """,
        "components": [
            ("c_heat_day", "c_heat_day", 0.25, True),      # less heat = more comfort
            ("c_heat_night", "c_heat_night", 0.20, True),   # less heat = more comfort
            ("c_precipitation", "c_precipitation", 0.20, False),  # more rain = better (subtropical)
            ("c_frost", "c_frost", 0.15, True),             # less frost = more comfort
            ("c_water_stress", "c_water_stress", 0.20, False),   # higher ET/PET = less stress
        ],
    },
    {
        "id": "green_capital",
        "sql": """
            SELECT r.redcode,
                COALESCE(n.mean_ndvi, 0) AS c_ndvi,
                COALESCE(h.treecover2000, 0) AS c_treecover,
                COALESCE(np.mean_npp, 0) AS c_npp,
                COALESCE(la.mean_lai, 0) AS c_lai,
                COALESCE(v.tree_cover, 0) AS c_vcf
            FROM radios_misiones r
            LEFT JOIN (
                SELECT redcode, AVG(mean_ndvi) AS mean_ndvi
                FROM ndvi_annual_mean WHERE year >= 2019 GROUP BY redcode
            ) n ON r.redcode = n.redcode
            LEFT JOIN hansen_baseline h ON r.redcode = h.redcode
            LEFT JOIN (
                SELECT redcode, AVG(mean_npp) AS mean_npp
                FROM npp_annual WHERE year >= 2019 GROUP BY redcode
            ) np ON r.redcode = np.redcode
            LEFT JOIN (
                SELECT redcode, AVG(mean_lai) AS mean_lai
                FROM lai_annual WHERE year >= 2019 GROUP BY redcode
            ) la ON r.redcode = la.redcode
            LEFT JOIN (
                SELECT redcode, AVG(tree_cover) AS tree_cover
                FROM vcf_annual WHERE year >= 2019 GROUP BY redcode
            ) v ON r.redcode = v.redcode
        """,
        "components": [
            ("c_ndvi", "c_ndvi", 0.25, False),
            ("c_treecover", "c_treecover", 0.20, False),
            ("c_npp", "c_npp", 0.20, False),
            ("c_lai", "c_lai", 0.15, False),
            ("c_vcf", "c_vcf", 0.20, False),
        ],
    },
    # ── INVERTIR ──────────────────────────────────────────────────────────
    {
        "id": "change_pressure",
        "sql": """
            SELECT r.redcode,
                COALESCE(vt.viirs_slope, 0) AS c_viirs_trend,
                COALESCE(g2.built_fraction - g1.built_fraction, 0) AS c_ghsl_change,
                COALESCE(h.total_loss, 0) AS c_hansen_loss,
                COALESCE(nt.ndvi_slope, 0) AS c_ndvi_trend,
                COALESCE(f.burn_sum, 0) AS c_fire_count
            FROM radios_misiones r
            LEFT JOIN (
                SELECT redcode, regr_slope(mean_radiance, year) AS viirs_slope
                FROM viirs_annual WHERE year >= 2016 GROUP BY redcode
            ) vt ON r.redcode = vt.redcode
            LEFT JOIN (
                SELECT redcode, built_fraction FROM ghsl_built_surface WHERE epoch = 2020
            ) g2 ON r.redcode = g2.redcode
            LEFT JOIN (
                SELECT redcode, built_fraction FROM ghsl_built_surface WHERE epoch = 2000
            ) g1 ON r.redcode = g1.redcode
            LEFT JOIN hansen_baseline h ON r.redcode = h.redcode
            LEFT JOIN (
                SELECT redcode, regr_slope(mean_ndvi, year) AS ndvi_slope
                FROM ndvi_annual_mean WHERE year >= 2019 GROUP BY redcode
            ) nt ON r.redcode = nt.redcode
            LEFT JOIN (
                SELECT redcode, SUM(burn_count) AS burn_sum
                FROM fire_annual WHERE year >= 2019 GROUP BY redcode
            ) f ON r.redcode = f.redcode
        """,
        "components": [
            ("c_viirs_trend", "c_viirs_trend", 0.25, False),  # rising lights = change
            ("c_ghsl_change", "c_ghsl_change", 0.25, False),  # built-up growth
            ("c_hansen_loss", "c_hansen_loss", 0.20, False),   # forest loss
            ("c_ndvi_trend", "c_ndvi_trend", 0.15, True),     # declining NDVI = transformation
            ("c_fire_count", "c_fire_count", 0.15, False),    # fire activity
        ],
    },
    {
        "id": "location_value",
        "sql": """
            SELECT r.redcode,
                COALESCE(n.tt_cities_20k_min, 300) AS c_access_20k,
                COALESCE(o.accessibility_healthcare_min, 300) AS c_healthcare,
                COALESCE(v.mean_radiance, 0) AS c_nightlights,
                COALESCE(t.slope_mean, 0) AS c_slope,
                COALESCE(rd.dist_primary_m, 50000) AS c_road_dist
            FROM radios_misiones r
            LEFT JOIN nelson_accessibility n ON r.redcode = n.redcode
            LEFT JOIN oxford_accessibility o ON r.redcode = o.redcode
            LEFT JOIN (
                SELECT redcode, AVG(mean_radiance) AS mean_radiance
                FROM viirs_annual WHERE year >= 2022 GROUP BY redcode
            ) v ON r.redcode = v.redcode
            LEFT JOIN fabdem_terrain t ON r.redcode = t.redcode
            LEFT JOIN road_access rd ON r.redcode = rd.redcode
        """,
        "components": [
            ("c_access_20k", "c_access_20k", 0.25, True),    # less time = better
            ("c_healthcare", "c_healthcare", 0.20, True),     # less time = better
            ("c_nightlights", "c_nightlights", 0.25, False),  # more light = more value
            ("c_slope", "c_slope", 0.15, True),               # flatter = better
            ("c_road_dist", "c_road_dist", 0.15, True),       # closer = better
        ],
    },
    # ── PRODUCIR ──────────────────────────────────────────────────────────
    {
        "id": "agri_potential",
        "sql": """
            SELECT r.redcode,
                COALESCE(s.soc, 0) AS c_soc,
                1.0 - LEAST(1.0, ABS(COALESCE(s.ph, 50) / 10.0 - 6.25) / 4.0) AS c_ph_optimal,
                COALESCE(s.clay, 0) AS c_clay,
                COALESCE(c.total_mm, 0) AS c_precipitation,
                COALESCE(e.gdd_base10, 0) AS c_gdd,
                COALESCE(t.slope_mean, 0) AS c_slope
            FROM radios_misiones r
            LEFT JOIN soilgrids s ON r.redcode = s.redcode
            LEFT JOIN (
                SELECT redcode, AVG(total_mm) AS total_mm
                FROM chirps_annual WHERE year >= 2019 GROUP BY redcode
            ) c ON r.redcode = c.redcode
            LEFT JOIN (
                SELECT redcode, AVG(gdd_base10) AS gdd_base10
                FROM era5_annual WHERE year >= 2019 GROUP BY redcode
            ) e ON r.redcode = e.redcode
            LEFT JOIN fabdem_terrain t ON r.redcode = t.redcode
        """,
        "components": [
            ("c_soc", "c_soc", 0.20, False),            # more organic carbon = better
            ("c_ph_optimal", "c_ph_optimal", 0.15, False),  # already 0-1 distance to optimal
            ("c_clay", "c_clay", 0.15, False),           # more clay = better water retention
            ("c_precipitation", "c_precipitation", 0.20, False),
            ("c_gdd", "c_gdd", 0.15, False),            # more heat units = more growth
            ("c_slope", "c_slope", 0.15, True),          # flatter = easier mechanization
        ],
    },
    {
        "id": "forest_health",
        "sql": """
            SELECT r.redcode,
                COALESCE(nt.ndvi_slope, 0) AS c_ndvi_trend,
                CASE WHEN COALESCE(h.treecover2000, 0) > 0
                     THEN COALESCE(h.total_loss, 0) / h.treecover2000
                     ELSE 0 END AS c_loss_ratio,
                COALESCE(f.burned_fraction, 0) AS c_fire,
                COALESCE(g.mean_gpp, 0) AS c_gpp,
                COALESCE(et.mean_et, 0) AS c_et
            FROM radios_misiones r
            LEFT JOIN (
                SELECT redcode, regr_slope(mean_ndvi, year) AS ndvi_slope
                FROM ndvi_annual_mean WHERE year >= 2019 GROUP BY redcode
            ) nt ON r.redcode = nt.redcode
            LEFT JOIN hansen_baseline h ON r.redcode = h.redcode
            LEFT JOIN (
                SELECT redcode, AVG(burned_fraction) AS burned_fraction
                FROM fire_annual WHERE year >= 2019 GROUP BY redcode
            ) f ON r.redcode = f.redcode
            LEFT JOIN (
                SELECT redcode, AVG(mean_gpp) AS mean_gpp
                FROM gpp_annual WHERE year >= 2019 GROUP BY redcode
            ) g ON r.redcode = g.redcode
            LEFT JOIN (
                SELECT redcode, AVG(mean_et) AS mean_et
                FROM et_annual WHERE year >= 2019 GROUP BY redcode
            ) et ON r.redcode = et.redcode
        """,
        "components": [
            ("c_ndvi_trend", "c_ndvi_trend", 0.25, False),  # positive trend = healthier
            ("c_loss_ratio", "c_loss_ratio", 0.25, True),    # less loss = healthier
            ("c_fire", "c_fire", 0.20, True),                # less fire = healthier
            ("c_gpp", "c_gpp", 0.15, False),                 # more productivity = healthier
            ("c_et", "c_et", 0.15, False),                   # more transpiration = active forest
        ],
    },
    {
        "id": "forestry_aptitude",
        "sql": """
            SELECT r.redcode,
                COALESCE(s.ph, 50) / 10.0 AS c_ph,
                COALESCE(s.clay, 0) AS c_clay,
                COALESCE(c.total_mm, 0) AS c_precipitation,
                COALESCE(t.slope_mean, 0) AS c_slope,
                COALESCE(rd.dist_primary_m, 50000) AS c_road_dist,
                COALESCE(n.tt_cities_50k_min, 300) AS c_access_50k
            FROM radios_misiones r
            LEFT JOIN soilgrids s ON r.redcode = s.redcode
            LEFT JOIN (
                SELECT redcode, AVG(total_mm) AS total_mm
                FROM chirps_annual WHERE year >= 2019 GROUP BY redcode
            ) c ON r.redcode = c.redcode
            LEFT JOIN fabdem_terrain t ON r.redcode = t.redcode
            LEFT JOIN road_access rd ON r.redcode = rd.redcode
            LEFT JOIN nelson_accessibility n ON r.redcode = n.redcode
        """,
        "components": [
            ("c_ph", "c_ph", 0.15, True),               # pines prefer acidic (lower pH)
            ("c_clay", "c_clay", 0.10, True),            # pines prefer sandy (less clay)
            ("c_precipitation", "c_precipitation", 0.25, False),  # >1200mm needed
            ("c_slope", "c_slope", 0.20, True),          # <15° for mechanized harvest
            ("c_road_dist", "c_road_dist", 0.15, True),  # closer to road = cheaper freight
            ("c_access_50k", "c_access_50k", 0.15, True),  # closer to sawmills
        ],
    },
    # ── SERVIR ────────────────────────────────────────────────────────────
    {
        "id": "service_deprivation",
        "sql": """
            SELECT r.redcode,
                COALESCE(ce.pct_nbi, 0) AS c_nbi,
                100.0 - COALESCE(ce.pct_agua_red, 0) AS c_sin_agua,
                100.0 - COALESCE(ce.pct_cloacas, 0) AS c_sin_cloacas,
                COALESCE(ce.pct_sin_techo_adecuado, 0) AS c_techo,
                COALESCE(ce.pct_sin_piso_adecuado, 0) AS c_piso,
                COALESCE(ce.pct_combustible_precario, 0) AS c_combustible,
                COALESCE(ce.pct_hacinamiento_critico, 0) AS c_hacinamiento
            FROM radios_misiones r
            LEFT JOIN censo2022_variables ce ON r.redcode = ce.redcode
        """,
        "components": [
            ("c_nbi", "c_nbi", 0.20, False),
            ("c_sin_agua", "c_sin_agua", 0.15, False),
            ("c_sin_cloacas", "c_sin_cloacas", 0.15, False),
            ("c_techo", "c_techo", 0.15, False),
            ("c_piso", "c_piso", 0.10, False),
            ("c_combustible", "c_combustible", 0.10, False),
            ("c_hacinamiento", "c_hacinamiento", 0.15, False),
        ],
    },
    {
        "id": "territorial_isolation",
        "sql": """
            SELECT r.redcode,
                COALESCE(o.accessibility_cities_min, 300) AS c_access_cities,
                COALESCE(o.accessibility_healthcare_min, 300) AS c_access_health,
                COALESCE(rd.dist_primary_m, 50000) AS c_road_dist,
                COALESCE(rd.road_density_km_per_km2, 0) AS c_road_density,
                COALESCE(v.mean_radiance, 0) AS c_nightlights,
                COALESCE(ce.densidad_hab_km2, 0) AS c_pop_density
            FROM radios_misiones r
            LEFT JOIN oxford_accessibility o ON r.redcode = o.redcode
            LEFT JOIN road_access rd ON r.redcode = rd.redcode
            LEFT JOIN (
                SELECT redcode, AVG(mean_radiance) AS mean_radiance
                FROM viirs_annual WHERE year >= 2022 GROUP BY redcode
            ) v ON r.redcode = v.redcode
            LEFT JOIN censo2022_variables ce ON r.redcode = ce.redcode
        """,
        "components": [
            ("c_access_cities", "c_access_cities", 0.20, False),      # more time = more isolated
            ("c_access_health", "c_access_health", 0.20, False),      # more time = more isolated
            ("c_road_dist", "c_road_dist", 0.15, False),              # farther from road = more isolated
            ("c_road_density", "c_road_density", 0.15, True),         # less roads = more isolated
            ("c_nightlights", "c_nightlights", 0.15, True),           # less light = more isolated
            ("c_pop_density", "c_pop_density", 0.15, True),           # less people = more isolated
        ],
    },
    {
        "id": "health_access",
        "sql": """
            SELECT r.redcode,
                COALESCE(o.accessibility_healthcare_min, 300) AS c_healthcare_time,
                COALESCE(ce.pct_cobertura_salud, 0) AS c_health_coverage,
                COALESCE(ce.pct_nbi, 0) AS c_nbi,
                COALESCE(ce.pct_adultos_mayores, 0) AS c_elderly,
                COALESCE(ce.pct_menores_18, 0) AS c_children,
                COALESCE(ce.densidad_hab_km2, 0) AS c_pop_density
            FROM radios_misiones r
            LEFT JOIN oxford_accessibility o ON r.redcode = o.redcode
            LEFT JOIN censo2022_variables ce ON r.redcode = ce.redcode
        """,
        "components": [
            ("c_healthcare_time", "c_healthcare_time", 0.25, False),   # more time = worse access
            ("c_health_coverage", "c_health_coverage", 0.15, True),    # more coverage = less gap
            ("c_nbi", "c_nbi", 0.20, False),                           # more NBI = more vulnerability
            ("c_elderly", "c_elderly", 0.15, False),                    # more elderly = more demand
            ("c_children", "c_children", 0.10, False),                  # more children = more demand
            ("c_pop_density", "c_pop_density", 0.15, False),            # more density = more demand
        ],
    },
    {
        "id": "education_capital",
        "sql": """
            SELECT r.redcode,
                COALESCE(ce.pct_sin_instruccion, 0) AS c_no_instruction,
                COALESCE(ce.pct_solo_primaria, 0) AS c_only_primary,
                COALESCE(ce.pct_secundario_comp, 0) AS c_secondary,
                COALESCE(ce.pct_terciario, 0) AS c_tertiary,
                COALESCE(ce.pct_universitario, 0) AS c_university
            FROM radios_misiones r
            LEFT JOIN censo2022_variables ce ON r.redcode = ce.redcode
        """,
        "components": [
            ("c_no_instruction", "c_no_instruction", 0.25, False),    # more = less capital
            ("c_only_primary", "c_only_primary", 0.20, False),        # more = less capital
            ("c_secondary", "c_secondary", 0.20, True),               # more = more capital (invert)
            ("c_tertiary", "c_tertiary", 0.15, True),                 # more = more capital (invert)
            ("c_university", "c_university", 0.20, True),             # more = more capital (invert)
        ],
    },
    {
        "id": "education_flow",
        "sql": """
            SELECT r.redcode,
                COALESCE(ce.tasa_inasistencia_6a12, 0) AS c_dropout_primary,
                COALESCE(ce.tasa_inasistencia_13a18, 0) AS c_dropout_secondary,
                COALESCE(ce.tasa_maternidad_adolescente, 0) AS c_teen_pregnancy,
                COALESCE(ce.pct_jovenes_18a29, 0) AS c_youth_pct,
                COALESCE(ce.pct_jefatura_femenina, 0) AS c_female_headed
            FROM radios_misiones r
            LEFT JOIN censo2022_variables ce ON r.redcode = ce.redcode
        """,
        "components": [
            ("c_dropout_primary", "c_dropout_primary", 0.25, False),       # more = worse flow
            ("c_dropout_secondary", "c_dropout_secondary", 0.25, False),   # more = worse flow
            ("c_teen_pregnancy", "c_teen_pregnancy", 0.20, False),          # more = worse flow
            ("c_youth_pct", "c_youth_pct", 0.15, False),                   # more youth = more pressure
            ("c_female_headed", "c_female_headed", 0.15, False),           # proxy for vulnerability
        ],
    },
]


def create_duckdb_conn() -> duckdb.DuckDBPyConnection:
    """Create DuckDB connection with all radio tables loaded from parquets."""
    conn = duckdb.connect()
    loaded = 0
    for table_name in RADIO_TABLES:
        path = os.path.join(RADIO_DATA_DIR, f"{table_name}.parquet")
        if os.path.exists(path):
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet('{path}')")
            loaded += 1
        else:
            # Create empty table so queries don't fail
            conn.execute(f"CREATE TABLE {table_name} (redcode VARCHAR)")
    print(f"  Loaded {loaded}/{len(RADIO_TABLES)} radio tables from parquets")
    return conn


def fetch_radio_data(conn, sql: str) -> pd.DataFrame:
    """Execute SQL query on DuckDB and return DataFrame."""
    return conn.execute(sql).fetchdf()


def join_to_h3(radio_df: pd.DataFrame, crosswalk: pd.DataFrame,
               areal_crosswalk: pd.DataFrame | None = None) -> pd.DataFrame:
    """Project radio-level data onto H3 hexagons via dasymetric crosswalk.

    Building-weighted average where buildings exist (~69K hex).
    If areal_crosswalk is provided, adds areal fallback for remaining hex
    (used for satellite analyses measuring environmental conditions).
    Census-based analyses should NOT pass areal_crosswalk — data only where people live.
    """
    value_cols = [c for c in radio_df.columns if c != "redcode"]

    def weighted_avg(g):
        w = g["weight"].values
        w_sum = w.sum()
        if w_sum == 0:
            return pd.Series({c: np.nan for c in value_cols})
        return pd.Series({c: np.average(g[c].values, weights=w) for c in value_cols})

    # Step 1: Dasymetric weighted average
    merged_dasy = crosswalk.merge(radio_df, on="redcode", how="inner")
    hex_dasy = merged_dasy.groupby("h3index", group_keys=False).apply(
        weighted_avg, include_groups=False
    ).reset_index()

    # Step 2: Areal fallback for hex without buildings
    if areal_crosswalk is not None:
        dasy_hex_set = set(hex_dasy["h3index"])
        areal_missing = areal_crosswalk[~areal_crosswalk["h3index"].isin(dasy_hex_set)]
        if len(areal_missing) > 0:
            merged_areal = areal_missing.merge(radio_df, on="redcode", how="inner")
            # Max-overlap assignment for areal (same as original approach)
            idx = merged_areal.groupby("h3index")["weight"].idxmax()
            hex_areal = merged_areal.loc[idx].drop(
                columns=["redcode", "weight"]
            ).reset_index(drop=True)
            hex_combined = pd.concat([hex_dasy, hex_areal], ignore_index=True)
            print(f"    Hybrid: {len(hex_dasy):,} dasymetric + {len(hex_areal):,} areal = {len(hex_combined):,}")
            return hex_combined

    return hex_dasy


def normalize_percentile(series: pd.Series) -> pd.Series:
    """Compute percentile rank 0-100 for a series."""
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index)
    if valid.sum() > 1:
        result[valid] = series[valid].rank(pct=True) * 100.0
    return result


def compute_analysis(
    conn,
    crosswalk: pd.DataFrame,
    analysis_def: dict,
    areal_crosswalk: pd.DataFrame | None = None,
    emit_diagnostics: bool = False,
    emit_legacy: bool = False,
    output_dir: str = OUTPUT_DIR,
) -> pd.DataFrame:
    """Compute a single composite analysis using PCA-validated geometric mean."""
    analysis_id = analysis_def["id"]
    components = analysis_def["components"]

    # Fetch radio-level data
    radio_data = fetch_radio_data(conn, analysis_def["sql"])
    print(f"    Radio data: {len(radio_data)} rows, "
          f"cols: {[c for c in radio_data.columns if c != 'redcode']}")

    # Project to H3 (hybrid: dasymetric + areal fallback)
    hex_data = join_to_h3(radio_data, crosswalk, areal_crosswalk)
    print(f"    H3 hexagons: {len(hex_data):,}")

    # Normalize each component via percentile rank
    for out_col, sql_col, _weight, invert in components:
        raw = hex_data[sql_col].astype(float)
        if invert:
            raw = -raw
        hex_data[out_col] = normalize_percentile(raw)

    comp_cols = [c[0] for c in components]

    # ── PCA diagnostics + variable selection ─────────────────────────────
    diagnostics = run_full_diagnostics(hex_data, comp_cols, corr_threshold=0.70)
    retained = diagnostics["variable_selection"]["retained"]
    dropped = diagnostics["variable_selection"]["dropped"]

    kmo = diagnostics["kmo_bartlett"].get("kmo_overall")
    if kmo is not None:
        print(f"    KMO: {kmo:.3f} {'OK' if kmo >= 0.60 else 'WARNING < 0.60'}")
    if dropped:
        print(f"    Dropped (|r|>0.70): {dropped}")
    print(f"    Retained ({len(retained)}): {retained}")

    # ── Geometric mean score (HDI-style, floor=1.0) ─────────────────────
    hex_data["score"] = geometric_mean_score(hex_data, retained, floor=1.0).round(1)

    # ── Legacy weighted arithmetic mean (for validation) ─────────────────
    if emit_legacy:
        legacy = pd.Series(0.0, index=hex_data.index)
        total_weight = 0.0
        for out_col, _, weight, _ in components:
            valid = hex_data[out_col].notna()
            legacy[valid] += hex_data.loc[valid, out_col] * weight
            total_weight += weight
        hex_data["score_legacy"] = (legacy / total_weight).round(1)

    # ── Diagnostics report ───────────────────────────────────────────────
    if emit_diagnostics:
        generate_report(analysis_id, diagnostics, output_dir=output_dir)

    # Round component columns
    for out_col, _, _, _ in components:
        hex_data[out_col] = hex_data[out_col].round(1)

    # Select output columns
    out_cols = ["h3index", "score"] + comp_cols
    if emit_legacy:
        out_cols.append("score_legacy")
    result = hex_data[out_cols].copy()

    # Stats
    non_null = result["score"].notna().sum()
    avg = result["score"].mean()
    median = result["score"].median()
    print(f"    Score (geometric mean): n={non_null:,}, avg={avg:.1f}, median={median:.1f}")
    if emit_legacy:
        avg_leg = result["score_legacy"].mean()
        print(f"    Score (legacy arith.):  avg={avg_leg:.1f}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Compute satellite composite scores at H3 res-9 (PCA + geometric mean)"
    )
    parser.add_argument(
        "--only", default=None,
        help="Comma-separated list of analysis IDs to compute (default: all)"
    )
    parser.add_argument(
        "--output-dir", default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})"
    )
    parser.add_argument(
        "--diagnostics", action="store_true",
        help="Emit PCA/KMO/correlation diagnostic JSON per analysis"
    )
    parser.add_argument(
        "--legacy", action="store_true",
        help="Include score_legacy column (old weighted arithmetic mean) for validation"
    )
    args = parser.parse_args()

    # Filter analyses if --only specified
    analyses = ANALYSIS_DEFS
    if args.only:
        only_ids = set(args.only.split(","))
        analyses = [a for a in analyses if a["id"] in only_ids]
        if not analyses:
            print(f"ERROR: No matching analyses for --only={args.only}")
            return 1

    print("=" * 60)
    print("  Compute Satellite Composite Scores")
    print(f"  Analyses: {len(analyses)}")
    print("=" * 60)

    # Load crosswalks
    print("\nLoading crosswalks...")
    crosswalk = pd.read_parquet(CROSSWALK_PATH)
    print(f"  Dasymetric: {len(crosswalk):,} rows, {crosswalk['h3index'].nunique():,} unique hexagons")
    areal_crosswalk = pd.read_parquet(AREAL_CROSSWALK_PATH)
    print(f"  Areal: {len(areal_crosswalk):,} rows, {areal_crosswalk['h3index'].nunique():,} unique hexagons")

    # Load radio data tables into DuckDB
    print("Loading radio tables into DuckDB...")
    conn = create_duckdb_conn()

    t0 = time.time()
    results = {}

    for i, analysis_def in enumerate(analyses, 1):
        aid = analysis_def["id"]
        print(f"\n[{i}/{len(analyses)}] Computing {aid}...")

        try:
            # Census-based analyses: dasymetric only (data where people live)
            # Satellite/spatial analyses: hybrid dasymetric + areal fallback
            CENSUS_ANALYSES = {'service_deprivation', 'health_access', 'education_capital', 'education_flow'}
            use_areal = None if aid in CENSUS_ANALYSES else areal_crosswalk
            result = compute_analysis(
                conn, crosswalk, analysis_def,
                areal_crosswalk=use_areal,
                emit_diagnostics=args.diagnostics,
                emit_legacy=args.legacy,
                output_dir=args.output_dir,
            )
            out_path = os.path.join(args.output_dir, f"sat_{aid}.parquet")
            result.to_parquet(out_path, index=False)
            size_kb = os.path.getsize(out_path) / 1024
            print(f"    Output: {out_path} ({size_kb:.0f} KB)")
            results[aid] = len(result)
        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback
            traceback.print_exc()
            results[aid] = 0

    conn.close()
    elapsed = time.time() - t0

    print(f"\n{'=' * 60}")
    print(f"  Completed in {elapsed:.0f}s")
    for aid, count in results.items():
        status = f"{count:,} hexes" if count > 0 else "FAILED"
        print(f"    {aid}: {status}")
    print(f"{'=' * 60}")

    failed = sum(1 for c in results.values() if c == 0)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
