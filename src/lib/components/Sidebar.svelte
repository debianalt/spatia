<script lang="ts">
	import { fly } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import ComparisonChart from './ComparisonChart.svelte';
	import DistrictComparisonChart from './DistrictComparisonChart.svelte';
	import AnalysisMenu from './AnalysisMenu.svelte';
	import AnalysisView from './AnalysisView.svelte';
	import ZoneComparison from './ZoneComparison.svelte';
	import CatastroZoneComparison from './CatastroZoneComparison.svelte';
	import FloodZoneComparison from './FloodZoneComparison.svelte';
	import HexComparison from './HexComparison.svelte';
	import HexZoneComparison from './HexZoneComparison.svelte';
	import ComparisonPanel from './ComparisonPanel.svelte';
	import { MapStore } from '$lib/stores/map.svelte';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { LassoStore } from '$lib/stores/lasso.svelte';
	import type { HexStore } from '$lib/stores/hex.svelte';
	import type { TerritoryStore } from '$lib/stores/territory.svelte';
	import { LENS_CONFIG, type AnalysisConfig, type LensId } from '$lib/config';
	import { i18n } from '$lib/stores/i18n.svelte';
	import CTADiagnostic from './CTADiagnostic.svelte';
	import MoranPanel from './MoranPanel.svelte';

	let {
		mapStore,
		lensStore,
		lassoStore,
		hexStore,
		territoryStore,
		showAbout = false,
		onRemoveRadio,
		onClearRadios,
		onRemoveDistrict,
		onClearDistricts,
		onSelectAnalysis,
		onRemoveZone,
		onClearZones,
		onRemoveHexZone,
		onClearHexZones,
		onSelectFloodDpto,
		onSelectFloodCatastroDpto,
		onSelectCatastroDpto,
		onSelectScoresCatastroDpto,
		onSelectRadioAnalysisDpto,
		onDownloadRadioCsv,
		onDownloadRadioGeoJson,
		onDownloadRadiosSummary,
		onShowLisa,
		onMoranBrush,
	}: {
		mapStore: MapStore;
		lensStore: LensStore;
		lassoStore: LassoStore;
		hexStore: HexStore;
		territoryStore: TerritoryStore;
		showAbout?: boolean;
		onRemoveRadio: (redcode: string) => void;
		onClearRadios: () => void;
		onRemoveDistrict: (distrito: string) => void;
		onClearDistricts: () => void;
		onSelectAnalysis: (analysis: AnalysisConfig) => void;
		onRemoveZone: (id: string) => void;
		onClearZones: () => void;
		onRemoveHexZone: (id: string) => void;
		onClearHexZones: () => void;
		onSelectFloodDpto: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
		onSelectFloodCatastroDpto?: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
		onSelectCatastroDpto?: (centroid: [number, number] | null, deptCode?: string | null) => void;
		onSelectScoresCatastroDpto?: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
		onSelectRadioAnalysisDpto?: (dpto: string, analysisId: string, centroid: [number, number]) => void;
		onDownloadRadioCsv?: (redcode: string) => void;
		onDownloadRadioGeoJson?: (redcode: string, properties: Record<string, any>) => void;
		onDownloadRadiosSummary?: () => void;
		onShowLisa?: (entries: { h3index: string; value: number; boundary?: number[][] }[]) => void;
		onMoranBrush?: (h3s: string[]) => void;
	} = $props();

	let collapsed = $state(true);

	// Auto-open when actual results exist
	$effect(() => {
		const hasContent =
			showAbout ||
			hexStore.hexZones.length > 0 ||
			lassoStore.zones.length > 0 ||
			hexStore.selectedHexes.size > 0 ||
			(lensStore.activeLens && lensStore.activeAnalysis) ||
			mapStore.selectedRadios.size > 0 ||
			mapStore.selectedDistricts.size > 0;
		if (hasContent) collapsed = false;
	});

	// Open when user switches lens — but don't fight with handleBack's explicit close.
	// prevLens is a plain variable (not $state) so assigning it never re-triggers the effect.
	let prevLens: LensId | null = null;
	$effect(() => {
		const lens = lensStore.activeLens;
		if (lens !== null && lens !== prevLens) collapsed = false;
		prevLens = lens;
	});

	const isCatastroAnalysis = $derived(lensStore.activeAnalysis?.id === 'catastro');
	const isFloodRiskAnalysis = $derived(lensStore.activeAnalysis?.id === 'flood_risk');

	function handleBack() {
		lensStore.clearAnalysis();
		collapsed = true;
	}
</script>

