<script lang="ts">
	export type ChartDataSet = {
		title: string;
		type: 'bar' | 'ranking';
		data: Array<{ label: string; value: number }>;
		unit?: string;
	};

	let { chart }: { chart: ChartDataSet } = $props();

	function fmt(v: number): string {
		if (Math.abs(v) < 1) return v.toFixed(3);
		if (Math.abs(v) < 100) return v.toFixed(1);
		return v.toLocaleString('en-US', { maximumFractionDigits: 0 });
	}

	const maxVal = $derived(Math.max(...chart.data.map((d) => Math.abs(d.value)), 0.001));
</script>

<div class="chart-container">
	<div class="chart-title">{chart.title}{chart.unit ? ` (${chart.unit})` : ''}</div>
	{#each chart.data as item}
		<div class="chart-row">
			<div class="chart-label" title={item.label}>{item.label}</div>
			<div class="chart-bar-container">
				<div
					class="chart-bar"
					style="width: {Math.max((Math.abs(item.value) / maxVal) * 100, 3)}%;"
				></div>
				<span class="chart-value">{fmt(item.value)}</span>
			</div>
		</div>
	{/each}
</div>

<style>
	.chart-container {
		margin: 6px 0;
		font-size: 11px;
	}
	.chart-title {
		font-size: 9px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #64748b;
		border-bottom: 1px solid #1e293b;
		padding-bottom: 2px;
		margin-bottom: 4px;
	}
	.chart-row {
		margin-bottom: 2px;
	}
	.chart-label {
		color: #94a3b8;
		font-size: 10px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 100%;
	}
	.chart-bar-container {
		display: flex;
		align-items: center;
		gap: 4px;
		height: 6px;
	}
	.chart-bar {
		height: 4px;
		border-radius: 1px;
		background: #60a5fa;
		min-width: 3px;
		transition: width 0.3s ease;
	}
	.chart-value {
		color: #cbd5e1;
		font-size: 9px;
		white-space: nowrap;
	}
</style>
