<script lang="ts">
	import PetalChart from './PetalChart.svelte';
	import type { LassoStore } from '$lib/stores/lasso.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import { PARQUETS } from '$lib/config';
	import { initDuckDB, query } from '$lib/stores/duckdb';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		lassoStore,
		mapStore,
		onRemoveZone,
		onClearZones,
	}: {
		lassoStore: LassoStore;
		mapStore: MapStore;
		onRemoveZone: (id: string) => void;
		onClearZones: () => void;
	} = $props();

	// 6 census variables relevant to flood risk vulnerability
	const FLOOD_CENSUS_COLS = ['flood_frequency', 'hand_mean', 'pct_nbi', 'pct_cloacas', 'pct_agua_red', 'infra_deficit'];
	const FLOOD_CENSUS_LABELS = [
		'Frec. inundación', 'Altura s/ drenaje', 'NBI',
		'Sin cloacas', 'Sin agua de red', 'Déficit infra'
	];
	// true = INVERT for petal (higher raw value = LESS risk, so flip)
	const FLOOD_CENSUS_INVERT = [false, true, false, false, false, false];

	interface ZoneFloodCensus {
		zoneId: string;
		rawValues: number[];        // 6 pop-weighted averages
		normalizedValues: number[]; // 0-100, 50 = provincial avg
	}

	const zones = $derived(lassoStore.zones);
	const h3Data = $derived(mapStore.floodH3Data);
	let zoneCensusData: ZoneFloodCensus[] = $state([]);
	let provAvg: number[] | null = $state(null);
	let loading = $state(true);

	function getRiskColor(score: number): string {
		if (score >= 70) return '#dc2626';
		if (score >= 40) return '#eab308';
		return '#22c55e';
	}

	// Load census data per zone
	$effect(() => {
		const z = zones;
		if (z.length > 0) loadAllZones(z);
		else { zoneCensusData = []; loading = false; }
	});

	async function loadAllZones(currentZones: typeof zones) {
		loading = true;
		try {
			await initDuckDB();
			if (!provAvg) await loadProvAvg();

			const results: ZoneFloodCensus[] = [];
			for (const zone of currentZones) {
				const data = await loadZoneCensus(zone.id, zone.redcodes);
				if (data) results.push(data);
			}
			zoneCensusData = results;
		} catch (e) {
			console.warn('Failed to load flood zone census:', e);
		} finally { loading = false; }
	}

	async function loadProvAvg() {
		const cols = FLOOD_CENSUS_COLS.map(c =>
			`SUM(CAST(${c} AS DOUBLE) * CAST(total_personas AS DOUBLE)) / NULLIF(SUM(CAST(total_personas AS DOUBLE)), 0) as ${c}`
		).join(', ');
		const result = await query(`SELECT ${cols} FROM '${PARQUETS.radio_stats_master}' WHERE total_personas > 0`);
		if (result.numRows > 0) {
			const row = result.get(0)!.toJSON() as Record<string, any>;
			provAvg = FLOOD_CENSUS_COLS.map(c => Number(row[c]) || 1);
		}
	}

	async function loadZoneCensus(zoneId: string, redcodes: string[]): Promise<ZoneFloodCensus | null> {
		if (redcodes.length === 0) return null;
		const inClause = redcodes.map(r => `'${r}'`).join(',');
		const agg = FLOOD_CENSUS_COLS.map(c =>
			`SUM(CAST(${c} AS DOUBLE) * CAST(total_personas AS DOUBLE)) / NULLIF(SUM(CAST(total_personas AS DOUBLE)), 0) as ${c}`
		).join(', ');
		const result = await query(
			`SELECT ${agg} FROM '${PARQUETS.radio_stats_master}' WHERE redcode IN (${inClause}) AND total_personas > 0`
		);
		if (result.numRows === 0) return null;
		const row = result.get(0)!.toJSON() as Record<string, any>;
		const rawValues = FLOOD_CENSUS_COLS.map(c => Number(row[c]) || 0);

		// Normalize: 50 = provincial avg. For inverted vars, flip the ratio.
		const normalizedValues = rawValues.map((v, i) => {
			const avg = provAvg?.[i] ?? 1;
			if (avg === 0) return 50;
			let ratio = v / avg;
			if (FLOOD_CENSUS_INVERT[i]) ratio = avg / (v || 1); // invert: lower raw = higher risk
			return Math.min(100, Math.max(0, ratio * 50));
		});

		return { zoneId, rawValues, normalizedValues };
	}

	// Flood score bars from h3 data
	const zoneFloodScores = $derived.by(() => {
		if (h3Data.size === 0 || zones.length === 0) return [];
		const h3Entries = [...h3Data.entries()];
		const deptAvg = h3Entries.reduce((s, [, d]) => s + d.flood_risk_score, 0) / h3Entries.length;

		return zones.map(zone => ({
			zoneId: zone.id,
			flood_risk_score: deptAvg, // dept average (best approx without per-radio crosswalk)
		}));
	});

	// Petal layers from census data
	const petalLayers = $derived(
		zoneCensusData.map((zd, i) => ({
			values: zd.normalizedValues,
			color: zones.find(z => z.id === zd.zoneId)?.color ?? '#60a5fa',
		}))
	);
	const petalLabels = $derived(FLOOD_CENSUS_LABELS);