{#if !collapsed}
<div class="sidebar absolute top-0 right-0 bottom-0 z-10 rounded-l-lg p-3 px-4 border-l border-border w-full md:w-[500px] text-xs leading-relaxed"
	style="background: var(--color-panel); backdrop-filter: blur(8px);"
	transition:fly={{ x: 500, duration: 180, easing: cubicOut }}>

	<button class="collapse-btn" onclick={() => collapsed = true} title={i18n.t('side.welcome.hidePanel')}>
		<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10 4 L18 12 L10 20"/></svg>
	</button>

	{#if showAbout}
		<!-- Welcome panel (triggered by header button) -->
		<div class="chart-scroll welcome-panel">
			<div class="welcome-brand">nealab</div>
			<div class="welcome-subtitle">{i18n.t('header.subtitle')}</div>

			<p class="welcome-desc">{i18n.t('side.welcome.desc')}</p>

			<div class="welcome-divider">{i18n.t('side.onboarding.title')}</div>

			<div class="welcome-steps">
				<div class="welcome-step"><span class="step-n">1</span> {i18n.t('side.onboarding.step1')}</div>
				<div class="welcome-step"><span class="step-n">2</span> {i18n.t('side.onboarding.step2')}</div>
				<div class="welcome-step"><span class="step-n">3</span> {i18n.t('side.onboarding.step3')}</div>
			</div>

			<div class="welcome-footer">
				<div>{i18n.t('side.welcome.footer.research')}</div>
				<div>{i18n.t('side.welcome.footer.author')}</div>
				<div>{i18n.t('side.welcome.footer.affiliation')}</div>
				<div>{i18n.t('side.welcome.footer.partner')}</div>
				<div class="welcome-links">
					<a href="/servicios" class="welcome-link">Ver servicios →</a>
					<span class="welcome-link-sep">·</span>
					<a href="/metodologia" class="welcome-link">Metodología e indicadores →</a>
					<span class="welcome-link-sep">·</span>
					<a href="/terminos" class="welcome-link">Términos →</a>
				</div>
			</div>

			<CTADiagnostic />
		</div>
	{:else if hexStore.hexZones.length > 0}
		<div class="chart-scroll">
			<HexZoneComparison {hexStore} {onRemoveHexZone} {onClearHexZones} />
		</div>
	{:else if lassoStore.zones.length > 0}
		<div class="chart-scroll">
			{#if isFloodRiskAnalysis}
				<FloodZoneComparison {lassoStore} {mapStore} {onRemoveZone} {onClearZones} />
			{:else if isCatastroAnalysis}
				<CatastroZoneComparison {lassoStore} {lensStore} {onRemoveZone} {onClearZones} />
			{:else}
				<ZoneComparison {lassoStore} {onRemoveZone} {onClearZones} />
			{/if}
		</div>
	{:else if hexStore.selectedHexes.size > 0}
		<div class="chart-scroll">
			<HexComparison {hexStore} />
		</div>
	{:else if lensStore.activeLens && lensStore.activeAnalysis}
		<!-- Compare selector always visible; when active it fills the panel and replaces AnalysisView -->
		<ComparisonPanel {territoryStore} {lensStore} {hexStore} />
		{#if !territoryStore.compareModeActive}
			<div class="chart-scroll">
				<AnalysisView {lensStore} {mapStore} {hexStore} onBack={handleBack} {onRemoveRadio} {onSelectFloodDpto} {onSelectFloodCatastroDpto} {onSelectCatastroDpto} {onSelectScoresCatastroDpto} {onSelectRadioAnalysisDpto} />
				{#if hexStore.visibleData.size > 0 && hexStore.activeLayer?.primaryVariable}
					<MoranPanel
						data={hexStore.visibleData}
						variable={hexStore.activeLayer.primaryVariable}
						boundaryCache={hexStore.boundaryCache}
						onShowLisa={onShowLisa ?? (() => {})}
						onBrushSelect={onMoranBrush ?? (() => {})}
					/>
				{/if}
			</div>
		{/if}
	{:else if mapStore.selectedDistricts.size > 0}
		<!-- Itapúa: districts selected -->
		<div class="chart-scroll">
			<DistrictComparisonChart
				districts={mapStore.selectedDistricts}
				{onRemoveDistrict}
				{onClearDistricts}
			/>
		</div>
	{:else if mapStore.selectedRadios.size > 0}
		<!-- No lens, radios selected: comparison chart -->
		<div class="chart-scroll">
			<ComparisonChart
				radios={mapStore.selectedRadios}
				{onRemoveRadio}
				{onClearRadios}
				{onDownloadRadioCsv}
				{onDownloadRadioGeoJson}
				{onDownloadRadiosSummary}
			/>
		</div>
	{:else if lensStore.activeLens}
		<!-- Lens active, no analysis, no radio: show analysis menu -->
		<div class="chart-scroll">
			<AnalysisMenu {lensStore} activeTerritory={territoryStore.activeTerritory} {onSelectAnalysis} />
		</div>
	{/if}

</div>
{:else}
	<button class="expand-btn" onclick={() => collapsed = false} title={i18n.t('side.welcome.showPanel')}>
		<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 4 L6 12 L14 20"/></svg>
	</button>
{/if}

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
	.faq-item {
		border: 1px solid rgba(255,255,255,0.08);
		border-radius: 6px;
		overflow: hidden;
	}
	.faq-q {
		font-size: 10px;
		font-weight: 600;
		color: #ffffff;
		padding: 6px 8px;
		cursor: pointer;
		user-select: none;
		list-style: none;
		display: flex;
		align-items: center;
		gap: 4px;
	}
	.faq-q::before { content: '\25B8'; font-size: 8px; transition: transform 0.15s; }
	.faq-item[open] > .faq-q::before { transform: rotate(90deg); }
	.faq-q::-webkit-details-marker { display: none; }
	.faq-a {
		padding: 2px 8px 8px;
	}
	.faq-a p {
		font-size: 10px;
		color: rgba(255,255,255,0.8);
		margin: 0;
		line-height: 1.5;
	}
	.collapse-btn {
		position: absolute;
		top: 8px;
		left: -14px;
		width: 28px;
		height: 28px;
		border: 1px solid rgba(255,255,255,0.1);
		background: rgba(15, 23, 42, 0.9);
		border-radius: 6px;
		color: #a3a3a3;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
		z-index: 11;
	}
	.collapse-btn:hover { color: #e2e8f0; border-color: #60a5fa; }
	.welcome-panel { padding-top: 4px; display: flex; flex-direction: column; gap: 16px; }
	.welcome-brand { font-size: 28px; font-weight: 700; color: #ffffff; letter-spacing: 0.02em; }
	.welcome-subtitle { font-size: 14px; color: rgba(255,255,255,0.7); margin-top: -10px; font-weight: 300; }
	.welcome-desc { font-size: 13px; color: rgba(255,255,255,0.8); line-height: 1.7; font-weight: 300; }
	.welcome-divider { font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.5); letter-spacing: 0.06em; text-transform: uppercase; border-top: 1px solid rgba(255,255,255,0.12); padding-top: 10px; }
	.welcome-lenses { display: flex; flex-direction: column; gap: 8px; }
	.welcome-lens { display: flex; flex-direction: column; gap: 2px; padding-left: 10px; border-left: 2px solid rgba(255,255,255,0.1); }
	.lens-name { font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
	.lens-items { font-size: 12px; color: rgba(255,255,255,0.55); line-height: 1.6; font-weight: 300; }
	.welcome-stats { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: rgba(255,255,255,0.65); line-height: 1.6; font-weight: 300; }
	.welcome-steps { display: flex; flex-direction: column; gap: 8px; }
	.welcome-step { font-size: 13px; color: rgba(255,255,255,0.75); line-height: 1.5; font-weight: 300; }
	.step-n { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.7); font-size: 11px; font-weight: 700; margin-right: 6px; }
	.welcome-footer { font-size: 12px; color: rgba(255,255,255,0.45); line-height: 1.6; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 10px; font-weight: 400; }
	.welcome-links { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 6px; margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1); }
	.welcome-link { color: rgba(255,255,255,0.55); font-size: 10px; text-decoration: none; letter-spacing: 0.02em; transition: color 0.15s; }
	.welcome-link:hover { color: #ffffff; }
	.welcome-link-sep { color: rgba(255,255,255,0.2); font-size: 10px; }
	.dashboard-link { display: block; font-size: 12px; color: rgba(255,255,255,0.55); line-height: 1.6; text-decoration: none; font-weight: 300; }
	.dashboard-link:hover { color: rgba(255,255,255,0.8); }
	.expand-btn {
		position: absolute;
		top: 12px;
		right: 12px;
		z-index: 10;
		width: 36px;
		height: 36px;
		border: 1px solid rgba(255,255,255,0.12);
		background: rgba(15, 23, 42, 0.85);
		backdrop-filter: blur(8px);
		border-radius: 8px;
		color: #d4d4d4;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
	}
	.expand-btn:hover { color: #e2e8f0; border-color: #60a5fa; background: rgba(59,130,246,0.1); }

	@media (max-width: 768px) {
		.sidebar {
			width: 100% !important;
			border-radius: 0;
			border-left: none;
			max-height: 60vh;
			bottom: auto;
		}
	}
</style>
