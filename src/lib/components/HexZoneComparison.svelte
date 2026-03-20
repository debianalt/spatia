<script lang="ts">
	import PetalChart from './PetalChart.svelte';
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		hexStore,
		onRemoveHexZone,
		onClearHexZones,
	}: {
		hexStore: HexStore;
		onRemoveHexZone: (id: string) => void;
		onClearHexZones: () => void;
	} = $props();

	const zones = $derived(hexStore.hexZones);
	const layers = $derived(hexStore.petalLayers);
	const labels = $derived(hexStore.petalLabels);
	const variables = $derived(hexStore.activeLayer?.variables ?? []);
</script>

<div class="hzc">
	<div class="hzc-header">
		<span class="hzc-title">{i18n.t('hexZone.title')}</span>
		<button class="hzc-clear-btn" onclick={onClearHexZones}>
			&#10005; {i18n.t('lasso.clearZones')}
		</button>
	</div>

	<!-- Zone chips -->
	<div class="hzc-chips">
		{#each zones as zone}
			<span class="hzc-chip">
				<span class="hzc-dot" style:background={zone.color}></span>
				<span class="hzc-chip-label">{i18n.t('zone.title')} {zone.id}</span>
				<button class="hzc-remove" onclick={() => onRemoveHexZone(zone.id)}>&#10005;</button>
			</span>
		{/each}
	</div>

	<!-- Petal chart (normalized: 50 = provincial avg) -->
	{#if layers.length > 0 && labels.length >= 3}
		<p class="text-[8px] text-text-dim text-center m-0 mb-0.5">{i18n.t('zone.petalNote')}</p>
		<PetalChart {layers} {labels} size={220} />
	{/if}

	<!-- Summary table -->
	<div class="hzc-table">
		<div class="hzc-table-header">
			<span class="hzt-col hzt-zone">{i18n.t('zone.title')}</span>
			<span class="hzt-col hzt-num">{i18n.t('hex.hexCount')}</span>
			{#each variables as v}
				<span class="hzt-col hzt-num">{i18n.t(v.labelKey)}</span>
			{/each}
		</div>
		{#each zones as zone}
			<div class="hzc-table-row">
				<span class="hzt-col hzt-zone">
					<span class="hzc-dot-sm" style:background={zone.color}></span>
					{zone.id}
				</span>
				<span class="hzt-col hzt-num">{zone.stats.hexCount}</span>
				{#each zone.stats.rawValues as rv}
					<span class="hzt-col hzt-num">{rv.toFixed(1)}</span>
				{/each}
			</div>
		{/each}
	</div>

	<!-- Dimension bars -->
	{#if variables.length > 0}
		<div class="hzc-dim-section">
			{#each labels as label, i}
				<div class="hzc-dim-row">
					<div class="hzc-dim-label">{label}</div>
					<div class="hzc-dim-bars">
						{#each zones as zone}
							{@const raw = zone.stats.rawValues[i] ?? 0}
							{@const maxVal = Math.max(...zones.map(z => z.stats.rawValues[i] ?? 0), 1)}
							{@const pct = (raw / maxVal) * 100}
							<div class="hzc-dim-bar-track">
								<div class="hzc-dim-bar-fill" style:width="{pct}%" style:background={zone.color}></div>
							</div>
						{/each}
					</div>
					<div class="hzc-dim-values">
						{#each zones as zone}
							{@const raw = zone.stats.rawValues[i] ?? 0}
							<span class="hzc-dim-val">{raw.toFixed(1)}</span>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.hzc { font-size: 11px; }
	.hzc-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;
	}
	.hzc-title {
		font-size: 12px;
		font-weight: 600;
		color: #e2e8f0;
	}
	.hzc-clear-btn {
		font-size: 9px;
		padding: 2px 6px;
		border-radius: 4px;
		background: rgba(255,255,255,0.06);
		border: 1px solid #334155;
		color: #94a3b8;
		cursor: pointer;
		transition: all 0.15s;
	}
	.hzc-clear-btn:hover { border-color: #ef4444; color: #ef4444; }

	.hzc-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-bottom: 6px;
	}
	.hzc-chip {
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
	.hzc-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.hzc-dot-sm {
		display: inline-block;
		width: 6px;
		height: 6px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.hzc-chip-label { font-weight: 500; }
	.hzc-remove {
		background: none;
		border: none;
		color: #64748b;
		cursor: pointer;
		font-size: 9px;
		padding: 0 2px;
		line-height: 1;
	}
	.hzc-remove:hover { color: #ef4444; }

	.hzc-table { margin: 8px 0; }
	.hzc-table-header {
		display: flex;
		gap: 4px;
		padding-bottom: 3px;
		border-bottom: 1px solid #1e293b;
		margin-bottom: 3px;
	}
	.hzc-table-header .hzt-col {
		font-size: 9px;
		font-weight: 600;
		color: #64748b;
		text-transform: uppercase;
	}
	.hzc-table-row {
		display: flex;
		gap: 4px;
		padding: 2px 0;
	}
	.hzt-col { flex: 1; }
	.hzt-zone { flex: 0.6; display: flex; align-items: center; gap: 4px; }
	.hzt-num { text-align: right; color: #cbd5e1; font-size: 10px; }

	.hzc-dim-section { margin: 8px 0; }
	.hzc-dim-row {
		display: flex;
		align-items: flex-start;
		gap: 4px;
		margin-bottom: 4px;
	}
	.hzc-dim-label {
		width: 65px;
		flex-shrink: 0;
		color: #94a3b8;
		font-size: 9px;
		text-align: right;
		padding-top: 1px;
	}
	.hzc-dim-bars {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.hzc-dim-bar-track {
		height: 5px;
		background: #1e293b;
		border-radius: 3px;
		overflow: hidden;
	}
	.hzc-dim-bar-fill {
		height: 100%;
		border-radius: 3px;
		transition: width 0.3s ease;
		min-width: 2px;
	}
	.hzc-dim-values {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0;
		width: 32px;
		flex-shrink: 0;
	}
	.hzc-dim-val {
		font-size: 8px;
		font-weight: 600;
		line-height: 7px;
		color: #cbd5e1;
	}
</style>
