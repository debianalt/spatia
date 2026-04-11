<script lang="ts">
	import type { RadioData } from '$lib/stores/map.svelte';
	import { PETAL_VARS, normalizeValues, getProvincialAvg } from '$lib/utils/petal';
	import PetalChart from './PetalChart.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		radios,
		onRemoveRadio,
		onClearRadios,
		onDownloadRadioCsv,
		onDownloadRadioGeoJson,
		onDownloadRadiosSummary
	}: {
		radios: Map<string, RadioData>;
		onRemoveRadio: (redcode: string) => void;
		onClearRadios: () => void;
		onDownloadRadioCsv?: (redcode: string) => void;
		onDownloadRadioGeoJson?: (redcode: string, properties: Record<string, any>) => void;
		onDownloadRadiosSummary?: () => void;
	} = $props();

	const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 0 });
	const fmt1 = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 1 });

	let provAvg: number[] | null = $state(null);

	// Load provincial averages once enriched data arrives
	$effect(() => {
		const hasEnriched = [...radios.values()].some(d => d.enriched != null);
		if (hasEnriched && !provAvg) {
			getProvincialAvg().then(avg => { provAvg = avg; }).catch(() => {});
		}
	});

	type RadioEntry = { redcode: string; color: string; data: RadioData; rawValues: number[]; normalizedValues: number[]; population: number; areaKm2: number };

	const entries = $derived.by((): RadioEntry[] => {
		if (!provAvg) return [];
		return [...radios.entries()]
			.filter(([, d]) => d.enriched != null)
			.map(([rc, d]) => {
				const e = d.enriched!;
				const rawValues = PETAL_VARS.map(v => {
					const val = e[v.col];
					return val != null ? parseFloat(val) : 0;
				});
				const normalizedValues = normalizeValues(rawValues, provAvg!);
				const population = parseInt(e.total_personas ?? d.census?.total_personas ?? '0') || 0;
				const areaKm2 = parseFloat(e.area_km2 ?? d.census?.area_km2 ?? '0') || 0;
				return { redcode: rc, color: d.color, data: d, rawValues, normalizedValues, population, areaKm2 };
			});
	});

	const petalLayers = $derived(entries.map(e => ({ values: e.normalizedValues, color: e.color })));
	const petalLabels = $derived(PETAL_VARS.map(v => i18n.t(v.labelKey)));

	function shortCode(rc: string): string {
		return rc.length > 5 ? '...' + rc.slice(-4) : rc;
	}
</script>

