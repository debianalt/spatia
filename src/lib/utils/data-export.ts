import type { Table } from 'apache-arrow';
import { cellToBoundary } from 'h3-js';
import { initDuckDB, query } from '$lib/stores/duckdb';

function escapeCsvValue(val: unknown): string {
	if (val == null) return '';
	if (typeof val === 'bigint') return val.toString();
	const str = String(val);
	if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
		return `"${str.replace(/"/g, '""')}"`;
	}
	return str;
}

function sanitizeFilename(name: string): string {
	return name.replace(/[^a-zA-Z0-9_.-]/g, '_');
}

function toJsonSafe(val: unknown): unknown {
	if (val == null) return null;
	if (typeof val === 'bigint') return Number(val);
	return val;
}

function triggerDownload(blob: Blob, filename: string): void {
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = sanitizeFilename(filename);
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
	URL.revokeObjectURL(url);
}

export function tableToCsv(table: Table): string {
	const cols = table.schema.fields.map((f) => f.name);
	const lines: string[] = [cols.join(',')];
	for (let i = 0; i < table.numRows; i++) {
		const row = table.get(i)!.toJSON() as Record<string, unknown>;
		lines.push(cols.map((c) => escapeCsvValue(row[c])).join(','));
	}
	return lines.join('\n') + '\n';
}

export async function downloadCsvFromQuery(sql: string, filename: string): Promise<void> {
	await initDuckDB();
	const table = await query(sql);
	const csv = tableToCsv(table);
	const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
	triggerDownload(blob, filename);
}

export function downloadCsvFromRows(
	rows: Array<Record<string, unknown>>,
	columns: string[],
	filename: string
): void {
	const lines: string[] = [columns.join(',')];
	for (const row of rows) {
		lines.push(columns.map((c) => escapeCsvValue(row[c])).join(','));
	}
	const csv = lines.join('\n') + '\n';
	const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
	triggerDownload(blob, filename);
}

export async function downloadGeoJsonFromHexQuery(
	sql: string,
	filename: string,
	h3Column = 'h3index'
): Promise<void> {
	await initDuckDB();
	const table = await query(sql);
	const cols = table.schema.fields.map((f) => f.name);
	const features: Array<Record<string, unknown>> = [];

	for (let i = 0; i < table.numRows; i++) {
		const row = table.get(i)!.toJSON() as Record<string, unknown>;
		const h3 = row[h3Column];
		if (!h3) continue;

		// h3-js v4: formatAsGeoJson=true returns [lng, lat] pairs, ready for GeoJSON
		const boundary = cellToBoundary(String(h3), true) as Array<[number, number]>;
		if (boundary.length < 3) continue;
		const ring: Array<[number, number]> = [...boundary, boundary[0]];

		const properties: Record<string, unknown> = {};
		for (const c of cols) {
			properties[c] = toJsonSafe(row[c]);
		}

		features.push({
			type: 'Feature',
			geometry: { type: 'Polygon', coordinates: [ring] },
			properties,
		});
	}

	const geojson = { type: 'FeatureCollection', features };
	const blob = new Blob([JSON.stringify(geojson)], { type: 'application/geo+json' });
	triggerDownload(blob, filename);
}

export function downloadGeoJsonFromHexList(
	h3indices: string[],
	dataByHex: Map<string, Record<string, unknown>>,
	filename: string
): void {
	const features: Array<Record<string, unknown>> = [];
	for (const h3 of h3indices) {
		const boundary = cellToBoundary(h3, true) as Array<[number, number]>;
		if (boundary.length < 3) continue;
		const ring: Array<[number, number]> = [...boundary, boundary[0]];
		const row = dataByHex.get(h3) ?? {};
		const properties: Record<string, unknown> = { h3index: h3 };
		for (const [k, v] of Object.entries(row)) {
			properties[k] = toJsonSafe(v);
		}
		features.push({
			type: 'Feature',
			geometry: { type: 'Polygon', coordinates: [ring] },
			properties,
		});
	}
	const geojson = { type: 'FeatureCollection', features };
	const blob = new Blob([JSON.stringify(geojson)], { type: 'application/geo+json' });
	triggerDownload(blob, filename);
}

// ── SVG / PNG export for charts ─────────────────────────────────────────────

function inlineSvgStyles(svg: SVGElement): void {
	// CSS classes don't apply once the SVG leaves the DOM context.
	// Copy computed styles to inline attributes so the file renders identically
	// in Illustrator/Inkscape (SVG) and on a fresh canvas (PNG).
	const props = ['fill', 'stroke', 'stroke-width', 'stroke-opacity', 'stroke-dasharray',
		'opacity', 'fill-opacity', 'font-family', 'font-size', 'font-weight', 'text-anchor'];
	const walk = (node: Element) => {
		const cs = window.getComputedStyle(node);
		for (const p of props) {
			const v = cs.getPropertyValue(p);
			if (v) (node as SVGElement).style.setProperty(p, v);
		}
		for (const child of Array.from(node.children)) walk(child);
	};
	walk(svg);
	svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
}

export function exportSvgAsSvg(svg: SVGElement, filename: string): void {
	const cloned = svg.cloneNode(true) as SVGElement;
	inlineSvgStyles(cloned);
	const xml = new XMLSerializer().serializeToString(cloned);
	const blob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' });
	triggerDownload(blob, filename);
}

export async function exportSvgAsPng(
	svg: SVGElement,
	filename: string,
	opts: { scale?: number; background?: string } = {}
): Promise<void> {
	const scale = opts.scale ?? 2;
	const background = opts.background ?? '#0a0e1a';
	const rect = svg.getBoundingClientRect();
	const width = rect.width || Number(svg.getAttribute('width')) || 600;
	const height = rect.height || Number(svg.getAttribute('height')) || 400;

	const cloned = svg.cloneNode(true) as SVGElement;
	inlineSvgStyles(cloned);
	// Ensure width/height attrs so Image() rasterises correctly
	cloned.setAttribute('width', String(width));
	cloned.setAttribute('height', String(height));
	const xml = new XMLSerializer().serializeToString(cloned);
	const blob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' });
	const url = URL.createObjectURL(blob);

	try {
		const img = new Image();
		await new Promise<void>((resolve, reject) => {
			img.onload = () => resolve();
			img.onerror = (e) => reject(e);
			img.src = url;
		});
		const canvas = document.createElement('canvas');
		canvas.width = width * scale;
		canvas.height = height * scale;
		const ctx = canvas.getContext('2d');
		if (!ctx) return;
		ctx.fillStyle = background;
		ctx.fillRect(0, 0, canvas.width, canvas.height);
		ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
		await new Promise<void>((resolve) => {
			canvas.toBlob((b) => {
				if (b) triggerDownload(b, filename);
				resolve();
			}, 'image/png');
		});
	} finally {
		URL.revokeObjectURL(url);
	}
}

export function downloadGeoJsonFromPolygon(
	coordinates: Array<[number, number]>,
	properties: Record<string, unknown>,
	filename: string
): void {
	if (coordinates.length < 3) return;
	const first = coordinates[0];
	const last = coordinates[coordinates.length - 1];
	const ring: Array<[number, number]> =
		first[0] === last[0] && first[1] === last[1] ? coordinates : [...coordinates, first];

	const geojson = {
		type: 'FeatureCollection',
		features: [
			{
				type: 'Feature',
				geometry: { type: 'Polygon', coordinates: [ring] },
				properties,
			},
		],
	};
	const blob = new Blob([JSON.stringify(geojson)], { type: 'application/geo+json' });
	triggerDownload(blob, filename);
}
