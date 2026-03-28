<script lang="ts">
	import type { MapStore } from '$lib/stores/map.svelte';
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import CTADiagnostic from '$lib/components/CTADiagnostic.svelte';
	import { PARQUETS, type RadioAnalysisConfig } from '$lib/config';
	import { initDuckDB, query, isReady } from '$lib/stores/duckdb';
	import PetalChart from '$lib/components/PetalChart.svelte';
	import scoresDeptData from '$lib/data/scores_dept_summary.json';

	let {
		config,
		mapStore,
		hexStore,
		onSelectRadioAnalysisDpto,
	}: {
		config: RadioAnalysisConfig;
		mapStore: MapStore;
		hexStore: HexStore;
		onSelectRadioAnalysisDpto?: (dpto: string, analysisId: string, centroid: [number, number]) => void;
	} = $props();

	// Dept centroids from pre-computed JSON (fast, reliable)
	const deptCentroids: Record<string, [number, number]> = {};
	for (const d of (scoresDeptData as any).departments) {
		deptCentroids[d.dpto] = d.centroid;
	}

	const locale = $derived(i18n.locale as 'es' | 'en');

	const selectedParcels = $derived(mapStore.selectedScoresParcels);
	const hasParcels = $derived(selectedParcels.length > 0);

	let activeDpto = $state<string | null>(null);
	let deptSummaries = $state<any[]>([]);
	let deptLoading = $state(false);
	let provAvgs = $state<Record<string, number>>({});

	// Load dept summaries on mount
	$effect(() => {
		if (deptSummaries.length === 0) loadDeptSummaries();
	});

	async function loadDeptSummaries() {
		deptLoading = true;
		try {
			await initDuckDB();
			const col = config.choroplethCol;
			const sortDir = 'DESC';
			const result = await query(`
				SELECT dpto,
					ROUND(AVG(CAST(${col} AS DOUBLE)), 1) as avg_val,
					count(*) as n_radios
				FROM '${PARQUETS.radio_stats_master}'
				WHERE dpto IS NOT NULL
				GROUP BY dpto
				ORDER BY avg_val ${sortDir}
			`);
			const rows: any[] = [];
			for (let i = 0; i < result.numRows; i++) {
				rows.push(result.get(i)!.toJSON());
			}
			deptSummaries = rows;

			// Provincial averages for petal normalization (only cols in radio_stats_master)
			const radioCols = config.petalCols.filter(c => !c.source);
			const allCols = radioCols.map(c => `ROUND(AVG(CAST(${c.col} AS DOUBLE)), 4) as ${c.col}`).join(', ');
			const avgResult = allCols ? await query(`SELECT ${allCols} FROM '${PARQUETS.radio_stats_master}'`) : null;
			if (avgResult && avgResult.numRows > 0) {
				const row = avgResult.get(0)!.toJSON() as Record<string, any>;
				const avgs: Record<string, number> = {};
				for (const c of config.petalCols) {
					avgs[c.col] = Number(row[c.col]) || 1; // default 1 for catastro cols
				}
				provAvgs = avgs;
			}
		} catch (e) {
			console.warn('Failed to load dept summaries:', e);
		}
		deptLoading = false;
	}

	// Auto-select top department on first load
	let hasAutoSelected = false;
	$effect(() => {
		if (deptSummaries.length > 0 && !hasAutoSelected && !activeDpto) {
			hasAutoSelected = true;
			setTimeout(() => handleDptoClick(deptSummaries[0]), 400);
		}
	});

	function handleDptoClick(dept: any) {
		activeDpto = dept.dpto;
		const centroid = deptCentroids[dept.dpto] || [-54.4, -27.0];
		onSelectRadioAnalysisDpto?.(dept.dpto, config.id, centroid);
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

	function getColor(val: number, max: number): string {
		if (max === 0) return '#64748b';
		const t = val / max;
		if (config.colorScale === 'flood') {
			// Higher = worse (red)
			if (t >= 0.7) return '#dc2626';
			if (t >= 0.4) return '#eab308';
			return '#22c55e';
		}
		if (config.invertChoropleth) {
			// Lower = better (green) — for accessibility, travel time, distances
			if (t <= 0.3) return '#22c55e';
			if (t <= 0.6) return '#eab308';
			return '#dc2626';
		}
		// Higher = better (green) — for scores, potential
		if (t >= 0.6) return '#22c55e';
		if (t >= 0.3) return '#eab308';
		return '#64748b';
	}

	const petalLabels = $derived(config.petalCols.map(c => c.label[locale]));

	// Build petal layers from selected parcels
	const parcelPetalLayers = $derived.by(() => {
		if (!hasParcels || Object.keys(provAvgs).length === 0) return [];
		return selectedParcels.map(p => ({
			values: config.petalCols.map(c => {
				const raw = p.scores[c.col] ?? 0;
				const avg = provAvgs[c.col] || 0.001;
				let ratio = raw / avg;
				if (c.invert && raw > 0) ratio = avg / raw;
				return Math.min(100, Math.max(0, ratio * 50));
			}),
			color: p.color,
		}));
	});

	const maxDeptVal = $derived(deptSummaries.length > 0 ? Math.max(...deptSummaries.map((d: any) => d.avg_val || 0)) : 1);
</script>

{#if hasParcels && activeDpto}
	<!-- ═══════ PARCEL DETAIL ═══════ -->
	<div class="view">
		<div class="parcel-nav">
			<button class="back-btn" onclick={handleBackToDepts}>{activeDpto}</button>
			<button class="clear-btn" onclick={() => mapStore.clearScoresParcels()}>&#10005; Limpiar</button>
		</div>

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

		{#if parcelPetalLayers.length > 0}
			<div class="petal-section">
				<div class="section-title">Perfil comparativo</div>
				<p class="petal-note">Relativo al promedio provincial (50 = promedio). {config.colorScale === 'flood' ? 'Mayor extensión = mayor riesgo.' : 'Mayor extensión = mejor dotación.'}</p>
				<div class="petal-wrapper">
					<PetalChart layers={parcelPetalLayers} labels={petalLabels} size={280} />
				</div>
			</div>
		{/if}

		{#each selectedParcels as parcel}
			<div class="parcel-block">
				<div class="parcel-header">
					<span class="chip-dot" style:background={parcel.color}></span>
					<span>{parcel.tipo === 'rural' ? 'Rural' : 'Urbana'}</span>
					{#if parcel.area_m2 > 0}
						<span class="chip-area">{parcel.area_m2.toLocaleString('es-AR', { maximumFractionDigits: 0 })} m²</span>
					{/if}
				</div>
				<div class="detail-grid">
					{#each config.petalCols as col}
						{@const val = parcel.scores[col.col] ?? 0}
						<div class="detail-item">
							<div class="detail-label">{col.label[locale]}</div>
							<div class="detail-value">{typeof val === 'number' ? (Number.isInteger(val) ? val.toLocaleString() : val.toFixed(1)) : val}</div>
							<div class="detail-desc">{col.desc[locale]}</div>
						</div>
					{/each}
				</div>
			</div>
		{/each}

		<div class="source-note-box">
			<div><strong>Fuente:</strong> INDEC Censo 2022 · SoilGrids · CHIRPS · Overture Maps · Catastro Misiones</div>
		</div>
	</div>

{:else if activeDpto}
	<!-- ═══════ DEPARTMENT VIEW ═══════ -->
	<div class="view">
		<div class="parcel-nav">
			<button class="back-btn" onclick={handleBackToDepts}>Departamentos</button>
		</div>
		<div class="dept-title">{activeDpto}</div>
		<div class="hint">Hacé click en una parcela para ver el detalle</div>

		<details class="method-details">
			<summary class="method-summary">Guía rápida</summary>
			<div class="method-body">
				<p class="explain-text">{config.howToRead[locale]}</p>
			</div>
		</details>

		<div class="source-note-box">
			<div><strong>Fuente:</strong> INDEC Censo 2022 · SoilGrids · CHIRPS · Overture Maps</div>
		</div>
	</div>

{:else}
	<!-- ═══════ DEPARTMENT LIST ═══════ -->
	<div class="view">
		{#if deptLoading}
			<div class="loading">Cargando datos...</div>
		{:else}
			<div class="dept-section">
				<div class="section-title">Seleccioná un departamento</div>
				{#each deptSummaries as dept}
					<button class="dept-row" onclick={() => handleDptoClick(dept)}>
						<div class="dept-name">{dept.dpto}</div>
						<div class="dept-bar-wrap">
							<div class="dept-bar" style:width="{Math.max(Math.min((dept.avg_val / maxDeptVal) * 100, 100), 3)}%"
								style:background={getColor(dept.avg_val, maxDeptVal)}></div>
						</div>
						<div class="dept-score" style:color={getColor(dept.avg_val, maxDeptVal)}>
							{dept.avg_val?.toFixed?.(1) ?? '—'}
						</div>
					</button>
				{/each}
			</div>
		{/if}

		<details class="method-details">
			<summary class="method-summary">Cómo leer este análisis</summary>
			<div class="method-body">
				<p class="explain-text">{config.howToRead[locale]}</p>
			</div>
		</details>

		<details class="method-details">
			<summary class="method-summary">Qué mide cada indicador</summary>
			<div class="method-body">
				{#each config.petalCols as col}
					<div class="method-item">
						<span class="method-term">{col.label[locale]}</span>
						<span class="method-def">{col.desc[locale]}</span>
					</div>
				{/each}
			</div>
		</details>

		<details class="method-details">
			<summary class="method-summary">Implicancias</summary>
			<div class="method-body">
				<p class="explain-text">{config.implications[locale]}</p>
			</div>
		</details>

		<details class="method-details">
			<summary class="method-summary">Metodologia</summary>
			<div class="method-body">
				<p class="explain-text">{config.methodology[locale]}</p>
			</div>
		</details>

		<div class="source-note-box">
			<div><strong>Fuente:</strong> INDEC Censo 2022 · SoilGrids · CHIRPS · Overture Maps · Catastro Misiones</div>
		</div>

		<CTADiagnostic analysisName={config.id} />
	</div>
{/if}

<style>
	.view { font-size: 11px; }
	.parcel-nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
	.back-btn { font-size: 10px; color: #d4d4d4; background: none; border: none; cursor: pointer; padding: 2px 0; }
	.back-btn::before { content: '← '; }
	.back-btn:hover { color: #e2e8f0; }
	.clear-btn { font-size: 9px; color: #a3a3a3; background: none; border: none; cursor: pointer; }
	.clear-btn:hover { color: #ef4444; }
	.parcel-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
	.parcel-chip { display: inline-flex; align-items: center; gap: 3px; background: rgba(255,255,255,0.06); border-radius: 4px; padding: 2px 6px; font-size: 9px; }
	.chip-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
	.chip-tipo { color: #d4d4d4; }
	.chip-area { color: #a3a3a3; font-size: 9px; }
	.chip-x { background: none; border: none; color: #a3a3a3; font-size: 9px; cursor: pointer; padding: 0 2px; }
	.chip-x:hover { color: #ef4444; }
	.petal-section { margin: 6px 0; }
	.petal-note { font-size: 9px; color: #a3a3a3; margin: 2px 0 6px 0; line-height: 1.4; }
	.petal-wrapper { margin: 0 auto; max-width: 300px; }
	.parcel-block { margin: 8px 0; padding: 6px; background: rgba(255,255,255,0.03); border-radius: 6px; }
	.parcel-header { display: flex; align-items: center; gap: 6px; font-size: 10px; color: #d4d4d4; margin-bottom: 6px; }
	.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
	.detail-item { background: rgba(100,116,139,0.08); border-radius: 4px; padding: 5px 6px; }
	.detail-label { font-size: 9px; color: #d4d4d4; margin-bottom: 1px; }
	.detail-value { font-size: 14px; font-weight: 700; color: #e2e8f0; }
	.detail-desc { font-size: 8px; color: #a3a3a3; line-height: 1.3; margin-top: 2px; }
	.dept-title { font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 8px; }
	.hint { font-size: 9px; color: #a3a3a3; margin-bottom: 8px; }
	.loading { font-size: 10px; color: #a3a3a3; padding: 12px 0; }
	.dept-section { margin-top: 6px; }
	.section-title { font-size: 10px; font-weight: 600; color: #a3a3a3; margin-bottom: 6px; }
	.dept-row { display: flex; align-items: center; gap: 6px; width: 100%; padding: 4px 0; background: none; border: none; cursor: pointer; color: inherit; text-align: left; }
	.dept-row:hover { background: rgba(255,255,255,0.04); }
	.dept-name { width: 100px; font-size: 10px; color: #d4d4d4; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.dept-bar-wrap { flex: 1; height: 6px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden; }
	.dept-bar { height: 100%; border-radius: 3px; transition: width 0.3s; }
	.dept-score { width: 36px; text-align: right; font-size: 10px; font-weight: 600; flex-shrink: 0; }
	.method-details { border: 1px solid rgba(100,116,139,0.15); border-radius: 6px; margin: 6px 0; overflow: hidden; }
	.method-summary { font-size: 9px; font-weight: 500; color: #d4d4d4; padding: 6px 8px; cursor: pointer; list-style: none; display: flex; align-items: center; gap: 4px; }
	.method-summary::before { content: '▸'; font-size: 8px; transition: transform 0.2s; }
	.method-details[open] .method-summary::before { transform: rotate(90deg); }
	.method-body { padding: 4px 8px 8px; }
	.explain-text { font-size: 9px; color: #cbd5e1; line-height: 1.5; margin: 0 0 6px 0; }
	.method-item { display: flex; gap: 4px; font-size: 9px; margin-bottom: 4px; line-height: 1.4; }
	.method-term { color: #e2e8f0; font-weight: 600; flex-shrink: 0; min-width: 80px; }
	.method-def { color: #a3a3a3; }
	.source-note-box { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 6px 8px; font-size: 9px; color: #e2e8f0; line-height: 1.5; margin-top: 10px; }
</style>
