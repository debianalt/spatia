const R2_PROD = 'https://pub-580c676bec7f4eeb96d7d30559a3cab7.r2.dev';

function getBase(): string {
	return R2_PROD;
}

export function getTilesUrl(name: 'buildings' | 'radios' | 'radios-chm' | 'terrain' | 'hexagons' | 'catastro'): string {
	if (name === 'terrain') {
		return '/api/terrain/{z}/{x}/{y}.png';
	}
	const files = {
		buildings: 'tiles/buildings-v5.pmtiles',
		radios: 'tiles/radios-v2.pmtiles',
		'radios-chm': 'tiles/radios-chm.pmtiles',
		hexagons: 'tiles/hexagons-v2.pmtiles',
		catastro: 'tiles/catastro.pmtiles'
	};
	return `pmtiles://${getBase()}/${files[name]}`;
}

export const CHM_COLORS: Record<number, string> = {
	0: '#15803d', // Selva alta continua
	1: '#65a30d', // Mosaico agro-forestal
	2: '#ca8a04', // Agrícola/pasturas
	3: '#6b7280', // Urbano/periurbano
} as const;

export const CHM_LABELS: Record<number, string> = {
	0: 'Selva alta continua',
	1: 'Mosaico agro-forestal',
	2: 'Agrícola/pasturas',
	3: 'Urbano/periurbano',
} as const;

export const TERRAIN_CONFIG = {
	exaggeration: 1.5,
	hillshade: {
		shadowColor: '#0a0a1a',
		highlightColor: '#8899bb',
		illuminationDirection: 315,
		exaggeration: 0.7
	}
} as const;

export function getParquetUrl(name: string): string {
	const busts: Record<string, string> = {
		hex_flood_risk: '?v=20',
		sat_environmental_risk: '?v=20',
		sat_climate_comfort: '?v=20',
		sat_green_capital: '?v=20',
		sat_change_pressure: '?v=20',
		sat_location_value: '?v=20',
		sat_agri_potential: '?v=20',
		sat_forest_health: '?v=20',
		sat_forestry_aptitude: '?v=20',
		sat_isolation_index: '?v=20',
		sat_territorial_gap: '?v=20',
		sat_health_access: '?v=20',
		sat_education_gap: '?v=20',
		sat_territorial_types: '?v=20',
		sat_sociodemographic: '?v=20',
		sat_economic_activity: '?v=20',
		sat_accessibility: '?v=20',
		overture_scores: '?v=20',
		emsa_powerlines: '?v=20',
	};
	const bust = busts[name] || '';
	return `${getBase()}/data/${name}.parquet${bust}`;
}

export function getFloodDptoUrl(parquetKey: string): string {
	return `${getBase()}/data/flood_dpto/hex_flood_${parquetKey}.parquet?v=20`;
}

export function getScoresDptoUrl(parquetKey: string): string {
	return `${getBase()}/data/scores_dpto/overture_scores_${parquetKey}.parquet?v=20`;
}

export function getSatDptoUrl(analysisId: string, parquetKey: string): string {
	return `${getBase()}/data/sat_dpto/sat_${analysisId}_${parquetKey}.parquet?v=20`;
}

export const PARQUETS = {
	get censo_radios() { return getParquetUrl('censo_radios'); },
	get censo_departamentos() { return getParquetUrl('censo_departamentos'); },
	get magyp_estimaciones() { return getParquetUrl('magyp_estimaciones'); },
	get ndvi_annual() { return getParquetUrl('ndvi_annual'); },
	get buildings_stats() { return getParquetUrl('buildings_stats'); },
	get radio_stats_master() { return getParquetUrl('radio_stats_master'); },
	get hex_flood_risk() { return getParquetUrl('hex_flood_risk'); },
	get h3_radio_crosswalk() { return getParquetUrl('h3_radio_crosswalk'); },
	get h3_parent_crosswalk() { return getParquetUrl('h3_parent_crosswalk'); },
	get catastro_by_radio() { return getParquetUrl('catastro_by_radio'); },
	get catastro_changes() { return getParquetUrl('catastro_changes_summary'); },
	get overture_buildings() { return getParquetUrl('overture_buildings'); },
	get overture_transportation() { return getParquetUrl('overture_transportation'); },
	get overture_places() { return getParquetUrl('overture_places'); },
	get overture_base() { return getParquetUrl('overture_base'); },
	get overture_scores() { return getParquetUrl('overture_scores'); },
	// Satellite composite scores
	get sat_environmental_risk() { return getParquetUrl('sat_environmental_risk'); },
	get sat_climate_comfort() { return getParquetUrl('sat_climate_comfort'); },
	get sat_green_capital() { return getParquetUrl('sat_green_capital'); },
	get sat_change_pressure() { return getParquetUrl('sat_change_pressure'); },
	get sat_location_value() { return getParquetUrl('sat_location_value'); },
	get sat_agri_potential() { return getParquetUrl('sat_agri_potential'); },
	get sat_forest_health() { return getParquetUrl('sat_forest_health'); },
	get sat_forestry_aptitude() { return getParquetUrl('sat_forestry_aptitude'); },
	get sat_isolation_index() { return getParquetUrl('sat_isolation_index'); },
	get sat_territorial_gap() { return getParquetUrl('sat_territorial_gap'); },
	get sat_land_use() { return getParquetUrl('sat_land_use'); },
	get sat_health_access() { return getParquetUrl('sat_health_access'); },
	get sat_education_gap() { return getParquetUrl('sat_education_gap'); },
	get sat_territorial_types() { return getParquetUrl('sat_territorial_types'); },
	get sat_sociodemographic() { return getParquetUrl('sat_sociodemographic'); },
	get sat_economic_activity() { return getParquetUrl('sat_economic_activity'); },
	get sat_accessibility() { return getParquetUrl('sat_accessibility'); },
	// Public infrastructure (datos.gob.ar)
	get emsa_powerlines() { return getParquetUrl('emsa_powerlines'); },
	// EUDR deforestation (H3 res-7, 10 provinces)
	get eudr_deforestation() { return getEudrParquetUrl('eudr_deforestation'); },
};

export const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

export const MAP_INIT = {
	center: [-54.4, -27.0] as [number, number],  // Misiones provincia
	zoom: 7.5,
	pitch: 30,
	bearing: -15,
	minZoom: 6,
	maxZoom: 18
} as const;

export const MAP_PROVINCE = {
	center: [-54.4, -27.0] as [number, number],
	zoom: 7.5,
	pitch: 30,
	bearing: -15,
} as const;

export const COLOR_RAMPS = {
	population: {
		property: 'est_personas',
		stops: [0, '#0d1b2a', 1, '#1b3a4b', 3, '#2a6f97', 5, '#468faf', 10, '#61a5c2', 20, '#89c2d9', 50, '#a9d6e5'],
		legendTitleKey: 'legend.estPersons',
		legendLabels: ['0', '1', '3', '5', '10', '50+']
	}
} as const;

export const GRADIENT_CSS = 'linear-gradient(to right, #0d1b2a, #1b3a4b, #2a6f97, #468faf, #61a5c2, #89c2d9, #a9d6e5)';

// ── Lens system ──────────────────────────────────────────────────────────────

export type LensId = 'invertir' | 'producir' | 'servir' | 'vivir';

export interface LensConfig {
	label: Record<'es' | 'en' | 'gn', string>;
	color: string;
}

