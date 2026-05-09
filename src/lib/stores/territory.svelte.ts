import { TERRITORY_REGISTRY, getDefaultTerritory, type TerritoryConfig } from '$lib/config';

export class TerritoryStore {
	activeTerritory: TerritoryConfig = $state(getDefaultTerritory());
	compareTerritory: TerritoryConfig | null = $state(null);
	compareModeActive: boolean = $state(false);
	regionalMode: boolean = $state(false);

	setTerritory(id: string) {
		const t = TERRITORY_REGISTRY[id];
		if (!t || !t.available) return;
		this.activeTerritory = t;
		// Exit compare mode when switching primary territory (but NOT regional mode — Option D)
		this.compareTerritory = null;
		this.compareModeActive = false;
	}

	enterCompareMode(territoryId: string) {
		const t = TERRITORY_REGISTRY[territoryId];
		if (!t || !t.available) return;
		this.compareTerritory = t;
		this.compareModeActive = true;
	}

	exitCompareMode() {
		this.compareTerritory = null;
		this.compareModeActive = false;
	}

	enterRegionalMode() {
		this.compareTerritory = null;
		this.compareModeActive = false;
		this.regionalMode = true;
	}

	exitRegionalMode() {
		this.regionalMode = false;
	}

	get availableCount(): number {
		return Object.values(TERRITORY_REGISTRY).filter(t => t.available).length;
	}
}
