<script lang="ts">
	import type { HexStore } from '$lib/stores/hex.svelte';

	let { hexStore }: { hexStore: HexStore } = $props();

	const PALETTE = ['#1565c0', '#7e57c2', '#4db6ac', '#66bb6a', '#c0ca33', '#ffb74d', '#e65100', '#78909c'];

	const layer = $derived(hexStore.activeLayer);
	const isCategorical = $derived(layer?.colorScale === 'categorical');

	// Extract unique type labels from visible data
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
</script>

{#if layer && isCategorical && typeEntries.length > 0}
	<div class="legend">
		<div class="legend-items">
			{#each typeEntries as [type, label]}
				<div class="legend-item">
					<span class="legend-swatch" style:background={PALETTE[(type - 1) % PALETTE.length]}></span>
					<span class="legend-label">{label || `Tipo ${type}`}</span>
				</div>
			{/each}
		</div>
	</div>
{/if}

<style>
	.legend {
		position: absolute;
		bottom: 24px;
		left: 12px;
		background: rgba(10, 12, 18, 0.85);
		backdrop-filter: blur(6px);
		border: 1px solid rgba(255,255,255,0.08);
		border-radius: 6px;
		padding: 8px 10px;
		z-index: 10;
		min-width: 100px;
		max-width: 180px;
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
</style>
