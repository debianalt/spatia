<script lang="ts">
	import PetalChart from './PetalChart.svelte';
	import type { LassoStore } from '$lib/stores/lasso.svelte';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { getParquetUrl, PARQUETS } from '$lib/config';
	import { initDuckDB, query, isReady } from '$lib/stores/duckdb';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		lassoStore,
		lensStore,
		onRemoveZone,
		onClearZones,
	}: {
		lassoStore: LassoStore;
		lensStore: LensStore;
		onRemoveZone: (id: string) => void;
		onClearZones: () => void;
	} = $props();

	// Housing quality variables (same as CatastroAnalysis)
	const HOUSING_COLS = ['pct_agua_red', 'pct_cloacas', 'pct_alumbrado', 'pct_pavimento', 'pct_hacinamiento', 'pct_nbi'];
	const HOUSING_LABELS_KEYS = [
		'analysis.catastro.h.agua', 'analysis.catastro.h.cloacas', 'analysis.catastro.h.alumbrado',
		'analysis.catastro.h.pavimento', 'analysis.catastro.h.hacinamiento', 'analysis.catastro.h.nbi'
	];
	// true = deficit variable (high=bad) → invert for petal (100-value)
	const HOUSING_DEFICIT = [true, true, false, false, true, true];

	const CATASTRO_METRICS = [
		{ key: 'n_parcelas_urbano', labelKey: 'analysis.catastro.totalUrban', agg: 'sum', fmt: 'int' },
		{ key: 'n_parcelas_rural', labelKey: 'analysis.catastro.totalRural', agg: 'sum', fmt: 'int' },
		{ key: 'area_media_urbano_m2', labelKey: 'analysis.catastro.avgAreaUrban', agg: 'avg', fmt: 'area' },
		{ key: 'area_media_rural_m2', labelKey: 'analysis.catastro.avgAreaRural', agg: 'avg', fmt: 'area' },
		{ key: 'n_new_parcels_90d', labelKey: 'analysis.catastro.newParcels', agg: 'sum', fmt: 'int' },
	] as const;

	interface ZoneCatastroData {
		zoneId: string;
		metrics: Record<string, number>;
		housingRaw: number[];       // population-weighted housing values
		housingNormalized: number[]; // 0-100, 50 = provincial avg
	}

	const zones = $derived(lassoStore.zones);
	let zoneData: ZoneCatastroData[] = $state([]);
	let housingProvAvg: Record<string, number> | null = $state(null);
	let loading = $state(true);

	// Reactive: reload when zones change
	$effect(() => {
		const z = zones;
		if (z.length > 0) {
			loadAllZoneData(z);
		} else {
			zoneData = [];
		}
	});

	async function loadAllZoneData(currentZones: typeof zones) {
		loading = true;
		try {
			await initDuckDB();
			if (!housingProvAvg) await loadHousingProvAvg();

			const results: ZoneCatastroData[] = [];
			for (const zone of currentZones) {
				const data = await loadZoneData(zone.id, zone.redcodes);
				if (data) results.push(data);
			}
			zoneData = results;
		} catch (e) {
			console.warn('Failed to load catastro zone data:', e);
		} finally {
			loading = false;
		}
	}

	async function loadHousingProvAvg() {
		const cols = HOUSING_COLS.map(c => `AVG(${c}) as ${c}`).join(', ');
		const result = await query(`SELECT ${cols} FROM '${PARQUETS.radio_stats_master}' WHERE pct_agua_red IS NOT NULL`);
		if (result.numRows > 0) {
			const row = result.get(0)!.toJSON() as Record<string, any>;
			const avg: Record<string, number> = {};
			for (const c of HOUSING_COLS) avg[c] = Number(row[c] ?? 0);
			housingProvAvg = avg;
		}
	}

	async function loadZoneData(zoneId: string, redcodes: string[]): Promise<ZoneCatastroData | null> {
		if (redcodes.length === 0) return null;
		const inClause = redcodes.map(r => `'${r}'`).join(',');

		// Catastro metrics
		const catUrl = getParquetUrl('catastro_by_radio');
		const catSql = `SELECT
			COALESCE(SUM(n_parcelas_urbano), 0) as n_parcelas_urbano,
			COALESCE(SUM(n_parcelas_rural), 0) as n_parcelas_rural,
			COALESCE(AVG(CASE WHEN area_media_urbano_m2 > 0 THEN area_media_urbano_m2 END), 0) as area_media_urbano_m2,
			COALESCE(AVG(CASE WHEN area_media_rural_m2 > 0 THEN area_media_rural_m2 END), 0) as area_media_rural_m2,
			COALESCE(SUM(n_new_parcels_90d), 0) as n_new_parcels_90d
		FROM '${catUrl}' WHERE redcode IN (${inClause})`;
		const catResult = await query(catSql);
		const catRow = catResult.numRows > 0 ? catResult.get(0)!.toJSON() as Record<string, any> : {};
		const metrics: Record<string, number> = {};
		for (const m of CATASTRO_METRICS) {
			metrics[m.key] = Number(catRow[m.key] ?? 0);
		}

		// Housing quality (population-weighted)
		const housingAgg = HOUSING_COLS.map(c =>
			`SUM(CAST(${c} AS DOUBLE) * CAST(total_personas AS DOUBLE)) / NULLIF(SUM(CAST(total_personas AS DOUBLE)), 0) as ${c}`
		).join(', ');
		const housingSql = `SELECT ${housingAgg} FROM '${PARQUETS.radio_stats_master}' WHERE redcode IN (${inClause}) AND total_personas > 0`;
		const housingResult = await query(housingSql);
		const housingRow = housingResult.numRows > 0 ? housingResult.get(0)!.toJSON() as Record<string, any> : {};

		const housingRaw = HOUSING_COLS.map(c => Number(housingRow[c] ?? 0));

		// Normalize to provincial avg
		const housingNormalized = HOUSING_COLS.map((col, i) => {
			let raw = housingRaw[i];
			let avg = housingProvAvg?.[col] ?? 1;
			if (HOUSING_DEFICIT[i]) { raw = 100 - raw; avg = 100 - avg; }
			if (avg === 0) return 50;
			return Math.min(100, Math.max(0, (raw / avg) * 50));
		});

		return { zoneId, metrics, housingRaw, housingNormalized };
	}

	// Petal layers for chart
	const petalLayers = $derived(
		zoneData.map((zd, i) => ({
			values: zd.housingNormalized,
			color: zones.find(z => z.id === zd.zoneId)?.color ?? '#60a5fa',
		}))
	);
	const petalLabels = $derived(HOUSING_LABELS_KEYS.map(k => i18n.t(k)));

	function fmt(n: number): string { return n.toLocaleString('es-AR', { maximumFractionDigits: 0 }); }
	function fmtArea(n: number): string {
		if (n === 0) return '-';
		return `${n.toLocaleString('es-AR', { maximumFractionDigits: 0 })} m\u00B2`;
	}
	function fmtMetric(v: number, f: string): string {
		return f === 'area' ? fmtArea(v) : fmt(v);
	}
