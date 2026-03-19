<script lang="ts">
	import { onMount } from 'svelte';
	import MapComponent from '$lib/components/Map.svelte';
	import Controls from '$lib/components/Controls.svelte';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import ChatPanel from '$lib/components/ChatPanel.svelte';
	import LensSelector from '$lib/components/LensSelector.svelte';
	import { MapStore } from '$lib/stores/map.svelte';
	import { LensStore } from '$lib/stores/lens.svelte';
	import { initDuckDB, query, isReady } from '$lib/stores/duckdb';
	import { PARQUETS, LENS_CONFIG, MAP_INIT } from '$lib/config';
	import { i18n, type Locale } from '$lib/stores/i18n.svelte';

	const mapStore = new MapStore();
	const lensStore = new LensStore();

	let mapComponent: ReturnType<typeof MapComponent>;
	let mapContainer: HTMLDivElement;
	let chatCollapsed = $state(true);

	onMount(() => {
		initDuckDB()
			.then(() => lensStore.loadData())
			.catch(e => console.warn('DuckDB init failed:', e));

		mapContainer?.addEventListener('radio-select', ((e: CustomEvent) => {
			const { redcode, selected, census } = e.detail;

			// If lens is active and radio is an opportunity, let $effects handle map
			if (lensStore.activeLens) {
				if (lensStore.comparisonMode) {
					lensStore.selectOpportunity(redcode);
					return;
				}
				if (lensStore.isOpportunity(redcode)) {
					lensStore.selectOpportunity(redcode);
					return;
				}
			}

			// Default behavior: clear chat highlights, add radio
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
				if (lensStore.comparisonMode) {
					lensStore.cancelComparison();
				} else if (lensStore.selectedOpportunity) {
					lensStore.clearSelection();
				} else if (lensStore.selectedDpto) {
					handleBackToDepts();
				} else {
					clearAll();
				}
			}
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
			mapStore.lensActive = true;
			mapComponent?.updateColorExpr();
			const redcodes = [...lensStore.opportunityRadios.keys()];
			mapComponent?.setOpportunityGlow(redcodes, cfg.color);
			// Clear any existing selection highlights
			mapComponent?.clearRadioHighlight();
			mapComponent?.clearChatHighlights();
		} else {
			mapStore.lensActive = false;
			mapComponent?.updateColorExpr();
			mapComponent?.clearOpportunityGlow();
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

	// ── Selected opportunity reactivity ──────────────────────────────────────
	let prevOpp: string | null = null;

	$effect(() => {
		const opp = lensStore.selectedOpportunity;
		if (opp === prevOpp) return;
		prevOpp = opp;

		if (!lensStore.activeLens) return;
		const cfg = LENS_CONFIG[lensStore.activeLens];

		if (opp) {
			mapComponent?.highlightSingleOpportunity(opp, cfg.color);
			const c = lensStore.radioCentroid(opp);
			if (c) mapComponent?.flyToCoords(c[0], c[1], 14);
		} else {
			mapComponent?.clearRadioHighlight();
		}
	});

	// ── Comparison radio reactivity ──────────────────────────────────────────
	let prevCompRadio: string | null = null;

	$effect(() => {
		const compRadio = lensStore.comparisonRadio;
		if (compRadio === prevCompRadio) return;
		prevCompRadio = compRadio;

		if (!lensStore.activeLens || !lensStore.selectedOpportunity) return;
		const cfg = LENS_CONFIG[lensStore.activeLens];

		if (compRadio) {
			// Both radios highlighted: A with lens color, B with violet
			mapComponent?.highlightComparisonPair(
				lensStore.selectedOpportunity, cfg.color,
				compRadio, '#a78bfa'
			);
		} else {
			// Comparison cancelled: restore only radio A
			mapComponent?.highlightSingleOpportunity(lensStore.selectedOpportunity, cfg.color);
		}
	});

	function handleSelectDpto(dpto: string) {
		lensStore.selectDpto(dpto);
	}

	function handleSelectRadio(redcode: string) {
		if (lensStore.activeLens && lensStore.isOpportunity(redcode)) {
			lensStore.selectOpportunity(redcode);
		}
	}

	function handleBackToDepts() {
		lensStore.clearDpto();
	}

	async function fetchRadioEnrichment(redcode: string): Promise<void> {
		if (!isReady()) return;
		if (!/^\d{9}$/.test(redcode)) return;
		try {
			const ENRICHMENT_COLS = 'redcode, total_personas, total_hogares, varones, tasa_empleo, pct_nbi';
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

	function clearAll() {
		mapStore.clearRadios();
		mapStore.clearChatState();
		mapComponent?.clearRadioHighlight();
		mapComponent?.clearChatHighlights();
		lensStore.clearSelection();
		lensStore.clearDpto();
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
			/>

			<!-- Sidebar (positioned relative to map) -->
			<Sidebar
				{mapStore}
				{lensStore}
				onRemoveRadio={handleRemoveRadio}
				onSelectDpto={handleSelectDpto}
				onSelectRadio={handleSelectRadio}
			/>
		</div>
	</div>
</div>
