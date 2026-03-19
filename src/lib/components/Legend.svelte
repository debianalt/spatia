<script lang="ts">
	import { GRADIENT_CSS } from '$lib/config';
	import { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let { mapStore }: { mapStore: MapStore } = $props();
</script>

<div class="mt-2 pt-2 border-t border-border text-[11px]">
	<div class="font-semibold mb-1.5 text-text-muted">{i18n.t(mapStore.currentRamp.legendTitleKey)}</div>
	<div class="w-full h-2.5 rounded" style="background: {GRADIENT_CSS}"></div>
	<div class="flex justify-between w-full text-[9px] text-text-dim mt-0.5">
		{#each mapStore.currentRamp.legendLabels as label}
			<span>{label}</span>
		{/each}
	</div>
</div>
