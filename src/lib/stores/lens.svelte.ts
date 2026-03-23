import { type LensId, type AnalysisConfig } from '$lib/config';

export class LensStore {
	activeLens: LensId | null = $state(null);
	activeAnalysis: AnalysisConfig | null = $state(null);

	setLens(id: LensId | null): void {
		if (id === this.activeLens) {
			// Toggle off
			this.activeLens = null;
			this.activeAnalysis = null;
			return;
		}
		this.activeLens = id;
		this.activeAnalysis = null;
	}

	setAnalysis(analysis: AnalysisConfig | null): void {
		this.activeAnalysis = analysis;
	}

	clearAnalysis(): void {
		this.activeAnalysis = null;
	}

	clearSelection(): void {
		// No-op (kept for compatibility with clearAll in +page.svelte)
	}

	clearDpto(): void {
		// No-op (kept for compatibility)
	}
}
