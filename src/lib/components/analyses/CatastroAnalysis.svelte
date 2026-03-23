<script lang="ts">
	import { onMount } from 'svelte';
	import { getParquetUrl, PARQUETS, DATA_FRESHNESS } from '$lib/config';
	import { initDuckDB, query } from '$lib/stores/duckdb';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import PetalChart from '$lib/components/PetalChart.svelte';

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
	let deptAvgs: Map<string, { avgUrban: number; avgAreaUrban: number; avgNew90d: number }> = $state(new Map());
	let provAvg = $state({ avgUrban: 0, avgAreaUrban: 0, avgNew90d: 0 });

	// Housing quality per radio (keyed by redcode)
	let housingCache: Map<string, Record<string, number>> = $state(new Map());
	let housingProvAvg = $state<Record<string, number> | null>(null);

	// Housing quality variables + petal config
	// DEFICIT vars (high=bad): agua_red, cloacas, hacinamiento, nbi → invert for petal
	// ACCESS vars (high=good): alumbrado, pavimento → direct for petal
	const HOUSING_COLS = ['pct_agua_red', 'pct_cloacas', 'pct_alumbrado', 'pct_pavimento', 'pct_hacinamiento', 'pct_nbi'];
	const HOUSING_LABELS_KEYS = [
		'analysis.catastro.h.agua', 'analysis.catastro.h.cloacas', 'analysis.catastro.h.alumbrado',
		'analysis.catastro.h.pavimento', 'analysis.catastro.h.hacinamiento', 'analysis.catastro.h.nbi'
	];
	// true = deficit variable → invert for petal (100-value so higher=better on chart)
	// agua_red and cloacas are DEFICIT (% WITHOUT, high=bad)
	// alumbrado and pavimento are ACCESS (high=good)
	// hacinamiento and nbi are DEFICIT (high=bad)
	const HOUSING_DEFICIT = [true, true, false, false, true, true];

	// Derived: ordered list of selected radios with their colors
	const selectedEntries = $derived(
		[...mapStore.selectedRadios.entries()].map(([rc, d]) => ({ redcode: rc, color: d.color }))
	);
	const hasRadios = $derived(selectedEntries.length > 0);

	// Petal layers: one per selected radio, using the radio's assigned color
	const petalLayers = $derived.by(() => {
		if (!housingProvAvg || selectedEntries.length === 0) return [];
		return selectedEntries
			.filter(e => housingCache.has(e.redcode))
			.map(e => {
				const hd = housingCache.get(e.redcode)!;
				const values = HOUSING_COLS.map((col, i) => {
					let raw = hd[col] ?? 0;
					let avg = housingProvAvg![col] ?? 1;
					if (HOUSING_DEFICIT[i]) { raw = 100 - raw; avg = 100 - avg; }
					if (avg === 0) return 50;
					return Math.min(100, Math.max(0, (raw / avg) * 50));
				});
				return { values, color: e.color };
			});
	});
	const petalLabels = $derived(HOUSING_LABELS_KEYS.map(k => i18n.t(k)));

	onMount(() => { loadData(); });

	// Load housing data for each new radio
	$effect(() => {
		for (const { redcode } of selectedEntries) {
			if (!housingCache.has(redcode)) {
				loadHousingData(redcode);
			}
		}
	});

	async function loadData() {
		try {
			await initDuckDB();
			const url = getParquetUrl('catastro_by_radio');
			const result = await query(`SELECT * FROM '${url}'`);
			const map = new Map<string, Record<string, any>>();
			const depts = new Map<string, { nUrban: number; nRural: number; newParcels: number }>();
			let tUrban = 0, tRural = 0, tNew = 0;
			const areas: number[] = [];

			for (let i = 0; i < result.numRows; i++) {
				const raw = result.get(i)!.toJSON() as Record<string, any>;
				const row: Record<string, any> = {};
				for (const [k, v] of Object.entries(raw)) row[k] = typeof v === 'bigint' ? Number(v) : v;
				map.set(row.redcode, row);
				tUrban += row.n_parcelas_urbano ?? 0;
				tRural += row.n_parcelas_rural ?? 0;
				tNew += row.n_new_parcels_90d ?? 0;
				if (row.area_media_urbano_m2 != null && row.area_media_urbano_m2 > 0) areas.push(row.area_media_urbano_m2);
				const dc = row.redcode.substring(0, 5);
				const d = depts.get(dc) ?? { nUrban: 0, nRural: 0, newParcels: 0 };
				d.nUrban += row.n_parcelas_urbano ?? 0;
				d.nRural += row.n_parcelas_rural ?? 0;
				d.newParcels += row.n_new_parcels_90d ?? 0;
				depts.set(dc, d);
			}

			allData = map;
			totalUrban = tUrban; totalRural = tRural; totalNew90d = tNew;
			avgAreaUrban = areas.length > 0 ? areas.reduce((a, b) => a + b, 0) / areas.length : 0;
			const n = map.size;
			provAvg = { avgUrban: n > 0 ? tUrban / n : 0, avgAreaUrban: avgAreaUrban, avgNew90d: n > 0 ? tNew / n : 0 };

			const deptRadioCounts = new Map<string, number>();
			const deptAreaSums = new Map<string, { sum: number; count: number }>();
			for (const [rc, row] of map) {
				const dc = rc.substring(0, 5);
				deptRadioCounts.set(dc, (deptRadioCounts.get(dc) ?? 0) + 1);
				if (row.area_media_urbano_m2 != null && row.area_media_urbano_m2 > 0) {
					const a = deptAreaSums.get(dc) ?? { sum: 0, count: 0 };
					a.sum += row.area_media_urbano_m2; a.count += 1;
					deptAreaSums.set(dc, a);
				}
			}
			const da = new Map<string, { avgUrban: number; avgAreaUrban: number; avgNew90d: number }>();
			for (const [code, d] of depts) {
				const nr = deptRadioCounts.get(code) ?? 1;
				const ai = deptAreaSums.get(code);
				da.set(code, { avgUrban: d.nUrban / nr, avgAreaUrban: ai ? ai.sum / ai.count : 0, avgNew90d: d.newParcels / nr });
			}
			deptAvgs = da;
			deptSummary = [...depts.entries()]
				.map(([code, d]) => ({ code, dpto: getDptoName(code), nUrban: d.nUrban, nRural: d.nRural, newParcels: d.newParcels }))
				.sort((a, b) => b.nUrban - a.nUrban).slice(0, 10);
			await loadHousingProvAvg();
		} catch (e) { console.warn('Failed to load catastro data:', e); }
		finally { loading = false; }
	}

	async function loadHousingProvAvg() {
		try {
			const cols = HOUSING_COLS.map(c => `AVG(${c}) as ${c}`).join(', ');
			const result = await query(`SELECT ${cols} FROM '${PARQUETS.radio_stats_master}' WHERE pct_agua_red IS NOT NULL`);
			if (result.numRows > 0) {
				const row = result.get(0)!.toJSON() as Record<string, any>;
				const avg: Record<string, number> = {};
				for (const c of HOUSING_COLS) avg[c] = Number(row[c] ?? 0);
				housingProvAvg = avg;
			}
		} catch (e) { console.warn('Failed to load housing provincial avg:', e); }
	}

	async function loadHousingData(redcode: string) {
		try {
			await initDuckDB();
			const cols = HOUSING_COLS.join(', ');
			const result = await query(
				`SELECT ${cols} FROM '${PARQUETS.radio_stats_master}' WHERE redcode = '${redcode.replace(/'/g, "''")}' LIMIT 1`
			);
			if (result.numRows > 0) {
				const row = result.get(0)!.toJSON() as Record<string, any>;
				const data: Record<string, number> = {};
				for (const c of HOUSING_COLS) data[c] = Number(row[c] ?? 0);
				housingCache = new Map(housingCache).set(redcode, data);
			}
		} catch (e) { console.warn('Failed to load housing data:', e); }
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

	function getDptoName(code: string): string { return DPTO_INFO[code]?.name ?? code; }

	function handleDptoClick(dptoCode: string) {
		const info = DPTO_INFO[dptoCode];
		if (info) { selectedDpto = dptoCode; onSelectCatastroDpto?.(info.centroid); }
	}

	function handleBackToDepts() {
		selectedDpto = null;
		onSelectCatastroDpto?.(null);
		for (const rc of [...mapStore.selectedRadios.keys()]) onRemoveRadio(rc);
	}

	function fmt(n: number | null | undefined): string {
		if (n == null) return '-';
		return n.toLocaleString('es-AR', { maximumFractionDigits: 0 });
	}
	function fmtArea(n: number | null | undefined): string {
		if (n == null || n === 0) return '-';
		return `${n.toLocaleString('es-AR', { maximumFractionDigits: 0 })} m\u00B2`;
	}
	function fmtPct(n: number | null | undefined): string {
		if (n == null) return '-';
		return `${n.toFixed(1)}%`;
	}

	const CMP_METRICS = [
		{ key: 'n_parcelas_urbano', labelKey: 'analysis.catastro.totalUrban', type: 'int' },
		{ key: 'n_parcelas_rural', labelKey: 'analysis.catastro.totalRural', type: 'int' },
		{ key: 'area_media_urbano_m2', labelKey: 'analysis.catastro.avgAreaUrban', type: 'area' },
		{ key: 'area_media_rural_m2', labelKey: 'analysis.catastro.avgAreaRural', type: 'area' },
		{ key: 'n_new_parcels_90d', labelKey: 'analysis.catastro.newParcels', type: 'int' },
	] as const;

	function fmtMetric(v: number | null | undefined, type: string): string {
		if (type === 'area') return fmtArea(v);
		return fmt(v);
	}
</script>

{#if loading}
	<div class="loading">{i18n.t('analysis.loading')}</div>
{:else if hasRadios}
	<!-- Radio comparison view (1 or more radios) -->
	<div class="radio-detail">
		<!-- Selected radios header + clear button -->
		<div class="radios-header">
			{#each selectedEntries as entry}
				<div class="radio-chip">
					<span class="chip-dot" style:background={entry.color}></span>
					<span class="chip-code">{entry.redcode.slice(-4)}</span>
					<span class="chip-dpto">{getDptoName(entry.redcode.substring(0, 5))}</span>
					<button class="chip-x" onclick={() => onRemoveRadio(entry.redcode)}>x</button>
				</div>
			{/each}
			{#if selectedEntries.length > 1}
				<button class="clear-btn" onclick={() => { for (const rc of [...mapStore.selectedRadios.keys()]) onRemoveRadio(rc); }}>
					{i18n.t('analysis.catastro.clearAll')}
				</button>
			{/if}
		</div>

		<!-- Comparison table -->
		<div class="cmp-table">
			<div class="cmp-header-row">
				<div class="cmp-metric-label"></div>
				{#each selectedEntries as entry}
					<div class="cmp-col-header" style:color={entry.color}>{entry.redcode.slice(-4)}</div>
				{/each}
			</div>
			{#each CMP_METRICS as m}
				{@const vals = selectedEntries.map(e => (allData.get(e.redcode)?.[m.key] ?? 0) as number)}
				{@const maxVal = Math.max(...vals, 1)}
				<div class="cmp-metric-row">
					<div class="cmp-metric-label">{i18n.t(m.labelKey)}</div>
					<div class="cmp-bars">
						{#each selectedEntries as entry, idx}
							{@const v = vals[idx]}
							<div class="cmp-bar-cell">
								<div class="cmp-bar-track">
									<div class="cmp-bar-fill" style:width="{(v / maxVal) * 100}%" style:background={entry.color}></div>
								</div>
								<span class="cmp-bar-val">{fmtMetric(v, m.type)}</span>
							</div>
						{/each}
					</div>
				</div>
			{/each}
		</div>

		<!-- Housing quality petals (overlaid) -->
		{#if petalLayers.length > 0}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.catastro.housingTitle')}</div>
				<div class="petal-wrapper">
					<PetalChart layers={petalLayers} labels={petalLabels} size={220} />
				</div>
				<!-- Housing values per radio -->
				{#each selectedEntries as entry}
					{#if housingCache.has(entry.redcode)}
						{@const hd = housingCache.get(entry.redcode)}
						<div class="housing-radio-row">
							<span class="chip-dot" style:background={entry.color}></span>
							<span class="housing-radio-code">{entry.redcode.slice(-4)}</span>
							{#each HOUSING_COLS as col, i}
								<span class="housing-cell">{fmtPct(HOUSING_DEFICIT[i] ? 100 - (hd?.[col] ?? 0) : hd?.[col])}</span>
							{/each}
						</div>
					{/if}
				{/each}
				<div class="petal-hint">{i18n.t('analysis.catastro.petalHint')}</div>
			</div>
		{/if}

		<div class="map-legend">
			<span class="legend-swatch" style:background="#22d3ee"></span> {i18n.t('analysis.catastro.legendUrban')}
			<span class="legend-swatch legend-gap" style:background="#4ade80"></span> {i18n.t('analysis.catastro.legendRural')}
		</div>
		<div class="source-note-box">
			<div><strong>{i18n.t('data.source.catastro')}</strong> · Censo 2022</div>
		</div>
	</div>
{:else if selectedDpto}
	<div class="dept-detail">
		<button class="back-btn" onclick={handleBackToDepts}>← {i18n.t('analysis.catastro.topDepts')}</button>
		<div class="dept-active-title">{getDptoName(selectedDpto)}</div>
		<div class="hint">{i18n.t('analysis.catastro.clickDept')}</div>
		<div class="map-legend">
			<span class="legend-swatch" style:background="#22d3ee"></span> {i18n.t('analysis.catastro.legendUrban')}
			<span class="legend-swatch legend-gap" style:background="#4ade80"></span> {i18n.t('analysis.catastro.legendRural')}
		</div>
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
					<button class="dept-row dept-clickable" onclick={() => handleDptoClick(dept.code)}>
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

		<div class="map-legend">
			<span class="legend-swatch" style:background="#22d3ee"></span> {i18n.t('analysis.catastro.legendUrban')}
			<span class="legend-swatch legend-gap" style:background="#4ade80"></span> {i18n.t('analysis.catastro.legendRural')}
		</div>
		<div class="source-note-box">
			<div><strong>{i18n.t('data.source.catastro')}</strong></div>
			<div>{i18n.t('analysis.catastro.updateFreq')} · {DATA_FRESHNESS.catastro_by_radio?.processedDate ?? ''}</div>
		</div>
	</div>
{/if}

<style>
	.loading { color: #a3a3a3; font-size: 10px; padding: 12px 0; }

	/* Radio chips header */
	.radios-header { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
	.radio-chip { display: inline-flex; align-items: center; gap: 3px; background: rgba(255,255,255,0.05); border-radius: 12px; padding: 2px 6px 2px 4px; font-size: 9px; }
	.chip-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
	.chip-code { font-family: monospace; font-weight: 600; color: #e2e8f0; }
	.chip-dpto { color: #a3a3a3; }
	.chip-x { background: none; border: none; color: #737373; cursor: pointer; font-size: 10px; padding: 0 2px; line-height: 1; }
	.chip-x:hover { color: #ef4444; }
	.clear-btn { background: none; border: 1px solid rgba(239,68,68,0.3); color: #ef4444; font-size: 8px; padding: 2px 8px; border-radius: 10px; cursor: pointer; transition: all 0.15s; }
	.clear-btn:hover { background: rgba(239,68,68,0.1); }

	/* Map legend */
	.map-legend { display: flex; align-items: center; gap: 4px; font-size: 8px; color: #a3a3a3; margin: 8px 0 4px; }
	.legend-swatch { width: 10px; height: 3px; border-radius: 1px; flex-shrink: 0; }
	.legend-gap { margin-left: 8px; }

	/* Comparison table */
	.cmp-table { margin-bottom: 10px; }
	.cmp-header-row { display: flex; gap: 4px; margin-bottom: 4px; padding-left: 70px; }
	.cmp-col-header { flex: 1; font-size: 8px; font-weight: 700; font-family: monospace; text-align: center; }
	.cmp-metric-row { display: flex; align-items: center; gap: 4px; margin-bottom: 3px; }
	.cmp-metric-label { width: 66px; flex-shrink: 0; font-size: 7px; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.03em; }
	.cmp-bars { flex: 1; display: flex; flex-direction: column; gap: 2px; }
	.cmp-bar-cell { display: flex; align-items: center; gap: 4px; }
	.cmp-bar-track { flex: 1; height: 6px; background: rgba(255,255,255,0.04); border-radius: 3px; overflow: hidden; }
	.cmp-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s ease; }
	.cmp-bar-val { font-size: 8px; font-weight: 600; color: #e2e8f0; min-width: 36px; text-align: right; }

	/* Sections */
	.section { margin-bottom: 8px; }
	.section-title { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #a3a3a3; border-bottom: 1px solid #1e293b; padding-bottom: 2px; margin-bottom: 4px; }

	/* Petal */
	.petal-wrapper { display: flex; justify-content: center; margin: 4px 0; }
	.housing-radio-row { display: flex; align-items: center; gap: 4px; font-size: 8px; padding: 1px 0; }
	.housing-radio-code { font-family: monospace; font-weight: 600; color: #e2e8f0; width: 32px; }
	.housing-cell { flex: 1; text-align: center; color: #a3a3a3; }
	.petal-hint { font-size: 7px; color: #737373; text-align: center; margin-top: 4px; }

	/* Stat grid (province view) */
	.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px; }
	.stat-item { background: rgba(255,255,255,0.03); border-radius: 6px; padding: 6px 8px; }
	.stat-item.highlight { background: rgba(6,182,212,0.08); border: 1px solid rgba(6,182,212,0.2); }
	.stat-label { font-size: 8px; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 2px; }
	.stat-value { font-size: 13px; font-weight: 600; color: #e2e8f0; }
	.stat-value.new-count { color: #06b6d4; }

	/* Department rows */
	.dept-row { margin-bottom: 4px; }
	.dept-clickable { background: none; border: none; width: 100%; text-align: left; cursor: pointer; padding: 3px 4px; border-radius: 4px; transition: background 0.15s; }
	.dept-clickable:hover { background: rgba(6,182,212,0.1); }
	.dept-top { display: flex; justify-content: space-between; align-items: baseline; }
	.dept-name { font-size: 10px; color: #d4d4d4; }
	.dept-count { font-size: 9px; color: #a3a3a3; }
	.dept-bar-bg { height: 3px; background: rgba(255,255,255,0.05); border-radius: 2px; margin-top: 1px; }
	.dept-bar { height: 100%; background: #06b6d4; border-radius: 2px; transition: width 0.3s ease; }

	/* Department detail */
	.dept-detail { font-size: 11px; }
	.back-btn { background: none; border: none; color: #60a5fa; font-size: 10px; cursor: pointer; padding: 0; margin-bottom: 8px; }
	.back-btn:hover { text-decoration: underline; }
	.dept-active-title { font-size: 14px; font-weight: 700; color: #e2e8f0; margin-bottom: 8px; }
	.hint { font-size: 9px; color: #a3a3a3; text-align: center; margin-top: 8px; }

	.radio-detail { padding: 2px 0; }
	.source-note-box { margin-top: 10px; padding: 6px 8px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px; font-size: 8px; color: #737373; line-height: 1.4; }
</style>
