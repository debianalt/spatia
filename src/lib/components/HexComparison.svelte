<script lang="ts">
	import type { HexStore } from '$lib/stores/hex.svelte';
	import PetalChart from './PetalChart.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		hexStore,
	}: {
		hexStore: HexStore;
	} = $props();

	const selected = $derived([...hexStore.selectedHexes.entries()]);
	const layer = $derived(hexStore.activeLayer);
	const variables = $derived(layer?.variables ?? []);
	const petalLayers = $derived(hexStore.selectionPetalLayers);
	const petalLabels = $derived(hexStore.petalLabels);
</script>

<div class="hex-comparison">
	<div class="hc-header">
		<span class="hc-title">{i18n.t('hex.comparison')}</span>
		<button class="hc-clear" onclick={() => hexStore.clearSelection()}>
			&#10005; {i18n.t('ctrl.clear')}
		</button>
	</div>

	<!-- Hex chips -->
	<div class="hc-chips">
		{#each selected as [h3index, data]}
			<span class="hc-chip">
				<span class="hc-dot" style:background={data.color}></span>
				<span class="hc-label">{h3index.slice(0, 4)}...{h3index.slice(-4)}</span>
				<button class="hc-remove" onclick={() => hexStore.deselectHex(h3index)}>&#10005;</button>
			</span>
		{/each}
	</div>

	<!-- Petal chart (normalized vs provincial avg) -->
	{#if petalLayers.length > 0 && petalLabels.length >= 3}
		<PetalChart layers={petalLayers} labels={petalLabels} size={420} />
		<div class="hc-ref-note">
			<span class="hc-ref-dash"></span> 50 = {i18n.t('hex.provAvg') ?? 'prov. avg'}
		</div>
	{/if}

	<!-- Dimension bars per variable -->
	{#if variables.length > 0}
		<div class="hc-bars-section">
			{#each variables as variable, vi}
				<div class="hc-var-row">
					<div class="hc-var-label">{i18n.t(variable.labelKey)}</div>
					<div class="hc-var-bars">
						{#each selected as [h3index, data]}
							{@const raw = data.data[variable.col] ?? 0}
							{@const maxVal = Math.max(...selected.map(([, d]) => d.data[variable.col] ?? 0), 1)}
							{@const pct = (raw / maxVal) * 100}
							<div class="hc-bar-row">
								<div class="hc-bar-track">
									<div class="hc-bar-fill" style:width="{pct}%" style:background={data.color}></div>
								</div>
								<span class="hc-bar-val">{raw.toFixed(1)}</span>
							</div>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.hex-comparison { font-size: 11px; }
	.hc-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;
	}
	.hc-title {
		font-size: 12px;
		font-weight: 600;
		color: #e2e8f0;
	}
	.hc-clear {
		font-size: 9px;
		padding: 2px 6px;
		border-radius: 4px;
		background: rgba(255,255,255,0.06);
		border: 1px solid #334155;
		color: #94a3b8;
		cursor: pointer;
		transition: all 0.15s;
	}
	.hc-clear:hover { border-color: #ef4444; color: #ef4444; }

	.hc-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-bottom: 8px;
	}
	.hc-chip {
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 2px 6px;
		border-radius: 4px;
		background: rgba(255,255,255,0.06);
		border: 1px solid #334155;
		font-size: 10px;
		color: #e2e8f0;
	}
	.hc-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.hc-label { font-family: monospace; font-weight: 500; }
	.hc-remove {
		background: none;
		border: none;
		color: #64748b;
		cursor: pointer;
		font-size: 9px;
		padding: 0 2px;
		line-height: 1;
	}
	.hc-remove:hover { color: #ef4444; }

	.hc-ref-note {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 9px;
		color: rgba(255,255,255,0.45);
		margin: -4px 0 8px;
		justify-content: center;
	}
	.hc-ref-dash {
		display: inline-block;
		width: 16px;
		border-top: 1px dashed rgba(255,255,255,0.5);
	}

	.hc-bars-section { margin-top: 4px; }
	.hc-var-row { margin-bottom: 6px; }
	.hc-var-label {
		font-size: 9px;
		color: #94a3b8;
		margin-bottom: 2px;
	}
	.hc-var-bars {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.hc-bar-row {
		display: flex;
		align-items: center;
		gap: 4px;
	}
	.hc-bar-track {
		flex: 1;
		height: 5px;
		background: #1e293b;
		border-radius: 3px;
		overflow: hidden;
	}
	.hc-bar-fill {
		height: 100%;
		border-radius: 3px;
		transition: width 0.3s ease;
		min-width: 2px;
	}
	.hc-bar-val {
		font-size: 8px;
		font-weight: 600;
		color: #cbd5e1;
		width: 32px;
		text-align: right;
		flex-shrink: 0;
	}
</style>
