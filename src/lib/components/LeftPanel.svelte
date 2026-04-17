<script lang="ts">
	import TerritorySelector from './TerritorySelector.svelte';
	import type { TerritoryStore } from '$lib/stores/territory.svelte';

	let { territoryStore }: { territoryStore: TerritoryStore } = $props();
</script>

<div class="left-panel">
	<TerritorySelector {territoryStore} />
</div>

<style>
	.left-panel {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: 172px;
		z-index: 10;
		background: rgba(10, 12, 18, 0.88);
		backdrop-filter: blur(8px);
		border-right: 1px solid rgba(255, 255, 255, 0.07);
		overflow-y: auto;
		padding: 10px 8px 16px;
		scrollbar-width: thin;
		scrollbar-color: #334155 transparent;
	}
	.left-panel::-webkit-scrollbar { width: 3px; }
	.left-panel::-webkit-scrollbar-track { background: transparent; }
	.left-panel::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }

	@media (max-width: 768px) {
		.left-panel { display: none; }
	}
</style>
