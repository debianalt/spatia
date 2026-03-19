<script lang="ts">
	import { GRADIENT_CSS, LENS_CONFIG } from '$lib/config';
	import { MapStore } from '$lib/stores/map.svelte';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let { mapStore, lensStore }: { mapStore: MapStore; lensStore: LensStore } = $props();

	const lens = $derived(lensStore.activeLens);
	const cfg = $derived(lens ? LENS_CONFIG[lens] : null);
</script>

<div class="mt-2 pt-2 border-t border-border text-[11px]">
	{#if lens && cfg}
		<!-- Lens mode legend -->
		<div class="font-semibold mb-1.5 text-text-muted">
			{cfg.label[i18n.locale as 'es' | 'en' | 'gn']}
		</div>
		<div class="flex items-center gap-2 mb-1">
			<span class="inline-block w-3 h-3 rounded-sm" style:background={cfg.color} style:opacity="0.5"></span>
			<span class="text-[9px] text-text-dim">{i18n.t('legend.lensOpportunity')}</span>
		</div>
		<div class="flex items-center gap-2">
			<span class="inline-block w-3 h-3 rounded-sm" style:background="#222240"></span>
			<span class="text-[9px] text-text-dim">{i18n.t('legend.lensRest')}</span>
		</div>
	{:else}
		<!-- Default population legend -->
		<div class="font-semibold mb-1.5 text-text-muted">{i18n.t(mapStore.currentRamp.legendTitleKey)}</div>
		<div class="w-full h-2.5 rounded" style="background: {GRADIENT_CSS}"></div>
		<div class="flex justify-between w-full text-[9px] text-text-dim mt-0.5">
			{#each mapStore.currentRamp.legendLabels as label}
				<span>{label}</span>
			{/each}
		</div>
	{/if}
</div>