</script>

<div class="zone-comparison">
	<div class="zone-header">
		<span class="zone-title">{i18n.t('zone.title')} — {i18n.t('analysis.floodRisk.title')}</span>
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

	<!-- Flood risk score bars -->
	{#if zoneFloodScores.length > 0}
		<div class="section-title">{i18n.t('analysis.flood.riskScore')}</div>
		<div class="flood-scores">
			{#each zoneFloodScores as zd, i}
				<div class="flood-zone-row">
					<span class="zone-dot-sm" style:background={zones[i]?.color}></span>
					<span class="flood-zone-label">{zones[i]?.id}</span>
					<div class="score-track">
						<div class="score-fill" style:width="{zd.flood_risk_score}%" style:background={getRiskColor(zd.flood_risk_score)}></div>
					</div>
					<span class="flood-zone-val" style:color={getRiskColor(zd.flood_risk_score)}>{zd.flood_risk_score.toFixed(1)}</span>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Census vulnerability petal chart -->
	{#if loading}
		<div class="loading">Cargando perfil de vulnerabilidad...</div>
	{:else if petalLayers.length > 0}
		<div class="section-title">Perfil de vulnerabilidad hídrica</div>
		<p class="petal-note">Relativo al promedio provincial (50 = promedio). Mayor extensión = mayor riesgo.</p>
		<PetalChart layers={petalLayers} labels={petalLabels} size={320} />
		<div class="petal-defs">
			<div><strong>Frec. inundación:</strong> frecuencia histórica de anegamiento (satelital)</div>
			<div><strong>Altura s/ drenaje:</strong> elevación sobre el curso de agua más cercano</div>
			<div><strong>NBI:</strong> hogares con necesidades básicas insatisfechas (Censo 2022)</div>
			<div><strong>Sin cloacas:</strong> hogares sin red cloacal (Censo 2022)</div>
			<div><strong>Sin agua de red:</strong> hogares sin agua de red pública (Censo 2022)</div>
			<div><strong>Déficit infra:</strong> índice compuesto de carencias en servicios básicos</div>
		</div>

		<!-- Raw values per zone -->
		<div class="dim-section">
			{#each FLOOD_CENSUS_LABELS as label, i}
				<div class="dim-row">
					<div class="dim-label">{label}</div>
					<div class="dim-bars-container">
						{#each zoneCensusData as zd, zi}
							{@const raw = zd.rawValues[i] ?? 0}
							{@const maxRaw = Math.max(...zoneCensusData.map(z => z.rawValues[i] ?? 0), 0.01)}
							<div class="dim-bar-track">
								<div class="dim-bar-fill" style:width="{(raw / maxRaw) * 100}%"
									style:background={zones.find(z => z.id === zd.zoneId)?.color ?? '#60a5fa'}></div>
							</div>
						{/each}
					</div>
					<div class="dim-values">
						{#each zoneCensusData as zd}
							<span class="dim-val">{(zd.rawValues[i] ?? 0).toFixed(1)}</span>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Legend -->
	<div class="flood-legend">
		<div class="legend-bar"></div>
		<div class="legend-labels">
			<span>{i18n.t('analysis.flood.riskLow')}</span>
			<span>{i18n.t('analysis.flood.riskMedium')}</span>
			<span>{i18n.t('analysis.flood.riskHigh')}</span>
		</div>
	</div>
</div>

<style>
	.zone-comparison { font-size: 11px; }
	.zone-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
	.zone-title { font-size: 12px; font-weight: 600; color: #e2e8f0; }
	.zone-clear-btn { font-size: 9px; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.06); border: 1px solid #334155; color: #d4d4d4; cursor: pointer; transition: all 0.15s; }
	.zone-clear-btn:hover { border-color: #ef4444; color: #ef4444; }
	.zone-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
	.zone-chip { display: flex; align-items: center; gap: 4px; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.06); border: 1px solid #334155; font-size: 10px; color: #e2e8f0; }
	.zone-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
	.zone-dot-sm { display: inline-block; width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
	.zone-label { font-weight: 500; }
	.zone-remove { background: none; border: none; color: #a3a3a3; cursor: pointer; font-size: 9px; padding: 0 2px; line-height: 1; }
	.zone-remove:hover { color: #ef4444; }
	.zone-table { margin: 8px 0; }
	.zone-table-header { display: flex; gap: 4px; padding-bottom: 3px; border-bottom: 1px solid #1e293b; margin-bottom: 3px; }
	.zone-table-header .zt-col { font-size: 9px; font-weight: 600; color: #a3a3a3; text-transform: uppercase; }
	.zone-table-row { display: flex; gap: 4px; padding: 2px 0; }
	.zt-col { flex: 1; }
	.zt-zone { flex: 0.6; display: flex; align-items: center; gap: 4px; }
	.zt-num { text-align: right; color: #cbd5e1; font-size: 10px; }
	.section-title { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #a3a3a3; border-bottom: 1px solid #1e293b; padding-bottom: 2px; margin: 8px 0 4px; }
	.loading { color: #a3a3a3; font-size: 10px; padding: 8px 0; }
	.petal-note { font-size: 8px; color: #737373; text-align: center; margin: 0 0 4px; }
	.flood-scores { margin: 4px 0 8px; }
	.flood-zone-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
	.flood-zone-label { font-size: 10px; font-weight: 600; color: #e2e8f0; width: 16px; }
	.score-track { flex: 1; height: 6px; background: rgba(100,116,139,0.2); border-radius: 3px; overflow: hidden; }
	.score-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
	.flood-zone-val { font-size: 11px; font-weight: 700; min-width: 28px; text-align: right; }
	.dim-section { margin: 8px 0; }
	.dim-row { display: flex; align-items: flex-start; gap: 4px; margin-bottom: 4px; }
	.dim-label { width: 80px; flex-shrink: 0; color: #d4d4d4; font-size: 9px; text-align: right; padding-top: 1px; }
	.dim-bars-container { flex: 1; display: flex; flex-direction: column; gap: 2px; }
	.dim-bar-track { height: 5px; background: #1e293b; border-radius: 3px; overflow: hidden; }
	.dim-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s ease; min-width: 2px; }
	.dim-values { display: flex; flex-direction: column; align-items: flex-end; gap: 0; width: 36px; flex-shrink: 0; }
	.dim-val { font-size: 8px; font-weight: 600; line-height: 7px; color: #cbd5e1; }
	.flood-legend { margin: 8px 0; }
	.legend-bar { height: 6px; border-radius: 3px; background: linear-gradient(to right, #0d1b2a, #1b3a5f, #2a6f97, #eab308, #f97316, #dc2626, #7f1d1d); }
	.legend-labels { display: flex; justify-content: space-between; font-size: 8px; color: #a3a3a3; margin-top: 2px; }
	.petal-defs { margin-top: 6px; font-size: 8px; color: #a3a3a3; line-height: 1.5; }
	.petal-defs div { margin-bottom: 1px; }
	.petal-defs strong { color: #cbd5e1; }
</style>
