<script lang="ts">
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import { DATA_FRESHNESS, PARQUETS } from '$lib/config';
	import { initDuckDB, query } from '$lib/stores/duckdb';
	import PetalChart from '$lib/components/PetalChart.svelte';
	import deptSummaryData from '$lib/data/flood_dept_summary.json';

	let {
		lensStore,
		mapStore,
		hexStore,
		onRemoveRadio,
		onSelectFloodDpto,
		onSelectFloodCatastroDpto,
	}: {
		lensStore: LensStore;
		mapStore: MapStore;
		hexStore: HexStore;
		onRemoveRadio: (redcode: string) => void;
		onSelectFloodDpto: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
		onSelectFloodCatastroDpto?: (dpto: string, parquetKey: string, centroid: [number, number]) => void;
	} = $props();

	// Static data — no DuckDB queries, instant load
	const deptSummaries = deptSummaryData.departments.sort((a: any, b: any) => b.avg_score - a.avg_score);
	const totalHexes = deptSummaryData.province.total_hexes;
	const totalHighRisk = deptSummaryData.province.high_risk_count;
	const avgScore = deptSummaryData.province.avg_score;

	const selectedDpto = $derived(hexStore.selectedDpto);
	const selectedHex = $derived(mapStore.selectedHex);
	const selectedParcels = $derived(mapStore.selectedFloodParcels);
	const hasParcels = $derived(selectedParcels.length > 0);

	let floodCatastroDpto = $state<string | null>(null);

	// Census vulnerability petal for parcel detail (multi-parcel)
	const FLOOD_CENSUS_COLS = ['flood_frequency', 'hand_mean', 'pct_nbi', 'pct_cloacas', 'pct_agua_red', 'infra_deficit'];
	const FLOOD_CENSUS_LABELS = ['Frec. inundación', 'Altura s/ drenaje', 'NBI', 'Sin cloacas', 'Sin agua de red', 'Déficit infra'];
	const FLOOD_CENSUS_INVERT = [false, true, false, false, false, false];
	let parcelPetalLayers: Array<{ values: number[]; color: string; rawValues: number[] }> = $state([]);
	let parcelPetalProvAvg: number[] | null = $state(null);

	// Reload petal when parcels change
	$effect(() => {
		const parcels = selectedParcels;
		if (parcels.length > 0) {
			loadAllParcelPetals(parcels);
		} else {
			parcelPetalLayers = [];
		}
	});

	async function loadAllParcelPetals(parcels: typeof selectedParcels) {
		try {
			await initDuckDB();
			if (!parcelPetalProvAvg) {
				const cols = FLOOD_CENSUS_COLS.map(c =>
					`SUM(CAST(${c} AS DOUBLE) * CAST(total_personas AS DOUBLE)) / NULLIF(SUM(CAST(total_personas AS DOUBLE)), 0) as ${c}`
				).join(', ');
				const r = await query(`SELECT ${cols} FROM '${PARQUETS.radio_stats_master}' WHERE total_personas > 0`);
				if (r.numRows > 0) {
					const row = r.get(0)!.toJSON() as Record<string, any>;
					parcelPetalProvAvg = FLOOD_CENSUS_COLS.map(c => Number(row[c]) || 1);
				}
			}

			const layers: typeof parcelPetalLayers = [];
			for (const parcel of parcels) {
				const data = await loadSingleParcelPetal(parcel.h3index, parcel.color);
				if (data) layers.push(data);
			}
			parcelPetalLayers = layers;
		} catch (e) {
			console.warn('Failed to load parcel petals:', e);
		}
	}

	async function loadSingleParcelPetal(h3index: string, color: string) {
		const xwalk = await query(
			`SELECT redcode FROM '${PARQUETS.h3_radio_crosswalk}' WHERE h3index = '${h3index.replace(/'/g, "''")}' ORDER BY weight DESC LIMIT 1`
		);
		if (xwalk.numRows === 0) return null;
		const redcode = (xwalk.get(0)!.toJSON() as any).redcode;

		const cols = FLOOD_CENSUS_COLS.join(', ');
		const result = await query(
			`SELECT ${cols} FROM '${PARQUETS.radio_stats_master}' WHERE redcode = '${redcode}' LIMIT 1`
		);
		if (result.numRows === 0) return null;
		const row = result.get(0)!.toJSON() as Record<string, any>;
		const rawValues = FLOOD_CENSUS_COLS.map(c => Number(row[c]) || 0);

		const values = rawValues.map((v, i) => {
			const avg = parcelPetalProvAvg?.[i] ?? 1;
			if (avg === 0) return 50;
			let ratio = v / avg;
			if (FLOOD_CENSUS_INVERT[i]) ratio = avg / (v || 1);
			return Math.min(100, Math.max(0, ratio * 50));
		});

		return { values, color, rawValues };
	}

	function getRiskLabel(score: number): string {
		if (score >= 70) return i18n.t('analysis.flood.riskHigh');
		if (score >= 40) return i18n.t('analysis.flood.riskMedium');
		return i18n.t('analysis.flood.riskLow');
	}

	function getRiskColor(score: number): string {
		if (score >= 70) return '#dc2626';
		if (score >= 40) return '#eab308';
		return '#22c55e';
	}

	function formatPct(v: number): string {
		return `${v.toFixed(1)}%`;
	}

	function handleBackToDepts() {
		if (hasParcels && floodCatastroDpto) {
			mapStore.clearFloodParcels();
			return;
		}
		if (floodCatastroDpto) {
			floodCatastroDpto = null;
			mapStore.clearFloodParcels();
			return;
		}
		hexStore.backToDepartments();
		mapStore.clearHexState();
	}

	function handleFloodCatastroDptoClick(dept: any) {
		floodCatastroDpto = dept.dpto;
		onSelectFloodCatastroDpto?.(dept.dpto, dept.parquetKey, dept.centroid as [number, number]);
	}
