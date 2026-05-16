<script lang="ts">
	import { goto } from '$app/navigation';
	import { terms } from '$lib/stores/terms.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';
	import LangSwitcher from '$lib/components/LangSwitcher.svelte';
	import { TERMINOS } from '$lib/content/terminos';

	const today = new Date().toLocaleDateString('es-AR', {
		year: 'numeric',
		month: 'long',
		day: 'numeric',
	});

	const c = $derived(TERMINOS[i18n.locale] ?? TERMINOS.es);

	function acceptAndEnter() {
		terms.accept();
		goto('/');
	}
</script>

<svelte:head>
	<title>{c.pageTitle}</title>
	<meta name="description" content={c.metaDesc} />
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="page">
	<div class="content">
		<div class="print-brand">{c.printBrand}</div>

		<header class="hdr">
			<div class="hdr-actions no-print">
				<a class="back-link" href="/">{i18n.t('nav.backToMap')}</a>
				<LangSwitcher variant="mono" />
			</div>
			<div class="kicker">{c.kicker}</div>
			<h1 class="title">{c.title}</h1>
			<p class="subtitle">{c.subtitle}</p>
		</header>

		<section class="section">
			<h2>{c.s1Title}</h2>
			<p>{@html c.s1P1}</p>
			<p>{c.s1P2}</p>
		</section>

		<section class="section">
			<h2>{c.s2Title}</h2>
			<p>{@html c.s2P1}</p>
			<p>{@html c.s2P2}</p>
		</section>

		<section class="section">
			<h2>{c.s3Title}</h2>
			<p>{@html c.s3Intro}</p>
			<ul class="list">
				{#each c.s3List as item}
					<li>{item}</li>
				{/each}
			</ul>
			<p>{c.s3P2}</p>
		</section>

		<section class="section">
			<h2>{c.s4Title}</h2>
			<p>{@html c.s4Intro}</p>
			<ul class="list">
				{#each c.s4List as item}
					<li>{item}</li>
				{/each}
			</ul>
			<p>{c.s4P2}</p>
		</section>

		<section class="section">
			<h2>{c.s5Title}</h2>
			<p>{@html c.s5P1}</p>
			<p>{c.s5P2}</p>
		</section>

		<section class="section">
			<h2>{c.s6Title}</h2>
			<p>{c.s6Intro}</p>
			<ul class="list">
				{#each c.s6List as item}
					<li>{item}</li>
				{/each}
			</ul>
			<p>{@html c.s6P2}</p>
		</section>

		<section class="section">
			<h2>{c.s7Title}</h2>
			<p>{c.s7Intro}</p>
			<ul class="list">
				{#each c.s7List as item}
					<li>{item}</li>
				{/each}
			</ul>
		</section>

		<section class="section">
			<h2>{c.s8Title}</h2>
			<p>{@html c.s8P1}</p>
		</section>

		<section class="section">
			<h2>{c.s9Title}</h2>
			<p>{c.s9P1}</p>
			<p>{c.s9P2}</p>
		</section>

		<section class="section">
			<h2>{c.s10Title}</h2>
			<p>{@html c.s10P1}</p>
		</section>

		<section class="section">
			<h2>{c.s11Title}</h2>
			<p>{@html c.s11P1}</p>
		</section>

		<div class="accept-block no-print">
			<p class="accept-text">{c.acceptText}</p>
			<button class="btn-accept" onclick={acceptAndEnter}>
				{c.acceptBtn}
			</button>
		</div>

		<footer class="footer">
			<p>{c.footerVersion}</p>
			<p class="affil">{c.affil}</p>
			<p class="print-only generated">{c.printGenerated.replace('{date}', today)}</p>
		</footer>
	</div>
</div>

<style>
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

	.back-link {
		display: inline-block;
		color: rgba(255, 255, 255, 0.55);
		font-size: 11px;
		text-decoration: none;
		letter-spacing: 0.02em;
	}

	.back-link:hover { color: #ffffff; }

	.kicker {
		font-size: 10px;
		color: rgba(255, 255, 255, 0.45);
		text-transform: uppercase;
		letter-spacing: 0.12em;
		margin-bottom: 10px;
	}

	.title {
		font-size: 36px;
		font-weight: 700;
		color: #ffffff;
		margin: 0 0 14px;
		line-height: 1.05;
	}

	.subtitle {
		color: rgba(255, 255, 255, 0.65);
		font-size: 12px;
		margin: 0;
		font-style: italic;
	}

	.section { margin: 36px 0; }

	.section h2 {
		font-size: 11px;
		font-weight: 700;
		color: #ffffff;
		text-transform: uppercase;
		letter-spacing: 0.12em;
		margin: 0 0 14px;
		padding-bottom: 8px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.15);
	}

	.section p {
		color: rgba(255, 255, 255, 0.8);
		margin: 0 0 12px;
		text-align: justify;
		text-justify: inter-word;
		hyphens: auto;
	}

	.section p strong { color: #ffffff; font-weight: 700; }

	.section a {
		color: #ffffff;
		text-decoration: underline;
		text-decoration-thickness: 1px;
		text-underline-offset: 3px;
	}

	.list {
		list-style: none;
		padding: 0;
		margin: 0 0 12px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.list li {
		color: rgba(255, 255, 255, 0.75);
		padding-left: 16px;
		position: relative;
		font-size: 12px;
		text-align: justify;
		text-justify: inter-word;
		hyphens: auto;
	}

	.list li::before {
		content: '—';
		position: absolute;
		left: 0;
		color: rgba(255, 255, 255, 0.35);
	}

	.accept-block {
		margin: 48px 0 0;
		padding: 28px;
		border: 1px solid rgba(255, 255, 255, 0.2);
		background: rgba(255, 255, 255, 0.03);
	}

	.accept-text {
		color: rgba(255, 255, 255, 0.7);
		font-size: 12px;
		margin: 0 0 16px;
		text-align: left;
	}

	.btn-accept {
		background: #ffffff;
		color: #000000;
		border: none;
		padding: 12px 24px;
		font-family: inherit;
		font-size: 12px;
		font-weight: 700;
		letter-spacing: 0.04em;
		cursor: pointer;
		transition: opacity 0.15s;
		width: 100%;
	}

	.btn-accept:hover { opacity: 0.85; }

	.footer {
		margin-top: 64px;
		padding-top: 24px;
		border-top: 1px solid rgba(255, 255, 255, 0.15);
		font-size: 11px;
		color: rgba(255, 255, 255, 0.45);
	}

	.footer p { margin: 4px 0; }
	.affil { font-style: italic; }

	:global(body) { background: #0a0a0a; }

	@media print {
		:global(html), :global(body) {
			background: #ffffff !important;
			color: #000000 !important;
			overflow: visible !important;
		}
		.no-print { display: none !important; }
		.print-only { display: block !important; }
		.print-brand {
			display: block !important;
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
			color: #000000;
			background: #ffffff;
			font-size: 9.5pt;
		}
		.content { max-width: none; margin: 0; padding: 0; }
		.section h2 { color: #000000; border-bottom: 0.5pt solid #000000; font-size: 9pt; }
		.section p { color: #000000; }
		.section p strong { color: #000000; }
		.list li { color: #000000; }
		.footer { border-top: 0.5pt solid #000000; color: #000000; font-size: 7.5pt; }
		.footer .generated { margin-top: 6pt; font-style: italic; }
	}
</style>
