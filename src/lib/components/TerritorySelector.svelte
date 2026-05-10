<script lang="ts">
	import { TERRITORY_REGISTRY, type CountryId } from '$lib/config';
	import type { TerritoryStore } from '$lib/stores/territory.svelte';

	let {
		territoryStore,
		activeCoverage = undefined,
	}: {
		territoryStore: TerritoryStore;
		activeCoverage?: Record<string, 'available' | 'pending' | 'unavailable'> | undefined;
	} = $props();

	const countries = [
		{ id: 'ar' as CountryId, label: 'Vista NEA', flag: '🇦🇷' },
		{ id: 'py' as CountryId, label: 'Paraguay', flag: '🇵🇾' },
		{ id: 'br' as CountryId, label: 'Brasil', flag: '🇧🇷' },
	];

	function hasAvailable(countryId: CountryId): boolean {
		return Object.values(TERRITORY_REGISTRY).some(t => t.country === countryId && t.available);
	}

	function countryCoverage(countryId: CountryId): 'available' | 'pending' | null {
		if (!activeCoverage) return null;
		const territories = Object.values(TERRITORY_REGISTRY).filter(t => t.country === countryId);
		const coverages = territories.map(t => activeCoverage![t.id]).filter(Boolean);
		if (coverages.includes('available')) return 'available';
		if (coverages.includes('pending')) return 'pending';
		return null;
	}
</script>

<div class="country-selector">
	{#each countries as country}
		{@const available = hasAvailable(country.id)}
		{@const cov = countryCoverage(country.id)}
		<button
			class="country-btn"
			class:active={territoryStore.countryFilter === country.id}
			class:dimmed={!available}
			disabled={!available}
			onclick={() => available && territoryStore.enterCountryView(country.id)}
			title={available ? country.label : `${country.label} — próximamente`}
		>
			<span class="c-flag">{country.flag}</span>
			<span class="c-label">{country.label}</span>
			{#if cov === 'available'}
				<span class="cov-dot available" title="análisis disponible"></span>
			{:else if cov === 'pending'}
				<span class="cov-dot pending" title="análisis en proceso"></span>
			{:else if !available}
				<span class="soon">próximamente</span>
			{/if}
		</button>
	{/each}
</div>

<style>
	.country-selector {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 2px 0 6px;
	}

	.country-btn {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 6px 8px;
		background: none;
		border: 1px solid transparent;
		border-radius: 4px;
		cursor: pointer;
		width: 100%;
		text-align: left;
		transition: all 0.12s;
	}

	.country-btn:hover:not(:disabled) {
		background: rgba(255, 255, 255, 0.06);
		border-color: rgba(255, 255, 255, 0.1);
	}

	.country-btn.active {
		background: rgba(167, 139, 250, 0.14);
		border-color: rgba(167, 139, 250, 0.35);
	}

	.country-btn.dimmed {
		cursor: not-allowed;
		opacity: 0.35;
	}

	.c-flag {
		font-size: 13px;
		line-height: 1;
		flex-shrink: 0;
	}

	.c-label {
		font-size: 10.5px;
		font-weight: 500;
		color: rgba(255, 255, 255, 0.65);
		flex: 1;
	}

	.country-btn.active .c-label {
		color: #c4b5fd;
		font-weight: 600;
	}

	.country-btn:hover:not(:disabled) .c-label {
		color: rgba(255, 255, 255, 0.85);
	}

	.cov-dot {
		width: 5px;
		height: 5px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.cov-dot.available { background: #22c55e; opacity: 0.85; }
	.cov-dot.pending   { background: #f59e0b; opacity: 0.85; }

	.soon {
		font-size: 7.5px;
		color: rgba(255, 255, 255, 0.25);
		font-style: italic;
	}
</style>
