<script lang="ts">
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import CTADiagnostic from '$lib/components/CTADiagnostic.svelte';
	import PetalChart from '$lib/components/PetalChart.svelte';
	import { HEX_LAYER_REGISTRY, DATA_FRESHNESS, getSatDptoUrl, getFloodDptoUrl, getScoresDptoUrl, getReportUrl, getTemporalCol, type AnalysisConfig, type TemporalMode } from '$lib/config';
	import { initDuckDB, query } from '$lib/stores/duckdb';

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
	const CENSUS_ANALYSES = new Set(['service_deprivation', 'health_access', 'education_capital', 'education_flow', 'sociodemographic', 'economic_activity', 'accessibility']);

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
	};

	$effect(() => {
		if (!isPerDept || !layerCfg) return;
		const loader = SAT_SUMMARIES[layerCfg.id];
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
			if (score >= 70) return '#dc2626';
			if (score >= 40) return '#eab308';
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
			onSelectDpto(dept.dpto, dept.parquetKey, dept.centroid as [number, number]);
		}
	}

	function handleBackToDepts() {
		hexStore.setLayer(analysis.id);
	}

	async function downloadCsv() {
		if (!dataUrl) return;
		try {
			await initDuckDB();
			const result = await query(`SELECT * FROM '${dataUrl}'`);
			const cols = result.schema.fields.map((f: any) => f.name);
			let csv = cols.join(',') + '\n';
			for (let i = 0; i < result.numRows; i++) {
				const row = result.get(i)!.toJSON() as Record<string, any>;
				csv += cols.map(c => row[c] ?? '').join(',') + '\n';
			}
			const blob = new Blob([csv], { type: 'text/csv' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			const dept = deptList.find((d: any) => d.dpto === selectedDpto);
			a.href = url;
			a.download = `spatia_${layerCfg?.id}_${dept?.parquetKey || 'data'}.csv`;
			a.click();
			URL.revokeObjectURL(url);
		} catch (e) {
			console.warn('CSV download failed:', e);
		}
	}

	// Data download URL for selected department
	const dataUrl = $derived.by(() => {
		if (!selectedDpto || !layerCfg || !deptList.length) return null;
		const dept = deptList.find((d: any) => d.dpto === selectedDpto);
		if (!dept) return null;
		return getSatDptoUrl(layerCfg.id, dept.parquetKey);
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

		const dept = deptList.find((d: any) => d.dpto === dpto);
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
		const dept = deptList.find((d: any) => d.dpto === selectedDpto);
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
		const dept = deptList.find((d: any) => d.dpto === selectedDpto);
		if (!dept) return null;
		return getReportUrl(layerCfg.id, dept.parquetKey);
	});

	// ── Explanatory content per analysis ──
	const METHOD_COMMON = 'Clasificacion por PCA (analisis de componentes principales) seguido de k-means clustering sobre las variables estandarizadas. Cada hexagono se asigna al tipo cuyo centroide multivariado es mas cercano. La validacion se realiza mediante coeficiente de silueta.';

	const ANALYSIS_CONTENT: Record<string, { howToRead: string; implications: string; method: string }> = {
		flood_risk: {
			howToRead: 'Los colores representan el riesgo hidrico de cada hexagono, combinando la presencia historica de agua (JRC, 1984–2021) y la deteccion actual de inundacion (Sentinel-1 SAR). Azul oscuro = riesgo bajo; amarillo = riesgo medio; rojo = riesgo alto. Selecciona un departamento para ver el detalle.',
			implications: 'Las zonas de riesgo alto pueden enfrentar anegamientos recurrentes, afectando el valor inmobiliario, la habitabilidad y la infraestructura de servicios basicos (agua, cloacas). La recurrencia interanual distingue inundaciones estacionales predecibles de eventos extremos esporadicos.',
			method: 'Indice compuesto 0–100: 50% presencia historica de agua (JRC Global Surface Water, Landsat 1984–2021) + 20% recurrencia interanual (JRC) + 30% extension actual (Sentinel-1 SAR, ultima imagen procesada). Fuentes: JRC v1.4 + Copernicus Sentinel-1. Resolucion: H3 resolucion 9.',
		},
		territorial_scores: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de consolidacion urbana segun 8 indicadores derivados de Overture Maps: pavimentacion, consolidacion, acceso a servicios, vitalidad comercial, conectividad vial, mezcla edilicia, urbanizacion y exposicion hidrica. Cada color representa un perfil urbano distinto.',
			implications: 'Los tipos permiten distinguir nucleos urbanos consolidados, periferias en expansion con servicios incompletos, y zonas rurales sin infraestructura urbana. La clasificacion multivariada evita reducir la complejidad urbana a un unico indicador de "desarrollo".',
			method: `${METHOD_COMMON} 8 variables: paving_index, urban_consolidation, service_access, commercial_vitality, road_connectivity, building_mix, urbanization, water_exposure. Fuente: Overture Maps Foundation (CC BY 4.0, release 2026-03-18) via walkthru.earth. k=5 tipos.`,
		},
		environmental_risk: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de riesgo ambiental segun la co-ocurrencia de deforestacion, amplitud termica, pendiente y altura sobre drenaje. Cada color representa un tipo distinto de configuracion de riesgo.',
			implications: 'Los tipos permiten identificar configuraciones de riesgo cualitativamente distintas: zonas de alta pendiente con baja deforestacion difieren estructuralmente de zonas planas con alta perdida forestal, aunque ambas puedan tener "riesgo" similar en un indice unico.',
			method: `${METHOD_COMMON} Variables: deforestacion Hansen GFC, amplitud termica LST MODIS, pendiente FABDEM 30m, HAND MERIT Hydro. k=5 tipos, silueta=0.33.`,
		},
		climate_comfort: {
			howToRead: 'El mapa clasifica cada hexagono en tipos climaticos segun la co-ocurrencia de temperatura diurna, nocturna, precipitacion, heladas y estres hidrico. Cada color representa un regimen climatico distinto.',
			implications: 'Los tipos climaticos revelan gradientes territoriales que un indice unico no captura: zonas calidas y humedas difieren estructuralmente de zonas frescas y secas, con implicancias distintas para habitabilidad y produccion.',
			method: `${METHOD_COMMON} Variables: LST diurno/nocturno MODIS, precipitacion CHIRPS, heladas ERA5, ratio ET/PET MODIS. k=4 tipos, silueta=0.40.`,
		},
		green_capital: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de capital verde segun la co-ocurrencia de verdor, cobertura arborea, productividad primaria, area foliar y fraccion de vegetacion. Cada color representa un estado ecosistemico distinto.',
			implications: 'Los tipos distinguen selva densa de alta productividad, bosque secundario con cobertura residual, y zonas deforestadas con baja vegetacion. Esta distincion cualitativa informa mejor las politicas de conservacion que un gradiente continuo.',
			method: `${METHOD_COMMON} Variables: NDVI MODIS 250m, cobertura arborea Hansen 2000, NPP MODIS, LAI MODIS, VCF MODIS. k=3 tipos, silueta=0.46.`,
		},
		change_pressure: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de presion de cambio segun la co-ocurrencia de tendencia de urbanizacion, expansion construida, perdida forestal y cambio de vegetacion.',
			implications: 'Los tipos separan urbanizacion activa de deforestacion agricola y de zonas estables. Un municipio con "alta presion" por urbanizacion requiere politicas distintas a uno con "alta presion" por avance de frontera agraria.',
			method: `${METHOD_COMMON} Variables: tendencia VIIRS 2016-2025, cambio GHSL 2000-2020, perdida Hansen, tendencia NDVI. k=5 tipos, silueta=0.34.`,
		},
		location_value: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de valor posicional segun la co-ocurrencia de accesibilidad, conectividad a salud, actividad economica, topografia y distancia a rutas.',
			implications: 'Los tipos distinguen nucleos urbanos bien conectados, periferias accesibles pero poco activas, y zonas rurales aisladas. El valor posicional emergente de la clasificacion es mas informativo que un ranking lineal.',
			method: `${METHOD_COMMON} Variables: tiempo a ciudad 20k Nelson, acceso a salud Oxford, radiancia VIIRS, pendiente FABDEM, distancia a ruta OSM. k=4 tipos, silueta=0.43.`,
		},
		agri_potential: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de aptitud agricola segun la co-ocurrencia de calidad del suelo, regimen hidrico, acumulacion termica y topografia.',
			implications: 'Los tipos reflejan configuraciones edafoclimaticas distintas: suelos acidos con alta lluvia (aptitud para yerba mate), suelos neutros con calor acumulado (aptitud para tabaco/citricos), y zonas con limitaciones multiples.',
			method: `${METHOD_COMMON} Variables: carbono organico SoilGrids, pH optimo, arcilla, precipitacion CHIRPS, GDD ERA5, pendiente FABDEM. k=3 tipos, silueta=0.32.`,
		},
		forest_health: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de integridad forestal segun la co-ocurrencia de tendencia de verdor, perdida arborea, productividad fotosintetica y evapotranspiracion.',
			implications: 'Los tipos separan bosque sano y productivo, bosque en degradacion con perdida activa, y zonas sin cobertura forestal significativa. Esta clasificacion permite priorizar intervenciones de restauracion donde la degradacion es incipiente.',
			method: `${METHOD_COMMON} Variables: tendencia NDVI 5 anos, ratio perdida/cobertura Hansen, GPP MODIS, ET MODIS. k=4 tipos, silueta=0.38.`,
		},
		forestry_aptitude: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de aptitud forestal comercial segun la co-ocurrencia de acidez del suelo, precipitacion, pendiente, y accesibilidad logistica.',
			implications: 'Los tipos identifican zonas optimas para plantaciones de pino/eucalipto (suelo acido, lluvia suficiente, pendiente mecanizable, cerca de rutas) frente a zonas marginales donde la forestacion comercial no es viable. Este analisis evalua aptitud del suelo y clima — no reemplaza la verificacion de restricciones legales (areas protegidas, comunidades indigenas, Ley de Bosques 26.331).',
			method: `${METHOD_COMMON} Variables: pH SoilGrids, arcilla, precipitacion CHIRPS, pendiente FABDEM, distancia a ruta OSM, accesibilidad Nelson. k=3 tipos, silueta=0.33.`,
		},
		service_deprivation: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de carencia de servicios basicos segun NBI, acceso a cloacas, calidad del piso, hacinamiento y acceso digital. Solo se muestran hexagonos con edificaciones detectadas (crosswalk dasimetrico). Cada color representa un perfil de carencia distinto.',
			implications: 'Los tipos separan carencia habitacional (piso inadecuado + hacinamiento), carencia de infraestructura (sin cloacas), y brecha digital (sin computadora). Cada configuracion demanda intervenciones distintas: vivienda social, extension de red cloacal, o programas de inclusion digital.',
			method: `${METHOD_COMMON} 6 variables Censo Nacional 2022 (INDEC): NBI, sin cloacas (100 - pct_cloacas), piso inadecuado, hacinamiento, hacinamiento critico, sin computadora (100 - pct_computadora). Crosswalk dasimetrico ponderado por edificios (2.8M footprints). KMO=0.73.`,
		},
		territorial_isolation: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de aislamiento territorial segun tiempo de viaje a ciudades y centros de salud, distancia a rutas, densidad vial, luces nocturnas y densidad poblacional. Cobertura completa de la provincia (crosswalk hibrido).',
			implications: 'Los tipos distinguen aislamiento por distancia (lejos de rutas y ciudades), aislamiento funcional (cerca de ruta pero sin servicios), y conectividad plena. Las zonas aisladas enfrentan costos de transporte, acceso limitado a salud y educacion, y menor oportunidad economica.',
			method: `${METHOD_COMMON} 6 variables: acceso a ciudades y salud (Oxford MAP 2019, friccion motorizada), distancia a ruta primaria y densidad vial (OSM), radiancia VIIRS 2022-2024, densidad poblacional Censo 2022. Crosswalk hibrido (dasimetrico + areal). KMO=0.87.`,
		},
		health_access: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de acceso a salud segun tiempo al centro de salud, cobertura sanitaria, vulnerabilidad social (NBI), presion demografica (ancianos y menores) y densidad poblacional. Solo hexagonos con edificaciones.',
			implications: 'Los tipos separan deficit por distancia (zonas rurales lejanas), deficit por saturacion (zonas densas con alta proporcion de poblacion vulnerable), y deficit por cobertura (alto NBI con baja cobertura sanitaria). Cada configuracion requiere respuestas distintas del sistema de salud.',
			method: `${METHOD_COMMON} 6 variables: tiempo motorizado a salud (Oxford MAP 2019), cobertura sanitaria, NBI, % adultos mayores, % menores 18, densidad poblacional (Censo 2022). Crosswalk dasimetrico. KMO=0.60.`,
		},
		education_capital: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de capital educativo segun el nivel de instruccion acumulado: sin instruccion, secundario completo o mas, educacion superior (terciario + universitario), y universitario. Solo hexagonos con edificaciones.',
			implications: 'Los tipos distinguen zonas con alto capital humano (universidades cercanas, alta formacion), zonas de educacion media (secundario completo pero sin terciario), y zonas de bajo capital (alta proporcion sin instruccion). El capital educativo es predictor de ingresos, salud y participacion civica.',
			method: `${METHOD_COMMON} 4 variables Censo 2022: % sin instruccion, % secundario completo o mas (umbral acumulativo), % educacion superior (terciario + universitario), % universitario. Terciario y universitario son tracks paralelos en el sistema argentino. Crosswalk dasimetrico. KMO=0.71.`,
		},
		education_flow: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de desempeno del sistema educativo segun inasistencia escolar primaria (6-12), secundaria (13-18) y maternidad adolescente. Solo hexagonos con edificaciones.',
			implications: 'Los tipos separan desercion temprana (primaria), desercion tardia (secundaria) y embarazo adolescente como factor de exclusion educativa. La inasistencia primaria indica fallas basicas del sistema; la secundaria indica problemas de retencion; la maternidad adolescente indica vulnerabilidad de genero intersectada con pobreza.',
			method: `${METHOD_COMMON} 3 variables Censo 2022: tasa de inasistencia 6-12 anos, tasa de inasistencia 13-18 anos, tasa de maternidad adolescente. Variables directas (mayor = peor flujo). Crosswalk dasimetrico. KMO=0.61.`,
		},
		land_use: {
			howToRead: 'El mapa clasifica cada hexagono segun su cobertura dominante: selva nativa, plantacion forestal, pastizal, agricultura, agua o urbano. La fuente es MapBiomas Argentina (Landsat 30m, 2022) que distingue bosque nativo de silvicultura.',
			implications: 'La separacion entre selva nativa (73%) y plantacion forestal (12%) permite evaluar el estado de conservacion real: los pinares/eucaliptos no son selva paranaense aunque Dynamic World los clasifique igual. Los mosaicos agropecuarios indican zonas de transicion activa.',
			method: `${METHOD_COMMON} Fuente: MapBiomas Argentina Collection 1 (Landsat 30m, 2022). Clases remapeadas: bosque nativo, plantacion, pastizal, agricultura, mosaico, humedal, urbano, agua. k=6 tipos, silueta=0.62.`,
		},
		powerline_density: {
			howToRead: 'Mapa de densidad de lineas de media y alta tension. Hexagonos mas claros = mayor densidad de infraestructura electrica. Score basado en longitud total y cantidad de lineas dentro de cada hexagono.',
			implications: 'La cobertura electrica condiciona toda actividad productiva y residencial. Zonas con baja densidad de lineas requieren extension de red para habilitar nuevos emprendimientos. La distancia a lineas existentes es el principal factor de costo de electrificacion rural.',
			method: 'Fuente: EMSA (Secretaria de Energia, datos.energia.gob.ar, abril 2024). Lineas de media y alta tension georreferenciadas, intersectadas con grilla H3 resolucion 9. Score = longitud total de lineas / area del hexagono, normalizado 0-100.',
		},
		territorial_types: {
			howToRead: 'El mapa clasifica cada hexagono en tipos territoriales segun su metabolismo ecosistemico: productividad, apropiacion humana y dinamica de cambio. Cada color representa un tipo cualitativamente distinto de territorio.',
			implications: 'Los tipos territoriales sintetizan 13 variables satelitales en una clasificacion interpretable. Permiten identificar selva productiva intacta, mosaicos agro-forestales en transicion, zonas agricolas consolidadas, periurbanos en expansion y nucleos urbanos — cada uno con necesidades de gestion distintas.',
			method: `${METHOD_COMMON} 13 variables: NPP, NDVI, cobertura arborea, fraccion arboles/cultivos/construido, deforestacion, luces nocturnas, tendencia VIIRS, expansion GHSL, precipitacion. k=8 tipos. Fuentes: MODIS, Hansen GFC, VIIRS, GHSL, CHIRPS.`,
		},
		sociodemographic: {
			howToRead: 'El mapa clasifica cada hexagono en tipos sociodemograficos segun la co-ocurrencia de densidad poblacional, pobreza (NBI), hacinamiento, tenencia de vivienda, tamano de hogar y acceso digital. Cada color representa un perfil censal distinto.',
			implications: 'Los tipos distinguen zonas urbanas densas con bajo NBI, periferias con hacinamiento y pobreza, y zonas rurales dispersas con alta propiedad pero baja conectividad. Esta clasificacion multivariada evita reducir la complejidad social a un solo indicador.',
			method: `${METHOD_COMMON} 6 variables del Censo Nacional 2022 (INDEC): densidad hab/km2, % NBI, % hacinamiento, % propietarios, tamano medio hogar, % computadora. Variables a nivel radio censal, agregadas a H3 via crosswalk ponderado por area.`,
		},
		economic_activity: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de actividad economica segun la co-ocurrencia de empleo, actividad economica, formacion universitaria, luces nocturnas y densidad edilicia. Cada color representa un nivel de dinamismo distinto.',
			implications: 'Los tipos separan centros economicos consolidados (alto empleo + universitarios + luces), periferias activas con posible informalidad (alta actividad, bajo empleo formal), y zonas rurales de baja actividad economica. La radiancia nocturna (VIIRS) es un proxy robusto de actividad que complementa los datos censales.',
			method: `${METHOD_COMMON} 5 variables: tasa de empleo y actividad (Censo 2022 INDEC, 14+ anos), % universitarios (Censo 2022), radiancia media VIIRS 500m (2022-2024), densidad edilicia Global Building Atlas 2025. Variables censales agregadas a H3 via crosswalk.`,
		},
		eudr: {
			howToRead: 'El mapa muestra el riesgo de deforestacion post-2020 por hexagono (H3 res-7, ~5 km2). Score alto (rojo) = mayor perdida forestal o actividad de fuego despues del cutoff EUDR (31/12/2020). Cobertura: 10 provincias del NOA y NEA argentino.',
			implications: 'Hexagonos con deforestacion post-2020 representan riesgo de no-conformidad bajo la Regulacion (UE) 2023/1115. Exportaciones de commodities (soja, carne, madera) originados en estas zonas requieren due diligence reforzado. Este analisis es orientativo — la verificacion formal requiere geometria parcelaria exacta.',
			method: 'Score compuesto 0-100: 70% perdida forestal post-2020 (Hansen GFC v1.12, Landsat 30m) + 20% area quemada post-2020 (MODIS MCD64A1, 500m) + 10% perdida de cobertura previa. Cutoff EUDR: 31/12/2020. Resolucion espacial: H3 resolucion 7 (~5.16 km2). Cobertura: Salta, Jujuy, Tucuman, Catamarca, Sgo. del Estero, Formosa, Chaco, Corrientes, Misiones, Entre Rios.',
		},
		accessibility: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de accesibilidad segun la co-ocurrencia de tiempo de viaje a Posadas, a la cabecera departamental, distancia a hospital, escuela secundaria y ruta principal. Cada color representa un nivel de conectividad distinto.',
			implications: 'Los tipos distinguen conectividad plena (cercania a servicios y rutas), accesibilidad parcial (cerca de ruta pero lejos de servicios especializados), y aislamiento funcional (lejos de todo). Cada configuracion requiere estrategias de inversion en infraestructura distintas.',
			method: `${METHOD_COMMON} 5 variables: tiempo motorizado a Posadas y cabecera (Nelson et al. 2019, superficie de friccion Oxford MAP), distancia euclidiana a hospital, escuela secundaria y ruta primaria (OSM). Fuente: Nelson 2019 + Oxford MAP 2019 + OSM.`,
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
</script>

