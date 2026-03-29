<script lang="ts">
	import PetalChart from './PetalChart.svelte';
	import { PETAL_VARS, type LassoStore } from '$lib/stores/lasso.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		lassoStore,
		onRemoveZone,
		onClearZones,
	}: {
		lassoStore: LassoStore;
		onRemoveZone: (id: string) => void;
		onClearZones: () => void;
	} = $props();

	const zones = $derived(lassoStore.zones);
	const layers = $derived(lassoStore.petalLayers);
	const labels = $derived(lassoStore.petalLabels);
</script>

<div class="zone-comparison">
	<div class="zone-header">
		<span class="zone-title">{i18n.t('zone.title')}</span>
		<button class="zone-clear-btn" onclick={onClearZones}>
			&#10005; {i18n.t('lasso.clearZones')}
		</button>
	</div>

	<!-- Zone chips -->
	<div class="zone-chips">
		{#each zones as zone}
			<span class="zone-chip">
				<span class="zone-dot" style:background={zone.color}></span>
				<span class="zone-label">{i18n.t('zone.title')} {zone.id}</span>
				<button class="zone-remove" onclick={() => onRemoveZone(zone.id)}>&#10005;</button>
			</span>
		{/each}
	</div>

	<!-- Petal chart (normalized: 50 = provincial avg) -->
	{#if layers.length > 0}
		<p class="text-[8px] text-text-dim text-center m-0 mb-0.5">{i18n.t('zone.petalNote')}</p>
		<PetalChart {layers} {labels} size={340} />
	{/if}

	<!-- Summary table -->
	<div class="zone-table">
		<div class="zone-table-header">
			<span class="zt-col zt-zone">{i18n.t('zone.title')}</span>
			<span class="zt-col zt-num">{i18n.t('zone.population')}</span>
			<span class="zt-col zt-num">{i18n.t('zone.area')}</span>
			<span class="zt-col zt-num">{i18n.t('zone.radios')}</span>
		</div>
		{#each zones as zone}
			<div class="zone-table-row">
				<span class="zt-col zt-zone">
					<span class="zone-dot-sm" style:background={zone.color}></span>
					{zone.id}
				</span>
				<span class="zt-col zt-num">{zone.stats.population.toLocaleString()}</span>
				<span class="zt-col zt-num">{zone.stats.area_km2.toFixed(1)}</span>
				<span class="zt-col zt-num">{zone.stats.radioCount}</span>
			</div>
		{/each}
	</div>

</div>

<style>
	.zone-comparison { font-size: 11px; }
	.zone-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;
	}
	.zone-title {
		font-size: 12px;
		font-weight: 600;
		color: #e2e8f0;
	}
	.zone-clear-btn {
		font-size: 9px;
		padding: 2px 6px;
		border-radius: 4px;
		background: rgba(255,255,255,0.06);
		border: 1px solid #334155;
		color: #d4d4d4;
		cursor: pointer;
		transition: all 0.15s;
	}
	.zone-clear-btn:hover { border-color: #ef4444; color: #ef4444; }

	.zone-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-bottom: 6px;
	}
	.zone-chip {
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
	.zone-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.zone-dot-sm {
		display: inline-block;
		width: 6px;
		height: 6px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.zone-label { font-weight: 500; }
	.zone-remove {
		background: none;
		border: none;
		color: #a3a3a3;
		cursor: pointer;
		font-size: 9px;
		padding: 0 2px;
		line-height: 1;
	}
	.zone-remove:hover { color: #ef4444; }

	.zone-table { margin: 8px 0; }
	.zone-table-header {
		display: flex;
		gap: 4px;
		padding-bottom: 3px;
		border-bottom: 1px solid #1e293b;
		margin-bottom: 3px;
	}
	.zone-table-header .zt-col {
		font-size: 9px;
		font-weight: 600;
		color: #a3a3a3;
		text-transform: uppercase;
	}
	.zone-table-row {
		display: flex;
		gap: 4px;
		padding: 2px 0;
	}
	.zt-col { flex: 1; }
	.zt-zone { flex: 0.6; display: flex; align-items: center; gap: 4px; }
	.zt-num { text-align: right; color: #cbd5e1; font-size: 10px; }

	.dim-section { margin: 8px 0; }
	.dim-row {
		display: flex;
		align-items: flex-start;
		gap: 4px;
		margin-bottom: 4px;
	}
	.dim-label {
		width: 65px;
		flex-shrink: 0;
		color: #d4d4d4;
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
		width: 32px;
		flex-shrink: 0;
	}
	.dim-val {
		font-size: 8px;
		font-weight: 600;
		line-height: 7px;
		color: #cbd5e1;
	}
</style>
