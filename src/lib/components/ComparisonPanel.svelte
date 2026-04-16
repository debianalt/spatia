<script lang="ts">
	import { query, isReady } from '$lib/stores/duckdb';
	import { HEX_LAYER_REGISTRY, getSatGlobalUrl, TERRITORY_REGISTRY, type TerritoryConfig } from '$lib/config';
	import type { TerritoryStore } from '$lib/stores/territory.svelte';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import { loadDeptList, type DeptItem } from '$lib/utils/deptSummaries';

	let {
		territoryStore,
		lensStore,
		hexStore,
	}: {
		territoryStore: TerritoryStore;
		lensStore: LensStore;
		hexStore: HexStore;
	} = $props();

	interface TerritoryStats {
		territory: TerritoryConfig;
		values: Record<string, number | null>;
		error?: string;
	}

	let stats: TerritoryStats[] = $state([]);
	let loading = $state(false);

	// Compare dept selector
	let compareDeptList: DeptItem[] = $state([]);
	let loadingDeptList = $state(false);
	let compareDeptOpen = $state(false);

	const activeLayer = $derived(
		lensStore.activeAnalysis ? HEX_LAYER_REGISTRY[lensStore.activeAnalysis.id] : null
	);

	const NON_NUMERIC = new Set(['type', 'type_label', 'pca_1', 'pca_2', 'pca_3', 'territorial_type']);
	const compareVars = $derived(
		activeLayer?.variables.filter(v => !NON_NUMERIC.has(v.col)) ?? []
	);

	// Load compare territory dept list when analysis or compare territory changes
	$effect(() => {
		const compareTerritory = territoryStore.compareTerritory;
		const analysis = lensStore.activeAnalysis;
		compareDeptList = [];
		compareDeptOpen = false;
		if (!compareTerritory || !analysis) return;
		loadingDeptList = true;
		loadDeptList(analysis.id, compareTerritory.parquetPrefix).then(list => {
			compareDeptList = list;
			loadingDeptList = false;
		});
	});

	function selectCompareDept(item: DeptItem) {
		const ct = territoryStore.compareTerritory;
		if (!ct) return;
		hexStore.loadCompareDept(item.name, item.parquetKey, ct.parquetPrefix);
		compareDeptOpen = false;
	}

	async function loadStats(territory: TerritoryConfig, cols: string[]): Promise<TerritoryStats> {
		if (cols.length === 0) return { territory, values: {} };
		const analysisId = lensStore.activeAnalysis?.id ?? '';
		if (analysisId === 'flood_risk') return { territory, values: {}, error: 'Sin datos globales' };
		const url = getSatGlobalUrl(analysisId, territory.parquetPrefix);

		try {
			const schema = await query(`DESCRIBE SELECT * FROM '${url}'`);
			const available = new Set<string>();
			for (let i = 0; i < schema.numRows; i++) {
				const row = schema.get(i)!.toJSON() as any;
				const name = (row.column_name ?? row['Column Name'] ?? '') as string;
				if (name) available.add(name);
			}
			const validCols = cols.filter(c => available.has(c));
			if (validCols.length === 0) return { territory, values: {} };

			const selects = validCols.map(col => `AVG("${col}") AS "${col}"`).join(', ');
			const result = await query(`SELECT ${selects} FROM '${url}'`);
			const values: Record<string, number | null> = {};
			for (const col of validCols) {
				const vec = result.getChild(col);
				values[col] = vec ? (vec.get(0) as number | null) : null;
			}
			return { territory, values };
		} catch (e) {
			return { territory, values: {}, error: String(e) };
		}
	}

	function computeDeptAvg(territory: TerritoryConfig, cols: string[], data: Map<string, Record<string, any>>): TerritoryStats {
		const values: Record<string, number | null> = {};
		for (const col of cols) {
			const nums = [...data.values()]
				.map(d => d[col])
				.filter((v): v is number => typeof v === 'number' && !isNaN(v));
			values[col] = nums.length > 0 ? nums.reduce((a, b) => a + b, 0) / nums.length : null;
		}
		return { territory, values };
	}

	$effect(() => {
		const layer = activeLayer;
		const primary = territoryStore.activeTerritory;
		const compare = territoryStore.compareTerritory;
		const dpto = hexStore.selectedDpto;
		const compareDpto = hexStore.compareDpto;
		void hexStore.visibleData.size;
		void hexStore.compareVisibleData.size;
		if (!layer || !compare || !isReady()) return;

		const cols = compareVars.map(v => v.col);
		loading = true;
		stats = [];

		if (dpto && hexStore.visibleData.size > 0 && compareDpto && hexStore.compareVisibleData.size > 0) {
			// Dept-to-dept: both from in-memory data
			stats = [
				computeDeptAvg(primary, cols, hexStore.visibleData),
				computeDeptAvg(compare, cols, hexStore.compareVisibleData),
			];
			loading = false;
		} else if (dpto && hexStore.visibleData.size > 0) {
			// Primary dept selected, no compare dept yet
			const localStat = computeDeptAvg(primary, cols, hexStore.visibleData);
			loadStats(compare, cols).then(compareStat => {
				stats = [localStat, compareStat];
				loading = false;
			}).catch(() => { loading = false; });
		} else {
			// Territory-level: both from global parquets
			Promise.all([loadStats(primary, cols), loadStats(compare, cols)]).then(results => {
				stats = results;
				loading = false;
			}).catch(() => { loading = false; });
		}
	});

	function fmt(v: number | null | undefined): string {
		if (v == null) return '—';
		const abs = Math.abs(v);
		if (abs >= 1000) return v.toFixed(0);
		if (abs >= 10) return v.toFixed(1);
		if (abs >= 0.1) return v.toFixed(2);
		return v.toFixed(3);
	}

	function diff(a: number | null | undefined, b: number | null | undefined): string {
		if (a == null || b == null) return '';
		const d = b - a;
		const sign = d > 0 ? '+' : '';
		return `${sign}${fmt(d)}`;
	}

	function diffClass(a: number | null | undefined, b: number | null | undefined): string {
		if (a == null || b == null) return '';
		return b > a ? 'pos' : b < a ? 'neg' : '';
	}

	// Compare trigger (shown when compare mode inactive + dept selected + candidates available)
	const compareCandidates = $derived(
		Object.values(TERRITORY_REGISTRY).filter(
			t => t.available && t.id !== territoryStore.activeTerritory.id
		)
	);

	const showTrigger = $derived(
		!territoryStore.compareModeActive &&
		!!hexStore.selectedDpto &&
		!!lensStore.activeAnalysis &&
		compareCandidates.length > 0
	);

	function activateCompare() {
		if (compareCandidates.length === 1) {
			territoryStore.enterCompareMode(compareCandidates[0].id);
		}
	}
