import { LENS_CONFIG, type LensId, type AnalysisConfig } from '$lib/config';
import { getParquetUrl } from '$lib/config';
import { query, isReady } from '$lib/stores/duckdb';
import centroids from '$lib/data/centroids.json';

export interface OpportunityRow {
	redcode: string;
	dpto: string;
	[key: string]: any;
}

export interface DepartmentSummary {
	dpto: string;
	count: number;
	avgScore: number;
	centroid: [number, number]; // [lat, lng]
}

const centroidMap = centroids as unknown as Record<string, [number, number]>;

export class LensStore {
	activeLens: LensId | null = $state(null);
	activeAnalysis: AnalysisConfig | null = $state(null);
	opportunityRadios: Map<string, OpportunityRow> = $state(new Map());
	selectedOpportunity: string | null = $state(null);
	comparisonRadio: string | null = $state(null);
	comparisonMode: boolean = $state(false);
	dataLoaded: boolean = $state(false);
	selectedDpto: string | null = $state(null);

	private allData: Map<string, OpportunityRow> = new Map();

	async loadData(): Promise<void> {
		if (this.dataLoaded) return;
		if (!isReady()) return;
		try {
			const url = getParquetUrl('lens_opportunities');
			const result = await query(`SELECT * FROM '${url}'`);
			for (let i = 0; i < result.numRows; i++) {
				const row = result.get(i)!.toJSON() as OpportunityRow;
				this.allData.set(row.redcode, row);
			}
			this.dataLoaded = true;
			// If opportunities analysis was already selected before data loaded, activate now
			if (this.activeLens && this.activeAnalysis?.id === 'opportunities') {
				this.activateOpportunities();
			}
		} catch (e) {
			console.warn('Failed to load lens data:', e);
		}
	}

	setAnalysis(analysis: AnalysisConfig | null): void {
		this.activeAnalysis = analysis;
		this.selectedDpto = null;
		this.selectedOpportunity = null;
		this.comparisonRadio = null;
		this.comparisonMode = false;
	}

	clearAnalysis(): void {
		if (this.activeAnalysis?.id === 'opportunities') {
			this.deactivateOpportunities();
		}
		this.activeAnalysis = null;
	}

	setLens(id: LensId | null): void {
		if (id === this.activeLens && this.dataLoaded) {
			// Toggle off
			this.activeLens = null;
			this.activeAnalysis = null;
			this.opportunityRadios = new Map();
			this.selectedOpportunity = null;
			this.comparisonRadio = null;
			this.comparisonMode = false;
			this.selectedDpto = null;
			return;
		}

		this.activeLens = id;
		this.activeAnalysis = null;
		this.selectedOpportunity = null;
		this.comparisonRadio = null;
		this.comparisonMode = false;
		this.selectedDpto = null;
		// Don't auto-filter opportunities — wait for user to select "Oportunidades" analysis
		this.opportunityRadios = new Map();
	}

	activateOpportunities(): void {
		if (!this.activeLens) return;
		const config = LENS_CONFIG[this.activeLens];
		const filtered = new Map<string, OpportunityRow>();
		for (const [redcode, row] of this.allData) {
			const score = row[config.scoreCol];
			if (score != null && score >= config.threshold) {
				filtered.set(redcode, row);
			}
		}
		this.opportunityRadios = filtered;
	}

	deactivateOpportunities(): void {
		this.opportunityRadios = new Map();
		this.selectedDpto = null;
		this.selectedOpportunity = null;
		this.comparisonRadio = null;
		this.comparisonMode = false;
	}

	selectOpportunity(redcode: string): void {
		if (this.comparisonMode) {
			this.comparisonRadio = redcode;
			this.comparisonMode = false;
			return;
		}
		this.selectedOpportunity = redcode;
		this.comparisonRadio = null;
	}

	clearSelection(): void {
		this.selectedOpportunity = null;
		this.comparisonRadio = null;
		this.comparisonMode = false;
	}

	startComparison(): void {
		this.comparisonMode = true;
	}

	cancelComparison(): void {
		this.comparisonMode = false;
		this.comparisonRadio = null;
	}

