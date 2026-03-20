<script lang="ts">
	import PetalChart from '../PetalChart.svelte';
	import PetalComparison from '../PetalComparison.svelte';
	import { LENS_CONFIG } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		lensStore,
		mapStore,
		onRemoveRadio,
	}: {
		lensStore: LensStore;
		mapStore: MapStore;
		onRemoveRadio: (redcode: string) => void;
	} = $props();

	const lens = $derived(lensStore.activeLens);
	const cfg = $derived(lens ? LENS_CONFIG[lens] : null);

	const entries = $derived(
		[...mapStore.selectedRadios.entries()].map(([rc, data]) => ({
			redcode: rc,
			color: data.color
		}))
	);
	const redcode = $derived(entries[0]?.redcode ?? '');

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

{#if !cfg}
	<!-- no lens -->
{:else if entries.length === 0}
	<p class="hint">{i18n.t('lens.selectRadio')}</p>
{:else if entries.length >= 2}
	<PetalComparison {entries} {lensStore} {onRemoveRadio} />
{:else if redcode}
	<div class="profile">
		<div class="profile-header">
			<div>
				<div class="profile-redcode">{redcode}</div>
				<div class="profile-dpto">{dpto}</div>
			</div>
			<button class="profile-close" onclick={() => onRemoveRadio(redcode)}>x</button>
		</div>

		<div class="profile-score">
			Score: {score.toFixed(0)} — Top {Math.max(1, Math.round(100 - score))}%
		</div>

		<div class="section">
			<div class="section-title">{i18n.t('card.territory')}</div>
			<PetalChart
				layers={[{values: subScores, color: entries[0]?.color ?? cfg.color}]}
				labels={subLabels}
				size={240}
			/>
		</div>

		{#if notables.length > 0}
			<div class="section">
				<div class="section-title">{i18n.t('card.whyHere')}</div>
				{#each notables as note}
					<div class="notable">
						<span class="notable-check">+</span>
						{note}
					</div>
				{/each}
			</div>
		{/if}

		<div class="section">
			<div class="section-title">{i18n.t('card.advantage')}</div>
			<p class="card-text">{bestDimension()}: {Math.max(...subScores).toFixed(0)}/100</p>
		</div>

		{#if risk}
			<div class="section">
				<div class="section-title risk-title">{i18n.t('card.risk')}</div>
				<p class="card-text risk-text">{risk}</p>
			</div>
		{/if}
	</div>
{/if}

<style>
	.hint {
		color: #64748b;
		font-size: 10px;
		margin: 8px 0;
	}
	.profile {
		font-size: 11px;
		line-height: 1.4;
	}
	.profile-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 6px;
	}
	.profile-redcode {
		font-weight: 600;
		color: #e0e0e0;
		font-size: 12px;
	}
	.profile-dpto {
		color: #64748b;
		font-size: 10px;
	}
	.profile-close {
		background: none;
		border: none;
		color: #64748b;
		font-size: 14px;
		cursor: pointer;
		padding: 0;
		line-height: 1;
	}
	.profile-close:hover { color: #e0e0e0; }
	.profile-score {
		font-size: 14px;
		font-weight: 700;
		color: #e2e8f0;
		margin-bottom: 8px;
	}
	.section {
		margin-bottom: 8px;
	}
	.section-title {
		font-size: 9px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #64748b;
		border-bottom: 1px solid #1e293b;
		padding-bottom: 2px;
		margin-bottom: 4px;
	}
	.notable {
		display: flex;
		align-items: flex-start;
		gap: 5px;
		color: #cbd5e1;
		margin-bottom: 2px;
	}
	.notable-check {
		color: #22c55e;
		font-size: 11px;
		font-weight: 700;
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
	.risk-text {
		color: #fbbf24;
		font-size: 10px;
	}
</style>
