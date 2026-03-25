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
	const bust = name === 'hex_flood_risk' ? '?v=3' : '';
	return `${getBase()}/data/${name}.parquet${bust}`;
}

export function getFloodDptoUrl(parquetKey: string): string {
	return `${getBase()}/data/flood_dpto/hex_flood_${parquetKey}.parquet`;
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
};

export const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

export const MAP_INIT = {
	center: [-54.4, -27.0] as [number, number],
	zoom: 7.5,
	pitch: 30,
	bearing: -15,
	minZoom: 6,
	maxZoom: 18
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

export interface HexLayerConfig {
	id: string;
	parquet: string;
	variables: HexVariable[];
	primaryVariable: string;
	colorScale: 'flood' | 'sequential' | 'diverging';
	aggregation: 'mean' | 'sum' | 'max';
	petalVars?: HexVariable[];
	titleKey: string;
	perDepartment?: boolean;
}

export const HEX_LAYER_REGISTRY: Record<string, HexLayerConfig> = {
	flood_risk: {
		id: 'flood_risk',
		parquet: 'hex_flood_risk',
		variables: [
			{ col: 'flood_risk_score', labelKey: 'analysis.flood.riskScore', aggregation: 'mean' },
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
	// ── Overture: Invertir ──
	building_density: {
		id: 'building_density',
		parquet: 'overture_buildings',
		variables: [
			{ col: 'building_count', labelKey: 'ov.buildingCount', aggregation: 'sum' },
			{ col: 'n_residential', labelKey: 'ov.nResidential', aggregation: 'sum' },
			{ col: 'n_commercial', labelKey: 'ov.nCommercial', aggregation: 'sum' },
			{ col: 'avg_height_m', labelKey: 'ov.avgHeight', aggregation: 'mean' },
			{ col: 'avg_floors', labelKey: 'ov.avgFloors', aggregation: 'mean' },
		],
		primaryVariable: 'building_count',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.buildingDensity.title',
		perDepartment: false,
	},
	land_use_mix: {
		id: 'land_use_mix',
		parquet: 'overture_base',
		variables: [
			{ col: 'landuse_count', labelKey: 'ov.landuseCount', aggregation: 'sum' },
			{ col: 'n_lu_residential', labelKey: 'ov.luResidential', aggregation: 'sum' },
			{ col: 'n_lu_agriculture', labelKey: 'ov.luAgriculture', aggregation: 'sum' },
			{ col: 'n_lu_developed', labelKey: 'ov.luDeveloped', aggregation: 'sum' },
			{ col: 'n_lu_recreation', labelKey: 'ov.luRecreation', aggregation: 'sum' },
		],
		primaryVariable: 'landuse_count',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.landUseMix.title',
		perDepartment: false,
	},
	infra_coverage: {
		id: 'infra_coverage',
		parquet: 'overture_base',
		variables: [
			{ col: 'infra_count', labelKey: 'ov.infraCount', aggregation: 'sum' },
			{ col: 'n_power', labelKey: 'ov.infraPower', aggregation: 'sum' },
			{ col: 'n_water_infra', labelKey: 'ov.infraWater', aggregation: 'sum' },
			{ col: 'n_communication', labelKey: 'ov.infraComm', aggregation: 'sum' },
			{ col: 'n_transportation', labelKey: 'ov.infraTransport', aggregation: 'sum' },
		],
		primaryVariable: 'infra_count',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.infraCoverage.title',
		perDepartment: false,
	},
	// ── Overture: Producir ──
	road_network: {
		id: 'road_network',
		parquet: 'overture_transportation',
		variables: [
			{ col: 'segment_count', labelKey: 'ov.segmentCount', aggregation: 'sum' },
			{ col: 'n_primary', labelKey: 'ov.roadPrimary', aggregation: 'sum' },
			{ col: 'n_secondary', labelKey: 'ov.roadSecondary', aggregation: 'sum' },
			{ col: 'n_tertiary', labelKey: 'ov.roadTertiary', aggregation: 'sum' },
			{ col: 'n_paved', labelKey: 'ov.roadPaved', aggregation: 'sum' },
			{ col: 'n_unpaved', labelKey: 'ov.roadUnpaved', aggregation: 'sum' },
		],
		primaryVariable: 'segment_count',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.roadNetwork.title',
		perDepartment: false,
	},
	agricultural_land: {
		id: 'agricultural_land',
		parquet: 'overture_base',
		variables: [
			{ col: 'n_lu_agriculture', labelKey: 'ov.luAgriculture', aggregation: 'sum' },
			{ col: 'n_lu_horticulture', labelKey: 'ov.luHorticulture', aggregation: 'sum' },
			{ col: 'n_lu_managed', labelKey: 'ov.luManaged', aggregation: 'sum' },
		],
		primaryVariable: 'n_lu_agriculture',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.agriculturalLand.title',
		perDepartment: false,
	},
	industrial_footprint: {
		id: 'industrial_footprint',
		parquet: 'overture_buildings',
		variables: [
			{ col: 'n_industrial', labelKey: 'ov.bldgIndustrial', aggregation: 'sum' },
			{ col: 'n_warehouse', labelKey: 'ov.bldgWarehouse', aggregation: 'sum' },
			{ col: 'n_factory', labelKey: 'ov.bldgFactory', aggregation: 'sum' },
			{ col: 'n_agricultural', labelKey: 'ov.bldgAgricultural', aggregation: 'sum' },
		],
		primaryVariable: 'n_industrial',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.industrialFootprint.title',
		perDepartment: false,
	},
	// ── Overture: Servir ──
	health_education: {
		id: 'health_education',
		parquet: 'overture_places',
		variables: [
			{ col: 'n_health_care', labelKey: 'ov.poiHealthCare', aggregation: 'sum' },
			{ col: 'n_education', labelKey: 'ov.poiEducation', aggregation: 'sum' },
			{ col: 'n_hospital', labelKey: 'ov.poiHospital', aggregation: 'sum' },
			{ col: 'n_school', labelKey: 'ov.poiSchool', aggregation: 'sum' },
		],
		primaryVariable: 'n_health_care',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.healthEducation.title',
		perDepartment: false,
	},
	community_services: {
		id: 'community_services',
		parquet: 'overture_places',
		variables: [
			{ col: 'n_community_and_government', labelKey: 'ov.poiCommunity', aggregation: 'sum' },
			{ col: 'n_services_and_business', labelKey: 'ov.poiServices', aggregation: 'sum' },
		],
		primaryVariable: 'n_community_and_government',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.communityServices.title',
		perDepartment: false,
	},
	emergency_infra: {
		id: 'emergency_infra',
		parquet: 'overture_base',
		variables: [
			{ col: 'n_emergency', labelKey: 'ov.infraEmergency', aggregation: 'sum' },
			{ col: 'n_barrier', labelKey: 'ov.infraBarrier', aggregation: 'sum' },
		],
		primaryVariable: 'n_emergency',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.emergencyInfra.title',
		perDepartment: false,
	},
	// ── Overture: Vivir ──
	urban_amenities: {
		id: 'urban_amenities',
		parquet: 'overture_places',
		variables: [
			{ col: 'place_count', labelKey: 'ov.placeCount', aggregation: 'sum' },
			{ col: 'n_food_and_drink', labelKey: 'ov.poiFoodDrink', aggregation: 'sum' },
			{ col: 'n_shopping', labelKey: 'ov.poiShopping', aggregation: 'sum' },
			{ col: 'n_arts_and_entertainment', labelKey: 'ov.poiArts', aggregation: 'sum' },
			{ col: 'n_sports_and_recreation', labelKey: 'ov.poiSports', aggregation: 'sum' },
		],
		primaryVariable: 'place_count',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.urbanAmenities.title',
		perDepartment: false,
	},
	green_water: {
		id: 'green_water',
		parquet: 'overture_base',
		variables: [
			{ col: 'n_lu_park', labelKey: 'ov.luPark', aggregation: 'sum' },
			{ col: 'n_lu_recreation', labelKey: 'ov.luRecreation', aggregation: 'sum' },
			{ col: 'water_count', labelKey: 'ov.waterCount', aggregation: 'sum' },
			{ col: 'n_river', labelKey: 'ov.waterRiver', aggregation: 'sum' },
			{ col: 'n_lake', labelKey: 'ov.waterLake', aggregation: 'sum' },
		],
		primaryVariable: 'water_count',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.greenWater.title',
		perDepartment: false,
	},
	walkability: {
		id: 'walkability',
		parquet: 'overture_transportation',
		variables: [
			{ col: 'n_pedestrian', labelKey: 'ov.roadPedestrian', aggregation: 'sum' },
			{ col: 'n_footway', labelKey: 'ov.roadFootway', aggregation: 'sum' },
			{ col: 'n_cycleway', labelKey: 'ov.roadCycleway', aggregation: 'sum' },
			{ col: 'n_living_street', labelKey: 'ov.roadLivingStreet', aggregation: 'sum' },
			{ col: 'n_steps', labelKey: 'ov.roadSteps', aggregation: 'sum' },
		],
		primaryVariable: 'n_pedestrian',
		colorScale: 'sequential',
		aggregation: 'sum',
		titleKey: 'analysis.walkability.title',
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
		icon: '🌊',
		status: 'available',
		spatialUnit: 'catastro',
	},
	{
		id: 'catastro',
		lensId: 'vivir',
		titleKey: 'analysis.catastro.title',
		descKey: 'analysis.catastro.desc',
		icon: '📐',
		status: 'available',
		spatialUnit: 'radio',
		choropleth: {
			parquet: 'catastro_by_radio',
			column: '(n_parcelas_urbano + n_parcelas_rural)',
			colorScale: 'sequential',
			legendKey: 'analysis.catastro.legend',
		},
	},
	// ── Invertir (Overture) ──
	{
		id: 'building_density',
		lensId: 'invertir',
		titleKey: 'analysis.buildingDensity.title',
		descKey: 'analysis.buildingDensity.desc',
		icon: '🏗️',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'land_use_mix',
		lensId: 'invertir',
		titleKey: 'analysis.landUseMix.title',
		descKey: 'analysis.landUseMix.desc',
		icon: '🗺️',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'infra_coverage',
		lensId: 'invertir',
		titleKey: 'analysis.infraCoverage.title',
		descKey: 'analysis.infraCoverage.desc',
		icon: '⚡',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	// ── Producir (Overture) ──
	{
		id: 'road_network',
		lensId: 'producir',
		titleKey: 'analysis.roadNetwork.title',
		descKey: 'analysis.roadNetwork.desc',
		icon: '🛣️',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'agricultural_land',
		lensId: 'producir',
		titleKey: 'analysis.agriculturalLand.title',
		descKey: 'analysis.agriculturalLand.desc',
		icon: '🌾',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'industrial_footprint',
		lensId: 'producir',
		titleKey: 'analysis.industrialFootprint.title',
		descKey: 'analysis.industrialFootprint.desc',
		icon: '🏭',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	// ── Servir (Overture) ──
	{
		id: 'health_education',
		lensId: 'servir',
		titleKey: 'analysis.healthEducation.title',
		descKey: 'analysis.healthEducation.desc',
		icon: '🏥',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'community_services',
		lensId: 'servir',
		titleKey: 'analysis.communityServices.title',
		descKey: 'analysis.communityServices.desc',
		icon: '🏛️',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'emergency_infra',
		lensId: 'servir',
		titleKey: 'analysis.emergencyInfra.title',
		descKey: 'analysis.emergencyInfra.desc',
		icon: '🚨',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	// ── Vivir (Overture) ──
	{
		id: 'urban_amenities',
		lensId: 'vivir',
		titleKey: 'analysis.urbanAmenities.title',
		descKey: 'analysis.urbanAmenities.desc',
		icon: '🍽️',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'green_water',
		lensId: 'vivir',
		titleKey: 'analysis.greenWater.title',
		descKey: 'analysis.greenWater.desc',
		icon: '🌳',
		status: 'available',
		spatialUnit: 'hexagon',
	},
	{
		id: 'walkability',
		lensId: 'vivir',
		titleKey: 'analysis.walkability.title',
		descKey: 'analysis.walkability.desc',
		icon: '🚶',
		status: 'available',
		spatialUnit: 'hexagon',
	},
];

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
};
