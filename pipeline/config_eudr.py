"""
Shared configuration for the EUDR deforestation compliance pipeline.

Covers Chaco, Salta, Santiago del Estero, and Formosa provinces —
Argentina's deforestation frontier for soy, cattle, and wood exports.

Import from this module instead of defining local constants.
"""

import os

# ── Spatial ───────────────────────────────────────────────────────────────
# Individual province bounding boxes [W, S, E, N] — padded ~0.1 deg
EUDR_PROVINCES = {
    # NOA
    "salta":              [-68.70, -26.50, -62.30, -21.90],
    "jujuy":              [-67.10, -24.40, -64.10, -21.70],
    "tucuman":            [-66.60, -28.00, -64.50, -26.00],
    "catamarca":          [-69.00, -30.20, -64.80, -25.80],
    "santiago_del_estero": [-65.30, -30.60, -61.60, -25.90],
    # NEA
    "formosa":            [-62.20, -27.00, -57.40, -22.90],
    "chaco":              [-63.50, -28.00, -58.40, -24.80],
    "corrientes":         [-59.80, -30.80, -55.60, -27.20],
    "misiones":           [-56.10, -28.20, -53.55, -25.44],
    "entre_rios":         [-60.80, -34.10, -57.80, -30.10],
}

# Combined bounding box covering all 10 NOA+NEA provinces (with padding)
EUDR_BBOX = [-69.00, -34.10, -53.55, -21.70]

H3_EUDR_RESOLUTION = 7  # ~5.16 km2 per hex, ~112K hexagons for 4 provinces

# ── EUDR Regulation ──────────────────────────────────────────────────────
EUDR_CUTOFF_YEAR = 2020  # Deforestation after 31 Dec 2020 is non-compliant
EUDR_COMMODITIES = ["soya", "cattle", "wood"]

# ── GEE Export ───────────────────────────────────────────────────────────
EXPORT_SCALE = 100       # metres per pixel (Hansen native 30m, 100m for efficiency)
DRIVE_FOLDER = "spatia-eudr"

# ── Cloudflare R2 ────────────────────────────────────────────────────────
R2_BUCKET = "neahub"
R2_EUDR_PREFIX = "data/eudr"

# ── Validation thresholds ────────────────────────────────────────────────
MIN_EUDR_HEXAGONS = 150_000  # 10 NOA+NEA provinces at res-7
MAX_NULL_FRACTION = 0.20     # max 20% nulls acceptable
SCORE_RANGE = (0, 100)

# ── Paths ────────────────────────────────────────────────────────────────
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PIPELINE_DIR, "output", "eudr")
GRID_PATH = os.path.join(OUTPUT_DIR, "hexagons_eudr.geojson")
GRID_LITE_PATH = os.path.join(OUTPUT_DIR, "hexagons_eudr_lite.geojson")
PARQUET_PATH = os.path.join(OUTPUT_DIR, "eudr_deforestation.parquet")

# Province boundary GeoJSON (from IGN)
PROJECT_ROOT = os.path.dirname(PIPELINE_DIR)
BOUNDARY_PATH = os.path.join(
    PROJECT_ROOT, "src", "lib", "data", "eudr_provinces_boundary.json"
)

# ── Risk Score Weights ───────────────────────────────────────────────────
# risk_score = w_loss * loss_post_2020 + w_fire * fire_post_2020
#            + w_noforest * (1 - forest_cover_2020)
WEIGHT_LOSS_POST_2020 = 0.70
WEIGHT_FIRE_POST_2020 = 0.20
WEIGHT_NO_FOREST_2020 = 0.10
