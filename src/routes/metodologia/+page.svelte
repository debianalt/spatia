<script lang="ts">
	import { i18n } from '$lib/stores/i18n.svelte';
	import LangSwitcher from '$lib/components/LangSwitcher.svelte';

	let { data } = $props();

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
	<title>Metodología e indicadores · nealab</title>
	<meta name="description" content="Metodología de los indicadores geoespaciales de nealab — fuentes, variables y métodos de cada análisis." />
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
	<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet" />
</svelte:head>

<div class="page">
	<div class="print-brand">
		<strong>nealab</strong> · inteligencia geoespacial abierta · spatia.ar
	</div>

	<header class="hdr">
		<div class="hdr-actions no-print">
			<a class="back-link" href="/">{i18n.t('nav.backToMap')}</a>
			<div class="hdr-right">
				<LangSwitcher variant="mono" />
				<button class="print-btn" onclick={handlePrint} type="button">
					{i18n.t('nav.printSave')}
				</button>
			</div>
		</div>
		<h1 class="title">{i18n.t('page.metodologia.title')}</h1>
		<div class="kicker">{i18n.t('page.metodologia.kicker')}</div>
		<p class="desc">
			{i18n.t('page.metodologia.desc')}
		</p>
	</header>

	{#each data.byLens as group}
		<section class="lens-section">
			<h2 class="lens-title" style="color: {group.color}">{group.label}</h2>
			<ul class="analysis-list">
				{#each group.analyses as analysis}
					<li class="analysis-item">
						<a href="/metodologia/{analysis.id}" class="analysis-link">
							<span class="analysis-name">{i18n.t(analysis.titleKey)}</span>
							{#if analysis.descKey}
								<span class="analysis-desc">{i18n.t(analysis.descKey)}</span>
							{/if}
							<span class="analysis-arrow">{i18n.t('page.metodologia.arrowLink')}</span>
						</a>
					</li>
				{/each}
			</ul>
		</section>
	{/each}

	<footer class="footer">
		<p>
			Citación sugerida: Gomez, R. E. (2026). nealab: A Zero-Cost Platform for Subnational Territorial
			Intelligence (Version v2). Zenodo.
			<a href="https://doi.org/10.5281/zenodo.19543818">https://doi.org/10.5281/zenodo.19543818</a>
		</p>
		<p class="affil">CONICET · FHyCS-UNaM · Google Earth Engine Partner Tier</p>
		<p class="print-only generated">Documento generado el {today} desde spatia.ar/metodologia</p>
	</footer>
</div>

<style>
	.page {
		max-width: 720px;
		margin: 0 auto;
		padding: 32px 24px 64px;
		color: #e2e8f0;
		font-family: 'JetBrains Mono', 'SF Mono', Monaco, 'Cascadia Code', monospace;
		font-size: 14px;
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
	.hdr-right {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.back-link {
		display: inline-block;
		color: #94a3b8;
		font-size: 12px;
		text-decoration: none;
	}
	.back-link:hover { color: #e2e8f0; text-decoration: underline; }
	.print-btn {
		background: rgba(255,255,255,0.06);
		border: 1px solid #334155;
		border-radius: 6px;
		color: #94a3b8;
		font-size: 12px;
		font-weight: 600;
		padding: 6px 12px;
		cursor: pointer;
		font-family: inherit;
		transition: all 0.15s;
	}
	.print-btn:hover {
		background: rgba(255,255,255,0.1);
		border-color: #475569;
		color: #e2e8f0;
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
		font-size: 13px;
		margin: 0;
	}
	.lens-section { margin: 28px 0; }
	.lens-title {
		font-size: 11px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		margin: 0 0 12px;
		padding-bottom: 6px;
		border-bottom: 1px solid #1e293b;
	}
	.analysis-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.analysis-item { display: block; }
	.analysis-link {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 10px 12px;
		background: rgba(255,255,255,0.03);
		border: 1px solid rgba(255,255,255,0.06);
		border-radius: 6px;
		text-decoration: none;
		transition: all 0.15s;
	}
	.analysis-link:hover {
		background: rgba(255,255,255,0.07);
		border-color: rgba(255,255,255,0.15);
	}
	.analysis-name {
		font-size: 13px;
		font-weight: 600;
		color: #f1f5f9;
	}
	.analysis-desc {
		font-size: 11px;
		color: #64748b;
		line-height: 1.4;
	}
	.analysis-arrow {
		font-size: 10px;
		color: #475569;
		margin-top: 2px;
		transition: color 0.15s;
	}
	.analysis-link:hover .analysis-arrow { color: #94a3b8; }
	.footer {
		margin-top: 48px;
		padding-top: 20px;
		border-top: 1px solid #1e293b;
		font-size: 12px;
		color: #64748b;
	}
	.footer p { margin: 4px 0; }
	.footer a { color: #94a3b8; text-decoration: underline; }
	.affil { font-style: italic; }

	:global(html), :global(body) { overflow: auto !important; background: #0a0e1a; }

	/* ═════ Print ═════ */
	@media print {
		:global(html), :global(body) {
			background: #ffffff !important;
			color: #1a1a1a !important;
		}
		@page { size: A4; margin: 18mm 16mm 22mm 16mm; }
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
		.title { color: #0f172a; font-size: 22pt; line-height: 1.15; margin-bottom: 4pt; }
		.kicker { color: #64748b; font-size: 8pt; margin-bottom: 8pt; }
		.desc { color: #334155; font-size: 10pt; }
		.lens-section { margin: 14pt 0; page-break-inside: avoid; }
		.lens-title { font-size: 9pt; border-bottom: 0.5pt solid #cbd5e1; padding-bottom: 3pt; margin-bottom: 8pt; }
		.analysis-link {
			background: #f8fafc;
			border: 0.25pt solid #e2e8f0;
			border-radius: 3pt;
		}
		.analysis-name { color: #0f172a; font-size: 10pt; }
		.analysis-desc { color: #475569; font-size: 9pt; }
		.analysis-arrow { display: none; }
		.footer {
			border-top: 0.5pt solid #cbd5e1;
			color: #475569;
			font-size: 8pt;
			margin-top: 28pt;
			padding-top: 8pt;
		}
		.footer a { color: #334155; }
		.footer .generated { margin-top: 6pt; font-style: italic; color: #64748b; }
	}
</style>
