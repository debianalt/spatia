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
	<title>Servicios · Spatia — Inteligencia geoespacial abierta</title>
	<meta
		name="description"
		content="Spatia es una plataforma pública de inteligencia geoespacial abierta para la provincia de Misiones, Argentina. Reúne más de veinte capas de análisis sobre la selva paranaense para gestión pública, investigación, cooperación y participación ciudadana."
	/>
	<meta property="og:title" content="Spatia — Servicios de inteligencia geoespacial" />
	<meta
		property="og:description"
		content="Plataforma pública de inteligencia geoespacial abierta. Análisis territorial reproducible, acceso abierto, ciencia ciudadana."
	/>
</svelte:head>

<div class="page">
	<div class="print-brand">
		<strong>Spatia</strong> · Inteligencia geoespacial abierta · spatia.ar
	</div>

	<header class="hdr">
		<div class="hdr-actions no-print">
			<a class="back-link" href="/">&larr; Volver al mapa</a>
			<button class="print-btn" type="button" onclick={handlePrint}>
				↓ Imprimir / Guardar PDF
			</button>
		</div>
		<div class="kicker">Inteligencia geoespacial abierta · Misiones, Argentina</div>
		<h1 class="title">Spatia</h1>
		<p class="subtitle">
			Plataforma pública de análisis geoespacial para la selva paranaense. Datos, métodos y código
			abiertos; pensada para investigación, gestión pública, cooperación internacional y ciencia
			ciudadana.
		</p>
	</header>

	<section class="section">
		<h2>Qué es Spatia</h2>
		<p>
			Spatia es una plataforma de <strong>inteligencia geoespacial abierta</strong> desarrollada en
			el marco del <strong>CONICET</strong> y la <strong>UNaM (FHyCS)</strong>. Reúne más de veinte
			capas de análisis sobre la provincia de Misiones —y parcialmente sobre el NEA argentino— para
			explorar de forma interactiva el estado ecológico, social, productivo y de infraestructura de
			la ecorregión.
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
		<ul class="principles">
			<li>
				<strong>Acceso abierto.</strong> Todos los datos, algoritmos y metodologías son públicos.
				Los parquets están disponibles en Cloudflare R2 con CORS abierto; cualquier persona puede
				leerlos con QGIS, Python, R o DuckDB sin registración.
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
				<strong>Interoperabilidad.</strong> Cualquier vista o zona puede exportarse a CSV, GeoJSON
				o Parquet. Se integra sin fricción con flujos de trabajo existentes en gobierno, academia
				y consultoría.
			</li>
		</ul>
	</section>

	<section class="section">
		<h2>Qué ofrece</h2>
		<p>
			Spatia organiza sus análisis en cuatro grandes preguntas o "lentes", que pueden combinarse
			entre sí:
		</p>
		<ul class="lenses">
			<li>
				<span class="lens-name">Habitar.</span>
				Riesgo de inundación (JRC Global Surface Water + Sentinel-1 SAR), carencia de servicios
				básicos (censo 2022), calidad edilicia, accesibilidad a salud y educación, catastro
				parcelario.
			</li>
			<li>
				<span class="lens-name">Producir.</span>
				Aptitud edafoclimática agrícola, aptitud forestal comercial, salud de la vegetación, stock
				de carbono y balance de emisiones, dinámica de deforestación, aire (PM2.5) y cumplimiento
				EUDR para commodities.
			</li>
			<li>
				<span class="lens-name">Servir.</span>
				Capital educativo, flujo del sistema educativo, acceso a salud, aislamiento geoespacial y
				perfil sociodemográfico, con crosswalk dasimétrico a hexágonos H3.
			</li>
			<li>
				<span class="lens-name">Invertir.</span>
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
		<ul class="audiences">
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
		<ul class="services">
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
				<strong>Integración con sistemas existentes.</strong> Conexión de Spatia con SIGs
				institucionales, tableros BI, APIs de terceros y flujos internos mediante DuckDB, Parquet
				o GeoJSON.
			</li>
			<li>
				<strong>Capacitación técnica.</strong> Talleres sobre el stack abierto que usa Spatia
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

	<section class="section disclaimer">
		<h2>Sobre los límites de este análisis</h2>
		<p>
			Esta sección es importante y pedimos que se lea con atención antes de utilizar Spatia en
			cualquier decisión con consecuencias reales.
		</p>
		<p>
			<strong>Spatia es una herramienta analítica, no prescriptiva.</strong> Ningún análisis en
			esta plataforma constituye una recomendación de acción. Los scores, tipologías y rankings
			son síntesis cuantitativas de variables observables desde percepción remota, censo y fuentes
			administrativas. No sustituyen el juicio experto, la deliberación democrática ni la
			responsabilidad política de quien decide.
		</p>
		<p>
			<strong>Ningún análisis geoespacial puede considerarse completo sin trabajo de campo en
			terreno.</strong> La mirada satelital capta estructura y promedios; rara vez capta
			significado, historia o proceso. Las capas de Spatia necesitan ser contrastadas con las
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
			Por eso <strong>cada una de las clasificaciones disponibles en Spatia debe entenderse como
			una hipótesis a contrastar, nunca como una verdad a aplicar.</strong> Usar esta plataforma
			con responsabilidad implica leer la ficha metodológica de cada capa, reconocer sus
			limitaciones, y completarla siempre con trabajo situado y escucha activa.
		</p>
		<p class="note">
			Quien utilice Spatia en un contexto de gestión, inversión, investigación o política pública
			asume la responsabilidad de ese uso. La plataforma se ofrece de buena fe como insumo y
			herramienta; no como autoridad.
		</p>
	</section>

	<section class="section">
		<h2>Stack técnico y abierto</h2>
		<ul class="stack">
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
			Spatia integra datos públicos de INDEC (Censo 2022), IGN, Dirección General de Catastro de
			Misiones, Google Earth Engine (JRC, Hansen GFC, MODIS, MapBiomas, CHIRPS, ERA5, VIIRS, GHSL,
			SoilGrids, Sentinel), Overture Maps Foundation, OpenStreetMap, Meta/WRI Canopy Height,
			Dalhousie University ACAG PM2.5, EMSA (Secretaría de Energía) y Oxford MAP, entre otras.
		</p>
		<p>
			El desarrollo es parte del programa de investigación de CONICET en economía ecológica y
			análisis geoespacial aplicado a la selva paranaense, con acceso académico al Google Earth
			Engine Research &amp; Innovation Program.
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
			Citación sugerida: Quenardelle, R. (2026). Spatia — Inteligencia geoespacial abierta para
			Misiones. <a href="https://spatia.ar">spatia.ar</a>
		</p>
		<p class="affil">CONICET / FHyCS-UNaM · Plataforma de análisis geoespacial abierto</p>
		<p class="print-only generated">
			Documento generado el {today} desde spatia.ar/servicios
		</p>
	</footer>