{#if selectedHex && selectedDpto && isPerDept}
	<!-- ═══ HEX DETAIL VIEW ═══ -->
	<div class="view">
		<button class="back-btn" onclick={handleBackToDepts}>{i18n.t('analysis.flood.topDepts')}</button>

		<div class="hex-header">
			<div class="hex-id" title={selectedHex.h3index}>
				{selectedHex.h3index.slice(0, 4)}...{selectedHex.h3index.slice(-4)}
			</div>
			{#if isCategorical}
				<div class="risk-badge" style:background={getTypeColor(selectedHex.type ?? 1)}>
					{selectedHex.type_label ?? `Tipo ${selectedHex.type ?? '?'}`}
				</div>
			{:else}
				<div class="risk-badge" style:background={getScoreColor(displayScore)}>
					{getScoreLevel(displayScore)}
				</div>
			{/if}
		</div>

		{#if hexPetalLayers.length > 0 && !CENSUS_ANALYSES.has(analysis.id)}
			<div class="petal-section">
				<div class="petal-wrapper">
					<PetalChart layers={hexPetalLayers} labels={petalLabels} size={240} />
				</div>
				<p class="petal-hint">{i18n.t('analysis.petalHint')}</p>
			</div>
		{:else if CENSUS_ANALYSES.has(analysis.id) && componentVars.length > 0}
			<div class="census-detail">
				{#each componentVars as v}
					{@const val = selectedHex[v.col]}
					{@const numVal = typeof val === 'number' ? val : 0}
					<div class="cd-row">
						<span class="cd-label">{i18n.t(v.labelKey)}</span>
						<div class="cd-bar-track">
							<div class="cd-bar-fill" style:width="{Math.min(100, Math.max(0, numVal))}%" style:background={numVal > 66 ? '#ef4444' : numVal > 33 ? '#eab308' : '#22c55e'}></div>
						</div>
						<span class="cd-val">{numVal.toFixed(0)}</span>
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
			<a class="action-btn" href="mailto:spatia.unused740@passinbox.com?subject=Solicitud%20de%20informe%20{selectedDpto}%20-%20{analysis.id}&body=Solicito%20informe%20territorial%20para%20el%20departamento%20{selectedDpto}%20en%20el%20analisis%20{analysis.id}." style="text-align:center;text-decoration:none;">{i18n.t('section.requestReport')}</a>
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
			{#each deptList as dept}
				<button class="dept-row dept-clickable" onclick={() => handleDptoClick(dept)}>
					<div class="dept-name">{dept.dpto}</div>
					<div class="dept-score">
						{dept.hex_count?.toLocaleString() ?? ''} hex
					</div>
				</button>
			{/each}
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
							<div class="hex-values">
								{#each layerCfg.variables as v}
									{@const val = sel.data[v.col]}
									{#if val != null}
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

	/* ── Download button ── */
	.download-btn { display: block; text-align: center; padding: 8px 12px; margin: 10px 0; background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3); border-radius: 6px; color: #60a5fa; font-size: 10px; font-weight: 600; text-decoration: none; transition: all 0.15s; cursor: pointer; }
	.download-btn:hover { background: rgba(59,130,246,0.25); border-color: rgba(59,130,246,0.5); }
	.download-row { display: flex; gap: 6px; margin: 10px 0; }
	.download-row .download-btn { flex: 1; }
	.download-secondary { background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.15); color: #a3a3a3; }
	.download-secondary:hover { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.25); color: #d4d4d4; }
	.download-date { font-weight: 400; font-size: 8px; opacity: 0.7; }

	/* ── Source box ── */
	.source-note-box { margin-top: 10px; padding: 8px 10px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; font-size: 9px; color: #e2e8f0; line-height: 1.5; }
	.source-note-box strong { color: #f8fafc; }

	/* ── Non-perDept hex cards ── */
	.variables-hint { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
	.variable-tag { background: rgba(255,255,255,0.06); color: #d4d4d4; padding: 2px 6px; border-radius: 3px; font-size: 9px; }
	.selected-hexes { display: flex; flex-direction: column; gap: 6px; }
	.hex-card { background: rgba(255,255,255,0.04); border-radius: 6px; padding: 6px 8px; }
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
