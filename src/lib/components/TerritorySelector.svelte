<script lang="ts">
	import { getTerritoriesByCountry, TERRITORY_REGISTRY, type TerritoryConfig, type CountryId } from '$lib/config';
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

	// Which country contains the active territory
	const activeCountry = $derived(
		(Object.values(TERRITORY_REGISTRY).find(t => t.id === territoryStore.activeTerritory.id)?.country ?? 'ar') as CountryId
	);

	// Expanded state — auto-open the active territory's country
	let expanded = $state<Record<CountryId, boolean>>({ ar: true, py: false, br: false });

	$effect(() => {
		expanded[activeCountry] = true;
	});

	function toggle(country: CountryId) {
		expanded[country] = !expanded[country];
	}

	// Territories available for comparison (available, not the active one)
	const compareCandidates = $derived(
		Object.values(TERRITORY_REGISTRY).filter(
			t => t.available && t.id !== territoryStore.activeTerritory.id
		)
	);

	let showCompareSelector = $state(false);

	function toggleCompare() {
		if (territoryStore.compareModeActive) {
			territoryStore.exitCompareMode();
			showCompareSelector = false;
		} else {
			showCompareSelector = !showCompareSelector;
		}
	}

	function selectCompare(t: TerritoryConfig) {
		territoryStore.enterCompareMode(t.id);
		showCompareSelector = false;
	}
</script>

<div class="territory-selector">
	{#each activeCountries as country}
		{@const territories = byCountry[country] ?? []}
		<div class="country-block">
			<button
				class="country-header"
				class:open={expanded[country]}
				onclick={() => toggle(country)}
			>
				<span class="country-flag">{countryFlags[country]}</span>
				<span class="country-name">{countryNames[country]}</span>
				<span class="chevron">{expanded[country] ? '▾' : '▸'}</span>
			</button>

			{#if expanded[country]}
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
			{/if}
		</div>
	{/each}

	<!-- Compare row -->
	<div class="compare-row">
		<button
			class="compare-btn"
			class:active={territoryStore.compareModeActive}
			disabled={compareCandidates.length === 0}
			title={compareCandidates.length === 0
				? 'Disponible cuando haya más territorios'
				: territoryStore.compareModeActive
					? `Comparando con ${territoryStore.compareTerritory?.label} — click para salir`
					: 'Comparar territorios'}
			onclick={toggleCompare}
		>
			{#if territoryStore.compareModeActive}
				{territoryStore.compareTerritory?.flag} {territoryStore.compareTerritory?.label} ×
			{:else}
				Comparar territorios →
			{/if}
		</button>
	</div>

	{#if showCompareSelector && !territoryStore.compareModeActive}
		<div class="compare-picker">
			<span class="picker-label">Comparar con:</span>
			{#each compareCandidates as t (t.id)}
				<button class="territory-btn" onclick={() => selectCompare(t)}>
					<span>{t.flag}</span>
					<span class="t-name">{t.label}</span>
				</button>
			{/each}
		</div>
	{/if}
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
		width: 100%;
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 4px 6px;
		background: none;
		border: none;
		cursor: pointer;
		text-align: left;
		transition: background 0.12s;
		border-radius: 4px;
	}

	.country-header:hover {
		background: rgba(255, 255, 255, 0.05);
	}

	.country-header.open {
		background: rgba(255, 255, 255, 0.04);
	}

	.country-flag { font-size: 11px; line-height: 1; }

	.country-name {
		font-size: 9px;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.50);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		flex: 1;
	}

	.chevron {
		font-size: 8px;
		color: rgba(255, 255, 255, 0.25);
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

	/* Compare row */
	.compare-row {
		margin-top: 4px;
		padding-top: 4px;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
	}

	.compare-btn {
		width: 100%;
		padding: 4px 8px;
		background: none;
		border: 1px solid rgba(255, 255, 255, 0.10);
		border-radius: 4px;
		color: rgba(255, 255, 255, 0.30);
		font-size: 9px;
		font-weight: 600;
		cursor: not-allowed;
		transition: all 0.15s;
		text-align: center;
		letter-spacing: 0.02em;
	}

	.compare-btn:not(:disabled) {
		color: #93c5fd;
		border-color: rgba(59, 130, 246, 0.30);
		cursor: pointer;
	}

	.compare-btn:not(:disabled):hover {
		background: rgba(59, 130, 246, 0.10);
		color: #bfdbfe;
		border-color: rgba(59, 130, 246, 0.50);
	}

	.compare-btn.active {
		background: rgba(59, 130, 246, 0.12);
		border-color: rgba(59, 130, 246, 0.35);
		color: #93c5fd;
	}

	/* Compare picker */
	.compare-picker {
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 4px 6px;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 4px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		flex-wrap: wrap;
		margin-top: 4px;
	}

	.picker-label {
		font-size: 8px;
		color: rgba(255, 255, 255, 0.35);
		font-weight: 500;
	}
</style>
