<script lang="ts">
	import { onMount } from 'svelte';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import { query, isReady } from '$lib/stores/duckdb';
	import { PARQUETS } from '$lib/config';

	let {
		lensStore,
		mapStore,
		onRemoveRadio,
	}: {
		lensStore: LensStore;
		mapStore: MapStore;
		onRemoveRadio: (redcode: string) => void;
	} = $props();

	type FloodRow = {
		h3index: string;
		jrc_occurrence: number;
		jrc_recurrence: number;
		jrc_seasonality: number;
		flood_extent_pct: number;
		flood_risk_score: number;
	};

	type DeptSummary = {
		departamento: string;
		avg_score: number;
		hex_count: number;
		high_risk_count: number;
	};

	let loading = $state(true);
	let allData: FloodRow[] = $state([]);
	let deptSummaries: DeptSummary[] = $state([]);
	let totalHighRisk = $derived(allData.filter(d => d.jrc_occurrence > 10).length);
	let avgScore = $derived(allData.length > 0 ? allData.reduce((s, d) => s + d.flood_risk_score, 0) / allData.length : 0);

	// Selected hex detail
	const selectedHex = $derived(mapStore.selectedHex);

	onMount(async () => {
		await loadData();
	});

	async function loadData() {
		if (!isReady()) { loading = false; return; }
		try {
			// Load all flood data
			const result = await query(
				`SELECT h3index, jrc_occurrence, jrc_recurrence, jrc_seasonality, flood_extent_pct, flood_risk_score
				 FROM '${PARQUETS.hex_flood_risk}'
				 WHERE flood_risk_score IS NOT NULL
				 ORDER BY flood_risk_score DESC`
			);
			const rows: FloodRow[] = [];
			for (let i = 0; i < result.numRows; i++) {
				rows.push(result.get(i)!.toJSON() as FloodRow);
			}
			allData = rows;

			// Department summary via crosswalk
			try {
				const deptResult = await query(
					`SELECT r.departamento,
					        AVG(f.flood_risk_score) as avg_score,
					        COUNT(*) as hex_count,
					        SUM(CASE WHEN f.jrc_occurrence > 10 THEN 1 ELSE 0 END) as high_risk_count
					 FROM '${PARQUETS.hex_flood_risk}' f
					 JOIN '${PARQUETS.h3_radio_crosswalk}' c ON f.h3index = c.h3index
					 JOIN '${PARQUETS.radio_stats_master}' r ON c.redcode = r.redcode
					 WHERE f.flood_risk_score IS NOT NULL AND c.redcode IS NOT NULL
					 GROUP BY r.departamento
					 ORDER BY avg_score DESC`
				);
				const depts: DeptSummary[] = [];
				for (let i = 0; i < deptResult.numRows; i++) {
					depts.push(deptResult.get(i)!.toJSON() as DeptSummary);
				}
				deptSummaries = depts;
			} catch {
				// Crosswalk may not exist yet — skip dept summaries
			}
		} catch (e) {
			console.warn('Failed to load flood risk data:', e);
		}
		loading = false;
	}

	export function getChoroplethEntries(): { h3index: string; value: number }[] {
		return allData
			.filter(d => d.flood_risk_score > 0)
			.map(d => ({ h3index: d.h3index, value: d.flood_risk_score }));
	}

	function getRiskClass(score: number): string {
		if (score >= 70) return 'high';
		if (score >= 40) return 'medium';
		return 'low';
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
</script>

{#if loading}
	<div class="loading">{i18n.t('analysis.loading')}</div>
{:else if selectedHex}
	<!-- Hex detail view -->
	<div class="hex-detail">
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

		<div class="source-note">{i18n.t('analysis.flood.source')}</div>
	</div>
{:else}
	<!-- Provincial summary view -->
	<div class="summary">
		<div class="summary-cards">
			<div class="summary-card">
				<div class="card-value">{allData.length.toLocaleString()}</div>
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

		{#if deptSummaries.length > 0}
			<div class="dept-section">
				<div class="section-title">{i18n.t('analysis.flood.topDepts')}</div>
				{#each deptSummaries.slice(0, 8) as dept}
					<div class="dept-row">
						<div class="dept-name">{dept.departamento}</div>
						<div class="dept-bar-wrap">
							<div class="dept-bar" style:width="{Math.min(dept.avg_score, 100)}%"
								style:background={getRiskColor(dept.avg_score)}></div>
						</div>
						<div class="dept-score" style:color={getRiskColor(dept.avg_score)}>
							{dept.avg_score.toFixed(1)}
						</div>
					</div>
				{/each}
			</div>
		{/if}

		<div class="hint">{i18n.t('analysis.flood.clickHint')}</div>

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

		<div class="source-note">{i18n.t('analysis.flood.source')}</div>
	</div>
{/if}

<style>
	.loading {
		color: #94a3b8;
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
		color: #94a3b8;
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
		color: #94a3b8;
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
		color: #94a3b8;
		margin-bottom: 2px;
	}
	.detail-value {
		font-size: 14px;
		font-weight: 700;
		color: #e2e8f0;
	}
	.detail-desc {
		font-size: 8px;
		color: #64748b;
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
		color: #94a3b8;
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
	.dept-row {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-bottom: 3px;
	}
	.dept-name {
		font-size: 9px;
		color: #94a3b8;
		width: 72px;
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
		color: #64748b;
		text-align: center;
		margin-top: 8px;
	}
	.source-note {
		font-size: 8px;
		color: #475569;
		margin-top: 8px;
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
		color: #94a3b8;
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
		color: #64748b;
		margin: 2px 0 0;
		line-height: 1.4;
	}
</style>
