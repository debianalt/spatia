<script lang="ts">
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import { HEX_LAYER_REGISTRY, DATA_FRESHNESS, type AnalysisConfig } from '$lib/config';

	let {
		analysis,
		hexStore,
	}: {
		analysis: AnalysisConfig;
		hexStore: HexStore;
	} = $props();

	const layerCfg = $derived(HEX_LAYER_REGISTRY[analysis.id]);
	const freshness = $derived(layerCfg ? DATA_FRESHNESS[layerCfg.parquet] : null);
	const loading = $derived(hexStore.loading);
	const selectedHexes = $derived(hexStore.selectedHexes);
</script>

<div class="overture-analysis">
	<p class="desc">{i18n.t(analysis.descKey)}</p>

	{#if freshness}
		<div class="freshness">
			<span class="freshness-label">{i18n.t('data.updatedAt')}: {freshness.processedDate}</span>
			<span class="freshness-source">{i18n.t(freshness.sourceKey)}</span>
		</div>
	{/if}

	{#if loading}
		<div class="loading">{i18n.t('lens.loading')}</div>
	{:else if layerCfg}
		<div class="variables-hint">
			{#each layerCfg.variables as v}
				<div class="variable-tag">{i18n.t(v.labelKey)}</div>
			{/each}
		</div>

		{#if selectedHexes.size === 0}
			<p class="hint">{i18n.t('lens.selectRadio')}</p>
		{:else}
			<div class="selected-hexes">
				{#each [...selectedHexes] as [h3index, sel]}
					<div class="hex-card">
						<div class="hex-id">{h3index.slice(0, 4)}...{h3index.slice(-4)}</div>
						<div class="hex-values">
							{#each layerCfg.variables as v}
								{@const val = sel.data[v.col]}
								{#if val != null}
									<div class="hex-val">
										<span class="hex-val-label">{i18n.t(v.labelKey)}</span>
										<span class="hex-val-num">{typeof val === 'number' ? (Number.isInteger(val) ? val.toLocaleString() : val.toFixed(1)) : val}</span>
									</div>
								{/if}
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	{/if}
</div>

<style>
	.overture-analysis {
		font-size: 11px;
	}
	.desc {
		color: #a3a3a3;
		margin: 0 0 8px;
		line-height: 1.4;
	}
	.freshness {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin-bottom: 8px;
		padding: 4px 6px;
		background: rgba(255, 255, 255, 0.03);
		border-radius: 4px;
	}
	.freshness-label {
		color: #737373;
		font-size: 9px;
	}
	.freshness-source {
		color: #525252;
		font-size: 9px;
	}
	.variables-hint {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-bottom: 10px;
	}
	.variable-tag {
		background: rgba(255, 255, 255, 0.06);
		color: #d4d4d4;
		padding: 2px 6px;
		border-radius: 3px;
		font-size: 9px;
	}
	.hint {
		color: #737373;
		font-style: italic;
	}
	.loading {
		color: #737373;
		font-style: italic;
	}
	.selected-hexes {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.hex-card {
		background: rgba(255, 255, 255, 0.04);
		border-radius: 6px;
		padding: 6px 8px;
	}
	.hex-id {
		font-family: monospace;
		font-size: 9px;
		color: #737373;
		margin-bottom: 4px;
	}
	.hex-values {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.hex-val {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
	}
	.hex-val-label {
		color: #a3a3a3;
	}
	.hex-val-num {
		color: #e5e5e5;
		font-weight: 500;
		font-variant-numeric: tabular-nums;
	}
</style>
