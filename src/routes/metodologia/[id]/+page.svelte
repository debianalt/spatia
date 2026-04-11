<script lang="ts">
	import { i18n } from '$lib/stores/i18n.svelte';

	let { data } = $props();
	const title = $derived(i18n.t(data.titleKey));
	const description = $derived(data.descKey ? i18n.t(data.descKey) : null);

	const today = new Date().toLocaleDateString('es-AR', {
		year: 'numeric',
		month: 'long',
		day: 'numeric',
	});

	function handlePrint() {
		if (typeof window !== 'undefined') window.print();
	}
</script>

<svelte:head>
	<title>{title} · Metodología · nealab</title>
	<meta name="description" content="Metodología del análisis {title} en nealab" />
</svelte:head>

<div class="page">
	<!-- Print-only brand header -->
	<div class="print-brand">
		<strong>nealab</strong> · inteligencia geoespacial abierta · spatia.ar
	</div>

	<header class="hdr">
		<div class="hdr-actions no-print">
			<a class="back-link" href="/?a={data.id}">&larr; Volver al mapa</a>
			<button class="print-btn" onclick={handlePrint} type="button">
				↓ Imprimir / Guardar PDF
			</button>
		</div>
		<h1 class="title">{title}</h1>
		<div class="kicker">Metodología · nealab · inteligencia geoespacial abierta</div>
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
			Citación sugerida: Quenardelle, R. (2026). nealab — inteligencia geoespacial abierta para el NEA argentino. <a href="https://spatia.ar/metodologia/{data.id}">spatia.ar/metodologia/{data.id}</a>
		</p>
		<p class="affil">CONICET · FHyCS-UNaM · Google Earth Engine R&amp;I Program</p>
		<p class="print-only generated">Documento generado el {today} desde spatia.ar/metodologia/{data.id}</p>
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
	.print-brand { display: none; }
	.print-only { display: none; }
	.hdr { margin-bottom: 32px; }
	.hdr-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		margin-bottom: 16px;
	}
	.back-link {
		display: inline-block;
		color: #60a5fa;
		font-size: 12px;
		text-decoration: none;
	}
	.back-link:hover { text-decoration: underline; }
	.print-btn {
		background: rgba(59,130,246,0.15);
		border: 1px solid rgba(59,130,246,0.3);
		border-radius: 6px;
		color: #60a5fa;
		font-size: 12px;
		font-weight: 600;
		padding: 6px 12px;
		cursor: pointer;
		font-family: inherit;
		transition: all 0.15s;
	}
	.print-btn:hover {
		background: rgba(59,130,246,0.25);
		border-color: rgba(59,130,246,0.5);
	}
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

	/* ═════ Print ═════ */
	@media print {
		:global(html), :global(body) {
			background: #ffffff !important;
			color: #1a1a1a !important;
		}
		@page {
			size: A4;
			margin: 18mm 16mm 22mm 16mm;
		}
		.no-print { display: none !important; }
		.print-only { display: block !important; }
		.print-brand {
			display: block !important;
			font-size: 9pt;
			color: #6b7280;
			letter-spacing: 0.02em;
			padding-bottom: 6pt;
			margin-bottom: 14pt;
			border-bottom: 0.5pt solid #cbd5e1;
		}
		.print-brand strong { color: #0f172a; font-weight: 700; }
		.page {
			max-width: none;
			margin: 0;
			padding: 0;
			color: #1a1a1a;
			font-size: 10pt;
			line-height: 1.45;
		}
		.hdr { margin-bottom: 18pt; }
		.title {
			color: #0f172a;
			font-size: 22pt;
			line-height: 1.15;
			margin-bottom: 4pt;
		}
		.kicker { color: #64748b; font-size: 8pt; margin-bottom: 8pt; }
		.desc { color: #334155; font-size: 10pt; }
		.section { margin: 14pt 0; page-break-inside: avoid; }
		.section h2 {
			color: #0f172a;
			font-size: 11pt;
			border-bottom: 0.5pt solid #cbd5e1;
			padding-bottom: 3pt;
			margin-bottom: 6pt;
		}
		.section p { color: #1a1a1a; }
		.vars li {
			background: #f5f5f5;
			color: #1a1a1a;
			border: 0.25pt solid #e5e7eb;
			font-size: 9pt;
		}
		.vars code { color: #0f172a; font-weight: 600; }
		.note { color: #475569; font-size: 9pt; }
		.note a { color: #1d4ed8; }
		/* Show URL next to external links so print readers can find them */
		.section a[href^="http"]::after {
			content: " (" attr(href) ")";
			font-size: 8pt;
			color: #64748b;
		}
		.footer {
			border-top: 0.5pt solid #cbd5e1;
			color: #475569;
			font-size: 8pt;
			margin-top: 28pt;
			padding-top: 8pt;
		}
		.footer a { color: #1d4ed8; }
		.footer .generated { margin-top: 6pt; font-style: italic; color: #64748b; }
	}
</style>
