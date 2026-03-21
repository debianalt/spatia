<script lang="ts">
	import { LENS_CONFIG, type LensId } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { i18n, type Locale } from '$lib/stores/i18n.svelte';

	let { lensStore }: { lensStore: LensStore } = $props();

	const lensIds: LensId[] = ['invertir', 'producir', 'servir', 'vivir'];


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
		color: #d4d4d4;
		font-size: 11px;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
		white-space: nowrap;
	}
	.lens-pill:hover {
		border-color: var(--lc);
		color: #ffffff;
		background: color-mix(in srgb, var(--lc) 10%, transparent);
	}
	.lens-pill.active {
		border-color: var(--lc);
		color: #ffffff;
		background: color-mix(in srgb, var(--lc) 20%, transparent);
		font-weight: 600;
	}
	.lens-label {
		line-height: 1;
	}
</style>
