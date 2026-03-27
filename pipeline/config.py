"""
Shared configuration for the Spatia satellite pipeline.

All constants used across pipeline scripts are centralised here.
Import from this module instead of defining local constants.
"""

import os
from datetime import date, timedelta

# ── Spatial ───────────────────────────────────────────────────────────────
MISIONES_BBOX = [-56.10, -28.20, -53.55, -25.44]  # [W, S, E, N] — padded to cover edge hexagons
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