</script>

{#if hasParcels && floodCatastroDpto}
	<!-- Multi-parcel flood detail view -->
	<div class="hex-detail">
		<div class="parcel-nav">
			<button class="back-btn" onclick={handleBackToDepts}>← {floodCatastroDpto}</button>
			<button class="clear-parcel-btn" onclick={() => mapStore.clearFloodParcels()}>&#10005; Limpiar</button>
		</div>

		<!-- Parcel chips -->
		<div class="parcel-chips">
			{#each selectedParcels as parcel}
				<span class="parcel-chip">
					<span class="chip-dot" style:background={parcel.color}></span>
					<span class="chip-tipo">{parcel.tipo === 'rural' ? 'R' : 'U'}</span>
					<span class="chip-score" style:color={getRiskColor(parcel.flood_risk_score)}>{parcel.flood_risk_score.toFixed(0)}</span>
					<button class="chip-x" onclick={() => mapStore.removeFloodParcel(parcel.h3index)}>x</button>
				</span>
			{/each}
		</div>

		<!-- Score bars per parcel -->
		<div class="flood-scores">
			{#each selectedParcels as parcel}
				<div class="flood-zone-row">
					<span class="zone-dot-sm" style:background={parcel.color}></span>
					<span class="flood-zone-label">{parcel.tipo === 'rural' ? 'R' : 'U'}</span>
					<div class="score-track">
						<div class="score-fill" style:width="{parcel.flood_risk_score}%" style:background={parcel.color}></div>
					</div>
					<span class="flood-zone-val" style:color={parcel.color}>{parcel.flood_risk_score.toFixed(1)}</span>
				</div>
			{/each}
		</div>

		<!-- Detail grid for each selected parcel -->
		{#each selectedParcels as parcel}
			<div class="parcel-detail-header">
				<span class="chip-dot" style:background={parcel.color}></span>
				<span class="chip-tipo">{parcel.tipo === 'rural' ? 'Rural' : 'Urbana'}</span>
				{#if parcel.area_m2 > 0}<span class="chip-area">· {parcel.area_m2.toLocaleString('es-AR', { maximumFractionDigits: 0 })} m²</span>{/if}
			</div>
			<div class="detail-grid">
				<div class="detail-item">
					<div class="detail-label">{i18n.t('analysis.flood.jrcOccurrence')}</div>
					<div class="detail-value">{parcel.jrc_occurrence.toFixed(1)}%</div>
				</div>
				<div class="detail-item">
					<div class="detail-label">{i18n.t('analysis.flood.jrcRecurrence')}</div>
					<div class="detail-value">{parcel.jrc_recurrence.toFixed(1)}%</div>
				</div>
				<div class="detail-item">
					<div class="detail-label">{i18n.t('analysis.flood.jrcSeasonality')}</div>
					<div class="detail-value">{parcel.jrc_seasonality.toFixed(1)}</div>
				</div>
				<div class="detail-item">
					<div class="detail-label">{i18n.t('analysis.flood.currentExtent')}</div>
					<div class="detail-value">{formatPct(parcel.flood_extent_pct)}</div>
				</div>
			</div>
		{/each}

		<!-- Vulnerability petal chart (all parcels overlaid) -->
		{#if parcelPetalLayers.length > 0}
			<div class="petal-section">
				<div class="section-title">Perfil de vulnerabilidad hídrica</div>
				<p class="petal-note">Relativo al promedio provincial (50 = promedio)</p>
				<div class="petal-wrapper">
					<PetalChart layers={parcelPetalLayers} labels={FLOOD_CENSUS_LABELS} size={260} />
				</div>
			</div>
		{/if}

		<div class="source-note-box">
			<div><strong>Fuente:</strong> JRC Global Surface Water (Landsat, 1984–2021) + Sentinel-1 SAR (Copernicus, {DATA_FRESHNESS.hex_flood_risk.dataDate})</div>
		</div>
	</div>
{:else if floodCatastroDpto}
	<!-- Department selected, catastro parcels colored by flood risk -->
	<div class="summary">
		<button class="back-btn" onclick={handleBackToDepts}>← {i18n.t('analysis.flood.topDepts')}</button>
		<div class="dept-active-title">{floodCatastroDpto}</div>
		<div class="hint">{i18n.t('analysis.flood.clickHint')}</div>
		<div class="flood-legend">
			<div class="legend-title">{i18n.t('analysis.flood.riskScore')}</div>
			<div class="legend-bar"></div>
			<div class="legend-labels">
				<span>{i18n.t('analysis.flood.riskLow')}</span>
				<span>{i18n.t('analysis.flood.riskMedium')}</span>
				<span>{i18n.t('analysis.flood.riskHigh')}</span>
			</div>
		</div>
		<div class="source-note-box">
			<div><strong>Fuente:</strong> JRC Global Surface Water + Sentinel-1 SAR ({DATA_FRESHNESS.hex_flood_risk.dataDate})</div>
		</div>
	</div>
{:else if selectedHex && selectedDpto}
	<!-- Hex detail view -->
	<div class="hex-detail">
		<button class="back-btn" onclick={handleBackToDepts}>← {i18n.t('analysis.flood.topDepts')}</button>
		<div class="hex-header">
			<div class="hex-id" title={selectedHex.h3index}>
				{selectedHex.h3index.slice(0, 4)}...{selectedHex.h3index.slice(-4)}
			</div>
			<div class="risk-badge" style:background={getRiskColor(selectedHex.flood_risk_score ?? 0)}>
				{getRiskLabel(selectedHex.flood_risk_score ?? 0)}
			</div>
		</div>

		<div class="score-bar">
			<div class="score-label">{i18n.t('analysis.flood.riskScore')}</div>
			<div class="score-track">
				<div class="score-fill" style:width="{selectedHex.flood_risk_score ?? 0}%"
					style:background={getRiskColor(selectedHex.flood_risk_score ?? 0)}></div>
			</div>
			<div class="score-value" style:color={getRiskColor(selectedHex.flood_risk_score ?? 0)}>
				{(selectedHex.flood_risk_score ?? 0).toFixed(1)}
			</div>
		</div>

		<div class="detail-grid">
			<div class="detail-item">
				<div class="detail-label">{i18n.t('analysis.flood.jrcOccurrence')}</div>
				<div class="detail-value">{(selectedHex.jrc_occurrence ?? 0).toFixed(1)}%</div>
				<div class="detail-desc">{i18n.t('analysis.flood.jrcOccurrenceDesc')}</div>
			</div>
			<div class="detail-item">
				<div class="detail-label">{i18n.t('analysis.flood.jrcRecurrence')}</div>
				<div class="detail-value">{(selectedHex.jrc_recurrence ?? 0).toFixed(1)}%</div>
				<div class="detail-desc">{i18n.t('analysis.flood.jrcRecurrenceDesc')}</div>
			</div>
			<div class="detail-item">
				<div class="detail-label">{i18n.t('analysis.flood.jrcSeasonality')}</div>
				<div class="detail-value">{(selectedHex.jrc_seasonality ?? 0).toFixed(1)}</div>
				<div class="detail-desc">{i18n.t('analysis.flood.jrcSeasonalityDesc')}</div>
			</div>
			<div class="detail-item">
				<div class="detail-label">{i18n.t('analysis.flood.currentExtent')}</div>
				<div class="detail-value">{formatPct(selectedHex.flood_extent_pct ?? 0)}</div>
				<div class="detail-desc">{i18n.t('analysis.flood.currentExtentDesc')}</div>
			</div>
		</div>

		<div class="source-note-box">
			<div><strong>Fuente:</strong> JRC Global Surface Water (Landsat, 1984–2021) + Sentinel-1 SAR (Copernicus, {DATA_FRESHNESS.hex_flood_risk.dataDate})</div>
			<div><strong>Última revisión:</strong> {DATA_FRESHNESS.hex_flood_risk.processedDate} · Imágenes SAR disponibles cada ~12 días</div>
		</div>
	</div>
{:else if selectedDpto}
	<!-- Department selected, hexes loading or loaded -->
	<div class="summary">
		<button class="back-btn" onclick={handleBackToDepts}>← {i18n.t('analysis.flood.topDepts')}</button>
		<div class="dept-active-title">{selectedDpto}</div>
		{#if hexStore.loading}
			<div class="loading">{i18n.t('analysis.loading')}</div>
		{:else}
			<div class="hint">{i18n.t('analysis.flood.clickHint')}</div>
		{/if}
		<div class="source-note-box">
			<div><strong>Fuente:</strong> JRC Global Surface Water (Landsat, 1984–2021) + Sentinel-1 SAR (Copernicus, {DATA_FRESHNESS.hex_flood_risk.dataDate})</div>
			<div><strong>Última revisión:</strong> {DATA_FRESHNESS.hex_flood_risk.processedDate} · Imágenes SAR disponibles cada ~12 días</div>
		</div>
	</div>
{:else}
	<!-- Department list (instant, from static JSON) -->
	<div class="summary">
		<div class="summary-cards">
			<div class="summary-card">
				<div class="card-value">{totalHexes.toLocaleString()}</div>
				<div class="card-label">{i18n.t('analysis.flood.totalHex')}</div>
			</div>
			<div class="summary-card">
				<div class="card-value" style="color: #eab308">{totalHighRisk.toLocaleString()}</div>
				<div class="card-label">{i18n.t('analysis.flood.highRecurrence')}</div>
			</div>
			<div class="summary-card">
				<div class="card-value">{avgScore.toFixed(1)}</div>
				<div class="card-label">{i18n.t('analysis.flood.avgScore')}</div>
			</div>
		</div>

		<div class="dept-section">
			<div class="section-title">{i18n.t('analysis.flood.topDepts')}</div>
			{#each deptSummaries as dept}
				<button class="dept-row dept-clickable"
					onclick={() => handleFloodCatastroDptoClick(dept)}>
					<div class="dept-name">{dept.dpto}</div>
					<div class="dept-bar-wrap">
						<div class="dept-bar" style:width="{Math.min(dept.avg_score * 3, 100)}%"
							style:background={getRiskColor(dept.avg_score)}></div>
					</div>
					<div class="dept-score" style:color={getRiskColor(dept.avg_score)}>
						{dept.avg_score.toFixed(1)}
					</div>
				</button>
			{/each}
		</div>

		<details class="method-details">
			<summary class="method-summary">{i18n.t('analysis.flood.methodTitle')}</summary>
			<div class="method-body">
				<div class="method-item">
					<span class="method-term">{i18n.t('analysis.flood.jrcOccurrence')}</span>
					<p>{i18n.t('analysis.flood.methodRecurrence')}</p>
				</div>
				<div class="method-item">
					<span class="method-term">{i18n.t('analysis.flood.currentExtent')}</span>
					<p>{i18n.t('analysis.flood.methodExtent')}</p>
				</div>
				<div class="method-item">
					<span class="method-term">{i18n.t('analysis.flood.riskScore')}</span>
					<p>{i18n.t('analysis.flood.methodScore')}</p>
				</div>
			</div>
		</details>

		<div class="source-note-box">
			<div><strong>Fuente:</strong> JRC Global Surface Water (Landsat, 1984–2021) + Sentinel-1 SAR (Copernicus, {DATA_FRESHNESS.hex_flood_risk.dataDate})</div>
			<div><strong>Última revisión:</strong> {DATA_FRESHNESS.hex_flood_risk.processedDate} · Imágenes SAR disponibles cada ~12 días</div>
		</div>
	</div>
{/if}

<style>
	.loading {
		color: #d4d4d4;
		font-size: 10px;
		text-align: center;
		padding: 20px 0;
	}
	.hex-detail, .summary {
		font-size: 11px;
	}
	.hex-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 10px;
	}
	.hex-id {
		font-family: monospace;
		font-size: 10px;
		color: #d4d4d4;
	}
	.risk-badge {
		font-size: 9px;
		font-weight: 700;
		color: #000;
		padding: 2px 8px;
		border-radius: 9999px;
	}
	.score-bar {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 12px;
	}
	.score-label {
		font-size: 9px;
		color: #d4d4d4;
		white-space: nowrap;
	}
	.score-track {
		flex: 1;
		height: 6px;
		background: rgba(100,116,139,0.2);
		border-radius: 3px;
		overflow: hidden;
	}
	.score-fill {
		height: 100%;
		border-radius: 3px;
		transition: width 0.3s;
	}
	.score-value {
		font-size: 13px;
		font-weight: 700;
		min-width: 32px;
		text-align: right;
	}
	.detail-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
		margin-bottom: 10px;
	}
	.detail-item {
		background: rgba(100,116,139,0.08);
		border-radius: 6px;
		padding: 8px;
	}
	.detail-label {
		font-size: 9px;
		color: #d4d4d4;
		margin-bottom: 2px;
	}
	.detail-value {
		font-size: 14px;
		font-weight: 700;
		color: #e2e8f0;
	}
	.detail-desc {
		font-size: 8px;
		color: #a3a3a3;
		margin-top: 2px;
	}
	.summary-cards {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: 6px;
		margin-bottom: 12px;
	}
	.summary-card {
		background: rgba(100,116,139,0.08);
		border-radius: 6px;
		padding: 8px 6px;
		text-align: center;
	}
	.card-value {
		font-size: 15px;
		font-weight: 700;
		color: #e2e8f0;
	}
	.card-label {
		font-size: 8px;
		color: #d4d4d4;
		margin-top: 2px;
	}
	.dept-section {
		margin-bottom: 10px;
	}
	.section-title {
		font-size: 10px;
		font-weight: 600;
		color: #cbd5e1;
		margin-bottom: 6px;
	}
	.back-btn {
		background: none;
		border: none;
		color: #60a5fa;
		font-size: 10px;
		cursor: pointer;
		padding: 0;
		margin-bottom: 8px;
	}
	.back-btn:hover { text-decoration: underline; }
	.dept-active-title {
		font-size: 14px;
		font-weight: 700;
		color: #e2e8f0;
		margin-bottom: 8px;
	}
	.dept-row {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-bottom: 3px;
	}
	.dept-clickable {
		background: none;
		border: none;
		width: 100%;
		padding: 4px 2px;
		border-radius: 4px;
		cursor: pointer;
		transition: background 0.15s;
	}
	.dept-clickable:hover { background: rgba(96,165,250,0.1); }
	.dept-name {
		font-size: 9px;
		color: #d4d4d4;
		width: 72px;
		text-align: left;
		flex-shrink: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.dept-bar-wrap {
		flex: 1;
		height: 4px;
		background: rgba(100,116,139,0.15);
		border-radius: 2px;
		overflow: hidden;
	}
	.dept-bar {
		height: 100%;
		border-radius: 2px;
		transition: width 0.3s;
	}
	.dept-score {
		font-size: 9px;
		font-weight: 600;
		min-width: 24px;
		text-align: right;
	}
	.hint {
		font-size: 9px;
		color: #a3a3a3;
		text-align: center;
		margin-top: 8px;
	}
	.source-note-box {
		margin-top: 10px;
		padding: 8px 10px;
		background: rgba(255,255,255,0.05);
		border: 1px solid rgba(255,255,255,0.08);
		border-radius: 6px;
		font-size: 9px;
		color: #e2e8f0;
		line-height: 1.5;
	}
	.source-note-box strong {
		color: #f8fafc;
	}
	.method-details {
		margin-top: 10px;
		border: 1px solid rgba(100,116,139,0.15);
		border-radius: 6px;
		overflow: hidden;
	}
	.method-summary {
		font-size: 9px;
		font-weight: 600;
		color: #d4d4d4;
		padding: 6px 8px;
		cursor: pointer;
		user-select: none;
		list-style: none;
		display: flex;
		align-items: center;
		gap: 4px;
	}
	.method-summary::before {
		content: '\25B8';
		font-size: 8px;
		transition: transform 0.15s;
	}
	.method-details[open] > .method-summary::before {
		transform: rotate(90deg);
	}
	.method-summary::-webkit-details-marker {
		display: none;
	}
	.method-body {
		padding: 4px 8px 8px;
	}
	.method-item {
		margin-bottom: 6px;
	}
	.method-item:last-child {
		margin-bottom: 0;
	}
	.method-term {
		font-size: 9px;
		font-weight: 600;
		color: #cbd5e1;
	}
	.method-item p {
		font-size: 8.5px;
		color: #a3a3a3;
		margin: 2px 0 0;
		line-height: 1.4;
	}
	.parcel-nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
	.parcel-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
	.parcel-chip { display: inline-flex; align-items: center; gap: 3px; background: rgba(255,255,255,0.05); border-radius: 12px; padding: 2px 6px 2px 4px; font-size: 9px; }
	.chip-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
	.chip-tipo { font-weight: 600; color: #e2e8f0; }
	.chip-score { font-weight: 700; font-family: monospace; }
	.chip-x { background: none; border: none; color: #737373; cursor: pointer; font-size: 10px; padding: 0 2px; line-height: 1; }
	.chip-x:hover { color: #ef4444; }
	.parcel-detail-header { display: flex; align-items: center; gap: 4px; font-size: 10px; margin: 6px 0 3px; padding-top: 4px; border-top: 1px solid #1e293b; }
	.chip-area { color: #a3a3a3; font-size: 9px; }
	.flood-scores { margin: 4px 0 8px; }
	.flood-zone-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
	.zone-dot-sm { display: inline-block; width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
	.flood-zone-label { font-size: 10px; font-weight: 600; color: #e2e8f0; width: 16px; }
	.flood-zone-val { font-size: 11px; font-weight: 700; min-width: 28px; text-align: right; }
	.clear-parcel-btn { font-size: 9px; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.06); border: 1px solid #334155; color: #d4d4d4; cursor: pointer; transition: all 0.15s; }
	.clear-parcel-btn:hover { border-color: #ef4444; color: #ef4444; }
	.petal-section { margin: 10px 0; }
	.section-title { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #a3a3a3; border-bottom: 1px solid #1e293b; padding-bottom: 2px; margin-bottom: 4px; }
	.petal-note { font-size: 8px; color: #737373; text-align: center; margin: 0 0 4px; }
	.petal-wrapper { display: flex; justify-content: center; }
	.raw-values { margin-top: 4px; }
	.raw-row { display: flex; justify-content: space-between; padding: 1px 0; font-size: 9px; }
	.raw-label { color: #a3a3a3; }
	.raw-val { color: #e2e8f0; font-weight: 600; font-family: monospace; }
	.flood-legend {
		margin: 12px 0;
	}
	.legend-title {
		font-size: 9px;
		font-weight: 600;
		color: #d4d4d4;
		margin-bottom: 4px;
	}
	.legend-bar {
		height: 8px;
		border-radius: 4px;
		background: linear-gradient(to right, #0d1b2a, #1b3a5f, #2a6f97, #eab308, #f97316, #dc2626, #7f1d1d);
	}
	.legend-labels {
		display: flex;
		justify-content: space-between;
		font-size: 8px;
		color: #a3a3a3;
		margin-top: 2px;
	}
</style>
