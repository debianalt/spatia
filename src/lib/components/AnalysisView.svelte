<script lang="ts">
	import { LENS_CONFIG, HEX_LAYER_REGISTRY, RADIO_ANALYSIS_REGISTRY, type AnalysisConfig } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import RealEstateAnalysis from './analyses/RealEstateAnalysis.svelte';
	import FloodRiskAnalysis from './analyses/FloodRiskAnalysis.svelte';
	import CatastroAnalysis from './analyses/CatastroAnalysis.svelte';
	import OvertureAnalysis from './analyses/OvertureAnalysis.svelte';
	import TerritorialScoresAnalysis from './analyses/TerritorialScoresAnalysis.svelte';
	import RadioAnalysis from './analyses/RadioAnalysis.svelte';

	let {
		lensStore,
		mapStore,
		hexStore,
		onBack,
		onRemoveRadio,
		onSelectFloodDpto,
		onSelectFloodCatastroDpto,
		onSelectCatastroDpto,
		onSelectScoresCatastroDpto,
		onSelectRadioAnalysisDpto,
	}: {

		lensStore: LensStore;
		mapStore: MapStore;
		hexStore: HexStore;
		onBack: () => void;
		onRemoveRadio: (redcode: string) => void;
		onSelectFloodDpto: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
		onSelectFloodCatastroDpto?: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
		onSelectCatastroDpto?: (centroid: [number, number] | null) => void;
		onSelectScoresCatastroDpto?: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
		onSelectRadioAnalysisDpto?: (dpto: string, analysisId: string, centroid: [number, number]) => void;
	} = $props();

	const analysis = $derived(lensStore.activeAnalysis);
	const lens = $derived(lensStore.activeLens);
	const cfg = $derived(lens ? LENS_CONFIG[lens] : null);

</script>

{#if analysis && cfg}
	<div class="analysis-view">
		<div class="view-header">
			<span class="view-icon">{analysis.icon}</span>
			<div class="view-title-group">
				<div class="view-title">{i18n.t(analysis.titleKey)}</div>
				<div class="view-lens" style:color={cfg.color}>
					{cfg.label[i18n.locale as 'es' | 'en' | 'gn']}
				</div>
			</div>
		</div>

		{#if analysis.status === 'coming_soon'}
			<div class="coming-soon-card">
				<div class="coming-soon-badge">{i18n.t('analysis.status.comingSoon')}</div>
				<p class="coming-soon-text">{i18n.t(analysis.descKey)}</p>
				<p class="coming-soon-body">{i18n.t('analysis.comingSoon.body')}</p>
			</div>
		{:else if analysis.id === 'real_estate'}
			<RealEstateAnalysis {lensStore} {mapStore} {onRemoveRadio} />
		{:else if analysis.id === 'flood_risk'}
			<FloodRiskAnalysis {lensStore} {mapStore} {hexStore} {onRemoveRadio} {onSelectFloodDpto} {onSelectFloodCatastroDpto} />
		{:else if analysis.id === 'catastro'}
			<CatastroAnalysis {lensStore} {mapStore} {onRemoveRadio} {onSelectCatastroDpto} />
		{:else if analysis.id === 'territorial_scores'}
			<TerritorialScoresAnalysis {lensStore} {mapStore} {hexStore} {onSelectScoresCatastroDpto} />
		{:else if RADIO_ANALYSIS_REGISTRY[analysis.id]}
			<RadioAnalysis config={RADIO_ANALYSIS_REGISTRY[analysis.id]} {mapStore} {hexStore} onSelectRadioAnalysisDpto={onSelectRadioAnalysisDpto} />
		{:else if HEX_LAYER_REGISTRY[analysis.id]}
			<OvertureAnalysis {analysis} {hexStore} />
		{:else}
			<p class="text-text-dim text-[10px]">{i18n.t(analysis.descKey)}</p>
		{/if}
	</div>
{/if}

<style>
	.analysis-view {
		font-size: 11px;
	}
	.back-btn {
		font-size: 10px;
		color: #d4d4d4;
		background: none;
		border: none;
		cursor: pointer;
		padding: 2px 0;
		text-align: left;
		transition: color 0.15s;
		margin-bottom: 6px;
	}
	.back-btn:hover { color: #e2e8f0; }
	.view-header {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 10px;
	}
	.view-icon {
		font-size: 20px;
		line-height: 1;
	}
	.view-title-group {
		flex: 1;
	}
	.view-title {
		font-size: 12px;
		font-weight: 600;
		color: #e2e8f0;
	}
	.view-lens {
		font-size: 9px;
		font-weight: 500;
	}
	.coming-soon-card {
		background: rgba(100,116,139,0.1);
		border: 1px solid rgba(100,116,139,0.2);
		border-radius: 8px;
		padding: 12px;
	}
	.coming-soon-badge {
		display: inline-block;
		font-size: 9px;
		font-weight: 600;
		color: #d4d4d4;
		background: rgba(100,116,139,0.2);
		padding: 2px 8px;
		border-radius: 9999px;
		margin-bottom: 8px;
	}
	.coming-soon-text {
		font-size: 10px;
		color: #cbd5e1;
		margin: 0 0 6px 0;
	}
	.coming-soon-body {
		font-size: 9px;
		color: #a3a3a3;
		margin: 0;
		line-height: 1.4;
	}
</style>
