<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { Protocol } from 'pmtiles';
	import { getTilesUrl, BASEMAP, MAP_INIT, TERRAIN_CONFIG } from '$lib/config';
	import { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import misionesBoundary from '$lib/data/misiones_boundary.json';
	import misionesMask from '$lib/data/misiones_mask.json';

	let { mapStore }: { mapStore: MapStore } = $props();

	let container: HTMLDivElement;
	let map: maplibregl.Map;
	let lassoActive = false;
	let catastroActive = false;

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
					'fill-extrusion-opacity': 0.85
				}
			});

			// Lighting (adjusted for terrain + buildings interaction)
			map.setLight({
				anchor: 'viewport',
				color: '#ffffff',
				intensity: 0.4,
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

		// Click-to-select/deselect radio (multi-select)
		map.on('click', 'buildings-3d', (e) => {
			if (lassoActive) return; // suppress building click during lasso
			if (mapStore.activeHexLayer) return; // hex mode: only hex-select, not radio
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
			const score = p.value != null ? Number(p.value).toFixed(1) : '—';
			const h3short = p.h3index.slice(0, 4) + '...' + p.h3index.slice(-4);
			tooltip.innerHTML = `<b style="color:#60a5fa">${h3short}</b><br>Score: <span style="color:#e2e8f0;font-weight:600">${score}</span>`;
			tooltip.style.display = 'block';
			tooltip.style.left = (e.originalEvent.clientX + 14) + 'px';
			tooltip.style.top = (e.originalEvent.clientY + 14) + 'px';
		});

		map.on('mouseleave', 'hex-fill', () => {
			if (!lassoActive) map.getCanvas().style.cursor = '';
			tooltip.style.display = 'none';
		});
	}

	export function flyToInit() {
		map?.flyTo({ ...MAP_INIT, duration: 1200 });
	}

	export function setPitch(p: number) {
		map?.easeTo({ pitch: p, duration: 200 });
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

	export function highlightChatRadios(redcodes: string[], color: string = '#60a5fa') {
		if (!map || !map.isStyleLoaded()) return;
		if (!map.getLayer('chat-highlight')) {
			map.addLayer({
				id: 'chat-highlight',
				type: 'fill',
				source: 'radios',
				'source-layer': 'radios',
				paint: {
					'fill-color': color,
					'fill-opacity': 0.25
				},
				filter: ['==', ['get', 'redcode'], '']
			});
		}
		if (!map.getLayer('chat-highlight-line')) {
			map.addLayer({
				id: 'chat-highlight-line',
				type: 'line',
				source: 'radios',
				'source-layer': 'radios',
				paint: {
					'line-color': color,
					'line-width': 3,
					'line-opacity': 0.9
				},
				filter: ['==', ['get', 'redcode'], '']
			});
		}
		if (redcodes.length === 0) {
			map.setFilter('chat-highlight', ['==', ['get', 'redcode'], '']);
			map.setFilter('chat-highlight-line', ['==', ['get', 'redcode'], '']);
		} else {
			// Update paint before filter to avoid flash
			map.setPaintProperty('chat-highlight', 'fill-color', color);
			map.setPaintProperty('chat-highlight', 'fill-opacity', color === '#ef4444' ? 0.55 : 0.25);
			map.setFilter('chat-highlight', ['in', ['get', 'redcode'], ['literal', redcodes]]);
			map.setPaintProperty('chat-highlight-line', 'line-color', color);
			map.setFilter('chat-highlight-line', ['in', ['get', 'redcode'], ['literal', redcodes]]);
		}
	}

	export function setChatChoropleth(entries: { redcode: string; value: number }[]) {
		if (!map || !map.isStyleLoaded()) return;

		// Ensure the chat-highlight layer exists
		if (!map.getLayer('chat-highlight')) {
			map.addLayer({
				id: 'chat-highlight',
				type: 'fill',
				source: 'radios',
				'source-layer': 'radios',
				paint: {
					'fill-color': '#60a5fa',
					'fill-opacity': 0.35
				},
				filter: ['==', ['get', 'redcode'], '']
			});
		}

		// Ensure the chat-highlight-line layer exists
		if (!map.getLayer('chat-highlight-line')) {
			map.addLayer({
				id: 'chat-highlight-line',
				type: 'line',
				source: 'radios',
				'source-layer': 'radios',
				paint: {
					'line-color': '#60a5fa',
					'line-width': 2.5,
					'line-opacity': 0.9
				},
				filter: ['==', ['get', 'redcode'], '']
			});
		}

		if (entries.length === 0) {
			map.setFilter('chat-highlight', ['==', ['get', 'redcode'], '']);
			map.setPaintProperty('chat-highlight', 'fill-color', '#60a5fa');
			map.setPaintProperty('chat-highlight', 'fill-opacity', 0.25);
			map.setFilter('chat-highlight-line', ['==', ['get', 'redcode'], '']);
			return;
		}

		// Compute min/max for interpolation
		const values = entries.map(e => e.value);
		const minVal = Math.min(...values);
		const maxVal = Math.max(...values);
		const range = maxVal - minVal || 1;

		// Build a match expression: map each redcode to a color
		// Scale: blue (#2166ac) → white (#f7f7f7) → red (#b2182b)
		const matchExpr: any[] = ['match', ['get', 'redcode']];
		for (const entry of entries) {
			const t = (entry.value - minVal) / range; // 0..1
			matchExpr.push(entry.redcode);
			// Interpolate blue → red through white
			const r = Math.round(t < 0.5 ? 33 + t * 2 * (247 - 33) : 247 + (t - 0.5) * 2 * (178 - 247));
			const g = Math.round(t < 0.5 ? 102 + t * 2 * (247 - 102) : 247 + (t - 0.5) * 2 * (24 - 247));
			const b = Math.round(t < 0.5 ? 172 + t * 2 * (247 - 172) : 247 + (t - 0.5) * 2 * (43 - 247));
			matchExpr.push(`rgb(${r},${g},${b})`);
		}
		matchExpr.push('rgba(0,0,0,0)'); // fallback: transparent

		const redcodes = entries.map(e => e.redcode);
		map.setFilter('chat-highlight', ['in', ['get', 'redcode'], ['literal', redcodes]]);
		map.setPaintProperty('chat-highlight', 'fill-color', matchExpr);
		map.setPaintProperty('chat-highlight', 'fill-opacity', 0.35);
		map.setFilter('chat-highlight-line', ['in', ['get', 'redcode'], ['literal', redcodes]]);
		map.setPaintProperty('chat-highlight-line', 'line-color', '#1e293b');
	}

	export function clearChatHighlights() {
		if (!map || !map.isStyleLoaded()) return;
		if (map.getLayer('chat-highlight')) {
			map.setFilter('chat-highlight', ['==', ['get', 'redcode'], '']);
			map.setPaintProperty('chat-highlight', 'fill-color', '#60a5fa');
			map.setPaintProperty('chat-highlight', 'fill-opacity', 0.25);
		}
		if (map.getLayer('chat-highlight-line')) {
			map.setFilter('chat-highlight-line', ['==', ['get', 'redcode'], '']);
			map.setPaintProperty('chat-highlight-line', 'line-color', '#60a5fa');
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
		map?.flyTo({ ...MAP_INIT, duration: 1200 });
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
			map.addSource('catastro', { type: 'vector', url: getTilesUrl('catastro') });
		}

		// Fill layer — visible cyan/green parcels (minzoom 8 for wider view)
		if (!map.getLayer('catastro-fill')) {
			map.addLayer({
				id: 'catastro-fill',
				type: 'fill',
				source: 'catastro',
				'source-layer': 'catastro',
				minzoom: 8,
				paint: {
					'fill-color': [
						'match', ['get', 'tipo'],
						'urbano', '#22d3ee',
						'rural', '#4ade80',
						'#22d3ee'
					],
					'fill-opacity': ['interpolate', ['linear'], ['zoom'], 8, 0.08, 10, 0.15, 12, 0.20, 14, 0.25]
				}
			});
		}

		// Line layer — thin crisp borders
		if (!map.getLayer('catastro-line')) {
			map.addLayer({
				id: 'catastro-line',
				type: 'line',
				source: 'catastro',
				'source-layer': 'catastro',
				minzoom: 8,
				paint: {
					'line-color': [
						'match', ['get', 'tipo'],
						'urbano', '#22d3ee',
						'rural', '#4ade80',
						'#22d3ee'
					],
					'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.1, 10, 0.3, 12, 0.6, 14, 0.9],
					'line-opacity': ['interpolate', ['linear'], ['zoom'], 8, 0.3, 10, 0.5, 12, 0.7, 14, 0.85]
				}
			});
		}

		// Buildings at max transparency — clicks still work through buildings-3d handler
		if (map.getLayer('buildings-3d')) {
			map.setPaintProperty('buildings-3d', 'fill-extrusion-opacity', 0.08);
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
		if (map.getLayer('catastro-fill')) map.removeLayer('catastro-fill');
		if (map.getLayer('catastro-line')) map.removeLayer('catastro-line');
		if (map.getLayer('buildings-3d')) {
			map.setPaintProperty('buildings-3d', 'fill-extrusion-opacity', 0.85);
		}
		for (const layerId of CARTO_BUILDING_LAYERS) {
			if (map.getLayer(layerId)) {
				map.setLayoutProperty(layerId, 'visibility', 'visible');
			}
		}
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
		const minVal = Math.min(...values);
		const maxVal = Math.max(...values);
		const range = maxVal - minVal || 1;

		const matchExpr: any[] = ['match', ['to-string', ['get', 'redcode']]];
		for (const entry of entries) {
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
				r = Math.round(t < 0.5 ? 33 + t * 2 * (247 - 33) : 247 + (t - 0.5) * 2 * (178 - 247));
				g = Math.round(t < 0.5 ? 102 + t * 2 * (247 - 102) : 247 + (t - 0.5) * 2 * (24 - 247));
				b = Math.round(t < 0.5 ? 172 + t * 2 * (247 - 172) : 247 + (t - 0.5) * 2 * (43 - 247));
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
		// Restore buildings
		if (map.getLayer('buildings-3d')) {
			map.setLayoutProperty('buildings-3d', 'visibility', 'visible');
			map.setPaintProperty('buildings-3d', 'fill-extrusion-color', mapStore.getColorExpr() as any);
			map.setPaintProperty('buildings-3d', 'fill-extrusion-opacity', 0.85);
		}
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

	export function setHexChoropleth(entries: { h3index: string; value: number; properties?: Record<string, number>; boundary?: number[][] }[], colorScale: 'flood' | 'sequential' = 'flood') {
		if (!map || !map.isStyleLoaded()) return;

		const src = map.getSource('hexagons') as maplibregl.GeoJSONSource | undefined;
		if (!src) return;

		if (entries.length === 0) {
			src.setData({ type: 'FeatureCollection', features: [] });
			map.setPaintProperty('hex-fill', 'fill-opacity', 0);
			map.setPaintProperty('hex-line', 'line-opacity', 0);
			return;
		}

		const values = entries.map(e => e.value);
		const minVal = Math.min(...values);
		const maxVal = Math.max(...values);
		const range = maxVal - minVal || 1;

		function getColor(value: number): string {
			const t = (value - minVal) / range;
			let r: number, g: number, b: number;
			if (colorScale === 'flood') {
				r = Math.round(t < 0.5 ? 59 + t * 2 * (234 - 59) : 234 + (t - 0.5) * 2 * (220 - 234));
				g = Math.round(t < 0.5 ? 130 + t * 2 * (179 - 130) : 179 + (t - 0.5) * 2 * (38 - 179));
				b = Math.round(t < 0.5 ? 246 + t * 2 * (8 - 246) : 8 + (t - 0.5) * 2 * (38 - 8));
			} else {
				r = Math.round(t < 0.5 ? 33 + t * 2 * (247 - 33) : 247 + (t - 0.5) * 2 * (178 - 247));
				g = Math.round(t < 0.5 ? 102 + t * 2 * (247 - 102) : 247 + (t - 0.5) * 2 * (24 - 247));
				b = Math.round(t < 0.5 ? 172 + t * 2 * (247 - 172) : 247 + (t - 0.5) * 2 * (43 - 247));
			}
			return `rgb(${r},${g},${b})`;
		}

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
		map.setPaintProperty('hex-fill', 'fill-opacity', 0.35);
		map.setPaintProperty('hex-line', 'line-color', '#0f172a');
		map.setPaintProperty('hex-line', 'line-width', 0.5);
		map.setPaintProperty('hex-line', 'line-opacity', 0.4);
	}

	export function clearHexChoropleth() {
		if (!map || !map.isStyleLoaded()) return;
		const src = map.getSource('hexagons') as maplibregl.GeoJSONSource | undefined;
		if (src) src.setData({ type: 'FeatureCollection', features: [] });
		if (map.getLayer('hex-fill')) map.setPaintProperty('hex-fill', 'fill-opacity', 0);
		if (map.getLayer('hex-line')) map.setPaintProperty('hex-line', 'line-opacity', 0);
		if (map.getLayer('hex-selected')) map.setFilter('hex-selected', ['==', ['get', 'h3index'], '']);
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
