<script lang="ts">
	import { PETAL_VARS, loadRadioPopulation } from '$lib/utils/petal';
	import { i18n } from '$lib/stores/i18n.svelte';
	import HistogramPanel from './HistogramPanel.svelte';
	import ParallelCoords from './ParallelCoords.svelte';

	let radioData = $state<Map<string, Record<string, any>> | null>(null);
	let loadError = $state(false);
	let selectedVar = $state(PETAL_VARS[0].col);

	// Plain var (NOT $state): a $state guard read+written inside the effect
	// would re-trigger it. Mirrors `prevLens` in Sidebar.svelte.
	let loadStarted = false;

	$effect(() => {
		if (loadStarted) return;
		loadStarted = true;
		loadRadioPopulation()
			.then((m) => { radioData = m; })
			.catch(() => { loadError = true; });
	});
</script>

<div class="chart-root">
	<div class="rc-header">
		<span class="rc-title">{i18n.t('side.radioCensus.title')}</span>
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
				{#each PETAL_VARS as v}
					<option value={v.col}>{i18n.t(v.labelKey)}</option>
				{/each}
			</select>
		</label>

		<HistogramPanel data={radioData} variable={selectedVar} xLabel="%" />
		<ParallelCoords data={radioData} variables={PETAL_VARS} />
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
		background: rgba(255,255,255,0.06); border: 1px solid #334155;
		color: #e2e8f0; cursor: pointer; font-family: inherit;
	}
	.rc-select:focus { outline: none; border-color: #64748b; }
</style>
