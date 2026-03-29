<script lang="ts">
	import type { RadioData } from '$lib/stores/map.svelte';
	import { PETAL_VARS, normalizeValues, getProvincialAvg } from '$lib/utils/petal';
	import PetalChart from './PetalChart.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		radios,
		onRemoveRadio,
		onClearRadios
	}: {
		radios: Map<string, RadioData>;
		onRemoveRadio: (redcode: string) => void;
		onClearRadios: () => void;
	} = $props();

	const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 0 });

	let provAvg: number[] | null = $state(null);

	// Load provincial averages once enriched data arrives
	$effect(() => {
		const hasEnriched = [...radios.values()].some(d => d.enriched != null);
		if (hasEnriched && !provAvg) {
			getProvincialAvg().then(avg => { provAvg = avg; }).catch(() => {});
		}
	});

	type RadioEntry = { redcode: string; color: string; data: RadioData; rawValues: number[]; normalizedValues: number[]; population: number };

	const entries = $derived.by((): RadioEntry[] => {
		if (!provAvg) return [];
		return [...radios.entries()]
			.filter(([, d]) => d.enriched != null)
			.map(([rc, d]) => {
				const e = d.enriched!;
				const rawValues = PETAL_VARS.map(v => {
					const val = e[v.col];
					return val != null ? parseFloat(val) : 0;
				});
				const normalizedValues = normalizeValues(rawValues, provAvg!);
				const population = parseInt(e.total_personas ?? d.census?.total_personas ?? '0') || 0;
				return { redcode: rc, color: d.color, data: d, rawValues, normalizedValues, population };
			});
	});

	const petalLayers = $derived(entries.map(e => ({ values: e.normalizedValues, color: e.color })));
	const petalLabels = $derived(PETAL_VARS.map(v => i18n.t(v.labelKey)));

	function shortCode(rc: string): string {
		return rc.length > 5 ? '...' + rc.slice(-4) : rc;
	}
</script>

<div class="chart-root">
	<div class="radio-header">
		<span class="radio-title">{i18n.t('side.radios')}</span>
		<button class="radio-clear-btn" onclick={onClearRadios}>
			&#10005; {i18n.t('side.clearRadios')}
		</button>
	</div>

	<!-- Radio chips -->
	<div class="flex flex-wrap gap-1 mb-2">
		{#each [...radios.entries()] as [rc, data]}
			<button
				class="chip"
				style="border-color: {data.color}; color: #e2e8f0;"
				onclick={() => onRemoveRadio(rc)}
				title={i18n.t('side.deselect')}>
				<span class="chip-dot" style="background: {data.color};"></span>
				{shortCode(rc)}
				<span class="chip-x">&times;</span>
			</button>
		{/each}
	</div>

	<!-- Population summary -->
	{#each entries as entry}
		<div class="pop-row">
			<span class="pop-dot" style="background: {entry.color};"></span>
			<span class="pop-code">{shortCode(entry.redcode)}:</span>
			<span class="pop-val">{fmt(entry.population)} hab</span>
		</div>
	{/each}

	<!-- Petal chart (normalized: 50 = provincial avg) -->
	{#if petalLayers.length > 0}
		<p class="ref-note">{i18n.t('zone.petalNote')}</p>
		<PetalChart layers={petalLayers} labels={petalLabels} size={300} />
	{/if}


	<div class="sources">
		<span class="sources-title">{i18n.t('source.title')}</span>
		<span>{i18n.t('source.census')}</span>
		<span>{i18n.t('source.buildings')}</span>
		<span>{i18n.t('source.basemap')}</span>
		<span>{i18n.t('source.terrain')}</span>
	</div>
</div>

<style>
	.chart-root { font-size: 11px; line-height: 1.3; }
	.radio-header {
		display: flex; justify-content: space-between; align-items: center;
		margin-bottom: 6px;
	}
	.radio-title { font-size: 10px; font-weight: 600; color: #e2e8f0; }
	.radio-clear-btn {
		font-size: 9px; padding: 2px 6px; border-radius: 4px;
		background: rgba(255,255,255,0.06); border: 1px solid #334155;
		color: #d4d4d4; cursor: pointer; transition: all 0.15s;
	}
	.radio-clear-btn:hover { border-color: #ef4444; color: #ef4444; }
	.chip {
		display: inline-flex; align-items: center; gap: 3px;
		padding: 1px 6px; border-radius: 9999px;
		border: 1px solid; background: transparent;
		font-size: 10px; cursor: pointer; transition: opacity 0.15s;
	}
	.chip:hover { opacity: 0.7; }
	.chip-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
	.chip-x { font-size: 12px; margin-left: 1px; }

	.pop-row {
		display: flex; align-items: center; gap: 4px;
		font-size: 10px; color: #cbd5e1; margin-bottom: 2px;
	}
	.pop-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
	.pop-code { color: #d4d4d4; font-family: monospace; }
	.pop-val { font-weight: 600; }

	.ref-note {
		font-size: 8px; color: rgba(255,255,255,0.45);
		text-align: center; margin: 4px 0 0;
	}

	.dim-section { margin: 8px 0; }
	.dim-row {
		display: flex; align-items: flex-start; gap: 4px; margin-bottom: 4px;
	}
	.dim-label {
		width: 65px; flex-shrink: 0;
		color: #d4d4d4; font-size: 9px;
		text-align: right; padding-top: 1px;
	}
	.dim-bars-container {
		flex: 1; display: flex; flex-direction: column; gap: 2px;
	}
	.dim-bar-track {
		height: 5px; background: #1e293b;
		border-radius: 3px; overflow: hidden;
	}
	.dim-bar-fill {
		height: 100%; border-radius: 3px;
		transition: width 0.3s ease; min-width: 2px;
	}
	.dim-values {
		display: flex; flex-direction: column;
		align-items: flex-end; gap: 0;
		width: 32px; flex-shrink: 0;
	}
	.dim-val {
		font-size: 8px; font-weight: 600;
		line-height: 7px; color: #cbd5e1;
	}

	.sources {
		display: flex; flex-direction: column; gap: 1px;
		margin-top: 12px; padding-top: 8px;
		border-top: 1px solid rgba(255,255,255,0.06);
		font-size: 8px; color: rgba(255,255,255,0.35); line-height: 1.4;
	}
	.sources-title {
		font-weight: 600; color: rgba(255,255,255,0.45);
		margin-bottom: 1px;
	}
</style>