export const LENS_CONFIG: Record<LensId, LensConfig> = {
	invertir: { label: { es: 'Invertir', en: 'Invest', gn: 'Moĩ viru' }, color: '#f59e0b' },
	producir: { label: { es: 'Producir', en: 'Produce', gn: "Mba'apo" }, color: '#22c55e' },
	servir: { label: { es: 'Servir', en: 'Serve', gn: 'Pytyvõ' }, color: '#3b82f6' },
	vivir: { label: { es: 'Vivir', en: 'Live', gn: 'Ñemity' }, color: '#06b6d4' },
} as const;

// ── Hex layer system (multi-resolution) ──────────────────────────────────────

export interface HexVariable {
	col: string;
	labelKey: string;
	aggregation: 'mean' | 'sum' | 'max';
}

export type TemporalMode = 'current' | 'baseline' | 'delta';

export interface HexLayerConfig {
	id: string;
	parquet: string;
	variables: HexVariable[];
	primaryVariable: string;
	colorScale: 'flood' | 'sequential' | 'diverging' | 'categorical' | 'green';
	aggregation: 'mean' | 'sum' | 'max';
	petalVars?: HexVariable[];
	titleKey: string;
	perDepartment?: boolean;
	temporal?: boolean;
}

export function getTemporalCol(col: string, mode: TemporalMode): string {
	if (mode === 'current') return col;
	if (mode === 'baseline') return col === 'score' ? 'score_baseline' : `${col}_baseline`;
	return col === 'score' ? 'delta_score' : `${col}_delta`;
}

