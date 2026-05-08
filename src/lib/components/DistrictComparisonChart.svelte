<script lang="ts">
	import type { DistrictData } from '$lib/stores/map.svelte';
	import PetalChart from './PetalChart.svelte';

	let {
		districts,
		onRemoveDistrict,
		onClearDistricts,
	}: {
		districts: Map<string, DistrictData>;
		onRemoveDistrict: (distrito: string) => void;
		onClearDistricts: () => void;
	} = $props();

	// 4 NBI components from CNPV 2022 — higher = more deprived (same direction as Misiones pct_nbi)
	const DISTRICT_PETAL_VARS = [
		{ col: 'pct_vivienda',     label: 'Calidad vivienda' },
		{ col: 'pct_sanitario',    label: 'Infra. sanitaria' },
		{ col: 'pct_educacion',    label: 'Acceso educación' },
		{ col: 'pct_subsistencia', label: 'Cap. subsistencia' },
	];

	const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 0 });

	type DistrictEntry = {
		distrito: string;
		color: string;
		personas: number;
		rawValues: number[];
		normalizedValues: number[];
		n_hexes: number;
		pct_nbi: number | null;
	};

	function normalizeValues(rawValues: number[], means: number[]): number[] {
		return rawValues.map((v, i) => {
			const m = means[i];
			if (!m || m === 0) return 50;
			return Math.min(100, Math.max(0, (v / m) * 50));
		});
	}

	const entries = $derived.by((): DistrictEntry[] => {
		const enriched = [...districts.entries()].filter(([, d]) => d.enriched != null);
		if (enriched.length === 0) return [];

		// Compute means across selected districts for normalization
		const means = DISTRICT_PETAL_VARS.map((v, _) => {
			const vals = enriched.map(([, d]) => {
				const val = d.enriched![v.col];
				return val != null && !isNaN(Number(val)) ? Number(val) : null;
			}).filter(x => x !== null) as number[];
			return vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : 1;
		});

		return enriched.map(([distrito, d]) => {
			const rawValues = DISTRICT_PETAL_VARS.map(v => {
				const val = d.enriched![v.col];
				return val != null && !isNaN(Number(val)) ? Number(val) : 0;
			});
			const pct_nbi_raw = d.enriched!.pct_nbi;
			return {
				distrito,
				color: d.color,
				personas: d.personas,
				rawValues,
				normalizedValues: normalizeValues(rawValues, means),
				n_hexes: Number(d.enriched!.n_hexes ?? 0),
				pct_nbi: pct_nbi_raw != null && !isNaN(Number(pct_nbi_raw)) ? Number(pct_nbi_raw) : null,
			};
		});
	});

	const petalLayers = $derived(entries.map(e => ({ values: e.normalizedValues, color: e.color })));
	const petalLabels = DISTRICT_PETAL_VARS.map(v => v.label);

	const pendingDistricts = $derived(
		[...districts.keys()].filter(d => !entries.find(e => e.distrito === d))
	);
</script>

<div class="chart-root">
	<div class="header">
		<span class="title">Distritos — Itapúa</span>
		<button class="clear-btn" onclick={onClearDistricts}>&#10005; Limpiar</button>
	</div>

	<!-- Chips -->
	<div class="flex flex-wrap gap-1 mb-2">
		{#each [...districts.entries()] as [distrito, data]}
			<button
				class="chip"
				style="border-color: {data.color}; color: #e2e8f0;"
				onclick={() => onRemoveDistrict(distrito)}
				title="Deseleccionar">
				<span class="chip-dot" style="background: {data.color};"></span>
				{distrito}
				<span class="chip-x">&times;</span>
			</button>
		{/each}
	</div>

	{#if pendingDistricts.length > 0}
		<p class="loading-note">Cargando datos...</p>
	{/if}

	<!-- Petal chart -->
	{#if petalLayers.length > 0}
		<p class="ref-note">NBI 2022 — 50 = promedio seleccionado · mayor = más privación</p>
		<PetalChart layers={petalLayers} labels={petalLabels} size={300} />
	{/if}

	<!-- Summary table -->
	{#if entries.length > 0}
		<div class="r-table">
			<div class="r-table-header">
				<span class="rt-col rt-zone">Distrito</span>
				<span class="rt-col rt-num">Personas</span>
				<span class="rt-col rt-num">NBI %</span>
			</div>
			{#each entries as entry}
				<div class="r-table-row">
					<span class="rt-col rt-zone">
						<span class="r-dot-sm" style:background={entry.color}></span>
						{entry.distrito}
					</span>
					<span class="rt-col rt-num">{fmt(entry.personas)}</span>
					<span class="rt-col rt-num">
						{#if entry.pct_nbi != null}
							{entry.pct_nbi.toFixed(1)}%
						{:else}
							—
						{/if}
					</span>
				</div>
			{/each}
		</div>
	{/if}

	<div class="sources">
		<span class="sources-title">Fuentes</span>
		<span>INE Paraguay — CNPV 2022 (NBI por distrito)</span>
		<span>Overture Maps Buildings</span>
	</div>
</div>

<style>
	.chart-root { font-size: 11px; line-height: 1.3; }
	.header {
		display: flex; justify-content: space-between; align-items: center;
		margin-bottom: 6px;
	}
	.title { font-size: 10px; font-weight: 600; color: #e2e8f0; }
	.clear-btn {
		font-size: 9px; padding: 2px 6px; border-radius: 4px;
		background: rgba(255,255,255,0.06); border: 1px solid #334155;
		color: #d4d4d4; cursor: pointer; transition: all 0.15s;
	}
	.clear-btn:hover { border-color: #ef4444; color: #ef4444; }
	.chip {
		display: inline-flex; align-items: center; gap: 3px;
		padding: 1px 6px; border-radius: 9999px;
		border: 1px solid; background: transparent;
		font-size: 10px; cursor: pointer; transition: opacity 0.15s;
	}
	.chip:hover { opacity: 0.7; }
	.chip-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
	.chip-x { font-size: 12px; margin-left: 1px; }
	.loading-note { font-size: 9px; color: #94a3b8; margin: 4px 0; }
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
	.r-table-row { display: flex; gap: 4px; padding: 2px 0; }
	.rt-col { flex: 1; }
	.rt-zone { flex: 1.4; display: flex; align-items: center; gap: 4px; font-size: 10px; color: #d4d4d4; }
	.rt-num { text-align: right; color: #cbd5e1; font-size: 10px; font-variant-numeric: tabular-nums; }
	.r-dot-sm {
		display: inline-block; width: 6px; height: 6px;
		border-radius: 50%; flex-shrink: 0;
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
