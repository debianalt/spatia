<script lang="ts">
	import { onMount } from 'svelte';
	import { getParquetUrl, PARQUETS, DATA_FRESHNESS } from '$lib/config';
	import { initDuckDB, query } from '$lib/stores/duckdb';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import PetalChart from '$lib/components/PetalChart.svelte';
	import CTADiagnostic from '$lib/components/CTADiagnostic.svelte';

	let {
		lensStore,
		mapStore,
		onRemoveRadio,
		onSelectCatastroDpto,
	}: {
		lensStore: LensStore;
		mapStore: MapStore;
		onRemoveRadio: (redcode: string) => void;
		onSelectCatastroDpto?: (centroid: [number, number] | null, deptCode?: string | null) => void;
	} = $props();

	let loading = $state(true);
	let selectedDpto = $state<string | null>(null);
	let allData: Map<string, Record<string, any>> = $state(new Map());
	let deptSummaryData = $state<any>(null);

	// Housing quality per radio (keyed by redcode)
	let housingCache: Map<string, Record<string, number>> = $state(new Map());
	let housingProvAvg = $state<Record<string, number> | null>(null);

	// Change history from parquet
	let changeHistory = $state<Array<{ change_date: string; parcel_type: string; change_type: string; departamento: string; n: number }>>([]);

	// Housing quality variables + petal config
	const HOUSING_COLS = ['pct_agua_red', 'pct_cloacas', 'pct_alumbrado', 'pct_pavimento', 'pct_hacinamiento', 'pct_nbi'];
	const HOUSING_LABELS_KEYS = [
		'analysis.catastro.h.agua', 'analysis.catastro.h.cloacas', 'analysis.catastro.h.alumbrado',
		'analysis.catastro.h.pavimento', 'analysis.catastro.h.hacinamiento', 'analysis.catastro.h.nbi'
	];
	const HOUSING_DEFICIT = [true, true, false, false, true, true];

	// Derived: ordered list of selected radios with their colors
	const selectedEntries = $derived(
		[...mapStore.selectedRadios.entries()].map(([rc, d]) => ({ redcode: rc, color: d.color }))
	);
	const hasRadios = $derived(selectedEntries.length > 0);

	// Petal layers: one per selected radio
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

	// Department list from static JSON
	const deptList = $derived.by(() => {
		if (!deptSummaryData?.departments) return [];
		return [...deptSummaryData.departments];
	});

	// Change bar data for selected department
	const deptChangeBars = $derived.by(() => {
		if (!selectedDpto || changeHistory.length === 0) return [];
		return changeBarData(selectedDpto);
	});

	// Selected department info
	const selectedDeptInfo = $derived.by(() => {
		if (!selectedDpto || !deptSummaryData?.departments) return null;
		return deptSummaryData.departments.find((d: any) => d.code === selectedDpto);
	});

	// Radios in selected department
	const deptRadios = $derived.by(() => {
		if (!selectedDpto) return [];
		const entries: Array<{ redcode: string; data: Record<string, any> }> = [];
		for (const [rc, data] of allData) {
			if (rc.startsWith(selectedDpto)) entries.push({ redcode: rc, data });
		}
		return entries.sort((a, b) => (b.data.n_new_parcels_90d ?? 0) - (a.data.n_new_parcels_90d ?? 0));
	});

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

			// Load dept summary JSON
			const summaryMod = await import('$lib/data/catastro_dept_summary.json');
			deptSummaryData = summaryMod.default;

			// Load catastro_by_radio for radio-level detail
			const url = getParquetUrl('catastro_by_radio');
			const result = await query(`SELECT * FROM '${url}'`);
			const map = new Map<string, Record<string, any>>();
			for (let i = 0; i < result.numRows; i++) {
				const raw = result.get(i)!.toJSON() as Record<string, any>;
				const row: Record<string, any> = {};
				for (const [k, v] of Object.entries(raw)) row[k] = typeof v === 'bigint' ? Number(v) : v;
				map.set(row.redcode, row);
			}
			allData = map;

			// Load changes history
			try {
				const chUrl = PARQUETS.catastro_changes;
				const chResult = await query(`SELECT * FROM '${chUrl}'`);
				const changes: typeof changeHistory = [];
				for (let i = 0; i < chResult.numRows; i++) {
					const raw = chResult.get(i)!.toJSON() as Record<string, any>;
					changes.push({
						change_date: String(raw.change_date ?? ''),
						parcel_type: String(raw.parcel_type ?? ''),
						change_type: String(raw.change_type ?? ''),
						departamento: String(raw.departamento ?? ''),
						n: Number(raw.n ?? 0),
					});
				}
				changeHistory = changes;
			} catch { /* changes parquet may not exist yet */ }

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

	function handleDptoClick(dept: any) {
		selectedDpto = dept.code;
		onSelectCatastroDpto?.(dept.centroid, dept.code);
	}

	function handleBackToDepts() {
		selectedDpto = null;
		onSelectCatastroDpto?.(null, null);
		for (const rc of [...mapStore.selectedRadios.keys()]) onRemoveRadio(rc);
	}

	function fmt(n: number | null | undefined): string {
		if (n == null) return '-';
		return n.toLocaleString('es-AR', { maximumFractionDigits: 0 });
	}

	function trendIcon(trend: string): string {
		if (trend === 'up') return '\u25B2';
		if (trend === 'down') return '\u25BC';
		return '\u2500';
	}

	function trendColor(trend: string): string {
		if (trend === 'up') return '#4ade80';
		if (trend === 'down') return '#f87171';
		return '#737373';
	}

	// Compute change bar widths for mini chart
	function changeBarData(deptCode: string): Array<{ date: string; nNew: number; nRemoved: number }> {
		const filtered = changeHistory.filter(c => c.departamento === deptCode);
		const byDate = new Map<string, { nNew: number; nRemoved: number }>();
		for (const c of filtered) {
			const d = byDate.get(c.change_date) ?? { nNew: 0, nRemoved: 0 };
			if (c.change_type === 'new') d.nNew += c.n;
			else d.nRemoved += c.n;
			byDate.set(c.change_date, d);
		}
		return [...byDate.entries()]
			.map(([date, d]) => ({ date, ...d }))
			.sort((a, b) => a.date.localeCompare(b.date))
			.slice(-8);
	}
