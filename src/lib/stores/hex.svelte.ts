import { query, isReady } from '$lib/stores/duckdb';
import { PARQUETS, HEX_LAYER_REGISTRY, type HexLayerConfig, type HexVariable } from '$lib/config';
import { pointInPolygon } from '$lib/utils/geometry';
import { i18n } from '$lib/stores/i18n.svelte';
import { cellToLatLng } from 'h3-js';

const ZONE_COLORS = ['#60a5fa', '#f97316', '#22c55e', '#a855f7', '#ef4444', '#eab308'];
const ZONE_LABELS = ['A', 'B', 'C', 'D', 'E', 'F'];

export interface HexSelectionData {
	color: string;
	data: Record<string, number>;
}

export interface HexZoneStats {
	hexCount: number;
	rawValues: number[];
	normalizedValues: number[];
}

export interface HexZone {
	id: string;
	color: string;
	h3indices: string[];
	polygon: [number, number][];
	stats: HexZoneStats;
}

export class HexStore {
	activeLayer: HexLayerConfig | null = $state(null);
	visibleData: Map<string, Record<string, number>> = $state(new Map());
	selectedHexes: Map<string, HexSelectionData> = $state(new Map());
	hexZones: HexZone[] = $state([]);
	loading: boolean = $state(false);

	private colorIndex = 0;
	private provincialAvg: number[] | null = $state(null);

	setLayer(layerId: string | null) {
		if (!layerId) {
			this.activeLayer = null;
			this.visibleData = new Map();
			this.clearSelection();
			this.clearHexZones();
			return;
		}
		const cfg = HEX_LAYER_REGISTRY[layerId];
		if (!cfg) return;
		this.activeLayer = cfg;
		this.provincialAvg = null;
		this.loadVisibleData();
	}

	async loadVisibleData() {
		const layer = this.activeLayer;
		if (!layer || !isReady()) return;

		this.loading = true;

		try {
			await this.loadBaseResolution(layer);
		} catch (e) {
			console.warn('Failed to load hex data:', e);
		}

		this.loading = false;
	}

	private async loadBaseResolution(layer: HexLayerConfig) {
		const url = PARQUETS[layer.parquet as keyof typeof PARQUETS];
		if (!url) return;

		const cols = layer.variables.map(v => v.col).join(', ');
		const result = await query(
			`SELECT h3index, ${cols} FROM '${url}' WHERE ${layer.primaryVariable} IS NOT NULL`
		);

		const data = new Map<string, Record<string, number>>();
		for (let i = 0; i < result.numRows; i++) {
			const row = result.get(i)!.toJSON() as Record<string, any>;
			const h3index = row.h3index as string;
			const values: Record<string, number> = {};
			for (const v of layer.variables) {
				values[v.col] = Number(row[v.col]) || 0;
			}
			data.set(h3index, values);
		}
		this.visibleData = data;
	}

	// ── Selection ────────────────────────────────────────────────────────

	selectHex(h3index: string) {
		if (this.selectedHexes.has(h3index)) return;
		const color = ZONE_COLORS[this.colorIndex % ZONE_COLORS.length];
		this.colorIndex++;
		const data = this.visibleData.get(h3index) ?? {};
		const updated = new Map(this.selectedHexes);
		updated.set(h3index, { color, data });
		this.selectedHexes = updated;
	}

	deselectHex(h3index: string) {
		if (!this.selectedHexes.has(h3index)) return;
		const updated = new Map(this.selectedHexes);
		updated.delete(h3index);
		this.selectedHexes = updated;
		if (updated.size === 0) this.colorIndex = 0;
	}

	toggleHex(h3index: string) {
		if (this.selectedHexes.has(h3index)) {
			this.deselectHex(h3index);
		} else {
			this.selectHex(h3index);
		}
	}

	hasHex(h3index: string): boolean {
		return this.selectedHexes.has(h3index);
	}

	clearSelection() {
		this.selectedHexes = new Map();
		this.colorIndex = 0;
	}

	// ── Choropleth entries ────────────────────────────────────────────────

	get choroplethEntries(): { h3index: string; value: number; properties: Record<string, number> }[] {
		if (!this.activeLayer) return [];
		const primary = this.activeLayer.primaryVariable;
		const entries: { h3index: string; value: number; properties: Record<string, number> }[] = [];
		for (const [h3index, data] of this.visibleData) {
			const value = data[primary] ?? 0;
			if (value > 0) {
				entries.push({ h3index, value, properties: data });
			}
		}
		return entries;
	}

	// ── Hex zone (lasso) operations ──────────────────────────────────────

