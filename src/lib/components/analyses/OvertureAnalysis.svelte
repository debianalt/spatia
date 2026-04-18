<script lang="ts">
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import CTADiagnostic from '$lib/components/CTADiagnostic.svelte';
	import PetalChart from '$lib/components/PetalChart.svelte';
	import TemporalToggle from '$lib/components/TemporalToggle.svelte';
	import { HEX_LAYER_REGISTRY, DATA_FRESHNESS, getSatDptoUrl, getFloodDptoUrl, getScoresDptoUrl, getReportUrl, getTemporalCol, getDeptSummaryUrl, type AnalysisConfig, type TemporalMode } from '$lib/config';
	import { query } from '$lib/stores/duckdb';
	import { downloadCsvFromQuery, downloadGeoJsonFromHexQuery } from '$lib/utils/data-export';
	import { ANALYSIS_CONTENT } from '$lib/content/methodology';

	let {
		analysis,
		hexStore,
		onSelectDpto,
	}: {
		analysis: AnalysisConfig;
		hexStore: HexStore;
		onSelectDpto?: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
	} = $props();

	const layerCfg = $derived(HEX_LAYER_REGISTRY[analysis.id]);
	const freshness = $derived(layerCfg ? DATA_FRESHNESS[layerCfg.parquet] : null);
	const loading = $derived(hexStore.loading);
	const selectedHexes = $derived(hexStore.selectedHexes);
	const isPerDept = $derived(layerCfg?.perDepartment === true);
	const selectedDpto = $derived(hexStore.selectedDpto);
	const selectedHex = $derived.by(() => {
		if (selectedHexes.size === 0) return null;
		const [h3index, sel] = [...selectedHexes.entries()][0];
		return { h3index, ...sel.data };
	});

	// Census-based analyses: hide petals (radio-level data → identical within radio, not informative)
	const CENSUS_ANALYSES = new Set(['service_deprivation', 'health_access', 'education_capital', 'education_flow', 'economic_activity', 'accessibility', 'carbon_stock']);

	// Department summaries for perDepartment layers
	let deptSummary = $state<any>(null);

	const SAT_SUMMARIES: Record<string, () => Promise<any>> = {
		environmental_risk: () => import('$lib/data/sat_environmental_risk_dept_summary.json'),
		climate_comfort: () => import('$lib/data/sat_climate_comfort_dept_summary.json'),
		green_capital: () => import('$lib/data/sat_green_capital_dept_summary.json'),
		change_pressure: () => import('$lib/data/sat_change_pressure_dept_summary.json'),
		location_value: () => import('$lib/data/sat_location_value_dept_summary.json'),
		agri_potential: () => import('$lib/data/sat_agri_potential_dept_summary.json'),
		forest_health: () => import('$lib/data/sat_forest_health_dept_summary.json'),
		forestry_aptitude: () => import('$lib/data/sat_forestry_aptitude_dept_summary.json'),
		service_deprivation: () => import('$lib/data/sat_service_deprivation_dept_summary.json'),
		territorial_isolation: () => import('$lib/data/sat_territorial_isolation_dept_summary.json'),
		health_access: () => import('$lib/data/sat_health_access_dept_summary.json'),
		education_capital: () => import('$lib/data/sat_education_capital_dept_summary.json'),
		education_flow: () => import('$lib/data/sat_education_flow_dept_summary.json'),
		land_use: () => import('$lib/data/sat_land_use_dept_summary.json'),
		territorial_types: () => import('$lib/data/sat_territorial_types_dept_summary.json'),
		flood_risk: () => import('$lib/data/flood_dept_summary.json'),
		territorial_scores: () => import('$lib/data/scores_dept_summary.json'),
		sociodemographic: () => import('$lib/data/sat_sociodemographic_dept_summary.json'),
		economic_activity: () => import('$lib/data/sat_economic_activity_dept_summary.json'),
		accessibility: () => import('$lib/data/sat_accessibility_dept_summary.json'),
		climate_vulnerability: () => import('$lib/data/sat_climate_vulnerability_dept_summary.json'),
		carbon_stock: () => import('$lib/data/sat_carbon_stock_dept_summary.json'),
		pm25_drivers: () => import('$lib/data/sat_pm25_drivers_dept_summary.json'),
		productive_activity: () => import('$lib/data/sat_productive_activity_dept_summary.json'),
		deforestation_dynamics: () => import('$lib/data/sat_deforestation_dynamics_dept_summary.json'),
	};

	// Bundled summaries for Itapúa (distritos, admin_col='distrito')
	const ITAPUA_SUMMARIES: Record<string, () => Promise<any>> = {
		environmental_risk:      () => import('$lib/data/itapua_py_sat_environmental_risk_summary.json'),
		climate_comfort:         () => import('$lib/data/itapua_py_sat_climate_comfort_summary.json'),
		green_capital:           () => import('$lib/data/itapua_py_sat_green_capital_summary.json'),
		change_pressure:         () => import('$lib/data/itapua_py_sat_change_pressure_summary.json'),
		forest_health:           () => import('$lib/data/itapua_py_sat_forest_health_summary.json'),
		agri_potential:          () => import('$lib/data/itapua_py_sat_agri_potential_summary.json'),
		carbon_stock:            () => import('$lib/data/itapua_py_sat_carbon_stock_summary.json'),
		climate_vulnerability:   () => import('$lib/data/itapua_py_sat_climate_vulnerability_summary.json'),
		deforestation_dynamics:  () => import('$lib/data/itapua_py_sat_deforestation_dynamics_summary.json'),
		forestry_aptitude:       () => import('$lib/data/itapua_py_sat_forestry_aptitude_summary.json'),
		location_value:          () => import('$lib/data/itapua_py_sat_location_value_summary.json'),
		pm25_drivers:            () => import('$lib/data/itapua_py_sat_pm25_drivers_summary.json'),
		productive_activity:     () => import('$lib/data/itapua_py_sat_productive_activity_summary.json'),
		flood_risk:              () => import('$lib/data/itapua_py_flood_dept_summary.json'),
	};

	// Lookup: territory prefix → summaries dict (add new territories here)
	const TERRITORY_SUMMARIES: Record<string, Record<string, () => Promise<any>>> = {
		'itapua_py/': ITAPUA_SUMMARIES,
	};

	$effect(() => {
		if (!isPerDept || !layerCfg) return;
		const prefix = hexStore.territoryPrefix;
		deptSummary = null;
		const summaries = prefix ? TERRITORY_SUMMARIES[prefix] : SAT_SUMMARIES;
		if (!summaries) return; // unknown territory, no dept summaries yet
		const loader = summaries[layerCfg.id];
		if (loader) {
			loader().then(mod => { deptSummary = mod.default; }).catch(() => {});
		}
	});

	const deptList = $derived.by(() => {
		if (!deptSummary?.departments) return [];
		return [...deptSummary.departments].sort((a: any, b: any) => b.avg_score - a.avg_score);
	});

	const colorScale = $derived(layerCfg?.colorScale ?? 'sequential');
	const isCategorical = $derived(colorScale === 'categorical');
	const PALETTE = ['#1565c0', '#7e57c2', '#4db6ac', '#66bb6a', '#c0ca33', '#ffb74d', '#e65100', '#78909c'];

	function getTypeColor(type: number): string {
		return PALETTE[(type - 1) % PALETTE.length];
	}

	function getScoreColor(score: number): string {
		if (isCategorical) return getTypeColor(Math.round(score));
		if (colorScale === 'flood') {
			if (score >= 10) return '#dc2626';
			if (score >= 4)  return '#eab308';
			return '#3b82f6';
		}
		if (colorScale === 'green') {
			if (score >= 70) return '#22c55e';
			if (score >= 40) return '#166534';
			return '#1e293b';
		}
		if (colorScale === 'warm') {
			if (score >= 70) return '#fde725';
			if (score >= 40) return '#f59e0b';
			return '#0f172a';
		}
		// Sequential (viridis)
		if (score >= 70) return '#fde725';
		if (score >= 40) return '#21918c';
		return '#440154';
	}

	function getScoreLevel(score: number): string {
		if (colorScale === 'flood') {
			if (score >= 10) return i18n.t('legend.high');
			if (score >= 4)  return i18n.t('legend.medium');
			if (score >= 2)  return i18n.t('legend.low');
			return i18n.t('legend.veryLow');
		}
		if (score >= 70) return i18n.t('legend.high');
		if (score >= 40) return i18n.t('legend.medium');
		if (score >= 20) return i18n.t('legend.low');
		return i18n.t('legend.veryLow');
	}

	const legendGradient = $derived(
		colorScale === 'flood'
			? 'linear-gradient(to right, #3b82f6, #eab308, #dc2626)'
			: colorScale === 'green'
			? 'linear-gradient(to right, #1e293b, #166534, #22c55e, #bbf7d0)'
			: 'linear-gradient(to right, #2166ac, #f7f7f7, #b2182b)'
	);

	const legendLabels = $derived(
		[i18n.t('legend.low'), i18n.t('legend.medium'), i18n.t('legend.high')]
	);

	const scoreDirection = $derived(
		colorScale === 'flood' ? 'danger' : isCategorical ? 'categorical' : 'good'
	);

	// Auto-select top department on first load
	// Department list loads, user picks manually

	function handleDptoClick(dept: any) {
		if (onSelectDpto) {
			// Support both 'dpto' (Misiones) and 'distrito' (Itapúa) admin column names
			const name = dept.dpto ?? dept.distrito ?? '';
			onSelectDpto(name, dept.parquetKey, dept.centroid as [number, number]);
		}
	}

	function handleBackToDepts() {
		hexStore.setLayer(analysis.id);
	}

	let downloadState = $state<'idle' | 'csv' | 'geojson'>('idle');

	function currentParquetKey(): string {
		const dept = deptList.find((d: any) => (d.dpto ?? d.distrito) === selectedDpto);
		return dept?.parquetKey || 'data';
	}

	async function handleDownloadCsv() {
		if (!dataUrl || downloadState !== 'idle') return;
		downloadState = 'csv';
		try {
			await downloadCsvFromQuery(
				`SELECT * FROM '${dataUrl}'`,
				`spatia_${layerCfg?.id}_${currentParquetKey()}.csv`
			);
		} catch (e) {
			console.warn('CSV download failed:', e);
		} finally {
			downloadState = 'idle';
		}
	}

	async function handleDownloadGeoJson() {
		if (!dataUrl || downloadState !== 'idle') return;
		downloadState = 'geojson';
		try {
			await downloadGeoJsonFromHexQuery(
				`SELECT * FROM '${dataUrl}'`,
				`spatia_${layerCfg?.id}_${currentParquetKey()}.geojson`
			);
		} catch (e) {
			console.warn('GeoJSON download failed:', e);
		} finally {
			downloadState = 'idle';
		}
	}

	function urlForAnalysis(id: string, parquetKey: string): string {
		const tp = hexStore.territoryPrefix;
		if (id === 'flood_risk') return getFloodDptoUrl(parquetKey, tp);
		if (id === 'territorial_scores') return getScoresDptoUrl(parquetKey, tp);
		return getSatDptoUrl(id, parquetKey, tp);
	}

	// Data download URL for selected department
	const dataUrl = $derived.by(() => {
		if (!selectedDpto || !layerCfg || !deptList.length) return null;
		const dept = deptList.find((d: any) => (d.dpto ?? d.distrito) === selectedDpto);
		if (!dept) return null;
		return urlForAnalysis(layerCfg.id, dept.parquetKey);
	});

	// Component variables (skip score, type, type_label, pca)
	const componentVars = $derived(
		layerCfg?.variables.filter(v =>
			!['score', 'flood_risk_score', 'risk_score', 'type', 'type_label', 'territorial_type', 'pca_1', 'pca_2'].includes(v.col)
		) ?? []
	);

	// Petal chart data for selected hex
	const petalLabels = $derived(componentVars.map(v => i18n.t(v.labelKey)));
	const hexPetalLayers = $derived.by(() => {
		if (!selectedHex || componentVars.length === 0) return [];
		const values = componentVars.map(v => {
			const val = selectedHex[v.col];
			return typeof val === 'number' ? Math.min(100, Math.max(0, val)) : 0;
		});
		return [{ values, color: getTypeColor(selectedHex.type ?? 1) }];
	});

	// ── Cross-analysis profile for selected hex ──
	const CROSS_ANALYSIS_IDS = ['environmental_risk', 'climate_comfort', 'green_capital', 'change_pressure', 'agri_potential', 'forest_health'];
	const CROSS_TITLE_KEYS: Record<string, string> = { land_use: 'sat.landUse.title' };
	const CROSS_ANALYSES = $derived(
		CROSS_ANALYSIS_IDS.map(id => {
			const cfg = HEX_LAYER_REGISTRY[id];
			const titleKey = cfg?.titleKey ?? CROSS_TITLE_KEYS[id] ?? id;
			return { id, label: i18n.t(titleKey) };
		})
	);

	let crossProfile = $state<{ label: string; typeLabel: string }[]>([]);

	$effect(() => {
		const hex = selectedHex;
		const dpto = selectedDpto;
		if (!hex || !dpto || !deptList.length) { crossProfile = []; return; }

		const dept = deptList.find((d: any) => (d.dpto ?? d.distrito) === dpto);
		if (!dept) { crossProfile = []; return; }

		const h3 = hex.h3index;
		const promises = CROSS_ANALYSES
			.filter(a => a.id !== analysis.id)
			.map(async (a) => {
				try {
					let url: string;
					if (a.id === 'flood_risk') url = getFloodDptoUrl(dept.parquetKey);
					else if (a.id === 'territorial_scores') url = getScoresDptoUrl(dept.parquetKey);
					else url = getSatDptoUrl(a.id, dept.parquetKey);
					const r = await query(`SELECT type_label FROM '${url}' WHERE h3index = '${h3}'`);
					if (r.numRows > 0) {
						const row = r.get(0)!.toJSON() as Record<string, any>;
						return { label: a.label, typeLabel: String(row.type_label || '—') };
					}
				} catch { /* skip unavailable */ }
				return { label: a.label, typeLabel: '—' };
			});

		Promise.all(promises).then(results => { crossProfile = results; });
	});

	// ── Type distribution for selected department ──
	let typeDistribution = $state<{ type: number; label: string; count: number; pct: number; avgScore: number | null }[]>([]);

	$effect(() => {
		const dpto = selectedDpto;
		if (!dpto || !dataUrl) { typeDistribution = []; return; }

		// Only categorical analyses (clustered with type labels) have the type/type_label columns.
		// For continuous analyses the query would fail with a Binder Error.
		if (!isCategorical) { typeDistribution = []; return; }

		const pv = layerCfg?.primaryVariable ?? 'score';
		const scoreCol = pv === 'type' || pv === 'territorial_type' ? '' : `, AVG(${pv}) as avg_score`;
		query(`SELECT type, type_label, COUNT(*) as n${scoreCol} FROM '${dataUrl}' GROUP BY type, type_label ORDER BY n DESC`)
			.then(r => {
				const total = Array.from({ length: r.numRows }, (_, i) => Number(r.get(i)!.toJSON().n)).reduce((a, b) => a + b, 0);
				typeDistribution = Array.from({ length: r.numRows }, (_, i) => {
					const row = r.get(i)!.toJSON() as Record<string, any>;
					return {
						type: Number(row.type),
						label: String(row.type_label || `Tipo ${row.type}`),
						count: Number(row.n),
						pct: Math.round(Number(row.n) / total * 100),
						avgScore: row.avg_score != null ? Number(row.avg_score) : null,
					};
				});
			})
			.catch(() => { typeDistribution = []; });
	});

	// ── Diagnostic: dominant type per analysis for department ──
	let showDiagnostic = $state(false);
	let diagnosticData = $state<{ label: string; dominant: string; pct: number }[]>([]);

	async function loadDiagnostic() {
		if (!selectedDpto || !deptList.length) return;
		const dept = deptList.find((d: any) => (d.dpto ?? d.distrito) === selectedDpto);
		if (!dept) return;

		showDiagnostic = true;
		const allAnalyses = [...CROSS_ANALYSES, { id: analysis.id, label: i18n.t(analysis.titleKey).replace(/ \(Misiones\)/, '') }];

		const results = await Promise.all(allAnalyses.map(async (a) => {
			try {
				let url: string;
				if (a.id === 'flood_risk') url = getFloodDptoUrl(dept.parquetKey);
				else if (a.id === 'territorial_scores') url = getScoresDptoUrl(dept.parquetKey);
				else url = getSatDptoUrl(a.id, dept.parquetKey);
				const r = await query(`SELECT type_label, COUNT(*) as n FROM '${url}' GROUP BY type_label ORDER BY n DESC LIMIT 1`);
				if (r.numRows > 0) {
					const row = r.get(0)!.toJSON() as Record<string, any>;
					const total_r = await query(`SELECT COUNT(*) as t FROM '${url}'`);
					const total = Number(total_r.get(0)!.toJSON().t);
					return { label: a.label, dominant: String(row.type_label), pct: Math.round(Number(row.n) / total * 100) };
				}
			} catch { /* skip */ }
			return { label: a.label, dominant: '—', pct: 0 };
		}));

		diagnosticData = results;
	}

	// PDF report URL for selected department
	const reportUrl = $derived.by(() => {
		if (!selectedDpto || !layerCfg || !deptList.length) return null;
		const dept = deptList.find((d: any) => (d.dpto ?? d.distrito) === selectedDpto);
		if (!dept) return null;
		return getReportUrl(layerCfg.id, dept.parquetKey);
	});

	// ── Explanatory content per analysis (legacy inline dict, replaced by import) ──
	const METHOD_COMMON = 'Valores por variable (0–100): cada variable se convierte a percentil provincial. 50 = mediana de Misiones, 100 = valor más alto de la provincia.\n\nTipos (clusters): las variables estandarizadas se procesan con PCA para validar independencia (se descartan variables con |r| > 0.70). Luego k-means agrupa hexágonos con perfiles multivariados similares. Cada hexágono se asigna al tipo cuyo centroide es más cercano. La calidad se valida con coeficiente de silueta. Los tipos no son un ranking — son perfiles cualitativos distintos.';

	const ANALYSIS_CONTENT_LEGACY: Record<string, { howToRead: string; implications: string; method: string }> = {
		flood_risk: {
			howToRead: 'Los colores representan el riesgo hídrico de cada hexágono, combinando la presencia histórica de agua (JRC, 1984–2021) y la detección actual de inundación (Sentinel-1 SAR). Azul oscuro = riesgo bajo; amarillo = riesgo medio; rojo = riesgo alto. Selecciona un departamento para ver el detalle.',
			implications: 'Las zonas de riesgo alto pueden enfrentar anegamientos recurrentes, afectando el valor inmobiliario, la habitabilidad y la infraestructura de servicios básicos (agua, cloacas). La recurrencia interanual distingue inundaciones estacionales predecibles de eventos extremos esporádicos.',
			method: 'Índice compuesto 0–100 (donde 0 = sin riesgo y 100 = máximo riesgo provincial): 50% presencia histórica de agua (JRC Global Surface Water, Landsat 1984–2021) + 20% recurrencia interanual (JRC) + 30% extensión actual (Sentinel-1 SAR, última imagen procesada). Fuentes: JRC v1.4 + Copernicus Sentinel-1. Resolución: H3 resolución 9.',
		},
		territorial_scores: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de consolidación urbana según 8 indicadores derivados de Overture Maps: pavimentación, consolidación, acceso a servicios, vitalidad comercial, conectividad vial, mezcla edilicia, urbanización y exposición hídrica. Cada color representa un perfil urbano distinto.',
			implications: 'Los tipos permiten distinguir núcleos urbanos consolidados, periferias en expansión con servicios incompletos, y zonas rurales sin infraestructura urbana. La clasificación multivariada evita reducir la complejidad urbana a un único indicador de "desarrollo".',
			method: `${METHOD_COMMON} 8 variables: paving_index, urban_consolidation, service_access, commercial_vitality, road_connectivity, building_mix, urbanization, water_exposure. Fuente: Overture Maps Foundation (CC BY 4.0, release 2026-03-18) vía walkthru.earth. k=5 tipos.`,
		},
		environmental_risk: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de riesgo ambiental según la co-ocurrencia de deforestación, amplitud térmica, pendiente y altura sobre drenaje. Cada color representa un tipo distinto de configuración de riesgo.',
			implications: 'Los tipos permiten identificar configuraciones de riesgo cualitativamente distintas: zonas de alta pendiente con baja deforestación difieren estructuralmente de zonas planas con alta pérdida forestal, aunque ambas puedan tener "riesgo" similar en un índice único.',
			method: `${METHOD_COMMON} Variables: deforestación Hansen GFC, amplitud térmica LST MODIS, pendiente FABDEM 30m, HAND MERIT Hydro. k=5 tipos, silueta=0.33.`,
		},
		climate_comfort: {
			howToRead: 'El mapa clasifica cada hexágono en tipos climáticos según la co-ocurrencia de temperatura diurna, nocturna, precipitación, heladas y estrés hídrico. Cada color representa un régimen climático distinto.',
			implications: 'Los tipos climáticos revelan gradientes geoespaciales que un índice único no captura: zonas cálidas y húmedas difieren estructuralmente de zonas frescas y secas, con implicancias distintas para habitabilidad y producción.',
			method: `${METHOD_COMMON} Variables: LST diurno/nocturno MODIS, precipitación CHIRPS, heladas ERA5, ratio ET/PET MODIS. k=4 tipos, silueta=0.40.`,
		},
		green_capital: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de capital verde según la co-ocurrencia de verdor, cobertura arbórea, productividad primaria, área foliar y fracción de vegetación. Cada color representa un estado ecosistémico distinto.',
			implications: 'Los tipos distinguen selva densa de alta productividad, bosque secundario con cobertura residual, y zonas deforestadas con baja vegetación. Esta distinción cualitativa informa mejor las políticas de conservación que un gradiente continuo.',
			method: `${METHOD_COMMON} Variables: NDVI MODIS 250m, cobertura arbórea Hansen 2000, NPP MODIS, LAI MODIS, VCF MODIS. k=3 tipos, silueta=0.46.`,
		},
		change_pressure: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de presión de cambio según la co-ocurrencia de tendencia de urbanización, expansión construida, pérdida forestal y cambio de vegetación.',
			implications: 'Los tipos separan urbanización activa de deforestación agrícola y de zonas estables. Un municipio con "alta presión" por urbanización requiere políticas distintas a uno con "alta presión" por avance de frontera agraria.',
			method: `${METHOD_COMMON} Variables: tendencia VIIRS 2016-2025, cambio GHSL 2000-2020, pérdida Hansen, tendencia NDVI. k=5 tipos, silueta=0.34.`,
		},
		location_value: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de valor posicional según la co-ocurrencia de accesibilidad, conectividad a salud, actividad económica, topografía y distancia a rutas.',
			implications: 'Los tipos distinguen núcleos urbanos bien conectados, periferias accesibles pero poco activas, y zonas rurales aisladas. El valor posicional emergente de la clasificación es más informativo que un ranking lineal.',
			method: `${METHOD_COMMON} Variables: tiempo a ciudad 20k Nelson, acceso a salud Oxford, radiancia VIIRS, pendiente FABDEM, distancia a ruta OSM. k=4 tipos, silueta=0.43.`,
		},
		agri_potential: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de aptitud agrícola según la co-ocurrencia de calidad del suelo, régimen hídrico, acumulación térmica y topografía.',
			implications: 'Los tipos reflejan configuraciones edafoclimáticas distintas: suelos ácidos con alta lluvia (aptitud para yerba mate), suelos neutros con calor acumulado (aptitud para tabaco/cítricos), y zonas con limitaciones múltiples.',
			method: `${METHOD_COMMON} Variables: carbono orgánico SoilGrids, pH óptimo, arcilla, precipitación CHIRPS, GDD ERA5, pendiente FABDEM. k=3 tipos, silueta=0.32.`,
		},
		forest_health: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de integridad forestal según la co-ocurrencia de tendencia de verdor, pérdida arbórea, productividad fotosintética y evapotranspiración.',
			implications: 'Los tipos separan bosque sano y productivo, bosque en degradación con pérdida activa, y zonas sin cobertura forestal significativa. Esta clasificación permite priorizar intervenciones de restauración donde la degradación es incipiente.',
			method: `${METHOD_COMMON} Variables: tendencia NDVI 5 años, ratio pérdida/cobertura Hansen, GPP MODIS, ET MODIS. k=4 tipos, silueta=0.38.`,
		},
		forestry_aptitude: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de aptitud forestal comercial según la co-ocurrencia de acidez del suelo, precipitación, pendiente, y accesibilidad logística.',
			implications: 'Los tipos identifican zonas óptimas para plantaciones de pino/eucalipto (suelo ácido, lluvia suficiente, pendiente mecanizable, cerca de rutas) frente a zonas marginales donde la forestación comercial no es viable. Este análisis evalúa aptitud del suelo y clima — no reemplaza la verificación de restricciones legales (áreas protegidas, comunidades indígenas, Ley de Bosques 26.331).',
			method: `${METHOD_COMMON} Variables: pH SoilGrids, arcilla, precipitación CHIRPS, pendiente FABDEM, distancia a ruta OSM, accesibilidad Nelson. k=3 tipos, silueta=0.33.`,
		},
		service_deprivation: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de carencia de servicios básicos según NBI, acceso a cloacas, calidad del piso, hacinamiento y acceso digital. Solo se muestran hexágonos con edificaciones detectadas (crosswalk dasimétrico). Cada color representa un perfil de carencia distinto.',
			implications: 'Los tipos separan carencia habitacional (piso inadecuado + hacinamiento), carencia de infraestructura (sin cloacas), y brecha digital (sin computadora). Cada configuración demanda intervenciones distintas: vivienda social, extensión de red cloacal, o programas de inclusión digital.',
			method: `${METHOD_COMMON} 6 variables Censo Nacional 2022 (INDEC): NBI, sin cloacas (100 - pct_cloacas), piso inadecuado, hacinamiento, hacinamiento crítico, sin computadora (100 - pct_computadora). Crosswalk dasimétrico ponderado por edificios (2.8M footprints). KMO=0.73.`,
		},
		territorial_isolation: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de aislamiento geoespacial según tiempo de viaje a ciudades y centros de salud, distancia a rutas, densidad vial, luces nocturnas y densidad poblacional. Cobertura completa de la provincia (crosswalk híbrido).',
			implications: 'Los tipos distinguen aislamiento por distancia (lejos de rutas y ciudades), aislamiento funcional (cerca de ruta pero sin servicios), y conectividad plena. Las zonas aisladas enfrentan costos de transporte, acceso limitado a salud y educación, y menor oportunidad económica.',
			method: `${METHOD_COMMON} 6 variables: acceso a ciudades y salud (Oxford MAP 2019, fricción motorizada), distancia a ruta primaria y densidad vial (OSM), radiancia VIIRS 2022-2024, densidad poblacional Censo 2022. Crosswalk híbrido (dasimétrico + areal). KMO=0.87.`,
		},
		health_access: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de acceso a salud según tiempo al centro de salud, cobertura sanitaria, vulnerabilidad social (NBI), presión demográfica (ancianos y menores) y densidad poblacional. Solo hexágonos con edificaciones.',
			implications: 'Los tipos separan déficit por distancia (zonas rurales lejanas), déficit por saturación (zonas densas con alta proporción de población vulnerable), y déficit por cobertura (alto NBI con baja cobertura sanitaria). Cada configuración requiere respuestas distintas del sistema de salud.',
			method: `${METHOD_COMMON} 6 variables: tiempo motorizado a salud (Oxford MAP 2019), cobertura sanitaria, NBI, % adultos mayores, % menores 18, densidad poblacional (Censo 2022). Crosswalk dasimétrico. KMO=0.60.`,
		},
		education_capital: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de capital educativo según el nivel de instrucción acumulado: sin instrucción, secundario completo o más, educación superior (terciario + universitario), y universitario. Solo hexágonos con edificaciones.',
			implications: 'Los tipos distinguen zonas con alto capital humano (universidades cercanas, alta formación), zonas de educación media (secundario completo pero sin terciario), y zonas de bajo capital (alta proporción sin instrucción). El capital educativo es predictor de ingresos, salud y participación cívica.',
			method: `${METHOD_COMMON} 4 variables Censo 2022: % sin instrucción, % secundario completo o más (umbral acumulativo), % educación superior (terciario + universitario), % universitario. Terciario y universitario son tracks paralelos en el sistema argentino. Crosswalk dasimétrico. KMO=0.71.`,
		},
		education_flow: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de desempeño del sistema educativo según inasistencia escolar primaria (6-12), secundaria (13-18) y maternidad adolescente. Solo hexágonos con edificaciones.',
			implications: 'Los tipos separan deserción temprana (primaria), deserción tardía (secundaria) y embarazo adolescente como factor de exclusión educativa. La inasistencia primaria indica fallas básicas del sistema; la secundaria indica problemas de retención; la maternidad adolescente indica vulnerabilidad de género intersectada con pobreza.',
			method: `${METHOD_COMMON} 3 variables Censo 2022: tasa de inasistencia 6-12 años, tasa de inasistencia 13-18 años, tasa de maternidad adolescente. Variables directas (mayor = peor flujo). Crosswalk dasimétrico. KMO=0.61.`,
		},
		land_use: {
			howToRead: 'El mapa clasifica cada hexágono según su cobertura dominante: selva nativa, plantación forestal, pastizal, agricultura, agua o urbano. La fuente es MapBiomas Argentina (Landsat 30m, 2022) que distingue bosque nativo de silvicultura.',
			implications: 'La separación entre selva nativa (73%) y plantación forestal (12%) permite evaluar el estado de conservación real: los pinares/eucaliptos no son selva paranaense aunque Dynamic World los clasifique igual. Los mosaicos agropecuarios indican zonas de transición activa.',
			method: `${METHOD_COMMON} Fuente: MapBiomas Argentina Collection 1 (Landsat 30m, 2022). Clases remapeadas: bosque nativo, plantación, pastizal, agricultura, mosaico, humedal, urbano, agua. k=6 tipos, silueta=0.62.`,
		},
		powerline_density: {
			howToRead: 'Mapa de densidad de líneas de media y alta tensión. Hexágonos más claros = mayor densidad de infraestructura eléctrica. Score basado en longitud total y cantidad de líneas dentro de cada hexágono.',
			implications: 'La cobertura eléctrica condiciona toda actividad productiva y residencial. Zonas con baja densidad de líneas requieren extensión de red para habilitar nuevos emprendimientos. La distancia a líneas existentes es el principal factor de costo de electrificación rural.',
			method: 'Fuente: EMSA (Secretaría de Energía, datos.energia.gob.ar, abril 2024). Líneas de media y alta tensión georreferenciadas, intersectadas con grilla H3 resolución 9. Score = longitud total de líneas / área del hexágono, normalizado 0-100.',
		},
		territorial_types: {
			howToRead: 'El mapa clasifica cada hexágono en tipos geoespaciales según su metabolismo ecosistémico: productividad, apropiación humana y dinámica de cambio. Cada color representa un tipo cualitativamente distinto de territorio.',
			implications: 'Los tipos geoespaciales sintetizan 13 variables satelitales en una clasificación interpretable. Permiten identificar selva productiva intacta, mosaicos agro-forestales en transición, zonas agrícolas consolidadas, periurbanos en expansión y núcleos urbanos — cada uno con necesidades de gestión distintas.',
			method: `${METHOD_COMMON} 13 variables: NPP, NDVI, cobertura arbórea, fracción arboles/cultivos/construido, deforestación, luces nocturnas, tendencia VIIRS, expansión GHSL, precipitación. k=8 tipos. Fuentes: MODIS, Hansen GFC, VIIRS, GHSL, CHIRPS.`,
		},
		sociodemographic: {
			howToRead: 'El mapa clasifica cada hexágono en tipos sociodemográficos según la co-ocurrencia de densidad poblacional, pobreza (NBI), hacinamiento, tenencia de vivienda, tamaño de hogar y acceso digital. Cada color representa un perfil censal distinto.',
			implications: 'Los tipos distinguen zonas urbanas densas con bajo NBI, periferias con hacinamiento y pobreza, y zonas rurales dispersas con alta propiedad pero baja conectividad. Esta clasificación multivariada evita reducir la complejidad social a un solo indicador.',
			method: `${METHOD_COMMON} 6 variables del Censo Nacional 2022 (INDEC): densidad hab/km², % NBI, % hacinamiento, % propietarios, tamaño medio hogar, % computadora. Variables a nivel radio censal, agregadas a H3 vía crosswalk ponderado por área.`,
		},
		economic_activity: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de actividad económica según la co-ocurrencia de empleo, actividad económica, formación universitaria, luces nocturnas y densidad edilicia. Cada color representa un nivel de dinamismo distinto.',
			implications: 'Los tipos separan centros económicos consolidados (alto empleo + universitarios + luces), periferias activas con posible informalidad (alta actividad, bajo empleo formal), y zonas rurales de baja actividad económica. La radiancia nocturna (VIIRS) es un proxy robusto de actividad que complementa los datos censales.',
			method: `${METHOD_COMMON} 5 variables: tasa de empleo y actividad (Censo 2022 INDEC, 14+ años), % universitarios (Censo 2022), radiancia media VIIRS 500m (2022-2024), densidad edilicia Global Building Atlas 2025. Variables censales agregadas a H3 vía crosswalk.`,
		},
		eudr: {
			howToRead: 'El mapa muestra el riesgo de deforestación post-2020 por hexágono (H3 res-7, ~5 km²). Score alto (rojo) = mayor pérdida forestal o actividad de fuego después del cutoff EUDR (31/12/2020). Cobertura: 10 provincias del NOA y NEA argentino.',
			implications: 'Hexágonos con deforestación post-2020 representan riesgo de no-conformidad bajo la Regulación (UE) 2023/1115. Exportaciones de commodities (soja, carne, madera) originados en estas zonas requieren due diligence reforzado. Este análisis es orientativo — la verificación formal requiere geometría parcelaria exacta.',
			method: 'Score compuesto 0-100: 70% pérdida forestal post-2020 (Hansen GFC v1.12, Landsat 30m) + 20% área quemada post-2020 (MODIS MCD64A1, 500m) + 10% pérdida de cobertura previa. Cutoff EUDR: 31/12/2020. Resolución espacial: H3 resolución 7 (~5.16 km²). Cobertura: Salta, Jujuy, Tucumán, Catamarca, Sgo. del Estero, Formosa, Chaco, Corrientes, Misiones, Entre Ríos.',
		},
		accessibility: {
			howToRead: 'El mapa clasifica cada hexágono en tipos de accesibilidad según la co-ocurrencia de tiempo de viaje a Posadas, a la cabecera departamental, distancia a hospital, escuela secundaria y ruta principal. Cada color representa un nivel de conectividad distinto.',
			implications: 'Los tipos distinguen conectividad plena (cercanía a servicios y rutas), accesibilidad parcial (cerca de ruta pero lejos de servicios especializados), y aislamiento funcional (lejos de todo). Cada configuración requiere estrategias de inversión en infraestructura distintas.',
			method: `${METHOD_COMMON} 5 variables: tiempo motorizado a Posadas y cabecera (Nelson et al. 2019, superficie de fricción Oxford MAP), distancia euclidiana a hospital, escuela secundaria y ruta primaria (OSM). Fuente: Nelson 2019 + Oxford MAP 2019 + OSM.`,
		},
		carbon_stock: {
			howToRead: 'El mapa muestra el stock de carbono total por hexágono (biomasa aérea + subterránea + carbono del suelo) y el balance anual de emisiones/remociones. Colores más intensos indican mayor stock. Los valores se muestran en unidades físicas (tC/ha, MgCO2/ha).',
			implications: 'Las zonas de alto stock con balance neto negativo (sumidero) son candidatas para créditos de carbono por conservación. Las zonas de alto stock con balance positivo (emisor) son prioridad para intervención REDD+. Las zonas de bajo stock con alta productividad (NPP) tienen potencial de restauración y secuestro futuro. *Valor teórico del carbono: estimación de referencia calculada como stock total x 3.67 (conversión C a CO2) x USD 10/tCO2e (mediana del mercado voluntario 2024, Ecosystem Marketplace 2024). No representa un precio de venta ni el valor realizable de un predio. La monetización efectiva requiere un proyecto certificado (VCS, Gold Standard) con línea base, adicionalidad demostrada y costos de transacción que reducen significativamente el valor neto.',
			method: `${METHOD_COMMON} 10 variables: biomasa aérea ESA CCI Biomass v6 (100m, Santoro et al. 2024) + GEDI L4B lidar (1km, validación). Biomasa subterránea vía Cairns et al. (1997): BGB = 0.489 x AGB^0.89. Carbono orgánico del suelo: SoilGrids v2 (ISRIC, 0-30cm extrapolado). Flujo de carbono: Harris et al. (2021) Nature Climate Change / Global Forest Watch (emisiones brutas + remociones + balance neto, 30m, 2001-2024). Productividad: MODIS MOD17A3HGF NPP (500m, 2019-2024). Total carbon = AGB x 0.47 + BGB x 0.47 + SOC. Precio de referencia: Ecosystem Marketplace (2024) State of the Voluntary Carbon Markets.`,
		},
		climate_vulnerability: {
			howToRead: 'El mapa clasifica cada hexágono según su vulnerabilidad climática integrada (framework IPCC AR5). Colores cálidos indican mayor vulnerabilidad: alta exposición a eventos extremos, alta sensibilidad ambiental, o baja capacidad adaptativa de la población. Cada tipo representa una configuración distinta de estos tres factores.',
			implications: 'Las zonas de alta vulnerabilidad integral requieren atención prioritaria en planes de adaptación climática. Las zonas con alta exposición pero buena capacidad adaptativa pueden absorber shocks; las zonas con baja capacidad adaptativa son vulnerables incluso ante exposición moderada. Este índice es el insumo estándar para fondos climáticos (GCF, GEF, Banco Mundial).',
			method: `${METHOD_COMMON} 8 variables agrupadas en 3 dimensiones IPCC: Exposición (estrés térmico MODIS LST, riesgo inundación JRC/S1, estrés hídrico ET/PET, frecuencia fuego MODIS MCD64A1), Sensibilidad (pérdida forestal Hansen GFC, desprotección vegetal Hansen treecover), Capacidad Adaptativa (aislamiento geoespacial Oxford MAP, privación de servicios INDEC 2022). Sub-índices: media geométrica por dimensión. Score final: media geométrica de las 3 dimensiones. PCA + k-means para tipología.`,
		},
		pm25_drivers: {
			howToRead: 'El mapa muestra la calidad del aire en cada hexágono, medida como concentración media de PM2.5 (partículas finas < 2.5 µm) y descompuesta en cuatro drivers: fuego regional, clima, terreno y vegetación. Score alto (colores fríos) = mejor calidad del aire; score bajo (colores cálidos) = mayor concentración de PM2.5. Selecciona un departamento para ver la contribución relativa de cada driver.',
			implications: 'La intensidad de fuego regional es el driver dominante de PM2.5 en Misiones: las quemas agrícolas y forestales en provincias vecinas y países limítrofes elevan la concentración de partículas finas incluso en zonas sin deforestación local. Las zonas con alta contribución climática son sensibles a eventos de inversión térmica que atrapan contaminantes. La vegetación actúa como filtro natural — la pérdida de cobertura arbórea reduce la capacidad de depuración del aire.',
			method: 'Descomposición por machine learning (LightGBM, SHAP feature attribution) de la concentración media anual de PM2.5. Fuente primaria: Atmospheric Composition Analysis Group (ACAG) V6.GL.02 (Dalhousie University, van Donkelaar et al. 2021), panel 1998-2022, resolución 0.01 deg (~1 km). Modelo entrenado con 31 covariables ambientales (R2 = 0.93 en validación cruzada espacial leave-one-department-out). Drivers agrupados por SHAP: fuego regional (contribución dominante, dR2 = 0.195), clima (precipitación, temperatura), terreno (elevación, pendiente) y vegetación (NDVI, NPP). El toggle temporal compara periodo 2001-2010 vs 2013-2022. Resolución espacial: H3 resolución 9.',
		},
		productive_activity: {
			howToRead: 'El mapa muestra la intensidad de actividad productiva medida por luces nocturnas satelitales (VIIRS). Colores cálidos = mayor radiancia nocturna = mayor actividad económica. Al hacer click se ven 6 indicadores en valores reales: luces, productividad vegetal, verdor, superficie construida, conversión forestal y temperatura. El toggle temporal compara con el periodo base (2014-2017 para VIIRS, 2005-2012 para otros indicadores).',
			implications: 'Las zonas con alta radiancia nocturna y crecimiento positivo (delta > 0) son polos económicos en expansión. Zonas con alta productividad vegetal (NPP) pero baja radiancia son áreas rurales productivas pero no urbanizadas. Un aumento de temperatura superficial (LST) junto con aumento de superficie construida indica urbanización activa. La conversión forestal alta combinada con baja actividad económica puede indicar deforestación sin desarrollo productivo asociado.',
			method: 'Seis indicadores satelitales en valores físicos reales (sin scores compuestos ni índices artificiales). VIIRS nightlights (NOAA, 500m, 2014-2025): radiancia media nocturna en nW/cm²/sr. NPP (MODIS, 1km, 2005-2024): productividad primaria neta en gC/m²/año. NDVI (MODIS, 250m, 2005-2024): índice de vegetación normalizado. GHSL built surface (JRC, 10m, epochs 2000/2020): fracción de superficie construida. Hansen forest loss (UMD/Landsat, 30m, 2001-2024): pérdida acumulada. LST (MODIS, 1km, 2005-2024): temperatura superficial diurna en grados Celsius. Cada hexágono H3 res-9 recibe el valor ponderado por la fracción de área del radio censal que lo cubre (crosswalk dasimétrico areal). El color del mapa representa el percentil provincial de la radiancia nocturna.',
		},
		deforestation_dynamics: {
			howToRead: 'Cada hexágono muestra la tasa de pérdida forestal observada en ese punto exacto (pixel Landsat 30m). Colores cálidos = mayor pérdida forestal reciente (2015-2024). El toggle temporal permite comparar con la línea base (2001-2010): el modo "Cambio" muestra si la deforestación aceleró (rojo) o frenó (verde) respecto al periodo base.',
			implications: 'Las zonas con alta tasa de pérdida sostenida representan frentes de deforestación activos donde la conversión del bosque nativo continúa. Las zonas donde la deforestación frenó (delta negativo) pueden reflejar el efecto de la Ley de Bosques (26.331/OTBN, vigente desde 2007) o el agotamiento del recurso. Las zonas que aceleraron post-2015 a pesar de la regulación requieren atención prioritaria de fiscalización.',
			method: 'Fuente: Hansen Global Forest Change v1.12 (University of Maryland / Google), derivado de series temporales Landsat a 30m de resolución, cobertura 2001-2024. Cada hexágono H3 resolución 9 (~0.1 km²) recibe el valor del pixel de pérdida en su centroide — no hay promedio por radio censal. La tasa de pérdida se calcula como fracción de años con pérdida detectada en cada periodo. Línea base: 2001-2010; actual: 2015-2024. Actualización automática vía GitHub Actions cuando Hansen publica nuevos datos (~abril de cada año).',
		},
	};

	// Dynamic World (land_use) — will be added when data is processed
	// SAT_SUMMARIES and ANALYSIS_CONTENT entries are ready for when the parquet exists

	const content = $derived(ANALYSIS_CONTENT[analysis.id] ?? null);

	// ── Temporal toggle support ──
	const isTemporal = $derived(layerCfg?.temporal === true);
	const tMode = $derived(hexStore.temporalMode);

	function getDisplayCol(col: string): string {
		if (!isTemporal || tMode === 'current') return col;
		return getTemporalCol(col, tMode);
	}

	function getDisplayVal(hex: Record<string, any>, col: string): number | null {
		const tCol = getDisplayCol(col);
		return hex[tCol] !== undefined ? (hex[tCol] as number) : null;
	}

	const effectiveLegendGradient = $derived(
		isTemporal && tMode === 'delta'
			? 'linear-gradient(to right, #dc2626, #737373, #22c55e)'
			: legendGradient
	);
	const effectiveLegendLabels = $derived(
		isTemporal && tMode === 'delta'
			? [i18n.t('temporal.legend.worse'), i18n.t('temporal.legend.noChange'), i18n.t('temporal.legend.better')]
			: legendLabels
	);

	const displayScore = $derived(selectedHex ? (getDisplayVal(selectedHex, layerCfg?.primaryVariable ?? 'score') ?? 0) : 0);

	/**
	 * Adaptive number formatter — picks precision based on magnitude so that
	 * fractional values like NDVI (0.85) do not collapse to "1" via toFixed(0).
	 */
	function fmtSmart(v: unknown): string {
		if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
		if (v === 0) return '0';
		const abs = Math.abs(v);
		if (abs < 0.01) return v.toExponential(1);
		if (abs < 1) return v.toFixed(2);
		if (abs < 10) return v.toFixed(2);
		if (abs < 100) return v.toFixed(1);
		return v.toFixed(0);
	}

	let reportCopied = $state(false);
	async function copyReportEmail() {
		await navigator.clipboard.writeText('nealab@spatia.ar');
		reportCopied = true;
		setTimeout(() => { reportCopied = false; }, 2000);
	}
