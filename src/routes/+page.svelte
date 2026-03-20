<script lang="ts">
	import { onMount } from 'svelte';
	import MapComponent from '$lib/components/Map.svelte';
	import Controls from '$lib/components/Controls.svelte';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import ChatPanel from '$lib/components/ChatPanel.svelte';
	import LensSelector from '$lib/components/LensSelector.svelte';
	import { MapStore } from '$lib/stores/map.svelte';
	import { LensStore } from '$lib/stores/lens.svelte';
	import { LassoStore } from '$lib/stores/lasso.svelte';
	import { initDuckDB, query, isReady } from '$lib/stores/duckdb';
	import { PARQUETS, LENS_CONFIG, MAP_INIT, type AnalysisConfig } from '$lib/config';
	import { i18n, type Locale } from '$lib/stores/i18n.svelte';

	const mapStore = new MapStore();
	const lensStore = new LensStore();
	const lassoStore = new LassoStore();

	let mapComponent: ReturnType<typeof MapComponent>;
	let mapContainer: HTMLDivElement;
	let chatCollapsed = $state(true);

	onMount(() => {
		initDuckDB()
			.then(() => lensStore.loadData())
			.catch(e => console.warn('DuckDB init failed:', e));

		mapContainer?.addEventListener('radio-select', ((e: CustomEvent) => {
			const { redcode, selected, census } = e.detail;

			// Unified behavior: clear chat highlights, add radio
			mapStore.clearChatState();
			mapComponent?.clearChatHighlights();

			mapStore.addRadio(redcode, {
				census,
				enriched: null,
				buildingCount: selected.length
			});
			mapComponent?.setRadioHighlight(getRadioHighlightEntries());
			fetchRadioEnrichment(redcode);
		}) as EventListener);

		mapContainer?.addEventListener('radio-deselect', ((e: CustomEvent) => {
			const { redcode } = e.detail;
			mapStore.removeRadio(redcode);
			mapComponent?.setRadioHighlight(getRadioHighlightEntries());
		}) as EventListener);

		document.addEventListener('keydown', (e) => {
			if (e.key === 'Escape') {
				if (lassoStore.drawing) {
					lassoStore.cancelDraw();
					mapComponent?.clearLassoDraw();
				} else if (lassoStore.active) {
					handleToggleLasso();
				} else if (lensStore.selectedDpto) {
					handleBackToDepts();
				} else {
					clearAll();
				}
			}
		});

		// Lasso mouse events on the map container
		mapContainer?.addEventListener('mousedown', (e: MouseEvent) => {
			if (!lassoStore.active || e.button !== 0) return;
			lassoStore.startDraw();
			const m = mapComponent?.getMap();
			if (!m) return;
			const lngLat = m.unproject([e.offsetX, e.offsetY]);
			lassoStore.addPoint([lngLat.lng, lngLat.lat]);
		});

		mapContainer?.addEventListener('mousemove', (e: MouseEvent) => {
			if (!lassoStore.drawing) return;
			const m = mapComponent?.getMap();
			if (!m) return;
			const lngLat = m.unproject([e.offsetX, e.offsetY]);
			lassoStore.addPoint([lngLat.lng, lngLat.lat]);
			mapComponent?.updateLassoDraw(lassoStore.currentPolygon);
		});

		mapContainer?.addEventListener('mouseup', async (e: MouseEvent) => {
			if (!lassoStore.drawing) return;
			const polygon = lassoStore.finishDraw();
			mapComponent?.clearLassoDraw();
			if (polygon.length < 4) return; // need at least 3 points + closing

			const redcodes = lassoStore.findRadiosInPolygon(polygon);
			if (redcodes.length === 0) return;

			await lassoStore.createZone(redcodes, polygon);
			updateZoneHighlights();
		});
	});

	// ── Lens reactivity ──────────────────────────────────────────────────────
	let prevLensKey: string = '';

	$effect(() => {
		const lens = lensStore.activeLens;
		const count = lensStore.opportunityCount;
		const key = `${lens}:${count}`;
		if (key === prevLensKey) return;
		prevLensKey = key;

		if (lens) {
			const cfg = LENS_CONFIG[lens];
			const redcodes = [...lensStore.opportunityRadios.keys()];
			mapComponent?.setOpportunityGlow(redcodes, cfg.color);
			// Clear any existing radio selections and highlights
			mapStore.clearRadios();
			mapComponent?.clearRadioHighlight();
			mapComponent?.clearChatHighlights();
			mapComponent?.clearAnalysisChoropleth();
		} else {
			mapComponent?.clearOpportunityGlow();
			mapComponent?.clearAnalysisChoropleth();
		}
	});

	// ── Department drill-down reactivity ─────────────────────────────────────
	let prevDpto: string | null = null;

	$effect(() => {
		const dpto = lensStore.selectedDpto;
		if (dpto === prevDpto) return;
		prevDpto = dpto;

		if (!lensStore.activeLens) return;
		const cfg = LENS_CONFIG[lensStore.activeLens];

		if (dpto) {
			// Filter glow to only this department's radios
			const dptoRedcodes = [...lensStore.dptoOpportunities.keys()];
			mapComponent?.setOpportunityGlow(dptoRedcodes, cfg.color);
			// Fly to department centroid
			const centroid = lensStore.dptoCentroid(dpto);
			if (centroid) mapComponent?.flyToCoords(centroid[0], centroid[1], 10);
		} else {
			// Back to province: restore all opportunity radios
			const allRedcodes = [...lensStore.opportunityRadios.keys()];
			mapComponent?.setOpportunityGlow(allRedcodes, cfg.color);
			mapComponent?.flyToProvince();
		}
	});

	function handleSelectDpto(dpto: string) {
		lensStore.selectDpto(dpto);
	}

	function handleSelectRadio(redcode: string) {
		if (mapStore.hasRadio(redcode)) {
			mapStore.removeRadio(redcode);
			mapComponent?.setRadioHighlight(getRadioHighlightEntries());
		} else {
			mapStore.addRadio(redcode, { census: {}, enriched: null, buildingCount: 0 });
			mapComponent?.setRadioHighlight(getRadioHighlightEntries());
			fetchRadioEnrichment(redcode);
			const c = lensStore.radioCentroid(redcode);
			if (c) mapComponent?.flyToCoords(c[0], c[1], 14);
		}
	}

	function handleBackToDepts() {
		lensStore.clearDpto();
	}

	function handleSelectAnalysis(analysis: AnalysisConfig) {
		if (analysis.status === 'coming_soon') {
			// Still set it so AnalysisView shows the coming-soon card
			lensStore.setAnalysis(analysis);
			mapComponent?.clearAnalysisChoropleth();
			return;
		}
		lensStore.setAnalysis(analysis);

		// For analyses with choropleth, load will happen inside the component
		// The choropleth is triggered via the $effect below
	}

	// ── Analysis choropleth reactivity ──────────────────────────────────────
	let prevAnalysisId: string | null = null;
	let analysisDataLoaded = $state(false);

	$effect(() => {
		const analysis = lensStore.activeAnalysis;
		const id = analysis?.id ?? null;

		if (id === prevAnalysisId) return;
		prevAnalysisId = id;

		if (!id || !analysis) {
			mapComponent?.clearAnalysisChoropleth();
			analysisDataLoaded = false;
			return;
		}

		// Choropleth loading is deferred — the analysis component loads data
		// and we poll for it via a timeout. This avoids tight coupling.
		if (analysis.choropleth && analysis.id === 'real_estate') {
			analysisDataLoaded = false;
			loadAnalysisChoropleth(analysis);
		}
	});

	async function loadAnalysisChoropleth(analysis: AnalysisConfig) {
		if (!analysis.choropleth || !isReady()) return;
		try {
			const { getParquetUrl } = await import('$lib/config');
			const url = getParquetUrl(analysis.choropleth.parquet);
			const col = analysis.choropleth.column;
			const result = await query(
				`SELECT redcode, ${col} as value FROM '${url}' WHERE ${col} IS NOT NULL AND ${col} > 0`
			);
			const entries: Array<{ redcode: string; value: number }> = [];
			for (let i = 0; i < result.numRows; i++) {
				const row = result.get(i)!.toJSON() as { redcode: string; value: number };
				entries.push(row);
			}
			mapComponent?.setAnalysisChoropleth(entries, analysis.choropleth.colorScale);
			analysisDataLoaded = true;
		} catch (e) {
			console.warn('Failed to load analysis choropleth:', e);
		}
	}

	async function fetchRadioEnrichment(redcode: string): Promise<void> {
		if (!isReady()) return;
		if (!/^\d{9}$/.test(redcode)) return;
		try {
			const ENRICHMENT_COLS = 'redcode, total_personas, tasa_actividad, tasa_empleo, pct_universitario, pct_nbi, pct_hacinamiento';
			const result = await query(
				`SELECT ${ENRICHMENT_COLS} FROM '${PARQUETS.radio_stats_master}' WHERE redcode = '${redcode}' LIMIT 1`
			);
			if (result.numRows === 0) return;
			const row = result.get(0)!;
			mapStore.updateEnriched(redcode, row.toJSON());
		} catch (e) {
			console.warn('DuckDB enrichment failed:', e);
		}
	}

	async function fetchRadioCensus(redcode: string): Promise<Record<string, any>> {
		if (!isReady()) return {};
		if (!/^\d{9}$/.test(redcode)) return {};
		try {
			const result = await query(
				`SELECT * FROM '${PARQUETS.radio_stats_master}' WHERE redcode = '${redcode}' LIMIT 1`
			);
			if (result.numRows === 0) return {};
			return result.get(0)!.toJSON();
		} catch (e) {
			console.warn('DuckDB census fetch failed:', e);
			return {};
		}
	}

	function getRadioHighlightEntries(): Array<{redcode: string, color: string}> {
		return [...mapStore.selectedRadios.entries()].map(([rc, d]) => ({redcode: rc, color: d.color}));
	}

	function handleRemoveRadio(redcode: string) {
		mapStore.removeRadio(redcode);
		mapComponent?.setRadioHighlight(getRadioHighlightEntries());
	}

	// ── Lasso handlers ──────────────────────────────────────────────────────

	function handleToggleLasso() {
		lassoStore.toggle();
		mapComponent?.setLassoMode(lassoStore.active);
	}

	function updateZoneHighlights() {
		const zones = lassoStore.zones.map(z => ({ redcodes: z.redcodes, color: z.color }));
		mapComponent?.setZoneHighlight(zones);
	}

	function handleRemoveZone(id: string) {
		lassoStore.removeZone(id);
		updateZoneHighlights();
	}

	function handleClearZones() {
		lassoStore.clearZones();
		mapComponent?.clearZoneHighlight();
	}

	function clearAll() {
		mapStore.clearRadios();
		mapStore.clearChatState();
		mapComponent?.clearRadioHighlight();
		mapComponent?.clearChatHighlights();
		mapComponent?.clearAnalysisChoropleth();
		lensStore.clearSelection();
		lensStore.clearDpto();
		lensStore.clearAnalysis();
		lassoStore.clearZones();
		mapComponent?.clearZoneHighlight();
		if (lassoStore.active) {
			lassoStore.toggle();
			mapComponent?.setLassoMode(false);
		}
	}

	function handleChatResponse(response: {
		text: string;
		mapActions: Array<{ type: string; redcodes?: string[]; values?: number[]; indicator?: string; lat?: number; lng?: number; zoom?: number }>;
		chartData: Array<{ title: string; type: string; data: Array<{ label: string; value: number }>; unit?: string }>;
		toolCalls: Array<{ name: string; elapsed: number }>;
	}) {
		// Process map actions
		for (const action of response.mapActions) {
			if (action.type === 'choropleth' && action.redcodes && action.values) {
				const entries = action.redcodes.map((rc, i) => ({ redcode: rc, value: action.values![i] }));
				mapStore.setChatHighlight(action.redcodes);
				mapComponent?.setChatChoropleth(entries);
			} else if (action.type === 'highlight' && action.redcodes) {
				mapStore.setChatHighlight(action.redcodes);
				if (action.redcodes.length === 1) {
					// Single radio from chat: select with red, highlight red
					const redcode = action.redcodes[0];
					if (!mapStore.hasRadio(redcode)) {
						mapStore.addRadio(redcode, { census: {}, enriched: null, buildingCount: 0 }, '#ef4444');
					}
					const radioColor = mapStore.selectedRadios.get(redcode)?.color ?? '#ef4444';
					mapComponent?.highlightChatRadios(action.redcodes, radioColor);
					mapComponent?.setRadioHighlight(getRadioHighlightEntries());
					// Async: fill census + enrichment data
					fetchRadioCensus(redcode).then(census => {
						mapStore.updateCensus(redcode, census);
					});
					fetchRadioEnrichment(redcode);
				} else {
					mapComponent?.highlightChatRadios(action.redcodes);
				}
			} else if (action.type === 'flyTo' && action.lat != null && action.lng != null) {
				mapComponent?.flyToCoords(action.lat, action.lng, action.zoom);
			}
		}

		// Pass chart data to sidebar
		if (response.chartData && response.chartData.length > 0) {
			mapStore.setChatCharts(response.chartData as any);
		}
	}
