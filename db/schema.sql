-- Spatia D1 Schema
-- Subset of PostGIS data for server-side chat tool use

DROP TABLE IF EXISTS radio_stats;
DROP TABLE IF EXISTS barrios_lookup;
DROP TABLE IF EXISTS radio_centroids;
DROP TABLE IF EXISTS indicator_catalog;
DROP TABLE IF EXISTS ndvi_annual;

CREATE TABLE radio_stats (
  redcode TEXT PRIMARY KEY,
  departamento TEXT NOT NULL,
  total_personas INTEGER,
  varones INTEGER,
  mujeres INTEGER,
  area_km2 REAL,
  densidad_hab_km2 REAL,
  pct_nbi REAL,
  pct_hacinamiento REAL,
  tasa_empleo REAL,
  tasa_desocupacion REAL,
  tasa_actividad REAL,
  pct_agua_red REAL,
  pct_cloacas REAL,
  pct_universitario REAL,
  pct_secundario_comp REAL,
  tamano_medio_hogar REAL,
  n_buildings INTEGER,
  ndvi_mean REAL,
  vulnerability_score REAL,
  vulnerability_class TEXT,
  -- Lens opportunity scores (percentile ranks 0-100)
  inv_score REAL,
  prod_score REAL,
  serv_score REAL,
  viv_score REAL,
  inv_sub1 REAL, inv_sub2 REAL, inv_sub3 REAL, inv_sub4 REAL, inv_sub5 REAL, inv_sub6 REAL,
  prod_sub1 REAL, prod_sub2 REAL, prod_sub3 REAL, prod_sub4 REAL, prod_sub5 REAL, prod_sub6 REAL,
  serv_sub1 REAL, serv_sub2 REAL, serv_sub3 REAL, serv_sub4 REAL, serv_sub5 REAL, serv_sub6 REAL,
  viv_sub1 REAL, viv_sub2 REAL, viv_sub3 REAL, viv_sub4 REAL, viv_sub5 REAL, viv_sub6 REAL
);

CREATE TABLE barrios_lookup (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  nombre_lower TEXT NOT NULL,
  localidad TEXT,
  departamento TEXT,
  tipo TEXT,
  fuente TEXT,
  redcodes TEXT NOT NULL -- JSON array: '["540070101","540070102"]'
);

CREATE TABLE radio_centroids (
  redcode TEXT PRIMARY KEY,
  lat REAL NOT NULL,
  lng REAL NOT NULL
);

CREATE TABLE indicator_catalog (
  id TEXT PRIMARY KEY,
  nombre TEXT NOT NULL,
  tema TEXT NOT NULL,
  unidad TEXT,
  descripcion TEXT
);

CREATE TABLE ndvi_annual (
  redcode TEXT NOT NULL,
  year INTEGER NOT NULL,
  mean_ndvi REAL,
  PRIMARY KEY (redcode, year)
);

CREATE INDEX idx_barrios_nombre ON barrios_lookup(nombre_lower);
CREATE INDEX idx_radio_stats_dpto ON radio_stats(departamento);
CREATE INDEX idx_ndvi_redcode ON ndvi_annual(redcode);
