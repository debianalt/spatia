<script lang="ts">
	import PetalChart from './PetalChart.svelte';
	import PetalComparison from './PetalComparison.svelte';
	import { LENS_CONFIG } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		mapStore,
		lensStore,
		onRemoveRadio
	}: {
		mapStore: MapStore;
		lensStore: LensStore;
		onRemoveRadio: (redcode: string) => void;
	} = $props();

	const lens = $derived(lensStore.activeLens);
	const cfg = $derived(lens ? LENS_CONFIG[lens] : null);

	// Derive entries with map colors from mapStore selection
	const entries = $derived(
		[...mapStore.selectedRadios.entries()].map(([rc, data]) => ({
			redcode: rc,
			color: data.color
		}))
	);
	const redcode = $derived(entries[0]?.redcode ?? '');

	// Primary radio data
	const score = $derived(redcode ? lensStore.getScore(redcode) : 0);
	const subScores = $derived(redcode ? lensStore.getSubScores(redcode) : [0,0,0,0,0,0]);
	const subLabels = $derived(cfg ? cfg.subLabelKeys.map(k => i18n.t(k)) : []);
	const notables = $derived(redcode ? lensStore.getNotables(redcode) : []);
	const risk = $derived(redcode ? lensStore.getRisk(redcode) : '');
	const dpto = $derived(redcode ? lensStore.getDpto(redcode) : '');

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
				<span class="card-badge" style:background="{cfg.color}20" style:border-color="{cfg.color}40">
					{cfg.label[i18n.locale as 'es' | 'en' | 'gn']}
				</span>
				<button class="card-close" onclick={() => onRemoveRadio(redcode)}>×</button>
			</div>
		</div>

		<!-- Score -->
		<div class="card-score">
			{i18n.t('card.score')}: {score.toFixed(0)}/100
		</div>

		{#if entries.length >= 2}
			<!-- Comparison mode: 2+ radios selected -->
			<PetalComparison
				{entries}
				{lensStore}
				{onRemoveRadio}
			/>
		{:else}
			<!-- Single radio: petal chart -->
			<div class="card-section">
				<div class="card-section-title">{i18n.t('card.territory')}</div>
				<PetalChart
					layers={[{values: subScores, color: entries[0]?.color ?? cfg.color}]}
					labels={subLabels}
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
		color: #e2e8f0;
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
		color: #e2e8f0;
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
</style>
