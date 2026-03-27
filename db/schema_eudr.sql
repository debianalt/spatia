-- EUDR deforestation data: H3 res-7 hexagons for Chaco, Salta, Santiago del Estero, Formosa
-- Source: Hansen Global Forest Change 2024 v1.12 (30m) + MODIS MCD64A1 burned area
-- EUDR cutoff date: 31 December 2020

CREATE TABLE IF NOT EXISTS eudr_deforestation (
    h3index TEXT PRIMARY KEY,
    province TEXT NOT NULL,
    forest_cover_2020 REAL,
    forest_cover_current REAL,
    loss_total_pct REAL,
    loss_post_2020_pct REAL,
    loss_pre_2020_pct REAL,
    fire_post_2020_pct REAL,
    risk_score REAL,
    deforestation_post_2020 INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_eudr_province ON eudr_deforestation(province);
CREATE INDEX IF NOT EXISTS idx_eudr_risk ON eudr_deforestation(risk_score);
CREATE INDEX IF NOT EXISTS idx_eudr_deforestation ON eudr_deforestation(deforestation_post_2020);
