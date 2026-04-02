<script lang="ts">
	import { page } from '$app/state';
</script>

<svelte:head>
	<title>{page.status} — spatia.ar</title>
</svelte:head>

<div class="min-h-screen bg-[#0a0c12] flex items-center justify-center font-mono">
	<div class="text-center space-y-6 px-8">
		<p class="text-6xl font-bold text-white/20">{page.status}</p>
		<p class="text-white/60 text-sm max-w-md">
			{#if page.status === 404}
				La página que buscás no existe.
			{:else}
				Algo salió mal. Intentá de nuevo.
			{/if}
		</p>
		<a href="/" class="inline-block px-6 py-2 text-xs uppercase tracking-widest text-white/80 border border-white/20 rounded hover:border-white/40 transition-colors">
			Volver al mapa
		</a>
	</div>
</div>
