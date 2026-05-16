<script lang="ts">
	import { i18n } from '$lib/stores/i18n.svelte';
	import LangSwitcher from '$lib/components/LangSwitcher.svelte';
	import { SERVICIOS } from '$lib/content/servicios';

	const today = new Date().toLocaleDateString('es-AR', {
		year: 'numeric',
		month: 'long',
		day: 'numeric',
	});

	const c = $derived(SERVICIOS[i18n.locale] ?? SERVICIOS.es);

	function handlePrint() {
		if (typeof window !== 'undefined') window.print();
	}
</script>

<svelte:head>
	<title>{c.pageTitle}</title>
	<meta name="description" content={c.metaDesc} />
	<meta property="og:title" content={c.ogTitle} />
	<meta property="og:description" content={c.ogDesc} />
</svelte:head>

<div class="page">
	<div class="content">
	<div class="print-brand">
		nealab · inteligencia geoespacial abierta · spatia.ar
	</div>

	<header class="hdr">
		<div class="hdr-actions no-print">
			<a class="back-link" href="/">{i18n.t('nav.backToMap')}</a>
			<div class="hdr-right">
				<LangSwitcher variant="mono" />
				<button class="print-btn" type="button" onclick={handlePrint}>
					{i18n.t('nav.printSave')}
				</button>
			</div>
		</div>
		<div class="kicker">{c.kicker}</div>
		<h1 class="title"><a class="title-link" href="/">nealab</a></h1>
		<p class="subtitle">
			{@html c.subtitle}
		</p>
	</header>

	<section class="section">
		<h2>{c.queEsTitle}</h2>
		<p>{@html c.queEsP1}</p>
		<p>{c.queEsP2}</p>
	</section>

	<section class="section">
		<h2>{c.marcoTitle}</h2>
		<p>{@html c.marcoP1}</p>
	</section>

	<section class="section">
		<h2>{c.principiosTitle}</h2>
		<ul class="list">
			{#each c.principios as item}
				<li>{@html item}</li>
			{/each}
		</ul>
	</section>

	<section class="section">
		<h2>{c.queOfreceTitle}</h2>
		<p>{c.queOfreceIntro}</p>
		<ul class="list">
			{#each c.queOfrece as item}
				<li>{@html item}</li>
			{/each}
		</ul>
		<p>{@html c.queOfreceFootnote}</p>
	</section>

	<section class="section">
		<h2>{c.paraQuienesTitle}</h2>
		<ul class="list">
			{#each c.paraQuienes as item}
				<li>{@html item}</li>
			{/each}
		</ul>
	</section>

	<section class="section">
		<h2>{c.serviciosTitle}</h2>
		<ul class="list">
			{#each c.servicios as item}
				<li>{@html item}</li>
			{/each}
		</ul>
	</section>

	<section class="section">
		<h2>{c.limitesTitle}</h2>
		<p>{c.limitesWarning}</p>
		<p>{@html c.limitesP1}</p>
		<p>{@html c.limitesP2}</p>
		<p>{@html c.limitesP3}</p>
		<p>{c.limitesP4}</p>
		<p>{@html c.limitesP5}</p>
		<div class="liability-block">
			<p class="liability-text">{@html c.liabilityText}</p>
			<a class="terms-link" href="/terminos">{c.termsLink}</a>
		</div>
	</section>

	<section class="section">
		<h2>{c.fuentesTitle}</h2>
		<p>{@html c.fuentesP1}</p>
	</section>

	<section class="section">
		<h2>{c.contactoTitle}</h2>
		<p>{@html c.contactoContent}</p>
	</section>

	<footer class="footer">
		<p>
			{c.citationLabel}: Gomez, R. E. (2026). nealab: A Zero-Cost Platform for Subnational
			Territorial Intelligence (Version v2). Zenodo.
			<a href="https://doi.org/10.5281/zenodo.19543818">https://doi.org/10.5281/zenodo.19543818</a>
		</p>
		<p class="affil">{c.affil}</p>
		<p class="print-only generated">
			{c.printGenerated.replace('{date}', today)}
		</p>
	</footer>
	</div>
</div>

<style>
	/* /servicios fills the viewport with its own scroll container —
	   the global app locks overflow on html/body for the map view. */
	.page {
		position: fixed;
		inset: 0;
		overflow-y: auto;
		overflow-x: hidden;
		background: #0a0a0a;
		color: #ffffff;
		font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 13px;
		line-height: 1.7;
		z-index: 50;
	}
	.content {
		max-width: 720px;
		margin: 0 auto;
		padding: 56px 32px 96px;
		text-align: left;
	}
	.print-brand { display: none; }
	.print-only { display: none; }

	.hdr { margin-bottom: 40px; }
	.hdr-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		margin-bottom: 24px;
	}
	.hdr-right {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.back-link {
		display: inline-block;
		color: rgba(255,255,255,0.55);
		font-size: 11px;
		text-decoration: none;
		letter-spacing: 0.02em;
	}
	.back-link:hover { color: #ffffff; }
	.print-btn {
		background: transparent;
		border: 1px solid rgba(255,255,255,0.25);
		border-radius: 0;
		color: rgba(255,255,255,0.7);
		font-size: 11px;
		font-weight: 500;
		padding: 6px 12px;
		cursor: pointer;
		font-family: inherit;
		letter-spacing: 0.02em;
		transition: all 0.15s;
	}
	.print-btn:hover {
		border-color: #ffffff;
		color: #ffffff;
	}

	.kicker {
		font-size: 10px;
		color: rgba(255,255,255,0.45);
		text-transform: uppercase;
		letter-spacing: 0.12em;
		margin-bottom: 10px;
	}
	.title {
		font-size: 40px;
		font-weight: 700;
		color: #ffffff;
		margin: 0 0 14px;
		line-height: 1.05;
		letter-spacing: -0.01em;
	}
	.title-link {
		color: inherit;
		text-decoration: none;
		transition: opacity 0.15s;
	}
	.title-link:hover { opacity: 0.7; }
	.subtitle {
		color: rgba(255,255,255,0.75);
		font-size: 14px;
		margin: 0;
	}

	.section { margin: 40px 0; }
	.section h2 {
		font-size: 11px;
		font-weight: 700;
		color: #ffffff;
		text-transform: uppercase;
		letter-spacing: 0.12em;
		margin: 0 0 16px;
		padding-bottom: 8px;
		border-bottom: 1px solid rgba(255,255,255,0.15);
	}
	.section p {
		color: rgba(255,255,255,0.8);
		margin: 0 0 14px;
		text-align: justify;
		text-justify: inter-word;
		hyphens: auto;
	}
	.section p strong { color: #ffffff; font-weight: 700; }
	.subtitle { text-align: justify; hyphens: auto; }
	.section a {
		color: #ffffff;
		text-decoration: underline;
		text-decoration-thickness: 1px;
		text-underline-offset: 3px;
	}
	.section a:hover { text-decoration-thickness: 2px; }

	.list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.list li {
		color: rgba(255,255,255,0.8);
		padding-left: 16px;
		position: relative;
		text-align: justify;
		text-justify: inter-word;
		hyphens: auto;
	}
	.list li::before {
		content: '—';
		position: absolute;
		left: 0;
		color: rgba(255,255,255,0.4);
	}
	.list li strong { color: #ffffff; font-weight: 700; }

	.liability-block {
		margin-top: 20px;
		padding: 20px;
		border: 1px solid rgba(255,255,255,0.2);
		background: rgba(255,255,255,0.03);
	}

	.liability-text {
		font-size: 12px;
		color: rgba(255,255,255,0.8);
		margin: 0 0 12px;
		text-align: justify;
		hyphens: auto;
	}

	.liability-text strong { color: #ffffff; }

	.terms-link {
		display: inline-block;
		font-size: 11px;
		color: rgba(255,255,255,0.55);
		text-decoration: underline;
		text-decoration-thickness: 1px;
		text-underline-offset: 3px;
		letter-spacing: 0.02em;
		transition: color 0.15s;
	}

	.terms-link:hover { color: #ffffff; }

	.footer {
		margin-top: 64px;
		padding-top: 24px;
		border-top: 1px solid rgba(255,255,255,0.15);
		font-size: 11px;
		color: rgba(255,255,255,0.55);
	}
	.footer p { margin: 6px 0; }
	.footer a {
		color: rgba(255,255,255,0.75);
		text-decoration: underline;
		text-decoration-thickness: 1px;
		text-underline-offset: 3px;
	}
	.footer a:hover { color: #ffffff; }
	.affil { font-style: italic; }

	:global(body) { background: #0a0a0a; }

	/* ═════ Print ═════ */
	@media print {
		:global(html), :global(body) {
			background: #ffffff !important;
			color: #000000 !important;
			overflow: visible !important;
		}
		@page {
			size: A4;
			margin: 18mm 16mm 22mm 16mm;
		}
		.no-print { display: none !important; }
		.print-only { display: block !important; }
		.content {
			max-width: none;
			margin: 0;
			padding: 0;
		}
		.print-brand {
			display: block !important;
			font-family: 'JetBrains Mono', ui-monospace, monospace;
			font-size: 8pt;
			color: #000000;
			letter-spacing: 0.05em;
			padding-bottom: 6pt;
			margin-bottom: 16pt;
			border-bottom: 0.5pt solid #000000;
		}
		.page {
			position: static;
			inset: auto;
			overflow: visible;
			max-width: none;
			margin: 0;
			padding: 0;
			color: #000000;
			background: #ffffff;
			font-family: 'JetBrains Mono', ui-monospace, monospace;
			font-size: 9.5pt;
			line-height: 1.55;
			z-index: auto;
		}
		.hdr { margin-bottom: 18pt; }
		.kicker {
			color: #000000;
			font-size: 7.5pt;
			letter-spacing: 0.12em;
			margin-bottom: 4pt;
		}
		.title {
			color: #000000;
			font-size: 26pt;
			line-height: 1.05;
			margin-bottom: 8pt;
		}
		.subtitle { color: #000000; font-size: 10pt; }
		.section { margin: 14pt 0; page-break-inside: avoid; }
		.section h2 {
			color: #000000;
			font-size: 10pt;
			border-bottom: 0.5pt solid #000000;
			padding-bottom: 3pt;
			margin-bottom: 8pt;
			letter-spacing: 0.1em;
		}
		.section p { color: #000000; }
		.section p strong { color: #000000; }
		.section a { color: #000000; }
		.list li { color: #000000; }
		.list li::before { color: #000000; }
		.list li strong { color: #000000; }
		.note { color: #000000; font-size: 8.5pt; }
		.section a[href^="http"]::after,
		.footer a[href^="http"]::after {
			content: " (" attr(href) ")";
			font-size: 7.5pt;
			color: #000000;
		}
		.footer {
			border-top: 0.5pt solid #000000;
			color: #000000;
			font-size: 7.5pt;
			margin-top: 24pt;
			padding-top: 8pt;
		}
		.footer a { color: #000000; }
		.footer .generated { margin-top: 6pt; font-style: italic; color: #000000; }
	}
</style>
