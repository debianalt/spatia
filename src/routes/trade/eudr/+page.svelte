<script lang="ts">
	import { i18n } from '$lib/stores/i18n.svelte';
</script>

<svelte:head>
	<title>EUDR &mdash; Spatia</title>
	<meta name="description" content={i18n.t('eudr.hero.subtitle')} />
	<meta property="og:title" content="EUDR — Spatia" />
	<meta property="og:description" content={i18n.t('eudr.hero.subtitle')} />
	<meta property="og:type" content="website" />
</svelte:head>

<div class="py-12">
	<!-- Hero -->
	<section class="mb-16">
		<div class="flex items-center gap-3 mb-4">
			<a href="/trade" class="text-[12px] text-white/40 hover:text-white">&larr; Spatia Trade</a>
		</div>
		<h1 class="text-3xl font-bold text-white mb-3">{i18n.t('eudr.hero.title')}</h1>
		<p class="text-lg text-white/60 max-w-3xl">
			{i18n.t('eudr.hero.subtitle')}
		</p>
		<div class="flex gap-3 mt-6">
			<a href="/trade/eudr/check"
				class="px-5 py-2.5 bg-white text-black font-bold text-[13px] rounded-lg hover:bg-white/80 transition-colors">
				{i18n.t('eudr.cta.try_demo')}
			</a>
			<a href="mailto:contacto@spatia.ar"
				class="px-5 py-2.5 border border-white/20 text-white/70 font-semibold text-[13px] rounded-lg hover:border-white/40 transition-colors">
				{i18n.t('eudr.cta.contact')}
			</a>
		</div>
	</section>

	<!-- What is EUDR -->
	<section class="mb-16">
		<h2 class="text-xl font-bold text-white mb-4">{i18n.t('eudr.what.title')}</h2>
		<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
			<div class="border border-border rounded-lg p-5 bg-white/[0.02]">
				<h3 class="text-sm font-bold text-white mb-2">{i18n.t('eudr.what.regulation')}</h3>
				<p class="text-[12px] text-white/50 leading-relaxed">{i18n.t('eudr.what.regulation_desc')}</p>
			</div>
			<div class="border border-border rounded-lg p-5 bg-white/[0.02]">
				<h3 class="text-sm font-bold text-white mb-2">{i18n.t('eudr.what.cutoff')}</h3>
				<p class="text-[12px] text-white/50 leading-relaxed">{i18n.t('eudr.what.cutoff_desc')}</p>
			</div>
			<div class="border border-border rounded-lg p-5 bg-white/[0.02]">
				<h3 class="text-sm font-bold text-white mb-2">{i18n.t('eudr.what.penalty')}</h3>
				<p class="text-[12px] text-white/50 leading-relaxed">{i18n.t('eudr.what.penalty_desc')}</p>
			</div>
		</div>
	</section>

	<!-- How it works -->
	<section class="mb-16">
		<h2 class="text-xl font-bold text-white mb-6">{i18n.t('eudr.how.title')}</h2>
		<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
			<div class="text-center">
				<div class="w-10 h-10 rounded-full bg-white/5 text-white/60 border border-border flex items-center justify-center text-lg font-bold mx-auto mb-3">1</div>
				<h3 class="text-sm font-bold text-white mb-1">{i18n.t('eudr.how.step1_title')}</h3>
				<p class="text-[12px] text-white/50">{i18n.t('eudr.how.step1_desc')}</p>
			</div>
			<div class="text-center">
				<div class="w-10 h-10 rounded-full bg-white/5 text-white/60 border border-border flex items-center justify-center text-lg font-bold mx-auto mb-3">2</div>
				<h3 class="text-sm font-bold text-white mb-1">{i18n.t('eudr.how.step2_title')}</h3>
				<p class="text-[12px] text-white/50">{i18n.t('eudr.how.step2_desc')}</p>
			</div>
			<div class="text-center">
				<div class="w-10 h-10 rounded-full bg-white/5 text-white/60 border border-border flex items-center justify-center text-lg font-bold mx-auto mb-3">3</div>
				<h3 class="text-sm font-bold text-white mb-1">{i18n.t('eudr.how.step3_title')}</h3>
				<p class="text-[12px] text-white/50">{i18n.t('eudr.how.step3_desc')}</p>
			</div>
		</div>
	</section>

	<!-- Data Sources -->
	<section class="mb-16">
		<h2 class="text-xl font-bold text-white mb-4">{i18n.t('eudr.data.title')}</h2>
		<div class="border border-border rounded-lg p-6 bg-white/[0.02]">
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-[13px]">
				<div>
					<h3 class="font-bold text-white/80 mb-2">{i18n.t('eudr.data.deforestation')}</h3>
					<ul class="text-white/50 space-y-1">
						<li>Hansen/UMD Global Forest Change v1.12 (30m, Landsat)</li>
						<li>MODIS MCD64A1 Burned Area (500m)</li>
					</ul>
				</div>
				<div>
					<h3 class="font-bold text-white/80 mb-2">{i18n.t('eudr.data.coverage')}</h3>
					<ul class="text-white/50 space-y-1">
						<li>NOA: Salta, Jujuy, Tucum&aacute;n, Catamarca, Santiago del Estero</li>
						<li>NEA: Formosa, Chaco, Corrientes, Misiones, Entre R&iacute;os</li>
						<li>~187,000 H3 res-7 hexagons</li>
						<li>{i18n.t('eudr.data.update_freq')}</li>
					</ul>
				</div>
			</div>
		</div>
	</section>

	<!-- Pricing -->
	<section class="mb-16">
		<h2 class="text-xl font-bold text-white mb-6">{i18n.t('eudr.pricing.title')}</h2>
		<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
			<div class="border border-border rounded-lg p-6 bg-white/[0.02]">
				<h3 class="text-sm font-bold text-white mb-1">Demo</h3>
				<p class="text-2xl font-bold text-white mb-2">{i18n.t('eudr.pricing.free')}</p>
				<ul class="text-[12px] text-white/50 space-y-1">
					<li>{i18n.t('eudr.pricing.demo_1')}</li>
					<li>{i18n.t('eudr.pricing.demo_2')}</li>
					<li>{i18n.t('eudr.pricing.demo_3')}</li>
				</ul>
			</div>
			<div class="border border-white/20 rounded-lg p-6 bg-white/[0.03]">
				<h3 class="text-sm font-bold text-white mb-1">Professional</h3>
				<p class="text-2xl font-bold text-white mb-2">{i18n.t('eudr.pricing.contact')}</p>
				<ul class="text-[12px] text-white/50 space-y-1">
					<li>{i18n.t('eudr.pricing.pro_1')}</li>
					<li>{i18n.t('eudr.pricing.pro_2')}</li>
					<li>{i18n.t('eudr.pricing.pro_3')}</li>
				</ul>
			</div>
			<div class="border border-border rounded-lg p-6 bg-white/[0.02]">
				<h3 class="text-sm font-bold text-white mb-1">Enterprise</h3>
				<p class="text-2xl font-bold text-white mb-2">{i18n.t('eudr.pricing.custom')}</p>
				<ul class="text-[12px] text-white/50 space-y-1">
					<li>{i18n.t('eudr.pricing.ent_1')}</li>
					<li>{i18n.t('eudr.pricing.ent_2')}</li>
					<li>{i18n.t('eudr.pricing.ent_3')}</li>
				</ul>
			</div>
		</div>
	</section>

	<!-- Regulatory Reference -->
	<section class="border-t border-border pt-8 text-[11px] text-white/30 leading-relaxed">
		<p>{i18n.t('eudr.disclaimer')}</p>
	</section>
</div>
