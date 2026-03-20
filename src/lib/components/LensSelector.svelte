<script lang="ts">
	import { LENS_CONFIG, type LensId } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { i18n, type Locale } from '$lib/stores/i18n.svelte';

	let { lensStore }: { lensStore: LensStore } = $props();

	const lensIds: LensId[] = ['invertir', 'producir', 'servir', 'vivir'];

	function counterText(n: number): string {
		const tpl = i18n.t('lens.counter');
		return tpl.replace('{n}', String(n));
	}
</script>

<div class="lens-bar">
	<div class="lens-pills">
		{#each lensIds as id}
			{@const cfg = LENS_CONFIG[id]}
			{@const active = lensStore.activeLens === id}
			<button
				class="lens-pill"
				class:active
				style:--lc={cfg.color}
				onclick={() => lensStore.setLens(id)}
			>
				<span class="lens-label">{cfg.label[i18n.locale as 'es' | 'en' | 'gn']}</span>
			</button>
		{/each}
	</div>
	{#if lensStore.activeLens}
		<div class="lens-counter">
			{#if !lensStore.dataLoaded}
				{i18n.t('lens.loading')}
			{:else}
				{counterText(lensStore.opportunityCount)}
			{/if}
		</div>
	{/if}
</div>

<style>
	.lens-bar {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
	}
	.lens-pills {
		display: flex;
		gap: 4px;
	}
	.lens-pill {
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 3px 10px;
		border-radius: 9999px;
		border: 1px solid #334155;
		background: transparent;
		color: #94a3b8;
		font-size: 11px;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
		white-space: nowrap;
	}
	.lens-pill:hover {
		border-color: var(--lc);
		color: #e2e8f0;
		background: color-mix(in srgb, var(--lc) 10%, transparent);
	}
	.lens-pill.active {
		border-color: var(--lc);
		color: #e2e8f0;
		background: color-mix(in srgb, var(--lc) 20%, transparent);
		font-weight: 600;
	}
	.lens-label {
		line-height: 1;
	}
	.lens-counter {
		font-size: 10px;
		font-weight: 500;
		color: #e2e8f0;
		opacity: 0.9;
	}
</style>