export const HEX_LAYER_REGISTRY: Record<string, HexLayerConfig> = {
	flood_risk: {
		id: 'flood_risk',
		parquet: 'hex_flood_risk',
		variables: [
			{ col: 'flood_risk_score', labelKey: 'analysis.flood.riskScore', aggregation: 'mean' },
			{ col: 'type', labelKey: 'analysis.flood.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'analysis.flood.typeLabel', aggregation: 'mean' },
			{ col: 'jrc_occurrence', labelKey: 'analysis.flood.jrcOccurrence', aggregation: 'mean' },
			{ col: 'jrc_recurrence', labelKey: 'analysis.flood.jrcRecurrence', aggregation: 'mean' },
			{ col: 'jrc_seasonality', labelKey: 'analysis.flood.jrcSeasonality', aggregation: 'mean' },
			{ col: 'flood_extent_pct', labelKey: 'analysis.flood.currentExtent', aggregation: 'mean' },
		],
		primaryVariable: 'flood_risk_score',
		colorScale: 'flood',
		aggregation: 'mean',
		petalVars: [
			{ col: 'flood_risk_score', labelKey: 'analysis.flood.riskScore', aggregation: 'mean' },
			{ col: 'jrc_occurrence', labelKey: 'analysis.flood.jrcOccurrence', aggregation: 'mean' },
			{ col: 'jrc_recurrence', labelKey: 'analysis.flood.jrcRecurrence', aggregation: 'mean' },
			{ col: 'flood_extent_pct', labelKey: 'analysis.flood.currentExtent', aggregation: 'mean' },
		],
		titleKey: 'analysis.floodRisk.title',
		perDepartment: true,
	},
	// ── EMSA: Infraestructura eléctrica ──
	powerline_density: {
		id: 'powerline_density',
		parquet: 'emsa_powerlines',
		variables: [
			{ col: 'score', labelKey: 'emsa.score', aggregation: 'mean' },
			{ col: 'line_length_m', labelKey: 'emsa.lineLength', aggregation: 'sum' },
			{ col: 'line_count', labelKey: 'emsa.lineCount', aggregation: 'sum' },
		],
		primaryVariable: 'score',
		colorScale: 'sequential',
		aggregation: 'mean',
		titleKey: 'emsa.title',
		perDepartment: false,
	},
	// ── Satellite composite scores ──
	environmental_risk: {
		id: 'environmental_risk',
		parquet: 'sat_environmental_risk',
		variables: [
			{ col: 'type', labelKey: 'sat.envRisk.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.envRisk.typeLabel', aggregation: 'mean' },
			{ col: 'c_deforest', labelKey: 'sat.envRisk.deforest', aggregation: 'mean' },
			{ col: 'c_thermal_amp', labelKey: 'sat.envRisk.thermal', aggregation: 'mean' },
			{ col: 'c_slope', labelKey: 'sat.envRisk.slope', aggregation: 'mean' },
			{ col: 'c_hand', labelKey: 'sat.envRisk.hand', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'flood',
		aggregation: 'mean',
		titleKey: 'sat.envRisk.title',
		perDepartment: true,
	},
	climate_comfort: {
		id: 'climate_comfort',
		parquet: 'sat_climate_comfort',
		variables: [
			{ col: 'type', labelKey: 'sat.climate.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.climate.typeLabel', aggregation: 'mean' },
			{ col: 'c_heat_day', labelKey: 'sat.climate.heatDay', aggregation: 'mean' },
			{ col: 'c_heat_night', labelKey: 'sat.climate.heatNight', aggregation: 'mean' },
			{ col: 'c_precipitation', labelKey: 'sat.climate.precip', aggregation: 'mean' },
			{ col: 'c_frost', labelKey: 'sat.climate.frost', aggregation: 'mean' },
			{ col: 'c_water_stress', labelKey: 'sat.climate.waterStress', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'sequential',
		aggregation: 'mean',
		titleKey: 'sat.climate.title',
		perDepartment: true,
	},
	green_capital: {
		id: 'green_capital',
		parquet: 'sat_green_capital',
		variables: [
			{ col: 'type', labelKey: 'sat.green.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.green.typeLabel', aggregation: 'mean' },
			{ col: 'c_ndvi', labelKey: 'sat.green.ndvi', aggregation: 'mean' },
			{ col: 'c_treecover', labelKey: 'sat.green.treecover', aggregation: 'mean' },
			{ col: 'c_npp', labelKey: 'sat.green.npp', aggregation: 'mean' },
			{ col: 'c_lai', labelKey: 'sat.green.lai', aggregation: 'mean' },
			{ col: 'c_vcf', labelKey: 'sat.green.vcf', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'sequential',
		aggregation: 'mean',
		titleKey: 'sat.green.title',
		perDepartment: true,
	},
	change_pressure: {
		id: 'change_pressure',
		parquet: 'sat_change_pressure',
		variables: [
			{ col: 'type', labelKey: 'sat.change.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.change.typeLabel', aggregation: 'mean' },
			{ col: 'c_viirs_trend', labelKey: 'sat.change.viirsTrend', aggregation: 'mean' },
			{ col: 'c_ghsl_change', labelKey: 'sat.change.ghslChange', aggregation: 'mean' },
			{ col: 'c_hansen_loss', labelKey: 'sat.change.hansenLoss', aggregation: 'mean' },
			{ col: 'c_ndvi_trend', labelKey: 'sat.change.ndviTrend', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'sequential',
		aggregation: 'mean',
		titleKey: 'sat.change.title',
		perDepartment: true,
	},
	location_value: {
		id: 'location_value',
		parquet: 'sat_location_value',
		variables: [
			{ col: 'type', labelKey: 'sat.locValue.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.locValue.typeLabel', aggregation: 'mean' },
			{ col: 'c_access_20k', labelKey: 'sat.locValue.access20k', aggregation: 'mean' },
			{ col: 'c_healthcare', labelKey: 'sat.locValue.healthcare', aggregation: 'mean' },
			{ col: 'c_nightlights', labelKey: 'sat.locValue.nightlights', aggregation: 'mean' },
			{ col: 'c_slope', labelKey: 'sat.locValue.slope', aggregation: 'mean' },
			{ col: 'c_road_dist', labelKey: 'sat.locValue.roadDist', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'sequential',
		aggregation: 'mean',
		titleKey: 'sat.locValue.title',
		perDepartment: true,
	},
	agri_potential: {
		id: 'agri_potential',
		parquet: 'sat_agri_potential',
		variables: [
			{ col: 'type', labelKey: 'sat.agri.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.agri.typeLabel', aggregation: 'mean' },
			{ col: 'c_soc', labelKey: 'sat.agri.soc', aggregation: 'mean' },
			{ col: 'c_ph_optimal', labelKey: 'sat.agri.ph', aggregation: 'mean' },
			{ col: 'c_clay', labelKey: 'sat.agri.clay', aggregation: 'mean' },
			{ col: 'c_precipitation', labelKey: 'sat.agri.precip', aggregation: 'mean' },
			{ col: 'c_gdd', labelKey: 'sat.agri.gdd', aggregation: 'mean' },
			{ col: 'c_slope', labelKey: 'sat.agri.slope', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'sequential',
		aggregation: 'mean',
		titleKey: 'sat.agri.title',
		perDepartment: true,
	},
	forest_health: {
		id: 'forest_health',
		parquet: 'sat_forest_health',
		variables: [
			{ col: 'type', labelKey: 'sat.forestH.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.forestH.typeLabel', aggregation: 'mean' },
			{ col: 'c_ndvi_trend', labelKey: 'sat.forestH.ndviTrend', aggregation: 'mean' },
			{ col: 'c_loss_ratio', labelKey: 'sat.forestH.lossRatio', aggregation: 'mean' },
			{ col: 'c_gpp', labelKey: 'sat.forestH.gpp', aggregation: 'mean' },
			{ col: 'c_et', labelKey: 'sat.forestH.et', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'sequential',
		aggregation: 'mean',
		titleKey: 'sat.forestH.title',
		perDepartment: true,
	},
	forestry_aptitude: {
		id: 'forestry_aptitude',
		parquet: 'sat_forestry_aptitude',
		variables: [
			{ col: 'type', labelKey: 'sat.forestry.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.forestry.typeLabel', aggregation: 'mean' },
			{ col: 'c_ph', labelKey: 'sat.forestry.ph', aggregation: 'mean' },
			{ col: 'c_clay', labelKey: 'sat.forestry.clay', aggregation: 'mean' },
			{ col: 'c_precipitation', labelKey: 'sat.forestry.precip', aggregation: 'mean' },
			{ col: 'c_slope', labelKey: 'sat.forestry.slope', aggregation: 'mean' },
			{ col: 'c_road_dist', labelKey: 'sat.forestry.roadDist', aggregation: 'mean' },
			{ col: 'c_access_50k', labelKey: 'sat.forestry.access50k', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'sequential',
		aggregation: 'mean',
		titleKey: 'sat.forestry.title',
		perDepartment: true,
	},
	isolation_index: {
		id: 'isolation_index',
		parquet: 'sat_isolation_index',
		variables: [
			{ col: 'type', labelKey: 'sat.isolation.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.isolation.typeLabel', aggregation: 'mean' },
			{ col: 'c_access_100k', labelKey: 'sat.isolation.access100k', aggregation: 'mean' },
			{ col: 'c_travel_posadas', labelKey: 'sat.isolation.travelPosadas', aggregation: 'mean' },
			{ col: 'c_road_density', labelKey: 'sat.isolation.roadDensity', aggregation: 'mean' },
			{ col: 'c_nightlights', labelKey: 'sat.isolation.nightlights', aggregation: 'mean' },
			{ col: 'c_friction', labelKey: 'sat.isolation.friction', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'flood',
		aggregation: 'mean',
		titleKey: 'sat.isolation.title',
		perDepartment: true,
	},
	territorial_gap: {
		id: 'territorial_gap',
		parquet: 'sat_territorial_gap',
		variables: [
			{ col: 'type', labelKey: 'sat.gap.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.gap.typeLabel', aggregation: 'mean' },
			{ col: 'c_nightlights', labelKey: 'sat.gap.nightlights', aggregation: 'mean' },
			{ col: 'c_nbi', labelKey: 'sat.gap.nbi', aggregation: 'mean' },
			{ col: 'c_sin_agua', labelKey: 'sat.gap.sinAgua', aggregation: 'mean' },
			{ col: 'c_sin_cloacas', labelKey: 'sat.gap.sinCloacas', aggregation: 'mean' },
			{ col: 'c_isolation', labelKey: 'sat.gap.isolation', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'flood',
		aggregation: 'mean',
		titleKey: 'sat.gap.title',
		perDepartment: true,
	},
	health_access: {
		id: 'health_access',
		parquet: 'sat_health_access',
		variables: [
			{ col: 'type', labelKey: 'sat.health.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.health.typeLabel', aggregation: 'mean' },
			{ col: 'c_healthcare_time', labelKey: 'sat.health.time', aggregation: 'mean' },
			{ col: 'c_healthcare_walk', labelKey: 'sat.health.walk', aggregation: 'mean' },
			{ col: 'c_pop_density', labelKey: 'sat.health.popDensity', aggregation: 'mean' },
			{ col: 'c_health_coverage', labelKey: 'sat.health.coverage', aggregation: 'mean' },
			{ col: 'c_nbi', labelKey: 'sat.health.nbi', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'flood',
		aggregation: 'mean',
		titleKey: 'sat.health.title',
		perDepartment: true,
	},
	education_gap: {
		id: 'education_gap',
		parquet: 'sat_education_gap',
		variables: [
			{ col: 'type', labelKey: 'sat.edu.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'sat.edu.typeLabel', aggregation: 'mean' },
			{ col: 'c_no_instruction', labelKey: 'sat.edu.noInstruction', aggregation: 'mean' },
			{ col: 'c_dropout_13_18', labelKey: 'sat.edu.dropout', aggregation: 'mean' },
			{ col: 'c_only_primary', labelKey: 'sat.edu.onlyPrimary', aggregation: 'mean' },
			{ col: 'c_university', labelKey: 'sat.edu.university', aggregation: 'mean' },
			{ col: 'c_isolation', labelKey: 'sat.edu.isolation', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'flood',
		aggregation: 'mean',
		titleKey: 'sat.edu.title',
		perDepartment: true,
	},
	// ── Territorial classification (PCA + metabolic clustering) ──
	territorial_types: {
		id: 'territorial_types',
		parquet: 'sat_territorial_types',
		variables: [
			{ col: 'score', labelKey: 'sat.types.score', aggregation: 'mean' },
			{ col: 'territorial_type', labelKey: 'sat.types.type', aggregation: 'mean' },
			{ col: 'c_npp', labelKey: 'sat.types.npp', aggregation: 'mean' },
			{ col: 'c_ndvi', labelKey: 'sat.types.ndvi', aggregation: 'mean' },
			{ col: 'c_treecover', labelKey: 'sat.types.treecover', aggregation: 'mean' },
			{ col: 'c_frac_trees', labelKey: 'sat.types.fracTrees', aggregation: 'mean' },
			{ col: 'c_frac_crops', labelKey: 'sat.types.fracCrops', aggregation: 'mean' },
			{ col: 'c_frac_built', labelKey: 'sat.types.fracBuilt', aggregation: 'mean' },
			{ col: 'c_deforest', labelKey: 'sat.types.deforest', aggregation: 'mean' },
			{ col: 'c_nightlights', labelKey: 'sat.types.nightlights', aggregation: 'mean' },
			{ col: 'c_viirs_trend', labelKey: 'sat.types.viirsTrend', aggregation: 'mean' },
			{ col: 'c_ghsl_change', labelKey: 'sat.types.ghslChange', aggregation: 'mean' },
			{ col: 'c_precipitation', labelKey: 'sat.types.precip', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'sequential',
		aggregation: 'mean',
		titleKey: 'sat.types.title',
		perDepartment: true,
	},
	// ── Migrated from radio/catastro to H3 ──
	territorial_scores: {
		id: 'territorial_scores',
		parquet: 'overture_scores',
		variables: [
			{ col: 'score', labelKey: 'analysis.scores.score', aggregation: 'mean' },
			{ col: 'type', labelKey: 'analysis.scores.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'analysis.scores.typeLabel', aggregation: 'mean' },
			{ col: 'urban_consolidation', labelKey: 'scores.urbanConsolidation', aggregation: 'mean' },
			{ col: 'paving_index', labelKey: 'scores.paving', aggregation: 'mean' },
			{ col: 'service_access', labelKey: 'scores.serviceAccess', aggregation: 'mean' },
			{ col: 'commercial_vitality', labelKey: 'scores.commercial', aggregation: 'mean' },
			{ col: 'road_connectivity', labelKey: 'scores.roadConnectivity', aggregation: 'mean' },
			{ col: 'building_mix', labelKey: 'scores.buildingMix', aggregation: 'mean' },
			{ col: 'urbanization', labelKey: 'scores.urbanization', aggregation: 'mean' },
			{ col: 'water_exposure', labelKey: 'scores.waterExposure', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'sequential',
		aggregation: 'mean',
		titleKey: 'analysis.scores.title',
		perDepartment: true,
	},
	sociodemographic: {
		id: 'sociodemographic',
		parquet: 'sat_sociodemographic',
		variables: [
			{ col: 'score', labelKey: 'analysis.socio.score', aggregation: 'mean' },
			{ col: 'type', labelKey: 'analysis.socio.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'analysis.socio.typeLabel', aggregation: 'mean' },
			{ col: 'densidad_hab_km2', labelKey: 'radio.densidad', aggregation: 'mean' },
			{ col: 'pct_nbi', labelKey: 'radio.nbi', aggregation: 'mean' },
			{ col: 'pct_hacinamiento', labelKey: 'radio.hacinamiento', aggregation: 'mean' },
			{ col: 'pct_propietario', labelKey: 'radio.propietario', aggregation: 'mean' },
			{ col: 'tamano_medio_hogar', labelKey: 'radio.tamHogar', aggregation: 'mean' },
			{ col: 'pct_computadora', labelKey: 'radio.computadora', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'flood',
		aggregation: 'mean',
		titleKey: 'analysis.socio.title',
		perDepartment: true,
	},
	economic_activity: {
		id: 'economic_activity',
		parquet: 'sat_economic_activity',
		variables: [
			{ col: 'score', labelKey: 'analysis.economic.score', aggregation: 'mean' },
			{ col: 'type', labelKey: 'analysis.economic.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'analysis.economic.typeLabel', aggregation: 'mean' },
			{ col: 'tasa_empleo', labelKey: 'radio.empleo', aggregation: 'mean' },
			{ col: 'tasa_actividad', labelKey: 'radio.actividad', aggregation: 'mean' },
			{ col: 'pct_universitario', labelKey: 'radio.universitario', aggregation: 'mean' },
			{ col: 'viirs_mean_radiance', labelKey: 'radio.viirs', aggregation: 'mean' },
			{ col: 'building_density_per_km2', labelKey: 'radio.buildingDensity', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'sequential',
		aggregation: 'mean',
		titleKey: 'analysis.economic.title',
		perDepartment: true,
	},
	accessibility: {
		id: 'accessibility',
		parquet: 'sat_accessibility',
		variables: [
			{ col: 'score', labelKey: 'analysis.accessibility.score', aggregation: 'mean' },
			{ col: 'type', labelKey: 'analysis.accessibility.type', aggregation: 'mean' },
			{ col: 'type_label', labelKey: 'analysis.accessibility.typeLabel', aggregation: 'mean' },
			{ col: 'travel_min_posadas', labelKey: 'radio.travelPosadas', aggregation: 'mean' },
			{ col: 'travel_min_cabecera', labelKey: 'radio.travelCabecera', aggregation: 'mean' },
			{ col: 'dist_nearest_hospital_km', labelKey: 'radio.distHospital', aggregation: 'mean' },
			{ col: 'dist_nearest_secundaria_km', labelKey: 'radio.distSecundaria', aggregation: 'mean' },
			{ col: 'dist_primary_m', labelKey: 'radio.distPrimaria', aggregation: 'mean' },
		],
		primaryVariable: 'score',
		colorScale: 'flood',
		aggregation: 'mean',
		titleKey: 'analysis.accessibility.title',
		perDepartment: true,
	},
	// ── EUDR deforestation risk (H3 res-7, 10 provinces) ──
	eudr: {
		id: 'eudr',
		parquet: 'eudr_deforestation',
		variables: [
			{ col: 'risk_score', labelKey: 'eudr.riskScore', aggregation: 'mean' },
			{ col: 'loss_post_2020_pct', labelKey: 'eudr.lossPost2020', aggregation: 'mean' },
			{ col: 'fire_post_2020_pct', labelKey: 'eudr.firePost2020', aggregation: 'mean' },
			{ col: 'forest_cover_2020', labelKey: 'eudr.forest2020', aggregation: 'mean' },
			{ col: 'forest_cover_current', labelKey: 'eudr.forestCurrent', aggregation: 'mean' },
		],
		primaryVariable: 'risk_score',
		colorScale: 'flood',
		aggregation: 'mean',
		petalVars: [
			{ col: 'risk_score', labelKey: 'eudr.riskScore', aggregation: 'mean' },
			{ col: 'loss_post_2020_pct', labelKey: 'eudr.lossPost2020', aggregation: 'mean' },
			{ col: 'fire_post_2020_pct', labelKey: 'eudr.firePost2020', aggregation: 'mean' },
			{ col: 'forest_cover_2020', labelKey: 'eudr.forest2020', aggregation: 'mean' },
		],
		titleKey: 'trade.eudr.analysis_title',
		perDepartment: false,
	},
};

// ── Analysis system ─────────────────────────────────────────────────────────

export interface AnalysisConfig {
	id: string;
	lensId: LensId;
	titleKey: string;
	descKey: string;
	icon: string;
	status: 'available' | 'coming_soon';
	spatialUnit?: 'radio' | 'hexagon' | 'catastro';
	dashboard?: boolean;
	choropleth?: {
		parquet: string;
		column: string;
		colorScale: 'price' | 'score' | 'diverging' | 'sequential' | 'flood';
		legendKey: string;
	};
}

export const ANALYSIS_REGISTRY: AnalysisConfig[] = [
	// ── Vivir ──
	{
		id: 'flood_risk',
		lensId: 'vivir',
		titleKey: 'analysis.floodRisk.title',
		descKey: 'analysis.floodRisk.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	// ── Perfil Territorial (cross-lens, catastro-integrated) ──
	{
		id: 'territorial_scores',
		lensId: 'invertir',
		titleKey: 'analysis.scores.title',
		descKey: 'analysis.scores.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	// ── Radio-based analyses (radio_stats_master via crosswalk) ──
	// investment_value removed — re_median_usd_m2 only covers 26% of radios
	{
		id: 'sociodemographic',
		lensId: 'vivir',
		titleKey: 'analysis.socio.title',
		descKey: 'analysis.socio.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	// forest_potential hidden — covered by forest_health + forestry_aptitude (H3)
	{
		id: 'economic_activity',
		lensId: 'invertir',
		titleKey: 'analysis.economic.title',
		descKey: 'analysis.economic.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	// change_dynamics hidden — covered by change_pressure (H3)
	// productive_aptitude hidden — covered by agri_potential (H3)
	{
		id: 'accessibility',
		lensId: 'servir',
		titleKey: 'analysis.accessibility.title',
		descKey: 'analysis.accessibility.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	// natural_risks hidden — covered by environmental_risk (H3)
	// ── Satellite H3 analyses ──
	{
		id: 'environmental_risk',
		lensId: 'vivir',
		titleKey: 'sat.envRisk.title',
		descKey: 'sat.envRisk.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'climate_comfort',
		lensId: 'vivir',
		titleKey: 'sat.climate.title',
		descKey: 'sat.climate.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'green_capital',
		lensId: 'vivir',
		titleKey: 'sat.green.title',
		descKey: 'sat.green.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'change_pressure',
		lensId: 'invertir',
		titleKey: 'sat.change.title',
		descKey: 'sat.change.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'location_value',
		lensId: 'invertir',
		titleKey: 'sat.locValue.title',
		descKey: 'sat.locValue.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'agri_potential',
		lensId: 'producir',
		titleKey: 'sat.agri.title',
		descKey: 'sat.agri.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'powerline_density',
		lensId: 'producir',
		titleKey: 'emsa.title',
		descKey: 'emsa.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'forest_health',
		lensId: 'producir',
		titleKey: 'sat.forestH.title',
		descKey: 'sat.forestH.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'forestry_aptitude',
		lensId: 'producir',
		titleKey: 'sat.forestry.title',
		descKey: 'sat.forestry.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'isolation_index',
		lensId: 'servir',
		titleKey: 'sat.isolation.title',
		descKey: 'sat.isolation.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'territorial_gap',
		lensId: 'servir',
		titleKey: 'sat.gap.title',
		descKey: 'sat.gap.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'health_access',
		lensId: 'servir',
		titleKey: 'sat.health.title',
		descKey: 'sat.health.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'education_gap',
		lensId: 'servir',
		titleKey: 'sat.edu.title',
		descKey: 'sat.edu.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	// ── EUDR ──
	{
		id: 'eudr',
		lensId: 'producir',
		titleKey: 'trade.eudr.analysis_title',
		descKey: 'trade.eudr.analysis_desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	// ── Territorial classification ──
	{
		id: 'territorial_types',
		lensId: 'vivir',
		titleKey: 'sat.types.title',
		descKey: 'sat.types.desc',
		icon: '',
		status: 'available',
		spatialUnit: 'hexagon',
	},
];

// ── Territorial Scores definitions ──────────────────────────────────────────
export const TERRITORIAL_SCORE_COLS = [
	'paving_index', 'urban_consolidation', 'service_access',
	'commercial_vitality', 'road_connectivity', 'building_mix',
	'urbanization', 'water_exposure',
] as const;

export const TERRITORIAL_SCORE_LABELS: Record<string, { es: string; en: string }> = {
	paving_index:         { es: 'Pavimentación',    en: 'Paving' },
	urban_consolidation:  { es: 'Consolidación',    en: 'Consolidation' },
	service_access:       { es: 'Servicios',        en: 'Services' },
	commercial_vitality:  { es: 'Comercio',         en: 'Commerce' },
	road_connectivity:    { es: 'Conectividad',     en: 'Connectivity' },
	building_mix:         { es: 'Mix tipológico',   en: 'Building Mix' },
	urbanization:         { es: 'Urbanización',     en: 'Urbanisation' },
	water_exposure:       { es: 'Exp. hídrica',     en: 'Water Exp.' },
};

export const TERRITORIAL_SCORE_DESCS: Record<string, { es: string; en: string }> = {
	paving_index:         { es: '% de calles pavimentadas en radio de 3 km', en: '% paved roads within 3 km' },
	urban_consolidation:  { es: 'Densidad edilicia + residencial + pavimentación + red vial', en: 'Building density + residential + paving + road network' },
	service_access:       { es: 'Salud, educación, farmacia y combustible en radio de 5 km', en: 'Health, education, pharmacy and fuel within 5 km' },
	commercial_vitality:  { es: 'Diversidad y densidad de comercios y servicios en 3 km', en: 'Diversity and density of commerce and services within 3 km' },
	road_connectivity:    { es: 'Jerarquía vial + densidad de segmentos + puentes', en: 'Road hierarchy + segment density + bridges' },
	building_mix:         { es: 'Diversidad de tipos: residencial, comercial, educativo, salud', en: 'Building type diversity: residential, commercial, education, health' },
	urbanization:         { es: 'Grado de desarrollo urbano (densidad edilicia + uso del suelo)', en: 'Degree of urban development (building density + land use)' },
	water_exposure:       { es: 'Densidad de ríos y arroyos en radio de 3 km', en: 'River and stream density within 3 km' },
};

export const TERRITORIAL_COMPONENT_COLS = [
	'building_count', 'n_paved', 'n_unpaved', 'place_count',
	'segment_count', 'water_kring_total',
] as const;

// ── Radio-based analysis configurations ─────────────────────────────────────
export type RadioPetalCol = {
	col: string;
	label: { es: string; en: string };
	desc: { es: string; en: string };
	invert: boolean;
	source?: 'catastro_by_radio';
};

export type RadioAnalysisConfig = {
	id: string;
	choroplethCol: string;
	colorScale: 'price' | 'sequential' | 'flood';
	invertChoropleth?: boolean;
	petalCols: RadioPetalCol[];
	howToRead: { es: string; en: string };
	implications: { es: string; en: string };
	methodology: { es: string; en: string };
};

export const RADIO_ANALYSIS_REGISTRY: Record<string, RadioAnalysisConfig> = {
	investment_value: {
		id: 'investment_value',
		choroplethCol: 're_median_usd_m2',
		colorScale: 'price',
		petalCols: [
			{ col: 're_median_usd_m2', label: { es: 'Precio USD/m²', en: 'Price USD/m²' }, desc: { es: 'Mediana de publicaciones activas', en: 'Median of active listings' }, invert: false },
			{ col: 're_n_listings', label: { es: 'Publicaciones', en: 'Listings' }, desc: { es: 'Cantidad de avisos activos en la zona', en: 'Number of active listings in the area' }, invert: false },
			{ col: 'opportunity_score', label: { es: 'Oportunidad', en: 'Opportunity' }, desc: { es: 'Score compuesto de potencial de inversión', en: 'Composite investment potential score' }, invert: false },
			{ col: 're_attract_score', label: { es: 'Atractivo inmob.', en: 'RE Attractiveness' }, desc: { es: 'Score de atractivo para el mercado', en: 'Market attractiveness score' }, invert: false },
			{ col: 'building_density_per_km2', label: { es: 'Densidad edilicia', en: 'Building density' }, desc: { es: 'Edificios por km²', en: 'Buildings per km²' }, invert: false },
		],
		howToRead: { es: 'Las parcelas se colorean según el precio mediano USD/m² de la zona. Colores cálidos = mayor precio. El pétalo compara precio, oferta, oportunidad, atractivo y densidad de la zona.', en: 'Parcels are coloured by median USD/m² price. Warmer colours = higher price. The petal compares price, supply, opportunity, attractiveness and density.' },
		implications: { es: 'Zonas con alto precio y pocas publicaciones indican mercado cerrado. Zonas con score de oportunidad alto y precio bajo pueden representar oportunidades de inversión.', en: 'High price with few listings indicates a closed market. High opportunity score with low price may represent investment opportunities.' },
		methodology: { es: 'Precio mediano USD/m² de publicaciones activas (MeLi/Argenprop). Score de oportunidad = precio bajo + accesibilidad alta + consolidación urbana. Cobertura: 26% de radios con datos de mercado.', en: 'Median USD/m² from active listings (MeLi/Argenprop). Opportunity score = low price + high accessibility + urban consolidation. Coverage: 26% of radios with market data.' },
	},
	natural_risks: {
		id: 'natural_risks',
		choroplethCol: 'landslide_score',
		colorScale: 'flood',
		petalCols: [
			{ col: 'flood_frequency', label: { es: 'Inundación', en: 'Flooding' }, desc: { es: 'Frecuencia histórica de inundaciones', en: 'Historical flood frequency' }, invert: false },
			{ col: 'landslide_score', label: { es: 'Deslizamiento', en: 'Landslide' }, desc: { es: 'Susceptibilidad a deslizamientos de suelo', en: 'Soil landslide susceptibility' }, invert: false },
			{ col: 'rusle_mean', label: { es: 'Erosión', en: 'Erosion' }, desc: { es: 'Potencial de erosión hídrica (RUSLE)', en: 'Water erosion potential (RUSLE)' }, invert: false },
			{ col: 'slope_mean', label: { es: 'Pendiente', en: 'Slope' }, desc: { es: 'Pendiente media del terreno (%)', en: 'Mean terrain slope (%)' }, invert: false },
			{ col: 'deforest_pressure_score', label: { es: 'Presión deforest.', en: 'Deforestation' }, desc: { es: 'Presión de deforestación en la zona', en: 'Deforestation pressure in the area' }, invert: false },
		],
		howToRead: { es: 'Las parcelas se colorean según el score de riesgo de deslizamiento. Colores cálidos = mayor riesgo. El pétalo muestra 5 riesgos simultáneos: mayor extensión = mayor exposición.', en: 'Parcels are coloured by landslide risk score. Warmer colours = higher risk. The petal shows 5 simultaneous risks.' },
		implications: { es: 'Parcelas con múltiples riesgos altos requieren estudios de suelo antes de invertir. Pendiente alta + erosión alta señalan terrenos inestables. La deforestación reciente agrava todos los riesgos.', en: 'Parcels with multiple high risks require soil studies before investing. High slope + high erosion indicate unstable terrain.' },
		methodology: { es: 'Score compuesto de 5 indicadores normalizados (0-100): frecuencia de inundación JRC, susceptibilidad deslizamiento (litología + pendiente), erosión RUSLE, pendiente media FABDEM, presión de deforestación Hansen.', en: 'Composite score of 5 normalised indicators (0-100): JRC flood frequency, landslide susceptibility, RUSLE erosion, mean slope, deforestation pressure.' },
	},
	productive_aptitude: {
		id: 'productive_aptitude',
		choroplethCol: 'agri_potential_score',
		colorScale: 'sequential',
		petalCols: [
			{ col: 'soil_ph', label: { es: 'pH del suelo', en: 'Soil pH' }, desc: { es: 'Acidez/alcalinidad del suelo (SoilGrids)', en: 'Soil acidity/alkalinity (SoilGrids)' }, invert: false },
			{ col: 'soil_organic_carbon', label: { es: 'Carbono orgánico', en: 'Organic carbon' }, desc: { es: 'Contenido de materia orgánica', en: 'Organic matter content' }, invert: false },
			{ col: 'chirps_annual_mm', label: { es: 'Precipitación', en: 'Rainfall' }, desc: { es: 'Lluvia anual media en mm (CHIRPS)', en: 'Mean annual rainfall in mm (CHIRPS)' }, invert: false },
			{ col: 'slope_mean', label: { es: 'Pendiente', en: 'Slope' }, desc: { es: 'Pendiente media — menor es mejor para cultivos', en: 'Mean slope — lower is better for crops' }, invert: true },
			{ col: 'agri_potential_score', label: { es: 'Aptitud agrícola', en: 'Ag. potential' }, desc: { es: 'Score compuesto de potencial productivo', en: 'Composite productive potential score' }, invert: false },
		],
		howToRead: { es: 'Las parcelas se colorean según el score de aptitud agrícola. Verde más intenso = mayor potencial. El pétalo muestra suelo, lluvia, pendiente y aptitud general.', en: 'Parcels are coloured by agricultural aptitude score. Greener = higher potential.' },
		implications: { es: 'Suelos con pH 5.5-6.5 y alto carbono orgánico son óptimos para yerba mate y té. Pendientes >15% requieren terrazas. Precipitación >1600mm/año permite cultivos sin riego.', en: 'Soils with pH 5.5-6.5 and high organic carbon are optimal for yerba mate and tea.' },
		methodology: { es: 'Score compuesto: pH del suelo SoilGrids (óptimo 5.5-6.5), carbono orgánico, precipitación CHIRPS, pendiente FABDEM. Fuente censal: radio_stats_master con datos SoilGrids 250m + CHIRPS 5km.', en: 'Composite score: soil pH SoilGrids, organic carbon, CHIRPS precipitation, FABDEM slope.' },
	},
	accessibility: {
		id: 'accessibility',
		choroplethCol: 'travel_min_posadas',
		colorScale: 'sequential',
		invertChoropleth: true,
		petalCols: [
			{ col: 'travel_min_posadas', label: { es: 'Tiempo a Posadas', en: 'Time to Posadas' }, desc: { es: 'Minutos de viaje a la capital', en: 'Travel minutes to the capital' }, invert: true },
			{ col: 'travel_min_cabecera', label: { es: 'Tiempo a cabecera', en: 'Time to dept. seat' }, desc: { es: 'Minutos a la cabecera departamental', en: 'Minutes to department seat' }, invert: true },
			{ col: 'dist_nearest_hospital_km', label: { es: 'Hospital', en: 'Hospital' }, desc: { es: 'Distancia al hospital más cercano (km)', en: 'Distance to nearest hospital (km)' }, invert: true },
			{ col: 'dist_nearest_secundaria_km', label: { es: 'Escuela sec.', en: 'High school' }, desc: { es: 'Distancia a escuela secundaria (km)', en: 'Distance to high school (km)' }, invert: true },
			{ col: 'dist_primary_m', label: { es: 'Ruta principal', en: 'Main road' }, desc: { es: 'Distancia a ruta primaria (metros)', en: 'Distance to primary road (meters)' }, invert: true },
		],
		howToRead: { es: 'Las parcelas se colorean según el tiempo de viaje a Posadas. Verde = más cercano. El pétalo muestra accesibilidad a servicios clave — en este caso mayor extensión = mejor acceso (menor distancia/tiempo).', en: 'Parcels are coloured by travel time to Posadas. Green = closer. The petal shows accessibility to key services.' },
		implications: { es: 'Zonas a más de 2 horas de Posadas y sin hospital cercano representan alto riesgo para familias. La distancia a ruta principal determina el costo logístico para producción.', en: 'Areas over 2 hours from Posadas without a nearby hospital represent high risk for families.' },
		methodology: { es: 'Tiempo de viaje motorizado a Posadas y cabecera departamental (superficie de fricción Oxford MAP). Distancia euclidiana a hospitales, escuelas secundarias y rutas primarias (OSM). Fuente: Nelson et al. 2019 + Oxford MAP 2019 + OSM.', en: 'Motorised travel time to Posadas and dept seat (Oxford MAP friction surface). Euclidean distance to hospitals, schools and primary roads.' },
	},
	change_dynamics: {
		id: 'change_dynamics',
		choroplethCol: 'deforest_pressure_score',
		colorScale: 'sequential',
		petalCols: [
			{ col: 'n_new_parcels_90d', label: { es: 'Parcelas nuevas', en: 'New parcels' }, desc: { es: 'Parcelas creadas en últimos 90 días', en: 'Parcels created in last 90 days' }, invert: false, source: 'catastro_by_radio' },
			{ col: 'deforest_pressure_score', label: { es: 'Presión deforest.', en: 'Deforestation' }, desc: { es: 'Intensidad de deforestación reciente', en: 'Recent deforestation intensity' }, invert: false },
			{ col: 'building_density_per_km2', label: { es: 'Densidad edilicia', en: 'Building density' }, desc: { es: 'Edificios por km² (proxy presión urbana)', en: 'Buildings per km² (urban pressure proxy)' }, invert: false },
			{ col: 'mb_urban_frac', label: { es: 'Fracción urbana', en: 'Urban fraction' }, desc: { es: '% de superficie urbanizada', en: '% urbanised surface' }, invert: false },
		],
		howToRead: { es: 'Las parcelas se colorean según la presión de deforestación. Mayor intensidad de color = mayor cambio. El pétalo muestra 4 indicadores de dinámica territorial.', en: 'Parcels are coloured by deforestation pressure. Higher intensity = more change.' },
		implications: { es: 'Zonas con muchas parcelas nuevas y alta presión de deforestación están en transición activa — posible valorización pero también riesgo ambiental. Alta densidad edilicia + baja fracción urbana indica expansión informal.', en: 'Areas with many new parcels and high deforestation pressure are in active transition.' },
		methodology: { es: 'Parcelas nuevas: Catastro Misiones (ventana 90 días). Deforestación: Hansen GFC pérdida acumulada. Densidad edilicia: Global Building Atlas. Fracción urbana: MapBiomas Argentina.', en: 'New parcels: Misiones Cadastre (90-day window). Deforestation: Hansen GFC cumulative loss. Building density: GBA. Urban fraction: MapBiomas.' },
	},
	sociodemographic: {
		id: 'sociodemographic',
		choroplethCol: 'pct_nbi',
		colorScale: 'flood',
		petalCols: [
			{ col: 'densidad_hab_km2', label: { es: 'Densidad hab.', en: 'Pop. density' }, desc: { es: 'Habitantes por km²', en: 'Inhabitants per km²' }, invert: false },
			{ col: 'pct_nbi', label: { es: 'NBI', en: 'UBN' }, desc: { es: '% hogares con necesidades básicas insatisfechas', en: '% households with unmet basic needs' }, invert: false },
			{ col: 'pct_hacinamiento', label: { es: 'Hacinamiento', en: 'Overcrowding' }, desc: { es: '% hogares en condiciones de hacinamiento', en: '% households in overcrowded conditions' }, invert: false },
			{ col: 'pct_propietario', label: { es: 'Propietarios', en: 'Homeowners' }, desc: { es: '% hogares propietarios de la vivienda', en: '% homeowner households' }, invert: false },
			{ col: 'tamano_medio_hogar', label: { es: 'Tamaño hogar', en: 'Household size' }, desc: { es: 'Personas promedio por hogar', en: 'Average persons per household' }, invert: false },
			{ col: 'pct_computadora', label: { es: 'Computadora', en: 'Computer' }, desc: { es: '% hogares con computadora', en: '% households with computer' }, invert: false },
		],
		howToRead: { es: 'Las parcelas se colorean según el % de NBI (necesidades básicas insatisfechas). Colores cálidos = mayor pobreza. El pétalo muestra el perfil sociodemográfico de la zona: densidad, NBI, hacinamiento, propiedad, tamaño de hogar y acceso digital.', en: 'Parcels are coloured by UBN %. Warmer = higher poverty. The petal shows the sociodemographic profile.' },
		implications: { es: 'Zonas con alto NBI y hacinamiento requieren políticas de vivienda social. Alto % de propietarios indica estabilidad residencial. Baja conectividad digital limita servicios y educación remota.', en: 'High UBN and overcrowding require social housing policies. High homeownership indicates residential stability.' },
		methodology: { es: 'Fuente: INDEC Censo Nacional de Población, Hogares y Viviendas 2022. Variables a nivel radio censal (2,012 radios). NBI según metodología INDEC. Densidad calculada como personas/km².', en: 'Source: INDEC National Population Census 2022. Variables at radio censal level (2,012 radios). UBN per INDEC methodology.' },
	},
	forest_potential: {
		id: 'forest_potential',
		choroplethCol: 'canopy_cover',
		colorScale: 'sequential',
		petalCols: [
			{ col: 'canopy_cover', label: { es: 'Cobertura dosel', en: 'Canopy cover' }, desc: { es: 'Fracción de suelo cubierto por dosel arbóreo', en: 'Fraction of ground covered by tree canopy' }, invert: false },
			{ col: 'canopy_height_mean', label: { es: 'Altura dosel', en: 'Canopy height' }, desc: { es: 'Altura media del dosel en metros (GEDI)', en: 'Mean canopy height in meters (GEDI)' }, invert: false },
			{ col: 'ndvi_mean', label: { es: 'NDVI', en: 'NDVI' }, desc: { es: 'Índice de vegetación (0-1, mayor = más verde)', en: 'Vegetation index (0-1, higher = greener)' }, invert: false },
			{ col: 'frac_bosque_nativo', label: { es: 'Bosque nativo', en: 'Native forest' }, desc: { es: 'Fracción de bosque nativo remanente', en: 'Remaining native forest fraction' }, invert: false },
			{ col: 'treecover2000', label: { es: 'Cobertura 2000', en: 'Treecover 2000' }, desc: { es: '% de cobertura arbórea en el año 2000 (Hansen)', en: '% tree cover in year 2000 (Hansen)' }, invert: false },
		],
		howToRead: { es: 'Las parcelas se colorean según la cobertura de dosel arbóreo. Verde más intenso = mayor cobertura. El pétalo muestra 5 métricas de vegetación: cobertura, altura, verdor, bosque nativo y cobertura histórica.', en: 'Parcels are coloured by canopy cover. Greener = more cover. The petal shows 5 vegetation metrics.' },
		implications: { es: 'Alta cobertura de dosel + bosque nativo alto indica zonas de conservación prioritaria. Baja cobertura con alto treecover2000 sugiere deforestación reciente. NDVI alto con baja altura de dosel puede indicar plantaciones vs bosque nativo.', en: 'High canopy cover + native forest indicates priority conservation areas.' },
		methodology: { es: 'Cobertura de dosel: Meta/WRI Canopy Height v2 (1m agregado a 10m). NDVI: MODIS 250m promedio 2019-2024. Bosque nativo: MapBiomas Argentina. Cobertura histórica: Hansen GFC baseline 2000.', en: 'Canopy cover: Meta/WRI CHM v2. NDVI: MODIS 250m mean 2019-2024. Native forest: MapBiomas. Historical cover: Hansen GFC 2000.' },
	},
	economic_activity: {
		id: 'economic_activity',
		choroplethCol: 'tasa_empleo',
		colorScale: 'sequential',
		petalCols: [
			{ col: 'tasa_empleo', label: { es: 'Empleo', en: 'Employment' }, desc: { es: 'Tasa de empleo (% población ocupada)', en: 'Employment rate (% employed population)' }, invert: false },
			{ col: 'tasa_actividad', label: { es: 'Actividad', en: 'Activity' }, desc: { es: 'Tasa de actividad económica', en: 'Economic activity rate' }, invert: false },
			{ col: 'pct_universitario', label: { es: 'Universitarios', en: 'University' }, desc: { es: '% población con título universitario', en: '% population with university degree' }, invert: false },
			{ col: 'viirs_mean_radiance', label: { es: 'Luces nocturnas', en: 'Night lights' }, desc: { es: 'Radiancia media nocturna (proxy actividad económica)', en: 'Mean night-time radiance (economic activity proxy)' }, invert: false },
			{ col: 'building_density_per_km2', label: { es: 'Densidad edilicia', en: 'Building density' }, desc: { es: 'Edificios por km²', en: 'Buildings per km²' }, invert: false },
		],
		howToRead: { es: 'Las parcelas se colorean según la tasa de empleo. Verde más intenso = mayor empleo. El pétalo combina empleo, actividad económica, formación universitaria, luces nocturnas y densidad edilicia como indicadores de dinamismo.', en: 'Parcels are coloured by employment rate. Greener = higher employment.' },
		implications: { es: 'Zonas con alta tasa de empleo + universitarios + luces nocturnas son centros económicos consolidados. Zonas con alta actividad pero bajo empleo pueden tener alta informalidad. Baja radiancia nocturna indica zonas rurales o de baja actividad.', en: 'High employment + university + night lights indicate consolidated economic centres.' },
		methodology: { es: 'Empleo y actividad: Censo 2022 INDEC (población 14+ años). Universitarios: Censo 2022. Luces nocturnas: VIIRS 500m promedio 2022-2024. Densidad edilicia: Global Building Atlas 2025.', en: 'Employment and activity: INDEC Census 2022 (14+ population). Night lights: VIIRS 500m mean 2022-2024. Building density: GBA 2025.' },
	},
};

export function getAnalysesForLens(lensId: LensId): AnalysisConfig[] {
	return ANALYSIS_REGISTRY.filter(a => a.lensId === lensId);
}


export function getAnalysisById(id: string): AnalysisConfig | undefined {
	return ANALYSIS_REGISTRY.find(a => a.id === id);
}

// ── Data freshness metadata ─────────────────────────────────────────────────

export const DATA_FRESHNESS: Record<string, { dataDate: string; processedDate: string; sourceKey: string }> = {
	hex_flood_risk: {
		dataDate: 'marzo 2026',
		processedDate: '21/03/2026',
		sourceKey: 'analysis.flood.source',
	},
	censo_radios: {
		dataDate: 'Censo 2022',
		processedDate: '21/03/2026',
		sourceKey: 'data.source.censo',
	},
	real_estate: {
		dataDate: '01/2025',
		processedDate: '21/03/2026',
		sourceKey: 'data.source.realEstate',
	},
	catastro_by_radio: {
		dataDate: 'marzo 2026',
		processedDate: '22/03/2026',
		sourceKey: 'data.source.catastro',
	},
	buildings_stats: {
		dataDate: '02/2025',
		processedDate: '21/03/2026',
		sourceKey: 'data.source.buildings',
	},
	overture_buildings: {
		dataDate: 'Overture 2026-03-18',
		processedDate: '24/03/2026',
		sourceKey: 'data.source.overture',
	},
	overture_transportation: {
		dataDate: 'Overture 2026-03-18',
		processedDate: '24/03/2026',
		sourceKey: 'data.source.overture',
	},
	overture_places: {
		dataDate: 'Overture 2026-03-18',
		processedDate: '24/03/2026',
		sourceKey: 'data.source.overture',
	},
	overture_base: {
		dataDate: 'Overture 2026-03-18',
		processedDate: '24/03/2026',
		sourceKey: 'data.source.overture',
	},
	overture_scores: {
		dataDate: 'Overture 2026-03-18',
		processedDate: '25/03/2026',
		sourceKey: 'data.source.overture',
	},
	sat_environmental_risk: { dataDate: 'Baseline MODIS/Hansen/ERA5 2019-2024', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_climate_comfort: { dataDate: 'Baseline MODIS/CHIRPS/ERA5 2019-2024', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_green_capital: { dataDate: 'Baseline MODIS/Hansen/VCF 2019-2024', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_change_pressure: { dataDate: 'Baseline VIIRS/GHSL/Hansen 2000-2025', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_location_value: { dataDate: 'Baseline Nelson 2019 / Oxford 2019 / VIIRS 2022-2024', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_agri_potential: { dataDate: 'Baseline SoilGrids / CHIRPS / ERA5 2019-2024', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_forest_health: { dataDate: 'Baseline MODIS/Hansen 2019-2024', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_forestry_aptitude: { dataDate: 'Baseline SoilGrids / CHIRPS / Nelson 2019', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_isolation_index: { dataDate: 'Baseline Nelson 2019 / Oxford 2019 / VIIRS 2022-2024', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_territorial_gap: { dataDate: 'Baseline VIIRS 2022-2024 / Censo 2022 / Nelson 2019', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_health_access: { dataDate: 'Baseline Oxford MAP 2019 + Censo 2022', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_education_gap: { dataDate: 'Baseline Censo 2022 + Nelson 2019', processedDate: '26/03/2026', sourceKey: 'data.source.satellite' },
	sat_land_use: { dataDate: 'MapBiomas Argentina Collection 1 (Landsat 30m, 2022)', processedDate: '29/03/2026', sourceKey: 'data.source.satellite' },
	emsa_powerlines: { dataDate: 'EMSA abril 2024', processedDate: '27/03/2026', sourceKey: 'data.source.emsa' },
	sat_territorial_types: { dataDate: 'PCA + k-means sobre 13 analisis satelitales 2019-2024', processedDate: '28/03/2026', sourceKey: 'data.source.satellite' },
	sat_sociodemographic: { dataDate: 'Censo Nacional 2022 (INDEC)', processedDate: '29/03/2026', sourceKey: 'data.source.censo' },
	sat_economic_activity: { dataDate: 'Censo 2022 + VIIRS 2022-2024 + GBA 2025', processedDate: '29/03/2026', sourceKey: 'data.source.satellite' },
	sat_accessibility: { dataDate: 'Nelson 2019 / Oxford MAP 2019 / OSM', processedDate: '29/03/2026', sourceKey: 'data.source.satellite' },
	eudr_deforestation: { dataDate: 'Hansen GFC v1.12 + MODIS MCD64A1 (cutoff 31/12/2020)', processedDate: '27/03/2026', sourceKey: 'data.source.satellite' },
};

// ── EUDR Configuration ──────────────────────────────────────────────────
export const MAP_EUDR = {
	center: [-62.5, -26.5] as [number, number],
	zoom: 5.5,
	minZoom: 4,
	maxZoom: 14,
};

const R2_EUDR_BASE = `${R2_PROD}/data/eudr`;

export function getEudrParquetUrl(name: string): string {
	return `${R2_EUDR_BASE}/${name}.parquet?v=20`;
}

export function getEudrProvinceParquetUrl(province: string): string {
	return `${R2_EUDR_BASE}/by_province/eudr_${province}.parquet?v=20`;
}

export const EUDR_RISK_COLORS = {
	low: '#22c55e',
	medium: '#f59e0b',
	high: '#ef4444',
	critical: '#991b1b',
	unknown: '#6b7280',
};
