"""
Compute 8 composite territorial indicators from Overture H3-indexed parquets.

Reads the 4 Overture parquets (buildings, transportation, places, base),
computes 8 continuous scores (0-100) per H3 hex using DuckDB with the H3
extension for k-ring neighborhood queries.

Indicators:
  1. paving_index         — Paved road ratio in k-ring(2) neighbourhood (~3km)
  2. urban_consolidation  — Composite: density + residential + paving + hierarchy
  3. service_access       — Essential services within k-ring(3) neighbourhood (~5km)
  4. commercial_vitality  — Shannon entropy of POI categories in k-ring(2) + density
  5. road_connectivity    — Road hierarchy + density + bridges
  6. building_mix         — Typological diversity of buildings (Shannon entropy)
  7. urbanization         — Degree of urban development (buildings + land use)
  8. water_exposure       — River/stream density in k-ring(2) neighbourhood (~3km)

Usage:
  python pipeline/compute_overture_scores.py
  python pipeline/compute_overture_scores.py --output path/to/output.parquet
"""

import argparse
import os
import sys
import time

import duckdb
import pandas as pd

from config import OUTPUT_DIR, get_territory
from scoring import geometric_mean_score, run_full_diagnostics, load_goalposts, score_with_goalposts

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TYPE_LABELS = {
    1: 'Urbano consolidado',
    2: 'Urbano',
    3: 'Periurbano',
    4: 'Rural conectado',
    5: 'Rural disperso',
}


