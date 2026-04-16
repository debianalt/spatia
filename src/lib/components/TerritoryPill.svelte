<script lang="ts">
	import { TERRITORY_REGISTRY } from '$lib/config';
	import type { TerritoryStore } from '$lib/stores/territory.svelte';

	let { territoryStore }: { territoryStore: TerritoryStore } = $props();

	const available = $derived(
		Object.values(TERRITORY_REGISTRY).filter(t => t.available)
	);

	const compareCandidates = $derived(
		available.filter(t => t.id !== territoryStore.activeTerritory.id)
	);

	function toggleCompare() {
		if (territoryStore.compareModeActive) {
			territoryStore.exitCompareMode();
		} else if (compareCandidates.length === 1) {
			territoryStore.enterCompareMode(compareCandidates[0].id);
		}
	}
</script>

<div class="territory-bar">
	{#each available as t (t.id)}
		<button
			class="t-btn"
			class:active={t.id === territoryStore.activeTerritory.id}
			onclick={() => territoryStore.setTerritory(t.id)}
		>
			<span class="t-flag">{t.flag}</span>
			<span class="t-name">{t.label}</span>
		</button>
	{/each}

	{#if compareCandidates.length > 0}
		<div class="t-divider" />
		<button
			class="t-compare"
			class:comparing={territoryStore.compareModeActive}
			onclick={toggleCompare}
			title={territoryStore.compareModeActive ? 'Salir de comparación' : `Comparar con ${compareCandidates[0].label}`}
		>
			{#if territoryStore.compareModeActive}
				{territoryStore.compareTerritory?.flag} ×
			{:else}
				⇄
			{/if}
		</button>
	{/if}
</div>

<style>
	.territory-bar {
		position: absolute;
		bottom: 32px;
		left: 12px;
		z-index: 10;
		display: flex;
		align-items: center;
		gap: 2px;
		background: rgba(10, 12, 18, 0.88);
		border: 1px solid rgba(255, 255, 255, 0.10);
		border-radius: 7px;
		backdrop-filter: blur(8px);
		padding: 3px;
	}

	.t-btn {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 4px 9px;
		background: none;
		border: none;
		border-radius: 5px;
		cursor: pointer;
		transition: background 0.12s;
		color: rgba(255, 255, 255, 0.60);
		white-space: nowrap;
	}
	.t-btn:hover { background: rgba(255,255,255,0.07); color: rgba(255,255,255,0.85); }
	.t-btn.active {
		background: rgba(255,255,255,0.10);
		color: #e2e8f0;
	}

	.t-flag { font-size: 12px; line-height: 1; }
	.t-name { font-size: 10px; font-weight: 600; letter-spacing: 0.02em; }

	.t-divider {
		width: 1px;
		height: 16px;
		background: rgba(255,255,255,0.10);
		margin: 0 2px;
	}

	.t-compare {
		padding: 4px 8px;
		background: none;
		border: none;
		border-radius: 5px;
		cursor: pointer;
		font-size: 11px;
		color: rgba(255,255,255,0.35);
		transition: all 0.12s;
		line-height: 1;
	}
	.t-compare:hover { background: rgba(59,130,246,0.10); color: #93c5fd; }
	.t-compare.comparing { color: #fca5a5; }
	.t-compare.comparing:hover { background: rgba(239,68,68,0.10); }
</style>
