import { query, isReady } from '$lib/stores/duckdb';
import { PARQUETS } from '$lib/config';
import { i18n } from '$lib/stores/i18n.svelte';
import { pointInPolygon } from '$lib/utils/geometry';
import centroids from '$lib/data/centroids.json';

const centroidMap = centroids as unknown as Record<string, [number, number]>;

const ZONE_COLORS = ['#60a5fa', '#f97316', '#22c55e', '#a855f7', '#ef4444', '#eab308'];
const ZONE_LABELS = ['A', 'B', 'C', 'D', 'E', 'F'];

export const PETAL_VARS = [
	{ col: 'tasa_actividad', labelKey: 'label.activityRate' },
	{ col: 'tasa_empleo', labelKey: 'label.employmentRate' },
	{ col: 'pct_universitario', labelKey: 'label.university' },
	{ col: 'pct_nbi', labelKey: 'label.ubn' },
	{ col: 'pct_hacinamiento', labelKey: 'label.overcrowding' },
	{ col: 'pct_agua_red', labelKey: 'label.waterNetwork' },
];

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

	// Provincial weighted averages (computed once)
	private provincialAvg: number[] | null = null;

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

	private async ensureProvincialAvg(): Promise<number[]> {
		if (this.provincialAvg) return this.provincialAvg;

		const cols = PETAL_VARS.map(v =>
			`SUM(${v.col} * total_personas) / NULLIF(SUM(total_personas), 0) as avg_${v.col}`
		).join(', ');

		const sql = `SELECT ${cols} FROM '${PARQUETS.radio_stats_master}' WHERE total_personas > 0`;
		const result = await query(sql);
		const row = result.get(0)!.toJSON() as Record<string, any>;

		this.provincialAvg = PETAL_VARS.map(v => Number(row[`avg_${v.col}`]) || 1);
		return this.provincialAvg;
	}

	private normalize(rawValues: number[], provAvg: number[]): number[] {
		// (zone / provincial) * 50, clamped 0-100
		// 50 = equal to provincial average
		// 100 = double the provincial average
		// 0 = zero
		return rawValues.map((v, i) => {
			const avg = provAvg[i];
			if (avg === 0) return 50;
			return Math.min(100, Math.max(0, (v / avg) * 50));
		});
	}

	async createZone(redcodes: string[], polygon: [number, number][]): Promise<void> {
		if (redcodes.length === 0) return;
		if (!isReady()) return;

		const idx = this.zones.length % ZONE_COLORS.length;
		const id = ZONE_LABELS[idx] || String.fromCharCode(65 + this.zones.length);
		const color = ZONE_COLORS[idx];

		const cols = PETAL_VARS.map(v => v.col).join(', ');
		const inClause = redcodes.map(r => `'${r}'`).join(',');

		try {
			// Fetch provincial averages (cached after first call)
			const provAvg = await this.ensureProvincialAvg();

			const sql = `SELECT redcode, total_personas, ${cols}, area_km2 FROM '${PARQUETS.radio_stats_master}' WHERE redcode IN (${inClause})`;
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

			const normalizedValues = this.normalize(rawValues, provAvg);

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
