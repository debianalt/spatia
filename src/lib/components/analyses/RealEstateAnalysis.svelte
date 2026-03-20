<script lang="ts">
	import { onMount } from 'svelte';
	import { getParquetUrl } from '$lib/config';
	import { query, isReady } from '$lib/stores/duckdb';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		lensStore,
		mapStore,
		onRemoveRadio,
	}: {
		lensStore: LensStore;
		mapStore: MapStore;
		onRemoveRadio: (redcode: string) => void;
	} = $props();

	// Data state
	let loading = $state(true);
	let allData: Map<string, Record<string, any>> = $state(new Map());
	let deptSummary: Array<{ dpto: string; n: number; median: number }> = $state([]);
	let totalListings = $state(0);
	let provincialMedian = $state(0);

	// Selected radio from mapStore
	const selectedRedcode = $derived(
		mapStore.selectedRadios.size === 1
			? [...mapStore.selectedRadios.keys()][0]
			: null
	);
	const radioData = $derived(
		selectedRedcode ? allData.get(selectedRedcode) ?? null : null
	);

	onMount(() => {
		loadData();
	});

	async function loadData() {
		if (!isReady()) {
			loading = false;
			return;
		}
		try {
			const url = getParquetUrl('real_estate_by_radio');
			const result = await query(`SELECT * FROM '${url}'`);
			const map = new Map<string, Record<string, any>>();
			const depts = new Map<string, { n: number; prices: number[] }>();
			let total = 0;
			const allPrices: number[] = [];

			for (let i = 0; i < result.numRows; i++) {
				const row = result.get(i)!.toJSON() as Record<string, any>;
				map.set(row.redcode, row);
				total += row.n_listings ?? 0;
				if (row.median_usd_m2 != null && row.median_usd_m2 > 0) {
					allPrices.push(row.median_usd_m2);
				}

				const dpto = row.dpto ?? 'Desconocido';
				const d = depts.get(dpto) ?? { n: 0, prices: [] };
				d.n += row.n_listings ?? 0;
				if (row.median_usd_m2 != null && row.median_usd_m2 > 0) {
					d.prices.push(row.median_usd_m2);
				}
				depts.set(dpto, d);
			}

			allData = map;
			totalListings = total;

			// Provincial median
			allPrices.sort((a, b) => a - b);
			provincialMedian = allPrices.length > 0
				? allPrices[Math.floor(allPrices.length / 2)]
				: 0;

			// Department summary
			deptSummary = [...depts.entries()]
				.map(([dpto, d]) => {
					d.prices.sort((a, b) => a - b);
					return {
						dpto,
						n: d.n,
						median: d.prices.length > 0
							? d.prices[Math.floor(d.prices.length / 2)]
							: 0,
					};
				})
				.sort((a, b) => b.n - a.n)
				.slice(0, 8);
		} catch (e) {
			console.warn('Failed to load real estate data:', e);
		} finally {
			loading = false;
		}
	}

	function fmt(n: number | null | undefined): string {
		if (n == null) return '-';
		return n.toLocaleString('es-AR', { maximumFractionDigits: 0 });
	}

	function fmtUsd(n: number | null | undefined): string {
		if (n == null || n === 0) return '-';
		return `$${n.toLocaleString('es-AR', { maximumFractionDigits: 0 })}`;
	}

	function fmtPct(n: number | null | undefined): string {
		if (n == null) return '-';
		return `${(n * 100).toFixed(0)}%`;
	}

	// Export data for choropleth (used by parent)
	export function getChoroplethEntries(): Array<{ redcode: string; value: number }> {
		const entries: Array<{ redcode: string; value: number }> = [];
		for (const [redcode, row] of allData) {
			const val = row.median_usd_m2;
			if (val != null && val > 0) {
				entries.push({ redcode, value: val });
			}
		}
		return entries;
	}

	export function isLoaded(): boolean {
		return !loading && allData.size > 0;
	}
</script>

