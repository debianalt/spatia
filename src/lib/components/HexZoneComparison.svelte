<script lang="ts">
	import PetalChart from './PetalChart.svelte';
	import type { HexStore, HexZone } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import {
		downloadCsvFromRows,
		downloadGeoJsonFromPolygon,
		downloadGeoJsonFromHexList,
	} from '$lib/utils/data-export';

	let {
		hexStore,
		onRemoveHexZone,
		onClearHexZones,
	}: {
		hexStore: HexStore;
		onRemoveHexZone: (id: string) => void;
		onClearHexZones: () => void;
	} = $props();

	const CENSUS_ANALYSES = new Set(['service_deprivation', 'health_access', 'education_capital', 'education_flow', 'sociodemographic', 'economic_activity', 'accessibility']);
	const zones = $derived(hexStore.hexZones);
	const layers = $derived(hexStore.petalLayers);
	const labels = $derived(hexStore.petalLabels);
	const variables = $derived(hexStore.activeLayer?.variables ?? []);
	const showPetals = $derived(hexStore.activeLayer ? !CENSUS_ANALYSES.has(hexStore.activeLayer.id) : true);

	function zoneFilenameBase(zone: HexZone): string {
		const layerId = hexStore.activeLayer?.id ?? 'layer';
		return `spatia_${layerId}_zone_${zone.id}`;
	}

	function downloadZoneHexesCsv(zone: HexZone) {
		const rows = zone.h3indices.map((h3) => {
			const data = hexStore.visibleData.get(h3) ?? {};
			return { h3index: h3, ...data };
		});
		if (rows.length === 0) return;
		const allCols = new Set<string>(['h3index']);
		for (const row of rows) for (const k of Object.keys(row)) allCols.add(k);
		downloadCsvFromRows(rows, [...allCols], `${zoneFilenameBase(zone)}_hexes.csv`);
	}

	function downloadZoneHexesGeoJson(zone: HexZone) {
		if (zone.h3indices.length === 0) return;
		downloadGeoJsonFromHexList(zone.h3indices, hexStore.visibleData, `${zoneFilenameBase(zone)}_hexes.geojson`);
	}

	function downloadZonePolygonGeoJson(zone: HexZone) {
		const props: Record<string, unknown> = {
			zone: zone.id,
			color: zone.color,
			hex_count: zone.stats.hexCount,
			layer: hexStore.activeLayer?.id ?? null,
		};
		variables.forEach((v, i) => {
			if (v.col in NON_NUMERIC) return;
			props[v.col] = zone.stats.rawValues[i];
		});
		downloadGeoJsonFromPolygon(zone.polygon, props, `${zoneFilenameBase(zone)}_polygon.geojson`);
	}

	const NON_NUMERIC: Record<string, true> = { type: true, type_label: true, pca_1: true, pca_2: true, pca_3: true, score: true, flood_risk_score: true, risk_score: true, territorial_type: true };

	function downloadZonesSummaryCsv() {
		if (zones.length === 0) return;
		const numericVars = variables.filter((v) => !(v.col in NON_NUMERIC));
		const rows = zones.map((z) => {
			const row: Record<string, unknown> = {
				zone: z.id,
				hex_count: z.stats.hexCount,
				layer: hexStore.activeLayer?.id ?? '',
			};
			numericVars.forEach((v, i) => {
				row[v.col] = z.stats.rawValues[i];
				row[`${v.col}_norm`] = z.stats.normalizedValues[i];
			});
			return row;
		});
		const columns = Object.keys(rows[0]);
		downloadCsvFromRows(rows, columns, `spatia_${hexStore.activeLayer?.id ?? 'layer'}_zones_summary.csv`);
	}
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
	{#if layers.length > 0 && labels.length >= 3 && showPetals}
		<p class="text-[8px] text-text-dim text-center m-0 mb-0.5">{i18n.t('zone.petalNote')}</p>
		<PetalChart {layers} {labels} size={400} />
	{/if}

	<!-- Summary table -->
	<div class="hzc-table">
		<div class="hzc-table-header">
			<span class="hzt-col hzt-zone">{i18n.t('zone.title')}</span>
			<span class="hzt-col hzt-num">{i18n.t('hex.hexCount')}</span>
			{#each variables as v}
				<span class="hzt-col hzt-num">{i18n.t(v.labelKey)}</span>
			{/each}
			<span class="hzt-col hzt-actions"></span>
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
				<span class="hzt-col hzt-actions">
					<button class="hzc-dl-btn" title="Hexágonos CSV" onclick={() => downloadZoneHexesCsv(zone)}>csv</button>
					<button class="hzc-dl-btn" title="Hexágonos GeoJSON" onclick={() => downloadZoneHexesGeoJson(zone)}>geo</button>
					<button class="hzc-dl-btn" title="Polígono del lasso GeoJSON" onclick={() => downloadZonePolygonGeoJson(zone)}>poly</button>
				</span>
			</div>
		{/each}
	</div>

	{#if zones.length > 0}
		<div class="hzc-download-row">
			<button class="hzc-download-btn" onclick={downloadZonesSummaryCsv}>
				↓ Resumen comparativo (CSV)
			</button>
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
		color: #d4d4d4;
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
		color: #a3a3a3;
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
		color: #a3a3a3;
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
	.hzt-actions { flex: 1.2; display: flex; gap: 3px; justify-content: flex-end; }
	.hzc-dl-btn { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1); color: #94a3b8; font-size: 8px; padding: 1px 4px; border-radius: 3px; cursor: pointer; font-family: inherit; transition: all 0.15s; }
	.hzc-dl-btn:hover { background: rgba(96,165,250,0.15); border-color: rgba(96,165,250,0.4); color: #60a5fa; }

	.hzc-download-row { margin-top: 6px; }
	.hzc-download-btn { display: block; width: 100%; text-align: center; padding: 6px 10px; background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3); border-radius: 4px; color: #60a5fa; font-size: 9px; font-weight: 600; cursor: pointer; font-family: inherit; transition: all 0.15s; }
	.hzc-download-btn:hover { background: rgba(59,130,246,0.25); border-color: rgba(59,130,246,0.5); }

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
		color: #d4d4d4;
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
