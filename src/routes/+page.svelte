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
	import { PARQUETS, MAP_INIT, HEX_LAYER_REGISTRY, type AnalysisConfig } from '$lib/config';
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
				warmupRadioStats();
			})
			.catch(e => console.warn('DuckDB init failed:', e));

		// No animation — map starts directly at Posadas with 3D buildings

		mapContainer?.addEventListener('radio-select', ((e: CustomEvent) => {
			if (lassoStore.active) return;
			if (lensStore.activeAnalysis?.spatialUnit === 'catastro') return; // flood mode uses parcel clicks
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
		mapComponent?.clearHexZoneHighlight();
		mapStore.clearHexState();
		hexStore.clearAll();
		prevDataVersion = hexStore.dataVersion;

		if (lens) {
			mapStore.clearRadios();
			mapComponent?.clearRadioHighlight();
			mapComponent?.clearChatHighlights();
			mapComponent?.clearAnalysisChoropleth();
		} else {
			mapComponent?.clearAnalysisChoropleth();
		}
	});

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

		// Catastro-based analyses (flood risk on parcels)
		if (analysis.spatialUnit === 'catastro') {
			analysisDataLoaded = false;
			mapComponent?.clearAnalysisChoropleth();
			mapComponent?.clearHexChoropleth();
			mapStore.clearHexState();
			hexStore.clearAll();
			// Show catastro layer — flood coloring happens when user selects a dept
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
				mapStore.setActiveHexLayer(analysis.id);
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
			// Show catastro parcel overlay when catastro analysis is active
			if (id === 'catastro') {
				mapComponent?.showCatastroLayer();
			}
		}
	});

	// ── HexStore reactivity: sync hex selection highlights with map ───────
	$effect(() => {
		const hexes = [...hexStore.selectedHexes.entries()].map(([h3index, d]) => ({
			h3index, color: d.color
		}));
		mapComponent?.highlightHexagons(hexes);
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
			// Just fly — keep buildings, radios, and choropleth visible
			mapComponent?.flyToCoords(centroid[0], centroid[1], 10);
		} else {
			// Back to province view
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
			for (let i = 0; i < result.numRows; i++) {
				const row = result.get(i)!.toJSON() as Record<string, any>;
				h3ScoreMap.set(row.h3index, Number(row.flood_risk_score) || 0);
				h3FullData.set(row.h3index, {
					flood_risk_score: Number(row.flood_risk_score) || 0,
					jrc_occurrence: Number(row.jrc_occurrence) || 0,
					jrc_recurrence: Number(row.jrc_recurrence) || 0,
					jrc_seasonality: Number(row.jrc_seasonality) || 0,
					flood_extent_pct: Number(row.flood_extent_pct) || 0,
				});
			}

			mapStore.setFloodH3Data(h3FullData);
			mapComponent?.setCatastroFloodChoropleth(h3ScoreMap);
			mapComponent?.flyToCoords(centroid[1], centroid[0], 11);
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
			for (let i = 0; i < result.numRows; i++) {
				const row = result.get(i)!.toJSON() as Record<string, any>;
				const h3 = row.h3index as string;
				// Use urban_consolidation as default choropleth indicator
				h3ScoreMap.set(h3, Number(row.urban_consolidation) || 0);
				const data: Record<string, number> = {};
				for (const key of Object.keys(row)) {
					if (key !== 'h3index') data[key] = Number(row[key]) || 0;
				}
				h3FullData.set(h3, data);
			}

			mapStore.setScoresH3Data(h3FullData);
			mapComponent?.setCatastroScoresChoropleth(h3ScoreMap);
			mapComponent?.flyToCoords(centroid[1], centroid[0], 11);
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
		mapStore.clearFloodParcelState();
		mapStore.clearScoresParcelState();
		hexStore.clearAll();
		mapComponent?.clearRadioHighlight();
		mapComponent?.clearChatHighlights();
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
			<h1 class="text-[15px] font-bold text-white tracking-wide cursor-pointer hover:opacity-80 transition-opacity" onclick={clearAll}>
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
			/>
		</div>
	</div>
</div>
