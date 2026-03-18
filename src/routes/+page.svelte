<script lang="ts">
	import { onMount } from 'svelte';
	import MapComponent from '$lib/components/Map.svelte';
	import Controls from '$lib/components/Controls.svelte';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import QueryDemo from '$lib/components/QueryDemo.svelte';
	import { MapStore } from '$lib/stores/map.svelte';
	import { initDuckDB, query, isReady } from '$lib/stores/duckdb';
	import { PARQUETS } from '$lib/config';
	import { i18n, type Locale } from '$lib/stores/i18n.svelte';

	const mapStore = new MapStore();

	let mapComponent: ReturnType<typeof MapComponent>;
	let mapContainer: HTMLDivElement;

	onMount(() => {
		initDuckDB().catch(e => console.warn('DuckDB init failed:', e));

		mapContainer?.addEventListener('radio-select', ((e: CustomEvent) => {
			const { redcode, selected, census } = e.detail;
			mapStore.addRadio(redcode, {
				census,
				enriched: null,
				buildingCount: selected.length
			});
			mapComponent?.setRadioHighlight([...mapStore.selectedRadios.keys()]);
			fetchRadioEnrichment(redcode);
		}) as EventListener);

		mapContainer?.addEventListener('radio-deselect', ((e: CustomEvent) => {
			const { redcode } = e.detail;
			mapStore.removeRadio(redcode);
			mapComponent?.setRadioHighlight([...mapStore.selectedRadios.keys()]);
		}) as EventListener);

		document.addEventListener('keydown', (e) => {
			if (e.key === 'Escape') {
				clearAll();
			}
		});
	});

	async function fetchRadioEnrichment(redcode: string): Promise<void> {
		if (!isReady()) return;
		if (!/^\d{9}$/.test(redcode)) return;
		try {
			const result = await query(
				`SELECT varones, mujeres, tasa_actividad, tasa_empleo, tasa_desocupacion, tamano_medio_hogar, pct_nbi FROM '${PARQUETS.radio_stats_master}' WHERE redcode = '${redcode}' LIMIT 1`
			);
			if (result.numRows === 0) return;
			const row = result.get(0)!;
			mapStore.updateEnriched(redcode, row.toJSON());
		} catch (e) {
			console.warn('DuckDB enrichment failed:', e);
		}
	}

	function handleRemoveRadio(redcode: string) {
		mapStore.removeRadio(redcode);
		mapComponent?.setRadioHighlight([...mapStore.selectedRadios.keys()]);
	}

	function clearAll() {
		mapStore.clearRadios();
		mapComponent?.clearRadioHighlight();
	}
</script>

<!-- Header -->
<div class="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-4 py-2.5 border-b border-border"
	style="background: rgba(10,12,18,0.88); backdrop-filter: blur(8px);">
	<h1 class="text-[15px] font-bold text-white tracking-wide">
		{i18n.t('header.title')} <span class="text-accent font-normal">&mdash; {i18n.t('header.subtitle')}</span>
	</h1>
	<div class="flex items-center gap-0.5">
		{#each (['es', 'en', 'gn'] as Locale[]) as lang}
			<button
				class="px-2 py-0.5 text-[11px] font-semibold rounded-full cursor-pointer border transition-all {i18n.locale === lang ? 'bg-accent-active text-accent border-accent' : 'bg-transparent text-text-dim border-transparent hover:text-text-muted'}"
				onclick={() => i18n.setLocale(lang)}>
				{lang.toUpperCase()}
			</button>
		{/each}
	</div>
</div>

<!-- Map (must be first, fills entire viewport) -->
<div bind:this={mapContainer} class="w-full h-full" style="position:fixed;inset:0;z-index:0;">
	<MapComponent bind:this={mapComponent} {mapStore} />
</div>

<!-- Controls -->
<Controls
	{mapStore}
	hasSelection={mapStore.selectedRadios.size > 0}
	onClear={clearAll}
/>

<!-- Sidebar -->
<Sidebar
	{mapStore}
	onRemoveRadio={handleRemoveRadio}
/>

<!-- Query Demo -->
<QueryDemo />
