<script lang="ts">
	import { query, isReady } from '$lib/stores/duckdb';
	import { HEX_LAYER_REGISTRY, getSatGlobalUrl, TERRITORY_REGISTRY, type TerritoryConfig } from '$lib/config';
	import type { TerritoryStore } from '$lib/stores/territory.svelte';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import { loadDeptList, type DeptItem } from '$lib/utils/deptSummaries';
	import PetalChart from './PetalChart.svelte';

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
		rawValues: Record<string, number | null>;
		error?: string;
	}

	interface TerritoryGroup {
		territory: TerritoryConfig;
		depts: DeptItem[];
	}

	let stats: TerritoryStats[] = $state([]);
	let loading = $state(false);
	let groups: TerritoryGroup[] = $state([]);
	let selectorOpen = $state(false);
	let statsGen = 0; // generation counter — cancels stale async loadStats promises

	const activeLayer = $derived(
		lensStore.activeAnalysis ? HEX_LAYER_REGISTRY[lensStore.activeAnalysis.id] : null
	);

	const NON_NUMERIC = new Set(['type', 'type_label', 'pca_1', 'pca_2', 'pca_3', 'territorial_type']);
	const compareVars = $derived(
		activeLayer?.variables.filter(v => !NON_NUMERIC.has(v.col)) ?? []
	);

	const petalVars = $derived(compareVars.filter(v => v.unit === 'percentil'));
	const hasPetal  = $derived(petalVars.length >= 3);
	const petalLayers = $derived.by(() => {
		if (!hasPetal || stats.length !== 2) return [];
		return [
			{ values: petalVars.map(v => stats[0].values[v.col] ?? 0), color: '#60a5fa' },
			{ values: petalVars.map(v => stats[1].values[v.col] ?? 0), color: '#fbbf24' },
		];
	});
	const petalLabels = $derived(petalVars.map(v => i18n.t(v.labelKey)));

	// Preload dept lists for ALL available territories when analysis changes
	$effect(() => {
		const analysis = lensStore.activeAnalysis;
		groups = [];
		selectorOpen = false;
		if (!analysis) return;
		const territories = Object.values(TERRITORY_REGISTRY).filter(t => t.available);
		Promise.all(
			territories.map(t =>
				loadDeptList(analysis.id, t.parquetPrefix).then(depts => ({ territory: t, depts }))
			)
		).then(results => {
			groups = results;
		});
	});

	function selectTarget(t: TerritoryConfig, dept?: DeptItem) {
		territoryStore.enterCompareMode(t.id);
		if (dept) {
			hexStore.loadCompareDept(dept.name, dept.parquetKey, t.parquetPrefix);
		} else {
			hexStore.loadFullCompare(t.parquetPrefix);
		}
		selectorOpen = false;
	}

	async function loadStats(territory: TerritoryConfig, cols: string[]): Promise<TerritoryStats> {
		if (cols.length === 0) return { territory, values: {}, rawValues: {} };
		const analysisId = lensStore.activeAnalysis?.id ?? '';
		if (analysisId === 'flood_risk') return { territory, values: {}, rawValues: {}, error: 'Sin datos globales' };
		const url = getSatGlobalUrl(analysisId, territory.parquetPrefix);

		const rawColMap = new Map<string, string>();
		for (const v of compareVars) {
			if (v.rawCol) rawColMap.set(v.col, v.rawCol);
		}

		try {
			const schema = await query(`DESCRIBE SELECT * FROM '${url}'`);
			const available = new Set<string>();
			for (let i = 0; i < schema.numRows; i++) {
				const row = schema.get(i)!.toJSON() as any;
				const name = (row.column_name ?? row['Column Name'] ?? '') as string;
				if (name) available.add(name);
			}
			const validCols = cols.filter(c => available.has(c));
			if (validCols.length === 0) return { territory, values: {}, rawValues: {} };

			const rawCols = [...rawColMap.values()].filter(c => available.has(c));
			const allCols = [...new Set([...validCols, ...rawCols])];
			const selects = allCols.map(col => `AVG("${col}") AS "${col}"`).join(', ');
			const result = await query(`SELECT ${selects} FROM '${url}'`);
			const values: Record<string, number | null> = {};
			const rawValues: Record<string, number | null> = {};
			for (const col of validCols) {
				const vec = result.getChild(col);
				values[col] = vec ? (vec.get(0) as number | null) : null;
			}
			for (const col of rawCols) {
				const vec = result.getChild(col);
				rawValues[col] = vec ? (vec.get(0) as number | null) : null;
			}
			return { territory, values, rawValues };
		} catch (e) {
			return { territory, values: {}, rawValues: {}, error: String(e) };
		}
	}

	function computeDeptAvg(territory: TerritoryConfig, cols: string[], data: Map<string, Record<string, any>>): TerritoryStats {
		const values: Record<string, number | null> = {};
		const rawValues: Record<string, number | null> = {};
		const rawCols = new Set<string>();
		for (const v of compareVars) {
			if (v.rawCol) rawCols.add(v.rawCol);
		}
		for (const col of [...cols, ...rawCols]) {
			const nums = [...data.values()]
				.map(d => d[col])
				.filter((v): v is number => typeof v === 'number' && !isNaN(v));
			const avg = nums.length > 0 ? nums.reduce((a, b) => a + b, 0) / nums.length : null;
			if (rawCols.has(col)) rawValues[col] = avg;
			else values[col] = avg;
		}
		return { territory, values, rawValues };
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
		const gen = ++statsGen; // mark this run; stale async results will be discarded
		loading = true;
		stats = [];

		if (dpto && hexStore.visibleData.size > 0 && compareDpto && hexStore.compareVisibleData.size > 0) {
			// Dept-to-dept: both from in-memory data — synchronous, no race risk
			stats = [
				computeDeptAvg(primary, cols, hexStore.visibleData),
				computeDeptAvg(compare, cols, hexStore.compareVisibleData),
			];
			loading = false;
		} else if (dpto && hexStore.visibleData.size > 0) {
			// Primary dept selected, compare dept loading or not yet chosen
			const localStat = computeDeptAvg(primary, cols, hexStore.visibleData);
			loadStats(compare, cols).then(compareStat => {
				if (statsGen !== gen) return; // superseded by newer run
				stats = [localStat, compareStat];
				loading = false;
			}).catch(() => { if (statsGen === gen) loading = false; });
		} else if (!dpto && compareDpto && hexStore.compareVisibleData.size > 0) {
			// No primary dept, compare dept loaded — primary is territory-level
			const compareStat = computeDeptAvg(compare, cols, hexStore.compareVisibleData);
			loadStats(primary, cols).then(primaryStat => {
				if (statsGen !== gen) return;
				stats = [primaryStat, compareStat];
				loading = false;
			}).catch(() => { if (statsGen === gen) loading = false; });
		} else {
			// Territory-level: both from global parquets
			Promise.all([loadStats(primary, cols), loadStats(compare, cols)]).then(results => {
				if (statsGen !== gen) return;
				stats = results;
				loading = false;
			}).catch(() => { if (statsGen === gen) loading = false; });
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
</script>

<div class="cp-root" class:cp-full={territoryStore.compareModeActive && !!activeLayer}>
	{#if activeLayer}
		<!-- Selector row: always visible when analysis active -->
		<div class="compare-row">
			<button class="compare-row-btn" onclick={() => selectorOpen = !selectorOpen}>
				{#if territoryStore.compareModeActive && territoryStore.compareTerritory}
					{territoryStore.compareTerritory.flag}
					{hexStore.compareDpto ?? territoryStore.compareTerritory.shortLabel} ▾
				{:else}
					Comparar con… ▾
				{/if}
			</button>
			{#if territoryStore.compareModeActive}
				<button class="close-btn" onclick={() => territoryStore.exitCompareMode()}>← volver</button>
			{/if}
			{#if selectorOpen}
				<div class="compare-dropdown">
					{#each groups as g (g.territory.id)}
						<div class="group-header">{g.territory.flag} {g.territory.label}</div>
						<button class="opt opt-province" onclick={() => selectTarget(g.territory)}>
							{g.territory.shortLabel} (provincia)
						</button>
						{#each g.depts.filter(d => d.name !== hexStore.selectedDpto) as d (d.parquetKey)}
							<button class="opt opt-dept" onclick={() => selectTarget(g.territory, d)}>
								{d.name}
							</button>
						{/each}
					{/each}
				</div>
			{/if}
		</div>

		<!-- Stats panel: only when compare active -->
		{#if territoryStore.compareModeActive && territoryStore.compareTerritory}
			{@const ct = territoryStore.compareTerritory}
			<div class="comparison-panel">
				<div class="panel-header">
					<span class="panel-title">
						{activeLayer ? i18n.t(activeLayer.titleKey) : 'Comparación territorial'}
					</span>
				</div>

				{#if loading}
					<p class="hint">Cargando datos…</p>
				{:else if stats.length === 2}
					{@const dpto = hexStore.selectedDpto}
					{@const compareDpto = hexStore.compareDpto}
					{@const primaryLabel = dpto ? (dpto.length > 10 ? dpto.slice(0, 9) + '.' : dpto) : stats[0].territory.shortLabel}
					{@const compareLabel = compareDpto ? (compareDpto.length > 10 ? compareDpto.slice(0, 9) + '.' : compareDpto) : stats[1].territory.shortLabel}
					{#if hasPetal && !stats[0].error && !stats[1].error}
						<div class="petal-section">
							<div class="petal-legend">
								<span class="petal-dot" style="background:#60a5fa"></span>
								<span class="petal-leg-label">{stats[0].territory.flag} {primaryLabel}</span>
								<span class="petal-dot" style="background:#fbbf24"></span>
								<span class="petal-leg-label">{stats[1].territory.flag} {compareLabel}</span>
							</div>
							<PetalChart layers={petalLayers} labels={petalLabels} size={200} />
						</div>
					{/if}
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
									{@const rawA = v.rawCol ? stats[0].rawValues[v.rawCol] : null}
									{@const rawB = v.rawCol ? stats[1].rawValues[v.rawCol] : null}
									{@const a = (rawA != null && typeof rawA === 'number') ? rawA : stats[0].values[v.col]}
									{@const b = (rawB != null && typeof rawB === 'number') ? rawB : stats[1].values[v.col]}
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
					{@const deptLabel = (t: typeof stats[0]['territory']) => t.country === 'py' ? 'Dist.' : t.country === 'br' ? 'Mun.' : 'Dept.'}
					{@const crossTerritory = stats[0].territory.id !== stats[1].territory.id}
					{@const hasPercentil = compareVars.some(v => v.unit === 'percentil')}
					<p class="note">
						{#if dpto && compareDpto}
							{deptLabel(stats[0].territory)} {dpto} ({stats[0].territory.flag}) vs {deptLabel(stats[1].territory)} {compareDpto} ({stats[1].territory.flag})
						{:else if dpto}
							{deptLabel(stats[0].territory)} {dpto} ({stats[0].territory.flag}) vs {stats[1].territory.flag} prom. provincial
						{:else}
							Prom. {stats[0].territory.flag} vs prom. {stats[1].territory.flag}
						{/if}
					</p>
					{#if crossTerritory && hasPercentil}
						<p class="note note-warn">Percentiles calculados dentro de cada provincia. El eje 50 = mediana provincial.</p>
					{/if}
				{/if}
			</div>
		{/if}
	{/if}
</div>

<style>
	.cp-root { }

	.cp-root.cp-full {
		max-height: 280px;
		overflow-y: auto;
	}

	/* Selector row */
	.compare-row {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 5px 0;
		border-bottom: 1px solid rgba(255,255,255,0.06);
		margin-bottom: 4px;
		position: relative;
	}

	.compare-row-btn {
		font-size: 9px;
		font-weight: 600;
		color: #93c5fd;
		background: none;
		border: none;
		cursor: pointer;
		padding: 2px 4px;
		transition: color 0.15s;
	}
	.compare-row-btn:hover { color: #bfdbfe; }

	.close-btn {
		background: rgba(255, 255, 255, 0.07);
		border: 1px solid rgba(255, 255, 255, 0.15);
		border-radius: 3px;
		color: rgba(255, 255, 255, 0.7);
		font-size: 9px;
		font-weight: 600;
		cursor: pointer;
		padding: 2px 6px;
		line-height: 1.4;
		margin-left: auto;
	}
	.close-btn:hover { color: #fff; background: rgba(255, 255, 255, 0.12); }

	/* Hierarchical dropdown */
	.compare-dropdown {
		position: absolute;
		top: calc(100% + 3px);
		left: 0;
		min-width: 180px;
		max-height: 260px;
		overflow-y: auto;
		background: rgba(10, 14, 22, 0.98);
		border: 1px solid rgba(255,255,255,0.12);
		border-radius: 5px;
		z-index: 50;
		padding: 4px;
		scrollbar-width: thin;
		scrollbar-color: #334155 transparent;
	}

	.group-header {
		font-size: 8px;
		font-weight: 700;
		color: rgba(255,255,255,0.35);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		padding: 6px 8px 2px;
	}
	.group-header:first-child { padding-top: 3px; }

	.opt {
		display: block;
		width: 100%;
		padding: 3px 8px;
		background: none;
		border: none;
		border-radius: 3px;
		text-align: left;
		font-size: 9px;
		color: rgba(255,255,255,0.75);
		cursor: pointer;
		transition: background 0.1s;
	}
	.opt:hover { background: rgba(255,255,255,0.07); }
	.opt-province { font-weight: 600; color: rgba(255,255,255,0.90); }
	.opt-dept { padding-left: 16px; }

	/* Stats panel */
	.comparison-panel {
		margin-top: 4px;
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
	.note-warn {
		color: rgba(251, 191, 36, 0.6);
		font-style: normal;
		text-align: left;
	}

	.petal-section {
		margin: 8px 0 4px;
	}
	.petal-legend {
		display: flex;
		align-items: center;
		gap: 6px;
		justify-content: center;
		margin-bottom: 2px;
	}
	.petal-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.petal-leg-label {
		font-size: 9px;
		color: rgba(255,255,255,0.65);
	}
</style>
