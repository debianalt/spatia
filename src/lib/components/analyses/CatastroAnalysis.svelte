<script lang="ts">
	import { onMount } from 'svelte';
	import { getParquetUrl, DATA_FRESHNESS } from '$lib/config';
	import { initDuckDB, query } from '$lib/stores/duckdb';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		lensStore,
		mapStore,
		onRemoveRadio,
		onSelectCatastroDpto,
	}: {
		lensStore: LensStore;
		mapStore: MapStore;
		onRemoveRadio: (redcode: string) => void;
		onSelectCatastroDpto?: (centroid: [number, number] | null) => void;
	} = $props();

	let loading = $state(true);
	let selectedDpto = $state<string | null>(null);
	let allData: Map<string, Record<string, any>> = $state(new Map());
	let deptSummary: Array<{ code: string; dpto: string; nUrban: number; nRural: number; newParcels: number }> = $state([]);
	let totalUrban = $state(0);
	let totalRural = $state(0);
	let totalNew90d = $state(0);
	let avgAreaUrban = $state(0);

	const selectedRedcode = $derived(
		mapStore.selectedRadios.size === 1
			? [...mapStore.selectedRadios.keys()][0]
			: null
	);
	const radioData = $derived(
		selectedRedcode ? allData.get(selectedRedcode) ?? null : null
	);

	onMount(() => {
		loadData();
	});

	async function loadData() {
		try {
			await initDuckDB();
			const url = getParquetUrl('catastro_by_radio');
			const result = await query(`SELECT * FROM '${url}'`);
			const map = new Map<string, Record<string, any>>();
			const depts = new Map<string, { nUrban: number; nRural: number; newParcels: number }>();
			let tUrban = 0;
			let tRural = 0;
			let tNew = 0;
			const areas: number[] = [];

			for (let i = 0; i < result.numRows; i++) {
				const raw = result.get(i)!.toJSON() as Record<string, any>;
				// Convert BigInt values to Number (DuckDB-WASM returns int64 as BigInt)
				const row: Record<string, any> = {};
				for (const [k, v] of Object.entries(raw)) {
					row[k] = typeof v === 'bigint' ? Number(v) : v;
				}
				map.set(row.redcode, row);
				tUrban += row.n_parcelas_urbano ?? 0;
				tRural += row.n_parcelas_rural ?? 0;
				tNew += row.n_new_parcels_90d ?? 0;
				if (row.area_media_urbano_m2 != null && row.area_media_urbano_m2 > 0) {
					areas.push(row.area_media_urbano_m2);
				}

				// Department aggregation (use first 5 chars of redcode as dept key)
				const dptoCode = row.redcode.substring(0, 5);
				const d = depts.get(dptoCode) ?? { nUrban: 0, nRural: 0, newParcels: 0 };
				d.nUrban += row.n_parcelas_urbano ?? 0;
				d.nRural += row.n_parcelas_rural ?? 0;
				d.newParcels += row.n_new_parcels_90d ?? 0;
				depts.set(dptoCode, d);
			}

			allData = map;
			totalUrban = tUrban;
			totalRural = tRural;
			totalNew90d = tNew;
			avgAreaUrban = areas.length > 0
				? areas.reduce((a, b) => a + b, 0) / areas.length
				: 0;

			// Resolve department names from mapStore if available
			deptSummary = [...depts.entries()]
				.map(([code, d]) => ({
					code,
					dpto: getDptoName(code),
					nUrban: d.nUrban,
					nRural: d.nRural,
					newParcels: d.newParcels,
				}))
				.sort((a, b) => b.nUrban - a.nUrban)
				.slice(0, 10);
		} catch (e) {
			console.warn('Failed to load catastro data:', e);
		} finally {
			loading = false;
		}
	}

	const DPTO_INFO: Record<string, { name: string; centroid: [number, number] }> = {
		'54007': { name: 'Apóstoles', centroid: [-27.92, -55.75] },
		'54014': { name: 'Cainguás', centroid: [-27.18, -54.73] },
		'54021': { name: 'Candelaria', centroid: [-27.45, -55.73] },
		'54028': { name: 'Capital', centroid: [-27.38, -55.90] },
		'54035': { name: 'Concepción', centroid: [-27.98, -55.52] },
		'54042': { name: 'Eldorado', centroid: [-26.40, -54.63] },
		'54049': { name: 'G. M. Belgrano', centroid: [-26.08, -53.78] },
		'54056': { name: 'Guaraní', centroid: [-27.18, -54.18] },
		'54063': { name: 'Iguazú', centroid: [-25.95, -54.30] },
		'54070': { name: 'L.G. San Martín', centroid: [-27.08, -54.95] },
		'54077': { name: 'L. N. Alem', centroid: [-27.60, -55.32] },
		'54084': { name: 'Montecarlo', centroid: [-26.58, -54.78] },
		'54091': { name: 'Oberá', centroid: [-27.48, -55.12] },
		'54098': { name: 'San Ignacio', centroid: [-27.25, -55.53] },
		'54105': { name: 'San Javier', centroid: [-27.77, -55.13] },
		'54112': { name: 'San Pedro', centroid: [-26.62, -54.12] },
		'54119': { name: '25 de Mayo', centroid: [-27.37, -54.02] },
	};

	function getDptoName(code: string): string {
		return DPTO_INFO[code]?.name ?? code;
	}

	function handleDptoClick(dptoCode: string) {
		const info = DPTO_INFO[dptoCode];
		if (info) {
			selectedDpto = dptoCode;
			onSelectCatastroDpto?.(info.centroid);
		}
	}

	function handleBackToDepts() {
		selectedDpto = null;
		onSelectCatastroDpto?.(null);
	}

	function fmt(n: number | null | undefined): string {
		if (n == null) return '-';
		return n.toLocaleString('es-AR', { maximumFractionDigits: 0 });
	}

	function fmtArea(n: number | null | undefined): string {
		if (n == null || n === 0) return '-';
		return `${n.toLocaleString('es-AR', { maximumFractionDigits: 0 })} m\u00B2`;
	}

	export function getChoroplethEntries(): Array<{ redcode: string; value: number }> {
		const entries: Array<{ redcode: string; value: number }> = [];
		for (const [redcode, row] of allData) {
			const val = row.n_parcelas_urbano;
			if (val != null && val > 0) {
				entries.push({ redcode, value: val });
			}
		}
		return entries;
	}

	export function isLoaded(): boolean {
		return !loading && allData.size > 0;
	}