def compute_scores(conn: duckdb.DuckDBPyConnection, output_path: str,
                   buildings_path: str, transportation_path: str,
                   places_path: str, base_path: str,
                   mode: str = 'local', goalposts: dict | None = None) -> int:
    """Compute all 8 indicators + composite score/type/type_label and write parquet."""

    t0 = time.time()

    # ── Load source tables ───────────────────────────────────────────────
    print("Loading source parquets...")
    conn.execute(f"""
        CREATE TABLE buildings AS
        SELECT h3index, building_count, n_residential, n_commercial,
               n_education, n_medical, n_religious, n_agricultural,
               avg_height_m, avg_floors
        FROM read_parquet('{buildings_path}')
    """)
    b_count = conn.execute("SELECT count(*) FROM buildings").fetchone()[0]
    print(f"  buildings: {b_count:,} hexes")

    conn.execute(f"""
        CREATE TABLE transportation AS
        SELECT h3index, segment_count, n_road, n_paved, n_unpaved,
               n_track, n_primary, n_secondary, n_tertiary,
               n_residential, n_bridge, n_pedestrian, n_footway,
               n_cycleway, n_living_street
        FROM read_parquet('{transportation_path}')
    """)
    t_count = conn.execute("SELECT count(*) FROM transportation").fetchone()[0]
    print(f"  transportation: {t_count:,} hexes")

    conn.execute(f"""
        CREATE TABLE places AS
        SELECT h3index, place_count,
               n_food_and_drink, n_shopping, n_services_and_business,
               n_health_care, n_education, n_community_and_government,
               n_sports_and_recreation, n_arts_and_entertainment,
               n_lodging, n_travel_and_transportation,
               n_hospital, n_school, n_pharmacy, n_gas_station,
               n_restaurant, n_grocery_store
        FROM read_parquet('{places_path}')
    """)
    p_count = conn.execute("SELECT count(*) FROM places").fetchone()[0]
    print(f"  places: {p_count:,} hexes")

    conn.execute(f"""
        CREATE TABLE base AS
        SELECT h3index, infra_count, n_power, n_water_infra, n_communication,
               n_emergency, landuse_count,
               n_lu_agriculture, n_lu_residential, n_lu_developed,
               n_lu_managed, n_lu_park, n_lu_protected, n_lu_recreation,
               water_count, n_river, n_stream, n_canal, n_lake
        FROM read_parquet('{base_path}')
    """)
    base_count = conn.execute("SELECT count(*) FROM base").fetchone()[0]
    print(f"  base: {base_count:,} hexes")

    # ── Compute normalization caps ─────────────────────────────────────
    gp_indicators = goalposts.get('indicators', {}) if goalposts else {}

    if mode == 'comparable':
        gp_bd = gp_indicators.get('c_building_density', {})
        gp_sd = gp_indicators.get('c_segment_density', {})
        p95_building = gp_bd.get('hi', 100)
        p95_segment = gp_sd.get('hi', 15)
        print(f"\n  [comparable] building_density cap: {p95_building}  (goalpost hi)")
        print(f"  [comparable] segment_density cap: {p95_segment}  (goalpost hi)")
    else:
        print("\nComputing percentiles for normalization...")
        p95_building = conn.execute(
            "SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY building_count) FROM buildings WHERE building_count > 0"
        ).fetchone()[0] or 1
        print(f"  P95 building_count: {p95_building}")
        p95_segment = conn.execute(
            "SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY segment_count) FROM transportation WHERE segment_count > 0"
        ).fetchone()[0] or 1
        print(f"  P95 segment_count: {p95_segment}")

    # ── Build master hex list + bigint versions ──────────────────────────
    print("\nBuilding master hex list...")
    conn.execute("""
        CREATE TABLE all_hexes AS
        SELECT DISTINCT h3index FROM (
            SELECT h3index FROM buildings
            UNION
            SELECT h3index FROM transportation
            UNION
            SELECT h3index FROM places
            UNION
            SELECT h3index FROM base
        )
    """)
    total = conn.execute("SELECT count(*) FROM all_hexes").fetchone()[0]
    print(f"  Total unique hexes: {total:,}")

    conn.execute("""
        CREATE TABLE all_hexes_big AS
        SELECT h3index, h3_string_to_h3(h3index) AS h3big
        FROM all_hexes
    """)

    # Pre-build bigint lookup tables for k-ring joins
    conn.execute("""
        CREATE TABLE transport_big AS
        SELECT h3_string_to_h3(h3index) AS h3big, h3index,
               n_paved, n_unpaved, n_track
        FROM transportation
    """)
    conn.execute("""
        CREATE TABLE places_big AS
        SELECT h3_string_to_h3(h3index) AS h3big, h3index,
               place_count, n_health_care, n_education, n_pharmacy, n_gas_station,
               n_food_and_drink, n_shopping, n_services_and_business,
               n_community_and_government, n_sports_and_recreation,
               n_arts_and_entertainment, n_lodging, n_travel_and_transportation
        FROM places
    """)
    conn.execute("""
        CREATE TABLE base_big AS
        SELECT h3_string_to_h3(h3index) AS h3big, h3index,
               COALESCE(n_river, 0) + COALESCE(n_stream, 0) + COALESCE(n_canal, 0) AS water_features
        FROM base
    """)

    # ── Score 1: Paving Index (k-ring=2, ~3km) ──────────────────────────
    print("\n[1/8] Computing paving_index (k-ring=2)...")
    conn.execute("""
        CREATE TABLE score_paving AS
        WITH kring AS (
            SELECT ah.h3index AS center_h3,
                   UNNEST(h3_grid_disk(ah.h3big, 2)) AS neighbor_big
            FROM all_hexes_big ah
        ),
        pav_agg AS (
            SELECT k.center_h3,
                   SUM(COALESCE(t.n_paved, 0)) AS sum_paved,
                   SUM(COALESCE(t.n_paved, 0) + COALESCE(t.n_unpaved, 0) + COALESCE(t.n_track, 0)) AS sum_total
            FROM kring k
            LEFT JOIN transport_big t ON k.neighbor_big = t.h3big
            GROUP BY k.center_h3
        )
        SELECT center_h3 AS h3index,
               CASE WHEN sum_total = 0 THEN 0
                    ELSE LEAST(100.0, sum_paved::FLOAT / sum_total * 100.0)
               END AS paving_index,
               COALESCE(sum_paved, 0) AS n_paved,
               COALESCE(sum_total, 0) - COALESCE(sum_paved, 0) AS n_unpaved
        FROM pav_agg
    """)
    stats = conn.execute("SELECT count(*) FILTER (WHERE paving_index > 0), ROUND(AVG(paving_index) FILTER (WHERE paving_index > 0), 1) FROM score_paving").fetchone()
    print(f"  non-zero: {stats[0]:,}, avg: {stats[1]}")

    # ── Score 2: Urban Consolidation — raw sub-components for post-processing ──
    print("[2/8] Computing urban_consolidation sub-components...")
    conn.execute(f"""
        CREATE TABLE score_urban AS
        SELECT
            h.h3index,
            -- Raw sub-components (post-processed to geometric mean in Python)
            LEAST(1.0, COALESCE(b.building_count, 0)::FLOAT / {p95_building}) AS uc_density,
            CASE WHEN COALESCE(b.building_count, 0) = 0 THEN 0
                 ELSE LEAST(1.0, COALESCE(b.n_residential, 0)::FLOAT / b.building_count)
            END AS uc_residential,
            COALESCE(sp.paving_index, 0) / 100.0 AS uc_paving,
            CASE WHEN COALESCE(t.n_primary, 0) + COALESCE(t.n_secondary, 0) + COALESCE(t.n_tertiary, 0) > 0
                 THEN 1.0 ELSE 0.0
            END AS uc_hierarchy,
            0.0 AS urban_consolidation,  -- placeholder, computed in Python post-processing
            COALESCE(b.building_count, 0) AS building_count
        FROM all_hexes h
        LEFT JOIN buildings b ON h.h3index = b.h3index
        LEFT JOIN transportation t ON h.h3index = t.h3index
        LEFT JOIN score_paving sp ON h.h3index = sp.h3index
    """)
    stats = conn.execute("SELECT count(*) FILTER (WHERE urban_consolidation > 0), ROUND(AVG(urban_consolidation) FILTER (WHERE urban_consolidation > 0), 1) FROM score_urban").fetchone()
    print(f"  non-zero: {stats[0]:,}, avg: {stats[1]}")

    # ── Score 3: Service Access (k-ring=3, ~5km) ────────────────────────
    print("[3/8] Computing service_access (k-ring=3)...")
    conn.execute("""
        CREATE TABLE score_services AS
        WITH kring AS (
            SELECT ah.h3index AS center_h3,
                   UNNEST(h3_grid_disk(ah.h3big, 3)) AS neighbor_big
            FROM all_hexes_big ah
        ),
        service_presence AS (
            SELECT k.center_h3,
                MAX(CASE WHEN COALESCE(p.n_health_care, 0) > 0 THEN 1 ELSE 0 END) AS has_health,
                MAX(CASE WHEN COALESCE(p.n_education, 0) > 0 THEN 1 ELSE 0 END) AS has_education,
                MAX(CASE WHEN COALESCE(p.n_pharmacy, 0) > 0 THEN 1 ELSE 0 END) AS has_pharmacy,
                MAX(CASE WHEN COALESCE(p.n_gas_station, 0) > 0 THEN 1 ELSE 0 END) AS has_fuel
            FROM kring k
            LEFT JOIN places_big p ON k.neighbor_big = p.h3big
            GROUP BY k.center_h3
        )
        SELECT center_h3 AS h3index,
            (COALESCE(has_health, 0) + COALESCE(has_education, 0)
             + COALESCE(has_pharmacy, 0) + COALESCE(has_fuel, 0))::FLOAT / 4.0 * 100.0
            AS service_access
        FROM service_presence
    """)
    stats = conn.execute("SELECT count(*) FILTER (WHERE service_access > 0), ROUND(AVG(service_access) FILTER (WHERE service_access > 0), 1) FROM score_services").fetchone()
    print(f"  non-zero: {stats[0]:,}, avg: {stats[1]}")

    # ── Score 4: Commercial Vitality (k-ring=2) ─────────────────────────
    print("[4/8] Computing commercial_vitality (k-ring=2)...")
    conn.execute("""
        CREATE TABLE score_commercial AS
        WITH kring AS (
            SELECT ah.h3index AS center_h3,
                   UNNEST(h3_grid_disk(ah.h3big, 2)) AS neighbor_big
            FROM all_hexes_big ah
        ),
        poi_agg AS (
            SELECT k.center_h3,
                SUM(COALESCE(p.place_count, 0)) AS total_places,
                SUM(COALESCE(p.n_food_and_drink, 0)) AS fd,
                SUM(COALESCE(p.n_shopping, 0)) AS sh,
                SUM(COALESCE(p.n_services_and_business, 0)) AS sb,
                SUM(COALESCE(p.n_health_care, 0)) AS hc,
                SUM(COALESCE(p.n_education, 0)) AS ed,
                SUM(COALESCE(p.n_community_and_government, 0)) AS cg,
                SUM(COALESCE(p.n_sports_and_recreation, 0)) AS sr,
                SUM(COALESCE(p.n_arts_and_entertainment, 0)) AS ae,
                SUM(COALESCE(p.n_lodging, 0)) AS lo,
                SUM(COALESCE(p.n_travel_and_transportation, 0)) AS tt
            FROM kring k
            LEFT JOIN places_big p ON k.neighbor_big = p.h3big
            GROUP BY k.center_h3
        )
        SELECT center_h3 AS h3index,
            CASE WHEN total_places = 0 THEN 0
            ELSE LEAST(100.0, GREATEST(0.0,
                0.60 * (
                    CASE WHEN fd > 0 THEN -(fd::FLOAT/total_places)*LN(fd::FLOAT/total_places) ELSE 0 END
                    + CASE WHEN sh > 0 THEN -(sh::FLOAT/total_places)*LN(sh::FLOAT/total_places) ELSE 0 END
                    + CASE WHEN sb > 0 THEN -(sb::FLOAT/total_places)*LN(sb::FLOAT/total_places) ELSE 0 END
                    + CASE WHEN hc > 0 THEN -(hc::FLOAT/total_places)*LN(hc::FLOAT/total_places) ELSE 0 END
                    + CASE WHEN ed > 0 THEN -(ed::FLOAT/total_places)*LN(ed::FLOAT/total_places) ELSE 0 END
                    + CASE WHEN cg > 0 THEN -(cg::FLOAT/total_places)*LN(cg::FLOAT/total_places) ELSE 0 END
                    + CASE WHEN sr > 0 THEN -(sr::FLOAT/total_places)*LN(sr::FLOAT/total_places) ELSE 0 END
                    + CASE WHEN ae > 0 THEN -(ae::FLOAT/total_places)*LN(ae::FLOAT/total_places) ELSE 0 END
                    + CASE WHEN lo > 0 THEN -(lo::FLOAT/total_places)*LN(lo::FLOAT/total_places) ELSE 0 END
                    + CASE WHEN tt > 0 THEN -(tt::FLOAT/total_places)*LN(tt::FLOAT/total_places) ELSE 0 END
                ) / LN(10) * 100.0
                + 0.40 * LEAST(1.0, total_places::FLOAT / 50.0) * 100.0
            ))
            END AS commercial_vitality,
            COALESCE(total_places, 0) AS place_count
        FROM poi_agg
    """)
    stats = conn.execute("SELECT count(*) FILTER (WHERE commercial_vitality > 0), ROUND(AVG(commercial_vitality) FILTER (WHERE commercial_vitality > 0), 1) FROM score_commercial").fetchone()
    print(f"  non-zero: {stats[0]:,}, avg: {stats[1]}")

    # ── Score 5: Road Connectivity — raw sub-components for post-processing ──
    print("[5/8] Computing road_connectivity sub-components...")
    conn.execute(f"""
        CREATE TABLE score_connectivity AS
        SELECT h.h3index,
            CASE
                WHEN COALESCE(t.n_primary, 0) > 0 THEN 1.0
                WHEN COALESCE(t.n_secondary, 0) > 0 THEN 0.7
                WHEN COALESCE(t.n_tertiary, 0) > 0 THEN 0.4
                WHEN COALESCE(t.n_residential, 0) > 0 THEN 0.15
                ELSE 0.0
            END AS rc_hierarchy,
            LEAST(1.0, COALESCE(t.segment_count, 0)::FLOAT / {p95_segment}) AS rc_density,
            LEAST(1.0, COALESCE(t.n_bridge, 0)::FLOAT / 3.0) AS rc_bridges,
            CASE WHEN COALESCE(t.segment_count, 0) = 0 THEN 0
                 ELSE LEAST(1.0, COALESCE(t.n_road, 0)::FLOAT / (t.segment_count * 0.5))
            END AS rc_road_ratio,
            0.0 AS road_connectivity,  -- placeholder, computed in Python post-processing
            COALESCE(t.segment_count, 0) AS segment_count
        FROM all_hexes h
        LEFT JOIN transportation t ON h.h3index = t.h3index
    """)
    stats = conn.execute("SELECT count(*) FILTER (WHERE road_connectivity > 0), ROUND(AVG(road_connectivity) FILTER (WHERE road_connectivity > 0), 1) FROM score_connectivity").fetchone()
    print(f"  non-zero: {stats[0]:,}, avg: {stats[1]}")

    # ── Score 6: Building Mix (NEW — replaces infra_coverage) ────────────
    print("[6/8] Computing building_mix (typological diversity)...")
    conn.execute("""
        CREATE TABLE score_building_mix AS
        SELECT h.h3index,
            CASE WHEN COALESCE(b.building_count, 0) < 2 THEN 0
            ELSE LEAST(100.0, GREATEST(0.0,
                -- Shannon entropy over 6 building types, normalized to ln(6)
                (
                    CASE WHEN COALESCE(b.n_residential, 0) > 0
                         THEN -(b.n_residential::FLOAT/b.building_count)*LN(b.n_residential::FLOAT/b.building_count)
                         ELSE 0 END
                    + CASE WHEN COALESCE(b.n_commercial, 0) > 0
                           THEN -(b.n_commercial::FLOAT/b.building_count)*LN(b.n_commercial::FLOAT/b.building_count)
                           ELSE 0 END
                    + CASE WHEN COALESCE(b.n_education, 0) > 0
                           THEN -(b.n_education::FLOAT/b.building_count)*LN(b.n_education::FLOAT/b.building_count)
                           ELSE 0 END
                    + CASE WHEN COALESCE(b.n_medical, 0) > 0
                           THEN -(b.n_medical::FLOAT/b.building_count)*LN(b.n_medical::FLOAT/b.building_count)
                           ELSE 0 END
                    + CASE WHEN COALESCE(b.n_religious, 0) > 0
                           THEN -(b.n_religious::FLOAT/b.building_count)*LN(b.n_religious::FLOAT/b.building_count)
                           ELSE 0 END
                    + CASE WHEN COALESCE(b.n_agricultural, 0) > 0
                           THEN -(b.n_agricultural::FLOAT/b.building_count)*LN(b.n_agricultural::FLOAT/b.building_count)
                           ELSE 0 END
                ) / LN(6) * 100.0
            ))
            END AS building_mix
        FROM all_hexes h
        LEFT JOIN buildings b ON h.h3index = b.h3index
    """)
    stats = conn.execute("SELECT count(*) FILTER (WHERE building_mix > 0), ROUND(AVG(building_mix) FILTER (WHERE building_mix > 0), 1) FROM score_building_mix").fetchone()
    print(f"  non-zero: {stats[0]:,}, avg: {stats[1]}")

    # ── Score 7: Urbanization — raw sub-components for post-processing ──
    print("[7/8] Computing urbanization sub-components...")
    conn.execute(f"""
        CREATE TABLE score_urbanization AS
        SELECT h.h3index,
            LEAST(1.0, COALESCE(b.building_count, 0)::FLOAT / {p95_building}) AS urb_density,
            CASE WHEN COALESCE(ba.n_lu_developed, 0) > 0 THEN 1.0 ELSE 0.0 END AS urb_developed,
            CASE WHEN COALESCE(ba.n_lu_residential, 0) > 0 THEN 1.0 ELSE 0.0 END AS urb_residential,
            0.0 AS urbanization  -- placeholder, computed in Python post-processing
        FROM all_hexes h
        LEFT JOIN buildings b ON h.h3index = b.h3index
        LEFT JOIN base ba ON h.h3index = ba.h3index
    """)
    stats = conn.execute("SELECT count(*) FILTER (WHERE urbanization > 0), ROUND(AVG(urbanization) FILTER (WHERE urbanization > 0), 1) FROM score_urbanization").fetchone()
    print(f"  non-zero: {stats[0]:,}, avg: {stats[1]}")

    # ── Score 8: Water Exposure (k-ring=2, ~3km) ────────────────────────
    print("[8/8] Computing water_exposure (k-ring=2)...")
    conn.execute("""
        CREATE TABLE score_water AS
        WITH kring AS (
            SELECT ah.h3index AS center_h3,
                   UNNEST(h3_grid_disk(ah.h3big, 2)) AS neighbor_big
            FROM all_hexes_big ah
        ),
        water_agg AS (
            SELECT k.center_h3,
                   SUM(COALESCE(bb.water_features, 0)) AS water_kring_total
            FROM kring k
            LEFT JOIN base_big bb ON k.neighbor_big = bb.h3big
            GROUP BY k.center_h3
        )
        SELECT center_h3 AS h3index, water_kring_total
        FROM water_agg
    """)
    if mode == 'comparable':
        gp_wk = gp_indicators.get('c_water_kring', {})
        p95_water = gp_wk.get('hi', 12)
        print(f"  [comparable] water_kring cap: {p95_water}  (goalpost hi)")
    else:
        p95_water = conn.execute(
            "SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY water_kring_total) FROM score_water WHERE water_kring_total > 0"
        ).fetchone()[0] or 1
        print(f"  P95 water_kring_total: {p95_water}")

    conn.execute(f"""
        CREATE TABLE score_water_final AS
        SELECT h3index,
            LEAST(100.0, GREATEST(0.0,
                COALESCE(water_kring_total, 0)::FLOAT / {p95_water} * 100.0
            )) AS water_exposure,
            COALESCE(water_kring_total, 0) AS water_kring_total
        FROM score_water
    """)
    stats = conn.execute("SELECT count(*) FILTER (WHERE water_exposure > 0), ROUND(AVG(water_exposure) FILTER (WHERE water_exposure > 0), 1) FROM score_water_final").fetchone()
    print(f"  non-zero: {stats[0]:,}, avg: {stats[1]}")

    # ── Join all scores into intermediate output ───────────────────────
    print("\nJoining all scores (intermediate)...")
    tmp_path = output_path.replace(".parquet", "_tmp.parquet")
    conn.execute(f"""
        COPY (
            SELECT
                h.h3index,
                -- 8 scores (urban_consolidation, road_connectivity, urbanization are placeholders)
                ROUND(COALESCE(sp.paving_index, 0), 1)          AS paving_index,
                0.0                                              AS urban_consolidation,
                ROUND(COALESCE(ss.service_access, 0), 1)        AS service_access,
                ROUND(COALESCE(sc.commercial_vitality, 0), 1)   AS commercial_vitality,
                0.0                                              AS road_connectivity,
                ROUND(COALESCE(sbm.building_mix, 0), 1)         AS building_mix,
                0.0                                              AS urbanization,
                ROUND(COALESCE(sw.water_exposure, 0), 1)        AS water_exposure,
                -- Raw sub-components for PCA + geometric mean post-processing
                COALESCE(su.uc_density, 0)         AS uc_density,
                COALESCE(su.uc_residential, 0)     AS uc_residential,
                COALESCE(su.uc_paving, 0)          AS uc_paving,
                COALESCE(su.uc_hierarchy, 0)       AS uc_hierarchy,
                COALESCE(sr.rc_hierarchy, 0)       AS rc_hierarchy,
                COALESCE(sr.rc_density, 0)         AS rc_density,
                COALESCE(sr.rc_bridges, 0)         AS rc_bridges,
                COALESCE(sr.rc_road_ratio, 0)      AS rc_road_ratio,
                COALESCE(surb.urb_density, 0)      AS urb_density,
                COALESCE(surb.urb_developed, 0)    AS urb_developed,
                COALESCE(surb.urb_residential, 0)  AS urb_residential,
                -- Component columns for transparency
                COALESCE(su.building_count, 0)     AS building_count,
                COALESCE(sp.n_paved, 0)            AS n_paved,
                COALESCE(sp.n_unpaved, 0)          AS n_unpaved,
                COALESCE(sc.place_count, 0)        AS place_count,
                COALESCE(sr.segment_count, 0)      AS segment_count,
                COALESCE(sw.water_kring_total, 0)  AS water_kring_total
            FROM all_hexes h
            LEFT JOIN score_paving sp        ON h.h3index = sp.h3index
            LEFT JOIN score_urban su         ON h.h3index = su.h3index
            LEFT JOIN score_services ss      ON h.h3index = ss.h3index
            LEFT JOIN score_commercial sc    ON h.h3index = sc.h3index
            LEFT JOIN score_connectivity sr  ON h.h3index = sr.h3index
            LEFT JOIN score_building_mix sbm ON h.h3index = sbm.h3index
            LEFT JOIN score_urbanization surb ON h.h3index = surb.h3index
            LEFT JOIN score_water_final sw   ON h.h3index = sw.h3index
            ORDER BY h.h3index
        ) TO '{tmp_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    # ── Post-process: PCA-validated geometric mean for 3 composite scores ──
    print("\nPost-processing: PCA + geometric mean for composites...")
    df = pd.read_parquet(tmp_path)

    composites = {
        "urban_consolidation": ["uc_density", "uc_residential", "uc_paving", "uc_hierarchy"],
        "road_connectivity": ["rc_hierarchy", "rc_density", "rc_bridges", "rc_road_ratio"],
        "urbanization": ["urb_density", "urb_developed", "urb_residential"],
    }

    for score_col, raw_cols in composites.items():
        if mode == 'comparable':
            pct_cols = []
            for col in raw_cols:
                pct_name = f"{col}_pct"
                df[pct_name] = (df[col].astype(float).clip(0, 1) * 100.0).round(2)
                pct_cols.append(pct_name)
        else:
            pct_cols = []
            for col in raw_cols:
                pct_name = f"{col}_pct"
                valid = df[col].notna() & (df[col] > 0)
                df[pct_name] = 0.0
                if valid.sum() > 1:
                    df.loc[valid, pct_name] = df.loc[valid, col].rank(pct=True) * 100.0
                pct_cols.append(pct_name)

        diagnostics = run_full_diagnostics(df[df[pct_cols].sum(axis=1) > 0], pct_cols, corr_threshold=0.70)
        retained = diagnostics["variable_selection"]["retained"]
        dropped = diagnostics["variable_selection"]["dropped"]

        kmo = diagnostics["kmo_bartlett"].get("kmo_overall")
        if kmo is not None:
            print(f"  {score_col} KMO: {kmo:.3f}")
        if dropped:
            print(f"  {score_col} dropped: {dropped}")
        print(f"  {score_col} retained ({len(retained)}): {retained}")

        df[score_col] = geometric_mean_score(df, retained, floor=1.0).round(1)

        for pct_name in pct_cols:
            df.drop(columns=[pct_name], inplace=True)

    # Drop raw sub-component columns (not needed in final output)
    raw_cols_all = [c for c in df.columns if c.startswith(("uc_", "rc_", "urb_"))]
    df.drop(columns=raw_cols_all, inplace=True)

    # ── Composite score + k-means types ─────────────────────────────────
    print("\nComputing composite score + types...")
    all_score_cols = [
        'paving_index', 'urban_consolidation', 'service_access',
        'commercial_vitality', 'road_connectivity', 'building_mix',
        'urbanization', 'water_exposure',
    ]

    if mode == 'comparable' and goalposts:
        # Sub-scores are already 0-100 with fixed caps → use directly for geomean.
        # Resolve locked selection: goalposts stores r_-prefixed names, strip to get bare cols.
        locked = goalposts.get('pca_variable_selection', {}).get('territorial_scores')
        if locked:
            retained_direct = [c.removeprefix('r_') for c in locked if c.removeprefix('r_') in all_score_cols]
            excluded = [c for c in all_score_cols if c not in retained_direct]
            print(f"  [comparable] Locked selection ({len(retained_direct)}): {retained_direct}")
            if excluded:
                print(f"  [comparable] Excluded: {excluded}")
        else:
            retained_direct = all_score_cols
            print(f"  [comparable] No lock found, using all 8: {retained_direct}")

        df['score'] = geometric_mean_score(df, retained_direct, floor=1.0).round(1)
    else:
        pct_cols = []
        for col in all_score_cols:
            p_col = f'r_{col}'
            valid = df[col] > 0
            df[p_col] = 0.0
            if valid.sum() > 1:
                df.loc[valid, p_col] = df.loc[valid, col].rank(pct=True) * 100.0
            pct_cols.append(p_col)

        diag = run_full_diagnostics(df[df[pct_cols].sum(axis=1) > 0], pct_cols, corr_threshold=0.70)
        retained_pct = diag['variable_selection']['retained']
        dropped_pct = diag['variable_selection']['dropped']
        kmo_all = diag['kmo_bartlett'].get('kmo_overall')
        if kmo_all is not None:
            print(f"  KMO (all 8): {kmo_all:.3f}")
        if dropped_pct:
            print(f"  Dropped (corr): {dropped_pct}")
        print(f"  Retained ({len(retained_pct)}): {retained_pct}")

        df['score'] = geometric_mean_score(df, retained_pct, floor=1.0).round(1)
        df.drop(columns=pct_cols, inplace=True)

    from sklearn.cluster import KMeans
    X_km = df[all_score_cols].fillna(0).values
    km = KMeans(n_clusters=5, random_state=42, n_init=10)
    raw_labels = km.fit_predict(X_km)
    cluster_means = {c: float(df['score'].values[raw_labels == c].mean()) for c in range(5)}
    order = sorted(cluster_means, key=lambda c: -cluster_means[c])
    label_map = {c: rank + 1 for rank, c in enumerate(order)}
    df['type'] = [label_map[l] for l in raw_labels]
    df['type_label'] = df['type'].map(TYPE_LABELS)

    type_dist = df['type_label'].value_counts().to_dict()
    print(f"  score: mean={df['score'].mean():.1f}, min={df['score'].min():.1f}, max={df['score'].max():.1f}")
    for t in range(1, 6):
        lbl = TYPE_LABELS[t]
        print(f"  type {t} ({lbl}): {type_dist.get(lbl, 0):,}")

    # Write final parquet
    df.to_parquet(output_path, index=False, compression="zstd")
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    elapsed = time.time() - t0
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    row_count = conn.execute(f"SELECT count(*) FROM read_parquet('{output_path}')").fetchone()[0]

    print(f"\n{'=' * 60}")
    print(f"  Output: {output_path}")
    print(f"  Rows: {row_count:,}")
    print(f"  Size: {size_mb:.1f} MB")
    print(f"  Time: {elapsed:.1f}s")
    print(f"{'=' * 60}")

    # ── Distribution summary ─────────────────────────────────────────────
    print("\nScore distributions (non-zero hexes):")
    scores = [
        'paving_index', 'urban_consolidation', 'service_access',
        'commercial_vitality', 'road_connectivity', 'building_mix',
        'urbanization', 'water_exposure'
    ]
    for s in scores:
        st = conn.execute(f"""
            SELECT
                count(*) FILTER (WHERE {s} > 0) AS n_nonzero,
                ROUND(AVG({s}) FILTER (WHERE {s} > 0), 1) AS avg_nz,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {s}) FILTER (WHERE {s} > 0), 1) AS median_nz,
                ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {s}) FILTER (WHERE {s} > 0), 1) AS p25,
                ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {s}) FILTER (WHERE {s} > 0), 1) AS p75
            FROM read_parquet('{output_path}')
        """).fetchone()
        print(f"  {s:25s}  n={st[0]:>7,}  avg={st[1]:>5}  median={st[2]:>5}  IQR=[{st[3]}, {st[4]}]")

    return row_count


def main():
    parser = argparse.ArgumentParser(description="Compute 8 territorial scores from Overture data")
    parser.add_argument("--territory", default="misiones", help="Territory ID (default: misiones)")
    parser.add_argument("--mode", choices=["comparable", "local"], default="local",
                        help="comparable: fixed goalpost normalization; local: P95 percentile (default)")
    parser.add_argument("--output", default=None, help="Output parquet path (default: auto)")
    args = parser.parse_args()

    gp = load_goalposts() if args.mode == "comparable" else None
    if gp:
        print(f"  Mode: comparable (goalposts v{gp.get('version', '?')})")

    territory = get_territory(args.territory)
    out_prefix = territory['output_prefix'].rstrip('/')
    t_dir = os.path.join(OUTPUT_DIR, out_prefix) if out_prefix else OUTPUT_DIR

    buildings_path = os.path.join(t_dir, "overture_buildings.parquet")
    transportation_path = os.path.join(t_dir, "overture_transportation.parquet")
    places_path = os.path.join(t_dir, "overture_places.parquet")
    base_path = os.path.join(t_dir, "overture_base.parquet")
    output_path = args.output or os.path.join(t_dir, "overture_scores.parquet")

    for path, name in [(buildings_path, "buildings"), (transportation_path, "transportation"),
                       (places_path, "places"), (base_path, "base")]:
        if not os.path.exists(path):
            print(f"ERROR: Missing {name} parquet: {path}")
            print("Run `python pipeline/ingest_overture.py` first.")
            return 1

    print("=" * 60)
    print(f"  Compute Overture Territorial Scores — {args.territory}")
    print("=" * 60)

    conn = duckdb.connect()
    conn.execute("INSTALL h3 FROM community; LOAD h3;")

    row_count = compute_scores(conn, output_path, buildings_path, transportation_path,
                               places_path, base_path,
                               mode=args.mode, goalposts=gp)
    conn.close()

    return 0 if row_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
