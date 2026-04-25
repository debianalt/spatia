<script lang="ts">
	import { goto } from '$app/navigation';
	import { terms } from '$lib/stores/terms.svelte';

	const today = new Date().toLocaleDateString('es-AR', {
		year: 'numeric',
		month: 'long',
		day: 'numeric',
	});

	function acceptAndEnter() {
		terms.accept();
		goto('/');
	}
</script>

<svelte:head>
	<title>Términos y condiciones — nealab</title>
	<meta name="description" content="Términos y condiciones de uso de nealab, plataforma de inteligencia geoespacial abierta. Exclusión de garantías, limitación de responsabilidad, ley aplicable." />
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="page">
	<div class="content">
		<div class="print-brand">nealab · términos y condiciones · spatia.ar</div>

		<header class="hdr">
			<div class="hdr-actions no-print">
				<a class="back-link" href="/">&larr; Volver al mapa</a>
			</div>
			<div class="kicker">Términos y condiciones de uso · nealab / spatia.ar</div>
			<h1 class="title">Términos y condiciones</h1>
			<p class="subtitle">
				Última actualización: mayo de 2026. Al usar nealab aceptás estos términos en su totalidad.
				Si no los aceptás, no uses la plataforma.
			</p>
		</header>

		<section class="section">
			<h2>1. Aceptación</h2>
			<p>
				El uso de nealab y de cualquier análisis, dato o visualización disponible en
				<strong>spatia.ar</strong> implica la aceptación plena e incondicional de estos términos y
				condiciones. Esta aceptación se produce en el momento en que el usuario accede a la
				plataforma y confirma haber leído y comprendido las condiciones aquí establecidas.
			</p>
			<p>
				Si usás nealab en nombre de una organización, institución o empresa, aceptás estos términos
				en nombre de esa entidad y declarás tener autoridad para hacerlo.
			</p>
		</section>

		<section class="section">
			<h2>2. Naturaleza del servicio</h2>
			<p>
				nealab es una <strong>herramienta de análisis geoespacial académico</strong> de acceso
				abierto, desarrollada en el marco de un proyecto de investigación financiado por el
				Consejo Nacional de Investigaciones Científicas y Técnicas (CONICET). Integra datos
				públicos de fuentes declaradas para generar visualizaciones e indicadores sobre el
				territorio de la provincia de Misiones y regiones circundantes.
			</p>
			<p>
				nealab <strong>no es</strong> un sistema de recomendación, un sistema de certificación,
				un peritaje técnico ni una consultoría profesional de ningún tipo. Sus análisis son
				síntesis cuantitativas de variables observables desde percepción remota, censos y fuentes
				administrativas, y deben entenderse como <strong>hipótesis a contrastar</strong>, nunca
				como verdades a aplicar directamente.
			</p>
		</section>

		<section class="section">
			<h2>3. Exclusión de garantías</h2>
			<p>
				La plataforma y toda la información que contiene se proveen <strong>tal cual (as-is)</strong>,
				sin garantías de ningún tipo, expresas ni implícitas, incluyendo pero no limitado a:
			</p>
			<ul class="list">
				<li>Exactitud o precisión de los datos</li>
				<li>Completitud o ausencia de errores</li>
				<li>Actualización o vigencia de la información</li>
				<li>Idoneidad para un propósito particular</li>
				<li>Ausencia de interrupciones o errores técnicos</li>
			</ul>
			<p>
				Los datos satelitales, censales y administrativos que integra nealab pueden contener
				errores, desfasajes temporales o limitaciones metodológicas documentadas en la ficha
				técnica de cada capa. Es responsabilidad del usuario verificar la adecuación de esa
				información para el uso que pretende darle.
			</p>
		</section>

		<section class="section">
			<h2>4. Limitación de responsabilidad</h2>
			<p>
				En la máxima medida permitida por la legislación aplicable, <strong>Raimundo Elias Gomez,
				el Consejo Nacional de Investigaciones Científicas y Técnicas (CONICET) y la Universidad
				Nacional de Misiones (UNaM)</strong> no serán responsables por daños de ningún tipo
				derivados del uso o la imposibilidad de uso de nealab, incluyendo pero no limitado a:
			</p>
			<ul class="list">
				<li>Daños directos, indirectos, incidentales, especiales o consecuentes</li>
				<li>Pérdidas económicas, pérdida de ganancias o de oportunidades de negocio</li>
				<li>Decisiones de inversión, gestión o política pública basadas en los análisis</li>
				<li>Consecuencias jurídicas, regulatorias o comerciales de cualquier índole</li>
				<li>Pérdida o corrupción de datos</li>
			</ul>
			<p>
				Esta limitación aplica independientemente de que los daños fueran previsibles o de que
				se hubiera advertido sobre su posibilidad.
			</p>
		</section>

		<section class="section">
			<h2>5. Marco institucional</h2>
			<p>
				CONICET y la UNaM (Facultad de Humanidades y Ciencias Sociales) son el <strong>marco
				académico e institucional</strong> de la investigación que dio origen a nealab. No son
				proveedores del servicio en sentido comercial, no avalan los análisis como documentos
				oficiales de ninguna institución pública o privada, y no asumen responsabilidad por
				el uso que terceros hagan de la información disponible en la plataforma.
			</p>
			<p>
				La mención de CONICET y UNaM en esta plataforma refleja el origen académico del
				desarrollo, no un aval institucional sobre la exactitud, completitud o idoneidad de
				ningún análisis particular.
			</p>
		</section>

		<section class="section">
			<h2>6. Uso permitido</h2>
			<p>nealab puede usarse libremente para:</p>
			<ul class="list">
				<li>Consulta, exploración y visualización de datos geoespaciales públicos</li>
				<li>Investigación académica y producción científica</li>
				<li>Educación, docencia y ciencia ciudadana</li>
				<li>Diagnósticos no vinculantes como insumo de deliberación o planificación</li>
				<li>Generación de hipótesis que serán contrastadas con fuentes primarias y trabajo de campo</li>
			</ul>
			<p>
				El uso en decisiones con consecuencias jurídicas, económicas, territoriales o de política
				pública requiere <strong>validación independiente</strong> por profesionales habilitados
				y trabajo situado en campo.
			</p>
		</section>

		<section class="section">
			<h2>7. Uso prohibido</h2>
			<p>Está prohibido:</p>
			<ul class="list">
				<li>
					Presentar los análisis de nealab como certificaciones técnicas, peritajes, informes
					oficiales o documentos con valor jurídico sin indicar explícitamente su naturaleza
					indicativa y sus limitaciones metodológicas.
				</li>
				<li>
					Usar nealab como única fuente de due-diligence en contextos regulatorios que exigen
					certificación profesional (incluido pero no limitado al cumplimiento EUDR, evaluaciones
					de impacto ambiental o tasaciones).
				</li>
				<li>
					Reproducir o redistribuir los análisis de nealab atribuyéndoles una precisión, autoridad
					o vigencia que el servicio no garantiza.
				</li>
			</ul>
		</section>

		<section class="section">
			<h2>8. Propiedad intelectual</h2>
			<p>
				Los datos integrados por nealab provienen de fuentes públicas declaradas en la ficha
				técnica de cada capa (INDEC, IGN, JRC, Hansen GFC, MODIS, MapBiomas, OSM, entre otras)
				y se usan conforme a sus licencias originales. El pipeline de procesamiento, el código
				de la plataforma y las visualizaciones son de autoría de Raimundo Elias Gomez y pueden
				citarse según la referencia indicada en
				<a href="/servicios">spatia.ar/servicios</a>.
			</p>
		</section>

		<section class="section">
			<h2>9. Privacidad y datos</h2>
			<p>
				nealab no recopila datos personales de los usuarios. El acceso a la plataforma puede
				generar registros técnicos estándar (dirección IP, timestamp, ruta de acceso) utilizados
				exclusivamente para monitoreo de infraestructura y detección de errores. Estos registros
				no se comparten con terceros ni se usan para identificar personas.
			</p>
			<p>
				La aceptación de estos términos se registra localmente en el navegador del usuario
				(localStorage) y no se transmite a ningún servidor.
			</p>
		</section>

		<section class="section">
			<h2>10. Modificaciones</h2>
			<p>
				Estos términos pueden modificarse. La versión vigente está siempre disponible en
				<strong>spatia.ar/terminos</strong>. Cambios sustanciales en las condiciones de
				responsabilidad o uso requerirán nueva aceptación explícita, que la plataforma
				solicitará automáticamente al usuario.
			</p>
		</section>

		<section class="section">
			<h2>11. Ley aplicable y jurisdicción</h2>
			<p>
				Estos términos y condiciones se rigen por las leyes de la <strong>República Argentina</strong>,
				en particular el Código Civil y Comercial de la Nación (Ley 26.994 y sus modificatorias).
				Para cualquier controversia derivada del uso de nealab, las partes se someten a la
				jurisdicción de los <strong>tribunales ordinarios de la ciudad de Posadas, provincia
				de Misiones</strong>, con renuncia expresa a cualquier otro fuero que pudiera corresponder.
			</p>
		</section>

		<div class="accept-block no-print">
			<p class="accept-text">
				Al hacer clic en el botón de abajo confirmás que leíste y aceptás estos términos y
				condiciones en su totalidad.
			</p>
			<button class="btn-accept" onclick={acceptAndEnter}>
				Acepto los términos — entrar a nealab
			</button>
		</div>

		<footer class="footer">
			<p>spatia.ar/terminos · Versión mayo 2026</p>
			<p class="affil">CONICET · FHyCS-UNaM</p>
			<p class="print-only generated">Documento generado el {today} desde spatia.ar/terminos</p>
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