	selectDpto(dpto: string): void {
		this.selectedDpto = dpto;
		this.selectedOpportunity = null;
		this.comparisonRadio = null;
		this.comparisonMode = false;
	}

	clearDpto(): void {
		this.selectedDpto = null;
		this.selectedOpportunity = null;
		this.comparisonRadio = null;
		this.comparisonMode = false;
	}

	radioCentroid(redcode: string): [number, number] | null {
		return centroidMap[redcode] ?? null;
	}

	dptoCentroid(dpto: string): [number, number] | null {
		let sumLat = 0, sumLng = 0, n = 0;
		for (const [redcode, row] of this.opportunityRadios) {
			if (row.dpto !== dpto) continue;
			const c = centroidMap[redcode];
			if (c) { sumLat += c[0]; sumLng += c[1]; n++; }
		}
		return n > 0 ? [sumLat / n, sumLng / n] : null;
	}

	get departmentSummary(): DepartmentSummary[] {
		if (!this.activeLens) return [];
		const config = LENS_CONFIG[this.activeLens];
		const groups = new Map<string, { count: number; totalScore: number; sumLat: number; sumLng: number; nCentroid: number }>();

		for (const [redcode, row] of this.opportunityRadios) {
			const dpto = row.dpto || 'Desconocido';
			const score = row[config.scoreCol] ?? 0;
			const g = groups.get(dpto) || { count: 0, totalScore: 0, sumLat: 0, sumLng: 0, nCentroid: 0 };
			g.count++;
			g.totalScore += score;
			const c = centroidMap[redcode];
			if (c) { g.sumLat += c[0]; g.sumLng += c[1]; g.nCentroid++; }
			groups.set(dpto, g);
		}

		const result: DepartmentSummary[] = [];
		for (const [dpto, g] of groups) {
			result.push({
				dpto,
				count: g.count,
				avgScore: g.count > 0 ? g.totalScore / g.count : 0,
				centroid: g.nCentroid > 0 ? [g.sumLat / g.nCentroid, g.sumLng / g.nCentroid] : [-27, -54.4]
			});
		}
		return result.sort((a, b) => b.count - a.count);
	}

	get dptoOpportunities(): Map<string, OpportunityRow> {
		if (!this.selectedDpto) return this.opportunityRadios;
		const filtered = new Map<string, OpportunityRow>();
		for (const [redcode, row] of this.opportunityRadios) {
			if (row.dpto === this.selectedDpto) {
				filtered.set(redcode, row);
			}
		}
		return filtered;
	}

	getSubScores(redcode: string): number[] {
		if (!this.activeLens) return [0, 0, 0, 0, 0, 0];
		const row = this.allData.get(redcode);
		if (!row) return [0, 0, 0, 0, 0, 0];
		const config = LENS_CONFIG[this.activeLens];
		return config.subCols.map(col => row[col] ?? 0);
	}

	getScore(redcode: string): number {
		if (!this.activeLens) return 0;
		const row = this.allData.get(redcode);
		if (!row) return 0;
		return row[LENS_CONFIG[this.activeLens].scoreCol] ?? 0;
	}

	getNotables(redcode: string): string[] {
		if (!this.activeLens) return [];
		const row = this.allData.get(redcode);
		if (!row) return [];
		const prefix = this.activeLens === 'invertir' ? 'inv'
			: this.activeLens === 'producir' ? 'prod'
			: this.activeLens === 'servir' ? 'serv' : 'viv';
		const text = row[`${prefix}_notable`] as string;
		if (!text) return [];
		return text.split(' | ').filter(Boolean);
	}

	getRisk(redcode: string): string {
		if (!this.activeLens) return '';
		const row = this.allData.get(redcode);
		if (!row) return '';
		const prefix = this.activeLens === 'invertir' ? 'inv'
			: this.activeLens === 'producir' ? 'prod'
			: this.activeLens === 'servir' ? 'serv' : 'viv';
		return (row[`${prefix}_risk`] as string) ?? '';
	}

	getDpto(redcode: string): string {
		return this.allData.get(redcode)?.dpto ?? '';
	}

	isOpportunity(redcode: string): boolean {
		return this.opportunityRadios.has(redcode);
	}

	get opportunityCount(): number {
		return this.opportunityRadios.size;
	}
}
