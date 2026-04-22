<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { Protocol } from 'pmtiles';
	import { getTilesUrl, BASEMAP, MAP_INIT, MAP_PROVINCE, TERRAIN_CONFIG } from '$lib/config';
	import { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import misionesBoundary from '$lib/data/misiones_boundary.json';
	import misionesMask from '$lib/data/misiones_mask.json';
	import itapuaBoundary from '$lib/data/itapua_boundary.json';
	import itapuaMask from '$lib/data/itapua_mask.json';

	let { mapStore }: { mapStore: MapStore } = $props();

	let container: HTMLDivElement;
	let hexLayerTitle = '';
	let hexLayerIsCategorical = false;
	let map: maplibregl.Map;
	let lassoActive = false;
	let catastroActive = false;
	let activeTerritoryId = 'misiones';

	onMount(() => {
		const protocol = new Protocol();
		maplibregl.addProtocol('pmtiles', protocol.tile);

		map = new maplibregl.Map({
			container,
			style: BASEMAP,
			center: MAP_INIT.center,
			zoom: MAP_INIT.zoom,
			pitch: MAP_INIT.pitch,
			bearing: MAP_INIT.bearing,
			minZoom: MAP_INIT.minZoom,
			maxZoom: MAP_INIT.maxZoom,
			antialias: true,
			attributionControl: false
		});

		map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right');
		map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left');

		map.on('error', (e) => console.error('MAP ERROR:', e.error?.message || e));

		map.on('load', () => {
			// Terrain DEM source (AWS Terrain Tiles, Terrarium encoding)
			map.addSource('terrain-dem', {
				type: 'raster-dem',
				tiles: [getTilesUrl('terrain')],
				encoding: 'terrarium',
				tileSize: 256
			});

			// Activate 3D terrain
			map.setTerrain({ source: 'terrain-dem', exaggeration: TERRAIN_CONFIG.exaggeration });

			// Radios source (PMTiles) — province boundary context
			map.addSource('radios', { type: 'vector', url: getTilesUrl('radios') });

			// Mask: fog outside Misiones (light overlay on dark basemap)
			map.addSource('mask', { type: 'geojson', data: misionesMask as any });
			map.addLayer({
				id: 'mask-fill',
				type: 'fill',
				source: 'mask',
				paint: { 'fill-color': '#1a1a2e', 'fill-opacity': 0.75 }
			});

			// Mask: fog outside Itapúa — same style, hidden until territory switches
			map.addSource('itapua-mask', { type: 'geojson', data: itapuaMask as any });
			map.addLayer({
				id: 'itapua-mask-fill',
				type: 'fill',
				source: 'itapua-mask',
				layout: { visibility: 'none' },
				paint: { 'fill-color': '#1a1a2e', 'fill-opacity': 0.75 }
			});

			// Hillshade (subtle, complements dark basemap)
			map.addLayer({
				id: 'hillshade',
				type: 'hillshade',
				source: 'terrain-dem',
				paint: {
					'hillshade-shadow-color': TERRAIN_CONFIG.hillshade.shadowColor,
					'hillshade-highlight-color': TERRAIN_CONFIG.hillshade.highlightColor,
					'hillshade-illumination-direction': TERRAIN_CONFIG.hillshade.illuminationDirection,
					'hillshade-exaggeration': TERRAIN_CONFIG.hillshade.exaggeration
				}
			});


				// Province fill
			map.addLayer({
				id: 'province-fill',
				type: 'fill',
				source: 'radios',
				'source-layer': 'radios',
				paint: { 'fill-color': '#60a5fa', 'fill-opacity': 0.06 }
			});

			// Province/radio borders
			map.addLayer({
				id: 'province-line',
				type: 'line',
				source: 'radios',
				'source-layer': 'radios',
				paint: {
					'line-color': '#d4d4d4',
					'line-width': [
						'interpolate', ['linear'], ['zoom'],
						6, 1.2,
						10, 0.6,
						14, 0.3
					],
					'line-opacity': [
						'interpolate', ['linear'], ['zoom'],
						6, 0.3,
						10, 0.25,
						14, 0.15
					]
				}
			});

			// Province border: neon green outline
			map.addSource('province-boundary', { type: 'geojson', data: misionesBoundary as any });
			map.addLayer({
				id: 'province-border',
				type: 'line',
				source: 'province-boundary',
				paint: {
					'line-color': '#f472b6',
					'line-width': [
						'interpolate', ['linear'], ['zoom'],
						6, 1.2,
						9, 1.0,
						12, 0.8,
						16, 0.5
					],
					'line-opacity': [
						'interpolate', ['linear'], ['zoom'],
						6, 0.7,
						12, 0.5,
						16, 0.3
					]
				},
				layout: { 'line-join': 'round', 'line-cap': 'round' }
			});

			// Itapúa territory border — always visible, indicates available coverage
			map.addSource('itapua-boundary', { type: 'geojson', data: itapuaBoundary as any });
			map.addLayer({
				id: 'itapua-border',
				type: 'line',
				source: 'itapua-boundary',
				paint: {
					'line-color': '#f472b6',
					'line-width': [
						'interpolate', ['linear'], ['zoom'],
						6, 1.2,
						9, 1.0,
						12, 0.8,
						16, 0.5
					],
					'line-opacity': [
						'interpolate', ['linear'], ['zoom'],
						6, 0.7,
						12, 0.5,
						16, 0.3
					]
				},
				layout: { 'line-join': 'round', 'line-cap': 'round' }
			});

			// Buildings source (PMTiles)
			map.addSource('buildings', { type: 'vector', url: getTilesUrl('buildings') });

			// 3D fill-extrusion layer
			map.addLayer({
				id: 'buildings-3d',
				type: 'fill-extrusion',
				source: 'buildings',
				'source-layer': 'buildings',
				paint: {
					'fill-extrusion-height': ['max', ['coalesce', ['get', 'best_height_m'], 5], 5],
					'fill-extrusion-base': 0,
					'fill-extrusion-color': mapStore.getColorExpr() as any,
					'fill-extrusion-opacity': 0.92
				}
			});

			// Itapúa buildings (pre-created, hidden until territory switch)
			map.addSource('itapua-buildings', { type: 'vector', url: getTilesUrl('itapua_buildings') });
			map.addLayer({
				id: 'itapua-buildings-3d',
				type: 'fill-extrusion',
				source: 'itapua-buildings',
				'source-layer': 'buildings',
				layout: { visibility: 'none' },
				paint: {
					'fill-extrusion-height': ['max', ['coalesce', ['get', 'best_height_m'], 5], 5],
					'fill-extrusion-base': 0,
					'fill-extrusion-color': mapStore.getHeightColorExpr() as any,
					'fill-extrusion-opacity': 0.92
				}
			});

			// Lighting (adjusted for terrain + buildings interaction)
			map.setLight({
				anchor: 'viewport',
				color: '#e0f0ff',
				intensity: 0.55,
				position: [1.5, 210, 35]
			});

			// Opportunity glow layers (pre-created, updated by setOpportunityGlow)
			const emptyFilter: any = ['==', ['get', 'redcode'], ''];
			map.addLayer({
				id: 'opportunity-fill',
				type: 'fill',
				source: 'radios',
				'source-layer': 'radios',
				paint: { 'fill-color': '#22c55e', 'fill-opacity': 0.25 },
				filter: emptyFilter
			});
			map.addLayer({
				id: 'opportunity-line',
				type: 'line',
				source: 'radios',
				'source-layer': 'radios',
				paint: { 'line-color': '#22c55e', 'line-width': 2, 'line-opacity': 0.7 },
				filter: emptyFilter
			});

			// Selected radio layers (pre-created, updated by highlightSingleOpportunity)
			map.addLayer({
				id: 'selected-fill',
				type: 'fill',
				source: 'radios',
				'source-layer': 'radios',
				paint: { 'fill-color': '#ffffff', 'fill-opacity': 0.45 },
				filter: emptyFilter
			});
			map.addLayer({
				id: 'selected-line',
				type: 'line',
				source: 'radios',
				'source-layer': 'radios',
				paint: { 'line-color': '#ffffff', 'line-width': 3, 'line-opacity': 1 },
				filter: emptyFilter
			});

			// Radio highlight layer (building outlines at high zoom)
			map.addLayer({
				id: 'radio-highlight',
				type: 'line',
				source: 'buildings',
				'source-layer': 'buildings',
				paint: { 'line-color': '#60a5fa', 'line-width': 4.5, 'line-opacity': 0.8 },
				filter: emptyFilter
			});

			// ── Lasso draw layers ──────────────────────────────────────────
			map.addSource('lasso-draw', {
				type: 'geojson',
				data: { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[]] }, properties: {} }
			});
			map.addLayer({
				id: 'lasso-draw-fill',
				type: 'fill',
				source: 'lasso-draw',
				paint: { 'fill-color': '#60a5fa', 'fill-opacity': 0.15 }
			});
			map.addLayer({
				id: 'lasso-draw-line',
				type: 'line',
				source: 'lasso-draw',
				paint: { 'line-color': '#60a5fa', 'line-width': 2, 'line-dasharray': [4, 2] }
			});

			// ── Zone highlight layers (radios + buildings) ─────────────
			map.addLayer({
				id: 'zone-fill',
				type: 'fill',
				source: 'radios',
				'source-layer': 'radios',
				paint: { 'fill-color': '#60a5fa', 'fill-opacity': 0.45 },
				filter: emptyFilter
			});
			map.addLayer({
				id: 'zone-line',
				type: 'line',
				source: 'radios',
				'source-layer': 'radios',
				paint: { 'line-color': '#60a5fa', 'line-width': 2.5, 'line-opacity': 0.9 },
				filter: emptyFilter
			});
			// Building outlines tinted by zone color (visible in 3D)
			map.addLayer({
				id: 'zone-buildings',
				type: 'line',
				source: 'buildings',
				'source-layer': 'buildings',
				paint: { 'line-color': '#60a5fa', 'line-width': 3, 'line-opacity': 0.85 },
				filter: emptyFilter
			});

			// ── Hexagon H3 layers (GeoJSON, loaded dynamically) ─────────
			map.addSource('hexagons', {
				type: 'geojson',
				data: { type: 'FeatureCollection', features: [] }
			});

			map.addLayer({
				id: 'hex-fill',
				type: 'fill',
				source: 'hexagons',
				paint: { 'fill-color': '#3b82f6', 'fill-opacity': 0 }
			});
			map.addLayer({
				id: 'hex-line',
				type: 'line',
				source: 'hexagons',
				paint: { 'line-color': '#1e293b', 'line-width': 0.5, 'line-opacity': 0 }
			});
			map.addLayer({
				id: 'hex-selected',
				type: 'line',
				source: 'hexagons',
				paint: { 'line-color': '#ffffff', 'line-width': 3, 'line-opacity': 0.9 },
				filter: ['==', ['get', 'h3index'], '']
			});

			// ── Compare territory hex choropleth (dept comparison mode) ─────
			map.addSource('compare-hexagons', {
				type: 'geojson',
				data: { type: 'FeatureCollection', features: [] }
			});
			map.addLayer({
				id: 'compare-hex-fill',
				type: 'fill',
				source: 'compare-hexagons',
				paint: { 'fill-color': '#0f172a', 'fill-opacity': 0 }
			});
			map.addLayer({
				id: 'compare-hex-line',
				type: 'line',
				source: 'compare-hexagons',
				paint: { 'line-color': '#0f172a', 'line-width': 0.5, 'line-opacity': 0 }
			});

			// ── Hex zone highlight layers (GeoJSON, for lasso zones) ────────
			map.addSource('hex-zones', {
				type: 'geojson',
				data: { type: 'FeatureCollection', features: [] }
			});
			map.addLayer({
				id: 'hex-zone-fill',
				type: 'fill',
				source: 'hex-zones',
				paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.35 }
			});
			map.addLayer({
				id: 'hex-zone-line',
				type: 'line',
				source: 'hex-zones',
				paint: { 'line-color': ['get', 'color'], 'line-width': 2, 'line-opacity': 0.8 }
			});

			setupInteractions();

			// Re-apply territory visibility in case territory was set before map loaded
			// (e.g., territory restored from URL state before onMount completed)
			applyTerritoryVisibility();
		});

		return () => {
			maplibregl.removeProtocol('pmtiles');
			map.remove();
		};
	});

	function setupInteractions() {
		const tooltip = document.createElement('div');
		tooltip.id = 'hover-tooltip';
		tooltip.style.cssText = `
			position: fixed; pointer-events: none; z-index: 20; display: none;
			background: rgba(8,10,20,0.92); backdrop-filter: blur(12px);
			border: 1px solid rgba(96,165,250,0.3); border-radius: 8px;
			padding: 10px 14px; font-size: 12px; line-height: 1.7; color: #cbd5e1;
			box-shadow: 0 4px 24px rgba(0,0,0,0.6); max-width: 260px;
		`;
		document.body.appendChild(tooltip);

		let leaveTimeout: ReturnType<typeof setTimeout> | null = null;

		map.on('mousemove', 'buildings-3d', (e) => {
			if (lassoActive) return; // keep crosshair, skip tooltip
			if (leaveTimeout) { clearTimeout(leaveTimeout); leaveTimeout = null; }
			map.getCanvas().style.cursor = 'pointer';
			const p = e.features![0].properties!;

			const pers = parseInt(p.est_personas) || 0;
			const h = p.best_height_m != null ? parseFloat(p.best_height_m).toFixed(1) : '?';
			const a = p.area_m2 != null ? Math.round(p.area_m2).toLocaleString() : '?';
			const redcode = p.redcode || null;
			const radioPop = parseInt(p.radio_personas) || 0;
			const radioDens = p.densidad_hab_km2 != null ? Math.round(p.densidad_hab_km2).toLocaleString() : '?';
			const radioViv = parseInt(p.radio_viviendas) || 0;
			const radioHog = parseInt(p.radio_hogares) || 0;
			const radioAreaKm2 = p.radio_area_km2 != null ? parseFloat(p.radio_area_km2).toFixed(1) : '?';

			let html = `<b style="color:#60a5fa">${i18n.t('tip.building')}</b> ${i18n.t('tip.height')} ${h} m | ${i18n.t('tip.area')} ${a} m\u00B2<br>` +
				`<b style="color:#60a5fa">${i18n.t('tip.estPersons')}</b> <span style="color:#60a5fa;font-weight:600">${pers}</span>`;
			if (redcode) {
				html += `<br><span style="color:#a3a3a3">\u2500\u2500\u2500</span><br>` +
					`<b style="color:#d4d4d4">${i18n.t('tip.radio')}</b> <span style="color:#d4d4d4">${redcode}</span><br>` +
					`<b style="color:#d4d4d4">${i18n.t('tip.pop')}</b> ${radioPop.toLocaleString()} &nbsp; <b style="color:#d4d4d4">${i18n.t('tip.density')}</b> ${radioDens} hab/km\u00B2<br>` +
					`<b style="color:#d4d4d4">${i18n.t('label.dwellings')}:</b> ${radioViv.toLocaleString()} &nbsp; <b style="color:#d4d4d4">${i18n.t('label.households')}:</b> ${radioHog.toLocaleString()} &nbsp; <b style="color:#d4d4d4">${i18n.t('label.area')}:</b> ${radioAreaKm2} km\u00B2`;
			}
			tooltip.innerHTML = html;
			tooltip.style.display = 'block';
			tooltip.style.left = (e.originalEvent.clientX + 14) + 'px';
			tooltip.style.top = (e.originalEvent.clientY + 14) + 'px';
		});

		map.on('mouseleave', 'buildings-3d', () => {
			leaveTimeout = setTimeout(() => {
				if (!lassoActive) map.getCanvas().style.cursor = '';
				tooltip.style.display = 'none';
			}, 80);
		});

		// Itapúa buildings tooltip (height + area only, no census data)
		map.on('mousemove', 'itapua-buildings-3d', (e) => {
			if (lassoActive) return;
			if (leaveTimeout) { clearTimeout(leaveTimeout); leaveTimeout = null; }
			map.getCanvas().style.cursor = 'pointer';
			const p = e.features![0].properties!;
			const h = p.best_height_m != null ? parseFloat(p.best_height_m).toFixed(1) : '?';
			const a = p.area_m2 != null ? Math.round(p.area_m2).toLocaleString() : '?';
			tooltip.innerHTML = `<b style="color:#60a5fa">${i18n.t('tip.building')}</b> ${i18n.t('tip.height')} ${h} m | ${i18n.t('tip.area')} ${a} m\u00B2`;
			tooltip.style.display = 'block';
			tooltip.style.left = (e.originalEvent.clientX + 14) + 'px';
			tooltip.style.top = (e.originalEvent.clientY + 14) + 'px';
		});
		map.on('mouseleave', 'itapua-buildings-3d', () => {
			leaveTimeout = setTimeout(() => {
				if (!lassoActive) map.getCanvas().style.cursor = '';
				tooltip.style.display = 'none';
			}, 80);
		});

		// Click-to-select/deselect radio (multi-select)
		map.on('click', 'buildings-3d', (e) => {
			if (lassoActive) return;
			if (mapStore.activeHexLayer) return;
			if (catastroClickMode !== 'none') return; // catastro-fill handler handles it
			const redcode = e.features![0].properties!.redcode;
			if (!redcode) return;

			if (mapStore.hasRadio(redcode)) {
				container.dispatchEvent(new CustomEvent('radio-deselect', { bubbles: true, detail: { redcode } }));
			} else {
				// Query all visible buildings for this redcode
				const canvas = map.getCanvas();
				const allFeatures = map.queryRenderedFeatures(
					[[0, 0], [canvas.width, canvas.height]],
					{ layers: ['buildings-3d'] }
				);
				const selected: Record<string, any>[] = [];
				const seen = new Set<string>();
				for (const f of allFeatures) {
					const id = f.properties?.gba_id;
					if (f.properties?.redcode !== redcode || seen.has(id)) continue;
					seen.add(id);
					selected.push(f.properties!);
				}

				container.dispatchEvent(new CustomEvent('radio-select', {
					bubbles: true,
					detail: { redcode, selected, census: e.features![0].properties! }
				}));
			}
		});

		// Click on hexagon: emit hex-select event
		map.on('click', 'hex-fill', (e) => {
			if (lassoActive) return;
			const h3index = e.features![0].properties!.h3index;
			if (!h3index) return;
			container.dispatchEvent(new CustomEvent('hex-select', {
				bubbles: true,
				detail: { h3index, properties: e.features![0].properties! }
			}));
		});

		map.on('click', 'compare-hex-fill', (e) => {
			if (lassoActive) return;
			const h3index = e.features![0].properties!.h3index;
			if (!h3index) return;
			container.dispatchEvent(new CustomEvent('compare-hex-select', {
				bubbles: true,
				detail: { h3index, properties: e.features![0].properties! }
			}));
		});

		// Click on selected hex border (thick line intercepts before hex-fill)
		map.on('click', 'hex-selected', (e) => {
			if (lassoActive) return;
			const h3index = e.features![0].properties!.h3index;
			if (!h3index) return;
			container.dispatchEvent(new CustomEvent('hex-select', {
				bubbles: true,
				detail: { h3index, properties: e.features![0].properties! }
			}));
		});

		// Hex hover tooltip
		map.on('mousemove', 'hex-fill', (e) => {
			if (lassoActive) return;
			const p = e.features![0].properties!;
			if (!p.h3index) return;
			map.getCanvas().style.cursor = 'pointer';

			const titleLine = hexLayerTitle ? `<div style="color:rgba(255,255,255,0.5);font-size:9px;margin-bottom:2px">${hexLayerTitle}</div>` : '';

			let valueLine: string;
			if (hexLayerIsCategorical && p.type_label) {
				valueLine = `<span style="color:#e2e8f0;font-weight:600">${p.type_label}</span>`;
			} else {
				const score = p.value != null ? Number(p.value).toFixed(1) : '—';
				valueLine = `<span style="color:#e2e8f0;font-weight:600">${score}</span><span style="color:rgba(255,255,255,0.4);font-size:9px"> /100</span>`;
			}

			tooltip.innerHTML = `${titleLine}${valueLine}`;
			tooltip.style.display = 'block';
			tooltip.style.left = (e.originalEvent.clientX + 14) + 'px';
			tooltip.style.top = (e.originalEvent.clientY + 14) + 'px';
		});

		map.on('mouseleave', 'hex-fill', () => {
			if (!lassoActive) map.getCanvas().style.cursor = '';
			tooltip.style.display = 'none';
		});

	}

	export function setHexLayerInfo(title: string, isCategorical: boolean) {
		hexLayerTitle = title;
		hexLayerIsCategorical = isCategorical;
	}

	export function flyToInit() {
		map?.flyTo({ ...MAP_PROVINCE, duration: 1200 });
	}

	export function getRadioGeometry(redcode: string): any | null {
		if (!map) return null;
		const features = map.querySourceFeatures('radios', {
			sourceLayer: 'radios',
			filter: ['==', ['get', 'redcode'], redcode] as any
		});
		if (features.length === 0) return null;
		return features[0].geometry;
	}

	export function setPitch(p: number) {
		map?.easeTo({ pitch: p, duration: 200 });
	}



	function showBuildingsForActiveTerritory() {
		const layer = activeTerritoryId === 'itapua_py' ? 'itapua-buildings-3d' : 'buildings-3d';
		const opacity = activeTerritoryId === 'itapua_py' ? 0.92 : 0.85;
		const colorExpr = activeTerritoryId === 'itapua_py'
			? mapStore.getHeightColorExpr()
			: mapStore.getColorExpr();
		if (map?.getLayer(layer)) {
			map.setLayoutProperty(layer, 'visibility', 'visible');
			map.setPaintProperty(layer, 'fill-extrusion-color', colorExpr as any);
			map.setPaintProperty(layer, 'fill-extrusion-opacity', opacity);
		}
	}

	export function updateColorExpr() {
		if (map?.getLayer('buildings-3d')) {
			map.setPaintProperty('buildings-3d', 'fill-extrusion-color', mapStore.getColorExpr() as any);
		}
	}

	export function setRadioHighlight(radios: Array<{redcode: string, color: string}>) {
		if (!map?.getLayer('radio-highlight')) return;
		if (radios.length === 0) {
			map.setFilter('radio-highlight', ['==', ['get', 'redcode'], '']);
		} else {
			const redcodes = radios.map(r => r.redcode);
			// Build match expression for per-radio colors
			const matchExpr: any[] = ['match', ['get', 'redcode']];
			for (const r of radios) {
				matchExpr.push(r.redcode, r.color);
			}
			matchExpr.push('#60a5fa'); // fallback
			map.setPaintProperty('radio-highlight', 'line-color', matchExpr);
			map.setPaintProperty('radio-highlight', 'line-width', 4.5);
			map.setFilter('radio-highlight', ['in', ['get', 'redcode'], ['literal', redcodes]]);
		}
	}

	export function clearRadioHighlight() {
		if (!map) return;
		const emptyFilter: any = ['==', ['get', 'redcode'], ''];
		map.setFilter('radio-highlight', emptyFilter);
		map.setFilter('selected-fill', emptyFilter);
		map.setFilter('selected-line', emptyFilter);
	}

	export function flyToCoords(lat: number, lng: number, zoom?: number) {
		map?.flyTo({
			center: [lng, lat],
			zoom: zoom || 12,
			pitch: 50,
			duration: 1500
		});
	}

	export function flyToBbox(bbox: [number, number, number, number]) {
		// bbox: [W, S, E, N]
		map?.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], {
			padding: 40,
			pitch: 50,
			duration: 1500,
			maxZoom: 10
		});
	}

	function applyTerritoryVisibility() {
		if (!map) return;
		const isItapua = activeTerritoryId === 'itapua_py';

		// Misiones-only layers: mask + census radios + province boundary
		for (const layerId of ['mask-fill', 'province-fill', 'province-line', 'province-border']) {
			if (map.getLayer(layerId)) {
				map.setLayoutProperty(layerId, 'visibility', isItapua ? 'none' : 'visible');
			}
		}
		// Itapúa mask (same dark fog, swapped in when territory is Itapúa)
		if (map.getLayer('itapua-mask-fill')) {
			map.setLayoutProperty('itapua-mask-fill', 'visibility', isItapua ? 'visible' : 'none');
		}
		// Buildings: swap visibility
		const hide = isItapua ? 'buildings-3d' : 'itapua-buildings-3d';
		const show = isItapua ? 'itapua-buildings-3d' : 'buildings-3d';
		if (map.getLayer(hide)) map.setLayoutProperty(hide, 'visibility', 'none');
		if (map.getLayer(show)) {
			map.setLayoutProperty(show, 'visibility', 'visible');
			const colorExpr = show === 'itapua-buildings-3d'
				? mapStore.getHeightColorExpr()
				: mapStore.getColorExpr();
			map.setPaintProperty(show, 'fill-extrusion-color', colorExpr as any);
		}
	}

	export function setActiveTerritory(territoryId: string) {
		activeTerritoryId = territoryId;
		applyTerritoryVisibility();
	}

	// ── Lens opportunity glow layers ─────────────────────────────────────────

	export function setOpportunityGlow(redcodes: string[], color: string) {
		if (!map) return;

		const filter: any = redcodes.length > 0
			? ['in', ['get', 'redcode'], ['literal', redcodes]]
			: ['==', ['get', 'redcode'], ''];

		// Layers are pre-created on map load — always update
		map.setPaintProperty('opportunity-fill', 'fill-color', color);
		map.setPaintProperty('opportunity-fill', 'fill-opacity', 0.25);
		map.setFilter('opportunity-fill', filter);

		map.setPaintProperty('opportunity-line', 'line-color', color);
		map.setFilter('opportunity-line', filter);
	}

	export function clearOpportunityGlow() {
		if (!map) return;
		const emptyFilter: any = ['==', ['get', 'redcode'], ''];
		if (map.getLayer('opportunity-fill')) {
			map.setFilter('opportunity-fill', emptyFilter);
		}
		if (map.getLayer('opportunity-line')) {
			map.setFilter('opportunity-line', emptyFilter);
		}
	}

	export function flyToProvince() {
		map?.flyTo({ ...MAP_PROVINCE, duration: 1200 });
	}

	// ── Catastro parcel layer (PMTiles) ─────────────────────────────────────

	// CARTO basemap building layer IDs (dark-matter style)
	const CARTO_BUILDING_LAYERS = ['building', 'building-top'];

	export function showCatastroLayer() {
		if (!map) return;
		// Retry if style not loaded yet
		if (!map.isStyleLoaded()) {
			map.once('idle', () => showCatastroLayer());
			return;
		}
		catastroActive = true;

		// Add catastro source
		if (!map.getSource('catastro')) {
			map.addSource('catastro', { type: 'vector', url: getTilesUrl('catastro'), maxzoom: 14 });
		}

		// Hide 3D buildings — add flat 2D fill BELOW catastro
		for (const layer of ['buildings-3d', 'itapua-buildings-3d']) {
			if (map.getLayer(layer)) map.setLayoutProperty(layer, 'visibility', 'none');
		}
		if (!map.getLayer('buildings-flat') && map.getSource('buildings')) {
			map.addLayer({
				id: 'buildings-flat',
				type: 'fill',
				source: 'buildings',
				'source-layer': 'buildings',
				paint: {
					'fill-color': mapStore.getColorExpr() as any,
					'fill-opacity': 0.3
				}
			});
			map.on('click', 'buildings-flat', (e) => {
				if (lassoActive) return;
				if (catastroClickMode !== 'none') return;
				const redcode = e.features![0]?.properties?.redcode;
				if (!redcode) return;
				if (mapStore.hasRadio(redcode)) {
					container.dispatchEvent(new CustomEvent('radio-deselect', { bubbles: true, detail: { redcode } }));
				} else {
					const selected = [e.features![0].properties!];
					container.dispatchEvent(new CustomEvent('radio-select', {
						bubbles: true, detail: { redcode, selected, census: e.features![0].properties! }
					}));
				}
			});
			map.on('mouseenter', 'buildings-flat', () => { map.getCanvas().style.cursor = 'pointer'; });
			map.on('mouseleave', 'buildings-flat', () => { map.getCanvas().style.cursor = ''; });
		}

		// Fill layer — bright solid colors ON TOP of everything.
		// Highlight recently added parcels in amber and recently removed
		// parcels (ghost layer) in red against the urbano/rural base palette.
		if (!map.getLayer('catastro-fill')) {
			map.addLayer({
				id: 'catastro-fill',
				type: 'fill',
				source: 'catastro',
				'source-layer': 'catastro',
				minzoom: 9,
				paint: {
					'fill-color': [
						'case',
						['==', ['get', 'is_removed'], 1], '#dc2626',
						['==', ['get', 'is_new'], 1], '#fbbf24',
						[
							'match', ['get', 'tipo'],
							'urbano', '#22d3ee',
							'rural', '#4ade80',
							'#22d3ee'
						]
					],
					'fill-opacity': [
						'case',
						['==', ['get', 'is_removed'], 1], 0.45,
						0.75
					],
					'fill-outline-color': [
						'case',
						['==', ['get', 'is_removed'], 1], '#7f1d1d',
						['==', ['get', 'is_new'], 1], '#b45309',
						[
							'match', ['get', 'tipo'],
							'urbano', '#0e7490',
							'rural', '#15803d',
							'#0e7490'
						]
					]
				}
			});
		}

		// Line layer at high zoom for definition — on top of fill.
		// New parcels: darker amber outline. Removed parcels: thick dark red.
		if (!map.getLayer('catastro-line')) {
			map.addLayer({
				id: 'catastro-line',
				type: 'line',
				source: 'catastro',
				'source-layer': 'catastro',
				minzoom: 12,
				paint: {
					'line-color': [
						'case',
						['==', ['get', 'is_removed'], 1], '#fca5a5',
						['==', ['get', 'is_new'], 1], '#fde68a',
						'rgba(0,0,0,0.7)'
					],
					'line-width': [
						'interpolate', ['linear'], ['zoom'],
						12, ['case', ['==', ['get', 'is_removed'], 1], 1.2, ['==', ['get', 'is_new'], 1], 1.0, 0.8],
						14, ['case', ['==', ['get', 'is_removed'], 1], 2.0, ['==', ['get', 'is_new'], 1], 1.6, 1.2],
						17, ['case', ['==', ['get', 'is_removed'], 1], 3.0, ['==', ['get', 'is_new'], 1], 2.5, 2.0]
					],
					'line-opacity': 1.0
				}
			});
		}
		for (const layerId of CARTO_BUILDING_LAYERS) {
			if (map.getLayer(layerId)) {
				map.setLayoutProperty(layerId, 'visibility', 'none');
			}
		}
	}

	export function hideCatastroLayer() {
		if (!map || !map.isStyleLoaded() || !catastroActive) return;
		catastroActive = false;
		catastroClickMode = 'none';
		catastroClickBound = false; // layer being removed, handlers gone
		if (map.getLayer('catastro-fill')) map.removeLayer('catastro-fill');
		if (map.getLayer('catastro-line')) map.removeLayer('catastro-line');
		if (map.getLayer('buildings-flat')) map.removeLayer('buildings-flat');
		showBuildingsForActiveTerritory();
		for (const layerId of CARTO_BUILDING_LAYERS) {
			if (map.getLayer(layerId)) {
				map.setLayoutProperty(layerId, 'visibility', 'visible');
			}
		}
	}

	// ── Catastro flood choropleth (parcels colored by H3 flood risk) ────────

	// ── Unified catastro parcel click system ────────────────────────────
	// Single handler for ALL catastro-based analyses (flood, scores, radio)
	let catastroClickMode: 'none' | 'flood' | 'scores' = 'none';
	let catastroClickBound = false;

	function catastroUnifiedClickHandler(e: any) {
		if (lassoActive || catastroClickMode === 'none') return;
		const feat = e.features?.[0];
		if (!feat) return;
		const props = feat.properties;
		if (!props?.h3index) return;
		const detail = { h3index: props.h3index, tipo: props.tipo ?? 'urbano', area_m2: Number(props.area_m2) || 0 };
		const eventName = catastroClickMode === 'flood' ? 'catastro-flood-select' : 'catastro-scores-select';
		container.dispatchEvent(new CustomEvent(eventName, { bubbles: true, detail }));
	}

	function catastroMouseEnter() {
		if (catastroClickMode !== 'none' && !lassoActive) map.getCanvas().style.cursor = 'pointer';
	}
	function catastroMouseLeave() {
		if (catastroClickMode !== 'none' && !lassoActive) map.getCanvas().style.cursor = '';
	}

	function bindCatastroClick() {
		// Always clean up first, then bind once
		try {
			map.off('click', 'catastro-fill', catastroUnifiedClickHandler);
			map.off('mouseenter', 'catastro-fill', catastroMouseEnter);
			map.off('mouseleave', 'catastro-fill', catastroMouseLeave);
		} catch (_) { /* ok if layer doesn't exist */ }
		catastroClickBound = true;
		map.on('click', 'catastro-fill', catastroUnifiedClickHandler);
		map.on('mouseenter', 'catastro-fill', catastroMouseEnter);
		map.on('mouseleave', 'catastro-fill', catastroMouseLeave);
	}

	function unbindCatastroClick() {
		if (!catastroClickBound) return;
		catastroClickBound = false;
		try {
			map.off('click', 'catastro-fill', catastroUnifiedClickHandler);
			map.off('mouseenter', 'catastro-fill', catastroMouseEnter);
			map.off('mouseleave', 'catastro-fill', catastroMouseLeave);
		} catch (_) { /* layer may have been removed */ }
	}

	function applyCatastroChoropleth(colorExpr: any) {
		if (map.getLayer('catastro-fill')) {
			map.setPaintProperty('catastro-fill', 'fill-color', colorExpr);
			map.setPaintProperty('catastro-fill', 'fill-opacity',
				['interpolate', ['linear'], ['zoom'], 10, 0.25, 11, 0.35, 12, 0.55, 14, 0.7]);
		}
		if (map.getLayer('catastro-line')) {
			map.setPaintProperty('catastro-line', 'line-color', '#ffffff');
			map.setPaintProperty('catastro-line', 'line-opacity',
				['interpolate', ['linear'], ['zoom'], 10, 0.1, 11, 0.15, 12, 0.3, 14, 0.5]);
		}
	}

	function resetCatastroStyle() {
		if (map.getLayer('catastro-fill')) {
			map.setPaintProperty('catastro-fill', 'fill-color', [
				'match', ['get', 'tipo'], 'urbano', '#22d3ee', 'rural', '#4ade80', '#22d3ee'
			]);
			map.setPaintProperty('catastro-fill', 'fill-opacity', 0.95);
			map.setPaintProperty('catastro-fill', 'fill-outline-color', [
				'match', ['get', 'tipo'], 'urbano', '#0e7490', 'rural', '#15803d', '#0e7490'
			]);
		}
		if (map.getLayer('catastro-line')) {
			map.setPaintProperty('catastro-line', 'line-color', [
				'match', ['get', 'tipo'], 'urbano', '#0e7490', 'rural', '#15803d', '#0e7490'
			]);
			map.setPaintProperty('catastro-line', 'line-opacity',
				['interpolate', ['linear'], ['zoom'], 13, 0.6, 15, 0.9]);
		}
	}

	export function filterCatastroDept(deptCode: string | null) {
		if (!map) return;
		if (deptCode) {
			const filter = ['==', ['get', 'departamento'], deptCode];
			if (map.getLayer('catastro-fill')) map.setFilter('catastro-fill', filter);
			if (map.getLayer('catastro-line')) map.setFilter('catastro-line', filter);
		} else {
			if (map.getLayer('catastro-fill')) map.setFilter('catastro-fill', null);
			if (map.getLayer('catastro-line')) map.setFilter('catastro-line', null);
		}
	}

	export function setCatastroFloodChoropleth(h3ScoreMap: Map<string, number>) {
		if (!map) return;

		function apply() {
			if (!catastroActive) showCatastroLayer();
			catastroClickMode = 'flood';

			const matchExpr: any[] = ['match', ['get', 'h3index']];
			for (const [h3index, score] of h3ScoreMap) { matchExpr.push(h3index, score); }
			matchExpr.push(0);

			applyCatastroChoropleth([
				'interpolate', ['linear'], matchExpr,
				0, '#0d1b2a', 10, '#1b3a5f', 25, '#2a6f97',
				40, '#eab308', 60, '#f97316', 80, '#dc2626', 100, '#7f1d1d'
			]);
			bindCatastroClick();
		}

		if (map.isStyleLoaded() && !map.isMoving()) {
			apply();
		} else {
			map.once('idle', apply);
		}
	}

	export function clearCatastroFloodChoropleth() {
		if (!map || !map.isStyleLoaded()) return;
		catastroClickMode = 'none';
		resetCatastroStyle();
		unbindCatastroClick();
	}

	export function setFloodParcelHighlight(parcels: Array<{ h3index: string; color: string }>) {
		if (!map || !map.isStyleLoaded() || !map.getSource('catastro')) return;

		// Build filter: match any selected h3index
		if (parcels.length === 0) {
			if (map.getLayer('catastro-sel-fill')) map.removeLayer('catastro-sel-fill');
			if (map.getLayer('catastro-sel-line')) map.removeLayer('catastro-sel-line');
			return;
		}

		const h3Filter: any = ['in', ['get', 'h3index'], ['literal', parcels.map(p => p.h3index)]];

		// Color match: h3index → parcel color
		const colorMatch: any[] = ['match', ['get', 'h3index']];
		for (const p of parcels) { colorMatch.push(p.h3index, p.color); }
		colorMatch.push('#ffffff');

		if (!map.getLayer('catastro-sel-fill')) {
			map.addLayer({
				id: 'catastro-sel-fill',
				type: 'fill',
				source: 'catastro',
				'source-layer': 'catastro',
				minzoom: 11,
				paint: { 'fill-color': colorMatch, 'fill-opacity': 0.45 },
				filter: h3Filter
			});
		} else {
			map.setPaintProperty('catastro-sel-fill', 'fill-color', colorMatch);
			map.setFilter('catastro-sel-fill', h3Filter);
		}

		if (!map.getLayer('catastro-sel-line')) {
			map.addLayer({
				id: 'catastro-sel-line',
				type: 'line',
				source: 'catastro',
				'source-layer': 'catastro',
				minzoom: 11,
				paint: { 'line-color': colorMatch, 'line-width': 3, 'line-opacity': 0.9 },
				filter: h3Filter
			});
		} else {
			map.setPaintProperty('catastro-sel-line', 'line-color', colorMatch);
			map.setFilter('catastro-sel-line', h3Filter);
		}
	}

	export function clearFloodParcelHighlight() {
		if (!map || !map.isStyleLoaded()) return;
		if (map.getLayer('catastro-sel-fill')) map.removeLayer('catastro-sel-fill');
		if (map.getLayer('catastro-sel-line')) map.removeLayer('catastro-sel-line');
	}

	// ── Scores/Radio choropleth (catastro-based, reuses unified click) ──

	export function setCatastroScoresChoropleth(h3ScoreMap: Map<string, number>) {
		if (!map) return;

		function apply() {
			if (!catastroActive) showCatastroLayer();
			catastroClickMode = 'scores';

			const matchExpr: any[] = ['match', ['get', 'h3index']];
			for (const [h3index, score] of h3ScoreMap) { matchExpr.push(h3index, score); }
			matchExpr.push(0);

			applyCatastroChoropleth([
				'interpolate', ['linear'], matchExpr,
				0, '#1e293b', 15, '#334155', 30, '#4a7c59',
				50, '#22c55e', 70, '#86efac', 100, '#f0fdf4'
			]);
			bindCatastroClick();
		}

		if (map.isStyleLoaded() && !map.isMoving()) {
			apply();
		} else {
			map.once('idle', apply);
		}
	}

	export function clearCatastroScoresChoropleth() {
		if (!map || !map.isStyleLoaded()) return;
		catastroClickMode = 'none';
		resetCatastroStyle();
		unbindCatastroClick();
	}

	export function setScoresParcelHighlight(parcels: Array<{ h3index: string; color: string }>) {
		setFloodParcelHighlight(parcels);
	}

	// ── Analysis choropleth layers (radio-based, for non-catastro analyses) ──

	export function setAnalysisChoropleth(entries: { redcode: string; value: number }[], colorScale: 'price' | 'score' | 'diverging' | 'sequential' = 'price') {
		if (!map || !map.isStyleLoaded()) return;

		// All analysis types: use radios PMTiles (existing logic)
		if (!map.getLayer('analysis-fill')) {
			map.addLayer({
				id: 'analysis-fill',
				type: 'fill',
				source: 'radios',
				'source-layer': 'radios',
				paint: { 'fill-color': '#f59e0b', 'fill-opacity': 0.35 },
				filter: ['==', ['get', 'redcode'], '']
			});
		}
		if (!map.getLayer('analysis-line')) {
			map.addLayer({
				id: 'analysis-line',
				type: 'line',
				source: 'radios',
				'source-layer': 'radios',
				paint: { 'line-color': '#1e293b', 'line-width': 0.5, 'line-opacity': 0.6 },
				filter: ['==', ['get', 'redcode'], '']
			});
		}

		if (entries.length === 0) return;

		const values = entries.map(e => e.value);
		let minVal = Infinity, maxVal = -Infinity;
		for (const v of values) { if (v < minVal) minVal = v; if (v > maxVal) maxVal = v; }
		const range = maxVal - minVal || 1;

		const matchExpr: any[] = ['match', ['to-string', ['get', 'redcode']]];
		for (const entry of entries) {
			if (entry.value === 0) {
				matchExpr.push(String(entry.redcode), 'rgb(30,41,59)');
				continue;
			}
			const t = (entry.value - minVal) / range;
			let r: number, g: number, b: number;
			if (colorScale === 'sequential') {
				// Dark navy → bright cyan ramp for catastro density
				r = Math.round(13 + t * (20 - 13));
				g = Math.round(27 + t * (182 - 27));
				b = Math.round(42 + t * (212 - 42));
			} else if (colorScale === 'price') {
				r = Math.round(t < 0.5 ? 34 + t * 2 * (234 - 34) : 234 + (t - 0.5) * 2 * (239 - 234));
				g = Math.round(t < 0.5 ? 197 + t * 2 * (179 - 197) : 179 + (t - 0.5) * 2 * (68 - 179));
				b = Math.round(t < 0.5 ? 94 + t * 2 * (8 - 94) : 8 + (t - 0.5) * 2 * (68 - 8));
			} else {
				// Viridis: dark purple → teal → yellow
				r = Math.round(t < 0.5 ? 68 + t * 2 * (33 - 68) : 33 + (t - 0.5) * 2 * (253 - 33));
				g = Math.round(t < 0.5 ? 1 + t * 2 * (145 - 1) : 145 + (t - 0.5) * 2 * (231 - 145));
				b = Math.round(t < 0.5 ? 84 + t * 2 * (140 - 84) : 140 + (t - 0.5) * 2 * (37 - 140));
			}
			matchExpr.push(String(entry.redcode), `rgb(${r},${g},${b})`);
		}
		matchExpr.push('rgba(0,0,0,0)');

		const redcodes = entries.map(e => e.redcode);
		map.setFilter('analysis-fill', ['in', ['get', 'redcode'], ['literal', redcodes]]);
		map.setPaintProperty('analysis-fill', 'fill-color', matchExpr);
		map.setPaintProperty('analysis-fill', 'fill-opacity', 0.4);
		map.setFilter('analysis-line', ['in', ['get', 'redcode'], ['literal', redcodes]]);
	}

	export function clearAnalysisChoropleth() {
		if (!map || !map.isStyleLoaded()) return;
		// Remove catastro layers only if active
		if (catastroActive) hideCatastroLayer();
		// Clear radio analysis layers
		if (map.getLayer('analysis-fill')) {
			map.setFilter('analysis-fill', ['==', ['get', 'redcode'], '']);
		}
		if (map.getLayer('analysis-line')) {
			map.setFilter('analysis-line', ['==', ['get', 'redcode'], '']);
		}
		// Restore buildings (territory-aware)
		showBuildingsForActiveTerritory();
	}

	export function highlightSingleOpportunity(redcode: string, color: string) {
		if (!map) return;
		const matchFilter: any = ['==', ['get', 'redcode'], redcode];

		// Dedicated selection layers (pre-created on map load, always update)
		map.setPaintProperty('selected-fill', 'fill-color', color);
		map.setFilter('selected-fill', matchFilter);

		map.setPaintProperty('selected-line', 'line-color', color);
		map.setFilter('selected-line', matchFilter);

		// Building outlines (visible at high zoom)
		map.setPaintProperty('radio-highlight', 'line-color', color);
		map.setPaintProperty('radio-highlight', 'line-width', 5);
		map.setFilter('radio-highlight', matchFilter);
	}

	export function highlightComparisonPair(redcodeA: string, colorA: string, redcodeB: string, colorB: string) {
		setRadioHighlight([
			{ redcode: redcodeA, color: colorA },
			{ redcode: redcodeB, color: colorB }
		]);
		// Use thicker line for comparison visibility
		if (map?.getLayer('radio-highlight')) {
			map.setPaintProperty('radio-highlight', 'line-width', 5);
		}
	}

	// ── Hexagon H3 choropleth functions ──────────────────────────────────

	const CATEGORICAL_PALETTE = ['#1565c0', '#7e57c2', '#4db6ac', '#66bb6a', '#c0ca33', '#ffb74d', '#e65100', '#78909c'];

	function computeHexColor(value: number, colorScale: string, minVal: number, maxVal: number, range: number): string {
		if (value === 0 && colorScale !== 'diverging' && colorScale !== 'categorical') return 'rgb(55,65,81)';
		if (colorScale === 'categorical') {
			const idx = Math.round(value) - 1;
			if (idx < 0) return 'rgb(55,65,81)';
			return CATEGORICAL_PALETTE[idx % CATEGORICAL_PALETTE.length];
		}
		let r: number, g: number, b: number;
		if (colorScale === 'diverging') {
			const absMax = Math.max(Math.abs(minVal), Math.abs(maxVal)) || 1;
			const t = value / absMax;
			if (t < 0) {
				const s = -t;
				r = Math.round(163 + s * 76); g = Math.round(163 - s * 95); b = Math.round(163 - s * 95);
			} else {
				const s = t;
				r = Math.round(163 - s * 129); g = Math.round(163 + s * 34); b = Math.round(163 - s * 69);
			}
		} else {
			const t = Math.max(0, Math.min(1, (value - minVal) / range));
			if (colorScale === 'flood') {
				r = Math.round(t < 0.5 ? 59 + t * 2 * (234 - 59) : 234 + (t - 0.5) * 2 * (220 - 234));
				g = Math.round(t < 0.5 ? 130 + t * 2 * (179 - 130) : 179 + (t - 0.5) * 2 * (38 - 179));
				b = Math.round(t < 0.5 ? 246 + t * 2 * (8 - 246) : 8 + (t - 0.5) * 2 * (38 - 8));
			} else if (colorScale === 'green') {
				r = Math.round(t < 0.5 ? 20 + t * 2 * (22 - 20) : 22 + (t - 0.5) * 2 * (187 - 22));
				g = Math.round(t < 0.5 ? 83 + t * 2 * (101 - 83) : 101 + (t - 0.5) * 2 * (247 - 101));
				b = Math.round(t < 0.5 ? 45 + t * 2 * (52 - 45) : 52 + (t - 0.5) * 2 * (208 - 52));
			} else if (colorScale === 'warm') {
				r = Math.round(t < 0.5 ? 120 + t * 2 * (245 - 120) : 245 + (t - 0.5) * 2 * (253 - 245));
				g = Math.round(t < 0.5 ? 53 + t * 2 * (158 - 53) : 158 + (t - 0.5) * 2 * (231 - 158));
				b = Math.round(t < 0.5 ? 15 + t * 2 * (11 - 15) : 11 + (t - 0.5) * 2 * (37 - 11));
			} else {
				r = Math.round(t < 0.5 ? 91 + t * 2 * (33 - 91) : 33 + (t - 0.5) * 2 * (253 - 33));
				g = Math.round(t < 0.5 ? 33 + t * 2 * (145 - 33) : 145 + (t - 0.5) * 2 * (231 - 145));
				b = Math.round(t < 0.5 ? 182 + t * 2 * (140 - 182) : 140 + (t - 0.5) * 2 * (37 - 140));
			}
		}
		return `rgb(${r},${g},${b})`;
	}

	export function setHexChoropleth(entries: { h3index: string; value: number; properties?: Record<string, number>; boundary?: number[][] }[], colorScale: 'flood' | 'sequential' | 'diverging' | 'categorical' | 'green' | 'warm' = 'flood', domain?: [number, number]) {
		if (!map) return;
		const src = map.getSource('hexagons') as maplibregl.GeoJSONSource | undefined;
		if (!src) return;

		if (entries.length === 0) {
			src.setData({ type: 'FeatureCollection', features: [] });
			map.setPaintProperty('hex-fill', 'fill-opacity', 0);
			map.setPaintProperty('hex-line', 'line-opacity', 0);
			return;
		}

		let minVal: number, maxVal: number;
		if (domain && colorScale !== 'diverging' && colorScale !== 'categorical') {
			// Use provincial percentile bounds (P2/P98) for consistent cross-department coloring
			[minVal, maxVal] = domain;
		} else {
			// Fallback: local min/max from entries
			minVal = Infinity; maxVal = -Infinity;
			const values = entries.map(e => e.value);
			for (const v of values) { if (v < minVal) minVal = v; if (v > maxVal) maxVal = v; }
		}
		const range = maxVal - minVal || 1;

		const getColor = (value: number) => computeHexColor(value, colorScale, minVal, maxVal, range);

		const features: any[] = [];
		for (const entry of entries) {
			if (!entry.boundary) continue;
			features.push({
				type: 'Feature',
				properties: {
					h3index: entry.h3index,
					value: entry.value,
					color: getColor(entry.value),
					...(entry.properties || {})
				},
				geometry: { type: 'Polygon', coordinates: [entry.boundary] }
			});
		}

		src.setData({ type: 'FeatureCollection', features });
		map.setPaintProperty('hex-fill', 'fill-color', ['get', 'color']);
		map.setPaintProperty('hex-fill', 'fill-opacity', 0.50);
		map.setPaintProperty('hex-line', 'line-color', '#0f172a');
		map.setPaintProperty('hex-line', 'line-width', 0.5);
		map.setPaintProperty('hex-line', 'line-opacity', 0.55);
	}

	export function clearHexChoropleth() {
		if (!map) return;
		const src = map.getSource('hexagons') as maplibregl.GeoJSONSource | undefined;
		if (src) src.setData({ type: 'FeatureCollection', features: [] });
		if (map.getLayer('hex-fill')) map.setPaintProperty('hex-fill', 'fill-opacity', 0);
		if (map.getLayer('hex-line')) map.setPaintProperty('hex-line', 'line-opacity', 0);
		if (map.getLayer('hex-selected')) map.setFilter('hex-selected', ['==', ['get', 'h3index'], '']);
	}

	export function setCompareHexChoropleth(entries: { h3index: string; value: number; properties?: Record<string, number>; boundary?: number[][] }[], colorScale: 'flood' | 'sequential' | 'diverging' | 'categorical' | 'green' | 'warm' = 'sequential', domain?: [number, number]) {
		if (!map) return;
		const src = map.getSource('compare-hexagons') as maplibregl.GeoJSONSource | undefined;
		if (!src) return;

		if (entries.length === 0) {
			src.setData({ type: 'FeatureCollection', features: [] });
			map.setPaintProperty('compare-hex-fill', 'fill-opacity', 0);
			map.setPaintProperty('compare-hex-line', 'line-opacity', 0);
			return;
		}

		let minVal: number, maxVal: number;
		if (domain && colorScale !== 'diverging' && colorScale !== 'categorical') {
			[minVal, maxVal] = domain;
		} else {
			minVal = Infinity; maxVal = -Infinity;
			for (const e of entries) {
				if (e.value < minVal) minVal = e.value;
				if (e.value > maxVal) maxVal = e.value;
			}
		}
		const range = maxVal - minVal || 1;
		const getColor = (v: number) => computeHexColor(v, colorScale, minVal, maxVal, range);

		const features: any[] = [];
		for (const entry of entries) {
			if (!entry.boundary) continue;
			features.push({
				type: 'Feature',
				properties: { h3index: entry.h3index, value: entry.value, color: getColor(entry.value), ...(entry.properties || {}) },
				geometry: { type: 'Polygon', coordinates: [entry.boundary] }
			});
		}

		src.setData({ type: 'FeatureCollection', features });
		map.setPaintProperty('compare-hex-fill', 'fill-color', ['get', 'color']);
		map.setPaintProperty('compare-hex-fill', 'fill-opacity', 0.50);
		map.setPaintProperty('compare-hex-line', 'line-color', '#0f172a');
		map.setPaintProperty('compare-hex-line', 'line-width', 0.5);
		map.setPaintProperty('compare-hex-line', 'line-opacity', 0.55);
	}

	export function clearCompareHexChoropleth() {
		if (!map) return;
		const src = map.getSource('compare-hexagons') as maplibregl.GeoJSONSource | undefined;
		if (src) src.setData({ type: 'FeatureCollection', features: [] });
		if (map.getLayer('compare-hex-fill')) map.setPaintProperty('compare-hex-fill', 'fill-opacity', 0);
		if (map.getLayer('compare-hex-line')) map.setPaintProperty('compare-hex-line', 'line-opacity', 0);
	}

	export function highlightHexagon(h3index: string) {
		if (!map || !map.getLayer('hex-selected')) return;
		if (!h3index) {
			map.setFilter('hex-selected', ['==', ['get', 'h3index'], '']);
			return;
		}
		map.setFilter('hex-selected', ['==', ['get', 'h3index'], h3index]);
	}

	export function highlightHexagons(hexes: { h3index: string; color: string }[]) {
		if (!map || !map.getLayer('hex-selected')) return;
		if (hexes.length === 0) {
			map.setFilter('hex-selected', ['==', ['get', 'h3index'], '']);
			return;
		}
		const ids = hexes.map(h => h.h3index);
		// Build match expression for per-hex colors
		const matchExpr: any[] = ['match', ['get', 'h3index']];
		for (const h of hexes) {
			matchExpr.push(h.h3index, h.color);
		}
		matchExpr.push('#ffffff');
		map.setPaintProperty('hex-selected', 'line-color', matchExpr);
		map.setFilter('hex-selected', ['in', ['get', 'h3index'], ['literal', ids]]);
	}

	// ── Hex zone highlight functions ──────────────────────────────────────

	export function setHexZoneHighlight(zones: { h3indices: string[]; color: string }[], boundaryCache?: Map<string, number[][]>) {
		if (!map) return;
		const src = map.getSource('hex-zones') as maplibregl.GeoJSONSource | undefined;
		if (!src) return;

		if (zones.length === 0) {
			src.setData({ type: 'FeatureCollection', features: [] });
			return;
		}

		const features: any[] = [];
		for (const zone of zones) {
			for (const h3index of zone.h3indices) {
				const cached = boundaryCache?.get(h3index);
				if (!cached) continue;
				features.push({
					type: 'Feature',
					properties: { h3index, color: zone.color },
					geometry: { type: 'Polygon', coordinates: [cached] }
				});
			}
		}
		src.setData({ type: 'FeatureCollection', features });
	}

	export function clearHexZoneHighlight() {
		if (!map) return;
		const src = map.getSource('hex-zones') as maplibregl.GeoJSONSource | undefined;
		if (src) src.setData({ type: 'FeatureCollection', features: [] });
	}

	// ── Lasso / Zone functions ────────────────────────────────────────────

	export function setLassoMode(active: boolean) {
		lassoActive = active;
		if (!map) return;
		map.getCanvas().style.cursor = active ? 'crosshair' : '';
		if (active) {
			map.dragPan.disable();
		} else {
			map.dragPan.enable();
		}
	}

	export function updateLassoDraw(polygon: [number, number][]) {
		if (!map) return;
		const src = map.getSource('lasso-draw') as maplibregl.GeoJSONSource | undefined;
		if (!src) return;
		const coords = polygon.length >= 3
			? [[...polygon, polygon[0]]]
			: polygon.length >= 2
				? [polygon]  // just show as open line during draw
				: [[]];
		src.setData({
			type: 'Feature',
			geometry: { type: 'Polygon', coordinates: coords },
			properties: {}
		});
	}

	export function clearLassoDraw() {
		if (!map) return;
		const src = map.getSource('lasso-draw') as maplibregl.GeoJSONSource | undefined;
		if (!src) return;
		src.setData({
			type: 'Feature',
			geometry: { type: 'Polygon', coordinates: [[]] },
			properties: {}
		});
	}

	export function setZoneHighlight(zones: { redcodes: string[]; color: string }[]) {
		if (!map) return;
		const emptyFilter: any = ['==', ['get', 'redcode'], ''];
		if (zones.length === 0) {
			if (map.getLayer('zone-fill')) map.setFilter('zone-fill', emptyFilter);
			if (map.getLayer('zone-line')) map.setFilter('zone-line', emptyFilter);
			if (map.getLayer('zone-buildings')) map.setFilter('zone-buildings', emptyFilter);
			return;
		}

		// Collect all redcodes and build match expression for colors
		const allRedcodes: string[] = [];
		const matchExpr: any[] = ['match', ['get', 'redcode']];
		for (const zone of zones) {
			for (const rc of zone.redcodes) {
				allRedcodes.push(rc);
				matchExpr.push(rc, zone.color);
			}
		}
		matchExpr.push('rgba(0,0,0,0)'); // fallback

		const filter: any = ['in', ['get', 'redcode'], ['literal', allRedcodes]];

		if (map.getLayer('zone-fill')) {
			map.setPaintProperty('zone-fill', 'fill-color', matchExpr);
			map.setFilter('zone-fill', filter);
		}
		if (map.getLayer('zone-line')) {
			map.setPaintProperty('zone-line', 'line-color', matchExpr);
			map.setFilter('zone-line', filter);
		}
		// Building outlines: same match expression, same filter
		if (map.getLayer('zone-buildings')) {
			map.setPaintProperty('zone-buildings', 'line-color', matchExpr);
			map.setFilter('zone-buildings', filter);
		}
	}

	export function clearZoneHighlight() {
		if (!map) return;
		const emptyFilter: any = ['==', ['get', 'redcode'], ''];
		if (map.getLayer('zone-fill')) map.setFilter('zone-fill', emptyFilter);
		if (map.getLayer('zone-line')) map.setFilter('zone-line', emptyFilter);
		if (map.getLayer('zone-buildings')) map.setFilter('zone-buildings', emptyFilter);
	}

	export function getLassoActive(): boolean {
		return lassoActive;
	}

	export function getMap(): maplibregl.Map | null {
		return map ?? null;
	}
</script>

<div bind:this={container} style="width:100%;height:100%;"></div>
