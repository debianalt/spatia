<script lang="ts">
	import { getAnalysesForLens, LENS_CONFIG, type AnalysisConfig } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		lensStore,
		onSelectAnalysis,
	}: {
		lensStore: LensStore;
		onSelectAnalysis: (analysis: AnalysisConfig) => void;
	} = $props();

	const lens = $derived(lensStore.activeLens);
	const cfg = $derived(lens ? LENS_CONFIG[lens] : null);
	const analyses = $derived(lens ? getAnalysesForLens(lens) : []);
</script>

{#if cfg && lens}
	<div class="analysis-menu">
		<div class="menu-header">
			<span class="header-label">{cfg.label[i18n.locale as 'es' | 'en' | 'gn']}</span>
			<span class="header-sub">{i18n.t('analysis.menu.title')}</span>
		</div>

		<div class="analysis-grid">
			{#each analyses as analysis}
				<button
					class="analysis-card"
					class:available={analysis.status === 'available'}
					class:coming-soon={analysis.status === 'coming_soon'}
					onclick={() => onSelectAnalysis(analysis)}
				>
					<div class="card-icon">{analysis.icon}</div>
					<div class="card-body">
						<div class="card-title">{i18n.t(analysis.titleKey)}</div>
						<div class="card-desc">{i18n.t(analysis.descKey)}</div>
					</div>
					<span
						class="card-badge"
						style:background={analysis.status === 'available' ? `${cfg.color}25` : 'rgba(100,116,139,0.2)'}
						style:color={analysis.status === 'available' ? cfg.color : '#a3a3a3'}
						style:border-color={analysis.status === 'available' ? `${cfg.color}40` : 'rgba(100,116,139,0.3)'}
					>
						{i18n.t(analysis.status === 'available' ? 'analysis.status.available' : 'analysis.status.comingSoon')}
					</span>
				</button>
			{/each}
		</div>
	</div>
{/if}

<style>
	.analysis-menu {
		font-size: 11px;
	}
	.menu-header {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 10px;
	}
	.header-label {
		font-size: 12px;
		font-weight: 600;
		color: #e2e8f0;
	}
	.header-sub {
		font-size: 10px;
		color: #a3a3a3;
		margin-left: auto;
	}
	.analysis-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
		max-height: calc(100vh - 200px);
		overflow-y: auto;
		scrollbar-width: thin;
		scrollbar-color: #334155 transparent;
	}
	.analysis-grid::-webkit-scrollbar { width: 4px; }
	.analysis-grid::-webkit-scrollbar-track { background: transparent; }
	.analysis-grid::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }
	.analysis-card {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 8px;
		border-radius: 8px;
		border: 1px solid rgba(255,255,255,0.06);
		background: rgba(255,255,255,0.03);
		cursor: pointer;
		transition: all 0.15s;
		text-align: left;
		width: 100%;
	}
	.analysis-card.available:hover {
		background: rgba(255,255,255,0.08);
		border-color: rgba(255,255,255,0.12);
	}
	.analysis-card.coming-soon {
		opacity: 0.6;
	}
	.analysis-card.coming-soon:hover {
		opacity: 0.75;
		background: rgba(255,255,255,0.05);
	}
	.card-icon {
		font-size: 18px;
		line-height: 1;
	}
	.card-body {
		flex: 1;
		min-width: 0;
	}
	.card-title {
		font-size: 10px;
		font-weight: 600;
		color: #e2e8f0;
		line-height: 1.3;
	}
	.card-desc {
		font-size: 9px;
		color: #a3a3a3;
		line-height: 1.3;
		margin-top: 2px;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.card-badge {
		display: inline-block;
		font-size: 8px;
		font-weight: 600;
		padding: 1px 6px;
		border-radius: 9999px;
		border: 1px solid;
		align-self: flex-start;
		white-space: nowrap;
	}
</style>
