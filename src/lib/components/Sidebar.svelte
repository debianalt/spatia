<script lang="ts">
	import Legend from './Legend.svelte';
	import ComparisonChart from './ComparisonChart.svelte';
	import ResponseChart from './ResponseChart.svelte';
	import { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		mapStore,
		onRemoveRadio
	}: {
		mapStore: MapStore;
		onRemoveRadio: (redcode: string) => void;
	} = $props();
</script>

<div class="sidebar absolute top-3 right-3 z-10 rounded-lg p-3 px-4 border border-border max-w-[280px] text-xs leading-relaxed"
	style="background: var(--color-panel); backdrop-filter: blur(8px);">

	{#if mapStore.selectedRadios.size > 0}
		<div class="chart-scroll">
			<ComparisonChart radios={mapStore.selectedRadios} {onRemoveRadio} />
		</div>
	{:else if mapStore.chatCharts.length > 0}
		<div class="chart-scroll">
			{#each mapStore.chatCharts as chart}
				<ResponseChart {chart} />
			{/each}
		</div>
	{:else}
		<p class="text-text-dim text-[10px] mt-1.5">{i18n.t('side.hover')}</p>
	{/if}

	<Legend {mapStore} />
</div>

<style>
	.sidebar {
		max-height: calc(100vh - 80px);
		display: flex;
		flex-direction: column;
	}
	.chart-scroll {
		overflow-y: auto;
		flex: 1;
		min-height: 0;
		scrollbar-width: thin;
		scrollbar-color: #334155 transparent;
	}
	.chart-scroll::-webkit-scrollbar { width: 4px; }
	.chart-scroll::-webkit-scrollbar-track { background: transparent; }
	.chart-scroll::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }
</style>
