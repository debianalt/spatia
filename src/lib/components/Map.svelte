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
	import corrientesBoundary from '$lib/data/corrientes_boundary.json';
	import corrientesMask from '$lib/data/corrientes_mask.json';
	import { isInsideMisiones } from '$lib/utils/misiones-pip';
	import { isInsideItapua } from '$lib/utils/itapua-pip';
	import { isInsideCorrientes } from '$lib/utils/corrientes-pip';

	let { mapStore }: { mapStore: MapStore } = $props();

	let container: HTMLDivElement;
	let hexLayerTitle = '';
	let hexLayerIsCategorical = false;
	let map: maplibregl.Map;
	let lassoActive = false;
	let catastroActive = false;
	let activeTerritoryId = 'misiones';
	let regionalModeActive = false;

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

			// Corrientes mask + border (hidden until territory switches)
			map.addSource('corrientes-mask', { type: 'geojson', data: corrientesMask as any });
			// Insert before province-fill so census radios render on top (same pattern as Misiones mask)
			map.addLayer({
				id: 'corrientes-mask-fill',
				type: 'fill',
				source: 'corrientes-mask',
				layout: { visibility: 'none' },
				paint: { 'fill-color': '#1a1a2e', 'fill-opacity': 0.75 }
			}, 'province-fill');
			map.addSource('corrientes-boundary', { type: 'geojson', data: corrientesBoundary as any });
			map.addLayer({
				id: 'corrientes-border',
				type: 'line',
				source: 'corrientes-boundary',
				layout: { visibility: 'none', 'line-join': 'round', 'line-cap': 'round' },
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
				}
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

			// Itapúa district polygons (31 GAUL distritos, hidden until territory switch)
			map.addSource('itapua-districts', { type: 'vector', url: getTilesUrl('itapua_districts') });
			const emptyDistrictFilter: any = ['==', ['get', 'district'], ''];
			map.addLayer({
				id: 'itapua-district-fill',
				type: 'fill',
				source: 'itapua-districts',
				'source-layer': 'districts',
				layout: { visibility: 'none' },
				paint: { 'fill-color': '#60a5fa', 'fill-opacity': 0.06 }
			});
			map.addLayer({
				id: 'itapua-district-line',
				type: 'line',
				source: 'itapua-districts',
				'source-layer': 'districts',
				layout: { visibility: 'none' },
				paint: {
					'line-color': '#d4d4d4',
					'line-width': ['interpolate', ['linear'], ['zoom'], 6, 1.2, 10, 0.6, 14, 0.3],
					'line-opacity': ['interpolate', ['linear'], ['zoom'], 6, 0.3, 10, 0.25, 14, 0.15]
				}
			});
			map.addLayer({
				id: 'itapua-district-selected-fill',
				type: 'fill',
				source: 'itapua-districts',
				'source-layer': 'districts',
				layout: { visibility: 'none' },
				paint: { 'fill-color': '#60a5fa', 'fill-opacity': 0.45 },
				filter: emptyDistrictFilter
			});
			map.addLayer({
				id: 'itapua-district-selected-line',
				type: 'line',
				source: 'itapua-districts',
				'source-layer': 'districts',
				layout: { visibility: 'none' },
				paint: { 'line-color': '#60a5fa', 'line-width': 3, 'line-opacity': 1 },
				filter: emptyDistrictFilter
			});

			// Corrientes buildings (pre-created, hidden until territory switch)
			map.addSource('corrientes-buildings', { type: 'vector', url: getTilesUrl('corrientes_buildings') });
			map.addLayer({
				id: 'corrientes-buildings-3d',
				type: 'fill-extrusion',
				source: 'corrientes-buildings',
				'source-layer': 'buildings',
				layout: { visibility: 'none' },
				paint: {
					'fill-extrusion-height': ['max', ['coalesce', ['get', 'best_height_m'], 5], 5],
					'fill-extrusion-base': 0,
					'fill-extrusion-color': mapStore.getColorExpr() as any,
					'fill-extrusion-opacity': 0.85
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
			map.addLayer({
				id: 'radio-highlight-corrientes',
				type: 'line',
				source: 'corrientes-buildings',
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
			map.addLayer({
				id: 'zone-buildings-corrientes',
				type: 'line',
				source: 'corrientes-buildings',
				'source-layer': 'buildings',
				paint: { 'line-color': '#60a5fa', 'line-width': 3, 'line-opacity': 0.85 },
				filter: emptyFilter
			});

			// ── Department bbox outlines — visible at all zoom levels ────────
			map.addSource('dept-highlights', {
				type: 'geojson',
				data: { type: 'FeatureCollection', features: [] }
			});
			map.addLayer({
				id: 'dept-highlight-fill',
				type: 'fill',
				source: 'dept-highlights',
				paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.07 }
			});
			map.addLayer({
				id: 'dept-highlight-line',
				type: 'line',
				source: 'dept-highlights',
				paint: {
					'line-color': ['get', 'color'],
					'line-width': ['interpolate', ['linear'], ['zoom'], 4, 2.5, 8, 1.5, 12, 1],
					'line-opacity': 0
				}
			});

			// ── Selected department outline (real polygon, single-dept mode) ──
			map.addSource('dept-outline', {
				type: 'geojson',
				data: { type: 'FeatureCollection', features: [] }
			});
			map.addLayer({
				id: 'dept-outline-line',
				type: 'line',
				source: 'dept-outline',
				paint: {
					'line-color': '#60a5fa',
					'line-width': ['interpolate', ['linear'], ['zoom'], 4, 2, 8, 1.8, 14, 1.2],
					'line-opacity': 0.85
				}
			});

			// ── Hexagon H3 layers (GeoJSON, loaded dynamically) ─────────
			map.addSource('hexagons', {
				type: 'geojson',
				data: { type: 'FeatureCollection', features: [] }
			});

			// Territory background: fills missing-parquet hexes so they show gray
			// instead of pure dark basemap, eliminating the "manchones" patch effect.
			map.addSource('territory-bg', {
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
				id: 'territory-bg-fill',
				type: 'fill',
				source: 'territory-bg',
				paint: { 'fill-color': 'rgb(55,65,81)', 'fill-opacity': 0.65 }
			}, 'hex-fill');
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
			map.addLayer({
				id: 'compare-hex-selected',
				type: 'line',
				source: 'compare-hexagons',
				paint: { 'line-color': '#f59e0b', 'line-width': 3, 'line-opacity': 0.9 },
				filter: ['==', ['get', 'h3index'], '']
			});

			// ── Regional mode hex choropleth (3rd territory slot) ────────────
			map.addSource('regional-hexagons', {
				type: 'geojson',
				data: { type: 'FeatureCollection', features: [] }
			});
			map.addLayer({
				id: 'regional-hex-fill',
				type: 'fill',
				source: 'regional-hexagons',
				paint: { 'fill-color': '#3b82f6', 'fill-opacity': 0 }
			});
			map.addLayer({
				id: 'regional-hex-line',
				type: 'line',
				source: 'regional-hexagons',
				paint: { 'line-color': '#1e293b', 'line-width': 0.5, 'line-opacity': 0 }
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
			if (regionalModeActive) setRegionalMapMode(true);
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

		// Corrientes buildings tooltip (same census data as Misiones)
		map.on('mousemove', 'corrientes-buildings-3d', (e) => {
			if (lassoActive) return;
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

			let html = `<b style="color:#60a5fa">${i18n.t('tip.building')}</b> ${i18n.t('tip.height')} ${h} m | ${i18n.t('tip.area')} ${a} m²<br>` +
				`<b style="color:#60a5fa">${i18n.t('tip.estPersons')}</b> <span style="color:#60a5fa;font-weight:600">${pers}</span>`;
			if (redcode) {
				html += `<br><span style="color:#a3a3a3">───</span><br>` +
					`<b style="color:#d4d4d4">${i18n.t('tip.radio')}</b> <span style="color:#d4d4d4">${redcode}</span><br>` +
					`<b style="color:#d4d4d4">${i18n.t('tip.pop')}</b> ${radioPop.toLocaleString()} &nbsp; <b style="color:#d4d4d4">${i18n.t('tip.density')}</b> ${radioDens} hab/km²<br>` +
					`<b style="color:#d4d4d4">${i18n.t('label.dwellings')}:</b> ${radioViv.toLocaleString()} &nbsp; <b style="color:#d4d4d4">${i18n.t('label.households')}:</b> ${radioHog.toLocaleString()} &nbsp; <b style="color:#d4d4d4">${i18n.t('label.area')}:</b> ${radioAreaKm2} km²`;
			}
			tooltip.innerHTML = html;
			tooltip.style.display = 'block';
			tooltip.style.left = (e.originalEvent.clientX + 14) + 'px';
			tooltip.style.top = (e.originalEvent.clientY + 14) + 'px';
		});
		map.on('mouseleave', 'corrientes-buildings-3d', () => {
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
			const res = p.is_residential ? 'residencial' : (p.subtype || 'no residencial');
			const dist = p.distrito || '';
			const est = p.est_personas > 0 ? ` | ~${p.est_personas} pers.` : '';
			tooltip.innerHTML = `<b style="color:#60a5fa">${i18n.t('tip.building')}</b> ${h} m | ${a} m\u00B2 | ${res}${est}${dist ? ` | ${dist}` : ''}`;
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

		// Itapúa area hover badge (district layer + regional hex layer)
		const dispatchItapuaEnter = () => container.dispatchEvent(new CustomEvent('itapua-area-enter', { bubbles: true }));
		const dispatchItapuaLeave = () => container.dispatchEvent(new CustomEvent('itapua-area-leave', { bubbles: true }));
		map.on('mouseenter', 'itapua-district-fill', dispatchItapuaEnter);
		map.on('mouseleave', 'itapua-district-fill', dispatchItapuaLeave);
		map.on('mouseenter', 'regional-hex-fill', () => {
			dispatchItapuaEnter();
			if (!lassoActive) map.getCanvas().style.cursor = 'pointer';
		});
		map.on('mouseleave', 'regional-hex-fill', () => {
			dispatchItapuaLeave();
			if (!lassoActive) map.getCanvas().style.cursor = '';
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

		// Corrientes buildings: click-to-select radio (same behavior as buildings-3d)
		map.on('click', 'corrientes-buildings-3d', (e) => {
			if (lassoActive) return;
			if (mapStore.activeHexLayer) return;
			if (catastroClickMode !== 'none') return;
			const redcode = e.features![0].properties!.redcode;
			if (!redcode) return;

			if (mapStore.hasRadio(redcode)) {
				container.dispatchEvent(new CustomEvent('radio-deselect', { bubbles: true, detail: { redcode } }));
			} else {
				const canvas = map.getCanvas();
				const allFeatures = map.queryRenderedFeatures(
					[[0, 0], [canvas.width, canvas.height]],
					{ layers: ['corrientes-buildings-3d'] }
				);
				const selected: Record<string, any>[] = [];
				const seen = new Set<string | number>();
				for (const f of allFeatures) {
					const id = f.id ?? `${f.properties?.area_m2}_${f.properties?.est_personas}`;
					if (f.properties?.redcode !== redcode || seen.has(id)) continue;
					seen.add(id as string | number);
					selected.push(f.properties!);
				}
				container.dispatchEvent(new CustomEvent('radio-select', {
					bubbles: true,
					detail: { redcode, selected, census: e.features![0].properties! }
				}));
			}
		});

		// Itapúa district click: select/deselect district
		map.on('click', 'itapua-district-fill', (e) => {
			if (lassoActive || mapStore.activeHexLayer) return;
			const distrito = e.features![0].properties!.district;
			const personas = e.features![0].properties!.personas ?? 0;
			if (!distrito) return;
			const event = mapStore.hasDistrict(distrito) ? 'district-deselect' : 'district-select';
			container.dispatchEvent(new CustomEvent(event, { bubbles: true, detail: { distrito, personas } }));
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

		// Click on regional (Itapúa) hex in regional mode
		map.on('click', 'regional-hex-fill', (e) => {
			if (lassoActive) return;
			const h3index = e.features![0].properties!.h3index;
			if (!h3index) return;
			container.dispatchEvent(new CustomEvent('regional-hex-select', {
				bubbles: true,
				detail: { h3index }
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
			if (p.nodata === true || p.nodata === 'true') {
				valueLine = `<span style="color:#94a3b8;font-weight:600;font-style:italic">${i18n.t('legend.noData')}</span>`;
			} else if (hexLayerIsCategorical && p.type_label) {
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

		map.on('mousemove', 'compare-hex-fill', () => {
			if (!lassoActive) map.getCanvas().style.cursor = 'pointer';
		});
		map.on('mouseleave', 'compare-hex-fill', () => {
			if (!lassoActive) map.getCanvas().style.cursor = '';
		});

		// General mousemove: show pointer over blank territory areas (Option A nav hint)
		map.on('mousemove', (e) => {
			if (lassoActive) return;
			const canvas = map.getCanvas();
			if (canvas.style.cursor !== '') return; // specific layer handler already set it
			const { lat, lng } = e.lngLat;
			const inTerritory = isInsideItapua(lat, lng) || isInsideMisiones(lat, lng) || isInsideCorrientes(lat, lng);
			canvas.style.cursor = inTerritory ? 'pointer' : '';
		});

		// General click: switch territory scope when clicking blank area inside a territory
		const TERRITORY_LAYERS = ['hex-fill', 'compare-hex-fill', 'regional-hex-fill',
			'buildings-3d', 'corrientes-buildings-3d', 'itapua-buildings-3d',
			'buildings-flat', 'province-fill', 'itapua-district-fill'];
		map.on('click', (e) => {
			if (lassoActive) return;
			const activeLayers = TERRITORY_LAYERS.filter(l => map.getLayer(l));
			if (activeLayers.length > 0 && map.queryRenderedFeatures(e.point, { layers: activeLayers }).length > 0) return;
			const { lat, lng } = e.lngLat;
			let territory: string | null = null;
			if (isInsideItapua(lat, lng)) territory = 'itapua_py';
			else if (isInsideMisiones(lat, lng)) territory = 'misiones';
			else if (isInsideCorrientes(lat, lng)) territory = 'corrientes';
			if (territory) {
				container.dispatchEvent(new CustomEvent('territory-map-select', {
					bubbles: true,
					detail: { territory }
				}));
			}
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
		const isCorrientes = activeTerritoryId === 'corrientes';
		const isItapua = activeTerritoryId === 'itapua_py';
		const layer = isCorrientes ? 'corrientes-buildings-3d'
		            : isItapua    ? 'itapua-buildings-3d'
		            :               'buildings-3d';
		const opacity = isItapua ? 0.92 : 0.85;
		const colorExpr = isItapua ? mapStore.getHeightColorExpr() : mapStore.getColorExpr();
		if (map?.getLayer(layer)) {
			map.setLayoutProperty(layer, 'visibility', 'visible');
			map.setPaintProperty(layer, 'fill-extrusion-color', colorExpr as any);
			map.setPaintProperty(layer, 'fill-extrusion-opacity', opacity);
		}
	}

	export function updateColorExpr() {
		const colorExpr = mapStore.getColorExpr() as any;
		if (map?.getLayer('buildings-3d')) {
			map.setPaintProperty('buildings-3d', 'fill-extrusion-color', colorExpr);
		}
		if (map?.getLayer('corrientes-buildings-3d')) {
			map.setPaintProperty('corrientes-buildings-3d', 'fill-extrusion-color', colorExpr);
		}
	}

	export function setRadioHighlight(radios: Array<{redcode: string, color: string}>) {
		const isCorrientes = activeTerritoryId === 'corrientes';
		const activeLayer  = isCorrientes ? 'radio-highlight-corrientes' : 'radio-highlight';
		const inactiveLayer = isCorrientes ? 'radio-highlight' : 'radio-highlight-corrientes';
		const emptyFilter: any = ['==', ['get', 'redcode'], ''];
		if (map?.getLayer(inactiveLayer)) map.setFilter(inactiveLayer, emptyFilter);
		if (!map?.getLayer(activeLayer)) return;
		if (radios.length === 0) {
			map.setFilter(activeLayer, emptyFilter);
			// In regional mode: also clear census polygon highlights
			if (regionalModeActive) {
				if (map.getLayer('selected-fill')) map.setFilter('selected-fill', emptyFilter);
				if (map.getLayer('selected-line')) map.setFilter('selected-line', emptyFilter);
			}
		} else {
			const redcodes = radios.map(r => r.redcode);
			const matchExpr: any[] = ['match', ['get', 'redcode']];
			for (const r of radios) {
				matchExpr.push(r.redcode, r.color);
			}
			matchExpr.push('#60a5fa'); // fallback
			map.setPaintProperty(activeLayer, 'line-color', matchExpr);
			map.setPaintProperty(activeLayer, 'line-width', 4.5);
			map.setFilter(activeLayer, ['in', ['get', 'redcode'], ['literal', redcodes]]);
			// In regional mode: also highlight census radio polygons for all territories
			if (regionalModeActive) {
				const polyFilter: any = ['in', ['get', 'redcode'], ['literal', redcodes]];
				if (map.getLayer('selected-fill')) {
					map.setPaintProperty('selected-fill', 'fill-color', matchExpr);
					map.setPaintProperty('selected-fill', 'fill-opacity', 0.30);
					map.setFilter('selected-fill', polyFilter);
				}
				if (map.getLayer('selected-line')) {
					map.setPaintProperty('selected-line', 'line-color', matchExpr);
					map.setPaintProperty('selected-line', 'line-width', 2.5);
					map.setFilter('selected-line', polyFilter);
				}
			}
		}
	}

	export function clearRadioHighlight() {
		if (!map) return;
		const emptyFilter: any = ['==', ['get', 'redcode'], ''];
		map.setFilter('radio-highlight', emptyFilter);
		if (map.getLayer('radio-highlight-corrientes')) map.setFilter('radio-highlight-corrientes', emptyFilter);
		map.setFilter('selected-fill', emptyFilter);
		map.setFilter('selected-line', emptyFilter);
	}

	export function setDistrictHighlight(districts: Array<{distrito: string, color: string}>) {
		if (!map) return;
		const emptyFilter: any = ['==', ['get', 'district'], ''];
		const fillId = 'itapua-district-selected-fill';
		const lineId = 'itapua-district-selected-line';
		if (!map.getLayer(fillId)) return;
		if (districts.length === 0) {
			map.setFilter(fillId, emptyFilter);
			map.setFilter(lineId, emptyFilter);
			return;
		}
		const names = districts.map(d => d.distrito);
		const matchExpr: any[] = ['match', ['get', 'district']];
		for (const d of districts) {
			matchExpr.push(d.distrito, d.color);
		}
		matchExpr.push('#60a5fa'); // fallback
		map.setPaintProperty(fillId, 'fill-color', matchExpr);
		map.setPaintProperty(fillId, 'fill-opacity', 0.45);
		map.setFilter(fillId, ['in', ['get', 'district'], ['literal', names]]);
		map.setPaintProperty(lineId, 'line-color', matchExpr);
		map.setFilter(lineId, ['in', ['get', 'district'], ['literal', names]]);
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

	export function fitBoundsDept(bbox: [number, number, number, number]) {
		// bbox: [minLng, minLat, maxLng, maxLat] — fits tightly to actual dept hexagons
		map?.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], {
			padding: 20,
			pitch: 50,
			duration: 1500,
		});
	}

	export function updateDeptHighlights(
		primary: [number, number, number, number] | null,
		compare: [number, number, number, number] | null
	) {
		const src = map?.getSource('dept-highlights') as maplibregl.GeoJSONSource | undefined;
		if (!src) return;
		const features: any[] = [];
		if (primary) {
			const [w, s, e, n] = primary;
			features.push({
				type: 'Feature',
				properties: { color: '#60a5fa' },
				geometry: { type: 'Polygon', coordinates: [[[w,s],[e,s],[e,n],[w,n],[w,s]]] }
			});
		}
		if (compare) {
			const [w, s, e, n] = compare;
			features.push({
				type: 'Feature',
				properties: { color: '#f59e0b' },
				geometry: { type: 'Polygon', coordinates: [[[w,s],[e,s],[e,n],[w,n],[w,s]]] }
			});
		}
		src.setData({ type: 'FeatureCollection', features });
		// Show border only in compare mode (both depts present); hide in single-dept mode
		const compareMode = !!(primary && compare);
		if (map.getLayer('dept-highlight-line')) {
			map.setPaintProperty('dept-highlight-line', 'line-opacity',
				compareMode ? ['interpolate', ['linear'], ['zoom'], 4, 0.8, 10, 0.5, 14, 0.25] : 0
			);
		}
		if (map.getLayer('dept-highlight-fill')) {
			map.setPaintProperty('dept-highlight-fill', 'fill-opacity', compareMode ? 0.06 : 0);
		}
	}

	export function setDeptOutline(feature: any | null) {
		const src = map?.getSource('dept-outline') as maplibregl.GeoJSONSource | undefined;
		if (!src) return;
		src.setData({
			type: 'FeatureCollection',
			features: feature ? [feature] : []
		});
	}

	function applyTerritoryVisibility() {
		if (!map) return;

		if (regionalModeActive) {
			// Regional mode: show ALL territory buildings simultaneously (all 3 PMTiles pre-loaded).
			// Fog masks and borders are managed by setRegionalMapMode().
			const colorExprDefault = mapStore.getColorExpr();
			const colorExprItapua = mapStore.getHeightColorExpr();
			for (const l of ['buildings-3d', 'itapua-buildings-3d', 'corrientes-buildings-3d']) {
				if (map.getLayer(l)) {
					map.setLayoutProperty(l, 'visibility', 'visible');
					const expr = l === 'itapua-buildings-3d' ? colorExprItapua : colorExprDefault;
					map.setPaintProperty(l, 'fill-extrusion-color', expr as any);
				}
			}
			return;
		}

		const isMisiones = activeTerritoryId === 'misiones';
		const isItapua = activeTerritoryId === 'itapua_py';
		const isCorrientes = activeTerritoryId === 'corrientes';

		// Province outline (radios): visible for Misiones + Corrientes, filtered by codprov
		for (const layerId of ['province-fill', 'province-line']) {
			if (map.getLayer(layerId)) {
				map.setLayoutProperty(layerId, 'visibility', (isMisiones || isCorrientes) ? 'visible' : 'none');
				if (isMisiones || isCorrientes) {
					map.setFilter(layerId, ['==', ['get', 'codprov'], isCorrientes ? '18' : '54']);
				}
			}
		}
		// Misiones-only: fog mask + province border polygon
		for (const layerId of ['mask-fill', 'province-border']) {
			if (map.getLayer(layerId)) {
				map.setLayoutProperty(layerId, 'visibility', isMisiones ? 'visible' : 'none');
			}
		}
		// Itapúa fog mask
		if (map.getLayer('itapua-mask-fill')) {
			map.setLayoutProperty('itapua-mask-fill', 'visibility', isItapua ? 'visible' : 'none');
		}
		// Corrientes fog mask + border
		if (map.getLayer('corrientes-mask-fill')) {
			map.setLayoutProperty('corrientes-mask-fill', 'visibility', isCorrientes ? 'visible' : 'none');
		}
		if (map.getLayer('corrientes-border')) {
			map.setLayoutProperty('corrientes-border', 'visibility', isCorrientes ? 'visible' : 'none');
		}
		// Itapúa district polygons: show only in Itapúa territory
		for (const l of ['itapua-district-fill', 'itapua-district-line', 'itapua-district-selected-fill', 'itapua-district-selected-line']) {
			if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', isItapua ? 'visible' : 'none');
		}

		// Buildings: show only the active territory's layer, hide the other two
		const activeLayer = isCorrientes ? 'corrientes-buildings-3d'
		                  : isItapua     ? 'itapua-buildings-3d'
		                  :               'buildings-3d';
		const otherLayers = ['buildings-3d', 'itapua-buildings-3d', 'corrientes-buildings-3d']
			.filter(l => l !== activeLayer);
		for (const l of otherLayers) {
			if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', 'none');
		}
		if (map.getLayer(activeLayer)) {
			map.setLayoutProperty(activeLayer, 'visibility', 'visible');
			const colorExpr = isItapua ? mapStore.getHeightColorExpr() : mapStore.getColorExpr();
			map.setPaintProperty(activeLayer, 'fill-extrusion-color', colorExpr as any);
		}
	}

	export function setActiveTerritory(territoryId: string) {
		activeTerritoryId = territoryId;
		applyTerritoryVisibility();
	}

	function regionalProvinceClickHandler(e: any) {
		if (lassoActive || mapStore.activeHexLayer) return;
		const redcode = e.features?.[0]?.properties?.redcode;
		if (!redcode) return;
		if (mapStore.hasRadio(redcode)) {
			container.dispatchEvent(new CustomEvent('radio-deselect', { bubbles: true, detail: { redcode } }));
		} else {
			container.dispatchEvent(new CustomEvent('radio-select', {
				bubbles: true,
				detail: { redcode, selected: [], census: e.features![0].properties! }
			}));
		}
	}

	export function setRegionalMapMode(active: boolean) {
		regionalModeActive = active;
		if (!map) return;
		if (active) {
			// Hide all fog masks
			for (const id of ['mask-fill', 'itapua-mask-fill', 'corrientes-mask-fill']) {
				if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'none');
			}
			// Show all territory borders
			for (const id of ['province-border', 'itapua-border', 'corrientes-border']) {
				if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'visible');
			}
			// Province fill/line: show both AR provinces (remove codprov filter)
			for (const id of ['province-fill', 'province-line']) {
				if (map.getLayer(id)) {
					map.setLayoutProperty(id, 'visibility', 'visible');
					map.setFilter(id, null);
				}
			}
			// Itapúa district outlines + selection layers: always visible in regional mode
			for (const id of ['itapua-district-fill', 'itapua-district-line', 'itapua-district-selected-fill', 'itapua-district-selected-line']) {
				if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'visible');
			}
			// Enable radio selection by clicking directly on census radio polygons
			map.on('click', 'province-fill', regionalProvinceClickHandler);
		} else {
			map.off('click', 'province-fill', regionalProvinceClickHandler);
			// Full restore via standard territory visibility logic
			applyTerritoryVisibility();
		}
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
		for (const layer of ['buildings-3d', 'itapua-buildings-3d', 'corrientes-buildings-3d']) {
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
	// "Sin cobertura" — azul-gris claro, distinguible del territory-bg (#374151).
	// Usado para hex sobre cuerpos de agua o zonas sin medición raster/censal.
	const NODATA_COLOR = '#4b6584';

	function computeHexColor(value: number, colorScale: string, minVal: number, maxVal: number, range: number): string {
		if (typeof value !== 'number' || !Number.isFinite(value)) return NODATA_COLOR;
		// Legacy: value=0 era usado como proxy de nodata. Tras la refactorización,
		// setHexChoropleth maneja nodata explícitamente antes de llamar a esta función.
		// Este branch permanece como red de seguridad para callsites legacy.
		if (value === 0 && colorScale !== 'diverging' && colorScale !== 'categorical' && colorScale !== 'lisa') return NODATA_COLOR;
		if (colorScale === 'lisa') {
			const LISA: Record<number, string> = { 1: '#3b82f6', 2: '#60a5fa', 3: '#f97316', 4: '#ef4444' };
			return LISA[Math.round(value)] ?? 'rgb(55,65,81)';
		}
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

	export function setHexChoropleth(entries: { h3index: string; value: number | null; properties?: Record<string, number>; boundary?: number[][]; nodata?: boolean }[], colorScale: 'flood' | 'sequential' | 'diverging' | 'categorical' | 'green' | 'warm' | 'lisa' = 'flood', domain?: [number, number]) {
		if (!map) return;
		const src = map.getSource('hexagons') as maplibregl.GeoJSONSource | undefined;
		if (!src) return;

		if (entries.length === 0) {
			src.setData({ type: 'FeatureCollection', features: [] });
			map.setPaintProperty('hex-fill', 'fill-opacity', 0);
			map.setPaintProperty('hex-line', 'line-opacity', 0);
			return;
		}

		const isNodata = (e: { value: number | null; nodata?: boolean }) =>
			e.nodata === true || e.value === null || typeof e.value !== 'number' || !Number.isFinite(e.value);

		let minVal: number, maxVal: number;
		if (domain && colorScale !== 'diverging' && colorScale !== 'categorical') {
			// Use provincial percentile bounds (P2/P98) for consistent cross-department coloring
			[minVal, maxVal] = domain;
		} else {
			// Fallback: local min/max from entries (skip nodata)
			minVal = Infinity; maxVal = -Infinity;
			for (const e of entries) {
				if (isNodata(e)) continue;
				const v = e.value as number;
				if (v < minVal) minVal = v;
				if (v > maxVal) maxVal = v;
			}
			if (!Number.isFinite(minVal)) { minVal = 0; maxVal = 1; }
		}
		const range = maxVal - minVal || 1;

		const getColor = (value: number) => computeHexColor(value, colorScale, minVal, maxVal, range);

		const features: any[] = [];
		for (const entry of entries) {
			if (!entry.boundary) continue;
			if (isNodata(entry)) {
				features.push({
					type: 'Feature',
					properties: {
						h3index: entry.h3index,
						value: null,
						color: NODATA_COLOR,
						nodata: true,
						...(entry.properties || {})
					},
					geometry: { type: 'Polygon', coordinates: [entry.boundary] }
				});
				continue;
			}
			features.push({
				type: 'Feature',
				properties: {
					h3index: entry.h3index,
					value: entry.value,
					color: getColor(entry.value as number),
					...(entry.properties || {})
				},
				geometry: { type: 'Polygon', coordinates: [entry.boundary] }
			});
		}

		src.setData({ type: 'FeatureCollection', features });
		map.setPaintProperty('hex-fill', 'fill-color', ['get', 'color']);
		map.setPaintProperty('hex-fill', 'fill-opacity', 0.78);
		map.setPaintProperty('hex-line', 'line-color', '#374151');
		map.setPaintProperty('hex-line', 'line-width', 0.5);
		map.setPaintProperty('hex-line', 'line-opacity', 0.25);

		const bgSrc = map.getSource('territory-bg') as maplibregl.GeoJSONSource | undefined;
		if (bgSrc) {
			const bgData = activeTerritoryId === 'corrientes' ? corrientesBoundary
			             : activeTerritoryId === 'itapua_py'  ? itapuaBoundary
			             : misionesBoundary;
			bgSrc.setData(bgData as any);
		}
	}

	export function clearHexChoropleth() {
		if (!map) return;
		const src = map.getSource('hexagons') as maplibregl.GeoJSONSource | undefined;
		if (src) src.setData({ type: 'FeatureCollection', features: [] });
		if (map.getLayer('hex-fill')) map.setPaintProperty('hex-fill', 'fill-opacity', 0);
		if (map.getLayer('hex-line')) map.setPaintProperty('hex-line', 'line-opacity', 0);
		if (map.getLayer('hex-selected')) map.setFilter('hex-selected', ['==', ['get', 'h3index'], '']);
		if (map.getLayer('compare-hex-selected')) map.setFilter('compare-hex-selected', ['==', ['get', 'h3index'], '']);
		const bgSrc = map.getSource('territory-bg') as maplibregl.GeoJSONSource | undefined;
		if (bgSrc) bgSrc.setData({ type: 'FeatureCollection', features: [] });
	}

	export function setCompareHexChoropleth(entries: { h3index: string; value: number | null; properties?: Record<string, number>; boundary?: number[][]; nodata?: boolean }[], colorScale: 'flood' | 'sequential' | 'diverging' | 'categorical' | 'green' | 'warm' = 'sequential', domain?: [number, number]) {
		if (!map) return;
		const src = map.getSource('compare-hexagons') as maplibregl.GeoJSONSource | undefined;
		if (!src) return;

		if (entries.length === 0) {
			src.setData({ type: 'FeatureCollection', features: [] });
			map.setPaintProperty('compare-hex-fill', 'fill-opacity', 0);
			map.setPaintProperty('compare-hex-line', 'line-opacity', 0);
			return;
		}

		const isNodata = (e: { value: number | null; nodata?: boolean }) =>
			e.nodata === true || e.value === null || typeof e.value !== 'number' || !Number.isFinite(e.value);

		let minVal: number, maxVal: number;
		if (domain && colorScale !== 'diverging' && colorScale !== 'categorical') {
			[minVal, maxVal] = domain;
		} else {
			minVal = Infinity; maxVal = -Infinity;
			for (const e of entries) {
				if (isNodata(e)) continue;
				const v = e.value as number;
				if (v < minVal) minVal = v;
				if (v > maxVal) maxVal = v;
			}
			if (!Number.isFinite(minVal)) { minVal = 0; maxVal = 1; }
		}
		const range = maxVal - minVal || 1;
		const getColor = (v: number) => computeHexColor(v, colorScale, minVal, maxVal, range);

		const features: any[] = [];
		for (const entry of entries) {
			if (!entry.boundary) continue;
			if (isNodata(entry)) {
				features.push({
					type: 'Feature',
					properties: { h3index: entry.h3index, value: null, color: NODATA_COLOR, nodata: true, ...(entry.properties || {}) },
					geometry: { type: 'Polygon', coordinates: [entry.boundary] }
				});
				continue;
			}
			features.push({
				type: 'Feature',
				properties: { h3index: entry.h3index, value: entry.value, color: getColor(entry.value as number), ...(entry.properties || {}) },
				geometry: { type: 'Polygon', coordinates: [entry.boundary] }
			});
		}

		src.setData({ type: 'FeatureCollection', features });
		map.setPaintProperty('compare-hex-fill', 'fill-color', ['get', 'color']);
		map.setPaintProperty('compare-hex-fill', 'fill-opacity', 0.78);
		map.setPaintProperty('compare-hex-line', 'line-color', '#374151');
		map.setPaintProperty('compare-hex-line', 'line-width', 0.5);
		map.setPaintProperty('compare-hex-line', 'line-opacity', 0.25);
	}

	export function clearCompareHexChoropleth() {
		if (!map) return;
		const src = map.getSource('compare-hexagons') as maplibregl.GeoJSONSource | undefined;
		if (src) src.setData({ type: 'FeatureCollection', features: [] });
		if (map.getLayer('compare-hex-fill')) map.setPaintProperty('compare-hex-fill', 'fill-opacity', 0);
		if (map.getLayer('compare-hex-line')) map.setPaintProperty('compare-hex-line', 'line-opacity', 0);
		if (map.getLayer('compare-hex-selected')) map.setFilter('compare-hex-selected', ['==', ['get', 'h3index'], '']);
	}

	export function setRegionalHexChoropleth(entries: { h3index: string; value: number | null; properties?: Record<string, number>; boundary?: number[][]; nodata?: boolean }[], colorScale: 'flood' | 'sequential' | 'diverging' | 'categorical' | 'green' | 'warm' = 'sequential', domain?: [number, number]) {
		if (!map) return;
		const src = map.getSource('regional-hexagons') as maplibregl.GeoJSONSource | undefined;
		if (!src) return;

		if (entries.length === 0) {
			src.setData({ type: 'FeatureCollection', features: [] });
			map.setPaintProperty('regional-hex-fill', 'fill-opacity', 0);
			map.setPaintProperty('regional-hex-line', 'line-opacity', 0);
			return;
		}

		const isNodata = (e: { value: number | null; nodata?: boolean }) =>
			e.nodata === true || e.value === null || typeof e.value !== 'number' || !Number.isFinite(e.value);

		let minVal: number, maxVal: number;
		if (domain && colorScale !== 'diverging' && colorScale !== 'categorical') {
			[minVal, maxVal] = domain;
		} else {
			minVal = Infinity; maxVal = -Infinity;
			for (const e of entries) {
				if (isNodata(e)) continue;
				const v = e.value as number;
				if (v < minVal) minVal = v;
				if (v > maxVal) maxVal = v;
			}
			if (!Number.isFinite(minVal)) { minVal = 0; maxVal = 1; }
		}
		const range = maxVal - minVal || 1;
		const getColor = (v: number) => computeHexColor(v, colorScale, minVal, maxVal, range);

		const features: any[] = [];
		for (const entry of entries) {
			if (!entry.boundary) continue;
			if (isNodata(entry)) {
				features.push({
					type: 'Feature',
					properties: { h3index: entry.h3index, value: null, color: NODATA_COLOR, nodata: true, ...(entry.properties || {}) },
					geometry: { type: 'Polygon', coordinates: [entry.boundary] }
				});
				continue;
			}
			features.push({
				type: 'Feature',
				properties: { h3index: entry.h3index, value: entry.value, color: getColor(entry.value as number), ...(entry.properties || {}) },
				geometry: { type: 'Polygon', coordinates: [entry.boundary] }
			});
		}

		src.setData({ type: 'FeatureCollection', features });
		map.setPaintProperty('regional-hex-fill', 'fill-color', ['get', 'color']);
		map.setPaintProperty('regional-hex-fill', 'fill-opacity', 0.78);
		map.setPaintProperty('regional-hex-line', 'line-color', '#374151');
		map.setPaintProperty('regional-hex-line', 'line-width', 0.5);
		map.setPaintProperty('regional-hex-line', 'line-opacity', 0.25);
	}

	export function clearRegionalHexChoropleth() {
		if (!map) return;
		const src = map.getSource('regional-hexagons') as maplibregl.GeoJSONSource | undefined;
		if (src) src.setData({ type: 'FeatureCollection', features: [] });
		if (map.getLayer('regional-hex-fill')) map.setPaintProperty('regional-hex-fill', 'fill-opacity', 0);
		if (map.getLayer('regional-hex-line')) map.setPaintProperty('regional-hex-line', 'line-opacity', 0);
	}

	export function highlightHexagon(h3index: string) {
		if (!map || !map.getLayer('hex-selected')) return;
		if (!h3index) {
			map.setFilter('hex-selected', ['==', ['get', 'h3index'], '']);
			return;
		}
		map.setFilter('hex-selected', ['==', ['get', 'h3index'], h3index]);
	}

	export function highlightHexagons(
		hexes: { h3index: string; color: string }[],
		compareHexes?: { h3index: string; color: string }[]
	) {
		if (!map || !map.getLayer('hex-selected')) return;
		if (hexes.length === 0) {
			map.setFilter('hex-selected', ['==', ['get', 'h3index'], '']);
		} else {
			const ids = hexes.map(h => h.h3index);
			const matchExpr: any[] = ['match', ['get', 'h3index']];
			for (const h of hexes) matchExpr.push(h.h3index, h.color);
			matchExpr.push('#ffffff');
			map.setPaintProperty('hex-selected', 'line-color', matchExpr);
			map.setFilter('hex-selected', ['in', ['get', 'h3index'], ['literal', ids]]);
		}

		if (!map.getLayer('compare-hex-selected')) return;
		if (!compareHexes || compareHexes.length === 0) {
			map.setFilter('compare-hex-selected', ['==', ['get', 'h3index'], '']);
			return;
		}
		const cIds = compareHexes.map(h => h.h3index);
		const cMatch: any[] = ['match', ['get', 'h3index']];
		for (const h of compareHexes) cMatch.push(h.h3index, h.color);
		cMatch.push('#f59e0b');
		map.setPaintProperty('compare-hex-selected', 'line-color', cMatch);
		map.setFilter('compare-hex-selected', ['in', ['get', 'h3index'], ['literal', cIds]]);
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
			if (map.getLayer('zone-buildings-corrientes')) map.setFilter('zone-buildings-corrientes', emptyFilter);
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
		// Building outlines: highlight both territory layers (regional mode shows mixed zones)
		if (map.getLayer('zone-buildings')) {
			map.setPaintProperty('zone-buildings', 'line-color', matchExpr);
			map.setFilter('zone-buildings', filter);
		}
		if (map.getLayer('zone-buildings-corrientes')) {
			map.setPaintProperty('zone-buildings-corrientes', 'line-color', matchExpr);
			map.setFilter('zone-buildings-corrientes', filter);
		}
	}

	export function clearZoneHighlight() {
		if (!map) return;
		const emptyFilter: any = ['==', ['get', 'redcode'], ''];
		if (map.getLayer('zone-fill')) map.setFilter('zone-fill', emptyFilter);
		if (map.getLayer('zone-line')) map.setFilter('zone-line', emptyFilter);
		if (map.getLayer('zone-buildings')) map.setFilter('zone-buildings', emptyFilter);
		if (map.getLayer('zone-buildings-corrientes')) map.setFilter('zone-buildings-corrientes', emptyFilter);
	}

	export function getLassoActive(): boolean {
		return lassoActive;
	}

	export function getMap(): maplibregl.Map | null {
		return map ?? null;
	}
</script>

<div bind:this={container} style="width:100%;height:100%;"></div>
