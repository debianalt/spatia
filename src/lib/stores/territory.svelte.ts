import { TERRITORY_REGISTRY, getDefaultTerritory, type TerritoryConfig, type CountryId } from '$lib/config';

export class TerritoryStore {
	activeTerritory: TerritoryConfig = $state(getDefaultTerritory());
	compareTerritory: TerritoryConfig | null = $state(null);
	compareModeActive: boolean = $state(false);
	regionalMode: boolean = $state(true);
	countryFilter: CountryId = $state('ar');

	setTerritory(id: string) {
		const t = TERRITORY_REGISTRY[id];
		if (!t || !t.available) return;
		this.activeTerritory = t;
		this.countryFilter = t.country;
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

	enterRegionalMode(country: CountryId | null = null) {
		this.compareTerritory = null;
		this.compareModeActive = false;
		this.countryFilter = country ?? 'ar';
		this.regionalMode = true;
		const resolved = country ?? 'ar';
		const first = Object.values(TERRITORY_REGISTRY).find(t => t.country === resolved && t.available);
		if (first) this.activeTerritory = first;
	}

	enterCountryView(country: CountryId) {
		this.enterRegionalMode(country);
	}

	exitRegionalMode() {
		this.regionalMode = false;
		this.countryFilter = 'ar';
	}

	get availableCount(): number {
		return Object.values(TERRITORY_REGISTRY).filter(t => t.available).length;
	}
}
