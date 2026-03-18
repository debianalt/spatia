<script lang="ts">
	import { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		mapStore,
		hasSelection,
		onClear
	}: {
		mapStore: MapStore;
		hasSelection: boolean;
		onClear: () => void;
	} = $props();
</script>

{#if hasSelection}
	<div class="absolute top-14 left-3 z-10 rounded-lg p-2.5 px-3.5 border border-border"
		style="background: var(--color-panel); backdrop-filter: blur(8px);">
		<button
			class="block bg-btn-bg text-text-muted border border-btn-border rounded-md py-1.5 px-2.5 text-[11px] font-semibold cursor-pointer text-left transition-all hover:text-text"
			onclick={onClear}>
			&#10005; {i18n.t('ctrl.clear')}
		</button>
	</div>
{/if}
