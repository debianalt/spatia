<script lang="ts">
	import '../../app.css';
	import { i18n } from '$lib/stores/i18n.svelte';
	import type { Locale } from '$lib/stores/i18n.svelte';

	let { children } = $props();
</script>

<div class="min-h-screen bg-bg text-text font-mono">
	<!-- Header -->
	<header class="sticky top-0 z-50 border-b border-border" style="background: rgba(10,12,18,0.88); backdrop-filter: blur(8px);">
		<div class="flex items-center justify-between px-4 py-2.5">
			<div class="flex items-center gap-4">
				<span class="text-[15px] font-bold text-white tracking-wide">
					spatia.ar
				</span>
				<nav class="flex items-center gap-1 text-[12px]">
					<a href="/" class="text-white/40 hover:text-white transition-colors">{i18n.t('header.nav.map')}</a>
					<span class="text-white/20">&middot;</span>
					<span class="text-white font-semibold">{i18n.t('header.nav.dashboards')}</span>
				</nav>
			</div>

			<div class="flex items-center gap-0.5">
				{#each (['es', 'en', 'gn'] as Locale[]) as lang}
					<button
						class="px-2 py-0.5 text-[11px] font-semibold rounded-full cursor-pointer border transition-all {i18n.locale === lang ? 'bg-white/10 text-white border-white/30' : 'bg-transparent text-white/50 border-transparent hover:text-white'}"
						onclick={() => i18n.setLocale(lang)}>
						{lang.toUpperCase()}
					</button>
				{/each}
			</div>
		</div>
	</header>

	<!-- Content -->
	<main class="max-w-6xl mx-auto px-6">
		{@render children()}
	</main>

	<!-- Footer -->
	<footer class="border-t border-border mt-16 py-8 text-center text-[11px] text-white/30">
		<div class="max-w-6xl mx-auto px-6">
			<p>Spatia &mdash; {i18n.t('trade.footer.tagline')}</p>
			<p class="mt-2">
				{i18n.t('trade.footer.data')} &middot;
				<a href="mailto:contacto@spatia.ar" class="text-white/50 hover:text-white">contacto@spatia.ar</a>
			</p>
		</div>
	</footer>
</div>

<style>
	:global(html), :global(body) {
		overflow: auto !important;
		height: auto !important;
	}
</style>
