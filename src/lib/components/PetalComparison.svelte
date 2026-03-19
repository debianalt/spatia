<script lang="ts">
	import PetalChart from './PetalChart.svelte';
	import { LENS_CONFIG } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		lensStore,
		redcodeA,
		redcodeB
	}: {
		lensStore: LensStore;
		redcodeA: string;
		redcodeB: string;
	} = $props();

	const lens = $derived(lensStore.activeLens);
	const cfg = $derived(lens ? LENS_CONFIG[lens] : null);
	const scoresA = $derived(lensStore.getSubScores(redcodeA));
	const scoresB = $derived(lensStore.getSubScores(redcodeB));
	const subLabels = $derived(cfg ? cfg.subLabelKeys.map(k => i18n.t(k)) : []);
	const dptoA = $derived(lensStore.getDpto(redcodeA));
	const dptoB = $derived(lensStore.getDpto(redcodeB));
	const totalA = $derived(lensStore.getScore(redcodeA));
	const totalB = $derived(lensStore.getScore(redcodeB));

	const OVERLAY_COLOR = '#a78bfa';

	// Find biggest delta dimension
	const biggestDelta = $derived.by(() => {
		if (!cfg) return { label: '', delta: 0, idx: 0 };
		let maxDelta = 0;
		let maxIdx = 0;
		for (let i = 0; i < 6; i++) {
			const d = Math.abs(scoresA[i] - scoresB[i]);
			if (d > maxDelta) { maxDelta = d; maxIdx = i; }
		}
		return {
			label: subLabels[maxIdx] ?? '',
			delta: scoresA[maxIdx] - scoresB[maxIdx],
			idx: maxIdx
		};
	});

	function shortCode(rc: string): string {
		return rc.length > 5 ? '...' + rc.slice(-4) : rc;
	}
</script>

{#if cfg}
	<div class="comparison">
		<!-- Identifiers -->
		<div class="comp-ids">
			<span class="comp-id" style:color={cfg.color}>
				<span class="comp-dot" style:background={cfg.color}></span>
				{shortCode(redcodeA)} <span class="comp-dpto">({dptoA})</span>
			</span>
			<span class="comp-vs">vs</span>
			<span class="comp-id" style:color={OVERLAY_COLOR}>
				<span class="comp-dot" style:background={OVERLAY_COLOR}></span>
				{shortCode(redcodeB)} <span class="comp-dpto">({dptoB})</span>
			</span>
		</div>

		<!-- Overlay petal chart -->
		<PetalChart
			values={scoresA}
			labels={subLabels}
			color={cfg.color}
			overlayValues={scoresB}
			overlayColor={OVERLAY_COLOR}
			size={240}
		/>

		<!-- Score comparison -->
		<div class="comp-scores">
			<span style:color={cfg.color}>{totalA.toFixed(0)}</span>
			<span class="comp-vs-score">vs</span>
			<span style:color={OVERLAY_COLOR}>{totalB.toFixed(0)}</span>
		</div>

		<!-- Delta bars -->
		<div class="delta-section">
			{#each subLabels as label, i}
				{@const delta = scoresA[i] - scoresB[i]}
				{@const pct = Math.abs(delta) / 100 * 100}
				<div class="delta-row">
					<div class="delta-label">{label}</div>
					<div class="delta-bar-container">
						{#if delta >= 0}
							<div class="delta-bar-bg">
								<div class="delta-bar positive" style:width="{pct}%" style:background={cfg.color}></div>
							</div>
						{:else}
							<div class="delta-bar-bg">
								<div class="delta-bar negative" style:width="{pct}%" style:background={OVERLAY_COLOR}></div>
							</div>
						{/if}
					</div>
					<div class="delta-value" style:color={delta >= 0 ? cfg.color : OVERLAY_COLOR}>
						{delta > 0 ? '+' : ''}{delta.toFixed(0)}
					</div>
				</div>
			{/each}
		</div>

		<!-- Most notable difference -->
		<div class="notable-diff">
			<div class="diff-title">{i18n.t('card.difference')}</div>
			<div class="diff-text">
				<strong>{biggestDelta.label}</strong>:
				{#if biggestDelta.delta > 0}
					{shortCode(redcodeA)} supera en {Math.abs(biggestDelta.delta).toFixed(0)} pts
				{:else}
					{shortCode(redcodeB)} supera en {Math.abs(biggestDelta.delta).toFixed(0)} pts
				{/if}
			</div>
		</div>

		<!-- Back button -->
		<button class="back-btn" onclick={() => lensStore.cancelComparison()}>
			← Volver a ficha
		</button>
	</div>
{/if}

<style>
	.comparison {
		font-size: 11px;
	}
	.comp-ids {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		margin-bottom: 6px;
	}
	.comp-id {
		display: flex;
		align-items: center;
		gap: 4px;
		font-size: 10px;
		font-weight: 600;
	}
	.comp-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.comp-dpto {
		font-weight: 400;
		opacity: 0.6;
		font-size: 9px;
	}
	.comp-vs {
		color: #475569;
		font-size: 9px;
	}
	.comp-scores {
		display: flex;
		justify-content: center;
		align-items: center;
		gap: 10px;
		font-size: 18px;
		font-weight: 700;
		margin: 4px 0 8px;
	}
	.comp-vs-score {
		color: #475569;
		font-size: 11px;
		font-weight: 400;
	}
	.delta-section {
		margin: 6px 0;
	}
	.delta-row {
		display: flex;
		align-items: center;
		gap: 4px;
		margin-bottom: 3px;
	}
	.delta-label {
		width: 65px;
		flex-shrink: 0;
		color: #94a3b8;
		font-size: 9px;
		text-align: right;
	}
	.delta-bar-container {
		flex: 1;
	}
	.delta-bar-bg {
		height: 6px;
		background: #1e293b;
		border-radius: 3px;
		overflow: hidden;
	}
	.delta-bar {
		height: 100%;
		border-radius: 3px;
		transition: width 0.3s ease;
		min-width: 2px;
	}
	.delta-value {
		width: 30px;
		text-align: right;
		font-size: 9px;
		font-weight: 600;
	}
	.notable-diff {
		margin-top: 8px;
		padding: 6px 8px;
		background: rgba(255, 255, 255, 0.03);
		border-radius: 6px;
		border: 1px solid #1e293b;
	}
	.diff-title {
		font-size: 9px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #64748b;
		margin-bottom: 3px;
	}
	.diff-text {
		color: #cbd5e1;
		font-size: 10px;
	}
	.back-btn {
		margin-top: 8px;
		width: 100%;
		padding: 5px 8px;
		border-radius: 6px;
		font-size: 10px;
		font-weight: 500;
		cursor: pointer;
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid #334155;
		color: #94a3b8;
		transition: all 0.15s;
	}
	.back-btn:hover {
		border-color: #60a5fa;
		color: #60a5fa;
	}
</style>
