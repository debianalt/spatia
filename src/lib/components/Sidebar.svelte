<script lang="ts">
	import Legend from './Legend.svelte';
	import ComparisonChart from './ComparisonChart.svelte';
	import OpportunityCard from './OpportunityCard.svelte';
	import ResponseChart from './ResponseChart.svelte';
	import DepartmentList from './DepartmentList.svelte';
	import AnalysisMenu from './AnalysisMenu.svelte';
	import AnalysisView from './AnalysisView.svelte';
	import ZoneComparison from './ZoneComparison.svelte';
	import HexComparison from './HexComparison.svelte';
	import HexZoneComparison from './HexZoneComparison.svelte';
	import { MapStore } from '$lib/stores/map.svelte';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { LassoStore } from '$lib/stores/lasso.svelte';
	import type { HexStore } from '$lib/stores/hex.svelte';
	import type { AnalysisConfig } from '$lib/config';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		mapStore,
		lensStore,
		lassoStore,
		hexStore,
		onRemoveRadio,
		onSelectDpto,
		onSelectRadio,
		onSelectAnalysis,
		onRemoveZone,
		onClearZones,
		onRemoveHexZone,
		onClearHexZones,
	}: {
		mapStore: MapStore;
		lensStore: LensStore;
		lassoStore: LassoStore;
		hexStore: HexStore;
		onRemoveRadio: (redcode: string) => void;
		onSelectDpto: (dpto: string) => void;
		onSelectRadio: (redcode: string) => void;
		onSelectAnalysis: (analysis: AnalysisConfig) => void;
		onRemoveZone: (id: string) => void;
		onClearZones: () => void;
		onRemoveHexZone: (id: string) => void;
		onClearHexZones: () => void;
	} = $props();

	function handleBack() {
		lensStore.clearAnalysis();
	}
</script>

<div class="sidebar absolute top-0 right-0 bottom-0 z-10 rounded-l-lg p-3 px-4 border-l border-border w-[440px] text-xs leading-relaxed"
	style="background: var(--color-panel); backdrop-filter: blur(8px);">

	{#if hexStore.hexZones.length > 0}
		<div class="chart-scroll">
			<HexZoneComparison {hexStore} {onRemoveHexZone} {onClearHexZones} />
		</div>
	{:else if lassoStore.zones.length > 0}
		<div class="chart-scroll">
			<ZoneComparison {lassoStore} {onRemoveZone} {onClearZones} />
		</div>
	{:else if hexStore.selectedHexes.size > 0}
		<div class="chart-scroll">
			<HexComparison {hexStore} />
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
		<!-- Welcome panel -->
		<div class="chart-scroll flex flex-col gap-4 pt-1">
			<!-- Bloque 1: Branding -->
			<div class="flex flex-col gap-1">
				<span class="text-lg font-bold text-accent">Spatia</span>
				<span class="text-text-muted italic text-[11px]">{i18n.t('header.subtitle')}</span>
				<span class="self-start mt-1 border border-accent text-accent text-[10px] px-2 py-0.5 rounded-full">{i18n.t('side.welcome.status')}</span>
			</div>

			<!-- Bloque 2: Pitch -->
			<p class="text-text-muted text-[11px] leading-relaxed">
				{i18n.t('side.welcome.desc')}
			</p>

			<!-- Bloque 3: Spatia Pro -->
			<div class="flex flex-col gap-2">
				<span class="text-sm font-semibold text-text">{i18n.t('side.welcome.pro')}</span>
				<ul class="flex flex-col gap-1.5 text-[11px] text-text-muted">
					<li class="flex items-start gap-1.5">
						<span class="text-accent mt-px">✓</span>
						<span>{i18n.t('side.welcome.pro.ia')}</span>
					</li>
					<li class="flex items-start gap-1.5">
						<span class="text-accent mt-px">✓</span>
						<span>{i18n.t('side.welcome.pro.pdf')}</span>
					</li>
					<li class="flex items-start gap-1.5">
						<span class="text-accent mt-px">✓</span>
						<span>{i18n.t('side.welcome.pro.method')}</span>
					</li>
					<li class="flex items-start gap-1.5">
						<span class="text-accent mt-px">✓</span>
						<span>{i18n.t('side.welcome.pro.multi')}</span>
					</li>
					<li class="flex items-start gap-1.5">
						<span class="text-accent mt-px">✓</span>
						<span>{i18n.t('side.welcome.pro.support')}</span>
					</li>
				</ul>
				<a href="mailto:spatia@conicet.gov.ar"
					class="self-start mt-1 bg-accent text-white text-[11px] font-medium px-4 py-1.5 rounded-md hover:opacity-90 transition-opacity">
					{i18n.t('side.welcome.pro.cta')}
				</a>
			</div>

			<!-- Bloque 4: Instituciones -->
			<div class="flex flex-col gap-1 border-t border-border/30 pt-3">
				<span class="text-text-dim text-[10px]">{i18n.t('side.welcome.backed')}:</span>
				<span class="text-text-dim text-[10px]">CONICET · UNAM · INREFRO</span>
			</div>

			<!-- Bloque 5: Hint -->
			<p class="text-text-dim text-[10px] mt-auto">{i18n.t('side.hover')}</p>
		</div>
	{/if}

	<Legend {mapStore} {lensStore} />
</div>

<style>
	.sidebar {
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
