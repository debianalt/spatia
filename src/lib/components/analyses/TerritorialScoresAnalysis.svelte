<script lang="ts">
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import CTADiagnostic from '$lib/components/CTADiagnostic.svelte';
	import { DATA_FRESHNESS, TERRITORIAL_SCORE_COLS, TERRITORIAL_SCORE_LABELS, TERRITORIAL_SCORE_DESCS } from '$lib/config';
	import PetalChart from '$lib/components/PetalChart.svelte';
	import deptSummaryData from '$lib/data/scores_dept_summary.json';

	let {
		lensStore,
		mapStore,
		hexStore,
		onSelectScoresCatastroDpto,
	}: {
		lensStore: LensStore;
		mapStore: MapStore;
		hexStore: HexStore;
		onSelectScoresCatastroDpto?: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
	} = $props();

	const locale = $derived(i18n.locale as 'es' | 'en');
	const deptSummaries = deptSummaryData.departments.sort((a: any, b: any) => b.overall_score - a.overall_score);
	const totalHexes = deptSummaryData.province.total_hexes;

	const selectedParcels = $derived(mapStore.selectedScoresParcels);
	const hasParcels = $derived(selectedParcels.length > 0);

	let activeDpto = $state<string | null>(null);
	let activeIndicator = $state<string>('urban_consolidation');

	const petalLabels = $derived(
		TERRITORIAL_SCORE_COLS.map(c => TERRITORIAL_SCORE_LABELS[c]?.[locale] ?? c)
	);

	const parcelPetalLayers = $derived.by(() => {
		if (!hasParcels) return [];
		return selectedParcels.map(p => ({
			values: TERRITORIAL_SCORE_COLS.map(c => p.scores[c] ?? 0),
			color: p.color,
		}));
	});

	function getScoreColor(score: number): string {
		if (score >= 50) return '#22c55e';
		if (score >= 20) return '#eab308';
		return '#64748b';
	}

	function getScoreLevel(score: number): string {
		if (locale === 'en') {
			if (score >= 70) return 'High';
			if (score >= 40) return 'Medium-high';
			if (score >= 20) return 'Medium';
			if (score >= 5) return 'Low';
			return 'Very low';
		}
		if (score >= 70) return 'Alto';
		if (score >= 40) return 'Medio-alto';
		if (score >= 20) return 'Medio';
		if (score >= 5) return 'Bajo';
		return 'Muy bajo';
	}

	// Department list loads, user picks manually

	function handleDptoClick(dept: any) {
		activeDpto = dept.dpto;
		onSelectScoresCatastroDpto?.(dept.dpto, dept.parquetKey, dept.centroid as [number, number]);
	}

	function handleBackToDepts() {
		if (hasParcels && activeDpto) {
			mapStore.clearScoresParcels();
			return;
		}
		if (activeDpto) {
			activeDpto = null;
			mapStore.clearScoresParcels();
			return;
		}
	}

	function handleIndicatorChange(e: Event) {
		const select = e.target as HTMLSelectElement;
		activeIndicator = select.value;
		if (activeDpto) {
			const dept = deptSummaries.find((d: any) => d.dpto === activeDpto);
			if (dept) {
				onSelectScoresCatastroDpto?.(dept.dpto, dept.parquetKey, dept.centroid as [number, number]);
			}
		}
	}

	const freshness = DATA_FRESHNESS.overture_scores ?? { dataDate: 'Overture 2026-03-18', processedDate: '25/03/2026' };
</script>