</script>

<div class="flex h-screen w-full">
	<!-- Chat column (left) -->
	<ChatPanel onResponse={handleChatResponse} bind:collapsed={chatCollapsed} />

	<!-- Map + overlays (right) -->
	<div class="flex-1 flex flex-col relative min-w-0">
		<!-- Header -->
		<div class="flex items-center justify-between px-4 py-2.5 border-b border-border z-10 shrink-0"
			style="background: rgba(10,12,18,0.88); backdrop-filter: blur(8px);">
			<h1 class="text-[15px] font-bold text-white tracking-wide">
				{i18n.t('header.title')} <span class="text-accent font-normal">&mdash; {i18n.t('header.subtitle')}</span>
			</h1>

			<!-- Lens selector (center) -->
			<LensSelector {lensStore} />

			<div class="flex items-center gap-0.5">
				{#each (['es', 'en', 'gn'] as Locale[]) as lang}
					<button
						class="px-2 py-0.5 text-[11px] font-semibold rounded-full cursor-pointer border transition-all {i18n.locale === lang ? 'bg-accent-active text-accent border-accent' : 'bg-transparent text-text-dim border-transparent hover:text-text-muted'}"
						onclick={() => i18n.setLocale(lang)}>
						{lang.toUpperCase()}
					</button>
				{/each}
			</div>
		</div>

		<!-- Map container -->
		<div bind:this={mapContainer} class="flex-1 relative min-h-0">
			<MapComponent bind:this={mapComponent} {mapStore} />

			<!-- Controls (positioned relative to map) -->
			<Controls
				{mapStore}
				hasSelection={mapStore.selectedRadios.size > 0}
				onClear={clearAll}
				lassoActive={lassoStore.active}
				onToggleLasso={handleToggleLasso}
				hasZones={lassoStore.zones.length > 0}
				onClearZones={handleClearZones}
			/>

			<!-- Sidebar (positioned relative to map) -->
			<Sidebar
				{mapStore}
				{lensStore}
				{lassoStore}
				onRemoveRadio={handleRemoveRadio}
				onSelectDpto={handleSelectDpto}
				onSelectRadio={handleSelectRadio}
				onSelectAnalysis={handleSelectAnalysis}
				onRemoveZone={handleRemoveZone}
				onClearZones={handleClearZones}
			/>
		</div>
	</div>
</div>
