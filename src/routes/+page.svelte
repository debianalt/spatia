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
	import { HexStore } from '$lib/stores/hex.svelte';
	import { initDuckDB, query, isReady } from '$lib/stores/duckdb';
	import { PARQUETS, LENS_CONFIG, MAP_INIT, HEX_LAYER_REGISTRY, type AnalysisConfig } from '$lib/config';
	import { i18n, type Locale } from '$lib/stores/i18n.svelte';

	const mapStore = new MapStore();
	const lensStore = new LensStore();
	const lassoStore = new LassoStore();
	const hexStore = new HexStore();

	let mapComponent: ReturnType<typeof MapComponent>;
	let mapContainer: HTMLDivElement;
	let chatCollapsed = $state(true);

	onMount(() => {
		initDuckDB()
			.then(() => {
				lensStore.loadData();
				warmupRadioStats();
			})
			.catch(e => console.warn('DuckDB init failed:', e));

		mapContainer?.addEventListener('radio-select', ((e: CustomEvent) => {
			if (lassoStore.active) return;
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

		mapContainer?.addEventListener('hex-select', ((e: CustomEvent) => {
			if (lassoStore.active) return;
			const { h3index, properties } = e.detail;
			if (hexStore.activeLayer) {
				hexStore.toggleHex(h3index);
				// Ensure provincial avg is loaded for petal normalization
				hexStore.ensureProvincialAvgLoaded();
			} else {
				// Legacy single-hex mode (direct analysis)
				mapStore.setSelectedHex({
					h3index,
					jrc_occurrence: properties.jrc_occurrence,
					jrc_recurrence: properties.jrc_recurrence,
					jrc_seasonality: properties.jrc_seasonality,
					flood_extent_pct: properties.flood_extent_pct,
					flood_risk_score: properties.flood_risk_score,
					...properties
				});
				mapComponent?.highlightHexagon(h3index);
				fetchHexData(h3index);
			}
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
			e.stopPropagation();
			lassoStore.startDraw();
			const m = mapComponent?.getMap();
			if (!m) return;
			const lngLat = m.unproject([e.offsetX, e.offsetY]);
			lassoStore.addPoint([lngLat.lng, lngLat.lat]);
		}, { capture: true });

		mapContainer?.addEventListener('mousemove', (e: MouseEvent) => {
			if (!lassoStore.drawing) return;
			e.stopPropagation();
			const m = mapComponent?.getMap();
			if (!m) return;
			const lngLat = m.unproject([e.offsetX, e.offsetY]);
			lassoStore.addPoint([lngLat.lng, lngLat.lat]);
			mapComponent?.updateLassoDraw(lassoStore.currentPolygon);
		}, { capture: true });

		mapContainer?.addEventListener('mouseup', async (e: MouseEvent) => {
			if (!lassoStore.drawing) return;
			e.stopPropagation();
			const polygon = lassoStore.finishDraw();
			mapComponent?.clearLassoDraw();
			if (polygon.length < 4) return; // need at least 3 points + closing

			if (hexStore.activeLayer) {
				// Hex mode: find hexagons in polygon
				const h3indices = hexStore.findHexesInPolygon(polygon);
				if (h3indices.length === 0) return;
				await hexStore.createHexZone(h3indices, polygon);
				updateHexZoneHighlights();
			} else {
				// Radio mode
				const redcodes = lassoStore.findRadiosInPolygon(polygon);
				if (redcodes.length === 0) return;
				await lassoStore.createZone(redcodes, polygon);
				updateZoneHighlights();
			}
		}, { capture: true });
	});

	// ── Lens reactivity ──────────────────────────────────────────────────────
	let prevLensKey: string = '';

	$effect(() => {
		const lens = lensStore.activeLens;
		const count = lensStore.opportunityCount;
		const key = `${lens}:${count}`;
		if (key === prevLensKey) return;
		prevLensKey = key;

		// Always clear hex state on any lens change (covers switch + deactivate)
		mapComponent?.clearHexChoropleth();
		mapComponent?.clearHexZoneHighlight();
		mapStore.clearHexState();
		hexStore.clearAll();
		prevDataVersion = hexStore.dataVersion;

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
		// Clean up catastro layer when leaving catastro analysis
		if (prevAnalysisId === 'catastro') {
			mapComponent?.hideCatastroLayer();
		}
		prevAnalysisId = id;

		if (!id || !analysis) {
			mapComponent?.clearAnalysisChoropleth();
			mapComponent?.clearHexChoropleth();
			mapStore.clearHexState();
			hexStore.clearAll();
			analysisDataLoaded = false;
			return;
		}

		// Hex-based analyses use HexStore multi-resolution system
		if (analysis.spatialUnit === 'hexagon' && analysis.choropleth) {
			analysisDataLoaded = false;
			mapComponent?.clearAnalysisChoropleth();
			const layerCfg = HEX_LAYER_REGISTRY[analysis.id];
			if (layerCfg) {
				hexStore.setLayer(analysis.id);
				mapStore.setActiveHexLayer(analysis.id);
			} else {
				// Fallback: direct load (legacy)
				loadHexChoropleth(analysis);
			}
			return;
		}

		// Choropleth loading is deferred — the analysis component loads data
		// and we poll for it via a timeout. This avoids tight coupling.
		if (analysis.choropleth && analysis.spatialUnit === 'radio') {
			analysisDataLoaded = false;
			mapComponent?.clearHexChoropleth();
			mapStore.clearHexState();
			loadAnalysisChoropleth(analysis);
		}
	});

	// ── HexStore reactivity: sync hex selection highlights with map ───────
	$effect(() => {
		const hexes = [...hexStore.selectedHexes.entries()].map(([h3index, d]) => ({
			h3index, color: d.color
		}));
		mapComponent?.highlightHexagons(hexes);
	});

	// ── HexStore reactivity: re-render choropleth when data changes ──────
	// For perDepartment layers, rendering is handled directly by handleSelectFloodDpto.
	// This $effect only handles non-perDepartment layers (legacy path).
	let prevDataVersion = 0;

	$effect(() => {
		const version = hexStore.dataVersion;
		const entries = hexStore.choroplethEntries;
		const layer = hexStore.activeLayer;

		if (version === prevDataVersion) return;
		prevDataVersion = version;

		// Skip for perDepartment layers — they render directly
		if (layer?.perDepartment) return;

		if (entries.length === 0) {
			mapComponent?.clearHexChoropleth();
			return;
		}

		const colorScale = (layer?.colorScale ?? 'flood') as 'flood' | 'sequential';
		mapComponent?.setHexChoropleth(entries, colorScale);
		analysisDataLoaded = true;
	});

	async function loadAnalysisChoropleth(analysis: AnalysisConfig) {
		if (!analysis.choropleth || !isReady()) return;
		try {
			const { getParquetUrl } = await import('$lib/config');
			const url = getParquetUrl(analysis.choropleth.parquet);
			const col = analysis.choropleth.column;
			const result = await query(
				`SELECT redcode, CAST(${col} AS DOUBLE) as value FROM '${url}' WHERE ${col} IS NOT NULL AND ${col} > 0`
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

	async function fetchHexData(h3index: string): Promise<void> {
		if (!isReady()) return;
		try {
			const result = await query(
				`SELECT h3index, jrc_occurrence, jrc_recurrence, jrc_seasonality, flood_extent_pct, flood_risk_score
				 FROM '${PARQUETS.hex_flood_risk}'
				 WHERE h3index = '${h3index.replace(/'/g, "''")}'
				 LIMIT 1`
			);
			if (result.numRows > 0) {
				const row = result.get(0)!.toJSON();
				mapStore.setSelectedHex(row as any);
			}
		} catch (e) {
			console.warn('Failed to fetch hex data:', e);
		}
	}

	async function loadHexChoropleth(analysis: AnalysisConfig) {
		if (!analysis.choropleth || !isReady()) return;
		try {
			const { getParquetUrl } = await import('$lib/config');
			const url = getParquetUrl(analysis.choropleth.parquet);
			const col = analysis.choropleth.column;
			const result = await query(
				`SELECT h3index, ${col} as value FROM '${url}' WHERE ${col} IS NOT NULL AND ${col} > 0`
			);
			const entries: Array<{ h3index: string; value: number }> = [];
			for (let i = 0; i < result.numRows; i++) {
				const row = result.get(i)!.toJSON() as { h3index: string; value: number };
				entries.push(row);
			}
			mapComponent?.setHexChoropleth(entries, analysis.choropleth.colorScale as any);
			mapStore.setActiveHexLayer(analysis.id);
			analysisDataLoaded = true;
		} catch (e) {
			console.warn('Failed to load hex choropleth:', e);
		}
	}

	async function warmupRadioStats(): Promise<void> {
		try {
			await query(`SELECT 1 FROM '${PARQUETS.radio_stats_master}' LIMIT 1`);
		} catch (_) { /* non-critical */ }
	}

	async function fetchRadioEnrichment(redcode: string): Promise<void> {
		await initDuckDB();
		if (!/^\d{9}$/.test(redcode)) return;
		try {
			const ENRICHMENT_COLS = 'redcode, total_personas, tasa_actividad, tasa_empleo, pct_universitario, pct_nbi, pct_hacinamiento, pct_agua_red';
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
		await initDuckDB();
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

	function handleClearRadios() {
		mapStore.clearRadios();
		mapComponent?.setRadioHighlight([]);
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

	// ── Hex selection + zone helpers ─────────────────────────────────────

	function updateHexZoneHighlights() {
		const zones = hexStore.hexZones.map(z => ({ h3indices: z.h3indices, color: z.color }));
		mapComponent?.setHexZoneHighlight(zones, hexStore.boundaryCache);
	}

	function handleRemoveHexZone(id: string) {
		hexStore.removeHexZone(id);
		updateHexZoneHighlights();
	}

	function handleClearHexZones() {
		hexStore.clearHexZones();
		mapComponent?.clearHexZoneHighlight();
	}

	function handleSelectCatastroDpto(centroid: [number, number] | null) {
		if (centroid) {
			mapComponent?.showCatastroLayer();
			mapComponent?.flyToCoords(centroid[0], centroid[1], 10);
		} else {
			mapComponent?.hideCatastroLayer();
		}
	}

	async function handleSelectFloodDpto(dpto: string, parquetKey: string, centroid: [number, number]) {
		mapComponent?.clearHexChoropleth();
		mapComponent?.clearHexZoneHighlight();
		mapStore.setActiveHexLayer(hexStore.activeLayer?.id ?? null);
		await hexStore.loadDepartment(dpto, parquetKey);
		prevDataVersion = hexStore.dataVersion;
		// Render outside Svelte's reactive batch to prevent $effect interference
		setTimeout(() => {
			const entries = hexStore.choroplethEntries;
			if (entries.length > 0) {
				const colorScale = (hexStore.activeLayer?.colorScale ?? 'flood') as 'flood' | 'sequential';
				mapComponent?.setHexChoropleth(entries, colorScale);
				analysisDataLoaded = true;
			}
			mapComponent?.flyToCoords(centroid[1], centroid[0], 10);
		}, 20);
	}

	function clearAll() {
		mapStore.clearRadios();
		mapStore.clearChatState();
		mapStore.clearHexState();
		hexStore.clearAll();
		mapComponent?.clearRadioHighlight();
		mapComponent?.clearChatHighlights();
		mapComponent?.clearAnalysisChoropleth();
		mapComponent?.clearHexChoropleth();
		mapComponent?.clearHexZoneHighlight();
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
		mapActions: Array<{ type: string; redcodes?: string[]; values?: number[]; h3indices?: string[]; indicator?: string; lat?: number; lng?: number; zoom?: number }>;
		chartData: Array<{ title: string; type: string; data: Array<{ label: string; value: number }>; unit?: string }>;
		toolCalls: Array<{ name: string; elapsed: number }>;
	}) {
		// Process map actions
		for (const action of response.mapActions) {
			if (action.type === 'hex_choropleth' && action.h3indices && action.values) {
				const entries = action.h3indices.map((h, i) => ({ h3index: h, value: action.values![i] }));
				mapComponent?.setHexChoropleth(entries, 'flood');
			} else if (action.type === 'choropleth' && action.redcodes && action.values) {
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
				{i18n.t('header.title')} <span class="text-white/70 font-normal">&mdash; {i18n.t('header.subtitle')}</span>
			</h1>

			<!-- Lens selector (center) -->
			<LensSelector {lensStore} />

			<div class="flex items-center gap-0.5">
				{#each (['es', 'en', 'gn'] as Locale[]) as lang}
					<button
						class="px-2 py-0.5 text-[11px] font-semibold rounded-full cursor-pointer border transition-all {i18n.locale === lang ? 'bg-white/10 text-white border-white/30' : 'bg-transparent text-white/50 border-transparent hover:text-white'}"
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
				hasZones={lassoStore.zones.length > 0 || hexStore.hexZones.length > 0}
				onClearZones={() => { handleClearZones(); handleClearHexZones(); }}
			/>

			<!-- Sidebar (positioned relative to map) -->
			<Sidebar
				{mapStore}
				{lensStore}
				{lassoStore}
				{hexStore}
				onRemoveRadio={handleRemoveRadio}
				onClearRadios={handleClearRadios}
				onSelectDpto={handleSelectDpto}
				onSelectRadio={handleSelectRadio}
				onSelectAnalysis={handleSelectAnalysis}
				onRemoveZone={handleRemoveZone}
				onClearZones={handleClearZones}
				onRemoveHexZone={handleRemoveHexZone}
				onClearHexZones={handleClearHexZones}
				onSelectFloodDpto={handleSelectFloodDpto}
			onSelectCatastroDpto={handleSelectCatastroDpto}
			/>
		</div>
	</div>
</div>
