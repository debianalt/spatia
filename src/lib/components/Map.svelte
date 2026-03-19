<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { Protocol } from 'pmtiles';
	import { getTilesUrl, BASEMAP, MAP_INIT } from '$lib/config';
	import { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import misionesBoundary from '$lib/data/misiones_boundary.geojson';
	import misionesMask from '$lib/data/misiones_mask.geojson';

	let { mapStore }: { mapStore: MapStore } = $props();

	let container: HTMLDivElement;
	let map: maplibregl.Map;

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
			// Radios source (PMTiles) — province boundary context
			map.addSource('radios', { type: 'vector', url: getTilesUrl('radios') });

			// Mask: darken everything outside Misiones
			map.addSource('mask', { type: 'geojson', data: misionesMask as any });
			map.addLayer({
				id: 'mask-fill',
				type: 'fill',
				source: 'mask',
				paint: { 'fill-color': '#0a0a0f', 'fill-opacity': 0.6 }
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
					'line-color': '#94a3b8',
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

			// Province border: bright white outline
			map.addSource('province-boundary', { type: 'geojson', data: misionesBoundary as any });
			map.addLayer({
				id: 'province-border',
				type: 'line',
				source: 'province-boundary',
				paint: {
					'line-color': '#ffffff',
					'line-width': [
						'interpolate', ['linear'], ['zoom'],
						6, 2.5,
						9, 2.0,
						12, 1.5,
						16, 1.0
					],
					'line-opacity': [
						'interpolate', ['linear'], ['zoom'],
						6, 0.9,
						12, 0.7,
						16, 0.5
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

			// Lighting
			map.setLight({
				anchor: 'viewport',
				color: '#ffffff',
				intensity: 0.3,
				position: [1.5, 200, 30]
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
				paint: { 'line-color': '#60a5fa', 'line-width': 1.5, 'line-opacity': 0.8 },
				filter: emptyFilter
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
				html += `<br><span style="color:#475569">\u2500\u2500\u2500</span><br>` +
					`<b style="color:#94a3b8">${i18n.t('tip.radio')}</b> <span style="color:#94a3b8">${redcode}</span><br>` +
					`<b style="color:#94a3b8">${i18n.t('tip.pop')}</b> ${radioPop.toLocaleString()} &nbsp; <b style="color:#94a3b8">${i18n.t('tip.density')}</b> ${radioDens} hab/km\u00B2<br>` +
					`<b style="color:#94a3b8">${i18n.t('label.dwellings')}:</b> ${radioViv.toLocaleString()} &nbsp; <b style="color:#94a3b8">${i18n.t('label.households')}:</b> ${radioHog.toLocaleString()} &nbsp; <b style="color:#94a3b8">${i18n.t('label.area')}:</b> ${radioAreaKm2} km\u00B2`;
			}

			tooltip.innerHTML = html;
			tooltip.style.display = 'block';
			tooltip.style.left = (e.originalEvent.clientX + 14) + 'px';
			tooltip.style.top = (e.originalEvent.clientY + 14) + 'px';
		});

		map.on('mouseleave', 'buildings-3d', () => {
			leaveTimeout = setTimeout(() => {
				map.getCanvas().style.cursor = '';
				tooltip.style.display = 'none';
			}, 80);
		});

		// Click-to-select/deselect radio (multi-select)
		map.on('click', 'buildings-3d', (e) => {
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
			pitch: 45,
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
		map.setPaintProperty('radio-highlight', 'line-width', 2.5);
		map.setFilter('radio-highlight', matchFilter);
	}

	export function highlightComparisonPair(redcodeA: string, colorA: string, redcodeB: string, colorB: string) {
		setRadioHighlight([
			{ redcode: redcodeA, color: colorA },
			{ redcode: redcodeB, color: colorB }
		]);
		// Use thicker line for comparison visibility
		if (map?.getLayer('radio-highlight')) {
			map.setPaintProperty('radio-highlight', 'line-width', 2.5);
		}
	}
</script>

<div bind:this={container} style="width:100%;height:100%;"></div>
