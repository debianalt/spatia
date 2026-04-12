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

	const CENSUS_ANALYSES = new Set(['service_deprivation', 'health_access', 'education_capital', 'education_flow', 'sociodemographic', 'economic_activity', 'accessibility', 'carbon_stock', 'productive_activity']);
	const zones = $derived(hexStore.hexZones);
	const variables = $derived(hexStore.activeLayer?.variables ?? []);
	// numericVariables matches rawValues indexing (same filter as store)
	const numVars = $derived(hexStore.numericVariables);
	const showPetals = $derived(hexStore.activeLayer ? !CENSUS_ANALYSES.has(hexStore.activeLayer.id) : true);
	const layers = $derived(hexStore.petalLayers);
	const labels = $derived(hexStore.petalLabels);

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

	function getDominantType(zone: HexZone): string | null {
		const counts = new Map<string, number>();
		for (const h3 of zone.h3indices) {
			const d = hexStore.visibleData.get(h3);
			const t = d?.type_label;
			if (typeof t === 'string') counts.set(t, (counts.get(t) ?? 0) + 1);
		}
		if (counts.size === 0) return null;
		let best = '', max = 0;
		for (const [k, v] of counts) { if (v > max) { best = k; max = v; } }
		return best;
	}

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
		const NON_NUMERIC: Record<string, true> = { type: true, type_label: true, pca_1: true, pca_2: true, pca_3: true, score: true, flood_risk_score: true, risk_score: true, territorial_type: true };
		variables.forEach((v, i) => {
			if (v.col in NON_NUMERIC) return;
			props[v.col] = zone.stats.rawValues[i];
		});
		downloadGeoJsonFromPolygon(zone.polygon, props, `${zoneFilenameBase(zone)}_polygon.geojson`);
	}

	function downloadZonesSummaryCsv() {
		if (zones.length === 0) return;
		const NON_NUMERIC: Record<string, true> = { type: true, type_label: true, pca_1: true, pca_2: true, pca_3: true, score: true, flood_risk_score: true, risk_score: true, territorial_type: true };
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

	<!-- Petal chart (normalized: 50 = provincial avg) — only for non-census layers -->
	{#if layers.length > 0 && labels.length >= 3 && showPetals}
		<p class="petal-note">{i18n.t('zone.petalNote')}</p>
		<PetalChart {layers} {labels} size={400} />
	{/if}

	<!-- Vertical zone blocks (like HexComparison) -->
	{#if numVars.length > 0}
		{#each zones as zone, zi}
			<div class="zone-block">
				<div class="zone-id">
					<span class="hzc-dot" style:background={zone.color}></span>
					{i18n.t('zone.title')} {zone.id}
					<span class="zone-hex-count">{zone.stats.hexCount} hex</span>
				</div>
				{#if getDominantType(zone)}
					<div class="zone-type">{getDominantType(zone)}</div>
				{/if}
				{#each numVars as v, vi}
					{@const rv = zone.stats.rawValues[vi]}
					<div class="cd-row">
						<span class="cd-label">{i18n.t(v.labelKey)}</span>
						<span class="cd-val">{fmtSmart(rv)}{v.unit ? ` ${v.unit}` : ' (0–100)'}</span>
					</div>
				{/each}
				<div class="zone-dl">
					<button class="hzc-dl-btn" title="Hexágonos CSV" onclick={() => downloadZoneHexesCsv(zone)}>csv</button>
					<button class="hzc-dl-btn" title="Hexágonos GeoJSON" onclick={() => downloadZoneHexesGeoJson(zone)}>geo</button>
					<button class="hzc-dl-btn" title="Polígono GeoJSON" onclick={() => downloadZonePolygonGeoJson(zone)}>poly</button>
				</div>
			</div>
		{/each}
	{/if}

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

	.petal-note { font-size: 8px; color: rgba(255,255,255,0.4); text-align: center; margin: 0 0 2px; }

	.zone-block { margin: 8px 0; padding: 6px 0; border-top: 1px solid rgba(255,255,255,0.06); }
	.zone-id { display: flex; align-items: center; gap: 5px; font-size: 10px; color: #e2e8f0; font-weight: 600; margin-bottom: 5px; }
	.zone-hex-count { font-size: 9px; color: rgba(255,255,255,0.4); font-weight: 400; margin-left: auto; }
	.zone-type { font-size: 10px; color: #e2e8f0; font-weight: 500; background: rgba(255,255,255,0.08); display: inline-block; padding: 1px 6px; border-radius: 3px; margin-bottom: 4px; }
	.cd-row { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }
	.cd-label { font-size: 9px; color: #d4d4d4; flex: 0 0 auto; min-width: 100px; }
	.cd-val { font-size: 10px; font-weight: 600; color: #e2e8f0; text-align: right; margin-left: auto; white-space: nowrap; }
	.zone-dl { display: flex; gap: 3px; margin-top: 4px; }

	.hzc-dl-btn { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1); color: #94a3b8; font-size: 8px; padding: 1px 4px; border-radius: 3px; cursor: pointer; font-family: inherit; transition: all 0.15s; }
	.hzc-dl-btn:hover { background: rgba(96,165,250,0.15); border-color: rgba(96,165,250,0.4); color: #60a5fa; }

	.hzc-download-row { margin-top: 6px; }
	.hzc-download-btn { display: block; width: 100%; text-align: center; padding: 6px 10px; background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3); border-radius: 4px; color: #60a5fa; font-size: 9px; font-weight: 600; cursor: pointer; font-family: inherit; transition: all 0.15s; }
	.hzc-download-btn:hover { background: rgba(59,130,246,0.25); border-color: rgba(59,130,246,0.5); }
</style>