</script>

<div class="zone-comparison">
	<div class="zone-header">
		<span class="zone-title">{i18n.t('zone.title')} — {i18n.t('analysis.catastro.title')}</span>
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

	{#if loading}
		<div class="loading">{i18n.t('analysis.loading')}</div>
	{:else if zoneData.length > 0}
		<!-- Catastro metrics comparison bars -->
		<div class="dim-section">
			{#each CATASTRO_METRICS as m}
				{@const vals = zoneData.map(zd => zd.metrics[m.key] ?? 0)}
				{@const maxVal = Math.max(...vals, 1)}
				<div class="dim-row">
					<div class="dim-label">{i18n.t(m.labelKey)}</div>
					<div class="dim-bars-container">
						{#each zones as zone, idx}
							{@const v = vals[idx] ?? 0}
							<div class="dim-bar-track">
								<div class="dim-bar-fill" style:width="{(v / maxVal) * 100}%" style:background={zone.color}></div>
							</div>
						{/each}
					</div>
					<div class="dim-values">
						{#each zones as _, idx}
							{@const v = vals[idx] ?? 0}
							<span class="dim-val">{fmtMetric(v, m.fmt)}</span>
						{/each}
					</div>
				</div>
			{/each}
		</div>

		<!-- Housing quality petal chart -->
		{#if petalLayers.length > 0}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.catastro.housingTitle')}</div>
				<p class="text-[8px] text-text-dim text-center m-0 mb-0.5">{i18n.t('analysis.catastro.petalHint')}</p>
				<PetalChart layers={petalLayers} labels={petalLabels} size={300} />
			</div>
		{/if}
	{/if}

	<div class="map-legend">
		<span class="legend-swatch" style:background="#22d3ee"></span> {i18n.t('analysis.catastro.legendUrban')}
		<span class="legend-swatch legend-gap" style:background="#4ade80"></span> {i18n.t('analysis.catastro.legendRural')}
	</div>
	<div class="source-note-box">
		<div><strong>{i18n.t('data.source.catastro')}</strong> · Censo 2022</div>
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

	.loading { color: #a3a3a3; font-size: 10px; padding: 12px 0; }

	.dim-section { margin: 8px 0; }
	.dim-row {
		display: flex;
		align-items: flex-start;
		gap: 4px;
		margin-bottom: 4px;
	}
	.dim-label {
		width: 72px;
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
		width: 50px;
		flex-shrink: 0;
	}
	.dim-val {
		font-size: 8px;
		font-weight: 600;
		line-height: 7px;
		color: #cbd5e1;
	}

	.section { margin-bottom: 8px; }
	.section-title {
		font-size: 9px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #a3a3a3;
		border-bottom: 1px solid #1e293b;
		padding-bottom: 2px;
		margin-bottom: 4px;
	}

	.map-legend { display: flex; align-items: center; gap: 4px; font-size: 8px; color: #a3a3a3; margin: 8px 0 4px; }
	.legend-swatch { width: 10px; height: 3px; border-radius: 1px; flex-shrink: 0; }
	.legend-gap { margin-left: 8px; }
	.source-note-box { margin-top: 10px; padding: 6px 8px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px; font-size: 8px; color: #737373; line-height: 1.4; }
</style>