{#if hasParcels && activeDpto}
	<!-- ═══════ PARCEL DETAIL VIEW ═══════ -->
	<div class="view">
		<div class="parcel-nav">
			<button class="back-btn" onclick={handleBackToDepts}>{activeDpto}</button>
			<button class="clear-btn" onclick={() => mapStore.clearScoresParcels()}>&#10005; Limpiar</button>
		</div>

		<!-- Parcel chips -->
		<div class="parcel-chips">
			{#each selectedParcels as parcel}
				<span class="parcel-chip">
					<span class="chip-dot" style:background={parcel.color}></span>
					<span class="chip-tipo">{parcel.tipo === 'rural' ? 'R' : 'U'}</span>
					<button class="chip-x" onclick={() => mapStore.addScoresParcel({
						h3index: parcel.h3index, tipo: parcel.tipo, area_m2: parcel.area_m2,
						scores: parcel.scores, components: parcel.components
					})}>x</button>
				</span>
			{/each}
		</div>

		<!-- 8-axis Petal Chart -->
		<div class="petal-section">
			<div class="section-title">Perfil territorial</div>
			<p class="petal-note">Cada eje muestra un indicador de 0 a 100. Mayor extensión = mejor dotación territorial.</p>
			<div class="petal-wrapper">
				<PetalChart layers={parcelPetalLayers} labels={petalLabels} size={280} />
			</div>
		</div>

		<div class="source-note-box">
			<div><strong>Fuente:</strong> Overture Maps Foundation via walkthru.earth (CC BY 4.0)</div>
			<div><strong>Grilla:</strong> H3 resolución 9 (~174 m de lado) · <strong>Actualización:</strong> {freshness.processedDate}</div>
		</div>
	</div>

{:else if activeDpto}
	<!-- ═══════ DEPARTMENT CATASTRO VIEW ═══════ -->
	<div class="view">
		<div class="parcel-nav">
			<button class="back-btn" onclick={handleBackToDepts}>{i18n.t('analysis.scores.selectDept')}</button>
		</div>
		<div class="dept-title">{activeDpto}</div>

		<div class="indicator-select">
			<label class="select-label">{i18n.t('analysis.scores.selectIndicator')}</label>
			<select class="select-input" value={activeIndicator} onchange={handleIndicatorChange}>
				{#each TERRITORIAL_SCORE_COLS as col}
					<option value={col}>{TERRITORIAL_SCORE_LABELS[col]?.[locale] ?? col}</option>
				{/each}
			</select>
		</div>

		<div class="hint">{i18n.t('analysis.scores.clickHint')}</div>

		<details class="method-details">
			<summary class="method-summary">Guía rápida</summary>
			<div class="method-body">
				<p class="explain-text">Cada parcela catastral está coloreada según el indicador seleccionado. Verde más intenso = mayor score. Hacé click en una parcela para ver su perfil completo de 8 indicadores.</p>
			</div>
		</details>

		<div class="scores-legend">
		</div>

		<div class="source-note-box">
			<div><strong>Fuente:</strong> Overture Maps Foundation ({freshness.dataDate})</div>
		</div>
	</div>

{:else}
	<!-- ═══════ DEPARTMENT LIST (ROOT VIEW) ═══════ -->
	<div class="view">
		<div class="summary-cards">
			<div class="summary-card">
				<div class="card-value">{totalHexes.toLocaleString()}</div>
				<div class="card-label">{i18n.t('analysis.scores.hexCount')}</div>
			</div>
		</div>

		<!-- Department ranking -->
		<div class="dept-section">
			<div class="section-title">{i18n.t('analysis.scores.selectDept')}</div>
			{#each deptSummaries as dept, di}
				<button class="dept-row" onclick={() => handleDptoClick(dept)}>
					<span class="dept-name">{dept.dpto}</span>
					<span class="dept-count">{dept.hex_count} hex</span>
				</button>
			{/each}
		</div>

		<!-- How to read -->
		<details class="method-details">
			<summary class="method-summary">Cómo leer este análisis</summary>
			<div class="method-body">
				<p class="explain-text">Cada hexagono recibe un perfil de 8 indicadores territoriales clasificados por PCA + k-means. Al seleccionar un departamento, los hexagonos se colorean por tipo. Al hacer click, un grafico de petalos muestra los 8 indicadores simultaneamente.</p>
				</div>
		</details>

		<!-- What each indicator measures -->
		<details class="method-details">
			<summary class="method-summary">Qué mide cada indicador</summary>
			<div class="method-body">
				{#each TERRITORIAL_SCORE_COLS as col}
					<div class="method-item">
						<span class="method-term">{TERRITORIAL_SCORE_LABELS[col]?.[locale] ?? col}</span>
						<span class="method-def">{TERRITORIAL_SCORE_DESCS[col]?.[locale] ?? ''}</span>
					</div>
				{/each}
			</div>
		</details>

		<!-- Implications -->
		<details class="method-details">
			<summary class="method-summary">Implicancias</summary>
			<div class="method-body">
				<p class="explain-text">Parcelas con scores altos en pavimentación, consolidación y servicios representan zonas consolidadas con bajo riesgo de inversión. Parcelas con alto score solo en conectividad señalan zonas en expansión con potencial de valorización. Scores bajos generalizados indican zonas rurales o en desarrollo temprano.</p>
			</div>
		</details>

		<!-- Methodology -->
		<details class="method-details">
			<summary class="method-summary">Metodologia</summary>
			<div class="method-body">
				<div class="method-item">
					<span class="method-term">Fuente</span>
					<span class="method-def">Overture Maps Foundation via walkthru.earth (CC BY 4.0)</span>
				</div>
				<div class="method-item">
					<span class="method-term">Grilla</span>
					<span class="method-def">H3 resolución 9 (~174 m de lado, ~0.1 km²)</span>
				</div>
				<div class="method-item">
					<span class="method-term">Vecindad</span>
					<span class="method-def">Pavimentación y comercio usan radio de 3 km (k-ring=2); servicios usa 5 km (k-ring=3); agua usa 3 km</span>
				</div>
				<div class="method-item">
					<span class="method-term">Scores</span>
					<span class="method-def">Cada indicador es un compuesto ponderado normalizado a 0–100</span>
				</div>
				<div class="method-item">
					<span class="method-term">Actualización</span>
					<span class="method-def">{freshness.dataDate} · Procesado: {freshness.processedDate}</span>
				</div>
			</div>
		</details>

		<div class="source-note-box">
			<div><strong>Fuente:</strong> Overture Maps Foundation via walkthru.earth (CC BY 4.0)</div>
		</div>

		<CTADiagnostic analysisName="Perfil territorial" />
	</div>
{/if}

<style>
	.view { font-size: 11px; }

	/* ── Navigation ── */
	.parcel-nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
	.back-btn { font-size: 10px; color: #d4d4d4; background: none; border: none; cursor: pointer; padding: 2px 0; }
	.back-btn::before { content: '← '; }
	.back-btn:hover { color: #e2e8f0; }
	.clear-btn { font-size: 9px; color: #a3a3a3; background: none; border: none; cursor: pointer; }
	.clear-btn:hover { color: #ef4444; }

	/* ── Parcel chips ── */
	.parcel-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
	.parcel-chip { display: inline-flex; align-items: center; gap: 3px; background: rgba(255,255,255,0.06); border-radius: 4px; padding: 2px 6px; font-size: 9px; }
	.chip-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
	.chip-tipo { color: #d4d4d4; }
	.chip-area { color: #a3a3a3; font-size: 9px; }
	.chip-x { background: none; border: none; color: #a3a3a3; font-size: 9px; cursor: pointer; padding: 0 2px; }
	.chip-x:hover { color: #ef4444; }

	/* ── Petal section ── */
	.petal-section { margin: 6px 0; }
	.petal-note { font-size: 9px; color: #a3a3a3; margin: 2px 0 6px 0; line-height: 1.4; }
	.petal-wrapper { margin: 0 auto; max-width: 300px; }

	/* ── Department view ── */
	.dept-title { font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 8px; }
	.indicator-select { margin-bottom: 8px; }
	.select-label { display: block; font-size: 9px; color: #a3a3a3; margin-bottom: 3px; }
	.select-input { width: 100%; background: #1e293b; border: 1px solid rgba(255,255,255,0.12); border-radius: 4px; color: #e2e8f0; font-size: 10px; padding: 4px 6px; }
	.select-input option { background: #1e293b; color: #e2e8f0; }
	.hint { font-size: 9px; color: #a3a3a3; margin-bottom: 8px; }

	/* ── Legend ── */
	.scores-legend { margin: 8px 0; }
	.legend-title { font-size: 9px; color: #d4d4d4; margin-bottom: 3px; font-weight: 500; }
	.legend-bar { height: 6px; border-radius: 3px; background: linear-gradient(to right, #1e293b, #334155, #4a7c59, #22c55e, #86efac, #f0fdf4); }
	.legend-labels { display: flex; justify-content: space-between; font-size: 8px; color: #a3a3a3; margin-top: 2px; }

	/* ── Summary cards ── */
	.summary-cards { display: flex; gap: 8px; margin-bottom: 10px; }
	.summary-card { flex: 1; background: rgba(255,255,255,0.04); border-radius: 6px; padding: 8px; text-align: center; }
	.card-value { font-size: 16px; font-weight: 700; color: #e2e8f0; }
	.card-label { font-size: 8px; color: #a3a3a3; margin-top: 2px; }

	/* ── Department list ── */
	.dept-section { margin-top: 6px; }
	.section-title { font-size: 10px; font-weight: 600; color: #a3a3a3; margin-bottom: 6px; }
	.dept-row { display: flex; align-items: center; gap: 6px; width: 100%; padding: 4px 0; background: none; border: none; cursor: pointer; color: inherit; text-align: left; }
	.dept-row:hover { background: rgba(255,255,255,0.04); }
	.dept-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
	.dept-name { font-size: 10px; color: #d4d4d4; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.dept-count { font-size: 9px; color: #a3a3a3; margin-left: auto; }

	/* ── Collapsible details (same pattern as FloodRisk) ── */
	.method-details { border: 1px solid rgba(100,116,139,0.15); border-radius: 6px; margin: 6px 0; overflow: hidden; }
	.method-summary { font-size: 9px; font-weight: 500; color: #d4d4d4; padding: 6px 8px; cursor: pointer; list-style: none; display: flex; align-items: center; gap: 4px; }
	.method-summary::before { content: '▸'; font-size: 8px; transition: transform 0.2s; }
	.method-details[open] .method-summary::before { transform: rotate(90deg); }
	.method-body { padding: 4px 8px 8px; }
	.explain-text { font-size: 9px; color: #cbd5e1; line-height: 1.5; margin: 0 0 6px 0; }
	.method-item { display: flex; gap: 4px; font-size: 9px; margin-bottom: 4px; line-height: 1.4; }
	.method-term { color: #e2e8f0; font-weight: 600; flex-shrink: 0; min-width: 80px; }
	.method-def { color: #a3a3a3; }
	.mini-legend { margin-top: 6px; }

	/* ── Source box ── */
	.source-note-box { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 6px 8px; font-size: 9px; color: #e2e8f0; line-height: 1.5; margin-top: 10px; }
</style>
