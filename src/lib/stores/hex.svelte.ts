import { query, isReady } from '$lib/stores/duckdb';
import { PARQUETS, HEX_LAYER_REGISTRY, getFloodDptoUrl, getScoresDptoUrl, getSatDptoUrl, getTemporalCol, type HexLayerConfig, type HexVariable, type TemporalMode } from '$lib/config';
import { pointInPolygon } from '$lib/utils/geometry';
import { i18n } from '$lib/stores/i18n.svelte';
import { cellToLatLng, cellToBoundary } from 'h3-js';

const ZONE_COLORS = ['#60a5fa', '#f97316', '#22c55e', '#a855f7', '#ef4444', '#eab308'];
const ZONE_LABELS = ['A', 'B', 'C', 'D', 'E', 'F'];

// Persistent cache that survives clearAll() / layer toggling
interface LayerCache {
	data: Map<string, Record<string, any>>;
	centroids: Map<string, [number, number]>;
	boundaries: Map<string, number[][]>;
	provincialAvg: number[] | null;
}
const layerDataCache = new Map<string, LayerCache>();

export interface HexSelectionData {
	color: string;
	data: Record<string, any>;
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

const NON_NUMERIC_COLS = new Set(['type', 'type_label', 'pca_1', 'pca_2', 'pca_3', 'score', 'flood_risk_score', 'risk_score', 'territorial_type']);

export class HexStore {
	activeLayer: HexLayerConfig | null = $state(null);
	visibleData: Map<string, Record<string, any>> = $state(new Map());
	selectedHexes: Map<string, HexSelectionData> = $state(new Map());
	hexZones: HexZone[] = $state([]);
	loading: boolean = $state(false);
	temporalMode: TemporalMode = $state('current');

	private colorIndex = 0;
	private provincialAvg: number[] | null = $state(null);
	colorDomain: [number, number] | null = $state(null);
	selectedDpto: string | null = $state(null);

	get numericVariables(): HexVariable[] {
		return this.activeLayer?.variables.filter(v => !NON_NUMERIC_COLS.has(v.col)) ?? [];
	}

	// Monotonic counter: increments on every meaningful visibleData change.
	// Used by $effect to detect changes regardless of data size.
	dataVersion: number = $state(0);

	// Pre-computed geometry caches (built once at load, reused everywhere)
	centroidCache: Map<string, [number, number]> = new Map(); // h3index → [lng, lat]
	boundaryCache: Map<string, number[][]> = new Map(); // h3index → [[lng, lat], ...]

	setTemporalMode(mode: TemporalMode) {
		this.temporalMode = mode;
		this.dataVersion++;
	}

	setLayer(layerId: string | null) {
		if (!layerId) {
			this.activeLayer = null;
			this.visibleData = new Map();
			this.centroidCache = new Map();
			this.boundaryCache = new Map();
			this.selectedDpto = null;
			this.temporalMode = 'current';
			this.dataVersion++;
			this.clearSelection();
			this.clearHexZones();
			return;
		}
		const cfg = HEX_LAYER_REGISTRY[layerId];
		if (!cfg) return;
		this.activeLayer = cfg;
		this.temporalMode = 'current';
		this.selectedDpto = null;

		// Per-department layers: don't load all data, wait for department selection.
		// Exception: non-default territories load the global parquet directly
		// (dept summaries may not exist, and territory is small enough to load all hexes at once).
		if (cfg.perDepartment && !this.territoryPrefix) {
			this.loading = false;
			return;
		}

		// Restore from persistent cache if available (instant re-activation)
		const cached = layerDataCache.get(layerId);
		if (cached) {
			this.visibleData = cached.data;
			this.centroidCache = cached.centroids;
			this.boundaryCache = cached.boundaries;
			this.provincialAvg = cached.provincialAvg;
			this.dataVersion++;
			this.loading = false;
			return;
		}

		this.provincialAvg = null;
		this.loadVisibleData();
	}

	territoryPrefix: string = $state('');

	setTerritoryPrefix(prefix: string) {
		if (this.territoryPrefix === prefix) return;
		this.territoryPrefix = prefix;
		layerDataCache.clear();
		this.colorDomain = null;
		// Clear hex data from previous territory so the old choropleth disappears immediately
		this.visibleData = new Map();
		this.selectedDpto = null;
		this.dataVersion++;
	}

	/** Territory-aware URL for the global parquet of a layer. */
	private layerGlobalUrl(layer: HexLayerConfig): string | undefined {
		const url = PARQUETS[layer.parquet as keyof typeof PARQUETS];
		if (!url) return undefined;
		return this.territoryPrefix ? url.replace('/data/', `/data/${this.territoryPrefix}`) : url;
	}

