<script lang="ts">
	import { getTerritoriesByCountry, type CountryId } from '$lib/config';
	import type { TerritoryStore } from '$lib/stores/territory.svelte';

	let { territoryStore }: { territoryStore: TerritoryStore } = $props();

	const byCountry = getTerritoriesByCountry();
	const countryOrder: CountryId[] = ['ar', 'py', 'br'];
	const countryNames: Record<CountryId, string> = { ar: 'Argentina', py: 'Paraguay', br: 'Brasil' };
	const countryFlags: Record<CountryId, string> = { ar: '🇦🇷', py: '🇵🇾', br: '🇧🇷' };

	// Countries that actually have territories
	const activeCountries = $derived(
		countryOrder.filter(c => (byCountry[c] ?? []).length > 0)
	);
</script>

<div class="territory-selector">
	{#each activeCountries as country}
		{@const territories = byCountry[country] ?? []}
		<div class="country-block">
			<div class="country-header">
				<span class="country-flag">{countryFlags[country]}</span>
				<span class="country-name">{countryNames[country]}</span>
			</div>

			<div class="territory-list">
				{#each territories as territory (territory.id)}
					<button
						class="territory-btn"
						class:active={territoryStore.activeTerritory.id === territory.id}
						class:unavailable={!territory.available}
						disabled={!territory.available}
						onclick={() => territoryStore.setTerritory(territory.id)}
						title={territory.available ? territory.label : `${territory.label} — próximamente`}
					>
						{#if territoryStore.activeTerritory.id === territory.id}
							<span class="dot active-dot">●</span>
						{:else if !territory.available}
							<span class="dot soon-dot">○</span>
						{:else}
							<span class="dot idle-dot">○</span>
						{/if}
						<span class="t-name">{territory.label}</span>
						{#if !territory.available}
							<span class="badge">próximamente</span>
						{/if}
					</button>
				{/each}
			</div>
		</div>
	{/each}

</div>

<style>
	.territory-selector {
		display: flex;
		flex-direction: column;
		gap: 1px;
		padding: 2px 0 6px;
	}

	/* Country accordion */
	.country-block {
		border-radius: 4px;
		overflow: hidden;
	}

	.country-header {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 4px 6px;
	}

	.country-flag { font-size: 11px; line-height: 1; }

	.country-name {
		font-size: 9px;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.50);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}

	/* Territory list inside accordion */
	.territory-list {
		display: flex;
		flex-direction: column;
		padding: 2px 0 2px 18px;
		gap: 1px;
	}

	.territory-btn {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 4px 6px;
		background: none;
		border: none;
		border-radius: 3px;
		cursor: pointer;
		text-align: left;
		width: 100%;
		transition: background 0.12s;
	}

	.territory-btn:hover:not(:disabled) {
		background: rgba(255, 255, 255, 0.06);
	}

	.territory-btn.active {
		background: rgba(255, 255, 255, 0.08);
	}

	.territory-btn.unavailable {
		cursor: not-allowed;
		opacity: 0.45;
	}

	.dot { font-size: 7px; line-height: 1; width: 8px; }
	.active-dot { color: #22c55e; }
	.soon-dot { color: rgba(255, 255, 255, 0.20); }
	.idle-dot { color: rgba(255, 255, 255, 0.35); }

	.t-name {
		font-size: 10px;
		font-weight: 500;
		color: rgba(255, 255, 255, 0.70);
		flex: 1;
	}

	.territory-btn.active .t-name { color: #e2e8f0; font-weight: 600; }
	.territory-btn.unavailable .t-name { color: rgba(255, 255, 255, 0.40); }

	.badge {
		font-size: 7.5px;
		color: rgba(255, 255, 255, 0.25);
		font-style: italic;
	}

</style>
