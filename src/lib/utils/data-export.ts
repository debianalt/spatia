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
