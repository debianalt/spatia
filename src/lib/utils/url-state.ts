import type { Locale } from '$lib/stores/i18n.svelte';
import type { LensId } from '$lib/config';
import { TERRITORY_REGISTRY } from '$lib/config';

export interface UrlState {
	territory?: string;
	lens?: LensId;
	analysis?: string;
	dept?: string;
	zoom?: number;
	lng?: number;
	lat?: number;
	bearing?: number;
	pitch?: number;
	lang?: Locale;
	zones?: string;
}

const LOCALES: readonly Locale[] = ['es', 'en', 'gn'];

function parseNumber(raw: string | null): number | undefined {
	if (raw == null) return undefined;
	const n = Number(raw);
	return Number.isFinite(n) ? n : undefined;
}

export function readUrlState(): UrlState {
	if (typeof window === 'undefined') return {};
	const params = new URLSearchParams(window.location.search);

	const state: UrlState = {};
	const territory = params.get('t');
	if (territory && TERRITORY_REGISTRY[territory]) state.territory = territory;

	const lens = params.get('lens');
	if (lens) state.lens = lens as LensId;

	const analysis = params.get('a');
	if (analysis) state.analysis = analysis;

	const dept = params.get('dept');
	if (dept) state.dept = dept;

	state.zoom = parseNumber(params.get('z'));
	state.lng = parseNumber(params.get('lng'));
	state.lat = parseNumber(params.get('lat'));
	state.bearing = parseNumber(params.get('b'));
	state.pitch = parseNumber(params.get('p'));

	const lang = params.get('lang');
	if (lang && (LOCALES as readonly string[]).includes(lang)) {
		state.lang = lang as Locale;
	}

	const zones = params.get('zones');
	if (zones) state.zones = zones;

	return state;
}

function serialize(state: UrlState): string {
	const params = new URLSearchParams();
	if (state.territory && state.territory !== 'misiones') params.set('t', state.territory);
	if (state.lens) params.set('lens', state.lens);
	if (state.analysis) params.set('a', state.analysis);
	if (state.dept) params.set('dept', state.dept);
	if (state.lang) params.set('lang', state.lang);
	if (state.zoom != null) params.set('z', state.zoom.toFixed(2));
	if (state.lng != null) params.set('lng', state.lng.toFixed(5));
	if (state.lat != null) params.set('lat', state.lat.toFixed(5));
	if (state.bearing != null) params.set('b', state.bearing.toFixed(1));
	if (state.pitch != null) params.set('p', state.pitch.toFixed(1));
	if (state.zones) params.set('zones', state.zones);
	return params.toString();
}

let pendingState: UrlState = {};
let writeTimer: ReturnType<typeof setTimeout> | null = null;
const WRITE_DEBOUNCE_MS = 150;

function flushWrite() {
	writeTimer = null;
	if (typeof window === 'undefined') return;
	const qs = serialize(pendingState);
	const target = qs ? `?${qs}` : window.location.pathname;
	const current = window.location.search
		? window.location.search.startsWith('?')
			? window.location.search.substring(1)
			: window.location.search
		: '';
	if (current === qs) return;
	window.history.replaceState({}, '', target);
}

export function writeUrlState(state: UrlState): void {
	pendingState = { ...state };
	if (typeof window === 'undefined') return;
	if (writeTimer) clearTimeout(writeTimer);
	writeTimer = setTimeout(flushWrite, WRITE_DEBOUNCE_MS);
}

export function flushUrlState(): void {
	if (writeTimer) {
		clearTimeout(writeTimer);
		flushWrite();
	}
}

// Zone encoding — compact base64url of polygon lists for URL sharing.
// Each zone: [[lng,lat], [lng,lat], ...] rounded to 5 decimals.
// Format: base64url(JSON.stringify([[polygon1], [polygon2], ...])).
export function encodeZones(polygons: Array<Array<[number, number]>>): string {
	if (polygons.length === 0) return '';
	const rounded = polygons.map((poly) =>
		poly.map(([lng, lat]) => [Number(lng.toFixed(5)), Number(lat.toFixed(5))])
	);
	const json = JSON.stringify(rounded);
	const base64 =
		typeof btoa !== 'undefined' ? btoa(json) : Buffer.from(json, 'utf8').toString('base64');
	return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function decodeZones(encoded: string): Array<Array<[number, number]>> {
	if (!encoded) return [];
	try {
		const base64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
		const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
		const json =
			typeof atob !== 'undefined'
				? atob(padded)
				: Buffer.from(padded, 'base64').toString('utf8');
		const parsed = JSON.parse(json);
		if (!Array.isArray(parsed)) return [];
		return parsed
			.filter((p: unknown) => Array.isArray(p))
			.map((poly: unknown) => {
				const arr = poly as Array<[number, number]>;
				return arr.filter((pt) => Array.isArray(pt) && pt.length === 2);
			})
			.filter((poly) => poly.length >= 3);
	} catch {
		return [];
	}
}
