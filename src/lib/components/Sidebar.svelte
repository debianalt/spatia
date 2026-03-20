<script lang="ts">
	import Legend from './Legend.svelte';
	import ComparisonChart from './ComparisonChart.svelte';
	import OpportunityCard from './OpportunityCard.svelte';
	import ResponseChart from './ResponseChart.svelte';
	import DepartmentList from './DepartmentList.svelte';
	import AnalysisMenu from './AnalysisMenu.svelte';
	import AnalysisView from './AnalysisView.svelte';
	import ZoneComparison from './ZoneComparison.svelte';
	import { MapStore } from '$lib/stores/map.svelte';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { LassoStore } from '$lib/stores/lasso.svelte';
	import type { AnalysisConfig } from '$lib/config';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		mapStore,
		lensStore,
		lassoStore,
		onRemoveRadio,
		onSelectDpto,
		onSelectRadio,
		onSelectAnalysis,
		onRemoveZone,
		onClearZones,
	}: {
		mapStore: MapStore;
		lensStore: LensStore;
		lassoStore: LassoStore;
		onRemoveRadio: (redcode: string) => void;
		onSelectDpto: (dpto: string) => void;
		onSelectRadio: (redcode: string) => void;
		onSelectAnalysis: (analysis: AnalysisConfig) => void;
		onRemoveZone: (id: string) => void;
		onClearZones: () => void;
	} = $props();

	function handleBack() {
		lensStore.clearAnalysis();
	}
</script>

<div class="sidebar absolute top-3 right-3 z-10 rounded-lg p-3 px-4 border border-border max-w-[420px] text-xs leading-relaxed"
	style="background: var(--color-panel); backdrop-filter: blur(8px);">

	{#if lassoStore.zones.length > 0}
		<div class="chart-scroll">
			<ZoneComparison {lassoStore} {onRemoveZone} {onClearZones} />
		</div>
	{:else if lensStore.activeLens && lensStore.activeAnalysis}
		<!-- Analysis active: show analysis view (with or without radio) -->
		<div class="chart-scroll">
			<AnalysisView {lensStore} {mapStore} onBack={handleBack} {onRemoveRadio} />
		</div>
	{:else if lensStore.activeLens && mapStore.selectedRadios.size > 0}
		<!-- Lens + radio but no analysis: show OpportunityCard (legacy, keeps petal working) -->
		<div class="chart-scroll">
			<OpportunityCard {mapStore} {lensStore} {onRemoveRadio} />
		</div>
	{:else if mapStore.selectedRadios.size > 0}
		<!-- No lens, radios selected: comparison chart -->
		<div class="chart-scroll">
			<ComparisonChart radios={mapStore.selectedRadios} {onRemoveRadio} />
		</div>
	{:else if lensStore.activeLens}
		<!-- Lens active, no analysis, no radio: show analysis menu -->
		<div class="chart-scroll">
			<AnalysisMenu {lensStore} {onSelectAnalysis} />
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

	<Legend {mapStore} {lensStore} />
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
