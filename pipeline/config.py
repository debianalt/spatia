"""
Shared configuration for the Spatia satellite pipeline.

All constants used across pipeline scripts are centralised here.
Import from this module instead of defining local constants.
"""

import os
from datetime import date, timedelta

# ── Spatial ───────────────────────────────────────────────────────────────
MISIONES_BBOX = [-56.10, -28.20, -53.55, -25.44]  # [W, S, E, N] — padded to cover edge hexagons
POSADAS_BBOX  = [-56.05, -27.55, -55.65, -27.15]  # Departamento Capital, Misiones
H3_RESOLUTION = 9

# ── Multi-territory configuration ────────────────────────────────────────
# Each territory can run the full satellite pipeline independently.
# 'output_prefix' maps to R2 path prefix ('' = root = Misiones legacy paths).
TERRITORY_CONFIGS: dict[str, dict] = {
    'misiones': {
        'id': 'misiones',
        'label': 'Misiones',
        'country': 'ar',
        'bbox': [-56.10, -28.20, -53.55, -25.44],   # padded
        'admin_level': 'departamento',
        'admin_col': 'dpto',                          # column name in crosswalk
        'admin_collection': None,                     # uses AR radio crosswalk
        'admin_filter': None,
        'output_prefix': '',                          # R2: data/sat_*.parquet
        'export_scale': 100,
    },
    'itapua_py': {
        'id': 'itapua_py',
        'label': 'Itapúa',
        'country': 'py',
        'bbox': [-57.40, -27.70, -54.60, -26.10],   # padded to cover edge hexagons
        'admin_level': 'distrito',
        'admin_col': 'distrito',
        'admin_collection': 'FAO/GAUL/2015/level2',  # provisional; see explore_itapua_admin.py
        'admin_filter': ('ADM1_NAME', 'Itapua'),
        'output_prefix': 'itapua_py/',               # R2: data/itapua_py/sat_*.parquet
        'export_scale': 100,
    },
    'corrientes': {
        'id': 'corrientes',
        'label': 'Corrientes',
        'country': 'ar',
        'bbox': [-59.50, -30.00, -56.00, -27.00],
        'admin_level': 'departamento',
        'admin_col': 'dpto',
        'admin_collection': None,                    # uses local ARG_adm2.shp (same as Misiones)
        'admin_filter': ('NAME_1', 'Corrientes'),   # GADM: filter province by NAME_1
        'output_prefix': 'corrientes/',              # R2: data/corrientes/sat_*.parquet
        'export_scale': 100,
    },
    'alto_parana_py': {
        'id': 'alto_parana_py',
        'label': 'Alto Paraná',
        'country': 'py',
        # Derived from INE district dissolve (build_territory_boundary_mask.py),
        # padded 0.1deg. Raw bounds: [-55.5506, -26.2571, -54.3458, -24.4762].
        'bbox': [-55.65, -26.36, -54.25, -24.38],   # [W, S, E, N]
        'admin_level': 'distrito',
        'admin_col': 'distrito',
        # Admin source = INE 2022 census cartography (22 distritos), NOT GAUL/GADM:
        # both GAUL 2015 and GADM 4.1 only have 18 (missing Iruña, Santa Fe del
        # Paraná, Dr. Raúl Peña, Tavapy — created post-2015). Built via
        # ine_cartografia_to_geojson.py -> output/alto_parana_py_ine_distritos.geojson,
        # consumed by build_admin_crosswalk.py --source geojson.
        'admin_collection': None,
        'admin_filter': ('ADM1_NAME', 'Alto Parana'),  # ascii-folded match vs INE 'ALTO PARANÁ'
        'output_prefix': 'alto_parana_py/',          # R2: data/alto_parana_py/sat_*.parquet
        'export_scale': 100,
    },
}

def get_territory(territory_id: str) -> dict:
    """Return territory config, raising KeyError with helpful message if not found."""
    if territory_id not in TERRITORY_CONFIGS:
        raise KeyError(
            f"Unknown territory '{territory_id}'. "
            f"Available: {list(TERRITORY_CONFIGS.keys())}"
        )
    return TERRITORY_CONFIGS[territory_id]

# ── Google Cloud Storage ──────────────────────────────────────────────────
GCS_BUCKET = "spatia-satellite"

# ── Cloudflare R2 ─────────────────────────────────────────────────────────
R2_BUCKET = "neahub"

# ── Flood detection ──────────────────────────────────────────────────────
VV_THRESHOLD_DB = -15   # dB threshold for Sentinel-1 water detection
EXPORT_SCALE = 30       # metres per pixel (S1 GRD native ~10m, 30m for efficiency)
EXPORT_PREFIX = "flood"
FLOOD_GCS_PREFIX = "flood/"

# ── Temporal windows for baseline vs current ─────────────────────────────
BASELINE_START = '2019-01-01'
BASELINE_END   = '2021-12-31'   # 3 stable years, pre-recent-change
_today = date.today()
CURRENT_END    = _today.isoformat()
CURRENT_START  = (_today - timedelta(days=180)).replace(day=1).isoformat()  # ~6 months back, 1st of month

# ── Validation thresholds ────────────────────────────────────────────────
MIN_HEXAGONS = 50_000       # Misiones has ~280K; <50K indicates corrupt data
MAX_NULL_FRACTION = 0.20    # max 20% nulls acceptable
SCORE_RANGE = (0, 100)

# ── Catastro ─────────────────────────────────────────────────────────────
MIN_RADIOS_CATASTRO = 1_800

# ── Paths ────────────────────────────────────────────────────────────────
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PIPELINE_DIR, "output")
GRID_PATH = os.path.join(OUTPUT_DIR, "hexagons.geojson")
PARQUET_PATH = os.path.join(OUTPUT_DIR, "hex_flood_risk.parquet")
CATASTRO_PARQUET_PATH = os.path.join(OUTPUT_DIR, "catastro_by_radio.parquet")
CATASTRO_CHANGES_PATH = os.path.join(OUTPUT_DIR, "catastro_changes_summary.parquet")

# ── Overture Maps (walkthru.earth H3-indexed indices) ───────────────────
OVERTURE_RELEASE = "2026-03-18.0"
OVERTURE_THEMES = ["buildings", "transportation", "places", "base"]
OVERTURE_BASE_URL = (
    "https://data.source.coop/walkthru-earth/indices/"
    "{theme}-index/v1/release={release}/h3/h3_res=9/data.parquet"
)
MIN_OVERTURE_HEXAGONS = 10_000  # Sparse layers (transport, places) have <50K populated cells

# ── EMSA (red eléctrica — media y alta tensión) ─────────────────────
EMSA_URL = (
    "http://datos.energia.gob.ar/dataset/"
    "ff99e7be-7bab-4617-9588-9a74ae046a40/resource/"
    "c8c0c8ff-5597-46d0-8b49-bbacd1560f29/download/"
    "-misiones-media-tensin-lneas.zip"
)
EMSA_PARQUET = os.path.join(OUTPUT_DIR, "emsa_powerlines.parquet")
MIN_EMSA_HEXAGONS = 1_000  # Sparse: only hexagons crossed by powerlines
