import { query, isReady } from '$lib/stores/duckdb';
import { PARQUETS } from '$lib/config';
import { i18n } from '$lib/stores/i18n.svelte';
import { pointInPolygon } from '$lib/utils/geometry';
import { PETAL_VARS, normalizeValues, getProvincialAvg } from '$lib/utils/petal';
import centroids from '$lib/data/centroids.json';

export { PETAL_VARS };

const centroidMap = centroids as unknown as Record<string, [number, number]>;

const ZONE_COLORS = ['#60a5fa', '#f97316', '#22c55e', '#a855f7', '#ef4444', '#eab308'];
const ZONE_LABELS = ['A', 'B', 'C', 'D', 'E', 'F'];

export interface ZoneStats {
	population: number;
	area_km2: number;
	radioCount: number;
	rawValues: number[];        // 6 raw weighted averages
	normalizedValues: number[]; // 6 values 0-100, 50 = provincial avg
}

export interface Zone {
	id: string;
	color: string;
	redcodes: string[];
	polygon: [number, number][];
	stats: ZoneStats;
}

export class LassoStore {
	active = $state(false);
	drawing = $state(false);
	currentPolygon: [number, number][] = $state([]);
	zones: Zone[] = $state([]);

	toggle() {
		this.active = !this.active;
		if (!this.active) this.cancelDraw();
	}

	startDraw() {
		this.drawing = true;
		this.currentPolygon = [];
	}

	addPoint(lngLat: [number, number]) {
		this.currentPolygon = [...this.currentPolygon, lngLat];
	}

	finishDraw(): [number, number][] {
		this.drawing = false;
		const polygon = [...this.currentPolygon];
		if (polygon.length > 2) {
			polygon.push(polygon[0]); // close
		}
		this.currentPolygon = [];
		return polygon;
	}

	cancelDraw() {
		this.drawing = false;
		this.currentPolygon = [];
	}

	findRadiosInPolygon(polygon: [number, number][]): string[] {
		const result: string[] = [];
		for (const [redcode, centroid] of Object.entries(centroidMap)) {
			// centroids are [lat, lng], polygon points are [lng, lat] (from map)
			const point: [number, number] = [centroid[1], centroid[0]];
			if (pointInPolygon(point, polygon)) {
				result.push(redcode);
			}
		}
		return result;
	}

	async createZone(redcodes: string[], polygon: [number, number][]): Promise<void> {
		if (redcodes.length === 0) return;
		if (!isReady()) return;

		const idx = this.zones.length % ZONE_COLORS.length;
		const id = ZONE_LABELS[idx] || String.fromCharCode(65 + this.zones.length);
		const color = ZONE_COLORS[idx];

		const inClause = redcodes.map(r => `'${r}'`).join(',');
		const isCorrientes = redcodes[0]?.startsWith('18');

		// Corrientes lacks pct_agua_red — substitute 0 so petal var count stays consistent
		const cols = isCorrientes
			? PETAL_VARS.map(v => v.col === 'pct_agua_red' ? '0 as pct_agua_red' : v.col).join(', ')
			: PETAL_VARS.map(v => v.col).join(', ');
		const parquet = isCorrientes ? PARQUETS.radio_stats_corrientes : PARQUETS.radio_stats_master;

		try {
			// Fetch provincial averages (cached after first call)
			const provAvg = await getProvincialAvg();

			const sql = `SELECT redcode, total_personas, ${cols}, area_km2 FROM '${parquet}' WHERE redcode IN (${inClause})`;
			const result = await query(sql);

			let totalPop = 0;
			let totalArea = 0;
			const weighted = new Array(PETAL_VARS.length).fill(0);

			for (let i = 0; i < result.numRows; i++) {
				const row = result.get(i)!.toJSON() as Record<string, any>;
				const pop = Number(row.total_personas) || 0;
				const area = Number(row.area_km2) || 0;
				totalPop += pop;
				totalArea += area;
				for (let v = 0; v < PETAL_VARS.length; v++) {
					const val = Number(row[PETAL_VARS[v].col]) || 0;
					weighted[v] += val * pop;
				}
			}

			const rawValues = totalPop > 0
				? weighted.map(w => w / totalPop)
				: new Array(PETAL_VARS.length).fill(0);

			const normalizedValues = normalizeValues(rawValues, provAvg);

			const zone: Zone = {
				id,
				color,
				redcodes,
				polygon,
				stats: {
					population: totalPop,
					area_km2: totalArea,
					radioCount: redcodes.length,
					rawValues,
					normalizedValues,
				},
			};

			this.zones = [...this.zones, zone];
		} catch (e) {
			console.warn('Failed to create lasso zone:', e);
		}
	}

	removeZone(id: string) {
		this.zones = this.zones.filter(z => z.id !== id);
	}

	clearZones() {
		this.zones = [];
	}

	get petalLayers(): Array<{ values: number[]; color: string }> {
		return this.zones.map(z => ({
			values: z.stats.normalizedValues,
			color: z.color,
		}));
	}

	get petalLabels(): string[] {
		return PETAL_VARS.map(v => i18n.t(v.labelKey));
	}
}
