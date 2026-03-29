<script lang="ts">
	import ComparisonChart from './ComparisonChart.svelte';
	import ResponseChart from './ResponseChart.svelte';
	import AnalysisMenu from './AnalysisMenu.svelte';
	import AnalysisView from './AnalysisView.svelte';
	import ZoneComparison from './ZoneComparison.svelte';
	import CatastroZoneComparison from './CatastroZoneComparison.svelte';
	import FloodZoneComparison from './FloodZoneComparison.svelte';
	import HexComparison from './HexComparison.svelte';
	import HexZoneComparison from './HexZoneComparison.svelte';
	import { MapStore } from '$lib/stores/map.svelte';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { LassoStore } from '$lib/stores/lasso.svelte';
	import type { HexStore } from '$lib/stores/hex.svelte';
	import type { AnalysisConfig } from '$lib/config';
	import { i18n } from '$lib/stores/i18n.svelte';
	import CTADiagnostic from './CTADiagnostic.svelte';

	let {
		mapStore,
		lensStore,
		lassoStore,
		hexStore,
		onRemoveRadio,
		onClearRadios,
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
	}: {
		mapStore: MapStore;
		lensStore: LensStore;
		lassoStore: LassoStore;
		hexStore: HexStore;
		onRemoveRadio: (redcode: string) => void;
		onClearRadios: () => void;
		onSelectAnalysis: (analysis: AnalysisConfig) => void;
		onRemoveZone: (id: string) => void;
		onClearZones: () => void;
		onRemoveHexZone: (id: string) => void;
		onClearHexZones: () => void;
		onSelectFloodDpto: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
		onSelectFloodCatastroDpto?: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
		onSelectCatastroDpto?: (centroid: [number, number] | null) => void;
		onSelectScoresCatastroDpto?: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
		onSelectRadioAnalysisDpto?: (dpto: string, analysisId: string, centroid: [number, number]) => void;
	} = $props();

	let collapsed = $state(false);

	// Auto-open when there's content to show
	$effect(() => {
		const hasContent =
			hexStore.hexZones.length > 0 ||
			lassoStore.zones.length > 0 ||
			hexStore.selectedHexes.size > 0 ||
			(lensStore.activeLens && lensStore.activeAnalysis) ||
			(lensStore.activeLens && mapStore.selectedRadios.size > 0) ||
			mapStore.selectedRadios.size > 0 ||
			lensStore.activeLens;
		if (hasContent) collapsed = false;
	});

	const isCatastroAnalysis = $derived(lensStore.activeAnalysis?.id === 'catastro');
	const isFloodRiskAnalysis = $derived(lensStore.activeAnalysis?.id === 'flood_risk');

	function handleBack() {
		lensStore.clearAnalysis();
	}
</script>

{#if !collapsed}
<div class="sidebar absolute top-0 right-0 bottom-0 z-10 rounded-l-lg p-3 px-4 border-l border-border w-[440px] text-xs leading-relaxed"
	style="background: var(--color-panel); backdrop-filter: blur(8px);">

	<button class="collapse-btn" onclick={() => collapsed = true} title="Ocultar panel">
		<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10 4 L18 12 L10 20"/></svg>
	</button>

	{#if hexStore.hexZones.length > 0}
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
		<!-- Analysis active: show analysis view -->
		<div class="chart-scroll">
			<AnalysisView {lensStore} {mapStore} {hexStore} onBack={handleBack} {onRemoveRadio} {onSelectFloodDpto} {onSelectFloodCatastroDpto} {onSelectCatastroDpto} {onSelectScoresCatastroDpto} {onSelectRadioAnalysisDpto} />
		</div>
	{:else if mapStore.selectedRadios.size > 0}
		<!-- No lens, radios selected: comparison chart -->
		<div class="chart-scroll">
			<ComparisonChart radios={mapStore.selectedRadios} {onRemoveRadio} {onClearRadios} />
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
		<div class="chart-scroll welcome-panel">
			<div class="welcome-brand">spatia.ar</div>
			<div class="welcome-subtitle">{i18n.t('header.subtitle')}</div>

			<p class="welcome-desc">{i18n.t('side.welcome.desc')}</p>

			<div class="welcome-divider">{i18n.t('side.welcome.analysesIntro')}</div>

			<div class="welcome-lenses">
				<div class="welcome-lens">
					<span class="lens-name">VIVIR</span>
					<span class="lens-items">Riesgo hídrico · Riesgo ambiental · Confort climático ·...</span>
				</div>
				<div class="welcome-lens">
					<span class="lens-name">INVERTIR</span>
					<span class="lens-items">Perfil territorial · Actividad económica · Presión de cambio ·...</span>
				</div>
				<div class="welcome-lens">
					<span class="lens-name">PRODUCIR</span>
					<span class="lens-items">Potencial agrícola · Salud de la selva · Aptitud silvícola ·...</span>
				</div>
				<div class="welcome-lens">
					<span class="lens-name">SERVIR</span>
					<span class="lens-items">Accesibilidad · Aislamiento · Brecha territorial ·...</span>
				</div>
			</div>

			<div class="welcome-divider">{i18n.t('side.welcome.dataTitle')}</div>

			<div class="welcome-stats">
				<div>— 319.871 hexágonos H3 a 100m de resolución</div>
				<div>— 2.012 radios censales · Censo Nacional 2022</div>
				<div>— 445.000 parcelas catastrales</div>
				<div>— 1.250.000 edificaciones detectadas por IA</div>
				<div>— Series históricas desde 1984 · Monitoreo SAR cada ~12 días</div>
				<div>— Informes PDF por departamento · Diagnósticos por microzona bajo demanda</div>
			</div>

			<div class="welcome-divider">{i18n.t('side.onboarding.title')}</div>

			<div class="welcome-steps">
				<div class="welcome-step"><span class="step-n">1</span> {i18n.t('side.onboarding.step1')}</div>
				<div class="welcome-step"><span class="step-n">2</span> {i18n.t('side.onboarding.step2')}</div>
				<div class="welcome-step"><span class="step-n">3</span> {i18n.t('side.onboarding.step3')}</div>
			</div>

			<div class="welcome-footer">
				<div>Investigación aplicada en inteligencia territorial</div>
				<div>Raimundo Elías Gómez · CONICET</div>
				<div>Google Earth Engine Partner</div>
			</div>

			<CTADiagnostic />
		</div>
	{/if}

</div>
{:else}
	<button class="expand-btn" onclick={() => collapsed = false} title="Mostrar panel">
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
	.welcome-lens { display: flex; flex-direction: column; gap: 2px; }
	.lens-name { font-size: 13px; font-weight: 700; color: rgba(255,255,255,0.95); letter-spacing: 0.04em; }
	.lens-items { font-size: 12px; color: rgba(255,255,255,0.55); line-height: 1.6; font-weight: 300; }
	.welcome-stats { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: rgba(255,255,255,0.65); line-height: 1.6; font-weight: 300; }
	.welcome-steps { display: flex; flex-direction: column; gap: 8px; }
	.welcome-step { font-size: 13px; color: rgba(255,255,255,0.75); line-height: 1.5; font-weight: 300; }
	.step-n { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.7); font-size: 11px; font-weight: 700; margin-right: 6px; }
	.welcome-footer { font-size: 12px; color: rgba(255,255,255,0.45); line-height: 1.6; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 10px; font-weight: 400; }
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
</style>
