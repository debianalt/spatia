<script lang="ts">
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
	<title>nealab — inteligencia geoespacial abierta para el NEA argentino</title>
	<meta
		name="description"
		content="nealab es una plataforma pública de inteligencia geoespacial abierta centrada especialmente en el Noreste Argentino. Reúne más de veinte capas de análisis para gestión pública, investigación, cooperación internacional y ciencia ciudadana."
	/>
	<meta property="og:title" content="nealab — servicios de inteligencia geoespacial" />
	<meta
		property="og:description"
		content="Plataforma pública de inteligencia geoespacial abierta. Análisis reproducible, acceso abierto, ciencia ciudadana. Hospedado en spatia.ar."
	/>
</svelte:head>

<div class="page">
	<div class="content">
	<div class="print-brand">
		nealab · inteligencia geoespacial abierta · spatia.ar
	</div>

	<header class="hdr">
		<div class="hdr-actions no-print">
			<a class="back-link" href="/">&larr; Volver al mapa</a>
			<button class="print-btn" type="button" onclick={handlePrint}>
				↓ Imprimir / Guardar PDF
			</button>
		</div>
		<div class="kicker">Inteligencia geoespacial abierta · NEA Argentino</div>
		<h1 class="title">nealab</h1>
		<p class="subtitle">
			Plataforma pública de análisis geoespacial centrada especialmente en el NEA argentino.
			Datos, métodos y código abiertos; pensada para investigación, gestión pública, cooperación
			internacional y ciencia ciudadana. Hospedado en <a href="/">spatia.ar</a>.
		</p>
	</header>

	<section class="section">
		<h2>Qué es nealab</h2>
		<p>
			<strong>nealab</strong> es una plataforma de <strong>inteligencia geoespacial abierta</strong>
			desarrollada en el marco del <strong>CONICET</strong>, la <strong>UNaM (FHyCS)</strong> y el
			partenariado académico con el <strong>Google Earth Engine Research &amp; Innovation Program</strong>.
			Reúne más de veinte capas de análisis sobre la provincia de Misiones —y parcialmente sobre el
			NEA argentino— para explorar de forma interactiva el estado ecológico, social, productivo y de
			infraestructura de la ecorregión.
		</p>
		<p>
			No es un sistema de recomendación, ni un rankeador automático, ni un sustituto del juicio de
			quienes habitan y conocen el lugar. Es una herramienta para preguntar mejor: para visualizar
			capas de información pública, contrastarlas entre sí, y acompañar la conversación con
			evidencia cuantitativa reproducible.
		</p>
	</section>

	<section class="section">
		<h2>Principios</h2>
		<ul class="list">
			<li>
				<strong>Acceso abierto.</strong> Todos los datos que integra la plataforma provienen de
				fuentes públicas declaradas en la ficha metodológica de cada capa (INDEC, OSM, IGN,
				MapBiomas, Catastro, JRC, Hansen GFC, MODIS, entre otras). Cualquier persona puede
				consultar esas fuentes originales y reproducir los análisis siguiendo el pipeline
				documentado.
			</li>
			<li>
				<strong>Trazabilidad metodológica.</strong> Cada capa tiene su ficha técnica con fuentes,
				resolución, pipeline de procesamiento, supuestos y limitaciones conocidas. Las fichas están
				linkeadas desde el panel lateral de cada análisis.
			</li>
			<li>
				<strong>Reproducibilidad.</strong> El pipeline completo vive en un repositorio público y
				puede volver a ejecutarse desde cero sobre otra jurisdicción cambiando sólo el bounding
				box. Sin dependencias propietarias.
			</li>
			<li>
				<strong>Ciencia ciudadana.</strong> La plataforma es un insumo para que comunidades,
				organizaciones y municipios puedan interrogar su propia geografía con las mismas
				herramientas que usan los organismos técnicos internacionales.
			</li>
			<li>
				<strong>Interoperabilidad.</strong> Cualquier vista o zona puede exportarse a CSV o
				GeoJSON. Se integra sin fricción con flujos de trabajo existentes en gobierno, academia
				y consultoría.
			</li>
		</ul>
	</section>

	<section class="section">
		<h2>Qué ofrece</h2>
		<p>
			nealab organiza sus análisis en cuatro grandes preguntas o "lentes", que pueden combinarse
			entre sí:
		</p>
		<ul class="list">
			<li>
				<strong>Habitar.</strong>
				Riesgo de inundación (JRC Global Surface Water + Sentinel-1 SAR), carencia de servicios
				básicos (censo 2022), calidad edilicia, accesibilidad a salud y educación, catastro
				parcelario.
			</li>
			<li>
				<strong>Producir.</strong>
				Aptitud edafoclimática agrícola, aptitud forestal comercial, salud de la vegetación, stock
				de carbono y balance de emisiones, dinámica de deforestación, aire (PM2.5) y cumplimiento
				EUDR para commodities.
			</li>
			<li>
				<strong>Servir.</strong>
				Capital educativo, flujo del sistema educativo, acceso a salud, aislamiento geoespacial y
				perfil sociodemográfico, con crosswalk dasimétrico a hexágonos H3.
			</li>
			<li>
				<strong>Invertir.</strong>
				Valor posicional, presión de cambio urbano, confort climático, infraestructura eléctrica
				y clasificación de tipos geoespaciales para informar decisiones de localización.
			</li>
		</ul>
		<p>
			Todas las capas se proyectan sobre una grilla <strong>H3 resolución 9</strong> uniforme
			(~0.1 km² por hexágono, ~320 000 hexágonos en Misiones), con crosswalks documentados a radios
			censales y parcelas catastrales para análisis cruzados.
		</p>
	</section>

	<section class="section">
		<h2>Para quién</h2>
		<ul class="list">
			<li>
				<strong>Organismos multilaterales</strong> (PNUD, BID, Banco Mundial, FAO, CEPAL) que
				necesiten diagnósticos geoespaciales rápidos y reproducibles sobre el NEA argentino, con
				datos curados y pipelines auditables.
			</li>
			<li>
				<strong>Gobiernos provinciales y municipales</strong> que busquen visualizar
				simultáneamente indicadores ambientales, sociales y de infraestructura para planificación
				sectorial o negociación con terceros.
			</li>
			<li>
				<strong>Investigación académica</strong> con necesidad de datos curados listos para
				análisis, especialmente en ecología, geografía, economía ecológica, ciencias sociales y
				salud pública.
			</li>
			<li>
				<strong>Organizaciones de la sociedad civil</strong> que quieran fundamentar denuncias,
				propuestas de política o campañas de incidencia con evidencia cuantitativa rigurosa.
			</li>
			<li>
				<strong>Consultoras ambientales, agrícolas y forestales</strong> que necesiten
				due-diligence geoespacial verificable, particularmente para cumplimiento EUDR en
				exportaciones hacia la Unión Europea.
			</li>
			<li>
				<strong>Docentes y estudiantes</strong> que quieran introducirse al análisis geoespacial
				con una plataforma en español, con metodologías explicadas y datos reales sobre el NEA.
			</li>
		</ul>
	</section>

	<section class="section">
		<h2>Servicios de transferencia disponibles</h2>
		<p>
			A través de la figura de <strong>Servicios Tecnológicos de Alto Nivel (STAN)</strong> del
			CONICET, los siguientes servicios pueden contratarse formalmente con facturación
			institucional a través del CCT Nordeste:
		</p>
		<ul class="list">
			<li>
				<strong>Asesoría geoespacial aplicada.</strong> Acompañamiento técnico a proyectos
				específicos de diagnóstico, planificación, evaluación de impacto o diseño de políticas.
			</li>
			<li>
				<strong>Extensión del pipeline a otras jurisdicciones.</strong> Replicación del stack
				completo sobre nuevas provincias, regiones o países del cono sur, con las mismas
				garantías metodológicas.
			</li>
			<li>
				<strong>Informes temáticos por departamento o zona.</strong> Fichas sintéticas que integran
				todas las capas relevantes sobre un recorte espacial solicitado, con interpretación
				contextualizada.
			</li>
			<li>
				<strong>Análisis de cumplimiento EUDR.</strong> Due diligence geoespacial sobre áreas de
				origen de commodities (soja, carne, madera, café, cacao, caucho, aceite de palma) con la
				Regulación UE 2023/1115, combinando Hansen GFC, MODIS MCD64A1 y geometrías parcelarias.
			</li>
			<li>
				<strong>Integración con sistemas existentes.</strong> Conexión de nealab con SIGs
				institucionales, tableros BI, APIs de terceros y flujos internos mediante DuckDB, Parquet
				o GeoJSON.
			</li>
			<li>
				<strong>Capacitación técnica.</strong> Talleres sobre el stack abierto que usa nealab
				(Google Earth Engine, H3, DuckDB, MapLibre) orientados a equipos técnicos de gobierno,
				academia y sociedad civil.
			</li>
		</ul>
		<p class="note">
			La formalización se realiza vía contrato de transferencia del CONICET, con tasa institucional
			estándar. La productividad generada se distribuye entre investigador/a, unidad ejecutora y
			CONICET según normativa vigente.
		</p>
	</section>

	<section class="section">
		<h2>Sobre los límites de este análisis</h2>
		<p>
			Esta sección es importante y pedimos que se lea con atención antes de utilizar nealab en
			cualquier decisión con consecuencias reales.
		</p>
		<p>
			<strong>nealab es una herramienta analítica, no prescriptiva.</strong> Ningún análisis en
			esta plataforma constituye una recomendación de acción. Los scores, tipologías y rankings
			son síntesis cuantitativas de variables observables desde percepción remota, censo y fuentes
			administrativas. No sustituyen el juicio experto, la deliberación democrática ni la
			responsabilidad política de quien decide.
		</p>
		<p>
			<strong>Ningún análisis geoespacial puede considerarse completo sin trabajo de campo en
			terreno.</strong> La mirada satelital capta estructura y promedios; rara vez capta
			significado, historia o proceso. Las capas de nealab necesitan ser contrastadas con las
			fuentes primarias que sólo pueden aportar <strong>quienes habitan el lugar</strong>:
			residentes, comunidades originarias, pobladores rurales, productores familiares, técnicos
			locales, organizaciones sociales, funcionarios de territorio.
		</p>
		<p>
			Esta participación no es un complemento ornamental del análisis —es condición de validez.
			Una zona clasificada como "alta aptitud agrícola" puede ser, para quienes la habitan, un
			sitio de memoria, un área de protección comunitaria o un territorio en disputa. Una zona con
			"bajo riesgo de inundación" según la serie histórica puede estar atravesando cambios
			recientes que todavía no llegaron a los datos. Estas diferencias no son ruido en el modelo:
			son la información que el modelo no puede ver.
		</p>
		<p>
			Por eso <strong>cada una de las clasificaciones disponibles en nealab debe entenderse como
			una hipótesis a contrastar, nunca como una verdad a aplicar.</strong> Usar esta plataforma
			con responsabilidad implica leer la ficha metodológica de cada capa, reconocer sus
			limitaciones, y completarla siempre con trabajo situado y escucha activa.
		</p>
		<p class="note">
			Quien utilice nealab en un contexto de gestión, inversión, investigación o política pública
			asume la responsabilidad de ese uso. La plataforma se ofrece de buena fe como insumo y
			herramienta; no como autoridad.
		</p>
	</section>

	<section class="section">
		<h2>Stack técnico y abierto</h2>
		<ul class="list">
			<li><strong>Frontend:</strong> SvelteKit 5 + MapLibre GL 5 + TailwindCSS 4.</li>
			<li><strong>Datos:</strong> DuckDB-WASM sobre Parquet en Cloudflare R2 (CORS abierto).</li>
			<li>
				<strong>Grid:</strong> H3 resolución 9 (uniforme, ~0.1 km² por hexágono). Crosswalks a
				radios censales (dasimétricos) y parcelas catastrales.
			</li>
			<li>
				<strong>Pipeline:</strong> Google Earth Engine (Partner Tier académico) + rasterio +
				scoring PCA + k-means. Python como única dependencia.
			</li>
			<li><strong>Despliegue:</strong> Cloudflare Pages (static + edge), sin servidor propietario.</li>
			<li>
				<strong>Licencias:</strong> Código abierto (MIT). Datos sujetos a las licencias de sus
				fuentes originales (mayoritariamente CC BY 4.0 o de dominio público).
			</li>
		</ul>
	</section>

	<section class="section">
		<h2>Fuentes y colaboraciones</h2>
		<p>
			nealab integra datos públicos de INDEC (Censo 2022), IGN, Dirección General de Catastro de
			Misiones, JRC Global Surface Water, Hansen Global Forest Change, MODIS, MapBiomas, CHIRPS,
			ERA5, VIIRS, GHSL, SoilGrids, Sentinel, Overture Maps Foundation, OpenStreetMap, Meta/WRI
			Canopy Height, Dalhousie University ACAG PM2.5, EMSA (Secretaría de Energía) y Oxford MAP,
			entre otras. El procesamiento se realiza sobre Google Earth Engine como plataforma de
			cómputo, con acceso académico al Research &amp; Innovation Program.
		</p>
		<p>
			El desarrollo es parte del programa de investigación del CONICET en economía ecológica y
			análisis geoespacial aplicado al Noreste Argentino.
		</p>
	</section>

	<section class="section">
		<h2>Contacto</h2>
		<p>
			<strong>Raimundo Quenardelle</strong><br />
			Investigador CONICET · Facultad de Humanidades y Ciencias Sociales, UNaM<br />
			<a href="mailto:contacto@spatia.ar">contacto@spatia.ar</a> ·
			<a href="https://spatia.ar">spatia.ar</a>
		</p>
		<p class="note">
			Para consultas de transferencia formal (contratos STAN, facturación institucional,
			capacitaciones), se gestionan a través de la Oficina de Vinculación Tecnológica del CCT
			Nordeste del CONICET.
		</p>
	</section>

	<footer class="footer">
		<p>
			Citación sugerida: Quenardelle, R. (2026). nealab — inteligencia geoespacial abierta para el
			NEA argentino. <a href="https://spatia.ar">spatia.ar</a>
		</p>
		<p class="affil">CONICET · FHyCS-UNaM · Google Earth Engine R&amp;I Program</p>
		<p class="print-only generated">
			Documento generado el {today} desde spatia.ar/servicios
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
	}
	.section p strong { color: #ffffff; font-weight: 700; }
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
	}
	.list li::before {
		content: '—';
		position: absolute;
		left: 0;
		color: rgba(255,255,255,0.4);
	}
	.list li strong { color: #ffffff; font-weight: 700; }

	.note {
		font-size: 12px;
		color: rgba(255,255,255,0.55);
		font-style: italic;
	}

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
