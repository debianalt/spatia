<script lang="ts">
	import type { RadioData } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		radios,
		onRemoveRadio
	}: {
		radios: Map<string, RadioData>;
		onRemoveRadio: (redcode: string) => void;
	} = $props();

	const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 0 });

	type VarDef = { key: string; label: string; getValue: (rc: string, d: RadioData) => number | null; unit?: string };

	const absoluteVars: VarDef[] = [
		{ key: 'population', label: 'label.population', getValue: (_, d) => {
			const v = d.enriched?.total_personas ?? d.census?.total_personas ?? d.census?.radio_personas;
			return v != null ? parseInt(v) || null : null;
		}},
		{ key: 'households', label: 'label.households', getValue: (_, d) => {
			const v = d.enriched?.total_hogares ?? d.census?.radio_hogares;
			return v != null ? parseInt(v) || null : null;
		}},
	];

	const rateVars: VarDef[] = [
		{ key: 'masculinity', label: 'label.masculinityRate', getValue: (_, d) => {
			const v = d.enriched?.varones; const t = d.enriched?.total_personas;
			return v != null && t != null && t > 0 ? (parseFloat(v) / parseFloat(t)) * 100 : null;
		}, unit: '%' },
		{ key: 'employment', label: 'label.employmentRate', getValue: (_, d) =>
			d.enriched?.tasa_empleo != null ? parseFloat(d.enriched.tasa_empleo) : null, unit: '%' },
		{ key: 'nbi', label: 'label.ubn', getValue: (_, d) =>
			d.enriched?.pct_nbi != null ? parseFloat(d.enriched.pct_nbi) : null, unit: '%' },
	];

	function getBarData(vars: VarDef[]) {
		const entries = [...radios.entries()];
		return vars.map(v => {
			const values = entries.map(([rc, d]) => ({
				redcode: rc,
				color: d.color,
				value: v.getValue(rc, d)
			}));
			const hasAny = values.some(x => x.value != null);
			const maxVal = Math.max(...values.map(x => x.value ?? 0), 1);
			return { ...v, values, hasAny, maxVal };
		}).filter(v => v.hasAny);
	}

	function shortCode(rc: string): string {
		return rc.length > 5 ? '...' + rc.slice(-4) : rc;
	}
</script>

<div class="chart-root">
	<!-- Radio chips -->
	<div class="flex flex-wrap gap-1 mb-2">
		{#each [...radios.entries()] as [rc, data]}
			<button
				class="chip"
				style="border-color: {data.color}; color: {data.color};"
				onclick={() => onRemoveRadio(rc)}
				title={i18n.t('side.deselect')}>
				<span class="chip-dot" style="background: {data.color};"></span>
				{shortCode(rc)}
				<span class="chip-x">&times;</span>
			</button>
		{/each}
	</div>

	<!-- Absolute values -->
	{#each getBarData(absoluteVars) as row, i}
		{#if i === 0}
			<div class="section-label">{i18n.t('chart.absolute')}</div>
		{/if}
		<div class="var-row">
			<div class="var-label">{i18n.t(row.label)}</div>
			<div class="bars">
				{#each row.values as bar}
					{#if bar.value != null}
						<div class="bar-wrap" title="{bar.redcode}: {fmt(bar.value)}">
							<div class="bar" style="width: {Math.max((bar.value / row.maxVal) * 100, 4)}%; background: {bar.color};"></div>
							<span class="bar-val">{fmt(bar.value)}</span>
						</div>
					{/if}
				{/each}
			</div>
		</div>
	{/each}

	<!-- Rate values -->
	{#each getBarData(rateVars) as row, i}
		{#if i === 0}
			<div class="section-label mt">{i18n.t('chart.rates')}</div>
		{/if}
		<div class="var-row">
			<div class="var-label">{i18n.t(row.label)}</div>
			<div class="bars">
				{#each row.values as bar}
					{#if bar.value != null}
						<div class="bar-wrap" title="{bar.redcode}: {bar.value.toFixed(1)}{row.unit ?? ''}">
							<div class="bar" style="width: {Math.max((bar.value / row.maxVal) * 100, 4)}%; background: {bar.color};"></div>
							<span class="bar-val">{bar.value.toFixed(1)}{row.unit ?? ''}</span>
						</div>
					{/if}
				{/each}
			</div>
		</div>
	{/each}
</div>

<style>
	.chart-root { font-size: 11px; line-height: 1.3; }
	.chip {
		display: inline-flex; align-items: center; gap: 3px;
		padding: 1px 6px; border-radius: 9999px;
		border: 1px solid; background: transparent;
		font-size: 10px; cursor: pointer; transition: opacity 0.15s;
	}
	.chip:hover { opacity: 0.7; }
	.chip-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
	.chip-x { font-size: 12px; margin-left: 1px; }
	.section-label {
		font-size: 9px; font-weight: 600; text-transform: uppercase;
		letter-spacing: 0.05em; color: #64748b;
		border-bottom: 1px solid #1e293b; padding-bottom: 2px; margin-bottom: 3px;
	}
	.section-label.mt { margin-top: 6px; }
	.var-row { margin-bottom: 3px; }
	.var-label { color: #94a3b8; font-size: 10px; margin-bottom: 0; }
	.bars { display: flex; flex-direction: column; gap: 1px; }
	.bar-wrap {
		display: flex; align-items: center; gap: 3px; height: 5px;
	}
	.bar {
		height: 3px; border-radius: 1px; min-width: 3px;
		transition: width 0.3s ease;
	}
	.bar-val { color: #cbd5e1; font-size: 9px; white-space: nowrap; }
</style>
