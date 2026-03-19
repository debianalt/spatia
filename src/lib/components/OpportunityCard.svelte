<script lang="ts">
	import PetalChart from './PetalChart.svelte';
	import PetalComparison from './PetalComparison.svelte';
	import { LENS_CONFIG } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let { lensStore }: { lensStore: LensStore } = $props();

	const lens = $derived(lensStore.activeLens);
	const redcode = $derived(lensStore.selectedOpportunity);
	const compRedcode = $derived(lensStore.comparisonRadio);
	const cfg = $derived(lens ? LENS_CONFIG[lens] : null);
	const score = $derived(redcode ? lensStore.getScore(redcode) : 0);
	const subScores = $derived(redcode ? lensStore.getSubScores(redcode) : [0,0,0,0,0,0]);
	const subLabels = $derived(cfg ? cfg.subLabelKeys.map(k => i18n.t(k)) : []);
	const notables = $derived(redcode ? lensStore.getNotables(redcode) : []);
	const risk = $derived(redcode ? lensStore.getRisk(redcode) : '');
	const dpto = $derived(redcode ? lensStore.getDpto(redcode) : '');

	// Comparison data
	const compSubScores = $derived(compRedcode ? lensStore.getSubScores(compRedcode) : null);
	const compScore = $derived(compRedcode ? lensStore.getScore(compRedcode) : 0);
	const compDpto = $derived(compRedcode ? lensStore.getDpto(compRedcode) : '');

	function bestDimension(): string {
		if (!cfg || subScores.length === 0) return '';
		let maxIdx = 0;
		for (let i = 1; i < 6; i++) {
			if (subScores[i] > subScores[maxIdx]) maxIdx = i;
		}
		return i18n.t(cfg.subLabelKeys[maxIdx]);
	}
</script>

{#if lens && redcode && cfg}
	<div class="opp-card">
		<!-- Header -->
		<div class="card-header">
			<div>
				<div class="card-redcode">{redcode}</div>
				<div class="card-dpto">{dpto}</div>
			</div>
			<div class="card-header-right">
				<span class="card-badge" style:background="{cfg.color}20" style:color={cfg.color} style:border-color="{cfg.color}40">
					{cfg.icon} {cfg.label[i18n.locale as 'es' | 'en' | 'gn']}
				</span>
				<button class="card-close" onclick={() => lensStore.clearSelection()}>×</button>
			</div>
		</div>

		<!-- Score -->
		<div class="card-score" style:color={cfg.color}>
			{i18n.t('card.score')}: {score.toFixed(0)}/100
		</div>

		{#if compRedcode && compSubScores}
			<!-- Comparison mode -->
			<PetalComparison
				{lensStore}
				redcodeA={redcode}
				redcodeB={compRedcode}
			/>
		{:else}
			<!-- Single radio: petal chart -->
			<div class="card-section">
				<div class="card-section-title">{i18n.t('card.territory')}</div>
				<PetalChart
					values={subScores}
					labels={subLabels}
					color={cfg.color}
					size={240}
				/>
			</div>

			<!-- Why here -->
			{#if notables.length > 0}
				<div class="card-section">
					<div class="card-section-title">{i18n.t('card.whyHere')}</div>
					{#each notables as note}
						<div class="card-notable">
							<span class="notable-icon">✓</span>
							{note}
						</div>
					{/each}
				</div>
			{/if}

			<!-- Advantage -->
			<div class="card-section">
				<div class="card-section-title">{i18n.t('card.advantage')}</div>
				<p class="card-text">{bestDimension()}: {Math.max(...subScores).toFixed(0)}/100</p>
			</div>

			<!-- Risk -->
			{#if risk}
				<div class="card-section">
					<div class="card-section-title risk-title">
						<span class="risk-icon">⚠</span> {i18n.t('card.risk')}
					</div>
					<p class="card-text risk-text">{risk}</p>
				</div>
			{/if}

			<!-- Actions -->
			<div class="card-actions">
				<button class="card-btn secondary" onclick={() => lensStore.startComparison()}>
					{i18n.t('card.compare')}
				</button>
			</div>
		{/if}

		<!-- Comparison prompt -->
		{#if lensStore.comparisonMode && !compRedcode}
			<div class="comparison-prompt" style:border-color="{cfg.color}40">
				{i18n.t('lens.comparePrompt')}
				<button class="cancel-btn" onclick={() => lensStore.cancelComparison()}>×</button>
			</div>
		{/if}
	</div>
{/if}

<style>
	.opp-card {
		font-size: 11px;
		line-height: 1.4;
	}
	.card-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 6px;
	}
	.card-redcode {
		font-weight: 600;
		color: #e0e0e0;
		font-size: 12px;
	}
	.card-dpto {
		color: #64748b;
		font-size: 10px;
	}
	.card-header-right {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.card-badge {
		display: inline-flex;
		align-items: center;
		gap: 3px;
		padding: 2px 8px;
		border-radius: 9999px;
		border: 1px solid;
		font-size: 10px;
		font-weight: 600;
	}
	.card-close {
		background: none;
		border: none;
		color: #64748b;
		font-size: 16px;
		cursor: pointer;
		padding: 0;
		line-height: 1;
	}
	.card-close:hover { color: #e0e0e0; }
	.card-score {
		font-size: 14px;
		font-weight: 700;
		margin-bottom: 8px;
	}
	.card-section {
		margin-bottom: 8px;
	}
	.card-section-title {
		font-size: 9px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #64748b;
		border-bottom: 1px solid #1e293b;
		padding-bottom: 2px;
		margin-bottom: 4px;
	}
	.card-notable {
		display: flex;
		align-items: flex-start;
		gap: 5px;
		color: #cbd5e1;
		margin-bottom: 2px;
	}
	.notable-icon {
		color: #22c55e;
		font-size: 11px;
		flex-shrink: 0;
		margin-top: 1px;
	}
	.card-text {
		color: #cbd5e1;
		margin: 0;
	}
	.risk-title {
		color: #f59e0b;
	}
	.risk-icon {
		font-size: 11px;
	}
	.risk-text {
		color: #fbbf24;
		font-size: 10px;
	}
	.card-actions {
		display: flex;
		gap: 6px;
		margin-top: 8px;
	}
	.card-btn {
		flex: 1;
		padding: 5px 8px;
		border-radius: 6px;
		font-size: 10px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.15s;
	}
	.card-btn.secondary {
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid #334155;
		color: #94a3b8;
	}
	.card-btn.secondary:hover {
		border-color: #60a5fa;
		color: #60a5fa;
	}
	.comparison-prompt {
		margin-top: 8px;
		padding: 6px 10px;
		border-radius: 6px;
		border: 1px dashed;
		color: #94a3b8;
		font-size: 10px;
		text-align: center;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
	}
	.cancel-btn {
		background: none;
		border: none;
		color: #64748b;
		font-size: 14px;
		cursor: pointer;
		padding: 0;
		line-height: 1;
	}
	.cancel-btn:hover { color: #e0e0e0; }
</style>