{#if loading}
	<div class="loading">{i18n.t('analysis.loading')}</div>
{:else if selectedRedcode && radioData}
	<!-- Radio detail view -->
	<div class="radio-detail">
		<div class="detail-header">
			<div>
				<div class="detail-redcode">{selectedRedcode}</div>
				<div class="detail-dpto">{radioData.dpto}</div>
			</div>
			<button class="detail-close" onclick={() => onRemoveRadio(selectedRedcode)}>x</button>
		</div>

		<div class="stat-grid">
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.re.medianPrice')}</div>
				<div class="stat-value price">{fmtUsd(radioData.median_usd_m2)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.re.medianTotal')}</div>
				<div class="stat-value">{fmtUsd(radioData.median_usd_total)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.re.listings')}</div>
				<div class="stat-value">{fmt(radioData.n_listings)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.re.avgArea')}</div>
				<div class="stat-value">{fmt(radioData.avg_area_m2)} m2</div>
			</div>
		</div>

		<!-- Property types -->
		{#if radioData.pct_casas != null || radioData.pct_dptos != null || radioData.pct_lotes != null}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.re.propertyTypes')}</div>
				<div class="type-bars">
					{#if radioData.pct_casas > 0}
						<div class="type-row">
							<span class="type-label">{i18n.t('analysis.re.houses')}</span>
							<div class="type-bar-bg">
								<div class="type-bar" style:width="{(radioData.pct_casas * 100)}%" style:background="#f59e0b"></div>
							</div>
							<span class="type-pct">{fmtPct(radioData.pct_casas)}</span>
						</div>
					{/if}
					{#if radioData.pct_dptos > 0}
						<div class="type-row">
							<span class="type-label">{i18n.t('analysis.re.apartments')}</span>
							<div class="type-bar-bg">
								<div class="type-bar" style:width="{(radioData.pct_dptos * 100)}%" style:background="#3b82f6"></div>
							</div>
							<span class="type-pct">{fmtPct(radioData.pct_dptos)}</span>
						</div>
					{/if}
					{#if radioData.pct_lotes > 0}
						<div class="type-row">
							<span class="type-label">{i18n.t('analysis.re.lots')}</span>
							<div class="type-bar-bg">
								<div class="type-bar" style:width="{(radioData.pct_lotes * 100)}%" style:background="#22c55e"></div>
							</div>
							<span class="type-pct">{fmtPct(radioData.pct_lotes)}</span>
						</div>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Comparison vs department -->
		{#if radioData.price_vs_dept_median != null}
			{@const ratio = radioData.price_vs_dept_median}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.re.vsMedian')}</div>
				<div class="vs-indicator" class:above={ratio > 1} class:below={ratio < 1}>
					{#if ratio > 1}
						<span class="vs-arrow">+{((ratio - 1) * 100).toFixed(0)}%</span>
						<span class="vs-text">sobre la mediana de {radioData.dpto}</span>
					{:else if ratio < 1}
						<span class="vs-arrow">-{((1 - ratio) * 100).toFixed(0)}%</span>
						<span class="vs-text">bajo la mediana de {radioData.dpto}</span>
					{:else}
						<span class="vs-text">igual a la mediana de {radioData.dpto}</span>
					{/if}
				</div>
			</div>
		{/if}
	</div>
{:else}
	<!-- Provincial summary -->
	<div class="provincial-summary">
		<div class="summary-stats">
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.re.listings')}</div>
				<div class="stat-value">{fmt(totalListings)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.re.medianPrice')}</div>
				<div class="stat-value price">{fmtUsd(provincialMedian)}</div>
			</div>
		</div>

		{#if deptSummary.length > 0}
			{@const maxN = deptSummary[0].n}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.re.topDepts')}</div>
				{#each deptSummary as dept}
					<div class="dept-row">
						<div class="dept-top">
							<span class="dept-name">{dept.dpto}</span>
							<span class="dept-price">{fmtUsd(dept.median)}/m2</span>
						</div>
						<div class="dept-bar-bg">
							<div class="dept-bar" style:width="{(dept.n / maxN) * 100}%"></div>
						</div>
						<span class="dept-count">{fmt(dept.n)} avisos</span>
					</div>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
	.loading {
		color: #64748b;
		font-size: 10px;
		padding: 12px 0;
	}
	.stat-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
		margin-bottom: 10px;
	}
	.stat-item {
		background: rgba(255,255,255,0.03);
		border-radius: 6px;
		padding: 6px 8px;
	}
	.stat-label {
		font-size: 8px;
		color: #64748b;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		margin-bottom: 2px;
	}
	.stat-value {
		font-size: 13px;
		font-weight: 600;
		color: #e2e8f0;
	}
	.stat-value.price {
		color: #f59e0b;
	}
	.section {
		margin-bottom: 8px;
	}
	.section-title {
		font-size: 9px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #64748b;
		border-bottom: 1px solid #1e293b;
		padding-bottom: 2px;
		margin-bottom: 4px;
	}

	/* Property type bars */
	.type-bars {
		display: flex;
		flex-direction: column;
		gap: 3px;
	}
	.type-row {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.type-label {
		font-size: 9px;
		color: #94a3b8;
		width: 70px;
		flex-shrink: 0;
	}
	.type-bar-bg {
		flex: 1;
		height: 6px;
		background: rgba(255,255,255,0.06);
		border-radius: 3px;
		overflow: hidden;
	}
	.type-bar {
		height: 100%;
		border-radius: 3px;
		transition: width 0.3s ease;
	}
	.type-pct {
		font-size: 9px;
		font-weight: 600;
		color: #e2e8f0;
		width: 30px;
		text-align: right;
	}

	/* vs department median */
	.vs-indicator {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 4px 8px;
		border-radius: 6px;
		font-size: 10px;
	}
	.vs-indicator.above {
		background: rgba(239,68,68,0.1);
	}
	.vs-indicator.below {
		background: rgba(34,197,94,0.1);
	}
	.vs-arrow {
		font-weight: 700;
		font-size: 12px;
	}
	.above .vs-arrow { color: #ef4444; }
	.below .vs-arrow { color: #22c55e; }
	.vs-text {
		color: #94a3b8;
		font-size: 9px;
	}

	/* Radio detail */
	.radio-detail {
		font-size: 11px;
	}
	.detail-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 8px;
	}
	.detail-redcode {
		font-weight: 600;
		color: #e0e0e0;
		font-size: 12px;
	}
	.detail-dpto {
		color: #64748b;
		font-size: 10px;
	}
	.detail-close {
		background: none;
		border: none;
		color: #64748b;
		font-size: 14px;
		cursor: pointer;
		padding: 0;
		line-height: 1;
	}
	.detail-close:hover { color: #e0e0e0; }

	/* Provincial summary */
	.provincial-summary {
		font-size: 11px;
	}
	.summary-stats {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
		margin-bottom: 10px;
	}
	.dept-row {
		margin-bottom: 4px;
	}
	.dept-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.dept-name {
		font-size: 9px;
		color: #cbd5e1;
		font-weight: 500;
	}
	.dept-price {
		font-size: 9px;
		color: #f59e0b;
		font-weight: 600;
	}
	.dept-bar-bg {
		height: 3px;
		background: rgba(255,255,255,0.06);
		border-radius: 2px;
		overflow: hidden;
		margin: 2px 0;
	}
	.dept-bar {
		height: 100%;
		border-radius: 2px;
		background: #f59e0b;
		transition: width 0.3s ease;
	}
	.dept-count {
		font-size: 8px;
		color: #64748b;
	}
</style>
