<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { Protocol } from 'pmtiles';
	import { getTilesUrl, BASEMAP, MAP_INIT } from '$lib/config';
	import { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

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
			antialias: true
		});

		map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right');

		map.on('error', (e) => console.error('MAP ERROR:', e.error?.message || e));

		map.on('load', () => {
			// Radios source (PMTiles) — province boundary context
			map.addSource('radios', { type: 'vector', url: getTilesUrl('radios') });

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
						6, 0.7,
						10, 0.4,
						14, 0.2
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

			// Radio highlight layer
			map.addLayer({
				id: 'radio-highlight',
				type: 'line',
				source: 'buildings',
				'source-layer': 'buildings',
				paint: { 'line-color': '#60a5fa', 'line-width': 1.5, 'line-opacity': 0.8 },
				filter: ['==', ['get', 'redcode'], '']
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

	export function setRadioHighlight(redcodes: string[]) {
		if (!map?.getLayer('radio-highlight')) return;
		if (redcodes.length === 0) {
			map.setFilter('radio-highlight', ['==', ['get', 'redcode'], '']);
		} else {
			map.setFilter('radio-highlight', ['in', ['get', 'redcode'], ['literal', redcodes]]);
		}
	}

	export function clearRadioHighlight() {
		map?.setFilter('radio-highlight', ['==', ['get', 'redcode'], '']);
	}
</script>

<div bind:this={container} style="width:100%;height:100%;"></div>
