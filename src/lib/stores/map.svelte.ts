import { COLOR_RAMPS } from '$lib/config';

export type RadioData = {
	color: string;
	census: Record<string, any>;
	enriched: Record<string, any> | null;
	buildingCount: number;
};

const RADIO_COLORS = ['#60a5fa', '#f97316', '#22c55e', '#a855f7', '#ef4444', '#eab308'];

export type HexData = {
	h3index: string;
	jrc_occurrence?: number;
	jrc_recurrence?: number;
	jrc_seasonality?: number;
	flood_extent_pct?: number;
	flood_risk_score?: number;
};

export type FloodParcelData = {
	h3index: string;
	tipo: string;
	area_m2: number;
	color: string;
	flood_risk_score: number;
	jrc_occurrence: number;
	jrc_recurrence: number;
	jrc_seasonality: number;
	flood_extent_pct: number;
};

export type ScoresParcelData = {
	h3index: string;
	tipo: string;
	area_m2: number;
	color: string;
	scores: Record<string, number>;
	components: Record<string, number>;
};

export type DistrictData = {
	color: string;
	personas: number;
	enriched: Record<string, any> | null;
};

const FLOOD_PARCEL_COLORS = ['#60a5fa', '#f97316', '#22c55e', '#a855f7', '#ef4444', '#eab308'];
const SCORES_PARCEL_COLORS = ['#60a5fa', '#f97316', '#22c55e', '#a855f7', '#ef4444', '#eab308'];

export class MapStore {
	selectedRadios: Map<string, RadioData> = $state(new Map());
	selectedDistricts: Map<string, DistrictData> = $state(new Map());
	pitch: number = $state(31);
	bearing: number = $state(-15);
	activeHexLayer: string | null = $state(null);
	selectedHex: HexData | null = $state(null);
	selectedFloodParcels: FloodParcelData[] = $state([]);
	floodH3Data: Map<string, Record<string, number>> = $state(new Map());
	selectedScoresParcels: ScoresParcelData[] = $state([]);
	scoresH3Data: Map<string, Record<string, number>> = $state(new Map());
	private floodParcelColorIndex = 0;
	private scoresParcelColorIndex = 0;
	private colorIndex = 0;
	private districtColorIndex = 0;

	get currentRamp() {
		return COLOR_RAMPS.population;
	}

	getColorExpr(): unknown[] {
		const ramp = this.currentRamp;
		return [
			'interpolate', ['linear'],
			['coalesce', ['get', ramp.property], 0],
			...ramp.stops
		];
	}

	getHeightColorExpr(): unknown[] {
		const ramp = COLOR_RAMPS.height;
		return [
			'interpolate', ['linear'],
			['coalesce', ['get', ramp.property], 3],
			...ramp.stops
		];
	}

	addRadio(redcode: string, data: Omit<RadioData, 'color'>, colorOverride?: string) {
		if (this.selectedRadios.has(redcode)) return;
		const color = colorOverride || RADIO_COLORS[this.colorIndex % RADIO_COLORS.length];
		if (!colorOverride) this.colorIndex++;
		const updated = new Map(this.selectedRadios);
		updated.set(redcode, { ...data, color });
		this.selectedRadios = updated;
	}

	removeRadio(redcode: string) {
		if (!this.selectedRadios.has(redcode)) return;
		const updated = new Map(this.selectedRadios);
		updated.delete(redcode);
		this.selectedRadios = updated;
		if (updated.size === 0) this.colorIndex = 0;
	}

	hasRadio(redcode: string): boolean {
		return this.selectedRadios.has(redcode);
	}

	clearRadios() {
		this.selectedRadios = new Map();
		this.colorIndex = 0;
	}

	addDistrict(distrito: string, personas: number, colorOverride?: string) {
		if (this.selectedDistricts.has(distrito)) return;
		const color = colorOverride || RADIO_COLORS[this.districtColorIndex % RADIO_COLORS.length];
		if (!colorOverride) this.districtColorIndex++;
		const updated = new Map(this.selectedDistricts);
		updated.set(distrito, { color, personas, enriched: null });
		this.selectedDistricts = updated;
	}

