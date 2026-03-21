<script lang="ts">
	import { MapStore } from '$lib/stores/map.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		mapStore,
		hasSelection,
		onClear,
		lassoActive = false,
		onToggleLasso,
		hasZones = false,
		onClearZones,
	}: {
		mapStore: MapStore;
		hasSelection: boolean;
		onClear: () => void;
		lassoActive?: boolean;
		onToggleLasso?: () => void;
		hasZones?: boolean;
		onClearZones?: () => void;
	} = $props();
</script>

<div class="absolute top-3 left-3 z-10 rounded-lg p-2.5 px-3.5 border border-border flex flex-col gap-1.5"
	style="background: var(--color-panel); backdrop-filter: blur(8px);">
	<!-- Lasso toggle -->
	{#if onToggleLasso}
		<button
			class="flex items-center gap-1.5 bg-btn-bg border rounded-md py-1.5 px-2.5 text-[11px] font-semibold cursor-pointer text-left transition-all {lassoActive ? 'border-accent text-accent' : 'border-btn-border text-text-muted hover:text-text'}"
			onclick={onToggleLasso}>
			<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<path d="M3 3 L12 2 L21 7 L18 18 L8 21 L2 14 Z" />
			</svg>
			{i18n.t('lasso.toggle')}
		</button>
	{/if}

	<!-- Lasso hint -->
	{#if lassoActive}
		<p class="text-[9px] text-text-dim leading-snug max-w-[140px] m-0 px-0.5">
			{i18n.t('lasso.hint')}
		</p>
	{/if}

	<!-- Clear zones -->
	{#if hasZones && onClearZones}
		<button
			class="block bg-btn-bg text-text-muted border border-btn-border rounded-md py-1.5 px-2.5 text-[11px] font-semibold cursor-pointer text-left transition-all hover:text-text hover:border-red-400"
			onclick={onClearZones}>
			&#10005; {i18n.t('lasso.clearZones')}
		</button>
	{/if}

	<!-- Clear selection -->
	{#if hasSelection}
		<button
			class="block bg-btn-bg text-text-muted border border-btn-border rounded-md py-1.5 px-2.5 text-[11px] font-semibold cursor-pointer text-left transition-all hover:text-text"
			onclick={onClear}>
			&#10005; {i18n.t('ctrl.clear')}
		</button>
	{/if}
</div>

