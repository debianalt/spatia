<script lang="ts">
	import { onMount } from 'svelte';
	import { getParquetUrl, PARQUETS, DATA_FRESHNESS } from '$lib/config';
	import { initDuckDB, query } from '$lib/stores/duckdb';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import type { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import PetalChart from '$lib/components/PetalChart.svelte';

	let {
		lensStore,
		mapStore,
		onRemoveRadio,
		onSelectCatastroDpto,
	}: {
		lensStore: LensStore;
		mapStore: MapStore;
		onRemoveRadio: (redcode: string) => void;
		onSelectCatastroDpto?: (centroid: [number, number] | null) => void;
	} = $props();

	let loading = $state(true);
	let selectedDpto = $state<string | null>(null);
	let allData: Map<string, Record<string, any>> = $state(new Map());
	let deptSummary: Array<{ code: string; dpto: string; nUrban: number; nRural: number; newParcels: number }> = $state([]);
	let totalUrban = $state(0);
	let totalRural = $state(0);
	let totalNew90d = $state(0);
	let avgAreaUrban = $state(0);
	let deptAvgs: Map<string, { avgUrban: number; avgAreaUrban: number; avgNew90d: number }> = $state(new Map());
	let provAvg = $state({ avgUrban: 0, avgAreaUrban: 0, avgNew90d: 0 });

	// Housing quality (loaded per-radio from radio_stats_master)
	let housingData = $state<Record<string, number> | null>(null);
	let housingProvAvg = $state<Record<string, number> | null>(null);

	const HOUSING_COLS = ['pct_agua_red', 'pct_cloacas', 'pct_alumbrado', 'pct_pavimento', 'pct_hacinamiento', 'pct_nbi'];
	const HOUSING_LABELS_KEYS = [
		'analysis.catastro.h.agua', 'analysis.catastro.h.cloacas', 'analysis.catastro.h.alumbrado',
		'analysis.catastro.h.pavimento', 'analysis.catastro.h.hacinamiento', 'analysis.catastro.h.nbi'
	];
	// For petal: hacinamiento and NBI are "inverse" (lower = better), so we use (100 - value)
	const HOUSING_INVERSE = [false, false, false, false, true, true];

	const selectedRedcode = $derived(
		mapStore.selectedRadios.size === 1
			? [...mapStore.selectedRadios.keys()][0]
			: null
	);
	const radioData = $derived(
		selectedRedcode ? allData.get(selectedRedcode) ?? null : null
	);

	// Petal values: normalize to 0-100 where 50 = provincial average
	const petalValues = $derived.by(() => {
		if (!housingData || !housingProvAvg) return null;
		return HOUSING_COLS.map((col, i) => {
			let raw = housingData[col] ?? 0;
			let avg = housingProvAvg[col] ?? 1;
			if (HOUSING_INVERSE[i]) { raw = 100 - raw; avg = 100 - avg; }
			if (avg === 0) return 50;
			return Math.min(100, Math.max(0, (raw / avg) * 50));
		});
	});
	const petalLabels = $derived(HOUSING_LABELS_KEYS.map(k => i18n.t(k)));

	onMount(() => { loadData(); });

	// Load housing data when radio changes
	$effect(() => {
		const rc = selectedRedcode;
		if (rc) {
			loadHousingData(rc);
		} else {
			housingData = null;
		}
	});

	async function loadData() {
		try {
			await initDuckDB();
			const url = getParquetUrl('catastro_by_radio');
			const result = await query(`SELECT * FROM '${url}'`);
			const map = new Map<string, Record<string, any>>();
			const depts = new Map<string, { nUrban: number; nRural: number; newParcels: number }>();
			let tUrban = 0;
			let tRural = 0;
			let tNew = 0;
			const areas: number[] = [];

			for (let i = 0; i < result.numRows; i++) {
				const raw = result.get(i)!.toJSON() as Record<string, any>;
				const row: Record<string, any> = {};
				for (const [k, v] of Object.entries(raw)) {
					row[k] = typeof v === 'bigint' ? Number(v) : v;
				}
				map.set(row.redcode, row);
				tUrban += row.n_parcelas_urbano ?? 0;
				tRural += row.n_parcelas_rural ?? 0;
				tNew += row.n_new_parcels_90d ?? 0;
				if (row.area_media_urbano_m2 != null && row.area_media_urbano_m2 > 0) {
					areas.push(row.area_media_urbano_m2);
				}
				const dptoCode = row.redcode.substring(0, 5);
				const d = depts.get(dptoCode) ?? { nUrban: 0, nRural: 0, newParcels: 0 };
				d.nUrban += row.n_parcelas_urbano ?? 0;
				d.nRural += row.n_parcelas_rural ?? 0;
				d.newParcels += row.n_new_parcels_90d ?? 0;
				depts.set(dptoCode, d);
			}

			allData = map;
			totalUrban = tUrban;
			totalRural = tRural;
			totalNew90d = tNew;
			avgAreaUrban = areas.length > 0 ? areas.reduce((a, b) => a + b, 0) / areas.length : 0;

			const n = map.size;
			provAvg = {
				avgUrban: n > 0 ? tUrban / n : 0,
				avgAreaUrban: avgAreaUrban,
				avgNew90d: n > 0 ? tNew / n : 0,
			};
			const deptRadioCounts = new Map<string, number>();
			const deptAreaSums = new Map<string, { sum: number; count: number }>();
			for (const [rc, row] of map) {
				const dc = rc.substring(0, 5);
				deptRadioCounts.set(dc, (deptRadioCounts.get(dc) ?? 0) + 1);
				if (row.area_media_urbano_m2 != null && row.area_media_urbano_m2 > 0) {
					const a = deptAreaSums.get(dc) ?? { sum: 0, count: 0 };
					a.sum += row.area_media_urbano_m2;
					a.count += 1;
					deptAreaSums.set(dc, a);
				}
			}
			const da = new Map<string, { avgUrban: number; avgAreaUrban: number; avgNew90d: number }>();
			for (const [code, d] of depts) {
				const nRadios = deptRadioCounts.get(code) ?? 1;
				const areaInfo = deptAreaSums.get(code);
				da.set(code, {
					avgUrban: d.nUrban / nRadios,
					avgAreaUrban: areaInfo ? areaInfo.sum / areaInfo.count : 0,
					avgNew90d: d.newParcels / nRadios,
				});
			}
			deptAvgs = da;

			deptSummary = [...depts.entries()]
				.map(([code, d]) => ({ code, dpto: getDptoName(code), nUrban: d.nUrban, nRural: d.nRural, newParcels: d.newParcels }))
				.sort((a, b) => b.nUrban - a.nUrban)
				.slice(0, 10);

			// Load provincial housing averages (one-time)
			await loadHousingProvAvg();
		} catch (e) {
			console.warn('Failed to load catastro data:', e);
		} finally {
			loading = false;
		}
	}

	async function loadHousingProvAvg() {
		try {
			const cols = HOUSING_COLS.map(c => `AVG(${c}) as ${c}`).join(', ');
			const result = await query(`SELECT ${cols} FROM '${PARQUETS.radio_stats_master}' WHERE pct_agua_red IS NOT NULL`);
			if (result.numRows > 0) {
				const row = result.get(0)!.toJSON() as Record<string, any>;
				housingProvAvg = {};
				for (const c of HOUSING_COLS) {
					housingProvAvg[c] = Number(row[c] ?? 0);
				}
			}
		} catch (e) {
			console.warn('Failed to load housing provincial avg:', e);
		}
	}

	async function loadHousingData(redcode: string) {
		try {
			await initDuckDB();
			const cols = HOUSING_COLS.join(', ');
			const result = await query(
				`SELECT ${cols} FROM '${PARQUETS.radio_stats_master}' WHERE redcode = '${redcode.replace(/'/g, "''")}' LIMIT 1`
			);
			if (result.numRows > 0) {
				const row = result.get(0)!.toJSON() as Record<string, any>;
				const data: Record<string, number> = {};
				for (const c of HOUSING_COLS) data[c] = Number(row[c] ?? 0);
				housingData = data;
			} else {
				housingData = null;
			}
		} catch (e) {
			console.warn('Failed to load housing data:', e);
			housingData = null;
		}
	}

	const DPTO_INFO: Record<string, { name: string; centroid: [number, number] }> = {
		'54007': { name: 'Apóstoles', centroid: [-27.92, -55.75] },
		'54014': { name: 'Cainguás', centroid: [-27.18, -54.73] },
		'54021': { name: 'Candelaria', centroid: [-27.45, -55.73] },
		'54028': { name: 'Capital', centroid: [-27.38, -55.90] },
		'54035': { name: 'Concepción', centroid: [-27.98, -55.52] },
		'54042': { name: 'Eldorado', centroid: [-26.40, -54.63] },
		'54049': { name: 'G. M. Belgrano', centroid: [-26.08, -53.78] },
		'54056': { name: 'Guaraní', centroid: [-27.18, -54.18] },
		'54063': { name: 'Iguazú', centroid: [-25.95, -54.30] },
		'54070': { name: 'L.G. San Martín', centroid: [-27.08, -54.95] },
		'54077': { name: 'L. N. Alem', centroid: [-27.60, -55.32] },
		'54084': { name: 'Montecarlo', centroid: [-26.58, -54.78] },
		'54091': { name: 'Oberá', centroid: [-27.48, -55.12] },
		'54098': { name: 'San Ignacio', centroid: [-27.25, -55.53] },
		'54105': { name: 'San Javier', centroid: [-27.77, -55.13] },
		'54112': { name: 'San Pedro', centroid: [-26.62, -54.12] },
		'54119': { name: '25 de Mayo', centroid: [-27.37, -54.02] },
	};

	function getDptoName(code: string): string { return DPTO_INFO[code]?.name ?? code; }

	function handleDptoClick(dptoCode: string) {
		const info = DPTO_INFO[dptoCode];
		if (info) {
			selectedDpto = dptoCode;
			onSelectCatastroDpto?.(info.centroid);
		}
	}

	function handleBackToDepts() {
		selectedDpto = null;
		onSelectCatastroDpto?.(null);
		// Clear any selected radio
		for (const rc of [...mapStore.selectedRadios.keys()]) {
			onRemoveRadio(rc);
		}
	}

	function fmt(n: number | null | undefined): string {
		if (n == null) return '-';
		return n.toLocaleString('es-AR', { maximumFractionDigits: 0 });
	}

	function fmtArea(n: number | null | undefined): string {
		if (n == null || n === 0) return '-';
		return `${n.toLocaleString('es-AR', { maximumFractionDigits: 0 })} m\u00B2`;
	}

	function fmtPct(n: number | null | undefined): string {
		if (n == null) return '-';
		return `${n.toFixed(1)}%`;
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
				<div class="detail-dpto">{getDptoName(selectedRedcode.substring(0, 5))}</div>
			</div>
			<button class="detail-close" onclick={() => onRemoveRadio(selectedRedcode)}>x</button>
		</div>

		<div class="stat-grid">
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalUrban')}</div>
				<div class="stat-value">{fmt(radioData.n_parcelas_urbano)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalRural')}</div>
				<div class="stat-value">{fmt(radioData.n_parcelas_rural)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.avgAreaUrban')}</div>
				<div class="stat-value">{fmtArea(radioData.area_media_urbano_m2)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.avgAreaRural')}</div>
				<div class="stat-value">{fmtArea(radioData.area_media_rural_m2)}</div>
			</div>
		</div>

		{#if radioData.n_new_parcels_90d > 0}
			<div class="pressure-badge">
				<span class="pressure-icon">+</span>
				<span>{radioData.n_new_parcels_90d} {i18n.t('analysis.catastro.newParcels')}</span>
			</div>
		{/if}

		<!-- Comparison bars: radio vs department vs province -->
		{#if deptAvgs.has(selectedRedcode.substring(0, 5))}
		{@const dptoCode = selectedRedcode.substring(0, 5)}
		{@const da = deptAvgs.get(dptoCode)}
		{@const bars = [
			{ label: i18n.t('analysis.catastro.totalUrban'), val: radioData.n_parcelas_urbano ?? 0, dept: da.avgUrban, prov: provAvg.avgUrban },
			{ label: i18n.t('analysis.catastro.avgAreaUrban'), val: radioData.area_media_urbano_m2 ?? 0, dept: da.avgAreaUrban, prov: provAvg.avgAreaUrban },
			{ label: i18n.t('analysis.catastro.newParcels'), val: radioData.n_new_parcels_90d ?? 0, dept: da.avgNew90d, prov: provAvg.avgNew90d },
		]}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.catastro.vsAvg')}</div>
				{#each bars as bar}
					{@const maxVal = Math.max(bar.val, bar.dept, bar.prov, 1)}
					<div class="cmp-row">
						<div class="cmp-label">{bar.label}</div>
						<div class="cmp-track">
							<div class="cmp-fill" style:width="{(bar.val / maxVal) * 100}%"></div>
							{#if bar.dept > 0}
								<div class="cmp-marker cmp-marker-dept" style:left="{(bar.dept / maxVal) * 100}%" title="{i18n.t('analysis.catastro.deptAvg')}"></div>
							{/if}
							{#if bar.prov > 0}
								<div class="cmp-marker cmp-marker-prov" style:left="{(bar.prov / maxVal) * 100}%" title="{i18n.t('analysis.catastro.provAvg')}"></div>
							{/if}
						</div>
						<div class="cmp-value">{bar.val >= 100 ? fmt(bar.val) : bar.val.toFixed(0)}</div>
					</div>
				{/each}
				<div class="cmp-legend">
					<span class="cmp-legend-item"><span class="cmp-dot cmp-dot-fill"></span>{i18n.t('analysis.catastro.thisRadio')}</span>
					<span class="cmp-legend-item"><span class="cmp-dot cmp-dot-dept"></span>{i18n.t('analysis.catastro.deptAvg')}</span>
					<span class="cmp-legend-item"><span class="cmp-dot cmp-dot-prov"></span>{i18n.t('analysis.catastro.provAvg')}</span>
				</div>
			</div>
		{/if}

		<!-- Housing quality petal -->
		{#if petalValues && housingData}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.catastro.housingTitle')}</div>
				<div class="petal-wrapper">
					<PetalChart layers={[{ values: petalValues, color: '#06b6d4' }]} labels={petalLabels} size={200} />
				</div>
				<div class="housing-grid">
					{#each HOUSING_COLS as col, i}
						<div class="housing-item">
							<span class="housing-label">{petalLabels[i]}</span>
							<span class="housing-value">{fmtPct(housingData[col])}</span>
						</div>
					{/each}
				</div>
				<div class="petal-hint">{i18n.t('analysis.catastro.petalHint')}</div>
			</div>
		{/if}
	</div>
{:else if selectedDpto}
	<!-- Department selected: parcels visible on map -->
	<div class="dept-detail">
		<button class="back-btn" onclick={handleBackToDepts}>← {i18n.t('analysis.catastro.topDepts')}</button>
		<div class="dept-active-title">{getDptoName(selectedDpto)}</div>
		<div class="hint">{i18n.t('analysis.catastro.clickDept')}</div>

		<div class="source-note-box">
			<div><strong>{i18n.t('data.source.catastro')}</strong></div>
			<div>{i18n.t('analysis.catastro.updateFreq')} · {DATA_FRESHNESS.catastro_by_radio?.processedDate ?? ''}</div>
		</div>
	</div>
{:else}
	<!-- Provincial summary -->
	<div class="provincial-summary">
		<div class="stat-grid">
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalUrban')}</div>
				<div class="stat-value">{fmt(totalUrban)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.totalRural')}</div>
				<div class="stat-value">{fmt(totalRural)}</div>
			</div>
			<div class="stat-item">
				<div class="stat-label">{i18n.t('analysis.catastro.avgAreaUrban')}</div>
				<div class="stat-value">{fmtArea(avgAreaUrban)}</div>
			</div>
			<div class="stat-item highlight">
				<div class="stat-label">{i18n.t('analysis.catastro.newParcels')}</div>
				<div class="stat-value new-count">{fmt(totalNew90d)}</div>
			</div>
		</div>

		{#if deptSummary.length > 0}
			{@const maxN = deptSummary[0].nUrban}
			<div class="section">
				<div class="section-title">{i18n.t('analysis.catastro.topDepts')}</div>
				{#each deptSummary as dept}
					<button class="dept-row dept-clickable"
						onclick={() => handleDptoClick(dept.code)}>
						<div class="dept-top">
							<span class="dept-name">{dept.dpto}</span>
							<span class="dept-count">{fmt(dept.nUrban)}</span>
						</div>
						<div class="dept-bar-bg">
							<div class="dept-bar" style:width="{(dept.nUrban / maxN) * 100}%"></div>
						</div>
					</button>
				{/each}
			</div>
		{/if}

		<div class="source-note-box">
			<div><strong>{i18n.t('data.source.catastro')}</strong></div>
			<div>{i18n.t('analysis.catastro.updateFreq')} · {DATA_FRESHNESS.catastro_by_radio?.processedDate ?? ''}</div>
		</div>
	</div>
{/if}

<style>
	.loading { color: #a3a3a3; font-size: 10px; padding: 12px 0; }
	.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px; }
	.stat-item { background: rgba(255,255,255,0.03); border-radius: 6px; padding: 6px 8px; }
	.stat-item.highlight { background: rgba(6,182,212,0.08); border: 1px solid rgba(6,182,212,0.2); }
	.stat-label { font-size: 8px; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 2px; }
	.stat-value { font-size: 13px; font-weight: 600; color: #e2e8f0; }
	.stat-value.new-count { color: #06b6d4; }

	.pressure-badge { display: inline-flex; align-items: center; gap: 4px; background: rgba(6,182,212,0.1); border: 1px solid rgba(6,182,212,0.3); border-radius: 6px; padding: 4px 10px; font-size: 10px; font-weight: 600; color: #06b6d4; margin-bottom: 8px; }
	.pressure-icon { font-size: 12px; font-weight: 700; }

	.section { margin-bottom: 8px; }
	.section-title { font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #a3a3a3; border-bottom: 1px solid #1e293b; padding-bottom: 2px; margin-bottom: 4px; }

	.dept-row { margin-bottom: 4px; }
	.dept-clickable { background: none; border: none; width: 100%; text-align: left; cursor: pointer; padding: 3px 4px; border-radius: 4px; transition: background 0.15s; }
	.dept-clickable:hover { background: rgba(6,182,212,0.1); }
	.dept-top { display: flex; justify-content: space-between; align-items: baseline; }
	.dept-name { font-size: 10px; color: #d4d4d4; }
	.dept-count { font-size: 9px; color: #a3a3a3; }
	.dept-bar-bg { height: 3px; background: rgba(255,255,255,0.05); border-radius: 2px; margin-top: 1px; }
	.dept-bar { height: 100%; background: #06b6d4; border-radius: 2px; transition: width 0.3s ease; }

	.radio-detail { padding: 2px 0; }
	.detail-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
	.detail-redcode { font-size: 11px; font-weight: 600; color: #e2e8f0; font-family: monospace; }
	.detail-dpto { font-size: 9px; color: #a3a3a3; }
	.detail-close { background: none; border: none; color: #a3a3a3; cursor: pointer; font-size: 12px; padding: 0 4px; line-height: 1; }
	.detail-close:hover { color: #e2e8f0; }

	/* Comparison bars */
	.cmp-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
	.cmp-label { font-size: 8px; color: #a3a3a3; width: 60px; flex-shrink: 0; text-transform: uppercase; letter-spacing: 0.03em; }
	.cmp-track { flex: 1; height: 8px; background: rgba(255,255,255,0.05); border-radius: 4px; position: relative; overflow: visible; }
	.cmp-fill { height: 100%; background: #06b6d4; border-radius: 4px; transition: width 0.3s ease; }
	.cmp-marker { position: absolute; top: -2px; width: 2px; height: 12px; border-radius: 1px; transform: translateX(-1px); }
	.cmp-marker-dept { background: #f59e0b; }
	.cmp-marker-prov { background: #a78bfa; }
	.cmp-value { font-size: 9px; font-weight: 600; color: #e2e8f0; min-width: 28px; text-align: right; }
	.cmp-legend { display: flex; gap: 10px; margin-top: 4px; margin-bottom: 8px; }
	.cmp-legend-item { font-size: 7px; color: #a3a3a3; display: flex; align-items: center; gap: 3px; }
	.cmp-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
	.cmp-dot-fill { background: #06b6d4; }
	.cmp-dot-dept { background: #f59e0b; }
	.cmp-dot-prov { background: #a78bfa; }

	/* Housing quality petal */
	.petal-wrapper { display: flex; justify-content: center; margin: 4px 0; }
	.housing-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 8px; }
	.housing-item { display: flex; justify-content: space-between; font-size: 9px; padding: 1px 0; }
	.housing-label { color: #a3a3a3; }
	.housing-value { color: #e2e8f0; font-weight: 600; }
	.petal-hint { font-size: 7px; color: #737373; text-align: center; margin-top: 4px; }

	/* Department detail */
	.dept-detail { font-size: 11px; }
	.back-btn { background: none; border: none; color: #60a5fa; font-size: 10px; cursor: pointer; padding: 0; margin-bottom: 8px; }
	.back-btn:hover { text-decoration: underline; }
	.dept-active-title { font-size: 14px; font-weight: 700; color: #e2e8f0; margin-bottom: 8px; }
	.hint { font-size: 9px; color: #a3a3a3; text-align: center; margin-top: 8px; }

	.source-note-box { margin-top: 10px; padding: 6px 8px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px; font-size: 8px; color: #737373; line-height: 1.4; }
</style>
