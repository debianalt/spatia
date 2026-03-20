<script lang="ts">
	import PetalChart from './PetalChart.svelte';
	import { LENS_CONFIG } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		entries,
		lensStore,
		onRemoveRadio
	}: {
		entries: Array<{redcode: string, color: string}>;
		lensStore: LensStore;
		onRemoveRadio: (redcode: string) => void;
	} = $props();

	const lens = $derived(lensStore.activeLens);
	const cfg = $derived(lens ? LENS_CONFIG[lens] : null);
	const subLabels = $derived(cfg ? cfg.subLabelKeys.map(k => i18n.t(k)) : []);

	// Build layers for PetalChart
	const layers = $derived(
		entries.map(e => ({
			values: lensStore.getSubScores(e.redcode),
			color: e.color
		}))
	);

	// Scores per entry
	const scores = $derived(
		entries.map(e => ({
			redcode: e.redcode,
			color: e.color,
			total: lensStore.getScore(e.redcode),
			dpto: lensStore.getDpto(e.redcode)
		}))
	);

	// SubScores per entry for dimension bars
	const allSubScores = $derived(
		entries.map(e => lensStore.getSubScores(e.redcode))
	);

	function shortCode(rc: string): string {
		return rc.length > 5 ? '...' + rc.slice(-4) : rc;
	}
</script>

{#if cfg}
	<div class="comparison">
		<!-- Identifiers -->
		<div class="comp-ids">
			{#each entries as entry, idx}
				{#if idx > 0}
					<span class="comp-vs">vs</span>
				{/if}
				<span class="comp-id">
					<span class="comp-dot" style:background={entry.color}></span>
					{shortCode(entry.redcode)} <span class="comp-dpto">({scores[idx]?.dpto})</span>
				</span>
			{/each}
		</div>

		<!-- Overlay petal chart -->
		<PetalChart
			{layers}
			labels={subLabels}
			size={420}
		/>

		<!-- Score comparison -->
		<div class="comp-scores">
			{#each scores as s, idx}
				{#if idx > 0}
					<span class="comp-vs-score">vs</span>
				{/if}
				<span class="comp-score-val">{s.total.toFixed(0)}</span>
			{/each}
		</div>

		<!-- Dimension bars: N mini-bars per dimension -->
		<div class="dim-section">
			{#each subLabels as label, i}
				<div class="dim-row">
					<div class="dim-label">{label}</div>
					<div class="dim-bars-container">
						{#each entries as entry, ei}
							{@const val = allSubScores[ei]?.[i] ?? 0}
							<div class="dim-bar-track">
								<div class="dim-bar-fill" style:width="{val}%" style:background={entry.color}></div>
							</div>
						{/each}
					</div>
					<div class="dim-values">
						{#each entries as entry, ei}
							{@const val = allSubScores[ei]?.[i] ?? 0}
							<span class="dim-val">{val.toFixed(0)}</span>
						{/each}
					</div>
				</div>
			{/each}
		</div>

		<!-- Back button: remove last added radio -->
		<button class="back-btn" onclick={() => onRemoveRadio(entries[entries.length - 1].redcode)}>
			{i18n.t('card.back')}
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
		gap: 6px;
		margin-bottom: 6px;
		flex-wrap: wrap;
	}
	.comp-id {
		display: flex;
		align-items: center;
		gap: 4px;
		font-size: 10px;
		font-weight: 600;
		color: #e2e8f0;
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
		flex-wrap: wrap;
	}
	.comp-vs-score {
		color: #475569;
		font-size: 11px;
		font-weight: 400;
	}
	.comp-score-val {
		color: #e2e8f0;
	}
	.dim-section {
		margin: 6px 0;
	}
	.dim-row {
		display: flex;
		align-items: flex-start;
		gap: 4px;
		margin-bottom: 4px;
	}
	.dim-label {
		width: 65px;
		flex-shrink: 0;
		color: #94a3b8;
		font-size: 9px;
		text-align: right;
		padding-top: 1px;
	}
	.dim-bars-container {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.dim-bar-track {
		height: 5px;
		background: #1e293b;
		border-radius: 3px;
		overflow: hidden;
	}
	.dim-bar-fill {
		height: 100%;
		border-radius: 3px;
		transition: width 0.3s ease;
		min-width: 2px;
	}
	.dim-values {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0;
		width: 28px;
		flex-shrink: 0;
	}
	.dim-val {
		font-size: 8px;
		font-weight: 600;
		line-height: 7px;
		color: #cbd5e1;
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
