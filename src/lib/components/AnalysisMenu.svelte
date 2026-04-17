<script lang="ts">
	import { getAnalysesForLens, LENS_CONFIG, type AnalysisConfig, type TerritoryConfig } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		lensStore,
		activeTerritory,
		onSelectAnalysis,
	}: {
		lensStore: LensStore;
		activeTerritory?: TerritoryConfig;
		onSelectAnalysis: (analysis: AnalysisConfig) => void;
	} = $props();

	const lens = $derived(lensStore.activeLens);
	const cfg = $derived(lens ? LENS_CONFIG[lens] : null);
	const analyses = $derived(lens ? getAnalysesForLens(lens) : []);

	function getCoverage(analysis: AnalysisConfig): 'available' | 'pending' | 'unavailable' {
		if (!activeTerritory) return 'available';
		if (!analysis.coverage) {
			// No coverage map: available for Misiones (backwards compat), pending for new territories
			return activeTerritory.id === 'misiones' ? 'available' : 'pending';
		}
		return analysis.coverage[activeTerritory.id] ?? (activeTerritory.id === 'misiones' ? 'available' : 'pending');
	}
</script>

{#if cfg && lens}
	<div class="analysis-menu">
		<div class="menu-header">
			<span class="header-label">{cfg.label[i18n.locale as 'es' | 'en' | 'gn']}</span>
		</div>

		<div class="analysis-list">
			{@const comparableGroup = analyses.filter(a => a.comparable && getCoverage(a) !== 'unavailable')}
			{@const localGroup = analyses.filter(a => !a.comparable && getCoverage(a) !== 'unavailable')}

			{#if comparableGroup.length > 0}
				<div class="group-label">↔ Comparables entre territorios</div>
				{#each comparableGroup as analysis}
					{@const coverage = getCoverage(analysis)}
					<button
						class="analysis-item"
						class:available={analysis.status === 'available' && coverage === 'available'}
						class:coming-soon={analysis.status === 'coming_soon' || coverage === 'pending'}
						disabled={analysis.status === 'coming_soon' || coverage === 'pending'}
						onclick={() => onSelectAnalysis(analysis)}
					>
						<div class="item-title">{i18n.t(analysis.titleKey)}</div>
						<div class="item-desc">{i18n.t(analysis.descKey)}</div>
						{#if analysis.status === 'coming_soon'}
							<span class="item-badge">{i18n.t('analysis.status.comingSoon')}</span>
						{:else if coverage === 'pending'}
							<span class="item-badge">⏳ próximamente</span>
						{/if}
					</button>
				{/each}
			{/if}

			{#if localGroup.length > 0}
				<div class="group-label local">
					{activeTerritory?.flag ?? ''} Solo {activeTerritory?.label ?? 'este territorio'}
				</div>
				{#each localGroup as analysis}
					{@const coverage = getCoverage(analysis)}
					<button
						class="analysis-item"
						class:available={analysis.status === 'available' && coverage === 'available'}
						class:coming-soon={analysis.status === 'coming_soon' || coverage === 'pending'}
						disabled={analysis.status === 'coming_soon' || coverage === 'pending'}
						onclick={() => onSelectAnalysis(analysis)}
					>
						<div class="item-title">{i18n.t(analysis.titleKey)}</div>
						<div class="item-desc">{i18n.t(analysis.descKey)}</div>
						{#if analysis.status === 'coming_soon'}
							<span class="item-badge">{i18n.t('analysis.status.comingSoon')}</span>
						{:else if coverage === 'pending'}
							<span class="item-badge">⏳ próximamente</span>
						{/if}
					</button>
				{/each}
			{/if}
		</div>
	</div>
{/if}

<style>
	.analysis-menu {
		font-size: 11px;
	}
	.menu-header {
		margin-bottom: 10px;
		padding-bottom: 6px;
		border-bottom: 1px solid rgba(255,255,255,0.08);
	}
	.header-label {
		font-size: 13px;
		font-weight: 700;
		color: #e2e8f0;
		letter-spacing: 0.02em;
	}
	.analysis-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
		max-height: calc(100vh - 200px);
		overflow-y: auto;
		scrollbar-width: thin;
		scrollbar-color: #334155 transparent;
	}
	.analysis-list::-webkit-scrollbar { width: 4px; }
	.analysis-list::-webkit-scrollbar-track { background: transparent; }
	.analysis-list::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }
	.group-label {
		font-size: 8px;
		font-weight: 700;
		color: rgba(255,255,255,0.30);
		text-transform: uppercase;
		letter-spacing: 0.07em;
		padding: 10px 10px 4px;
		border-top: 1px solid rgba(255,255,255,0.06);
		margin-top: 4px;
	}
	.group-label:first-child {
		border-top: none;
		padding-top: 0;
		margin-top: 0;
	}
	.group-label.local { color: rgba(255,255,255,0.22); }

	.analysis-item {
		display: flex;
		flex-direction: column;
		gap: 3px;
		padding: 10px 10px;
		border-radius: 4px;
		border: none;
		background: transparent;
		cursor: pointer;
		transition: background 0.12s;
		text-align: left;
		width: 100%;
		border-left: 2px solid transparent;
	}
	.analysis-item.available:hover {
		background: rgba(255,255,255,0.05);
		border-left-color: rgba(255,255,255,0.3);
	}
	.analysis-item.coming-soon {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.analysis-item.coming-soon:hover {
		opacity: 0.6;
	}
	.item-title {
		font-size: 11px;
		font-weight: 600;
		color: #ffffff;
		line-height: 1.3;
	}
	.item-desc {
		font-size: 9px;
		color: rgba(255,255,255,0.5);
		line-height: 1.45;
	}
	.item-badge {
		display: inline-block;
		font-size: 8px;
		color: #737373;
		font-style: italic;
		margin-top: 1px;
	}
</style>
