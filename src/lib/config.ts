const R2_PROD = 'https://pub-580c676bec7f4eeb96d7d30559a3cab7.r2.dev';

function getBase(): string {
	return R2_PROD;
}

export function getTilesUrl(name: 'buildings' | 'radios' | 'radios-chm' | 'terrain' | 'hexagons'): string {
	if (name === 'terrain') {
		return '/api/terrain/{z}/{x}/{y}.png';
	}
	const files = {
		buildings: 'tiles/buildings-v4.pmtiles',
		radios: 'tiles/radios-v2.pmtiles',
		'radios-chm': 'tiles/radios-chm.pmtiles',
		hexagons: 'tiles/hexagons-v2.pmtiles'
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
	return `${getBase()}/data/${name}.parquet`;
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
	get h3_parent_crosswalk() { return getParquetUrl('h3_parent_crosswalk'); }
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
	icon: string;
	color: string;
	scoreCol: string;
	subCols: [string, string, string, string, string, string];
	subLabelKeys: [string, string, string, string, string, string];
	threshold: number;
}

export const LENS_CONFIG: Record<LensId, LensConfig> = {
	invertir: {
		label: { es: 'Invertir', en: 'Invest', gn: 'Moĩ viru' },
		icon: '',
		color: '#f59e0b',
		scoreCol: 'inv_score',
		subCols: ['inv_sub1', 'inv_sub2', 'inv_sub3', 'inv_sub4', 'inv_sub5', 'inv_sub6'],
		subLabelKeys: ['lens.inv.s1', 'lens.inv.s2', 'lens.inv.s3', 'lens.inv.s4', 'lens.inv.s5', 'lens.inv.s6'],
		threshold: 70,
	},
	producir: {
		label: { es: 'Producir', en: 'Produce', gn: 'Mba\'apo' },
		icon: '',
		color: '#22c55e',
		scoreCol: 'prod_score',
		subCols: ['prod_sub1', 'prod_sub2', 'prod_sub3', 'prod_sub4', 'prod_sub5', 'prod_sub6'],
		subLabelKeys: ['lens.prod.s1', 'lens.prod.s2', 'lens.prod.s3', 'lens.prod.s4', 'lens.prod.s5', 'lens.prod.s6'],
		threshold: 70,
	},
	servir: {
		label: { es: 'Servir', en: 'Serve', gn: 'Pytyvõ' },
		icon: '',
		color: '#3b82f6',
		scoreCol: 'serv_score',
		subCols: ['serv_sub1', 'serv_sub2', 'serv_sub3', 'serv_sub4', 'serv_sub5', 'serv_sub6'],
		subLabelKeys: ['lens.serv.s1', 'lens.serv.s2', 'lens.serv.s3', 'lens.serv.s4', 'lens.serv.s5', 'lens.serv.s6'],
		threshold: 70,
	},
	vivir: {
		label: { es: 'Vivir', en: 'Live', gn: 'Ñemity' },
		icon: '',
		color: '#06b6d4',
		scoreCol: 'viv_score',
		subCols: ['viv_sub1', 'viv_sub2', 'viv_sub3', 'viv_sub4', 'viv_sub5', 'viv_sub6'],
		subLabelKeys: ['lens.viv.s1', 'lens.viv.s2', 'lens.viv.s3', 'lens.viv.s4', 'lens.viv.s5', 'lens.viv.s6'],
		threshold: 70,
	},
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
}

export const HEX_LAYER_REGISTRY: Record<string, HexLayerConfig> = {
	flood_risk: {
		id: 'flood_risk',
		parquet: 'hex_flood_risk',
		variables: [
			{ col: 'flood_risk_score', labelKey: 'analysis.flood.riskScore', aggregation: 'mean' },
			{ col: 'flood_recurrence_mean', labelKey: 'analysis.flood.recurrence', aggregation: 'mean' },
			{ col: 'flood_extent_pct', labelKey: 'analysis.flood.currentExtent', aggregation: 'mean' },
		],
		primaryVariable: 'flood_risk_score',
		colorScale: 'flood',
		aggregation: 'mean',
		petalVars: [
			{ col: 'flood_risk_score', labelKey: 'analysis.flood.riskScore', aggregation: 'mean' },
			{ col: 'flood_recurrence_mean', labelKey: 'analysis.flood.recurrence', aggregation: 'mean' },
			{ col: 'flood_extent_pct', labelKey: 'analysis.flood.currentExtent', aggregation: 'mean' },
		],
		titleKey: 'analysis.floodRisk.title',
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
	spatialUnit?: 'radio' | 'hexagon';
	choropleth?: {
		parquet: string;
		column: string;
		colorScale: 'price' | 'score' | 'diverging' | 'sequential' | 'flood';
		legendKey: string;
	};
}

export const ANALYSIS_REGISTRY: AnalysisConfig[] = [
	// ── Invertir ──
	{
		id: 'real_estate',
		lensId: 'invertir',
		titleKey: 'analysis.realEstate.title',
		descKey: 'analysis.realEstate.desc',
		icon: '🏠',
		status: 'available',
		choropleth: {
			parquet: 'real_estate_by_radio',
			column: 'median_usd_m2',
			colorScale: 'price',
			legendKey: 'analysis.realEstate.legend',
		},
	},
	{
		id: 'building_suitability',
		lensId: 'invertir',
		titleKey: 'analysis.buildingSuitability.title',
		descKey: 'analysis.buildingSuitability.desc',
		icon: '🏗️',
		status: 'coming_soon',
	},
	{
		id: 'territorial_profile_inv',
		lensId: 'invertir',
		titleKey: 'analysis.territorialProfile.title',
		descKey: 'analysis.territorialProfile.desc',
		icon: '🌸',
		status: 'available',
	},
	{
		id: 'building_permits',
		lensId: 'invertir',
		titleKey: 'analysis.buildingPermits.title',
		descKey: 'analysis.buildingPermits.desc',
		icon: '📋',
		status: 'coming_soon',
	},
	{
		id: 'vehicle_registrations',
		lensId: 'invertir',
		titleKey: 'analysis.vehicleRegistrations.title',
		descKey: 'analysis.vehicleRegistrations.desc',
		icon: '🚗',
		status: 'coming_soon',
	},
	{
		id: 'mortgage_credit',
		lensId: 'invertir',
		titleKey: 'analysis.mortgageCredit.title',
		descKey: 'analysis.mortgageCredit.desc',
		icon: '🏦',
		status: 'coming_soon',
	},

	// ── Producir ──
	{
		id: 'crop_production',
		lensId: 'producir',
		titleKey: 'analysis.cropProduction.title',
		descKey: 'analysis.cropProduction.desc',
		icon: '🌾',
		status: 'coming_soon',
	},
	{
		id: 'soil_suitability',
		lensId: 'producir',
		titleKey: 'analysis.soilSuitability.title',
		descKey: 'analysis.soilSuitability.desc',
		icon: '🧪',
		status: 'coming_soon',
	},
	{
		id: 'crop_suitability',
		lensId: 'producir',
		titleKey: 'analysis.cropSuitability.title',
		descKey: 'analysis.cropSuitability.desc',
		icon: '🌱',
		status: 'coming_soon',
	},
	{
		id: 'forestry',
		lensId: 'producir',
		titleKey: 'analysis.forestry.title',
		descKey: 'analysis.forestry.desc',
		icon: '🌲',
		status: 'coming_soon',
	},
	{
		id: 'territorial_profile_prod',
		lensId: 'producir',
		titleKey: 'analysis.territorialProfile.title',
		descKey: 'analysis.territorialProfile.desc',
		icon: '🌸',
		status: 'available',
	},
	{
		id: 'commodity_prices',
		lensId: 'producir',
		titleKey: 'analysis.commodityPrices.title',
		descKey: 'analysis.commodityPrices.desc',
		icon: '📈',
		status: 'coming_soon',
	},

	// ── Servir ──
	{
		id: 'health_coverage',
		lensId: 'servir',
		titleKey: 'analysis.healthCoverage.title',
		descKey: 'analysis.healthCoverage.desc',
		icon: '🏥',
		status: 'coming_soon',
	},
	{
		id: 'education_coverage',
		lensId: 'servir',
		titleKey: 'analysis.educationCoverage.title',
		descKey: 'analysis.educationCoverage.desc',
		icon: '🎓',
		status: 'coming_soon',
	},
	{
		id: 'social_vulnerability',
		lensId: 'servir',
		titleKey: 'analysis.socialVulnerability.title',
		descKey: 'analysis.socialVulnerability.desc',
		icon: '🛡️',
		status: 'coming_soon',
	},
	{
		id: 'water_network',
		lensId: 'servir',
		titleKey: 'analysis.waterNetwork.title',
		descKey: 'analysis.waterNetwork.desc',
		icon: '💧',
		status: 'coming_soon',
	},
	{
		id: 'territorial_profile_serv',
		lensId: 'servir',
		titleKey: 'analysis.territorialProfile.title',
		descKey: 'analysis.territorialProfile.desc',
		icon: '🌸',
		status: 'available',
	},

	// ── Vivir ──
	{
		id: 'environment',
		lensId: 'vivir',
		titleKey: 'analysis.environment.title',
		descKey: 'analysis.environment.desc',
		icon: '🌿',
		status: 'coming_soon',
	},
	{
		id: 'flood_risk',
		lensId: 'vivir',
		titleKey: 'analysis.floodRisk.title',
		descKey: 'analysis.floodRisk.desc',
		icon: '🌊',
		status: 'available',
		spatialUnit: 'hexagon',
		choropleth: {
			parquet: 'hex_flood_risk',
			column: 'flood_risk_score',
			colorScale: 'flood',
			legendKey: 'analysis.floodRisk.legend',
		},
	},
	{
		id: 'natural_risks',
		lensId: 'vivir',
		titleKey: 'analysis.naturalRisks.title',
		descKey: 'analysis.naturalRisks.desc',
		icon: '⚠️',
		status: 'coming_soon',
	},
	{
		id: 'transport',
		lensId: 'vivir',
		titleKey: 'analysis.transport.title',
		descKey: 'analysis.transport.desc',
		icon: '🚌',
		status: 'coming_soon',
	},
	{
		id: 'digital_connectivity',
		lensId: 'vivir',
		titleKey: 'analysis.digitalConnectivity.title',
		descKey: 'analysis.digitalConnectivity.desc',
		icon: '📡',
		status: 'coming_soon',
	},
	{
		id: 'territorial_profile_viv',
		lensId: 'vivir',
		titleKey: 'analysis.territorialProfile.title',
		descKey: 'analysis.territorialProfile.desc',
		icon: '🌸',
		status: 'available',
	},
];

export function getAnalysesForLens(lensId: LensId): AnalysisConfig[] {
	return ANALYSIS_REGISTRY.filter(a => a.lensId === lensId);
}

export function getAnalysisById(id: string): AnalysisConfig | undefined {
	return ANALYSIS_REGISTRY.find(a => a.id === id);
}