	async loadDepartment(dpto: string, parquetKey: string) {
		if (!this.activeLayer) return;
		const layer = this.activeLayer;

		this.loading = true;
		this.selectedDpto = dpto;
		this.visibleData = new Map();
		this.clearSelection();
		this.clearHexZones();
		this.dataVersion++;

		try {
			// Dispatch URL based on layer type
			let url: string;
			if (layer.id === 'flood_risk') {
				url = getFloodDptoUrl(parquetKey, this.territoryPrefix);
			} else if (layer.parquet?.startsWith('sat_')) {
				url = getSatDptoUrl(layer.id, parquetKey, this.territoryPrefix);
			} else {
				url = getScoresDptoUrl(parquetKey, this.territoryPrefix);
			}
			// Use SELECT * for robustness — temporal parquets may or may not have _baseline/_delta cols
			const result = await query(
				`SELECT * FROM '${url}'`
			);

			const data = new Map<string, Record<string, any>>();
			const centroids = new Map<string, [number, number]>();
			const boundaries = new Map<string, number[][]>();

			const resultCols = result.schema.fields
				.map((f: any) => f.name)
				.filter((name: string) => name !== 'h3index');
			const h3indexVec = result.getChild('h3index');
			const colVecs = Object.fromEntries(
				resultCols.map((col: string) => [col, result.getChild(col)])
			);

			for (let i = 0; i < result.numRows; i++) {
				const h3index = String(h3indexVec!.get(i));
				const values: Record<string, any> = {};
				for (const col of resultCols) {
					const val = colVecs[col]?.get(i);
					if (val === null || val === undefined) continue;
					const num = Number(val);
					values[col] = Number.isFinite(num) && typeof val !== 'string' ? num : String(val);
				}
				data.set(h3index, values);

				try {
					const [lat, lng] = cellToLatLng(h3index);
					centroids.set(h3index, [lng, lat]);
					const boundary = cellToBoundary(h3index);
					const coords = boundary.map(([lat, lng]) => [lng, lat]);
					coords.push(coords[0]);
					boundaries.set(h3index, coords);
				} catch { /* skip invalid h3 */ }
			}

			this.visibleData = data;
			this.centroidCache = centroids;
			this.boundaryCache = boundaries;
			this.dataVersion++;

			this.ensureProvincialAvg().catch(() => {});
		} catch (e) {
			console.warn('Failed to load department hex data:', e);
		}

		this.loading = false;
	}

	backToDepartments() {
		this.selectedDpto = null;
		this.clearSelection();
		this.clearHexZones();
	}

	async loadVisibleData() {
		const layer = this.activeLayer;
		if (!layer || !isReady()) return;
		// For non-default territories, always load global parquet even for perDepartment layers
		if (layer.perDepartment && !this.territoryPrefix) return;

		this.loading = true;

		try {
			await this.loadBaseResolution(layer);
			// Fire-and-forget: pre-cache provincial averages so lasso zones are instant
			this.ensureProvincialAvg().catch(() => {});
		} catch (e) {
			console.warn('Failed to load hex data:', e);
		}

		this.loading = false;
	}

