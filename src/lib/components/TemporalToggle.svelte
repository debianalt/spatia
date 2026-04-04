<script lang="ts">
	import type { TemporalMode } from '$lib/config';
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let { hexStore, layerId = '' }: { hexStore: HexStore; layerId?: string } = $props();

	const modes: TemporalMode[] = ['current', 'baseline', 'delta'];
	const labelKeys: Record<TemporalMode, string> = {
		current: 'temporal.current',
		baseline: 'temporal.baseline',
		delta: 'temporal.delta',
	};

	function getHint(mode: TemporalMode): string {
		// Try layer-specific hint first, fall back to generic
		if (layerId) {
			const specific = `temporal.hint.${layerId}.${mode}`;
			const val = i18n.t(specific);
			if (val !== specific) return val; // found
		}
		return i18n.t(`temporal.hint.${mode}`);
	}
</script>

<div class="temporal-toggle">
	{#each modes as mode}
		<button
			class="toggle-btn"
			class:active={hexStore.temporalMode === mode}
			onclick={() => hexStore.setTemporalMode(mode)}
		>
			{i18n.t(labelKeys[mode])}
		</button>
	{/each}
</div>
<p class="temporal-hint">{getHint(hexStore.temporalMode)}</p>

<style>
	.temporal-toggle {
		display: flex;
		gap: 2px;
		background: rgba(255,255,255,0.04);
		border-radius: 6px;
		padding: 2px;
		margin: 8px 0;
	}
	.toggle-btn {
		flex: 1;
		padding: 4px 6px;
		background: none;
		border: none;
		border-radius: 4px;
		color: #737373;
		font-size: 9px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.15s;
	}
	.toggle-btn:hover { color: #a3a3a3; }
	.toggle-btn.active {
		background: rgba(255,255,255,0.10);
		color: #e2e8f0;
	}
	.temporal-hint {
		font-size: 8px;
		color: rgba(255,255,255,0.40);
		margin: -4px 0 6px;
		line-height: 1.3;
	}
</style>
