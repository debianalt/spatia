<script lang="ts">
	import { query, isReady } from '$lib/stores/duckdb';
	import { HEX_LAYER_REGISTRY, getSatGlobalUrl, getFloodDptoUrl, type TerritoryConfig } from '$lib/config';
	import type { TerritoryStore } from '$lib/stores/territory.svelte';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		territoryStore,
		lensStore,
	}: {
		territoryStore: TerritoryStore;
		lensStore: LensStore;
	} = $props();

	interface TerritoryStats {
		territory: TerritoryConfig;
		values: Record<string, number | null>;
		error?: string;
	}

	let stats: TerritoryStats[] = $state([]);
	let loading = $state(false);

	// The active layer for the selected analysis
	const activeLayer = $derived(
		lensStore.activeAnalysis ? HEX_LAYER_REGISTRY[lensStore.activeAnalysis.id] : null
	);

	// Variables to compare: use rawCol if defined, else col; skip non-numeric
	const NON_NUMERIC = new Set(['type', 'type_label', 'pca_1', 'pca_2', 'pca_3', 'territorial_type']);
	const compareVars = $derived(
		activeLayer?.variables.filter(v => !NON_NUMERIC.has(v.col)) ?? []
	);

	async function loadStats(territory: TerritoryConfig, cols: string[]): Promise<TerritoryStats> {
		if (cols.length === 0) return { territory, values: {} };
		const analysisId = lensStore.activeAnalysis?.id ?? '';
		let url: string;
		if (analysisId === 'flood_risk') {
			// flood_risk has no global parquet — skip comparison
			return { territory, values: {}, error: 'Sin datos globales' };
		} else {
			url = getSatGlobalUrl(analysisId, territory.parquetPrefix);
		}

		const selects = cols.map(col => `AVG("${col}") AS "${col}"`).join(', ');
		try {
			const result = await query(`SELECT ${selects} FROM '${url}'`);
			const values: Record<string, number | null> = {};
			for (const col of cols) {
				const vec = result.getChild(col);
				values[col] = vec ? (vec.get(0) as number | null) : null;
			}
			return { territory, values };
		} catch (e) {
			return { territory, values: {}, error: String(e) };
		}
	}

	$effect(() => {
		const layer = activeLayer;
		const primary = territoryStore.activeTerritory;
		const compare = territoryStore.compareTerritory;
		if (!layer || !compare || !isReady()) return;

		const cols = compareVars.map(v => v.col);
		loading = true;
		stats = [];

		Promise.all([
			loadStats(primary, cols),
			loadStats(compare, cols),
		]).then(results => {
			stats = results;
			loading = false;
		}).catch(() => {
			loading = false;
		});
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

{#if territoryStore.compareModeActive && territoryStore.compareTerritory}
	<div class="comparison-panel">
		<div class="panel-header">
			<span class="panel-title">
				{activeLayer ? i18n.t(activeLayer.titleKey) : 'Comparación territorial'}
			</span>
			<button class="close-btn" onclick={() => territoryStore.exitCompareMode()}>×</button>
		</div>

		{#if !activeLayer}
			<p class="hint">Seleccioná un análisis para comparar.</p>
		{:else if loading}
			<p class="hint">Cargando datos…</p>
		{:else if stats.length === 2}
			<table class="stats-table">
				<thead>
					<tr>
						<th class="col-var"></th>
						<th class="col-val">{stats[0].territory.flag} {stats[0].territory.shortLabel}</th>
						<th class="col-val">{stats[1].territory.flag} {stats[1].territory.shortLabel}</th>
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
			<p class="note">Promedio provincial · valores absolutos</p>
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
</style>
