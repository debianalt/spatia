<script lang="ts">
	import { getTerritoriesByCountry, type CountryId } from '$lib/config';
	import type { TerritoryStore } from '$lib/stores/territory.svelte';

	let {
		territoryStore,
		activeCoverage = undefined,
	}: {
		territoryStore: TerritoryStore;
		activeCoverage?: Record<string, 'available' | 'pending' | 'unavailable'> | undefined;
	} = $props();

	const byCountry = getTerritoriesByCountry();
	const countryOrder: CountryId[] = ['ar', 'py', 'br'];
	const countryNames: Record<CountryId, string> = { ar: 'Argentina', py: 'Paraguay', br: 'Brasil' };
	const countryFlags: Record<CountryId, string> = { ar: '🇦🇷', py: '🇵🇾', br: '🇧🇷' };

	const activeCountries = $derived(
		countryOrder.filter(c => (byCountry[c] ?? []).length > 0)
	);

	function coverageColor(tid: string): string | null {
		if (tid === 'misiones') return null;
		const c = activeCoverage?.[tid];
		if (!c) return null;
		return c === 'available' ? '#22c55e' : c === 'pending' ? '#f59e0b' : '#6b7280';
	}

	function hasAvailable(country: CountryId): boolean {
		return (byCountry[country] ?? []).some(t => t.available);
	}

	const regionalLabel = $derived(
		territoryStore.countryFilter
			? `Vista Regional · ${countryFlags[territoryStore.countryFilter]}`
			: 'Vista Regional · NEA'
	);
</script>

<div class="territory-selector">
	{#if territoryStore.regionalMode}
		<!-- Collapsed: single-line indicator in regional mode -->
		<button
			class="regional-active-btn"
			onclick={() => territoryStore.exitRegionalMode()}
			title="Salir de vista regional"
		>
			<span class="r-dot">◉</span>
			<span class="r-label">{regionalLabel}</span>
			<span class="r-exit">seleccionar →</span>
		</button>
	{:else}
		<!-- Expanded: full territory list when in per-territory mode -->
		{#each activeCountries as country}
			{@const territories = byCountry[country] ?? []}
			{@const canSelect = hasAvailable(country)}
			<div class="country-block">
				<button
					class="country-header"
					class:country-active={territoryStore.regionalMode && territoryStore.countryFilter === country}
					disabled={!canSelect}
					onclick={() => canSelect && territoryStore.enterCountryView(country)}
					title={canSelect ? `Vista regional ${countryNames[country]}` : `${countryNames[country]} — próximamente`}
				>
					<span class="country-flag">{countryFlags[country]}</span>
					<span class="country-name">{countryNames[country]}</span>
					{#if canSelect}
						<span class="country-arrow">›</span>
					{/if}
				</button>

				<div class="territory-list">
					{#each territories as territory (territory.id)}
						{@const cc = coverageColor(territory.id)}
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
							{#if cc}
								<span class="coverage-dot" style="background:{cc}" title={activeCoverage?.[territory.id]}></span>
							{/if}
							{#if !territory.available}
								<span class="badge">próximamente</span>
							{/if}
						</button>
					{/each}
				</div>
			</div>
		{/each}

		<div class="regional-row">
			<button
				class="regional-btn"
				onclick={() => territoryStore.enterRegionalMode()}
			>
				<span class="r-dot">◎</span>
				Vista Regional NEA
			</button>
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

	/* ── Regional mode: collapsed single-line ── */
	.regional-active-btn {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 5px 6px;
		background: rgba(167, 139, 250, 0.12);
		border: 1px solid rgba(167, 139, 250, 0.3);
		border-radius: 3px;
		cursor: pointer;
		width: 100%;
		text-align: left;
		transition: all 0.15s;
	}

	.regional-active-btn:hover {
		background: rgba(167, 139, 250, 0.18);
		border-color: rgba(167, 139, 250, 0.5);
	}

	.r-label {
		font-size: 10px;
		font-weight: 600;
		color: #a78bfa;
		flex: 1;
	}

	.r-exit {
		font-size: 8.5px;
		color: rgba(167, 139, 250, 0.5);
		font-weight: 400;
		white-space: nowrap;
	}

	/* ── Per-territory mode: full list ── */
	.country-block {
		border-radius: 4px;
		overflow: hidden;
	}

	.country-header {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 4px 6px;
		background: none;
		border: none;
		border-radius: 3px;
		cursor: pointer;
		width: 100%;
		text-align: left;
		transition: background 0.12s;
	}

	.country-header:hover:not(:disabled) {
		background: rgba(167, 139, 250, 0.08);
	}

	.country-header:disabled {
		cursor: default;
		opacity: 0.5;
	}

	.country-header.country-active {
		background: rgba(167, 139, 250, 0.15);
		border: 1px solid rgba(167, 139, 250, 0.3);
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

	.country-header:hover:not(:disabled) .country-name {
		color: rgba(255, 255, 255, 0.75);
	}

	.country-arrow {
		font-size: 10px;
		color: rgba(167, 139, 250, 0.4);
		font-weight: 400;
	}

	.country-header:hover:not(:disabled) .country-arrow {
		color: rgba(167, 139, 250, 0.8);
	}

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

	.coverage-dot {
		width: 5px;
		height: 5px;
		border-radius: 50%;
		flex-shrink: 0;
		opacity: 0.85;
	}

	.badge {
		font-size: 7.5px;
		color: rgba(255, 255, 255, 0.25);
		font-style: italic;
	}

	.regional-row {
		margin-top: 6px;
		padding-top: 6px;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
	}

	.regional-btn {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 5px 6px;
		background: none;
		border: 1px solid transparent;
		border-radius: 3px;
		cursor: pointer;
		width: 100%;
		font-size: 10px;
		font-weight: 500;
		color: rgba(255, 255, 255, 0.55);
		transition: all 0.15s;
		text-align: left;
	}

	.regional-btn:hover {
		background: rgba(167, 139, 250, 0.08);
		color: rgba(255, 255, 255, 0.8);
	}

	.r-dot { font-size: 8px; color: #a78bfa; }
</style>
