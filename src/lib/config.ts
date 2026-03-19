const R2_PROD = 'https://pub-580c676bec7f4eeb96d7d30559a3cab7.r2.dev';

function getBase(): string {
	return R2_PROD;
}

export function getTilesUrl(name: 'buildings' | 'radios'): string {
	const files = { buildings: 'tiles/buildings-v4.pmtiles', radios: 'tiles/radios-v2.pmtiles' };
	return `pmtiles://${getBase()}/${files[name]}`;
}

export function getParquetUrl(name: string): string {
	return `${getBase()}/data/${name}.parquet`;
}

export const PARQUETS = {
	get censo_radios() { return getParquetUrl('censo_radios'); },
	get censo_departamentos() { return getParquetUrl('censo_departamentos'); },
	get magyp_estimaciones() { return getParquetUrl('magyp_estimaciones'); },
	get ndvi_annual() { return getParquetUrl('ndvi_annual'); },
	get buildings_stats() { return getParquetUrl('buildings_stats'); },
	get radio_stats_master() { return getParquetUrl('radio_stats_master'); }
};

export const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

export const MAP_INIT = {
	center: [-54.4, -27.0] as [number, number],
	zoom: 7.5,
	pitch: 31,
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
		icon: '📈',
		color: '#f59e0b',
		scoreCol: 'inv_score',
		subCols: ['inv_sub1', 'inv_sub2', 'inv_sub3', 'inv_sub4', 'inv_sub5', 'inv_sub6'],
		subLabelKeys: ['lens.inv.s1', 'lens.inv.s2', 'lens.inv.s3', 'lens.inv.s4', 'lens.inv.s5', 'lens.inv.s6'],
		threshold: 70,
	},
	producir: {
		label: { es: 'Producir', en: 'Produce', gn: 'Mba\'apo' },
		icon: '🌱',
		color: '#22c55e',
		scoreCol: 'prod_score',
		subCols: ['prod_sub1', 'prod_sub2', 'prod_sub3', 'prod_sub4', 'prod_sub5', 'prod_sub6'],
		subLabelKeys: ['lens.prod.s1', 'lens.prod.s2', 'lens.prod.s3', 'lens.prod.s4', 'lens.prod.s5', 'lens.prod.s6'],
		threshold: 70,
	},
	servir: {
		label: { es: 'Servir', en: 'Serve', gn: 'Pytyvõ' },
		icon: '🏥',
		color: '#3b82f6',
		scoreCol: 'serv_score',
		subCols: ['serv_sub1', 'serv_sub2', 'serv_sub3', 'serv_sub4', 'serv_sub5', 'serv_sub6'],
		subLabelKeys: ['lens.serv.s1', 'lens.serv.s2', 'lens.serv.s3', 'lens.serv.s4', 'lens.serv.s5', 'lens.serv.s6'],
		threshold: 70,
	},
	vivir: {
		label: { es: 'Vivir', en: 'Live', gn: 'Ñemity' },
		icon: '🏡',
		color: '#06b6d4',
		scoreCol: 'viv_score',
		subCols: ['viv_sub1', 'viv_sub2', 'viv_sub3', 'viv_sub4', 'viv_sub5', 'viv_sub6'],
		subLabelKeys: ['lens.viv.s1', 'lens.viv.s2', 'lens.viv.s3', 'lens.viv.s4', 'lens.viv.s5', 'lens.viv.s6'],
		threshold: 70,
	},
} as const;