</script>

{#if selectedHex && selectedDpto && isPerDept}
	<!-- ═══ HEX DETAIL VIEW ═══ -->
	<div class="view">
		<button class="back-btn" onclick={handleBackToDepts}>{i18n.t('analysis.flood.topDepts')}</button>

		<div class="hex-header">
			<div class="hex-id" title={selectedHex.h3index}>
				{selectedHex.h3index.slice(0, 4)}...{selectedHex.h3index.slice(-4)}
			</div>
			{#if selectedHex.type_label}
				<div class="risk-badge" style:background={getTypeColor(selectedHex.type ?? 1)}>
					{selectedHex.type_label}
				</div>
			{:else if !isCategorical}
				<div class="risk-badge" style:background={getScoreColor(displayScore)}>
					{getScoreLevel(displayScore)}
				</div>
			{/if}
		</div>

		{#if isTemporal}
			<TemporalToggle {hexStore} layerId={layerCfg?.id ?? ''} />
		{/if}

		{#if hexPetalLayers.length > 0}
			<div class="petal-section">
				<div class="petal-wrapper">
					<PetalChart layers={hexPetalLayers} labels={petalLabels} size={240} />
				</div>
				<p class="petal-hint">{i18n.t('analysis.petalHint')}</p>
			</div>
		{/if}
		{#if CENSUS_ANALYSES.has(analysis.id) && componentVars.length > 0}
			<div class="census-detail">
				{#each componentVars as v}
					{@const val = selectedHex[v.col]}
					{@const numVal = typeof val === 'number' ? val : 0}
					{@const rawVal = v.rawCol ? selectedHex[v.rawCol] : null}
					{@const displayVal = (rawVal != null && typeof rawVal === 'number') ? rawVal : numVal}
					<div class="cd-row">
						<span class="cd-label">{i18n.t(v.labelKey)}</span>
						<span class="cd-val-data">{fmtSmart(displayVal)}{v.unit ? ` ${v.unit}` : ' (0–100)'}</span>
					</div>
				{/each}
			</div>
		{/if}

		{#if crossProfile.length > 0}
			<div class="cross-profile">
				<div class="cross-title">{i18n.t('section.territorialProfile')}</div>
				{#each crossProfile as cp}
					<div class="cross-row">
						<span class="cross-label">{cp.label}</span>
						<span class="cross-value">{cp.typeLabel}</span>
					</div>
				{/each}
			</div>
		{/if}

		{#if dataUrl}
			<div class="download-row">
				<button class="download-btn" onclick={handleDownloadCsv} disabled={downloadState !== 'idle'} title="CSV del departamento (todos los hexágonos)">
					{downloadState === 'csv' ? '…' : 'CSV'}
				</button>
				<button class="download-btn download-secondary" onclick={handleDownloadGeoJson} disabled={downloadState !== 'idle'} title="GeoJSON del departamento (polígonos H3)">
					{downloadState === 'geojson' ? '…' : 'GeoJSON'}
				</button>
			</div>
		{/if}

		{#if freshness}
			<div class="source-note-box">
				<div><strong>{i18n.t('section.source')}:</strong> {i18n.t(freshness.sourceKey)}</div>
				<div><strong>{i18n.t('section.processed')}:</strong> {freshness.processedDate}</div>
			</div>
		{/if}
	</div>

{:else if selectedDpto && isPerDept}
	<!-- ═══ DEPARTMENT SELECTED (minimal, like FloodRisk) ═══ -->
	<div class="view">
		<button class="back-btn" onclick={handleBackToDepts}>{i18n.t('analysis.flood.topDepts')}</button>

		<div class="dept-active-title">{selectedDpto}</div>

		{#if dataUrl}
			<div class="download-row">
				<button
					class="download-btn"
					onclick={handleDownloadCsv}
					disabled={downloadState !== 'idle'}
					title="CSV · todas las variables por hexágono H3"
				>
					{downloadState === 'csv' ? '…' : '↓ CSV'}
				</button>
				<button
					class="download-btn download-secondary"
					onclick={handleDownloadGeoJson}
					disabled={downloadState !== 'idle'}
					title="GeoJSON · polígonos H3 para QGIS / ArcGIS"
				>
					{downloadState === 'geojson' ? '…' : '↓ GeoJSON'}
				</button>
			</div>
		{/if}

		{#if content}
			<a class="methodology-link" href="/metodologia/{analysis.id}" target="_blank" rel="noopener">
				¿Cómo se calcula? →
			</a>
		{/if}

		{#if isTemporal}
			<TemporalToggle {hexStore} layerId={layerCfg?.id ?? ''} />
		{/if}

		{#if loading}
			<div class="loading">{i18n.t('analysis.loading')}</div>
		{:else}
			<div class="hint">{i18n.t('analysis.flood.clickHint')}</div>
		{/if}

		{#if typeDistribution.length > 0}
			<div class="type-dist">
				<div class="cross-title">{i18n.t('section.typeDistribution')}</div>
				{#each typeDistribution as td}
					<div class="cross-row">
						<span class="cross-label">{td.label}</span>
						<span class="cross-value">{td.count.toLocaleString()} ({td.pct}%)</span>
					</div>
				{/each}
			</div>
		{/if}

		<div class="action-row">
			<button class="action-btn" onclick={copyReportEmail} style="text-align:center;cursor:pointer;">
				{reportCopied ? 'nealab@spatia.ar ✓' : i18n.t('section.requestReport')}
			</button>
		</div>

		{#if content}
			<details class="method-details">
				<summary class="method-summary">{i18n.t('section.howToRead')}</summary>
				<div class="method-body">
					<p class="explain-text">{content.howToRead}</p>
				</div>
			</details>
			<details class="method-details">
				<summary class="method-summary">{i18n.t('section.implications')}</summary>
				<div class="method-body">
					<p class="explain-text">{content.implications}</p>
				</div>
			</details>
			<details class="method-details">
				<summary class="method-summary">{i18n.t('section.methodology')}</summary>
				<div class="method-body">
					<p class="explain-text">{content.method}</p>
				</div>
			</details>
		{/if}

		{#if freshness}
			<div class="source-note-box">
				<div><strong>{i18n.t('section.source')}:</strong> {i18n.t(freshness.sourceKey)}</div>
				<div><strong>{i18n.t('section.processed')}:</strong> {freshness.processedDate}</div>
			</div>
		{/if}
	</div>

{:else if isPerDept}
	<!-- ═══ DEPARTMENT LIST ═══ -->
	<div class="view">
		<p class="desc">{i18n.t(analysis.descKey)}</p>

		{#if !isCategorical}
			<div class="score-info-box">
				<span class="score-range">{i18n.t('legend.range')}</span>
				{#if scoreDirection === 'danger'}
					<span class="score-dir score-dir-danger">{i18n.t('legend.highMeansDanger')}</span>
				{:else}
					<span class="score-dir score-dir-good">{i18n.t('legend.highMeansGood')}</span>
				{/if}
			</div>
		{/if}

		{#if deptSummary}
			<div class="summary-cards">
				<div class="summary-card">
					<div class="card-value">{deptSummary.province.total_hexes?.toLocaleString()}</div>
					<div class="card-label">{i18n.t('section.zonesAnalyzed')}</div>
				</div>
			</div>
		{/if}

		<div class="dept-section">
			<div class="section-title">{i18n.t('analysis.flood.topDepts')}</div>
			{#if deptList.length === 0 && isPerDept}
				<div class="dept-row" style="color: var(--text-secondary); font-style: italic; padding: 8px 0;">
					{hexStore.territoryPrefix ? 'No hay datos departamentales para este territorio.' : 'Cargando…'}
				</div>
			{:else}
				{#if !selectedDpto}
					<p class="dept-select-hint">▼ Seleccioná un sector para ver el análisis</p>
				{/if}
				{#each deptList as dept}
					<button class="dept-row dept-clickable" onclick={() => handleDptoClick(dept)}>
						<div class="dept-name">{dept.dpto ?? dept.distrito}</div>
						<div class="dept-score">
							{dept.hex_count?.toLocaleString() ?? ''} hex
						</div>
					</button>
				{/each}
			{/if}
		</div>

		{#if content}
			<details class="method-details">
				<summary class="method-summary">{i18n.t('section.howToRead')}</summary>
				<div class="method-body">
					<p class="explain-text">{content.howToRead}</p>
				</div>
			</details>

			<details class="method-details">
				<summary class="method-summary">{i18n.t('section.implications')}</summary>
				<div class="method-body">
					<p class="explain-text">{content.implications}</p>
				</div>
			</details>

			<details class="method-details">
				<summary class="method-summary">{i18n.t('section.methodology')}</summary>
				<div class="method-body">
					<p class="explain-text">{content.method}</p>
					<div class="method-components">
						{#each componentVars as v}
							<div class="method-item">
								<span class="method-term">{i18n.t(v.labelKey)}</span>
							</div>
						{/each}
					</div>
				</div>
			</details>
		{/if}


		{#if freshness}
			<div class="source-note-box">
				<div><strong>{i18n.t('section.source')}:</strong> {i18n.t(freshness.sourceKey)}</div>
				<div><strong>{i18n.t('section.processed')}:</strong> {freshness.processedDate}</div>
			</div>
		{/if}

		<CTADiagnostic analysisName={i18n.t(analysis.titleKey)} />
	</div>

{:else}
	<!-- ═══ NON-perDepartment (Overture layers) ═══ -->
	<div class="view">
		<p class="desc">{i18n.t(analysis.descKey)}</p>

		{#if freshness}
			<div class="freshness">
				<span class="freshness-label">{i18n.t('data.updatedAt')}: {freshness.processedDate}</span>
				<span class="freshness-source">{i18n.t(freshness.sourceKey)}</span>
			</div>
		{/if}

		{#if loading}
			<div class="loading">{i18n.t('lens.loading')}</div>
		{:else if layerCfg}
			<div class="variables-hint">
				{#each layerCfg.variables as v}
					<div class="variable-tag">{i18n.t(v.labelKey)}</div>
				{/each}
			</div>

			{#if selectedHexes.size === 0}
				<p class="hint">{i18n.t('lens.selectRadio')}</p>
			{:else}
				<div class="selected-hexes">
					{#each [...selectedHexes] as [h3index, sel]}
						<div class="hex-card">
							<div class="hex-id">{h3index.slice(0, 4)}...{h3index.slice(-4)}</div>
							{#if analysis.id === 'sociodemographic' && componentVars.length > 0}
								{@const cardPetalVals = componentVars.map(v => { const n = Number(sel.data[v.col]); return Number.isFinite(n) ? Math.min(100, Math.max(0, n)) : 0; })}
								{@const cardPetalColor = getTypeColor(Number(sel.data['type']) || 1)}
								<div class="hex-petal">
									<PetalChart layers={[{values: cardPetalVals, color: cardPetalColor}]} labels={petalLabels} size={160} />
								</div>
							{/if}
							<div class="hex-values">
								{#each layerCfg.variables as v}
									{@const val = sel.data[v.col]}
									{#if val != null && !(v.hideIfZero && val === 0)}
										<div class="hex-val">
											<span class="hex-val-label">{i18n.t(v.labelKey)}</span>
											<span class="hex-val-num">{typeof val === 'number' ? (Number.isInteger(val) ? val.toLocaleString() : val.toFixed(1)) : val}</span>
										</div>
									{/if}
								{/each}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		{/if}
	</div>
{/if}

<style>
	.view { font-size: 11px; }
	.desc { color: #a3a3a3; margin: 0 0 8px; line-height: 1.4; }
	.score-info-box { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; padding: 5px 8px; background: rgba(255,255,255,0.04); border-radius: 4px; border: 1px solid rgba(255,255,255,0.06); }
	.score-range { font-size: 9px; color: #737373; font-weight: 600; }
	.score-dir { font-size: 9px; font-weight: 500; }
	.score-dir-danger { color: #f87171; }
	.score-dir-good { color: #4ade80; }
	.freshness { display: flex; flex-direction: column; gap: 2px; margin-bottom: 8px; padding: 4px 6px; background: rgba(255,255,255,0.03); border-radius: 4px; }
	.freshness-label { color: #737373; font-size: 9px; }
	.freshness-source { color: #525252; font-size: 9px; }
	.loading { color: #d4d4d4; font-size: 10px; text-align: center; padding: 20px 0; }
	.hint { font-size: 9px; color: #a3a3a3; text-align: center; margin-top: 8px; }

	/* ── Summary cards ── */
	.summary-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 12px; }
	.summary-card { background: rgba(100,116,139,0.08); border-radius: 6px; padding: 8px 6px; text-align: center; }
	.card-value { font-size: 15px; font-weight: 700; color: #e2e8f0; }
	.card-label { font-size: 8px; color: #d4d4d4; margin-top: 2px; }

	/* ── Department list ── */
	.dept-section { margin-bottom: 10px; }
	.section-title { font-size: 10px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px; }
	.dept-select-hint { font-size: 9px; color: #60a5fa; margin: 0 0 6px; font-style: italic; opacity: 0.8; }
	.dept-row { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
	.dept-clickable { background: none; border: none; width: 100%; padding: 4px 2px; border-radius: 4px; cursor: pointer; transition: background 0.15s; }
	.dept-clickable:hover { background: rgba(96,165,250,0.1); }
	.dept-name { font-size: 9px; color: #d4d4d4; width: 72px; text-align: left; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.dept-bar-wrap { flex: 1; height: 4px; background: rgba(100,116,139,0.15); border-radius: 2px; overflow: hidden; }
	.dept-bar { height: 100%; border-radius: 2px; transition: width 0.3s; }
	.dept-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
	.dept-score { font-size: 9px; font-weight: 600; min-width: 24px; text-align: right; }
	.dept-active-title { font-size: 14px; font-weight: 700; color: #e2e8f0; margin-bottom: 8px; }

	/* ── Navigation ── */
	.back-btn { background: none; border: none; color: #60a5fa; font-size: 10px; cursor: pointer; padding: 0; margin-bottom: 8px; }
	.back-btn:hover { text-decoration: underline; }

	/* ── Hex detail ── */
	.hex-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
	.hex-id { font-family: monospace; font-size: 10px; color: #d4d4d4; }
	.risk-badge { font-size: 9px; font-weight: 700; color: #000; padding: 2px 8px; border-radius: 9999px; }
	.score-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
	.score-label { font-size: 9px; color: #d4d4d4; white-space: nowrap; }
	.score-track { flex: 1; height: 6px; background: rgba(100,116,139,0.2); border-radius: 3px; overflow: hidden; }
	.score-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
	.score-value { font-size: 13px; font-weight: 700; min-width: 32px; text-align: right; }
	.petal-section { margin: 6px 0; }
	.petal-hint { font-size: 8px; color: rgba(255,255,255,0.35); text-align: center; margin: 2px 0 0; line-height: 1.3; }
	.census-detail { display: flex; flex-direction: column; gap: 4px; margin: 8px 0; }
	.cd-row { display: flex; align-items: center; gap: 6px; }
	.cd-label { font-size: 9px; color: #d4d4d4; flex: 0 0 auto; min-width: 100px; }
	.cd-bar-track { flex: 1; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden; }
	.cd-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; min-width: 2px; }
	.cd-val { font-size: 9px; font-weight: 600; color: #cbd5e1; width: 28px; text-align: right; flex-shrink: 0; }
	.cd-val-data { font-size: 10px; font-weight: 600; color: #e2e8f0; text-align: right; margin-left: auto; white-space: nowrap; }
	.petal-wrapper { display: flex; justify-content: center; margin: 0 auto; max-width: 260px; }

	/* Cross-analysis profile + type distribution + diagnostic */
	.cross-profile, .type-dist, .diagnostic { margin: 10px 0; padding: 8px 0; border-top: 1px solid rgba(255,255,255,0.06); }
	.cross-title { font-size: 9px; font-weight: 600; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }
	.cross-row { display: flex; align-items: center; gap: 6px; padding: 2px 0; font-size: 10px; }
	.cross-label { color: #737373; flex-shrink: 0; min-width: 90px; }
	.cross-value { color: #d4d4d4; font-weight: 500; }
	.type-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
	.action-row { display: flex; gap: 6px; margin: 10px 0; }
	.action-btn { flex: 1; padding: 6px 8px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 4px; color: #a3a3a3; font-size: 9px; cursor: pointer; transition: all 0.15s; }
	.action-btn:hover { background: rgba(255,255,255,0.08); color: #d4d4d4; }
	.detail-label { font-size: 9px; color: #d4d4d4; margin-bottom: 2px; }
	.detail-value { font-size: 14px; font-weight: 700; color: #e2e8f0; }
	.detail-desc { font-size: 8px; color: #a3a3a3; margin-top: 2px; }

	/* ── Legend ── */
	.flood-legend { margin: 12px 0; }
	.legend-title { font-size: 9px; font-weight: 600; color: #d4d4d4; margin-bottom: 4px; }
	.legend-bar { height: 8px; border-radius: 4px; }
	.legend-labels { display: flex; justify-content: space-between; font-size: 8px; color: #a3a3a3; margin-top: 2px; }

	/* ── Collapsibles ── */
	.method-details { margin-top: 10px; border: 1px solid rgba(100,116,139,0.15); border-radius: 6px; overflow: hidden; }
	.method-summary { font-size: 9px; font-weight: 600; color: #d4d4d4; padding: 6px 8px; cursor: pointer; user-select: none; list-style: none; display: flex; align-items: center; gap: 4px; }
	.method-summary::before { content: '\25B8'; font-size: 8px; transition: transform 0.15s; }
	.method-details[open] > .method-summary::before { transform: rotate(90deg); }
	.method-summary::-webkit-details-marker { display: none; }
	.method-body { padding: 4px 8px 8px; }
	.method-item { margin-bottom: 4px; }
	.method-term { font-size: 9px; font-weight: 600; color: #cbd5e1; }
	.explain-text { font-size: 9px; color: #a3a3a3; line-height: 1.5; margin: 2px 0 0; }
	.mini-legend { margin-top: 6px; }
	.method-components { margin-top: 6px; }

	/* ── Methodology link ── */
	.methodology-link { display: inline-block; font-size: 9px; color: #94a3b8; text-decoration: none; padding: 4px 0; margin: 4px 0 10px; transition: color 0.15s; }
	.methodology-link:hover { color: #60a5fa; text-decoration: underline; }

	/* ── Download button ── */
	.download-btn { display: block; text-align: center; padding: 6px 10px; margin: 0; background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3); border-radius: 4px; color: #60a5fa; font-size: 9px; font-weight: 600; text-decoration: none; transition: all 0.15s; cursor: pointer; font-family: inherit; }
	.download-btn:hover:not(:disabled) { background: rgba(59,130,246,0.25); border-color: rgba(59,130,246,0.5); }
	.download-btn:disabled { cursor: wait; opacity: 0.6; }
	.download-row { display: flex; gap: 6px; margin: 10px 0; }
	.download-row .download-btn { flex: 1; }
	.download-secondary { background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.15); color: #a3a3a3; }
	.download-secondary:hover:not(:disabled) { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.25); color: #d4d4d4; }
	.download-date { font-weight: 400; font-size: 8px; opacity: 0.7; }

	/* ── Source box ── */
	.source-note-box { margin-top: 10px; padding: 8px 10px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; font-size: 9px; color: #e2e8f0; line-height: 1.5; }
	.source-note-box strong { color: #f8fafc; }

	/* ── Non-perDept hex cards ── */
	.variables-hint { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
	.variable-tag { background: rgba(255,255,255,0.06); color: #d4d4d4; padding: 2px 6px; border-radius: 3px; font-size: 9px; }
	.selected-hexes { display: flex; flex-direction: column; gap: 6px; }
	.hex-card { background: rgba(255,255,255,0.04); border-radius: 6px; padding: 6px 8px; }
	.hex-petal { margin: 4px 0 6px; }
	.hex-values { display: flex; flex-direction: column; gap: 2px; }
	.hex-val { display: flex; justify-content: space-between; align-items: baseline; }
	.hex-val-label { color: #a3a3a3; }
	.hex-val-num { color: #e5e5e5; font-weight: 500; font-variant-numeric: tabular-nums; }

	/* ── Temporal toggle ── */
	.temporal-toggle { display: flex; gap: 0; margin-bottom: 10px; border-radius: 6px; overflow: hidden; border: 1px solid rgba(100,116,139,0.2); }
	.temporal-toggle button { flex: 1; background: rgba(255,255,255,0.03); border: none; color: #a3a3a3; font-size: 9px; font-weight: 500; padding: 5px 4px; cursor: pointer; transition: all 0.15s; }
	.temporal-toggle button:not(:last-child) { border-right: 1px solid rgba(100,116,139,0.15); }
	.temporal-toggle button.active { background: rgba(59,130,246,0.15); color: #60a5fa; font-weight: 700; }
	.temporal-toggle button:hover:not(.active) { background: rgba(255,255,255,0.06); }
</style>
