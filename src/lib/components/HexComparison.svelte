<script lang="ts">
	import type { HexStore } from '$lib/stores/hex.svelte';
	import PetalChart from './PetalChart.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import { downloadCsvFromRows, downloadGeoJsonFromHexList } from '$lib/utils/data-export';

	let {
		hexStore,
	}: {
		hexStore: HexStore;
	} = $props();

	const CENSUS_ANALYSES = new Set(['service_deprivation', 'health_access', 'education_capital', 'education_flow', 'economic_activity', 'accessibility', 'carbon_stock', 'productive_activity']);
	const selected = $derived([...hexStore.selectedHexes.entries()]);
	const layer = $derived(hexStore.activeLayer);
	const isCensus = $derived(layer ? CENSUS_ANALYSES.has(layer.id) : false);
	const showPetals = $derived(layer ? !CENSUS_ANALYSES.has(layer.id) : true);
	const variables = $derived(layer?.variables ?? []);
	const componentVars = $derived(
		variables.filter(v => !['score', 'type', 'pca_1', 'pca_2'].includes(v.col))
	);
	const petalLayers = $derived(hexStore.selectionPetalLayers);
	const petalLabels = $derived(hexStore.petalLabels);

	/**
	 * Adaptive number formatter — picks precision based on magnitude so that
	 * fractional values like NDVI (0.85) do not collapse to "1" via toFixed(0).
	 */
	function fmtSmart(v: unknown): string {
		if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
		if (v === 0) return '0';
		const abs = Math.abs(v);
		if (abs < 0.01) return v.toExponential(1);
		if (abs < 1) return v.toFixed(2);
		if (abs < 10) return v.toFixed(2);
		if (abs < 100) return v.toFixed(1);
		return v.toFixed(0);
	}

	function downloadSelectedCsv() {
		const rows = [...hexStore.selectedHexes.entries()].map(([h3, sel]) => ({ h3index: h3, ...sel.data }));
		if (rows.length === 0) return;
		const allCols = new Set<string>(['h3index']);
		for (const row of rows) for (const k of Object.keys(row)) allCols.add(k);
		const layerId = hexStore.activeLayer?.id ?? 'layer';
		downloadCsvFromRows(rows, [...allCols], `spatia_${layerId}_hexes_seleccionados.csv`);
	}

	function downloadSelectedGeoJson() {
		const h3s = [...hexStore.selectedHexes.keys()];
		if (h3s.length === 0) return;
		const layerId = hexStore.activeLayer?.id ?? 'layer';
		downloadGeoJsonFromHexList(h3s, hexStore.visibleData, `spatia_${layerId}_hexes_seleccionados.geojson`);
	}
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
	{#if petalLayers.length > 0 && petalLabels.length >= 3 && showPetals}
		<PetalChart layers={petalLayers} labels={petalLabels} size={340} />
		<div class="hc-ref-note">
			<span class="hc-ref-dash"></span> 50 = {i18n.t('hex.provAvg') ?? 'prov. avg'}
		</div>
	{/if}

	<!-- Data rows for ALL selected hexagons (always shown) -->
	{#if componentVars.length > 0}
		{#each selected as [h3index, hexData]}
			<div class="cd-hex-block">
				<div class="cd-hex-id">
					<span class="hc-dot" style:background={hexData.color}></span>
					{h3index.slice(0, 4)}...{h3index.slice(-4)}
					{#if hexData.data?.type_label}
						<span class="cd-type">{hexData.data.type_label}</span>
					{/if}
				</div>
				{#each componentVars as v}
					{@const val = hexData.data?.[v.col]}
					{@const isStr = typeof val === 'string' && val.length > 0}
					{@const numVal = typeof val === 'number' ? val : 0}
					{@const rawVal = v.rawCol ? hexData.data?.[v.rawCol] : null}
					{@const displayVal = (rawVal != null && typeof rawVal === 'number') ? rawVal : numVal}
					<div class="cd-row">
						<span class="cd-label">{i18n.t(v.labelKey)}</span>
						<span class="cd-val-data">{isStr ? val : fmtSmart(displayVal) + (v.unit ? ` ${v.unit}` : ' (0–100)')}</span>
					</div>
				{/each}
			</div>
		{/each}
	{/if}

	{#if selected.length > 0}
		<div class="hc-download-row">
			<button class="hc-dl-btn" onclick={downloadSelectedCsv}>↓ CSV</button>
			<button class="hc-dl-btn" onclick={downloadSelectedGeoJson}>↓ GeoJSON</button>
		</div>
	{/if}

</div>

<style>
	.hex-comparison { font-size: 11px; }
	.cd-hex-block { margin: 8px 0; padding: 6px 0; border-top: 1px solid rgba(255,255,255,0.06); }
	.cd-hex-id { display: flex; align-items: center; gap: 5px; font-size: 10px; color: #e2e8f0; font-family: monospace; margin-bottom: 5px; }
	.cd-type { font-size: 10px; color: #e2e8f0; font-weight: 500; background: rgba(255,255,255,0.08); padding: 1px 6px; border-radius: 3px; font-family: sans-serif; }
	.cd-row { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }
	.cd-label { font-size: 9px; color: #d4d4d4; flex: 0 0 auto; min-width: 100px; }
	.cd-bar-track { flex: 1; height: 5px; background: #1e293b; border-radius: 3px; overflow: hidden; }
	.cd-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; min-width: 2px; }
	.cd-val { font-size: 8px; font-weight: 600; color: #cbd5e1; width: 24px; text-align: right; flex-shrink: 0; }
	.cd-val-data { font-size: 10px; font-weight: 600; color: #e2e8f0; text-align: right; margin-left: auto; white-space: nowrap; }
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
		color: #d4d4d4;
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
		color: #a3a3a3;
		cursor: pointer;
		font-size: 9px;
		padding: 0 2px;
		line-height: 1;
	}
	.hc-remove:hover { color: #ef4444; }

	.hc-download-row { margin-top: 8px; display: flex; gap: 6px; }
	.hc-dl-btn { flex: 1; padding: 6px 10px; background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3); border-radius: 4px; color: #60a5fa; font-size: 9px; font-weight: 600; cursor: pointer; font-family: inherit; transition: all 0.15s; }
	.hc-dl-btn:hover { background: rgba(59,130,246,0.25); border-color: rgba(59,130,246,0.5); }

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
		color: #d4d4d4;
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
