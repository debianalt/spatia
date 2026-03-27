<script lang="ts">
	import { i18n } from '$lib/stores/i18n.svelte';
</script>

<svelte:head>
	<title>Dashboards &mdash; Spatia</title>
	<meta name="description" content={i18n.t('trade.hero.subtitle')} />
	<meta property="og:title" content="Dashboards — Spatia" />
	<meta property="og:description" content={i18n.t('trade.hero.subtitle')} />
	<meta property="og:type" content="website" />
</svelte:head>

<div class="py-16">
	<!-- Hero -->
	<section class="text-center mb-20">
		<h1 class="text-3xl font-bold text-white mb-3">Dashboards</h1>
		<p class="text-lg text-white/60 max-w-2xl mx-auto">
			{i18n.t('trade.hero.subtitle')}
		</p>
	</section>

	<!-- Product Cards -->
	<section class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-20">
		<!-- EUDR -->
		<a href="/trade/eudr"
			class="group border border-border rounded-lg p-6 hover:border-white/20 transition-all bg-white/[0.02] hover:bg-white/[0.04]">
			<div class="mb-3">
				<span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/10 text-white/70">
					{i18n.t('trade.status.available')}
				</span>
			</div>
			<h3 class="text-lg font-bold text-white mb-2">{i18n.t('trade.eudr.card_title')}</h3>
			<p class="text-[13px] text-white/50 leading-relaxed mb-4">
				{i18n.t('trade.eudr.card_desc')}
			</p>
			<span class="text-white/70 text-[12px] font-semibold group-hover:text-white transition-colors">
				{i18n.t('trade.eudr.card_cta')} &rarr;
			</span>
		</a>

		<!-- ARCA Radar (coming soon) -->
		<div class="border border-border/50 rounded-lg p-6 opacity-50 bg-white/[0.01]">
			<div class="mb-3">
				<span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/5 text-white/40">
					{i18n.t('trade.status.coming_soon')}
				</span>
			</div>
			<h3 class="text-lg font-bold text-white/60 mb-2">{i18n.t('trade.radar.card_title')}</h3>
			<p class="text-[13px] text-white/35 leading-relaxed">
				{i18n.t('trade.radar.card_desc')}
			</p>
		</div>

		<!-- Risk Assessment (coming soon) -->
		<div class="border border-border/50 rounded-lg p-6 opacity-50 bg-white/[0.01]">
			<div class="mb-3">
				<span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/5 text-white/40">
					{i18n.t('trade.status.coming_soon')}
				</span>
			</div>
			<h3 class="text-lg font-bold text-white/60 mb-2">{i18n.t('trade.risk.card_title')}</h3>
			<p class="text-[13px] text-white/35 leading-relaxed">
				{i18n.t('trade.risk.card_desc')}
			</p>
		</div>
	</section>

	<!-- Trust Section -->
	<section class="border-t border-border pt-12 text-center">
		<h2 class="text-sm font-bold text-white/40 uppercase tracking-wider mb-6">
			{i18n.t('trade.trust.title')}
		</h2>
		<div class="flex flex-wrap justify-center gap-8 text-[12px] text-white/40">
			<span>Hansen/UMD Global Forest Change</span>
			<span>NASA MODIS</span>
			<span>ESA Sentinel-2</span>
			<span>Google Earth Engine</span>
			<span>Cloudflare Edge Network</span>
		</div>
	</section>
</div>
