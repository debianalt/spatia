"""
Shared configuration for the Spatia satellite pipeline.

All constants used across pipeline scripts are centralised here.
Import from this module instead of defining local constants.
"""

import os

# ── Spatial ───────────────────────────────────────────────────────────────
MISIONES_BBOX = [-55.95, -28.17, -53.60, -25.47]  # [W, S, E, N]
H3_RESOLUTION = 9

# ── Google Cloud Storage ──────────────────────────────────────────────────
GCS_BUCKET = "spatia-satellite"

# ── Cloudflare R2 ─────────────────────────────────────────────────────────
R2_BUCKET = "neahub"

# ── Flood detection ──────────────────────────────────────────────────────
VV_THRESHOLD_DB = -15   # dB threshold for Sentinel-1 water detection
EXPORT_SCALE = 30       # metres per pixel (S1 GRD native ~10m, 30m for efficiency)
EXPORT_PREFIX = "flood"
FLOOD_GCS_PREFIX = "flood/"

# ── Validation thresholds ────────────────────────────────────────────────
MIN_HEXAGONS = 50_000       # Misiones has ~280K; <50K indicates corrupt data
MAX_NULL_FRACTION = 0.20    # max 20% nulls acceptable
SCORE_RANGE = (0, 100)

# ── Paths ────────────────────────────────────────────────────────────────
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PIPELINE_DIR, "output")
GRID_PATH = os.path.join(OUTPUT_DIR, "hexagons.geojson")
PARQUET_PATH = os.path.join(OUTPUT_DIR, "hex_flood_risk.parquet")
