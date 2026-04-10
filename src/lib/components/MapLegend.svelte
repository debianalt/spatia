<script lang="ts">
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let { hexStore }: { hexStore: HexStore } = $props();

	const PALETTE = ['#1565c0', '#7e57c2', '#4db6ac', '#66bb6a', '#c0ca33', '#ffb74d', '#e65100', '#78909c'];

	const layer = $derived(hexStore.activeLayer);
	// Use diverging scale when temporal delta mode is active, otherwise use layer's configured scale
	const effectiveScale = $derived(
		layer?.temporal && hexStore.temporalMode === 'delta' ? 'diverging' : layer?.colorScale
	);
	const isCategorical = $derived(effectiveScale === 'categorical');
	const isSequential = $derived(effectiveScale === 'sequential');
	const isFlood = $derived(effectiveScale === 'flood');
	const isGreen = $derived(effectiveScale === 'green');
	const isWarm = $derived(effectiveScale === 'warm');
	const isDiverging = $derived(effectiveScale === 'diverging');
	const isGradient = $derived(isSequential || isFlood || isGreen || isWarm || isDiverging);

	const title = $derived(layer ? i18n.t(layer.titleKey) : '');

	// Extract unique type labels from visible data (categorical)
	const typeEntries = $derived.by(() => {
		if (!isCategorical) return [];
		const types = new Map<number, string>();
		for (const [, data] of hexStore.visibleData) {
			const t = data.type ?? data.territorial_type;
			if (t && !types.has(t)) {
				const label = data.type_label;
				types.set(t, typeof label === 'number' ? '' : (label as unknown as string) || '');
			}
		}
		return [...types.entries()].sort((a, b) => a[0] - b[0]);
	});

	const gradient = $derived(
		isFlood
			? 'linear-gradient(to right, #3b82f6, #eab308, #dc2626)'
			: isGreen
			? 'linear-gradient(to right, #14532d, #166534, #bbf7d0)'
			: isWarm
			? 'linear-gradient(to right, #78350f, #f59e0b, #fde725)'
			: isDiverging
			? 'linear-gradient(to right, #ef4444, #a3a3a3, #22c55e)'
			: 'linear-gradient(to right, #5b21b6, #21918c, #fde725)'
	);

	const lowLabel = $derived(
		layer?.legendLowKey ? i18n.t(layer.legendLowKey)
		: isFlood ? i18n.t('legend.lowRisk')
		: isDiverging ? i18n.t('temporal.legend.worse')
		: i18n.t('legend.low')
	);
	const highLabel = $derived(
		layer?.legendHighKey ? i18n.t(layer.legendHighKey)
		: isFlood ? i18n.t('legend.highRisk')
		: isDiverging ? i18n.t('temporal.legend.better')
		: i18n.t('legend.high')
	);
</script>

{#if layer && (isCategorical && typeEntries.length > 0)}
	<div class="legend">
		<div class="legend-title">{title}</div>
		<div class="legend-items">
			{#each typeEntries as [type, label]}
				<div class="legend-item">
					<span class="legend-swatch" style:background={PALETTE[(type - 1) % PALETTE.length]}></span>
					<span class="legend-label">{label || `Tipo ${type}`}</span>
				</div>
			{/each}
		</div>
	</div>
{:else if layer && isGradient}
	<div class="legend">
		<div class="legend-title">{title}</div>
		<div class="gradient-bar" style:background={gradient}></div>
		<div class="gradient-labels">
			<span>{lowLabel}</span>
			<span class="gradient-range">0–100</span>
			<span>{highLabel}</span>
		</div>
		<div class="nodata-row">
			<span class="nodata-swatch"></span>
			<span class="nodata-label">{i18n.t('legend.noData')}</span>
		</div>
	</div>
{/if}

<style>
	.legend {
		position: absolute;
		bottom: 68px;
		left: 12px;
		background: rgba(10, 12, 18, 0.85);
		backdrop-filter: blur(6px);
		border: 1px solid rgba(255,255,255,0.08);
		border-radius: 6px;
		padding: 8px 10px;
		z-index: 10;
		min-width: 120px;
		max-width: 200px;
	}
	.legend-title {
		font-size: 9px;
		font-weight: 600;
		color: rgba(255,255,255,0.7);
		margin-bottom: 6px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		line-height: 1.3;
	}
	.legend-items {
		display: flex;
		flex-direction: column;
		gap: 3px;
	}
	.legend-item {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.legend-swatch {
		width: 10px;
		height: 10px;
		border-radius: 2px;
		flex-shrink: 0;
	}
	.legend-label {
		font-size: 9px;
		color: #d4d4d4;
	}
	.gradient-bar {
		height: 8px;
		border-radius: 3px;
		width: 100%;
	}
	.gradient-labels {
		display: flex;
		justify-content: space-between;
		font-size: 8px;
		color: rgba(255,255,255,0.55);
		margin-top: 3px;
	}
	.gradient-range {
		font-size: 7px;
		color: rgba(255,255,255,0.35);
	}
	.nodata-row {
		display: flex;
		align-items: center;
		gap: 5px;
		margin-top: 5px;
		padding-top: 4px;
		border-top: 1px solid rgba(255,255,255,0.06);
	}
	.nodata-swatch {
		width: 10px;
		height: 10px;
		border-radius: 2px;
		background: #374151;
		flex-shrink: 0;
	}
	.nodata-label {
		font-size: 8px;
		color: rgba(255,255,255,0.4);
	}

	@media (max-width: 768px) {
		.legend {
			bottom: 50px;
			left: 8px;
			max-width: 160px;
			padding: 6px 8px;
		}
	}
</style>