<div class="chart-root">
	<div class="radio-header">
		<span class="radio-title">{i18n.t('side.radios')}</span>
		<button class="radio-clear-btn" onclick={onClearRadios}>
			&#10005; {i18n.t('side.clearRadios')}
		</button>
	</div>

	<!-- Radio chips -->
	<div class="flex flex-wrap gap-1 mb-2">
		{#each [...radios.entries()] as [rc, data]}
			<button
				class="chip"
				style="border-color: {data.color}; color: #e2e8f0;"
				onclick={() => onRemoveRadio(rc)}
				title={i18n.t('side.deselect')}>
				<span class="chip-dot" style="background: {data.color};"></span>
				{shortCode(rc)}
				<span class="chip-x">&times;</span>
			</button>
		{/each}
	</div>

	<!-- Petal chart (normalized: 50 = provincial avg) -->
	{#if petalLayers.length > 0}
		<p class="ref-note">{i18n.t('zone.petalNote')}</p>
		<PetalChart layers={petalLayers} labels={petalLabels} size={300} />
	{/if}

	<!-- Summary table -->
	{#if entries.length > 0}
		<div class="r-table">
			<div class="r-table-header">
				<span class="rt-col rt-zone">Radio</span>
				<span class="rt-col rt-num">Población</span>
				<span class="rt-col rt-num">km²</span>
				<span class="rt-col rt-actions"></span>
			</div>
			{#each entries as entry}
				<div class="r-table-row">
					<span class="rt-col rt-zone">
						<span class="r-dot-sm" style:background={entry.color}></span>
						{shortCode(entry.redcode)}
					</span>
					<span class="rt-col rt-num">{fmt(entry.population)}</span>
					<span class="rt-col rt-num">{fmt1(entry.areaKm2)}</span>
					<span class="rt-col rt-actions">
						<button
							class="r-dl-btn"
							title="Datos del radio (CSV)"
							onclick={() => onDownloadRadioCsv?.(entry.redcode)}
							disabled={!onDownloadRadioCsv}
						>csv</button>
						<button
							class="r-dl-btn"
							title="Polígono del radio (GeoJSON)"
							onclick={() => onDownloadRadioGeoJson?.(entry.redcode, entry.data.enriched ?? {})}
							disabled={!onDownloadRadioGeoJson}
						>geo</button>
					</span>
				</div>
			{/each}
		</div>

		{#if onDownloadRadiosSummary}
			<div class="r-download-row">
				<button class="r-download-btn" onclick={() => onDownloadRadiosSummary?.()}>
					↓ Resumen comparativo (CSV)
				</button>
			</div>
		{/if}
	{/if}

	<div class="sources">
		<span class="sources-title">{i18n.t('source.title')}</span>
		<span>{i18n.t('source.census')}</span>
		<span>{i18n.t('source.buildings')}</span>
		<span>{i18n.t('source.basemap')}</span>
		<span>{i18n.t('source.terrain')}</span>
	</div>
</div>

<style>
	.chart-root { font-size: 11px; line-height: 1.3; }
	.radio-header {
		display: flex; justify-content: space-between; align-items: center;
		margin-bottom: 6px;
	}
	.radio-title { font-size: 10px; font-weight: 600; color: #e2e8f0; }
	.radio-clear-btn {
		font-size: 9px; padding: 2px 6px; border-radius: 4px;
		background: rgba(255,255,255,0.06); border: 1px solid #334155;
		color: #d4d4d4; cursor: pointer; transition: all 0.15s;
	}
	.radio-clear-btn:hover { border-color: #ef4444; color: #ef4444; }
	.chip {
		display: inline-flex; align-items: center; gap: 3px;
		padding: 1px 6px; border-radius: 9999px;
		border: 1px solid; background: transparent;
		font-size: 10px; cursor: pointer; transition: opacity 0.15s;
	}
	.chip:hover { opacity: 0.7; }
	.chip-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
	.chip-x { font-size: 12px; margin-left: 1px; }

	.pop-row {
		display: flex; align-items: center; gap: 4px;
		font-size: 10px; color: #cbd5e1; margin-bottom: 2px;
	}
	.pop-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
	.pop-code { color: #d4d4d4; font-family: monospace; }
	.pop-val { font-weight: 600; }

	.ref-note {
		font-size: 8px; color: rgba(255,255,255,0.45);
		text-align: center; margin: 4px 0 0;
	}

	.r-table { margin: 8px 0; }
	.r-table-header {
		display: flex; gap: 4px;
		padding-bottom: 3px;
		border-bottom: 1px solid #1e293b;
		margin-bottom: 3px;
	}
	.r-table-header .rt-col {
		font-size: 9px; font-weight: 600;
		color: #a3a3a3; text-transform: uppercase;
	}
	.r-table-row {
		display: flex; gap: 4px; padding: 2px 0;
	}
	.rt-col { flex: 1; }
	.rt-zone { flex: 0.9; display: flex; align-items: center; gap: 4px; font-family: monospace; font-size: 10px; color: #d4d4d4; }
	.rt-num { text-align: right; color: #cbd5e1; font-size: 10px; font-variant-numeric: tabular-nums; }
	.rt-actions { flex: 0.8; display: flex; gap: 3px; justify-content: flex-end; }
	.r-dot-sm {
		display: inline-block; width: 6px; height: 6px;
		border-radius: 50%; flex-shrink: 0;
	}
	.r-dl-btn {
		background: rgba(255,255,255,0.04);
		border: 1px solid rgba(255,255,255,0.1);
		color: #94a3b8; font-size: 8px;
		padding: 1px 4px; border-radius: 3px;
		cursor: pointer; font-family: inherit;
		transition: all 0.15s;
	}
	.r-dl-btn:hover:not(:disabled) {
		background: rgba(96,165,250,0.15);
		border-color: rgba(96,165,250,0.4);
		color: #60a5fa;
	}
	.r-dl-btn:disabled { opacity: 0.4; cursor: not-allowed; }

	.r-download-row { margin-top: 6px; }
	.r-download-btn {
		display: block; width: 100%; text-align: center;
		padding: 6px 10px;
		background: rgba(59,130,246,0.15);
		border: 1px solid rgba(59,130,246,0.3);
		border-radius: 4px;
		color: #60a5fa; font-size: 9px; font-weight: 600;
		cursor: pointer; font-family: inherit;
		transition: all 0.15s;
	}
	.r-download-btn:hover {
		background: rgba(59,130,246,0.25);
		border-color: rgba(59,130,246,0.5);
	}

	.dim-section { margin: 8px 0; }
	.dim-row {
		display: flex; align-items: flex-start; gap: 4px; margin-bottom: 4px;
	}
	.dim-label {
		width: 65px; flex-shrink: 0;
		color: #d4d4d4; font-size: 9px;
		text-align: right; padding-top: 1px;
	}
	.dim-bars-container {
		flex: 1; display: flex; flex-direction: column; gap: 2px;
	}
	.dim-bar-track {
		height: 5px; background: #1e293b;
		border-radius: 3px; overflow: hidden;
	}
	.dim-bar-fill {
		height: 100%; border-radius: 3px;
		transition: width 0.3s ease; min-width: 2px;
	}
	.dim-values {
		display: flex; flex-direction: column;
		align-items: flex-end; gap: 0;
		width: 32px; flex-shrink: 0;
	}
	.dim-val {
		font-size: 8px; font-weight: 600;
		line-height: 7px; color: #cbd5e1;
	}

	.sources {
		display: flex; flex-direction: column; gap: 1px;
		margin-top: 12px; padding-top: 8px;
		border-top: 1px solid rgba(255,255,255,0.06);
		font-size: 8px; color: rgba(255,255,255,0.35); line-height: 1.4;
	}
	.sources-title {
		font-weight: 600; color: rgba(255,255,255,0.45);
		margin-bottom: 1px;
	}
</style>
