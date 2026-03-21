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
		id: 'territorial_profile_inv',
		lensId: 'invertir',
		titleKey: 'analysis.territorialProfile.title',
		descKey: 'analysis.territorialProfile.desc',
		icon: '🌸',
		status: 'available',
	},

	// ── Producir ──
	{
		id: 'territorial_profile_prod',
		lensId: 'producir',
		titleKey: 'analysis.territorialProfile.title',
		descKey: 'analysis.territorialProfile.desc',
		icon: '🌸',
		status: 'available',
	},

	// ── Servir ──
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
	buildings_stats: {
		dataDate: '02/2025',
		processedDate: '21/03/2026',
		sourceKey: 'data.source.buildings',
	},
};
