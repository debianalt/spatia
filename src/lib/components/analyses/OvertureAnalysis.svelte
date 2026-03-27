<script lang="ts">
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import CTADiagnostic from '$lib/components/CTADiagnostic.svelte';
	import { HEX_LAYER_REGISTRY, DATA_FRESHNESS, type AnalysisConfig } from '$lib/config';
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

	function getScoreColor(score: number): string {
		if (colorScale === 'flood') {
			// Blue → yellow → red (risk: high = bad)
			if (score >= 70) return '#dc2626';
			if (score >= 40) return '#eab308';
			return '#3b82f6';
		}
		// Blue → white → red (sequential: high = intense)
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

	// Component variables (skip 'score' itself)
	const componentVars = $derived(
		layerCfg?.variables.filter(v => v.col !== 'score') ?? []
	);

	// PDF report URL for selected department
	const reportUrl = $derived.by(() => {
		if (!selectedDpto || !layerCfg || !deptList.length) return null;
		const dept = deptList.find((d: any) => d.dpto === selectedDpto);
		if (!dept) return null;
		return `https://pub-580c676bec7f4eeb96d7d30559a3cab7.r2.dev/data/reports/sat_${layerCfg.id}_${dept.parquetKey}.pdf`;
	});

	// ── Explanatory content per analysis ──
	const ANALYSIS_CONTENT: Record<string, { howToRead: string; implications: string; method: string }> = {
		environmental_risk: {
			howToRead: 'El mapa muestra un score de 0 a 100 donde mayor valor indica mayor riesgo ambiental acumulado. Se combinan cinco factores: frecuencia de incendios, pérdida forestal histórica, amplitud térmica diurna-nocturna, pendiente del terreno y altura sobre el drenaje más cercano. Colores cálidos (rojo) indican zonas con múltiples riesgos superpuestos.',
			implications: 'Zonas con score alto presentan vulnerabilidad ambiental múltiple: mayor probabilidad de incendios, suelos inestables por pendiente, y exposición a inundaciones por baja elevación sobre cauces. Estas áreas requieren evaluación detallada antes de cualquier intervención territorial.',
			method: 'Score = promedio ponderado de 5 componentes normalizados por percentil (0-100): frecuencia de incendios MODIS (25%), pérdida forestal Hansen GFC (25%), amplitud térmica LST MODIS (20%), pendiente FABDEM 30m (15%), HAND invertido MERIT Hydro (15%). Baseline satelital 2019-2024.',
		},
		climate_comfort: {
			howToRead: 'El score indica qué tan confortable es el clima de la zona en una escala de 0 a 100. Valores altos implican menor estrés térmico, menos heladas y mejor balance hídrico. Se combinan temperatura diurna y nocturna, precipitación, días de helada y relación evapotranspiración/potencial.',
			implications: 'Zonas con bajo confort climático presentan extremos térmicos (calor diurno intenso o heladas frecuentes), precipitación insuficiente o excesiva, y estrés hídrico. Esto impacta tanto la habitabilidad como la productividad agrícola y forestal.',
			method: 'Score = promedio ponderado de: LST diurno invertido (25%), LST nocturno invertido (20%), precipitación CHIRPS (20%), días de helada invertido ERA5 (15%), ratio ET/PET MODIS (20%). Baseline satelital 2019-2024. Temperaturas en °C (MODIS 1km), precipitación en mm/año (CHIRPS 5km).',
		},
		green_capital: {
			howToRead: 'El score mide la cantidad y calidad de vegetación en cada zona. Valores altos indican mayor cobertura vegetal, bosque más denso y ecosistemas más productivos. Se combinan cinco indicadores satelitales complementarios de verdor, cobertura arbórea y productividad primaria.',
			implications: 'Zonas con alto capital verde son reservorios de biodiversidad, regulan el clima local, protegen el suelo de la erosión y proveen servicios ecosistémicos. Su pérdida genera efectos cascada: mayor temperatura, menor retención hídrica, pérdida de hábitat.',
			method: 'Score = promedio ponderado de: NDVI medio MODIS 250m (25%), cobertura arbórea Hansen 2000 (20%), NPP MODIS (20%), LAI MODIS (15%), fracción arbórea VCF MODIS (20%). Baseline satelital 2019-2024 excepto Hansen (baseline 2000).',
		},
		change_pressure: {
			howToRead: 'El score indica cuánto se está transformando cada zona. Valores altos señalan cambios intensos: urbanización creciente, pérdida de cobertura vegetal o expansión de la frontera agropecuaria. Se combinan tendencias temporales (luces, NDVI) con cambios acumulados (GHSL, Hansen).',
			implications: 'Zonas con alta presión de cambio están en transición activa: pueden representar oportunidades de inversión (urbanización) o alertas ambientales (deforestación). La combinación de tendencia VIIRS creciente con NDVI decreciente señala conversión de uso del suelo.',
			method: 'Score = promedio ponderado de: tendencia VIIRS 2016-2025 regr_slope (25%), cambio GHSL built fraction 2000-2020 (25%), pérdida forestal total Hansen (20%), tendencia NDVI invertida 2019-2024 (15%), actividad de fuego MODIS (15%).',
		},
		location_value: {
			howToRead: 'El score estima el valor posicional de cada zona según su accesibilidad, conectividad y actividad económica. Valores altos indican zonas bien conectadas, cercanas a servicios de salud, con actividad económica visible y topografía favorable.',
			implications: 'El valor posicional es un predictor de precio del suelo y potencial de desarrollo. Zonas con alto score pero baja densidad edilicia pueden representar oportunidades de inversión. Zonas con bajo score están funcionalmente aisladas.',
			method: 'Score = promedio ponderado de: tiempo a ciudad 20k invertido Nelson (25%), acceso a salud invertido Oxford (20%), radiancia nocturna VIIRS (25%), pendiente invertida FABDEM (15%), distancia a ruta invertida OSM (15%).',
		},
		agri_potential: {
			howToRead: 'El score indica la aptitud agroclimática del suelo. Valores altos señalan suelos fértiles con buena lluvia, calor suficiente y pendiente manejable para cultivos. Se combinan propiedades del suelo (SoilGrids), clima (CHIRPS, ERA5) y topografía (FABDEM).',
			implications: 'Zonas con score alto son óptimas para cultivos extensivos e intensivos. El pH cercano a 6.0-6.5 y alto carbono orgánico favorecen yerba mate, té y tabaco. Pendientes >15° limitan la mecanización. Precipitación <1200mm/año requiere riego.',
			method: 'Score = promedio ponderado de: carbono orgánico SoilGrids (20%), distancia pH a óptimo 6.25 invertida (15%), contenido de arcilla (15%), precipitación CHIRPS (20%), GDD base 10 ERA5 (15%), pendiente invertida FABDEM (15%). Suelos a 0-5cm, 250m resolución.',
		},
		forest_health: {
			howToRead: 'El score indica la integridad y salud del bosque. Valores altos señalan bosques con tendencia de verdor estable o creciente, baja pérdida arbórea, poca actividad de fuego y alta productividad fotosintética.',
			implications: 'Bosques con score bajo están en proceso de degradación: pérdida de cobertura, incendios recurrentes o reducción de productividad. La combinación de tendencia NDVI negativa con alta pérdida Hansen señala deforestación activa.',
			method: 'Score = promedio ponderado de: tendencia NDVI 5 años (25%), ratio pérdida/cobertura Hansen invertido (25%), fracción quemada MODIS invertida (20%), GPP MODIS (15%), ET MODIS (15%). Baseline satelital 2019-2024.',
		},
		forestry_aptitude: {
			howToRead: 'El score indica dónde es más rentable establecer plantaciones forestales comerciales. Valores altos señalan zonas con suelo ácido (favorable para pinos), lluvia suficiente, pendiente mecanizable y buena logística de transporte.',
			implications: 'Misiones concentra el 80% de las plantaciones forestales de Argentina. Las zonas con alto score combinan condiciones edafoclimáticas óptimas con accesibilidad logística. El pH bajo (ácido) es preferido por Pinus y Eucalyptus.',
			method: 'Score = promedio ponderado de: pH invertido SoilGrids (15%), arcilla invertida (10%), precipitación CHIRPS (25%), pendiente invertida FABDEM (20%), distancia a ruta invertida OSM (15%), tiempo a ciudad 50k invertido Nelson (15%).',
		},
		isolation_index: {
			howToRead: 'El score indica cuán aislado está cada lugar. Valores altos señalan zonas con largo tiempo de viaje a centros urbanos, baja densidad vial, poca actividad económica nocturna y alta fricción de desplazamiento.',
			implications: 'El aislamiento limita el acceso a salud, educación y mercados. Zonas con score alto tienen mayor costo logístico, menor cobertura de servicios y menor conectividad digital. Poblaciones aisladas son más vulnerables ante emergencias.',
			method: 'Score = promedio ponderado de: tiempo a ciudad 100k Nelson (25%), tiempo a Posadas custom (25%), densidad vial invertida OSM (20%), radiancia nocturna invertida VIIRS (15%), fricción motorizada Oxford (15%).',
		},
		health_access: {
			howToRead: 'El score indica el déficit de acceso a servicios de salud. Valores altos señalan zonas donde la combinación de lejanía al centro de salud, alta demanda poblacional y vulnerabilidad social genera una brecha sanitaria significativa.',
			implications: 'Zonas con score alto tienen poblaciones que enfrentan barreras concretas para acceder a atención médica: largo tiempo de viaje, falta de cobertura formal, y condiciones socioeconómicas que agravan los problemas de salud.',
			method: 'Score = promedio ponderado de: tiempo motorizado a salud Oxford MAP (30%), tiempo a pie a salud (20%), densidad poblacional censo 2022 (15%), cobertura de salud invertida (15%), NBI (20%). Resolución: 1km (Oxford) + radio censal (censo).',
		},
		education_gap: {
			howToRead: 'El score mide la brecha educativa territorial. Valores altos indican zonas con alto porcentaje de población sin instrucción, alta deserción adolescente, bajo nivel educativo máximo, y aislamiento que dificulta el acceso a instituciones educativas.',
			implications: 'La brecha educativa tiene efectos intergeneracionales: zonas con alta deserción y bajo nivel educativo reproducen la pobreza. El aislamiento amplifica el problema al limitar el acceso a escuelas secundarias y terciarias.',
			method: 'Score = promedio ponderado de: sin instrucción censo 2022 (25%), deserción 13-18 años (25%), solo primaria (20%), universitarios invertido (15%), aislamiento Nelson (15%). Datos del Censo Nacional 2022 a nivel radio censal.',
		},
		land_use: {
			howToRead: 'El mapa muestra la diversidad de uso del suelo (índice de Shannon, 0-100). Valores altos indican zonas con múltiples usos del suelo coexistiendo (mosaico agro-forestal). Valores bajos indican uso homogéneo (bosque puro o monocultivo). Los componentes muestran la fracción de cada clase.',
			implications: 'Alta diversidad de uso puede indicar resiliencia territorial (múltiples actividades económicas) o fragmentación del paisaje. Zonas de bosque puro (diversidad baja, frac_trees alto) son prioritarias para conservación. Zonas con alto frac_built y bajo frac_trees indican islas de calor urbano.',
			method: 'Fuente: Google Dynamic World v1 (Sentinel-2, 10m, 2024). Composite anual (moda por píxel). 9 clases: agua, bosque, pasto, vegetación inundable, cultivos, arbustos, construido, desnudo, nieve. Score = Shannon entropy normalizada sobre 9 clases × 100.',
		},
		territorial_gap: {
			howToRead: 'El score mide la desigualdad territorial: la brecha entre actividad económica visible y acceso a servicios básicos. Valores altos indican zonas donde hay actividad económica (luces nocturnas) pero falta infraestructura básica (agua, cloacas) o hay alta pobreza.',
			implications: 'La brecha territorial señala zonas donde el crecimiento económico no se traduce en bienestar. Alta radiancia nocturna con alto NBI indica urbanización sin servicios. Zonas aisladas con bajo NBI no son "brecha" sino pobreza estructural — un problema diferente.',
			method: 'Score = promedio ponderado de: radiancia nocturna invertida VIIRS (15%), NBI censo 2022 (25%), sin red de agua censo 2022 (25%), sin cloacas censo 2022 (20%), tiempo a ciudad 20k Nelson (15%). La inversión de VIIRS penaliza zonas con luces pero sin servicios.',
		},
	};

	// Dynamic World (land_use) — will be added when data is processed
	// SAT_SUMMARIES and ANALYSIS_CONTENT entries are ready for when the parquet exists

	const content = $derived(ANALYSIS_CONTENT[analysis.id] ?? null);
</script>

{#if selectedHex && selectedDpto && isPerDept}
	<!-- ═══ HEX DETAIL VIEW ═══ -->
	<div class="view">
		<button class="back-btn" onclick={handleBackToDepts}>{i18n.t('analysis.flood.topDepts')}</button>

		<div class="hex-header">
			<div class="hex-id" title={selectedHex.h3index}>
				{selectedHex.h3index.slice(0, 4)}...{selectedHex.h3index.slice(-4)}
			</div>
			<div class="risk-badge" style:background={getScoreColor(selectedHex.score ?? 0)}>
				{getScoreLevel(selectedHex.score ?? 0)}
			</div>
		</div>

		<div class="score-bar">
			<div class="score-label">Score</div>
			<div class="score-track">
				<div class="score-fill" style:width="{selectedHex.score ?? 0}%"
					style:background={getScoreColor(selectedHex.score ?? 0)}></div>
			</div>
			<div class="score-value" style:color={getScoreColor(selectedHex.score ?? 0)}>
				{(selectedHex.score ?? 0).toFixed(1)}
			</div>
		</div>

		<div class="detail-grid">
			{#each componentVars as v}
				{@const val = selectedHex[v.col] ?? 0}
				<div class="detail-item">
					<div class="detail-label">{i18n.t(v.labelKey)}</div>
					<div class="detail-value">{typeof val === 'number' ? val.toFixed(1) : val}</div>
					<div class="detail-desc">Percentil provincial (0-100)</div>
				</div>
			{/each}
		</div>

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
				<div class="summary-card">
					<div class="card-value" style:color={getScoreColor(deptSummary.province.avg_score ?? 50)}>
						{deptSummary.province.avg_score?.toFixed(1)}
					</div>
					<div class="card-label">Score promedio</div>
				</div>
			</div>
		{/if}

		<div class="dept-section">
			<div class="section-title">{i18n.t('analysis.flood.topDepts')}</div>
			{#each deptList as dept}
				<button class="dept-row dept-clickable" onclick={() => handleDptoClick(dept)}>
					<div class="dept-name">{dept.dpto}</div>
					<div class="dept-bar-wrap">
						<div class="dept-bar" style:width="{dept.avg_score}%"
							style:background={getScoreColor(dept.avg_score)}></div>
					</div>
					<div class="dept-score" style:color={getScoreColor(dept.avg_score)}>
						{dept.avg_score.toFixed(1)}
					</div>
				</button>
			{/each}
		</div>

		{#if content}
			<details class="method-details">
				<summary class="method-summary">Como leer este mapa</summary>
				<div class="method-body">
					<p class="explain-text">{content.howToRead}</p>
					<div class="mini-legend">
						<div class="legend-bar" style:background={legendGradient}></div>
						<div class="legend-labels">
							{#each legendLabels as label}<span>{label}</span>{/each}
						</div>
					</div>
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

		<div class="flood-legend">
			<div class="legend-title">Escala de score</div>
			<div class="legend-bar" style:background={legendGradient}></div>
			<div class="legend-labels">
				{#each legendLabels as label}
					<span>{label}</span>
				{/each}
			</div>
		</div>

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
	.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
	.detail-item { background: rgba(100,116,139,0.08); border-radius: 6px; padding: 8px; }
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
</style>
