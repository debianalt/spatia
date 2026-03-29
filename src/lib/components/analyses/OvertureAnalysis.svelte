<script lang="ts">
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import CTADiagnostic from '$lib/components/CTADiagnostic.svelte';
	import PetalChart from '$lib/components/PetalChart.svelte';
	import { HEX_LAYER_REGISTRY, DATA_FRESHNESS, getTemporalCol, type AnalysisConfig, type TemporalMode } from '$lib/config';
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
		isolation_index: () => import('$lib/data/sat_isolation_index_dept_summary.json'),
		territorial_gap: () => import('$lib/data/sat_territorial_gap_dept_summary.json'),
		health_access: () => import('$lib/data/sat_health_access_dept_summary.json'),
		education_gap: () => import('$lib/data/sat_education_gap_dept_summary.json'),
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
		if (score >= 70) return '#b2182b';
		if (score >= 40) return '#d6604d';
		if (score >= 20) return '#92c5de';
		return '#2166ac';
	}

	function getScoreLevel(score: number): string {
		if (score >= 70) return 'Alto';
		if (score >= 40) return 'Medio';
		if (score >= 20) return 'Bajo';
		return 'Muy bajo';
	}

	const legendGradient = $derived(
		colorScale === 'flood'
			? 'linear-gradient(to right, #3b82f6, #eab308, #dc2626)'
			: 'linear-gradient(to right, #2166ac, #f7f7f7, #b2182b)'
	);

	const legendLabels = $derived(
		colorScale === 'flood'
			? ['Bajo', 'Medio', 'Alto']
			: ['Bajo', 'Medio', 'Alto']
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
		return `https://pub-580c676bec7f4eeb96d7d30559a3cab7.r2.dev/data/sat_dpto/sat_${layerCfg.id}_${dept.parquetKey}.parquet`;
	});

	// Component variables (skip score, type, type_label, pca)
	const componentVars = $derived(
		layerCfg?.variables.filter(v =>
			!['score', 'type', 'type_label', 'pca_1', 'pca_2'].includes(v.col)
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

	// PDF report URL for selected department
	const reportUrl = $derived.by(() => {
		if (!selectedDpto || !layerCfg || !deptList.length) return null;
		const dept = deptList.find((d: any) => d.dpto === selectedDpto);
		if (!dept) return null;
		return `https://pub-580c676bec7f4eeb96d7d30559a3cab7.r2.dev/data/reports/sat_${layerCfg.id}_${dept.parquetKey}.pdf`;
	});

	// ── Explanatory content per analysis ──
	const METHOD_COMMON = 'Clasificacion por PCA (analisis de componentes principales) seguido de k-means clustering sobre las variables estandarizadas. Cada hexagono se asigna al tipo cuyo centroide multivariado es mas cercano. La validacion se realiza mediante coeficiente de silueta.';

	const ANALYSIS_CONTENT: Record<string, { howToRead: string; implications: string; method: string }> = {
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
			implications: 'Los tipos identifican zonas optimas para plantaciones de pino/eucalipto (suelo acido, lluvia suficiente, pendiente mecanizable, cerca de rutas) frente a zonas marginales donde la forestacion comercial no es viable.',
			method: `${METHOD_COMMON} Variables: pH SoilGrids, arcilla, precipitacion CHIRPS, pendiente FABDEM, distancia a ruta OSM, accesibilidad Nelson. k=3 tipos, silueta=0.33.`,
		},
		isolation_index: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de aislamiento territorial segun la co-ocurrencia de tiempo de viaje a centros urbanos, densidad vial, actividad economica nocturna y friccion de desplazamiento.',
			implications: 'Los tipos distinguen aislamiento por distancia (lejos de ciudades pero con rutas), aislamiento por friccion (terreno dificil aunque cercano), y conectividad plena. Cada tipo requiere estrategias de acceso distintas.',
			method: `${METHOD_COMMON} Variables: tiempo a ciudad 100k Nelson, tiempo a Posadas, densidad vial OSM, radiancia VIIRS, friccion Oxford. k=4 tipos, silueta=0.45.`,
		},
		health_access: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de acceso a salud segun la co-ocurrencia de tiempo al centro de salud, densidad poblacional, cobertura sanitaria y vulnerabilidad social.',
			implications: 'Los tipos separan deficit por distancia (zonas rurales lejanas al hospital), deficit por saturacion (zonas densas con demanda excesiva), y deficit por vulnerabilidad (zonas con alto NBI aunque cercanas a servicios).',
			method: `${METHOD_COMMON} Variables: tiempo motorizado y a pie a salud Oxford MAP, densidad poblacional, cobertura sanitaria, NBI Censo 2022. k=5 tipos, silueta=0.33.`,
		},
		education_gap: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de brecha educativa segun la co-ocurrencia de poblacion sin instruccion, desercion adolescente, nivel educativo maximo y aislamiento territorial.',
			implications: 'Los tipos distinguen brecha por pobreza educativa (alta desercion + sin instruccion), brecha por aislamiento (lejos de instituciones terciarias), y zonas con alta formacion universitaria. Cada configuracion demanda intervenciones diferentes.',
			method: `${METHOD_COMMON} Variables: sin instruccion Censo 2022, desercion 13-18, solo primaria, universitarios, aislamiento Nelson. k=4 tipos, silueta=0.35.`,
		},
		land_use: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de cobertura del suelo segun la co-ocurrencia de las 9 fracciones de uso: bosque, cultivos, pasturas, construido, agua, arbustos, inundable, desnudo y otros.',
			implications: 'Los tipos separan bosque dominante (72% de Misiones), paisaje abierto agropecuario, cuerpos de agua, y nucleos urbanos. Esta clasificacion reemplaza el indice de Shannon con una tipologia directamente interpretable.',
			method: `${METHOD_COMMON} Fuente: Dynamic World v1 (Sentinel-2, 10m, 2024). 9 fracciones de cobertura. k=4 tipos, silueta=0.52.`,
		},
		territorial_gap: {
			howToRead: 'El mapa clasifica cada hexagono en tipos de brecha territorial segun la co-ocurrencia de actividad economica, pobreza, acceso a agua, cloacas y aislamiento.',
			implications: 'Los tipos separan urbanizacion sin servicios (luces nocturnas pero sin cloacas), pobreza rural estructural (alto NBI + aislamiento), y zonas con servicios consolidados. La clasificacion multivariada evita confundir causas distintas de desigualdad.',
			method: `${METHOD_COMMON} Variables: radiancia VIIRS, NBI Censo 2022, acceso a agua y cloacas Censo 2022, aislamiento Nelson. k=4 tipos, silueta=0.31.`,
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

	const displayScore = $derived(selectedHex ? (getDisplayVal(selectedHex, 'score') ?? 0) : 0);
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

		{#if hexPetalLayers.length > 0}
			<div class="petal-section">
				<div class="petal-wrapper">
					<PetalChart layers={hexPetalLayers} labels={petalLabels} size={240} />
				</div>
			</div>
		{/if}

		{#if freshness}
			<div class="source-note-box">
				<div><strong>Fuente:</strong> {i18n.t(freshness.sourceKey)}</div>
				<div><strong>Procesado:</strong> {freshness.processedDate}</div>
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

		{#if reportUrl}
			<div class="download-row">
				<a class="download-btn" href={reportUrl} target="_blank" rel="noopener">
					Informe PDF <span class="download-date">({freshness?.processedDate})</span>
				</a>
				{#if dataUrl}
					<button class="download-btn download-secondary" onclick={downloadCsv}>
						Datos (CSV)
					</button>
				{/if}
			</div>
		{/if}

		{#if content}
			<details class="method-details">
				<summary class="method-summary">Como leer este mapa</summary>
				<div class="method-body">
					<p class="explain-text">{content.howToRead}</p>
				</div>
			</details>
			<details class="method-details">
				<summary class="method-summary">Implicancias</summary>
				<div class="method-body">
					<p class="explain-text">{content.implications}</p>
				</div>
			</details>
			<details class="method-details">
				<summary class="method-summary">Metodologia</summary>
				<div class="method-body">
					<p class="explain-text">{content.method}</p>
				</div>
			</details>
		{/if}

		{#if freshness}
			<div class="source-note-box">
				<div><strong>Fuente:</strong> {i18n.t(freshness.sourceKey)}</div>
				<div><strong>Procesado:</strong> {freshness.processedDate}</div>
			</div>
		{/if}
	</div>

{:else if isPerDept}
	<!-- ═══ DEPARTMENT LIST ═══ -->
	<div class="view">
		<p class="desc">{i18n.t(analysis.descKey)}</p>

		{#if deptSummary}
			<div class="summary-cards">
				<div class="summary-card">
					<div class="card-value">{deptSummary.province.total_hexes?.toLocaleString()}</div>
					<div class="card-label">Zonas analizadas</div>
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
				<summary class="method-summary">Como leer este mapa</summary>
				<div class="method-body">
					<p class="explain-text">{content.howToRead}</p>
				</div>
			</details>

			<details class="method-details">
				<summary class="method-summary">Implicancias</summary>
				<div class="method-body">
					<p class="explain-text">{content.implications}</p>
				</div>
			</details>

			<details class="method-details">
				<summary class="method-summary">Metodologia</summary>
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
				<div><strong>Fuente:</strong> {i18n.t(freshness.sourceKey)}</div>
				<div><strong>Procesado:</strong> {freshness.processedDate}</div>
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
	.petal-wrapper { display: flex; justify-content: center; margin: 0 auto; max-width: 260px; }
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
