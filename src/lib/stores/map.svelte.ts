import { COLOR_RAMPS } from '$lib/config';

export type RadioData = {
	color: string;
	census: Record<string, any>;
	enriched: Record<string, any> | null;
	buildingCount: number;
};

const RADIO_COLORS = ['#60a5fa', '#f97316', '#22c55e', '#a855f7', '#ef4444', '#eab308'];

export type ChartDataSet = {
	title: string;
	type: 'bar' | 'ranking';
	data: Array<{ label: string; value: number }>;
	unit?: string;
};

export class MapStore {
	selectedRadios: Map<string, RadioData> = $state(new Map());
	pitch: number = $state(31);
	chatHighlightedRedcodes: string[] = $state([]);
	chatCharts: ChartDataSet[] = $state([]);
	lensActive: boolean = $state(false);

	private colorIndex = 0;

	get currentRamp() {
		return COLOR_RAMPS.population;
	}

	getColorExpr(): unknown[] {
		if (this.lensActive) {
			// Neutral grey buildings when lens is active
			return [
				'interpolate', ['linear'],
				['coalesce', ['get', 'best_height_m'], 5],
				5, '#12121f',
				10, '#1a1a2e',
				20, '#222240',
				40, '#2a2a4a'
			];
		}
		const ramp = this.currentRamp;
		return [
			'interpolate', ['linear'],
			['coalesce', ['get', ramp.property], 0],
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

	setChatHighlight(redcodes: string[]) {
		this.chatHighlightedRedcodes = redcodes;
	}

	setChatCharts(charts: ChartDataSet[]) {
		this.chatCharts = charts;
	}

	clearChatState() {
		this.chatHighlightedRedcodes = [];
		this.chatCharts = [];
	}
}