	findHexesInPolygon(polygon: [number, number][]): string[] {
		const result: string[] = [];
		for (const [h3index] of this.visibleData) {
			try {
				const [lat, lng] = cellToLatLng(h3index);
				if (pointInPolygon([lng, lat], polygon)) {
					result.push(h3index);
				}
			} catch { /* skip invalid */ }
		}
		return result;
	}

	private async ensureProvincialAvg(): Promise<number[]> {
		if (this.provincialAvg) return this.provincialAvg;
		if (!this.activeLayer) return [];

		const layer = this.activeLayer;
		const dataUrl = PARQUETS[layer.parquet as keyof typeof PARQUETS];
		if (!dataUrl) return [];

		const aggExprs = layer.variables.map(v => `AVG(${v.col}) as avg_${v.col}`).join(', ');
		const sql = `SELECT ${aggExprs} FROM '${dataUrl}' WHERE ${layer.primaryVariable} IS NOT NULL`;
		const result = await query(sql);
		const row = result.get(0)!.toJSON() as Record<string, any>;

		this.provincialAvg = layer.variables.map(v => Number(row[`avg_${v.col}`]) || 1);
		return this.provincialAvg;
	}

	private normalize(rawValues: number[], provAvg: number[]): number[] {
		return rawValues.map((v, i) => {
			const avg = provAvg[i];
			if (avg === 0) return 50;
			return Math.min(100, Math.max(0, (v / avg) * 50));
		});
	}

	async createHexZone(h3indices: string[], polygon: [number, number][]): Promise<void> {
		if (h3indices.length === 0 || !this.activeLayer) return;
		if (!isReady()) return;

		const layer = this.activeLayer;
		const idx = this.hexZones.length % ZONE_COLORS.length;
		const id = ZONE_LABELS[idx] || String.fromCharCode(65 + this.hexZones.length);
		const color = ZONE_COLORS[idx];

		try {
			const provAvg = await this.ensureProvincialAvg();

			// Compute averages from visibleData
			const rawValues = new Array(layer.variables.length).fill(0);
			let count = 0;
			for (const h3index of h3indices) {
				const data = this.visibleData.get(h3index);
				if (!data) continue;
				count++;
				for (let v = 0; v < layer.variables.length; v++) {
					rawValues[v] += data[layer.variables[v].col] || 0;
				}
			}
			if (count > 0) {
				for (let v = 0; v < rawValues.length; v++) {
					rawValues[v] /= count;
				}
			}

			const normalizedValues = this.normalize(rawValues, provAvg);

			const zone: HexZone = {
				id,
				color,
				h3indices,
				polygon,
				stats: {
					hexCount: h3indices.length,
					rawValues,
					normalizedValues,
				},
			};

			this.hexZones = [...this.hexZones, zone];
		} catch (e) {
			console.warn('Failed to create hex zone:', e);
		}
	}

	removeHexZone(id: string) {
		this.hexZones = this.hexZones.filter(z => z.id !== id);
	}

	clearHexZones() {
		this.hexZones = [];
	}

	// ── Petal chart data ─────────────────────────────────────────────────

	get petalLayers(): Array<{ values: number[]; color: string }> {
		return this.hexZones.map(z => ({
			values: z.stats.normalizedValues,
			color: z.color,
		}));
	}

	get petalLabels(): string[] {
		if (!this.activeLayer) return [];
		return this.activeLayer.variables.map(v => i18n.t(v.labelKey));
	}

	// ── Selection petal data (individual hex clicks) ─────────────────────

	get selectionPetalLayers(): Array<{ values: number[]; color: string }> {
		if (!this.activeLayer || this.selectedHexes.size === 0 || !this.provincialAvg) return [];
		const provAvg = this.provincialAvg;
		const vars = this.activeLayer.variables;
		const result: Array<{ values: number[]; color: string }> = [];
		for (const [, sel] of this.selectedHexes) {
			const rawValues = vars.map(v => sel.data[v.col] ?? 0);
			const normalizedValues = this.normalize(rawValues, provAvg);
			result.push({ values: normalizedValues, color: sel.color });
		}
		return result;
	}

	async ensureProvincialAvgLoaded(): Promise<void> {
		await this.ensureProvincialAvg();
	}

	// ── Full clear ───────────────────────────────────────────────────────

	clearAll() {
		this.activeLayer = null;
		this.visibleData = new Map();
		this.selectedHexes = new Map();
		this.hexZones = [];
		this.colorIndex = 0;
		this.provincialAvg = null;
	}
}