</div>

<style>
	.page {
		max-width: 780px;
		margin: 0 auto;
		padding: 32px 24px 64px;
		color: #e2e8f0;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
		font-size: 15px;
		line-height: 1.65;
	}
	.print-brand { display: none; }
	.print-only { display: none; }
	.hdr { margin-bottom: 36px; }
	.hdr-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		margin-bottom: 20px;
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
	.kicker {
		font-size: 11px;
		color: #64748b;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		margin-bottom: 6px;
	}
	.title {
		font-size: 44px;
		font-weight: 800;
		color: #f8fafc;
		margin: 0 0 8px;
		line-height: 1.05;
		letter-spacing: -0.02em;
	}
	.subtitle {
		color: #cbd5e1;
		font-size: 16px;
		margin: 0;
		max-width: 680px;
	}
	.section { margin: 36px 0; }
	.section h2 {
		font-size: 14px;
		font-weight: 700;
		color: #f8fafc;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin: 0 0 14px;
		padding-bottom: 6px;
		border-bottom: 1px solid #1e293b;
	}
	.section p {
		color: #cbd5e1;
		margin: 0 0 12px;
	}
	.section p strong { color: #f8fafc; }
	.section a { color: #60a5fa; }
	.principles, .lenses, .audiences, .services, .stack {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.principles li, .audiences li, .services li, .stack li {
		color: #cbd5e1;
		padding: 10px 12px;
		background: rgba(255,255,255,0.02);
		border-left: 2px solid rgba(96,165,250,0.3);
		border-radius: 0 4px 4px 0;
	}
	.principles li strong, .audiences li strong, .services li strong, .stack li strong {
		color: #f8fafc;
	}
	.lenses li {
		color: #cbd5e1;
		padding: 8px 12px;
		background: rgba(255,255,255,0.02);
		border-radius: 4px;
	}
	.lens-name {
		color: #93c5fd;
		font-weight: 700;
		margin-right: 6px;
	}
	.note {
		font-size: 13px;
		color: #94a3b8;
		font-style: italic;
	}
	.disclaimer {
		margin-top: 44px;
		padding: 20px 24px;
		background: rgba(251, 191, 36, 0.04);
		border-left: 3px solid rgba(251, 191, 36, 0.4);
		border-radius: 0 6px 6px 0;
	}
	.disclaimer h2 { border-bottom-color: rgba(251, 191, 36, 0.25); }
	.disclaimer p strong { color: #fde68a; }

	.footer {
		margin-top: 56px;
		padding-top: 20px;
		border-top: 1px solid #1e293b;
		font-size: 12px;
		color: #64748b;
	}
	.footer p { margin: 6px 0; }
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
		.kicker { color: #64748b; font-size: 8pt; letter-spacing: 0.08em; margin-bottom: 4pt; }
		.title {
			color: #0f172a;
			font-size: 26pt;
			line-height: 1.1;
			margin-bottom: 6pt;
		}
		.subtitle { color: #334155; font-size: 11pt; }
		.section { margin: 14pt 0; page-break-inside: avoid; }
		.section h2 {
			color: #0f172a;
			font-size: 11pt;
			border-bottom: 0.5pt solid #cbd5e1;
			padding-bottom: 3pt;
			margin-bottom: 6pt;
		}
		.section p { color: #1a1a1a; }
		.section p strong { color: #0f172a; }
		.section a { color: #1d4ed8; }
		.principles li, .audiences li, .services li, .stack li {
			background: #f9fafb;
			color: #1a1a1a;
			border-left: 1pt solid #cbd5e1;
			padding: 5pt 8pt;
			font-size: 9pt;
		}
		.principles li strong, .audiences li strong, .services li strong, .stack li strong {
			color: #0f172a;
		}
		.lenses li {
			background: #f9fafb;
			color: #1a1a1a;
			font-size: 9pt;
			padding: 4pt 8pt;
		}
		.lens-name { color: #1d4ed8; }
		.disclaimer {
			background: #fffbeb;
			border-left: 2pt solid #f59e0b;
			padding: 10pt 12pt;
			page-break-inside: avoid;
		}
		.disclaimer p strong { color: #92400e; }
		.note { color: #475569; font-size: 9pt; }
		.section a[href^="http"]::after,
		.footer a[href^="http"]::after {
			content: " (" attr(href) ")";
			font-size: 8pt;
			color: #64748b;
		}
		.footer {
			border-top: 0.5pt solid #cbd5e1;
			color: #475569;
			font-size: 8pt;
			margin-top: 24pt;
			padding-top: 8pt;
		}
		.footer a { color: #1d4ed8; }
		.footer .generated { margin-top: 6pt; font-style: italic; color: #64748b; }
	}
</style>
