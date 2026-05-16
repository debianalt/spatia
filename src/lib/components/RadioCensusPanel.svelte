<script lang="ts">
	import { PETAL_VARS, loadRadioPopulation } from '$lib/utils/petal';
	import { i18n } from '$lib/stores/i18n.svelte';
	import HistogramPanel from './HistogramPanel.svelte';
	import ParallelCoords from './ParallelCoords.svelte';

	let { territory }: { territory: string } = $props();

	const TERR_LABEL: Record<string, string> = { misiones: 'Misiones', corrientes: 'Corrientes' };

	let radioData = $state<Map<string, Record<string, any>> | null>(null);
	let activeVars = $state(PETAL_VARS as typeof PETAL_VARS);
	let loadError = $state(false);
	let selectedVar = $state(PETAL_VARS[0].col);

	// Plain var (NOT $state): tracks which territory is loaded so the effect
	// neither loops nor re-queries. Set before the await. Mirrors `prevLens`.
	let loadedFor: string | null = null;

	$effect(() => {
		const terr = territory; // reactive dep — reload on territory switch
		if (terr === loadedFor) return;
		loadedFor = terr;
		radioData = null;
		loadError = false;
		loadRadioPopulation(terr)
			.then(({ data, vars }) => {
				if (loadedFor !== terr) return;
				radioData = data;
				activeVars = vars;
			})
			.catch(() => { if (loadedFor === terr) loadError = true; });
	});

	// Defensive: when vars shrink (MIS 6 → COR 5) keep a valid selection.
	const effVar = $derived(
		activeVars.some((v) => v.col === selectedVar) ? selectedVar : activeVars[0].col
	);
</script>

<div class="chart-root">
	<div class="rc-header">
		<span class="rc-title">{i18n.t('side.radioCensus.title')} — {TERR_LABEL[territory] ?? territory}</span>
	</div>
	<p class="rc-subtitle">{i18n.t('side.radioCensus.subtitle')}</p>

	{#if loadError}
		<p class="rc-msg">{i18n.t('side.radioCensus.error')}</p>
	{:else if radioData === null}
		<p class="rc-msg">{i18n.t('side.radioCensus.loading')}</p>
	{:else if radioData.size === 0}
		<p class="rc-msg">{i18n.t('side.radioCensus.empty')}</p>
	{:else}
		<label class="rc-select-row">
			<span class="rc-select-label">{i18n.t('side.radioCensus.variable')}</span>
			<select class="rc-select" bind:value={selectedVar}>
				{#each activeVars as v}
					<option value={v.col}>{i18n.t(v.labelKey)}</option>
				{/each}
			</select>
		</label>

		<HistogramPanel data={radioData} variable={effVar} xLabel="%" />
		<ParallelCoords data={radioData} variables={activeVars} />
	{/if}
</div>

<style>
	.chart-root { font-size: 11px; line-height: 1.3; }
	.rc-header {
		display: flex; justify-content: space-between; align-items: center;
		margin-bottom: 2px;
	}
	.rc-title { font-size: 10px; font-weight: 600; color: #e2e8f0; }
	.rc-subtitle {
		font-size: 9px; color: rgba(255,255,255,0.45);
		margin: 0 0 8px;
	}
	.rc-msg {
		font-size: 10px; color: #94a3b8;
		padding: 12px 0; text-align: center;
	}
	.rc-select-row {
		display: flex; align-items: center; gap: 6px;
		margin-bottom: 6px;
	}
	.rc-select-label {
		font-size: 9px; font-weight: 600;
		color: #a3a3a3; text-transform: uppercase;
	}
	.rc-select {
		flex: 1;
		font-size: 10px; padding: 2px 6px; border-radius: 4px;
		background: #1e293b; border: 1px solid #334155;
		color: #e2e8f0; cursor: pointer; font-family: inherit;
	}
	.rc-select option { background: #1e293b; color: #e2e8f0; }
	.rc-select:focus { outline: none; border-color: #64748b; }
</style>