	removeDistrict(distrito: string) {
		const updated = new Map(this.selectedDistricts);
		updated.delete(distrito);
		this.selectedDistricts = updated;
		if (updated.size === 0) this.districtColorIndex = 0;
	}

	hasDistrict(d: string): boolean {
		return this.selectedDistricts.has(d);
	}

	clearDistricts() {
		this.selectedDistricts = new Map();
		this.districtColorIndex = 0;
	}

	updateDistrictEnriched(distrito: string, enriched: Record<string, any>) {
		const existing = this.selectedDistricts.get(distrito);
		if (!existing) return;
		const updated = new Map(this.selectedDistricts);
		updated.set(distrito, { ...existing, enriched });
		this.selectedDistricts = updated;
	}

	updateEnriched(redcode: string, enriched: Record<string, any>) {
		const existing = this.selectedRadios.get(redcode);
		if (!existing) return;
		const updated = new Map(this.selectedRadios);
		updated.set(redcode, { ...existing, enriched });
		this.selectedRadios = updated;
	}

	updateCensus(redcode: string, census: Record<string, any>) {
		const existing = this.selectedRadios.get(redcode);
		if (!existing) return;
		const updated = new Map(this.selectedRadios);
		updated.set(redcode, { ...existing, census: { ...existing.census, ...census } });
		this.selectedRadios = updated;
	}

	setActiveHexLayer(layer: string | null) {
		this.activeHexLayer = layer;
	}

	setSelectedHex(hex: HexData | null) {
		this.selectedHex = hex;
	}

	clearHexState() {
		this.activeHexLayer = null;
		this.selectedHex = null;
	}

	addFloodParcel(data: Omit<FloodParcelData, 'color'>) {
		// Toggle: if already selected, remove it
		const existing = this.selectedFloodParcels.findIndex(p => p.h3index === data.h3index);
		if (existing >= 0) {
			this.selectedFloodParcels = this.selectedFloodParcels.filter((_, i) => i !== existing);
			if (this.selectedFloodParcels.length === 0) this.floodParcelColorIndex = 0;
			return;
		}
		const color = FLOOD_PARCEL_COLORS[this.floodParcelColorIndex % FLOOD_PARCEL_COLORS.length];
		this.floodParcelColorIndex++;
		this.selectedFloodParcels = [...this.selectedFloodParcels, { ...data, color }];
	}

	removeFloodParcel(h3index: string) {
		this.selectedFloodParcels = this.selectedFloodParcels.filter(p => p.h3index !== h3index);
		if (this.selectedFloodParcels.length === 0) this.floodParcelColorIndex = 0;
	}

	clearFloodParcels() {
		this.selectedFloodParcels = [];
		this.floodParcelColorIndex = 0;
	}

	setFloodH3Data(data: Map<string, Record<string, number>>) {
		this.floodH3Data = data;
	}

	clearFloodParcelState() {
		this.selectedFloodParcels = [];
		this.floodParcelColorIndex = 0;
		this.floodH3Data = new Map();
	}

	addScoresParcel(data: Omit<ScoresParcelData, 'color'>) {
		const existing = this.selectedScoresParcels.findIndex(p => p.h3index === data.h3index);
		if (existing >= 0) {
			this.selectedScoresParcels = this.selectedScoresParcels.filter((_, i) => i !== existing);
			if (this.selectedScoresParcels.length === 0) this.scoresParcelColorIndex = 0;
			return;
		}
		const color = SCORES_PARCEL_COLORS[this.scoresParcelColorIndex % SCORES_PARCEL_COLORS.length];
		this.scoresParcelColorIndex++;
		this.selectedScoresParcels = [...this.selectedScoresParcels, { ...data, color }];
	}

	clearScoresParcels() {
		this.selectedScoresParcels = [];
		this.scoresParcelColorIndex = 0;
	}

	setScoresH3Data(data: Map<string, Record<string, number>>) {
		this.scoresH3Data = data;
	}

	clearScoresParcelState() {
		this.selectedScoresParcels = [];
		this.scoresParcelColorIndex = 0;
		this.scoresH3Data = new Map();
	}
}