</script>

{#if showTrigger}
	<div class="compare-trigger">
		<button class="trigger-btn" onclick={activateCompare}>
			Comparar {hexStore.selectedDpto} →
		</button>
		<span class="trigger-hint">con {compareCandidates[0].flag} {compareCandidates[0].label}</span>
	</div>
{:else if territoryStore.compareModeActive && territoryStore.compareTerritory}
	{@const ct = territoryStore.compareTerritory}
	<div class="comparison-panel">
		<div class="panel-header">
			<span class="panel-title">
				{activeLayer ? i18n.t(activeLayer.titleKey) : 'Comparación territorial'}
			</span>
			<button class="close-btn" onclick={() => territoryStore.exitCompareMode()}>×</button>
		</div>

		<!-- Compare dept selector (shown when primary dept is selected) -->
		{#if hexStore.selectedDpto && activeLayer}
			<div class="dept-row">
				<span class="dept-label">{ct.flag} Distrito:</span>
				{#if loadingDeptList}
					<span class="dept-loading">…</span>
				{:else if compareDeptList.length > 0}
					<div class="dept-select-wrap">
						<button class="dept-select-btn" onclick={() => compareDeptOpen = !compareDeptOpen}>
							<span>{hexStore.compareDpto ?? 'elegir…'}</span>
							<svg width="8" height="8" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
								<path d="M1 3 L5 7 L9 3"/>
							</svg>
						</button>
						{#if compareDeptOpen}
							<div class="dept-dropdown">
								{#each compareDeptList as item (item.parquetKey)}
									<button
										class="dept-opt"
										class:sel={hexStore.compareDpto === item.name}
										onclick={() => selectCompareDept(item)}
									>{item.name}</button>
								{/each}
							</div>
						{/if}
					</div>
				{:else}
					<span class="dept-none">Sin datos</span>
				{/if}
			</div>
		{/if}

		{#if !activeLayer}
			<p class="hint">Seleccioná un análisis para comparar.</p>
		{:else if loading}
			<p class="hint">Cargando datos…</p>
		{:else if stats.length === 2}
			{@const dpto = hexStore.selectedDpto}
			{@const compareDpto = hexStore.compareDpto}
			{@const primaryLabel = dpto ? (dpto.length > 10 ? dpto.slice(0, 9) + '.' : dpto) : stats[0].territory.shortLabel}
			{@const compareLabel = compareDpto ? (compareDpto.length > 10 ? compareDpto.slice(0, 9) + '.' : compareDpto) : stats[1].territory.shortLabel}
			<table class="stats-table">
				<thead>
					<tr>
						<th class="col-var"></th>
						<th class="col-val">{stats[0].territory.flag} {primaryLabel}</th>
						<th class="col-val">{stats[1].territory.flag} {compareLabel}</th>
						<th class="col-diff">Δ</th>
					</tr>
				</thead>
				<tbody>
					{#if stats[0].error || stats[1].error}
						<tr><td colspan="4" class="hint">{stats[0].error ?? stats[1].error}</td></tr>
					{:else}
						{#each compareVars as v}
							{@const a = stats[0].values[v.col]}
							{@const b = stats[1].values[v.col]}
							<tr>
								<td class="col-var">{i18n.t(v.labelKey)}</td>
								<td class="col-val">{fmt(a)}{v.unit ? ` ${v.unit}` : ''}</td>
								<td class="col-val">{fmt(b)}{v.unit ? ` ${v.unit}` : ''}</td>
								<td class="col-diff {diffClass(a, b)}">{diff(a, b)}</td>
							</tr>
						{/each}
					{/if}
				</tbody>
			</table>
			<p class="note">
				{#if dpto && compareDpto}
					Dept. {dpto} ({stats[0].territory.flag}) vs Dist. {compareDpto} ({stats[1].territory.flag})
				{:else if dpto}
					Dept. {dpto} ({stats[0].territory.flag}) vs {stats[1].territory.flag} prom. provincial
				{:else}
					Prom. {stats[0].territory.flag} vs prom. {stats[1].territory.flag}
				{/if}
			</p>
		{/if}
	</div>
{/if}

<style>
	.comparison-panel {
		margin-top: 8px;
		padding: 8px 10px;
		background: rgba(59, 130, 246, 0.08);
		border: 1px solid rgba(59, 130, 246, 0.20);
		border-radius: 6px;
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 6px;
	}

	.panel-title {
		font-size: 9px;
		font-weight: 700;
		color: #93c5fd;
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}

	.close-btn {
		background: none;
		border: none;
		color: rgba(255, 255, 255, 0.35);
		font-size: 14px;
		cursor: pointer;
		padding: 0 2px;
		line-height: 1;
	}
	.close-btn:hover { color: rgba(255, 255, 255, 0.7); }

	/* Compare dept selector */
	.dept-row {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-bottom: 6px;
		flex-wrap: wrap;
	}
	.dept-label {
		font-size: 8.5px;
		color: rgba(255, 255, 255, 0.45);
		white-space: nowrap;
	}
	.dept-loading, .dept-none {
		font-size: 8.5px;
		color: rgba(255, 255, 255, 0.30);
		font-style: italic;
	}
	.dept-select-wrap { position: relative; }
	.dept-select-btn {
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 3px 7px;
		background: rgba(255,255,255,0.06);
		border: 1px solid rgba(255,255,255,0.14);
		border-radius: 4px;
		color: #e2e8f0;
		font-size: 9px;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.1s;
	}
	.dept-select-btn:hover { background: rgba(255,255,255,0.10); }
	.dept-dropdown {
		position: absolute;
		top: calc(100% + 3px);
		left: 0;
		min-width: 140px;
		max-height: 180px;
		overflow-y: auto;
		background: rgba(10, 14, 22, 0.98);
		border: 1px solid rgba(255,255,255,0.12);
		border-radius: 5px;
		z-index: 50;
		padding: 3px;
		scrollbar-width: thin;
		scrollbar-color: #334155 transparent;
	}
	.dept-opt {
		display: block;
		width: 100%;
		padding: 4px 8px;
		background: none;
		border: none;
		border-radius: 3px;
		text-align: left;
		font-size: 9px;
		color: rgba(255,255,255,0.75);
		cursor: pointer;
		transition: background 0.1s;
	}
	.dept-opt:hover { background: rgba(255,255,255,0.07); }
	.dept-opt.sel { color: #f97316; font-weight: 700; }

	.hint {
		font-size: 9px;
		color: rgba(255, 255, 255, 0.40);
		font-style: italic;
		margin: 4px 0;
	}

	.stats-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 9px;
	}

	.stats-table th {
		color: rgba(255, 255, 255, 0.40);
		font-weight: 600;
		font-size: 8px;
		padding: 2px 4px;
		text-align: right;
		border-bottom: 1px solid rgba(255, 255, 255, 0.08);
	}
	.stats-table th.col-var { text-align: left; }

	.stats-table td {
		padding: 3px 4px;
		color: rgba(255, 255, 255, 0.75);
		border-bottom: 1px solid rgba(255, 255, 255, 0.04);
		text-align: right;
		white-space: nowrap;
	}
	.stats-table td.col-var {
		text-align: left;
		color: rgba(255, 255, 255, 0.55);
		font-size: 8.5px;
		max-width: 110px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.col-diff { font-weight: 600; font-size: 8px; }
	.col-diff.pos { color: #4ade80; }
	.col-diff.neg { color: #f87171; }

	.note {
		font-size: 7.5px;
		color: rgba(255, 255, 255, 0.25);
		margin: 5px 0 0;
		text-align: right;
		font-style: italic;
	}

	.compare-trigger {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-top: 6px;
		margin-bottom: 2px;
		padding: 6px 8px;
		background: rgba(59, 130, 246, 0.05);
		border: 1px solid rgba(59, 130, 246, 0.15);
		border-radius: 5px;
	}

	.trigger-btn {
		background: none;
		border: none;
		color: #93c5fd;
		font-size: 9px;
		font-weight: 600;
		cursor: pointer;
		padding: 0;
		transition: color 0.15s;
		white-space: nowrap;
	}

	.trigger-btn:hover { color: #bfdbfe; }

	.trigger-hint {
		font-size: 8px;
		color: rgba(255, 255, 255, 0.30);
		white-space: nowrap;
	}
</style>