</script>

{#if loading}
	<div class="loading">{i18n.t('analysis.loading')}</div>
{:else if selectedRedcode && radioData}
	<!-- Radio detail view -->
	<div class="radio-detail">
		<div class="detail-header">
			<div>
				<div class="detail-redcode">{selectedRedcode}</div>
				<div class="detail-dpto">{getDptoName(selectedRedcode.substring(0, 5))}</div>
			</div>
			<button class="detail-close" onclick={() => onRemoveRadio(selectedRedcode)}>x</button>
		</div>

		<div class="stat-grid">
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalUrban')}</div>
				<div class="stat-value">{fmt(radioData.n_parcelas_urbano)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalRural')}</div>
				<div class="stat-value">{fmt(radioData.n_parcelas_rural)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.avgAreaUrban')}</div>
				<div class="stat-value">{fmtArea(radioData.area_media_urbano_m2)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.avgAreaRural')}</div>
				<div class="stat-value">{fmtArea(radioData.area_media_rural_m2)}</div>
			</div>
		</div>

		{#if radioData.n_new_parcels_90d > 0}
			<div class="pressure-badge">
				<span class="pressure-icon">+</span>
				<span>{radioData.n_new_parcels_90d} {i18n.t('analysis.catastro.newParcels')}</span>
			</div>
		{/if}

		<!-- vs provincial average -->
		{#if radioData.n_parcelas_urbano > 0}
			{@const ratio = radioData.n_parcelas_urbano / (totalUrban / allData.size)}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.catastro.vsAvg')}</div>
				<div class="vs-indicator" class:above={ratio > 1.2} class:below={ratio < 0.8}>
					{#if ratio > 1.2}
						<span class="vs-arrow">+{((ratio - 1) * 100).toFixed(0)}%</span>
						<span class="vs-text">sobre el promedio</span>
					{:else if ratio < 0.8}
						<span class="vs-arrow">-{((1 - ratio) * 100).toFixed(0)}%</span>
						<span class="vs-text">bajo el promedio</span>
					{:else}
						<span class="vs-text">en el promedio provincial</span>
					{/if}
				</div>
			</div>
		{/if}
	</div>
{:else if selectedDpto}
	<!-- Department selected: parcels visible on map -->
	<div class="dept-detail">
		<button class="back-btn" onclick={handleBackToDepts}>← {i18n.t('analysis.catastro.topDepts')}</button>
		<div class="dept-active-title">{getDptoName(selectedDpto)}</div>
		<div class="hint">{i18n.t('analysis.catastro.clickDept')}</div>

		<div class="source-note-box">
			<div><strong>{i18n.t('data.source.catastro')}</strong></div>
			<div>{i18n.t('analysis.catastro.updateFreq')} · {DATA_FRESHNESS.catastro_by_radio?.processedDate ?? ''}</div>
		</div>
	</div>
{:else}
	<!-- Provincial summary -->
	<div class="provincial-summary">
		<div class="stat-grid">
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalUrban')}</div>
				<div class="stat-value">{fmt(totalUrban)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalRural')}</div>
				<div class="stat-value">{fmt(totalRural)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.avgAreaUrban')}</div>
				<div class="stat-value">{fmtArea(avgAreaUrban)}</div>
			</div>
			<div class="stat-item highlight">
				<div class="stat-label">{i18n.t('analysis.catastro.newParcels')}</div>
				<div class="stat-value new-count">{fmt(totalNew90d)}</div>
			</div>
		</div>

		{#if deptSummary.length > 0}
			{@const maxN = deptSummary[0].nUrban}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.catastro.topDepts')}</div>
				{#each deptSummary as dept}
					<button class="dept-row dept-clickable"
						onclick={() => handleDptoClick(dept.code)}>
						<div class="dept-top">
							<span class="dept-name">{dept.dpto}</span>
							<span class="dept-count">{fmt(dept.nUrban)}</span>
						</div>
						<div class="dept-bar-bg">
							<div class="dept-bar" style:width="{(dept.nUrban / maxN) * 100}%"></div>
						</div>
					</button>
				{/each}
			</div>
		{/if}

		<div class="source-note-box">
			<div><strong>{i18n.t('data.source.catastro')}</strong></div>
			<div>{i18n.t('analysis.catastro.updateFreq')} · {DATA_FRESHNESS.catastro_by_radio?.processedDate ?? ''}</div>
		</div>
	</div>
{/if}

<style>
	.loading {
		color: #a3a3a3;
		font-size: 10px;
		padding: 12px 0;
	}
	.stat-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
		margin-bottom: 10px;
	}
	.stat-item {
		background: rgba(255,255,255,0.03);
		border-radius: 6px;
		padding: 6px 8px;
	}
	.stat-item.highlight {
		background: rgba(6,182,212,0.08);
		border: 1px solid rgba(6,182,212,0.2);
	}
	.stat-label {
		font-size: 8px;
		color: #a3a3a3;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		margin-bottom: 2px;
	}
	.stat-value {
		font-size: 13px;
		font-weight: 600;
		color: #e2e8f0;
	}
	.stat-value.new-count {
		color: #06b6d4;
	}

	/* Pressure badge */
	.pressure-badge {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		background: rgba(6,182,212,0.1);
		border: 1px solid rgba(6,182,212,0.3);
		border-radius: 6px;
		padding: 4px 10px;
		font-size: 10px;
		font-weight: 600;
		color: #06b6d4;
		margin-bottom: 8px;
	}
	.pressure-icon {
		font-size: 12px;
		font-weight: 700;
	}

	/* Sections */
	.section {
		margin-bottom: 8px;
	}
	.section-title {
		font-size: 9px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #a3a3a3;
		border-bottom: 1px solid #1e293b;
		padding-bottom: 2px;
		margin-bottom: 4px;
	}

	/* Department rows */
	.dept-row {
		margin-bottom: 4px;
	}
	.dept-clickable {
		background: none;
		border: none;
		width: 100%;
		text-align: left;
		cursor: pointer;
		padding: 3px 4px;
		border-radius: 4px;
		transition: background 0.15s;
	}
	.dept-clickable:hover { background: rgba(6,182,212,0.1); }
	.dept-top {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
	}
	.dept-name {
		font-size: 10px;
		color: #d4d4d4;
	}
	.dept-count {
		font-size: 9px;
		color: #a3a3a3;
	}
	.dept-bar-bg {
		height: 3px;
		background: rgba(255,255,255,0.05);
		border-radius: 2px;
		margin-top: 1px;
	}
	.dept-bar {
		height: 100%;
		background: #06b6d4;
		border-radius: 2px;
		transition: width 0.3s ease;
	}
	.dept-new {
		font-size: 8px;
		color: #06b6d4;
		font-weight: 600;
	}

	/* vs indicator */
	.vs-indicator {
		font-size: 10px;
		color: #a3a3a3;
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 4px 0;
	}
	.vs-indicator.above .vs-arrow { color: #f59e0b; font-weight: 600; }
	.vs-indicator.below .vs-arrow { color: #22c55e; font-weight: 600; }
	.vs-text { color: #a3a3a3; }

	/* Radio detail */
	.radio-detail {
		padding: 2px 0;
	}
	.detail-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 8px;
	}
	.detail-redcode {
		font-size: 11px;
		font-weight: 600;
		color: #e2e8f0;
		font-family: monospace;
	}
	.detail-dpto {
		font-size: 9px;
		color: #a3a3a3;
	}
	.detail-close {
		background: none;
		border: none;
		color: #a3a3a3;
		cursor: pointer;
		font-size: 12px;
		padding: 0 4px;
		line-height: 1;
	}
	.detail-close:hover { color: #e2e8f0; }

	/* Department detail */
	.dept-detail {
		font-size: 11px;
	}
	.back-btn {
		background: none;
		border: none;
		color: #60a5fa;
		font-size: 10px;
		cursor: pointer;
		padding: 0;
		margin-bottom: 8px;
	}
	.back-btn:hover { text-decoration: underline; }
	.dept-active-title {
		font-size: 14px;
		font-weight: 700;
		color: #e2e8f0;
		margin-bottom: 8px;
	}
	.hint {
		font-size: 9px;
		color: #a3a3a3;
		text-align: center;
		margin-top: 8px;
	}

	/* Source */
	.source-note-box {
		margin-top: 10px;
		padding: 6px 8px;
		background: rgba(255,255,255,0.02);
		border: 1px solid rgba(255,255,255,0.05);
		border-radius: 6px;
		font-size: 8px;
		color: #737373;
		line-height: 1.4;
	}
</style>
