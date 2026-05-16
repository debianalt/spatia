<script lang="ts">
	import { LENS_CONFIG, type LensId } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { i18n, type Locale } from '$lib/stores/i18n.svelte';

	let { lensStore }: { lensStore: LensStore } = $props();

	const lensIds: LensId[] = ['vivir', 'invertir', 'producir', 'servir'];
</script>

<div class="lens-bar">
	{#each lensIds as id}
		{@const cfg = LENS_CONFIG[id]}
		{@const active = lensStore.activeLens === id}
		<button
			class="lens-btn"
			class:active
			style:--lc={cfg.color}
			onclick={() => lensStore.setLens(id)}
		>
			{cfg.label[i18n.locale as 'es' | 'en' | 'gn' | 'pt']}
		</button>
	{/each}
</div>

<style>
	.lens-bar {
		display: flex;
		gap: 2px;
	}
	.lens-btn {
		padding: 4px 14px;
		border: none;
		border-bottom: 2px solid transparent;
		background: transparent;
		color: rgba(255,255,255,0.5);
		font-size: 11px;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.15s;
		white-space: nowrap;
		letter-spacing: 0.02em;
	}
	.lens-btn:hover {
		color: rgba(255,255,255,0.8);
		border-bottom-color: rgba(255,255,255,0.2);
	}
	.lens-btn.active {
		color: #ffffff;
		font-weight: 700;
		border-bottom-color: var(--lc);
	}

	@media (max-width: 768px) {
		.lens-btn {
			padding: 8px 8px;
			font-size: 10px;
		}
	}
</style>