	private async loadBaseResolution(layer: HexLayerConfig) {
		const url = this.layerGlobalUrl(layer);
		if (!url) return;

		const baseCols = layer.variables.map(v => v.col);
		const allCols = new Set(baseCols);
		if (layer.temporal) {
			for (const col of baseCols) {
				allCols.add(getTemporalCol(col, 'baseline'));
				allCols.add(getTemporalCol(col, 'delta'));
			}
		}
		const cols = [...allCols].join(', ');
		const result = await query(
			`SELECT h3index, ${cols} FROM '${url}'`
		);

		const data = new Map<string, Record<string, any>>();
		const centroids = new Map<string, [number, number]>();
		const boundaries = new Map<string, number[][]>();

		const h3Vec = result.getChild('h3index');
		const allColVecs = Object.fromEntries(
			[...allCols].map((col: string) => [col, result.getChild(col)])
		);

		for (let i = 0; i < result.numRows; i++) {
			const h3index = String(h3Vec!.get(i));
			const values: Record<string, any> = {};
			for (const col of allCols) {
				const val = allColVecs[col]?.get(i);
				if (val === null || val === undefined) continue;
				const num = Number(val);
				values[col] = Number.isFinite(num) && typeof val !== 'string' ? num : String(val);
			}
			data.set(h3index, values);

			// Pre-compute geometry once for all subsequent operations
			try {
				const [lat, lng] = cellToLatLng(h3index);
				centroids.set(h3index, [lng, lat]);
				const boundary = cellToBoundary(h3index);
				const coords = boundary.map(([lat, lng]) => [lng, lat]);
				coords.push(coords[0]); // close ring
				boundaries.set(h3index, coords);
			} catch { /* skip invalid h3 */ }
		}

		this.visibleData = data;
		this.centroidCache = centroids;
		this.boundaryCache = boundaries;
		this.dataVersion++;

		// Persist in module-level cache for instant re-activation
		layerDataCache.set(layer.id, { data, centroids, boundaries, provincialAvg: null });
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

	get choroplethEntries(): { h3index: string; value: number; properties: Record<string, number>; boundary?: number[][] }[] {
		if (!this.activeLayer) return [];
		const effectivePrimary = this.activeLayer.temporal && this.temporalMode !== 'current'
			? getTemporalCol(this.activeLayer.primaryVariable, this.temporalMode)
			: this.activeLayer.primaryVariable;
		const isDelta = this.activeLayer.temporal && this.temporalMode === 'delta';
		const entries: { h3index: string; value: number; properties: Record<string, number>; boundary?: number[][] }[] = [];
		for (const [h3index, data] of this.visibleData) {
			const value = data[effectivePrimary] ?? 0;
			if (!isDelta || value !== 0) {
				entries.push({ h3index, value, properties: data, boundary: this.boundaryCache.get(h3index) });
			}
		}
		return entries;
	}

	// ── Hex zone (lasso) operations ──────────────────────────────────────

	findHexesInPolygon(polygon: [number, number][]): string[] {
		// Pre-compute bounding box of the lasso polygon to skip ~90% of candidates
		let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
		for (const [lng, lat] of polygon) {
			if (lng < minLng) minLng = lng;
			if (lng > maxLng) maxLng = lng;
			if (lat < minLat) minLat = lat;
			if (lat > maxLat) maxLat = lat;
		}

		const result: string[] = [];
		for (const [h3index, centroid] of this.centroidCache) {
			const [lng, lat] = centroid;
			// Fast bbox rejection
			if (lng < minLng || lng > maxLng || lat < minLat || lat > maxLat) continue;
			if (pointInPolygon([lng, lat], polygon)) {
				result.push(h3index);
			}
		}
		return result;
	}

	private async ensureProvincialAvg(): Promise<number[]> {
		if (this.provincialAvg) return this.provincialAvg;
		if (!this.activeLayer) return [];

		const layer = this.activeLayer;
		const dataUrl = this.layerGlobalUrl(layer);
		if (!dataUrl) return [];

		const numVars = this.numericVariables;
		if (numVars.length === 0) return [];

		try {
			// Inspect actual parquet schema first to avoid Binder errors when config
			// and parquet columns are out of sync (stale config / new pipeline output).
			const schemaResult = await query(`SELECT * FROM '${dataUrl}' LIMIT 0`);
			const actualCols = new Set(schemaResult.schema.fields.map((f: any) => f.name as string));
			const availableVars = numVars.filter(v => actualCols.has(v.col));

			if (availableVars.length === 0) {
				this.provincialAvg = numVars.map(() => 1);
			} else {
				const aggExprs = availableVars.map(v => `AVG(${v.col}) as avg_${v.col}`).join(', ');
				const whereClause = actualCols.has(layer.primaryVariable)
					? `WHERE ${layer.primaryVariable} IS NOT NULL`
					: '';
				const sql = `SELECT ${aggExprs} FROM '${dataUrl}' ${whereClause}`;
				const result = await query(sql);
				const row = result.get(0)!.toJSON() as Record<string, any>;
				this.provincialAvg = numVars.map(v =>
					actualCols.has(v.col) ? (Number(row[`avg_${v.col}`]) || 1) : 1
				);
			}
		} catch (e) {
			console.warn('ensureProvincialAvg failed (schema mismatch?), using defaults:', e);
			this.provincialAvg = numVars.map(() => 1);
		}

		// Update persistent cache with provincial avg
		const cached = layerDataCache.get(layer.id);
		if (cached) cached.provincialAvg = this.provincialAvg;
		return this.provincialAvg;
	}

	async ensureColorDomain(): Promise<[number, number] | null> {
		if (this.colorDomain) return this.colorDomain;
		if (!this.activeLayer) return null;

		const layer = this.activeLayer;
		const dataUrl = this.layerGlobalUrl(layer);
		if (!dataUrl) return null;

		const pv = layer.primaryVariable;
		try {
			const sql = `SELECT MIN(${pv}) as lo, MAX(${pv}) as hi FROM '${dataUrl}' WHERE ${pv} IS NOT NULL`;
			const result = await query(sql);
			const row = result.get(0)!.toJSON() as Record<string, any>;
			const lo = Number(row.lo) || 0;
			const hi = Number(row.hi) || 100;
			if (hi > lo) {
				this.colorDomain = [lo, hi];
			}
			return this.colorDomain;
		} catch {
			return null;
		}
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

			// Compute averages from visibleData (numeric vars only)
			const numVars = this.numericVariables;
			const rawValues = new Array(numVars.length).fill(0);
			let count = 0;
			for (const h3index of h3indices) {
				const data = this.visibleData.get(h3index);
				if (!data) continue;
				count++;
				for (let v = 0; v < numVars.length; v++) {
					rawValues[v] += data[numVars[v].col] || 0;
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
		return this.numericVariables.map(v => i18n.t(v.labelKey));
	}

	// ── Selection petal data (individual hex clicks) ─────────────────────

	get selectionPetalLayers(): Array<{ values: number[]; color: string }> {
		if (!this.activeLayer || this.selectedHexes.size === 0 || !this.provincialAvg) return [];
		const provAvg = this.provincialAvg;
		const vars = this.numericVariables;
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
		this.centroidCache = new Map();
		this.boundaryCache = new Map();
		this.selectedDpto = null;
		this.temporalMode = 'current';
		this.dataVersion++;
		this.selectedHexes = new Map();
		this.hexZones = [];
		this.colorIndex = 0;
		this.provincialAvg = null;
		this.colorDomain = null;
	}
}