</script>

{#if loading}
	<div class="loading">{i18n.t('analysis.loading')}</div>
{:else if hasRadios}
	<!-- Radio comparison view -->
	<div class="radio-detail">
		<div class="radios-header">
			{#each selectedEntries as entry}
				<div class="radio-chip">
					<span class="chip-dot" style:background={entry.color}></span>
					<span class="chip-code">{entry.redcode.slice(-4)}</span>
					<button class="chip-x" onclick={() => onRemoveRadio(entry.redcode)}>x</button>
				</div>
			{/each}
			{#if selectedEntries.length > 1}
				<button class="clear-btn" onclick={() => { for (const rc of [...mapStore.selectedRadios.keys()]) onRemoveRadio(rc); }}>
					{i18n.t('analysis.catastro.clearAll')}
				</button>
			{/if}
		</div>

		<!-- Catastro metrics for selected radios -->
		{#each selectedEntries as entry}
			{@const data = allData.get(entry.redcode)}
			{#if data}
				<div class="radio-metrics">
					<div class="radio-metrics-header">
						<span class="chip-dot" style:background={entry.color}></span>
						<span class="radio-code">{entry.redcode}</span>
					</div>
					<div class="mini-stats">
						<span>{i18n.t('analysis.catastro.legendUrban')}: <strong>{fmt(data.n_parcelas_urbano)}</strong></span>
						<span>{i18n.t('analysis.catastro.legendRural')}: <strong>{fmt(data.n_parcelas_rural)}</strong></span>
						{#if data.n_new_parcels_90d > 0}
							<span class="new-badge">+{fmt(data.n_new_parcels_90d)} {i18n.t('analysis.catastro.new90d')}</span>
						{/if}
					</div>
				</div>
			{/if}
		{/each}

		<!-- Housing quality petals -->
		{#if petalLayers.length > 0}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.catastro.housingTitle')}</div>
				<div class="petal-wrapper">
					<PetalChart layers={petalLayers} labels={petalLabels} size={220} />
				</div>
				<div class="petal-hint">{i18n.t('analysis.catastro.petalHint')}</div>
			</div>
		{/if}

		<div class="map-legend">
			<span class="legend-swatch" style:background="#06b6d4"></span> {i18n.t('analysis.catastro.legendUrban')}
			<span class="legend-swatch legend-gap" style:background="#4ade80"></span> {i18n.t('analysis.catastro.legendRural')}
			<span class="legend-swatch legend-gap" style:background="#fbbf24"></span> {i18n.t('analysis.catastro.legendNew')}
		</div>
	</div>
{:else if selectedDpto && selectedDeptInfo}
	<!-- Department detail view -->
	<div class="dept-detail">
		<button class="back-btn" onclick={handleBackToDepts}>{i18n.t('analysis.catastro.backToDepts')}</button>
		<div class="dept-active-title">{selectedDeptInfo.name}</div>

		<!-- Department stats -->
		<div class="stat-grid">
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalUrban')}</div>
				<div class="stat-value">{fmt(selectedDeptInfo.n_urbano)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalRural')}</div>
				<div class="stat-value">{fmt(selectedDeptInfo.n_rural)}</div>
			</div>
			<div class="stat-item highlight">
				<div class="stat-label">{i18n.t('analysis.catastro.new90d')}</div>
				<div class="stat-value new-count">+{fmt(selectedDeptInfo.n_new_90d)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.new7d')}</div>
				<div class="stat-value">
					<span style:color={trendColor(selectedDeptInfo.trend)}>
						{trendIcon(selectedDeptInfo.trend)} {fmt(selectedDeptInfo.n_new_7d)}
					</span>
				</div>
			</div>
		</div>

		<!-- Change history mini chart -->
		{#if deptChangeBars.length > 0}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.catastro.changeHistory')}</div>
				<div class="change-chart">
					{#each deptChangeBars as bar}
						{@const maxN = Math.max(...deptChangeBars.map(b => Math.max(b.nNew, b.nRemoved)), 1)}
						<div class="change-bar-group" title="{bar.date}: +{bar.nNew} / -{bar.nRemoved}">
							<div class="change-bar new" style:height="{Math.max(2, (bar.nNew / maxN) * 40)}px"></div>
							{#if bar.nRemoved > 0}
								<div class="change-bar removed" style:height="{Math.max(2, (bar.nRemoved / maxN) * 40)}px"></div>
							{/if}
							<div class="change-bar-label">{bar.date.slice(5)}</div>
						</div>
					{/each}
				</div>
				<div class="change-legend">
					<span class="legend-swatch" style:background="#4ade80"></span> {i18n.t('analysis.catastro.newParcels')}
					<span class="legend-swatch legend-gap" style:background="#f87171"></span> {i18n.t('analysis.catastro.removedParcels')}
				</div>
			</div>
		{/if}

		<div class="hint">{i18n.t('analysis.catastro.clickDept')}</div>

		<div class="map-legend">
			<span class="legend-swatch" style:background="#06b6d4"></span> {i18n.t('analysis.catastro.legendUrban')}
			<span class="legend-swatch legend-gap" style:background="#4ade80"></span> {i18n.t('analysis.catastro.legendRural')}
			<span class="legend-swatch legend-gap" style:background="#fbbf24"></span> {i18n.t('analysis.catastro.legendNew')}
		</div>
		<div class="source-note-box">
			<div><strong>{i18n.t('data.source.catastro')}</strong></div>
			<div>{i18n.t('analysis.catastro.updateFreq')} · {DATA_FRESHNESS.catastro_by_radio?.processedDate ?? ''}</div>
		</div>
	</div>
{:else}
	<!-- Provincial summary with department selector -->
	<div class="provincial-summary">
		<div class="stat-grid">
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalUrban')}</div>
				<div class="stat-value">{fmt(deptSummaryData?.total_parcelas ? deptSummaryData.total_parcelas - deptList.reduce((s: number, d: any) => s + d.n_rural, 0) : 0)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalRural')}</div>
				<div class="stat-value">{fmt(deptList.reduce((s: number, d: any) => s + d.n_rural, 0))}</div>
			</div>
			<div class="stat-item full-width highlight">
				<div class="stat-label">{i18n.t('analysis.catastro.totalParcels')}</div>
				<div class="stat-value new-count">{fmt(deptSummaryData?.total_parcelas)}</div>
			</div>
		</div>

		{#if deptList.length > 0}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.catastro.topDepts')}</div>
				{#each deptList as dept}
					<button class="dept-row dept-clickable" onclick={() => handleDptoClick(dept)}>
						<span class="dept-name">{dept.name}</span>
						<span class="dept-count">{fmt(dept.n_parcelas)}</span>
						{#if dept.n_new_7d > 0 || dept.n_removed_7d > 0}
							<span class="dept-trend" style:color={trendColor(dept.trend)}>
								{trendIcon(dept.trend)}
								{#if dept.n_new_7d > 0}+{dept.n_new_7d}{/if}
							</span>
						{/if}
					</button>
				{/each}
			</div>
		{/if}

		<details class="method-details">
			<summary class="method-summary">{i18n.t('analysis.catastro.howToReadTitle')}</summary>
			<div class="method-body">
				<p class="explain-text">{i18n.t('analysis.catastro.howToReadBody')}</p>
				<div class="map-legend" style="margin-top: 6px;">
					<span class="legend-swatch" style:background="#06b6d4"></span> {i18n.t('analysis.catastro.legendUrban')}
					<span class="legend-swatch legend-gap" style:background="#4ade80"></span> {i18n.t('analysis.catastro.legendRural')}
				</div>
			</div>
		</details>

		<details class="method-details">
			<summary class="method-summary">{i18n.t('analysis.catastro.implicationsTitle')}</summary>
			<div class="method-body">
				<p class="explain-text">{i18n.t('analysis.catastro.implicationsBody')}</p>
			</div>
		</details>

		<details class="method-details">
			<summary class="method-summary">{i18n.t('analysis.catastro.methodTitle')}</summary>
			<div class="method-body">
				<p class="explain-text">{i18n.t('analysis.catastro.methodBody')}</p>
			</div>
		</details>

		<div class="source-note-box">
			<div><strong>{i18n.t('data.source.catastro')}</strong></div>
			<div>{i18n.t('analysis.catastro.updateFreq')} · {DATA_FRESHNESS.catastro_by_radio?.processedDate ?? ''}</div>
		</div>

		<CTADiagnostic analysisName={i18n.t('analysis.catastro.title')} />
	</div>
{/if}

<style>
	.loading { color: #a3a3a3; font-size: 10px; padding: 12px 0; }

	/* Radio chips header */
	.radios-header { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
	.radio-chip { display: inline-flex; align-items: center; gap: 3px; background: rgba(255,255,255,0.05); border-radius: 12px; padding: 2px 6px 2px 4px; font-size: 9px; }
	.chip-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
	.chip-code { font-family: monospace; font-weight: 600; color: #e2e8f0; }
	.chip-x { background: none; border: none; color: #737373; cursor: pointer; font-size: 10px; padding: 0 2px; line-height: 1; }
	.chip-x:hover { color: #ef4444; }
	.clear-btn { background: none; border: 1px solid rgba(239,68,68,0.3); color: #ef4444; font-size: 8px; padding: 2px 8px; border-radius: 10px; cursor: pointer; transition: all 0.15s; }
	.clear-btn:hover { background: rgba(239,68,68,0.1); }

	/* Radio metrics */
	.radio-metrics { background: rgba(255,255,255,0.03); border-radius: 6px; padding: 6px 8px; margin-bottom: 6px; }
	.radio-metrics-header { display: flex; align-items: center; gap: 4px; margin-bottom: 4px; }
	.radio-code { font-family: monospace; font-size: 9px; color: #a3a3a3; }
	.mini-stats { display: flex; flex-wrap: wrap; gap: 8px; font-size: 9px; color: #d4d4d4; }
	.mini-stats strong { color: #e2e8f0; }
	.new-badge { color: #4ade80; font-weight: 600; }

	/* Map legend */
	.map-legend { display: flex; align-items: center; gap: 4px; font-size: 8px; color: #a3a3a3; margin: 8px 0 4px; }
	.legend-swatch { width: 10px; height: 3px; border-radius: 1px; flex-shrink: 0; }
	.legend-gap { margin-left: 8px; }

	/* Sections */
	.section { margin-bottom: 8px; }
	.section-title { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #a3a3a3; border-bottom: 1px solid #1e293b; padding-bottom: 2px; margin-bottom: 4px; }

	/* Petal */
	.petal-wrapper { display: flex; justify-content: center; margin: 4px 0; }
	.petal-hint { font-size: 7px; color: #737373; text-align: center; margin-top: 4px; }

	/* Stat grid */
	.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px; }
	.stat-item { background: rgba(255,255,255,0.03); border-radius: 6px; padding: 6px 8px; }
	.stat-item.highlight { background: rgba(6,182,212,0.08); border: 1px solid rgba(6,182,212,0.2); }
	.stat-item.full-width { grid-column: 1 / -1; }
	.stat-label { font-size: 8px; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 2px; }
	.stat-value { font-size: 13px; font-weight: 600; color: #e2e8f0; }
	.stat-value.new-count { color: #06b6d4; }

	/* Department rows */
	.dept-row { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }
	.dept-clickable { background: none; border: none; width: 100%; text-align: left; cursor: pointer; padding: 4px 6px; border-radius: 4px; transition: background 0.15s; }
	.dept-clickable:hover { background: rgba(6,182,212,0.1); }
	.dept-name { font-size: 10px; color: #d4d4d4; flex: 1; }
	.dept-count { font-size: 9px; color: #a3a3a3; font-variant-numeric: tabular-nums; }
	.dept-trend { font-size: 8px; font-weight: 600; min-width: 32px; text-align: right; }

	/* Department detail */
	.dept-detail { font-size: 11px; }
	.back-btn { background: none; border: none; color: #60a5fa; font-size: 10px; cursor: pointer; padding: 0; margin-bottom: 8px; }
	.back-btn:hover { text-decoration: underline; }
	.dept-active-title { font-size: 14px; font-weight: 700; color: #e2e8f0; margin-bottom: 8px; }
	.hint { font-size: 9px; color: #a3a3a3; text-align: center; margin: 8px 0; }

	/* Change history chart */
	.change-chart { display: flex; gap: 4px; align-items: flex-end; padding: 4px 0; min-height: 50px; }
	.change-bar-group { display: flex; flex-direction: column; align-items: center; gap: 1px; flex: 1; }
	.change-bar { width: 100%; border-radius: 2px 2px 0 0; min-height: 2px; }
	.change-bar.new { background: #4ade80; }
	.change-bar.removed { background: #f87171; border-radius: 0 0 2px 2px; }
	.change-bar-label { font-size: 7px; color: #737373; margin-top: 2px; }
	.change-legend { display: flex; align-items: center; gap: 4px; font-size: 7px; color: #a3a3a3; margin-top: 4px; }

	/* Source + method */
	.radio-detail { padding: 2px 0; }
	.source-note-box { margin-top: 10px; padding: 6px 8px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px; font-size: 8px; color: #737373; line-height: 1.4; }
	.method-details { margin-top: 8px; border: 1px solid rgba(100,116,139,0.15); border-radius: 6px; overflow: hidden; }
	.method-summary { font-size: 9px; font-weight: 600; color: #d4d4d4; padding: 6px 8px; cursor: pointer; user-select: none; list-style: none; display: flex; align-items: center; gap: 4px; }
	.method-summary::before { content: '\25B8'; font-size: 8px; transition: transform 0.15s; }
	.method-details[open] > .method-summary::before { transform: rotate(90deg); }
	.method-summary::-webkit-details-marker { display: none; }
	.method-body { padding: 4px 8px 8px; }
	.explain-text { font-size: 9px; color: #a3a3a3; line-height: 1.5; margin: 2px 0 0; }
</style>
