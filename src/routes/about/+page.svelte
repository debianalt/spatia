<svelte:head>
	<title>Acerca — Spatia</title>
	<meta name="description" content="Spatia es una plataforma de inteligencia geoespacial para el NEA argentino. Desarrollada en CONICET / FHyCS-UNaM." />
	<meta property="og:title" content="Acerca — Spatia" />
	<meta property="og:description" content="Plataforma de inteligencia geoespacial para el NEA. CONICET / FHyCS-UNaM." />
	<meta property="og:image" content="https://spatia.ar/og-image.png" />
	<meta property="og:url" content="https://spatia.ar/about" />
</svelte:head>

<div class="min-h-screen bg-bg text-text font-mono">
	<!-- Header -->
	<header class="sticky top-0 z-50 border-b border-border" style="background: rgba(10,12,18,0.88); backdrop-filter: blur(8px);">
		<div class="flex items-center justify-between px-4 py-2.5">
			<div class="flex items-center gap-4">
				<a href="/" class="text-[17px] font-bold text-white tracking-wide hover:text-white/80 transition-colors">spatia.ar</a>
				<nav class="flex items-center gap-1 text-[13px]">
					<a href="/" class="text-white/40 hover:text-white transition-colors">Mapa</a>
					<span class="text-white/20">&middot;</span>
					<a href="/trade" class="text-white/40 hover:text-white transition-colors">Trade</a>
					<span class="text-white/20">&middot;</span>
					<span class="text-white font-semibold">Acerca</span>
				</nav>
			</div>
		</div>
	</header>

	<main class="max-w-3xl mx-auto px-6 py-16">

		<!-- Hero -->
		<section class="mb-16">
			<h1 class="text-3xl font-bold text-white mb-3">Spatia</h1>
			<p class="text-lg text-white/60 leading-relaxed max-w-2xl">
				Plataforma de inteligencia geoespacial para el NEA argentino. Integra datos satelitales,
				censales y ambientales en una grilla hexagonal H3 para análisis territorial a escala local.
			</p>
		</section>

		<!-- Quién lo construye -->
		<section class="mb-12">
			<h2 class="text-sm font-bold text-white/40 uppercase tracking-wider mb-6">Quién lo construye</h2>
			<div class="border border-border rounded-lg p-6 bg-white/[0.02]">
				<p class="text-white font-semibold mb-1">Raimundo Elías Gómez</p>
				<p class="text-[13px] text-white/50 mb-3">Investigador · Economía Ecológica · Geomática aplicada</p>
				<p class="text-[13px] text-white/50">CONICET / FHyCS-UNaM / GEE Partner</p>
			</div>
		</section>

		<!-- Datos -->
		<section class="mb-12">
			<h2 class="text-sm font-bold text-white/40 uppercase tracking-wider mb-6">Fuentes de datos</h2>
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				<div class="border border-border rounded-lg p-4 bg-white/[0.02]">
					<h3 class="text-[12px] font-bold text-white/70 mb-2">Satelital</h3>
					<ul class="text-[12px] text-white/40 space-y-1">
						<li>Landsat 8/9 · Sentinel-1/2 (ESA/USGS)</li>
						<li>MODIS Terra/Aqua (NASA)</li>
						<li>VIIRS NOAA · GEDI NASA</li>
						<li>Hansen/UMD Global Forest Change v1.12</li>
						<li>ESA CCI Biomass v6 · SoilGrids ISRIC</li>
					</ul>
				</div>
				<div class="border border-border rounded-lg p-4 bg-white/[0.02]">
					<h3 class="text-[12px] font-bold text-white/70 mb-2">Vectorial y censal</h3>
					<ul class="text-[12px] text-white/40 space-y-1">
						<li>INDEC — Censo 2022</li>
						<li>Overture Maps Foundation (CC BY 4.0)</li>
						<li>OpenStreetMap contributors</li>
						<li>Oxford MAP Accessibility (Weiss et al.)</li>
						<li>IGN Argentina — límites administrativos</li>
					</ul>
				</div>
			</div>
		</section>

		<!-- Metodología -->
		<section class="mb-12">
			<h2 class="text-sm font-bold text-white/40 uppercase tracking-wider mb-6">Metodología</h2>
			<div class="border border-border rounded-lg p-6 bg-white/[0.02] text-[13px] text-white/50 space-y-3 leading-relaxed">
				<p><strong class="text-white/70">Grilla:</strong> H3 resolución 9 (~174 m de lado, ~0.1 km²). 27 análisis satelitales y censales indexados en la misma grilla hexagonal.</p>
				<p><strong class="text-white/70">Scoring:</strong> PCA + k-means sobre variables estandarizadas. Cada hexágono recibe un percentil provincial (0–100) y un tipo cualitativo por cluster. Metodología compatible con OCDE Handbook y PNUD HDI.</p>
				<p><strong class="text-white/70">Infraestructura:</strong> Google Earth Engine para procesamiento satelital · Cloudflare R2 para Parquet/PMTiles · DuckDB-WASM en cliente · H3-js para índices geoespaciales.</p>
				<p><strong class="text-white/70">EUDR:</strong> Hansen GFC v1.12 (30 m, Landsat 1984–2021) + MODIS MCD64A1 Burned Area. Cobertura: NOA y NEA (10 provincias, ~187.000 celdas H3 res-7).</p>
			</div>
		</section>

		<!-- Contacto -->
		<section class="mb-12">
			<h2 class="text-sm font-bold text-white/40 uppercase tracking-wider mb-4">Contacto</h2>
			<p class="text-[13px] text-white/50">
				Para consultas, diagnósticos o acceso API: <span class="text-white/70">contacto@spatia.ar</span>
			</p>
		</section>

		<!-- Back links -->
		<div class="flex gap-6 text-[12px] text-white/30 border-t border-border pt-8">
			<a href="/" class="hover:text-white transition-colors">← Mapa principal</a>
			<a href="/trade" class="hover:text-white transition-colors">← Spatia Trade</a>
		</div>

	</main>

	<footer class="border-t border-border mt-8 py-6 text-center text-[11px] text-white/20">
		<p>Spatia · CONICET / FHyCS-UNaM · {new Date().getFullYear()}</p>
	</footer>
</div>
