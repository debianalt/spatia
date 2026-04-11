<script lang="ts">
	import { i18n } from '$lib/stores/i18n.svelte';

	let { data } = $props();
	const title = $derived(i18n.t(data.titleKey));
	const description = $derived(data.descKey ? i18n.t(data.descKey) : null);
</script>

<svelte:head>
	<title>{title} · Metodología · Spatia</title>
	<meta name="description" content="Metodología del análisis {title} en Spatia" />
</svelte:head>

<div class="page">
	<header class="hdr">
		<a class="back-link" href="/?a={data.id}">&larr; Volver al mapa</a>
		<h1 class="title">{title}</h1>
		<div class="kicker">Metodología · Spatia · Inteligencia Territorial para Misiones</div>
		{#if description}
			<p class="desc">{description}</p>
		{/if}
	</header>

	<section class="section">
		<h2>¿Cómo leer el mapa?</h2>
		<p>{data.content.howToRead}</p>
	</section>

	<section class="section">
		<h2>Implicaciones</h2>
		<p>{data.content.implications}</p>
	</section>

	<section class="section">
		<h2>Metodología y fuentes</h2>
		<p>{data.content.method}</p>
	</section>

	{#if data.variables.length > 0}
		<section class="section">
			<h2>Variables incluidas</h2>
			<ul class="vars">
				{#each data.variables as v}
					<li><code>{v.col}</code> — {i18n.t(v.labelKey)}</li>
				{/each}
			</ul>
		</section>
	{/if}

	<section class="section">
		<h2>Datos descargables</h2>
		<p class="note">
			Los datos crudos de este análisis están disponibles en formato Parquet en Cloudflare R2, y pueden
			descargarse en CSV o GeoJSON desde el panel lateral del mapa una vez seleccionado un departamento.
		</p>
		<p class="note">
			Pipeline reproducible: <a href="https://github.com/raimundoquenardelle/spatia-pipeline" rel="noopener">github.com/…/spatia-pipeline</a>
		</p>
	</section>

	<footer class="footer">
		<p>
			Citación sugerida: Quenardelle, R. (2026). Spatia — Inteligencia Territorial para Misiones. <a href="https://spatia.ar/metodologia/{data.id}">spatia.ar/metodologia/{data.id}</a>
		</p>
		<p class="affil">CONICET / FHyCS-UNaM · Plataforma de análisis geoespacial abierto</p>
	</footer>
</div>

<style>
	.page {
		max-width: 720px;
		margin: 0 auto;
		padding: 32px 24px 64px;
		color: #e2e8f0;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
		font-size: 15px;
		line-height: 1.6;
	}
	.hdr { margin-bottom: 32px; }
	.back-link {
		display: inline-block;
		color: #60a5fa;
		font-size: 12px;
		text-decoration: none;
		margin-bottom: 16px;
	}
	.back-link:hover { text-decoration: underline; }
	.title {
		font-size: 28px;
		font-weight: 700;
		color: #f8fafc;
		margin: 0 0 4px;
		line-height: 1.2;
	}
	.kicker {
		font-size: 11px;
		color: #64748b;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin-bottom: 12px;
	}
	.desc {
		color: #cbd5e1;
		font-size: 14px;
		margin: 0;
	}
	.section { margin: 28px 0; }
	.section h2 {
		font-size: 14px;
		font-weight: 600;
		color: #f8fafc;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		margin: 0 0 10px;
		padding-bottom: 6px;
		border-bottom: 1px solid #1e293b;
	}
	.section p {
		color: #cbd5e1;
		margin: 0 0 10px;
	}
	.vars {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.vars li {
		font-size: 13px;
		color: #cbd5e1;
		padding: 4px 8px;
		background: rgba(255, 255, 255, 0.03);
		border-radius: 4px;
	}
	.vars code {
		color: #93c5fd;
		font-family: 'SF Mono', Monaco, monospace;
		font-size: 12px;
	}
	.note {
		font-size: 13px;
		color: #94a3b8;
	}
	.note a { color: #60a5fa; }
	.footer {
		margin-top: 48px;
		padding-top: 20px;
		border-top: 1px solid #1e293b;
		font-size: 12px;
		color: #64748b;
	}
	.footer p { margin: 4px 0; }
	.footer a { color: #60a5fa; }
	.affil { font-style: italic; }

	:global(body) { background: #0a0e1a; }
</style>
