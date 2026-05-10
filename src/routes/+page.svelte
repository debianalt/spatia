<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import MapComponent from '$lib/components/Map.svelte';
	import MapLegend from '$lib/components/MapLegend.svelte';
	import Controls from '$lib/components/Controls.svelte';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import TerritorySelector from '$lib/components/TerritorySelector.svelte';
	import LensSelector from '$lib/components/LensSelector.svelte';
	import { MapStore } from '$lib/stores/map.svelte';
	import { LensStore } from '$lib/stores/lens.svelte';
	import { LassoStore } from '$lib/stores/lasso.svelte';
	import { HexStore } from '$lib/stores/hex.svelte';
	import { TerritoryStore } from '$lib/stores/territory.svelte';
	import { initDuckDB, query, isReady, getInitError } from '$lib/stores/duckdb';
	import { cellToLatLng } from 'h3-js';
	import { isInsideMisiones } from '$lib/utils/misiones-pip';
	import { isInsideItapua } from '$lib/utils/itapua-pip';
	import { isInsideCorrientes } from '$lib/utils/corrientes-pip';
	import { PARQUETS, MAP_INIT, HEX_LAYER_REGISTRY, getAnalysisById, getAnalysesForLens, type AnalysisConfig, type LensId } from '$lib/config';
	import { i18n, type Locale } from '$lib/stores/i18n.svelte';
	import { terms } from '$lib/stores/terms.svelte';
	import { page } from '$app/stores';

	const mapStore = new MapStore();
	const lensStore = new LensStore();
	const lassoStore = new LassoStore();
	const hexStore = new HexStore();
	const territoryStore = new TerritoryStore();

	let mapComponent: ReturnType<typeof MapComponent>;
	let mapContainer: HTMLDivElement;
	let duckdbFailed = $state(false);
	// ── URL state: read params on mount, write on change ──
	function updateUrlState() {
		const params = new URLSearchParams();
		if (territoryStore.activeTerritory.id !== 'misiones') params.set('t', territoryStore.activeTerritory.id);
		if (lensStore.activeLens) params.set('lens', lensStore.activeLens);
		if (lensStore.activeAnalysis) params.set('a', lensStore.activeAnalysis.id);
		if (hexStore.selectedDpto) params.set('dept', hexStore.selectedDpto);
		if (hexStore.temporalMode !== 'current') params.set('tm', hexStore.temporalMode);
		if (!territoryStore.regionalMode) params.set('rm', '0');
		const qs = params.toString();
		window.history.replaceState({}, '', qs ? `?${qs}` : window.location.pathname);
	}

	$effect(() => {
		const _territory = territoryStore.activeTerritory;
		const _lens = lensStore.activeLens;
		const _analysis = lensStore.activeAnalysis;
		const _dept = hexStore.selectedDpto;
		const _tm = hexStore.temporalMode;
		const _rm = territoryStore.regionalMode;
		if (typeof window !== 'undefined') updateUrlState();
	});

	const REGIONAL_NEA_BBOX: [number, number, number, number] = [-59.8, -30.8, -53.6, -25.4];

	function getRegionalOtherPrefixes(): [string, string] {
		const activePrefix = hexStore.territoryPrefix;
		const all = ['', 'corrientes/', 'itapua_py/'];
		const others = all.filter(p => p !== activePrefix);
		return [others[0], others[1]];
	}

	// Sync territory prefix + fly map + reload data whenever territory changes
	$effect(() => {
		const t = territoryStore.activeTerritory;
		const isRegional = untrack(() => territoryStore.regionalMode);
		hexStore.setTerritoryPrefix(t.parquetPrefix);
		// Toggle territory-specific layers (mask, province boundary, buildings)
		mapComponent?.setActiveTerritory(t.id); // applyTerritoryVisibility() respects regionalModeActive
		// Reload hex choropleth for the new territory
		hexStore.loadVisibleData();
		// Reset selected dept since admin units differ per territory
		hexStore.selectedDpto = null;
		if (!isRegional) {
			// Normal mode: fly to territory + clear cross-territory selections
			setTimeout(() => mapComponent?.flyToBbox(t.bbox), 100);
			mapStore.clearDistricts();
			mapComponent?.setDistrictHighlight([]);
		} else {
			// Regional mode (Option D): keep selections, reload other territories' hex data
			if (hexStore.activeLayer?.comparable) {
				untrack(() => hexStore.clearCompareDept());
				untrack(() => hexStore.clearRegionalData());
				const [p2, p3] = getRegionalOtherPrefixes();
				hexStore.loadFullCompare(p2).catch(() => {});
				hexStore.loadRegionalData(p3).catch(() => {});
			}
		}
	});

	// Regional mode toggle: zoom to union bbox, remove fog masks, load all 3 territories
	$effect(() => {
		const isRegional = territoryStore.regionalMode;
		if (isRegional) {
			setTimeout(() => mapComponent?.flyToBbox(REGIONAL_NEA_BBOX), 100);
			mapComponent?.setRegionalMapMode(true);
			if (hexStore.activeLayer?.comparable) {
				const [p2, p3] = getRegionalOtherPrefixes();
				hexStore.loadFullCompare(p2).catch(() => {});
				hexStore.loadRegionalData(p3).catch(() => {});
			}
		} else {
			mapComponent?.setRegionalMapMode(false);
			mapComponent?.clearCompareHexChoropleth();
			mapComponent?.clearRegionalHexChoropleth();
			untrack(() => hexStore.clearCompareDept());
			untrack(() => hexStore.clearRegionalData());
			setTimeout(() => mapComponent?.flyToBbox(territoryStore.activeTerritory.bbox), 100);
		}
	});

	onMount(() => {
		// Auto-collapse sidebar on mobile so map is visible first
		if (window.innerWidth < 768) {
			showAbout = false;
		}

		// Restore state from URL params
		const params = new URLSearchParams(window.location.search);
		const territory = params.get('t');
		if (territory) territoryStore.setTerritory(territory);
		if (params.get('rm') === '0') territoryStore.exitRegionalMode();
		const lens = params.get('lens') as LensId | null;
		const analysisId = params.get('a');
		if (lens) {
			lensStore.setLens(lens);
			if (analysisId) {
				const a = getAnalysisById(analysisId);
				if (a) lensStore.setAnalysis(a);
			}
		}
		const tm = params.get('tm');
		if (tm === 'baseline' || tm === 'delta') hexStore.setTemporalMode(tm);

		initDuckDB()
			.then(() => {
				warmupRadioStats();
			})
			.catch(e => { console.warn('DuckDB init failed:', e); duckdbFailed = true; });

		mapContainer?.addEventListener('radio-select', ((e: CustomEvent) => {
			if (lassoStore.active) return;
			if (lensStore.activeAnalysis?.spatialUnit === 'catastro') return; // flood mode uses parcel clicks
			const { redcode, selected, census } = e.detail;

			// Dismiss welcome panel so ComparisonChart (petals) can render
			showAbout = false;

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

		mapContainer?.addEventListener('district-select', ((e: CustomEvent) => {
			showAbout = false;
			const { distrito, personas } = e.detail;
			mapStore.addDistrict(distrito, personas);
			mapComponent?.setDistrictHighlight(getDistrictHighlightEntries());
			fetchDistrictEnrichment(distrito);
		}) as EventListener);

		mapContainer?.addEventListener('district-deselect', ((e: CustomEvent) => {
			const { distrito } = e.detail;
			mapStore.removeDistrict(distrito);
			mapComponent?.setDistrictHighlight(getDistrictHighlightEntries());
		}) as EventListener);

		mapContainer?.addEventListener('compare-hex-select', ((e: CustomEvent) => {
			if (lassoStore.active) return;
			const { h3index } = e.detail;
			if (hexStore.activeLayer && hexStore.compareVisibleData.size > 0) {
				hexStore.selectCompareHex(h3index);
				hexStore.ensureProvincialAvgLoaded();
			}
		}) as EventListener);

		mapContainer?.addEventListener('hex-select', ((e: CustomEvent) => {
			if (lassoStore.active) return;
			const { h3index, properties } = e.detail;
			// Auto-switch territory in regional mode when clicking a hex from a different territory
			if (territoryStore.regionalMode) {
				const detected = inferTerritoryFromH3(h3index);
				if (detected && detected !== territoryStore.activeTerritory.id) {
					territoryStore.setTerritory(detected);
				}
			}
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

		mapContainer?.addEventListener('catastro-flood-select', ((e: CustomEvent) => {
			const { h3index, tipo, area_m2 } = e.detail;
			const floodData = mapStore.floodH3Data.get(h3index);
			if (floodData) {
				mapStore.addFloodParcel({
					h3index,
					tipo: tipo ?? 'urbano',
					area_m2: Number(area_m2) || 0,
					flood_risk_score: floodData.flood_risk_score,
					jrc_occurrence: floodData.jrc_occurrence,
					jrc_recurrence: floodData.jrc_recurrence,
					jrc_seasonality: floodData.jrc_seasonality,
					flood_extent_pct: floodData.flood_extent_pct,
				});
			}
		}) as EventListener);

		mapContainer?.addEventListener('catastro-scores-select', ((e: CustomEvent) => {
			const { h3index, tipo, area_m2 } = e.detail;
			const allData = mapStore.scoresH3Data.get(h3index);
			const scores: Record<string, number> = {};
			const components: Record<string, number> = {};
			if (allData) {
				for (const [key, val] of Object.entries(allData)) {
					scores[key] = Number(val) || 0;
				}
			}
			// Always add parcel (even without data — shows "sin datos" in UI)
			mapStore.addScoresParcel({
				h3index,
				tipo: tipo ?? 'urbano',
				area_m2: Number(area_m2) || 0,
				scores,
				components,
			});
		}) as EventListener);

		document.addEventListener('keydown', (e) => {
			if (e.key === 'Escape') {
				if (lassoStore.drawing) {
					lassoStore.cancelDraw();
					mapComponent?.clearLassoDraw();
				} else if (lassoStore.active) {
					handleToggleLasso();
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
	let prevLensId: string | null = null;

	$effect(() => {
		const lens = lensStore.activeLens;
		if (lens === prevLensId) return;
		prevLensId = lens;

		// Clear hex state on any lens change
		mapComponent?.clearHexChoropleth();
		mapComponent?.clearCompareHexChoropleth();
		mapComponent?.clearHexZoneHighlight();
		mapStore.clearHexState();
		hexStore.clearAll();
		prevDataVersion = hexStore.dataVersion;
		prevCompareDataVersion = hexStore.compareDataVersion;

		if (lens) {
			mapStore.clearRadios();
			mapComponent?.clearRadioHighlight();
			mapComponent?.clearAnalysisChoropleth();
		} else {
			mapComponent?.clearAnalysisChoropleth();
		}
	});

	function handleSelectAnalysis(analysis: AnalysisConfig) {
		showAbout = false;
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
	let showAbout = $state(false);

	// Auto-open welcome panel on first visit after terms acceptance
	const WELCOMED_KEY = 'spatia_welcomed_v1';
	let hasShownWelcome = typeof window !== 'undefined'
		? localStorage.getItem(WELCOMED_KEY) === 'true'
		: true;
	$effect(() => {
		if (terms.accepted && !hasShownWelcome) {
			showAbout = true;
			hasShownWelcome = true;
			if (typeof window !== 'undefined') localStorage.setItem(WELCOMED_KEY, 'true');
		}
	});

	// Dismiss welcome panel when user selects a lens
	$effect(() => {
		if (lensStore.activeLens) {
			showAbout = false;
		}
	});

	$effect(() => {
		const analysis = lensStore.activeAnalysis;
		const id = analysis?.id ?? null;

		if (id === prevAnalysisId) return;
		// Clean up previous analysis
		if (prevAnalysisId === 'catastro') {
			mapComponent?.hideCatastroLayer();
		}
		if (prevAnalysisId === 'flood_risk') {
			mapComponent?.clearCatastroFloodChoropleth();
			mapComponent?.clearFloodParcelHighlight();
			mapComponent?.hideCatastroLayer();
			mapStore.clearFloodParcelState();
		}
		if (['territorial_scores', 'investment_value', 'natural_risks',
			'productive_aptitude', 'accessibility', 'change_dynamics',
			'sociodemographic', 'forest_potential', 'economic_activity'].includes(prevAnalysisId ?? '')) {
			mapComponent?.clearCatastroScoresChoropleth();
			mapComponent?.clearFloodParcelHighlight();
			mapComponent?.hideCatastroLayer();
			mapStore.clearScoresParcelState();
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

		// Catastro-based analyses
		if (analysis.spatialUnit === 'catastro') {
			analysisDataLoaded = false;
			mapComponent?.clearAnalysisChoropleth();
			mapComponent?.clearHexChoropleth();
			mapStore.clearHexState();
			hexStore.clearAll();
			mapComponent?.showCatastroLayer();
			return;
		}

		// Hex-based analyses use HexStore multi-resolution system
		if (analysis.spatialUnit === 'hexagon' && (analysis.choropleth || HEX_LAYER_REGISTRY[analysis.id])) {
			analysisDataLoaded = false;
			mapComponent?.clearAnalysisChoropleth();
			const layerCfg = HEX_LAYER_REGISTRY[analysis.id];
			if (layerCfg) {
				hexStore.setLayer(analysis.id);
				hexStore.ensureColorDomain().catch(() => {});
				mapStore.setActiveHexLayer(analysis.id);
				mapComponent?.setHexLayerInfo(i18n.t(layerCfg.titleKey), layerCfg.colorScale === 'categorical');
				// Regional mode: also load data for the other 2 territories
				if (untrack(() => territoryStore.regionalMode) && layerCfg.comparable) {
					const [p2, p3] = getRegionalOtherPrefixes();
					hexStore.loadFullCompare(p2).catch(() => {});
					hexStore.loadRegionalData(p3).catch(() => {});
				}
			} else {
				// Fallback: direct load (legacy)
				loadHexChoropleth(analysis);
			}
			return;
		}

		// Radio-based analyses: load choropleth + catastro overlay
		if (analysis.choropleth && analysis.spatialUnit === 'radio') {
			analysisDataLoaded = false;
			mapComponent?.clearHexChoropleth();
			mapStore.clearHexState();
			loadAnalysisChoropleth(analysis);
		}
	});

	// ── HexStore reactivity: sync hex selection highlights with map ───────
	$effect(() => {
		const allHexes = [...hexStore.selectedHexes.entries()].map(([h3index, d]) => ({
			h3index, color: d.color
		}));
		const primary = allHexes.filter(h => hexStore.visibleData.has(h.h3index));
		const compare = allHexes.filter(h => hexStore.compareVisibleData.has(h.h3index));
		mapComponent?.highlightHexagons(primary, compare);
	});

	// ── Flood parcel selection highlights on catastro layer ───────────────
	$effect(() => {
		const parcels = mapStore.selectedFloodParcels;
		mapComponent?.setFloodParcelHighlight(
			parcels.map(p => ({ h3index: p.h3index, color: p.color }))
		);
	});

	// ── Scores parcel selection highlights on catastro layer ─────────────
	$effect(() => {
		const parcels = mapStore.selectedScoresParcels;
		mapComponent?.setScoresParcelHighlight(
			parcels.map(p => ({ h3index: p.h3index, color: p.color }))
		);
	});

	// ── HexStore reactivity: re-render choropleth when data changes ──────
	// For perDepartment layers, rendering is handled directly by handleSelectFloodDpto.
	// This $effect only handles non-perDepartment layers (legacy path).
	let prevDataVersion = 0;
	let prevCompareDataVersion = 0;
	let prevRegionalDataVersion = 0;

	$effect(() => {
		const version = hexStore.dataVersion;
		const entries = hexStore.choroplethEntries;
		const layer = hexStore.activeLayer;

		if (version === prevDataVersion) return;
		prevDataVersion = version;

		// Skip for perDepartment layers — rendered directly via handleSelectFloodDpto
		if (layer?.perDepartment) return;

		if (entries.length === 0) {
			mapComponent?.clearHexChoropleth();
			return;
		}

		let colorScale: 'flood' | 'sequential' | 'diverging' | 'categorical' | 'green' | 'warm' = layer?.colorScale ?? 'flood';
		if (layer?.temporal && hexStore.temporalMode === 'delta') colorScale = 'diverging';
		mapComponent?.setHexChoropleth(entries, colorScale, hexStore.colorDomain ?? undefined);
		analysisDataLoaded = true;
	});

	function handleShowLisa(entries: { h3index: string; value: number; boundary?: number[][] }[]) {
		if (entries.length === 0) {
			prevDataVersion = 0;
			const layer = hexStore.activeLayer;
			const cEntries = hexStore.choroplethEntries;
			if (cEntries.length === 0) { mapComponent?.clearHexChoropleth(); return; }
			let cs: 'flood' | 'sequential' | 'diverging' | 'categorical' | 'green' | 'warm' = layer?.colorScale ?? 'flood';
			if (layer?.temporal && hexStore.temporalMode === 'delta') cs = 'diverging';
			mapComponent?.setHexChoropleth(cEntries, cs, hexStore.colorDomain ?? undefined);
			return;
		}
		mapComponent?.setHexChoropleth(entries, 'lisa');
	}

	function handleMoranBrush(h3s: string[]) {
		if (h3s.length === 0) {
			mapComponent?.clearHexZoneHighlight();
			return;
		}
		mapComponent?.setHexZoneHighlight(
			[{ h3indices: h3s, color: '#fbbf24' }],
			hexStore.boundaryCache
		);
	}

	function handleHistogramBrush(h3s: string[]) {
		if (h3s.length === 0) {
			mapComponent?.clearHexZoneHighlight();
			return;
		}
		mapComponent?.setHexZoneHighlight(
			[{ h3indices: h3s, color: '#34d399' }],
			hexStore.boundaryCache
		);
	}

	function handleBivariateBrush(h3s: string[]) {
		if (h3s.length === 0) {
			mapComponent?.clearHexZoneHighlight();
			return;
		}
		mapComponent?.setHexZoneHighlight(
			[{ h3indices: h3s, color: '#fb923c' }],
			hexStore.boundaryCache
		);
	}

	function handleFlowBrush(h3s: string[]) {
		if (h3s.length === 0) { mapComponent?.clearHexZoneHighlight(); return; }
		mapComponent?.setHexZoneHighlight(
			[{ h3indices: h3s, color: '#a78bfa' }],
			hexStore.boundaryCache
		);
	}

	function handleParallelBrush(h3s: string[]) {
		if (h3s.length === 0) { mapComponent?.clearHexZoneHighlight(); return; }
		mapComponent?.setHexZoneHighlight(
			[{ h3indices: h3s, color: '#22d3ee' }],
			hexStore.boundaryCache
		);
	}

	// ── Compare choropleth: render compare dept hexes when compareDataVersion changes ──
	$effect(() => {
		const version = hexStore.compareDataVersion;
		const entries = hexStore.compareChoroplethEntries;
		const layer = hexStore.activeLayer;
		if (version === prevCompareDataVersion) return;
		prevCompareDataVersion = version;
		if (entries.length === 0) {
			mapComponent?.clearCompareHexChoropleth();
			return;
		}
		let colorScale: 'flood' | 'sequential' | 'diverging' | 'categorical' | 'green' | 'warm' = layer?.colorScale ?? 'sequential';
		mapComponent?.setCompareHexChoropleth(entries, colorScale, hexStore.colorDomain ?? undefined);
	});

	// ── Regional choropleth: render 3rd territory hexes when regionalDataVersion changes ──
	$effect(() => {
		const version = hexStore.regionalDataVersion;
		const entries = hexStore.regionalChoroplethEntries;
		const layer = hexStore.activeLayer;
		if (version === prevRegionalDataVersion) return;
		prevRegionalDataVersion = version;
		if (entries.length === 0) {
			mapComponent?.clearRegionalHexChoropleth();
			return;
		}
		const colorScale: 'flood' | 'sequential' | 'diverging' | 'categorical' | 'green' | 'warm' = layer?.colorScale ?? 'sequential';
		mapComponent?.setRegionalHexChoropleth(entries, colorScale, hexStore.colorDomain ?? undefined);
	});

	// ── Clear data load error when analysis changes ──────────────────────────
	$effect(() => {
		lensStore.activeAnalysis; // reactive dependency
		hexStore.clearLoadError();
	});

	// ── Dept bbox outlines + auto-fly when both depts are loaded ────────────
	$effect(() => {
		const p = hexStore.deptBbox;
		const c = hexStore.compareDeptBbox;
		mapComponent?.updateDeptHighlights(p, c);
		if (p && c) {
			const union: [number, number, number, number] = [
				Math.min(p[0], c[0]),
				Math.min(p[1], c[1]),
				Math.max(p[2], c[2]),
				Math.max(p[3], c[3])
			];
			mapComponent?.flyToBbox(union);
		}
	});

	// ── Clear compare dept when compare mode is exited ───────────────────
	$effect(() => {
		if (!territoryStore.compareModeActive) {
			untrack(() => hexStore.clearCompareDept());
		}
	});

	// ── Temporal mode toggle: re-render perDepartment layers on mode change ──
	let prevTemporalMode: string = 'current';
	$effect(() => {
		const mode = hexStore.temporalMode;
		const layer = hexStore.activeLayer;
		if (mode === prevTemporalMode) return;
		prevTemporalMode = mode;
		if (!layer?.temporal || !layer?.perDepartment) return;
		const entries = hexStore.choroplethEntries;
		if (entries.length === 0) return;
		let colorScale: 'flood' | 'sequential' | 'diverging' | 'categorical' = layer.colorScale ?? 'flood';
		if (mode === 'delta') colorScale = 'diverging';
		mapComponent?.setHexChoropleth(entries, colorScale, hexStore.colorDomain ?? undefined);
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

	function inferTerritoryFromH3(h3index: string): string | null {
		const [lat, lng] = cellToLatLng(h3index);
		if (isInsideMisiones(lat, lng)) return 'misiones';
		if (isInsideItapua(lat, lng)) return 'itapua_py';
		if (isInsideCorrientes(lat, lng)) return 'corrientes';
		return null;
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
			const isCorrientes = redcode.startsWith('18');
			if (isCorrientes) {
				const CORRIENTES_COLS = 'redcode, total_personas, area_km2, tasa_actividad, tasa_empleo, pct_universitario, pct_nbi, pct_hacinamiento';
				const result = await query(
					`SELECT ${CORRIENTES_COLS} FROM '${PARQUETS.radio_stats_corrientes}' WHERE redcode = '${redcode}' LIMIT 1`
				);
				if (result.numRows === 0) return;
				mapStore.updateEnriched(redcode, result.get(0)!.toJSON());
			} else {
				const ENRICHMENT_COLS = 'redcode, total_personas, area_km2, tasa_actividad, tasa_empleo, pct_universitario, pct_nbi, pct_hacinamiento, pct_agua_red';
				const result = await query(
					`SELECT ${ENRICHMENT_COLS} FROM '${PARQUETS.radio_stats_master}' WHERE redcode = '${redcode}' LIMIT 1`
				);
				if (result.numRows === 0) return;
				mapStore.updateEnriched(redcode, result.get(0)!.toJSON());
			}
		} catch (e) {
			console.warn('DuckDB enrichment failed:', e);
		}
	}

	// ── Radio export handlers (CSV / GeoJSON / summary) ─────────────────────
	async function downloadRadioCsv(redcode: string): Promise<void> {
		const { downloadCsvFromQuery } = await import('$lib/utils/data-export');
		await downloadCsvFromQuery(
			`SELECT * FROM '${PARQUETS.radio_stats_master}' WHERE redcode = '${redcode}' LIMIT 1`,
			`spatia_radio_${redcode}.csv`
		);
	}

	function downloadRadioGeoJson(redcode: string, properties: Record<string, any>): void {
		const geometry = mapComponent?.getRadioGeometry(redcode);
		if (!geometry) {
			console.warn('Radio geometry not available for', redcode);
			return;
		}
		const fc = {
			type: 'FeatureCollection',
			features: [{ type: 'Feature', geometry, properties: { redcode, ...properties } }]
		};
		const blob = new Blob([JSON.stringify(fc)], { type: 'application/geo+json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `spatia_radio_${redcode}.geojson`;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	}

	async function downloadRadiosSummary(): Promise<void> {
		const { downloadCsvFromRows } = await import('$lib/utils/data-export');
		const rows: Array<Record<string, unknown>> = [];
		for (const [rc, d] of mapStore.selectedRadios.entries()) {
			const e = d.enriched ?? {};
			rows.push({
				redcode: rc,
				total_personas: e.total_personas,
				area_km2: e.area_km2,
				tasa_actividad: e.tasa_actividad,
				tasa_empleo: e.tasa_empleo,
				pct_universitario: e.pct_universitario,
				pct_nbi: e.pct_nbi,
				pct_hacinamiento: e.pct_hacinamiento,
				pct_agua_red: e.pct_agua_red
			});
		}
		if (rows.length === 0) return;
		const cols = Object.keys(rows[0]);
		downloadCsvFromRows(rows, cols, 'spatia_radios_summary.csv');
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

	function getDistrictHighlightEntries(): Array<{distrito: string, color: string}> {
		return [...mapStore.selectedDistricts.entries()].map(([d, data]) => ({distrito: d, color: data.color}));
	}

	async function fetchDistrictEnrichment(distrito: string): Promise<void> {
		try {
			await initDuckDB();
			const result = await query(`SELECT * FROM '${PARQUETS.district_stats_itapua}' WHERE distrito = '${distrito.replace(/'/g, "''")}' LIMIT 1`);
			if (result.numRows > 0) {
				mapStore.updateDistrictEnriched(distrito, result.get(0)!.toJSON() as Record<string, any>);
			}
		} catch (e) {
			console.warn('District enrichment fetch failed:', e);
		}
	}

	function handleRemoveDistrict(distrito: string) {
		mapStore.removeDistrict(distrito);
		mapComponent?.setDistrictHighlight(getDistrictHighlightEntries());
	}

	function handleClearDistricts() {
		mapStore.clearDistricts();
		mapComponent?.setDistrictHighlight([]);
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

	function handleSelectCatastroDpto(centroid: [number, number] | null, deptCode?: string | null) {
		if (centroid && deptCode) {
			mapComponent?.showCatastroLayer();
			mapComponent?.filterCatastroDept(deptCode);
			mapComponent?.flyToCoords(centroid[0], centroid[1], 12);
		} else {
			mapComponent?.filterCatastroDept(null);
			mapComponent?.flyToProvince();
		}
	}

	async function handleSelectFloodCatastroDpto(dpto: string, parquetKey: string, centroid: [number, number]) {
		// Load per-dept hex flood data and color catastro parcels
		try {
			await initDuckDB();
			const { getFloodDptoUrl } = await import('$lib/config');
			const url = getFloodDptoUrl(parquetKey);
			const result = await query(
				`SELECT h3index, flood_risk_score, jrc_occurrence, jrc_recurrence, jrc_seasonality, flood_extent_pct FROM '${url}' WHERE flood_risk_score IS NOT NULL`
			);

			const h3ScoreMap = new Map<string, number>();
			const h3FullData = new Map<string, Record<string, number>>();
			const floodLats: number[] = [];
			const floodLngs: number[] = [];
			for (let i = 0; i < result.numRows; i++) {
				const row = result.get(i)!.toJSON() as Record<string, any>;
				const [lat, lng] = cellToLatLng(row.h3index);
				if (!isInsideMisiones(lat, lng)) continue;
				h3ScoreMap.set(row.h3index, Number(row.flood_risk_score) || 0);
				h3FullData.set(row.h3index, {
					flood_risk_score: Number(row.flood_risk_score) || 0,
					jrc_occurrence: Number(row.jrc_occurrence) || 0,
					jrc_recurrence: Number(row.jrc_recurrence) || 0,
					jrc_seasonality: Number(row.jrc_seasonality) || 0,
					flood_extent_pct: Number(row.flood_extent_pct) || 0,
				});
				floodLats.push(lat); floodLngs.push(lng);
			}

			mapStore.setFloodH3Data(h3FullData);
			mapComponent?.setCatastroFloodChoropleth(h3ScoreMap);
			if (floodLats.length > 0) {
				mapComponent?.fitBoundsDept([Math.min(...floodLngs), Math.min(...floodLats), Math.max(...floodLngs), Math.max(...floodLats)]);
			} else {
				mapComponent?.flyToCoords(centroid[1], centroid[0], 11);
			}
		} catch (e) {
			console.warn('Failed to load flood catastro data:', e);
		}
	}

	async function handleSelectScoresCatastroDpto(dpto: string, parquetKey: string, centroid: [number, number]) {
		try {
			await initDuckDB();
			const { getScoresDptoUrl } = await import('$lib/config');
			const url = getScoresDptoUrl(parquetKey);
			const result = await query(`SELECT * FROM '${url}'`);

			const h3ScoreMap = new Map<string, number>();
			const h3FullData = new Map<string, Record<string, number>>();
			const scoreLats: number[] = [];
			const scoreLngs: number[] = [];
			for (let i = 0; i < result.numRows; i++) {
				const row = result.get(i)!.toJSON() as Record<string, any>;
				const h3 = row.h3index as string;
				const [lat, lng] = cellToLatLng(h3);
				if (!isInsideMisiones(lat, lng)) continue;
				// Use urban_consolidation as default choropleth indicator
				h3ScoreMap.set(h3, Number(row.urban_consolidation) || 0);
				const data: Record<string, number> = {};
				for (const key of Object.keys(row)) {
					if (key !== 'h3index') data[key] = Number(row[key]) || 0;
				}
				h3FullData.set(h3, data);
				scoreLats.push(lat); scoreLngs.push(lng);
			}

			mapStore.setScoresH3Data(h3FullData);
			mapComponent?.setCatastroScoresChoropleth(h3ScoreMap);
			if (scoreLats.length > 0) {
				mapComponent?.fitBoundsDept([Math.min(...scoreLngs), Math.min(...scoreLats), Math.max(...scoreLngs), Math.max(...scoreLats)]);
			} else {
				mapComponent?.flyToCoords(centroid[1], centroid[0], 11);
			}
		} catch (e) {
			console.warn('Failed to load scores catastro data:', e);
		}
	}

	async function handleSelectRadioAnalysisDpto(dpto: string, analysisId: string, centroid: [number, number]) {
		// Fly immediately (centroid from static JSON, no query needed)
		mapComponent?.flyToCoords(centroid[1], centroid[0], 9);

		try {
			await initDuckDB();
			const { RADIO_ANALYSIS_REGISTRY, PARQUETS } = await import('$lib/config');
			const config = RADIO_ANALYSIS_REGISTRY[analysisId];
			if (!config) return;

			// Get all columns we need from radio_stats_master
			const allCols = [...new Set([...config.petalCols.filter(c => !c.source).map(c => c.col), config.choroplethCol])];
			const colList = allCols.map(c => `rs.${c}`).join(', ');

			const result = await query(`
				SELECT xw.h3index, ${colList}
				FROM '${PARQUETS.h3_radio_crosswalk}' xw
				JOIN '${PARQUETS.radio_stats_master}' rs ON xw.redcode = rs.redcode
				WHERE rs.dpto = '${dpto.replace(/'/g, "''")}'
			`);

			const h3ScoreMap = new Map<string, number>();
			const h3FullData = new Map<string, Record<string, number>>();

			// First pass: collect raw choropleth values for min/max normalization
			const rawValues: number[] = [];
			const rows: Array<Record<string, any>> = [];
			for (let i = 0; i < result.numRows; i++) {
				const row = result.get(i)!.toJSON() as Record<string, any>;
				rows.push(row);
				rawValues.push(Number(row[config.choroplethCol]) || 0);
			}
			let cMin = Infinity, cMax = -Infinity;
			for (const v of rawValues) { if (v < cMin) cMin = v; if (v > cMax) cMax = v; }
			const cRange = cMax - cMin || 1;

			// Second pass: normalize choropleth to 0-100, store all data
			for (const row of rows) {
				const h3 = row.h3index as string;
				const val = Number(row[config.choroplethCol]) || 0;
				let normalized = ((val - cMin) / cRange) * 100;
				if (config.invertChoropleth) normalized = 100 - normalized;
				h3ScoreMap.set(h3, Math.round(normalized));
				const data: Record<string, number> = {};
				for (const col of allCols) {
					data[col] = Number(row[col]) || 0;
				}
				h3FullData.set(h3, data);
			}

			// Load catastro_by_radio cols if needed (e.g., n_new_parcels_90d)
			const catCols = config.petalCols.filter(c => c.source === 'catastro_by_radio');
			if (catCols.length > 0) {
				const catColList = catCols.map(c => `cb.${c.col}`).join(', ');
				const catResult = await query(`
					SELECT xw.h3index, ${catColList}
					FROM '${PARQUETS.h3_radio_crosswalk}' xw
					JOIN '${PARQUETS.catastro_by_radio}' cb ON xw.redcode = cb.redcode
					WHERE cb.redcode IN (
						SELECT redcode FROM '${PARQUETS.radio_stats_master}' WHERE dpto = '${dpto.replace(/'/g, "''")}'
					)
				`);
				for (let i = 0; i < catResult.numRows; i++) {
					const row = catResult.get(i)!.toJSON() as Record<string, any>;
					const h3 = row.h3index as string;
					const existing = h3FullData.get(h3) || {};
					for (const c of catCols) {
						existing[c.col] = Number(row[c.col]) || 0;
					}
					h3FullData.set(h3, existing);
				}
			}

			// Data loaded successfully
			mapStore.setScoresH3Data(h3FullData);
			mapComponent?.setCatastroScoresChoropleth(h3ScoreMap);
		} catch (e) {
			console.error('[RadioAnalysis] Failed:', e);
		}
	}

	async function handleSelectFloodDpto(dpto: string, parquetKey: string, centroid: [number, number]) {
		mapComponent?.clearHexChoropleth();
		mapComponent?.clearHexZoneHighlight();
		mapStore.setActiveHexLayer(hexStore.activeLayer?.id ?? null);
		if (hexStore.activeLayer) {
			mapComponent?.setHexLayerInfo(i18n.t(hexStore.activeLayer.titleKey), hexStore.activeLayer.colorScale === 'categorical');
		}
		await hexStore.loadDepartment(dpto, parquetKey);
		// Compute provincial min/max for consistent cross-department coloring
		await hexStore.ensureColorDomain().catch(() => {});
		prevDataVersion = hexStore.dataVersion;
		// Render outside Svelte's reactive batch to prevent $effect interference
		setTimeout(() => {
			const allEntries = hexStore.choroplethEntries;
			const entries = allEntries.filter(e => {
				const [lat, lng] = cellToLatLng(e.h3index);
				return hexStore.territoryPrefix === 'itapua_py/'
					? isInsideItapua(lat, lng)
					: hexStore.territoryPrefix === 'corrientes/'
					? isInsideCorrientes(lat, lng)
					: isInsideMisiones(lat, lng);
			});
			if (entries.length > 0) {
				let colorScale: 'flood' | 'sequential' | 'diverging' | 'categorical' = hexStore.activeLayer?.colorScale ?? 'flood';
				if (hexStore.activeLayer?.temporal && hexStore.temporalMode === 'delta') colorScale = 'diverging';
				mapComponent?.setHexChoropleth(entries, colorScale, hexStore.colorDomain ?? undefined);
				analysisDataLoaded = true;
				const hexLats = entries.map(e => cellToLatLng(e.h3index)[0]);
				const hexLngs = entries.map(e => cellToLatLng(e.h3index)[1]);
				mapComponent?.fitBoundsDept([Math.min(...hexLngs), Math.min(...hexLats), Math.max(...hexLngs), Math.max(...hexLats)]);
			} else {
				mapComponent?.flyToCoords(centroid[1], centroid[0], 10);
			}
		}, 20);
	}

	function clearAll() {
		mapStore.clearRadios();
		mapStore.clearDistricts();
		mapStore.clearHexState();
		mapComponent?.setHexLayerInfo('', false);
		mapStore.clearFloodParcelState();
		mapStore.clearScoresParcelState();
		hexStore.clearAll();
		mapComponent?.clearRadioHighlight();
		mapComponent?.setDistrictHighlight([]);
		mapComponent?.clearAnalysisChoropleth();
		mapComponent?.clearHexChoropleth();
		mapComponent?.clearHexZoneHighlight();
		mapComponent?.clearCatastroFloodChoropleth();
		mapComponent?.clearCatastroScoresChoropleth();
		mapComponent?.clearFloodParcelHighlight();
		lensStore.clearSelection();
		lensStore.clearDpto();
		lensStore.clearAnalysis();
		lassoStore.clearZones();
		mapComponent?.clearZoneHighlight();
		if (lassoStore.active) {
			lassoStore.toggle();
			mapComponent?.setLassoMode(false);
		}
		showAbout = true;
	}

</script>

<div class="flex h-screen w-full">
	<!-- Territory column: vertical list, always visible -->
	<div class="territory-col">
		<TerritorySelector {territoryStore} activeCoverage={hexStore.activeLayer?.coverage} />
	</div>

	<!-- Map + overlays -->
	<div class="flex-1 flex flex-col relative min-w-0">
		<!-- Header -->
		<div class="app-header flex items-center justify-between px-4 py-2.5 border-b border-border z-10 shrink-0"
			style="background: rgba(10,12,18,0.88); backdrop-filter: blur(8px);">
			<div class="flex items-center gap-4">
				<h1 class="app-title text-[15px] font-bold text-white tracking-wide cursor-pointer hover:opacity-80 transition-opacity" onclick={clearAll}>
					{i18n.t('header.title')}
				</h1>
				<button
					class="text-[12px] text-white/70 hover:text-white cursor-pointer transition-colors border border-white/20 rounded px-2 py-0.5"
					onclick={() => { showAbout = !showAbout; }}
					title={i18n.t('header.whatIsThis')}>
					{i18n.t('header.whatIsThis')}
				</button>
			</div>

			<!-- Lens selector (center) -->
			<LensSelector {lensStore} />

			<div class="flex items-center gap-0.5">
				{#each (['es', 'en', 'gn'] as Locale[]) as lang}
					<button
						class="px-2.5 py-1 text-[11px] font-semibold rounded-full cursor-pointer border transition-all {i18n.locale === lang ? 'bg-white/10 text-white border-white/30' : 'bg-transparent text-white/50 border-transparent hover:text-white'}"
						onclick={() => i18n.setLocale(lang)}>
						{lang.toUpperCase()}
					</button>
				{/each}
			</div>
		</div>

		<!-- Map container -->
		<div bind:this={mapContainer} class="flex-1 relative min-h-0">
			<MapComponent bind:this={mapComponent} {mapStore} />
			<MapLegend {hexStore} />

			{#if hexStore.loading}
				<div class="loading-overlay">
					<div class="loading-spinner"></div>
					<span class="loading-text">{i18n.t('analysis.loading')}</span>
				</div>
			{/if}

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
				{territoryStore}
				{showAbout}
				onRemoveRadio={handleRemoveRadio}
				onClearRadios={handleClearRadios}
				onSelectAnalysis={handleSelectAnalysis}
				onRemoveZone={handleRemoveZone}
				onClearZones={handleClearZones}
				onRemoveHexZone={handleRemoveHexZone}
				onClearHexZones={handleClearHexZones}
				onSelectFloodDpto={handleSelectFloodDpto}
				onSelectFloodCatastroDpto={handleSelectFloodCatastroDpto}
			onSelectCatastroDpto={handleSelectCatastroDpto}
			onSelectScoresCatastroDpto={handleSelectScoresCatastroDpto}
			onSelectRadioAnalysisDpto={handleSelectRadioAnalysisDpto}
			onDownloadRadioCsv={downloadRadioCsv}
			onDownloadRadioGeoJson={downloadRadioGeoJson}
			onDownloadRadiosSummary={downloadRadiosSummary}
			onShowLisa={handleShowLisa}
			onMoranBrush={handleMoranBrush}
			onHistogramBrush={handleHistogramBrush}
			onBivariateBrush={handleBivariateBrush}
			onParallelBrush={handleParallelBrush}
			onFlowBrush={handleFlowBrush}
			onRemoveDistrict={handleRemoveDistrict}
			onClearDistricts={handleClearDistricts}
			/>
		</div>
	</div>
</div>

{#if duckdbFailed || hexStore.loadError}
	<div style="position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;align-items:flex-start;gap:12px;border-radius:10px;border:1px solid rgba(239,68,68,0.35);background:rgba(23,5,5,0.92);padding:12px 16px;backdrop-filter:blur(8px);max-width:280px;box-shadow:0 4px 24px rgba(0,0,0,0.6)">
		<span style="font-size:12px;color:#fca5a5;line-height:1.5;flex:1">
			{duckdbFailed ? i18n.t('error.engineFailed') : i18n.t('error.dataLoadFailed')}
		</span>
		<button
			style="background:none;border:none;cursor:pointer;color:rgba(252,165,165,0.5);font-size:16px;line-height:1;padding:0;flex-shrink:0"
			onclick={() => { duckdbFailed = false; hexStore.clearLoadError(); }}
		>✕</button>
	</div>
{/if}

<style>
	.territory-col {
		width: 145px;
		flex-shrink: 0;
		background: rgba(10, 12, 18, 0.88);
		backdrop-filter: blur(8px);
		border-right: 1px solid rgba(255, 255, 255, 0.07);
		overflow-y: auto;
		padding: 10px 6px 16px;
		scrollbar-width: thin;
		scrollbar-color: #334155 transparent;
	}
	@media (max-width: 768px) {
		.territory-col { display: none; }
	}

	.loading-overlay {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		background: rgba(10, 12, 18, 0.5);
		z-index: 8;
		pointer-events: none;
	}
	.loading-spinner {
		width: 18px;
		height: 18px;
		border: 2px solid rgba(255,255,255,0.15);
		border-top-color: #60a5fa;
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}
	.loading-text {
		font-size: 12px;
		color: rgba(255,255,255,0.7);
		font-weight: 500;
	}
	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 768px) {
		.app-header {
			padding: 6px 8px;
			flex-wrap: wrap;
			gap: 4px;
		}
		.app-title {
			font-size: 13px;
		}
	}
</style>
