import type { Locale } from '$lib/stores/i18n.svelte';

export interface ServiciosContent {
	pageTitle: string;
	metaDesc: string;
	ogTitle: string;
	ogDesc: string;
	kicker: string;
	subtitle: string;
	queEsTitle: string;
	queEsP1: string;
	queEsP2: string;
	marcoTitle: string;
	marcoP1: string;
	principiosTitle: string;
	principios: string[];
	queOfreceTitle: string;
	queOfreceIntro: string;
	queOfrece: string[];
	queOfreceFootnote: string;
	paraQuienesTitle: string;
	paraQuienes: string[];
	serviciosTitle: string;
	servicios: string[];
	limitesTitle: string;
	limitesWarning: string;
	limitesP1: string;
	limitesP2: string;
	limitesP3: string;
	limitesP4: string;
	limitesP5: string;
	liabilityText: string;
	termsLink: string;
	fuentesTitle: string;
	fuentesP1: string;
	contactoTitle: string;
	contactoContent: string;
	citationLabel: string;
	affil: string;
	printGenerated: string;
}

export const SERVICIOS: Record<Locale, ServiciosContent> = {
	es: {
		pageTitle: 'nealab — inteligencia geoespacial abierta para el noreste argentino y sus regiones transfronterizas',
		metaDesc: 'nealab es una plataforma de análisis geoespacial orientada al noreste argentino y sus regiones transfronterizas. Reúne más de veinte capas de análisis satelital, censal y ambiental para investigación, gestión pública y cooperación internacional.',
		ogTitle: 'nealab — servicios de inteligencia geoespacial',
		ogDesc: 'Plataforma pública de inteligencia geoespacial abierta. Análisis reproducible, acceso abierto, ciencia ciudadana. Hospedado en spatia.ar.',
		kicker: 'Inteligencia geoespacial abierta · Noreste argentino y regiones transfronterizas',
		subtitle: 'Plataforma de análisis geoespacial orientada al noreste argentino y sus regiones transfronterizas. Datos, métodos y código abiertos. Hospedado en <a href="/">spatia.ar</a>.',
		queEsTitle: 'Qué es nealab',
		queEsP1: '<strong>nealab</strong> es una plataforma de <strong>inteligencia geoespacial abierta</strong> desarrollada en el marco del <strong>Consejo Nacional de Investigaciones Científicas y Técnicas (CONICET, Argentina)</strong>, la <strong>Secretaría de Investigación y Posgrado (SINVyP)</strong> de la <strong>Facultad de Humanidades y Ciencias Sociales (FHyCS)</strong> de la <strong>Universidad Nacional de Misiones (UNaM)</strong>, y el acceso de nivel investigación al <strong>Google Earth Engine (GEE) Partner Tier</strong>. Reúne más de veinte capas de análisis sobre el noreste argentino y sus regiones transfronterizas para explorar de forma interactiva el estado ecológico, social, productivo y de infraestructura de la región.',
		queEsP2: 'No constituye un sistema de recomendación, ni un sustituto del juicio experto o de la decisión política. Es una herramienta para visualizar capas de información pública, contrastarlas entre sí y enriquecer diagnósticos con evidencia cuantitativa reproducible.',
		marcoTitle: 'Marco institucional',
		marcoP1: 'El desarrollo de nealab se enmarca en el proyecto de investigación <em>Evolución de las desigualdades sociales en torno a las Áreas Naturales Protegidas Transfronterizas de Argentina, Brasil y Paraguay</em> (código 16/H1710-FE, SINVyP FHyCS-UNaM), dirigido por el Dr. Raimundo Elias Gomez, y desarrollado con el aval de CONICET. Este proyecto integra el <strong>Programa de Investigaciones Interdisciplinarias sobre Regiones de Frontera (INREFRO)</strong> de la FHyCS-UNaM.',
		principiosTitle: 'Principios',
		principios: [
			'<strong>Acceso abierto.</strong> Todos los datos que integra la plataforma provienen de fuentes públicas declaradas en la ficha metodológica de cada capa — entre otras: el Instituto Nacional de Estadística y Censos (INDEC), el Instituto Geográfico Nacional (IGN), OpenStreetMap (OSM), MapBiomas, Catastro, el Joint Research Centre (JRC) de la Comisión Europea, Hansen Global Forest Change (GFC) y MODIS (Moderate Resolution Imaging Spectroradiometer). Cualquier persona puede consultar esas fuentes originales y reproducir los análisis siguiendo el pipeline documentado.',
			'<strong>Trazabilidad metodológica.</strong> Cada capa tiene su ficha técnica con fuentes, resolución, pipeline de procesamiento, supuestos y limitaciones conocidas. Las fichas están linkeadas desde el panel lateral de cada análisis.',
			'<strong>Reproducibilidad.</strong> El pipeline completo está documentado en un repositorio público. Los análisis pueden reproducirse y adaptarse a otras jurisdicciones sobre las mismas fuentes de datos abiertos.',
			'<strong>Actualización continua.</strong> Las capas actualizables —dinámica de deforestación, riesgo hídrico, actividad productiva, confort climático, entre otras— se regeneran de forma automatizada a partir de las fuentes originales. Los pipelines corren programados sin intervención manual, de modo que los datos visualizados reflejan el estado más reciente disponible en cada momento.',
			'<strong>Acceso abierto a herramientas técnicas.</strong> La plataforma permite a gobiernos locales, organizaciones de investigación e instituciones técnicas acceder a las mismas herramientas de análisis que usan organismos multilaterales, e incorporar evidencia geoespacial reproducible a sus diagnósticos.',
			'<strong>Interoperabilidad.</strong> Cualquier vista o zona puede exportarse a CSV o GeoJSON. Se integra sin fricción con flujos de trabajo existentes en gobierno, academia y consultoría.',
		],
		queOfreceTitle: 'Qué ofrece',
		queOfreceIntro: 'nealab organiza sus análisis en cuatro grandes preguntas o "lentes", que pueden combinarse entre sí:',
		queOfrece: [
			'<strong>Habitar.</strong> Riesgo de inundación (JRC Global Surface Water + Sentinel-1 SAR — radar de apertura sintética, satélites de la Agencia Espacial Europea — ESA), carencia de servicios básicos (censo 2022), calidad edilicia, accesibilidad a salud y educación, catastro parcelario.',
			'<strong>Producir.</strong> Aptitud edafoclimática agrícola, aptitud forestal comercial, salud de la vegetación, stock de carbono y balance de emisiones, dinámica de deforestación, calidad del aire (PM2.5 — material particulado fino de diámetro ≤ 2,5 micrómetros) y cumplimiento del Reglamento de Deforestación de la Unión Europea (EUDR, por sus siglas en inglés) para commodities.',
			'<strong>Servir.</strong> Capital educativo, flujo del sistema educativo, acceso a salud, aislamiento geoespacial y perfil sociodemográfico, con crosswalk dasimétrico a hexágonos H3.',
			'<strong>Invertir.</strong> Valor posicional, presión de cambio urbano, confort climático, infraestructura eléctrica y clasificación de tipos geoespaciales para informar decisiones de localización.',
		],
		queOfreceFootnote: 'Todas las capas se proyectan sobre una grilla hexagonal <strong>H3</strong> (sistema de indexación geoespacial de código abierto desarrollado por Uber Technologies) de resolución 9 (~0,1 km² por hexágono, ~320 000 hexágonos por territorio analizado), con crosswalks documentados a radios censales y parcelas catastrales para análisis cruzados.',
		paraQuienesTitle: 'Para quienes',
		paraQuienes: [
			'<strong>Organismos multilaterales</strong> — Programa de las Naciones Unidas para el Desarrollo (PNUD), Banco Interamericano de Desarrollo (BID), Banco Mundial, Organización de las Naciones Unidas para la Alimentación y la Agricultura (FAO), Comisión Económica para América Latina y el Caribe (CEPAL) — que necesiten diagnósticos geoespaciales rápidos y reproducibles sobre el noreste argentino y sus regiones transfronterizas, con datos curados y pipelines auditables.',
			'<strong>Gobiernos provinciales y municipales</strong> que busquen visualizar simultáneamente indicadores ambientales, sociales y de infraestructura para planificación sectorial o negociación con terceros.',
			'<strong>Investigación académica</strong> con necesidad de datos curados listos para análisis, especialmente en ecología, geografía, economía ecológica, ciencias sociales y salud pública.',
			'<strong>Organizaciones de la sociedad civil</strong> que quieran fundamentar denuncias, propuestas de política o campañas de incidencia con evidencia cuantitativa rigurosa.',
			'<strong>Consultoras ambientales, agrícolas y forestales</strong> que necesiten due-diligence geoespacial verificable, particularmente para cumplimiento EUDR en exportaciones hacia la Unión Europea.',
			'<strong>Docentes y estudiantes</strong> que quieran introducirse al análisis geoespacial con una plataforma en español, con metodologías explicadas y datos reales.',
		],
		serviciosTitle: 'Servicios disponibles',
		servicios: [
			'<strong>Asesoría geoespacial aplicada.</strong> Acompañamiento técnico a proyectos específicos de diagnóstico, planificación, evaluación de impacto o diseño de políticas.',
			'<strong>Informes temáticos por departamento o zona.</strong> Fichas sintéticas que integran todas las capas relevantes sobre un recorte espacial solicitado, con interpretación contextualizada.',
			'<strong>Análisis de cumplimiento EUDR.</strong> Due diligence geoespacial sobre áreas de origen de commodities (soja, carne, madera, café, cacao, caucho, aceite de palma) con la Regulación UE 2023/1115, combinando Hansen GFC, MODIS MCD64A1 y geometrías parcelarias.',
			'<strong>Integración con sistemas existentes.</strong> Conexión de nealab con Sistemas de Información Geográfica (SIG) institucionales, tableros de Business Intelligence (BI), interfaces de programación (API) de terceros y flujos internos mediante DuckDB, Parquet o GeoJSON.',
		],
		limitesTitle: 'Sobre los límites de este análisis',
		limitesWarning: 'Esta sección es importante y pedimos que se lea con atención antes de utilizar nealab en cualquier decisión con consecuencias reales.',
		limitesP1: '<strong>nealab es una herramienta analítica, no prescriptiva.</strong> Ningún análisis en esta plataforma constituye una recomendación de acción, una certificación técnica ni una consultoría profesional. Los scores, tipologías y rankings son síntesis cuantitativas de variables observables desde percepción remota, censos y fuentes administrativas. No sustituyen el juicio experto ni la responsabilidad de quien decide.',
		limitesP2: '<strong>Sin garantía de exactitud.</strong> La plataforma y toda la información que contiene se proveen tal cual (as-is), sin garantías expresas ni implícitas sobre exactitud, completitud, actualización o idoneidad para ningún propósito en particular. Los datos satelitales, censales y administrativos pueden contener errores, desfasajes temporales o limitaciones metodológicas documentadas en la ficha técnica de cada capa.',
		limitesP3: '<strong>Ningún análisis geoespacial reemplaza el trabajo de campo.</strong> La percepción remota captura condiciones físicas promedio en ventanas temporales definidas; no captura procesos sociales, conflictos de uso, restricciones jurídicas o cambios recientes que aún no se hayan incorporado a los datos. Las capas de nealab requieren validación en terreno por parte de técnicos y responsables que conozcan la situación local.',
		limitesP4: 'Una zona clasificada con alta aptitud agrícola puede tener restricciones de uso, regímenes de tenencia o condiciones locales no reflejados en los datos disponibles. Una zona con bajo riesgo histórico de inundación puede estar experimentando cambios hidrológicos recientes. En todos los casos, el análisis geoespacial es un insumo diagnóstico, no un resultado de política.',
		limitesP5: '<strong>Cada clasificación disponible en nealab debe entenderse como una hipótesis a contrastar, no como un resultado definitivo.</strong> El uso responsable implica leer la ficha metodológica de cada capa, reconocer sus limitaciones, y complementar el análisis con validación de campo.',
		liabilityText: '<strong>Responsabilidad.</strong> Bajo ninguna circunstancia el autor, CONICET ni UNaM serán responsables por daños directos, indirectos, incidentales o consecuentes derivados del uso de nealab. Quien utilice esta plataforma en un contexto de gestión, inversión, investigación o política pública asume la responsabilidad de ese uso y debe complementarlo con validación profesional independiente.',
		termsLink: 'Leer términos y condiciones completos →',
		fuentesTitle: 'Fuentes y colaboraciones',
		fuentesP1: 'nealab integra datos de fuentes públicas, entre ellas: INDEC (Censo Nacional de Población, Hogares y Viviendas 2022), IGN, Dirección General de Catastro de Misiones, JRC Global Surface Water, Hansen Global Forest Change, MODIS, MapBiomas (Argentina y Paraguay), CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data), ERA5 (reanálisis climático del Centro Europeo de Predicción Meteorológica a Medio Plazo — ECMWF, 5.ª versión), VIIRS (Visible Infrared Imaging Radiometer Suite, sensor NOAA/NASA), GHSL (Global Human Settlement Layer, Centro Común de Investigación de la Unión Europea), SoilGrids (ISRIC — International Soil Reference and Information Centre), misiones Sentinel de la Agencia Espacial Europea (ESA) / programa Copernicus, Global Building Atlas (GBA; Zhu et al., 2025, Earth System Science Data — ESSD), Overture Maps Foundation, OpenStreetMap, Meta / World Resources Institute (WRI) Canopy Height, GEDI L4B (Global Ecosystem Dynamics Investigation — NASA), ESA CCI Biomass (Climate Change Initiative de la ESA), Global Forest Watch (GFW), conjunto PM2.5 de la Universidad de Dalhousie (ACAG — Atmospheric Composition Analysis Group), EMSA (Empresa Misionera de Energía), Oxford MAP (Malaria Atlas Project), Dirección General de Estadística, Encuestas y Censos de Paraguay (DGEEC) e Instituto Brasileiro de Geografia e Estatística (IBGE), entre otras. El procesamiento se realiza sobre Google Earth Engine como plataforma de cómputo, con acceso al <strong>Google Earth Engine Partner Tier</strong>.',
		contactoTitle: 'Contacto',
		contactoContent: '<strong>Raimundo Elias Gomez</strong><br />Investigador CONICET · Facultad de Humanidades y Ciencias Sociales, Universidad Nacional de Misiones (Argentina)<br /><a href="mailto:nealab@spatia.ar">nealab@spatia.ar</a>',
		citationLabel: 'Citación sugerida',
		affil: 'CONICET · FHyCS-UNaM · Google Earth Engine Partner Tier',
		printGenerated: 'Documento generado el {date} desde spatia.ar/servicios',
	},

	en: {
		pageTitle: 'nealab — open geospatial intelligence for northeast Argentina and its cross-border regions',
		metaDesc: 'nealab is a geospatial analysis platform focused on northeast Argentina and its cross-border regions. It brings together more than twenty satellite, census and environmental analysis layers for research, public management and international cooperation.',
		ogTitle: 'nealab — geospatial intelligence services',
		ogDesc: 'Open public geospatial intelligence platform. Reproducible analysis, open access, citizen science. Hosted at spatia.ar.',
		kicker: 'Open geospatial intelligence · Northeast Argentina & cross-border regions',
		subtitle: 'Geospatial analysis platform focused on northeast Argentina and its cross-border regions. Open data, methods and code. Hosted at <a href="/">spatia.ar</a>.',
		queEsTitle: 'What is nealab',
		queEsP1: '<strong>nealab</strong> is an <strong>open geospatial intelligence</strong> platform developed within the framework of the <strong>National Scientific and Technical Research Council (CONICET, Argentina)</strong>, the <strong>Research and Postgraduate Secretariat (SINVyP)</strong> of the <strong>Faculty of Humanities and Social Sciences (FHyCS)</strong> at the <strong>National University of Misiones (UNaM)</strong>, and research-level access to the <strong>Google Earth Engine (GEE) Partner Tier</strong>. It brings together more than twenty analysis layers covering northeast Argentina and its cross-border regions to interactively explore the ecological, social, productive and infrastructure status of the region.',
		queEsP2: 'It is not a recommendation system, nor a substitute for expert judgement or political decision-making. It is a tool for visualising layers of public information, cross-referencing them, and enriching diagnostics with reproducible quantitative evidence.',
		marcoTitle: 'Institutional framework',
		marcoP1: 'The development of nealab is embedded in the research project <em>Evolution of social inequalities around Transboundary Protected Natural Areas in Argentina, Brazil and Paraguay</em> (code 16/H1710-FE, SINVyP FHyCS-UNaM), directed by Dr. Raimundo Elias Gomez, and conducted with the backing of CONICET. This project is part of the <strong>Interdisciplinary Research Programme on Border Regions (INREFRO)</strong> of FHyCS-UNaM.',
		principiosTitle: 'Principles',
		principios: [
			'<strong>Open access.</strong> All data integrated by the platform comes from public sources declared in the methodological fact sheet of each layer — including: the National Institute of Statistics and Censuses (INDEC), the National Geographic Institute (IGN), OpenStreetMap (OSM), MapBiomas, Land Registry, the Joint Research Centre (JRC) of the European Commission, Hansen Global Forest Change (GFC) and MODIS (Moderate Resolution Imaging Spectroradiometer). Anyone can consult those original sources and reproduce the analyses following the documented pipeline.',
			'<strong>Methodological traceability.</strong> Each layer has its technical fact sheet with sources, resolution, processing pipeline, assumptions and known limitations. The fact sheets are linked from the side panel of each analysis.',
			'<strong>Reproducibility.</strong> The complete pipeline is documented in a public repository. The analyses can be reproduced and adapted to other jurisdictions using the same open data sources.',
			'<strong>Continuous updates.</strong> Updatable layers — deforestation dynamics, flood risk, productive activity, climate comfort, among others — are automatically regenerated from the original sources. The pipelines run on schedule without manual intervention, so the visualised data reflects the most recent available state at any given time.',
			'<strong>Open access to technical tools.</strong> The platform enables local governments, research organisations and technical institutions to access the same analytical tools used by multilateral organisations, and to incorporate reproducible geospatial evidence into their diagnostics.',
			'<strong>Interoperability.</strong> Any view or zone can be exported to CSV or GeoJSON. It integrates seamlessly with existing workflows in government, academia and consulting.',
		],
		queOfreceTitle: 'What it offers',
		queOfreceIntro: 'nealab organises its analyses around four broad questions or "lenses", which can be combined:',
		queOfrece: [
			'<strong>Inhabit.</strong> Flood risk (JRC Global Surface Water + Sentinel-1 SAR — synthetic aperture radar, satellites of the European Space Agency — ESA), basic service deprivation (2022 census), building quality, health and education accessibility, land registry parcels.',
			'<strong>Produce.</strong> Agricultural agro-climatic suitability, commercial forestry suitability, vegetation health, carbon stock and emissions balance, deforestation dynamics, air quality (PM2.5 — fine particulate matter ≤ 2.5 microns in diameter) and EU Deforestation Regulation (EUDR) compliance for commodities.',
			'<strong>Serve.</strong> Educational capital, educational system flow, health access, geospatial isolation and sociodemographic profile, with dasymetric crosswalk to H3 hexagons.',
			'<strong>Invest.</strong> Locational value, urban change pressure, climate comfort, electrical infrastructure and geospatial type classification to inform location decisions.',
		],
		queOfreceFootnote: 'All layers are projected onto an <strong>H3</strong> hexagonal grid (open-source geospatial indexing system developed by Uber Technologies) at resolution 9 (~0.1 km² per hexagon, ~320,000 hexagons per analysed territory), with documented crosswalks to census tracts and cadastral parcels for cross-analysis.',
		paraQuienesTitle: 'Who it is for',
		paraQuienes: [
			'<strong>Multilateral organisations</strong> — United Nations Development Programme (UNDP), Inter-American Development Bank (IDB), World Bank, Food and Agriculture Organization (FAO), Economic Commission for Latin America and the Caribbean (ECLAC) — that need rapid and reproducible geospatial diagnostics on northeast Argentina and its cross-border regions, with curated data and auditable pipelines.',
			'<strong>Provincial and municipal governments</strong> seeking to simultaneously visualise environmental, social and infrastructure indicators for sectoral planning or negotiations with third parties.',
			'<strong>Academic research</strong> requiring curated data ready for analysis, particularly in ecology, geography, ecological economics, social sciences and public health.',
			'<strong>Civil society organisations</strong> wishing to support complaints, policy proposals or advocacy campaigns with rigorous quantitative evidence.',
			'<strong>Environmental, agricultural and forestry consultancies</strong> requiring verifiable geospatial due diligence, particularly for EUDR compliance in exports to the European Union.',
			'<strong>Teachers and students</strong> wishing to engage with geospatial analysis through a Spanish-language platform with explained methodologies and real data.',
		],
		serviciosTitle: 'Available services',
		servicios: [
			'<strong>Applied geospatial advisory.</strong> Technical support for specific diagnostic, planning, impact assessment or policy design projects.',
			'<strong>Thematic reports by department or area.</strong> Synthetic fact sheets integrating all relevant layers for a requested spatial extent, with contextualised interpretation.',
			'<strong>EUDR compliance analysis.</strong> Geospatial due diligence on commodity origin areas (soy, beef, timber, coffee, cocoa, rubber, palm oil) under EU Regulation 2023/1115, combining Hansen GFC, MODIS MCD64A1 and parcel geometries.',
			'<strong>Integration with existing systems.</strong> Connecting nealab with institutional Geographic Information Systems (GIS), Business Intelligence (BI) dashboards, third-party application programming interfaces (APIs) and internal workflows via DuckDB, Parquet or GeoJSON.',
		],
		limitesTitle: 'On the limits of this analysis',
		limitesWarning: 'This section is important and we ask that it be read carefully before using nealab in any decision with real consequences.',
		limitesP1: '<strong>nealab is an analytical, not prescriptive, tool.</strong> No analysis on this platform constitutes an action recommendation, technical certification or professional consultancy. The scores, typologies and rankings are quantitative summaries of variables observable through remote sensing, censuses and administrative sources. They do not replace expert judgement or the responsibility of the decision-maker.',
		limitesP2: '<strong>No accuracy guarantee.</strong> The platform and all information it contains are provided as-is, without express or implied warranties of accuracy, completeness, currency or fitness for any particular purpose. Satellite, census and administrative data may contain errors, time lags or methodological limitations documented in each layer\'s technical fact sheet.',
		limitesP3: '<strong>No geospatial analysis replaces fieldwork.</strong> Remote sensing captures average physical conditions over defined time windows; it does not capture social processes, land-use conflicts, legal restrictions or recent changes not yet incorporated into the data. nealab\'s layers require on-the-ground validation by technicians and responsible parties who know the local situation.',
		limitesP4: 'An area classified as having high agricultural suitability may have use restrictions, tenure arrangements or local conditions not reflected in the available data. An area with a low historical flood risk may be experiencing recent hydrological changes. In all cases, geospatial analysis is a diagnostic input, not a policy outcome.',
		limitesP5: '<strong>Every classification available in nealab should be understood as a hypothesis to be tested, not a definitive result.</strong> Responsible use entails reading each layer\'s methodological fact sheet, acknowledging its limitations, and complementing the analysis with field validation.',
		liabilityText: '<strong>Liability.</strong> Under no circumstances shall the author, CONICET or UNaM be liable for direct, indirect, incidental or consequential damages arising from the use of nealab. Anyone using this platform in a management, investment, research or public policy context assumes responsibility for that use and must complement it with independent professional validation.',
		termsLink: 'Read full terms and conditions →',
		fuentesTitle: 'Sources and collaborations',
		fuentesP1: 'nealab integrates data from public sources, including: INDEC (National Population, Household and Housing Census 2022), IGN, Directorate-General of Land Registry of Misiones, JRC Global Surface Water, Hansen Global Forest Change, MODIS, MapBiomas (Argentina and Paraguay), CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data), ERA5 (climate reanalysis by the European Centre for Medium-Range Weather Forecasts — ECMWF, 5th generation), VIIRS (Visible Infrared Imaging Radiometer Suite, NOAA/NASA sensor), GHSL (Global Human Settlement Layer, European Commission Joint Research Centre), SoilGrids (ISRIC — International Soil Reference and Information Centre), Sentinel missions by the European Space Agency (ESA) / Copernicus programme, Global Building Atlas (GBA; Zhu et al., 2025, Earth System Science Data — ESSD), Overture Maps Foundation, OpenStreetMap, Meta / World Resources Institute (WRI) Canopy Height, GEDI L4B (Global Ecosystem Dynamics Investigation — NASA), ESA CCI Biomass (ESA Climate Change Initiative), Global Forest Watch (GFW), PM2.5 dataset from Dalhousie University (ACAG — Atmospheric Composition Analysis Group), EMSA (Empresa Misionera de Energía), Oxford MAP (Malaria Atlas Project), Dirección General de Estadística, Encuestas y Censos de Paraguay (DGEEC) and the Brazilian Institute of Geography and Statistics (IBGE), among others. Processing is carried out on Google Earth Engine as the computing platform, with access to the <strong>Google Earth Engine Partner Tier</strong>.',
		contactoTitle: 'Contact',
		contactoContent: '<strong>Raimundo Elias Gomez</strong><br />CONICET Researcher · Faculty of Humanities and Social Sciences, National University of Misiones (Argentina)<br /><a href="mailto:nealab@spatia.ar">nealab@spatia.ar</a>',
		citationLabel: 'Suggested citation',
		affil: 'CONICET · FHyCS-UNaM · Google Earth Engine Partner Tier',
		printGenerated: 'Document generated on {date} from spatia.ar/servicios',
	},

	pt: {
		pageTitle: 'nealab — inteligência geoespacial aberta para o nordeste argentino e suas regiões transfronteiriças',
		metaDesc: 'nealab é uma plataforma de análise geoespacial orientada ao nordeste argentino e suas regiões transfronteiriças. Reúne mais de vinte camadas de análise satelital, censitária e ambiental para pesquisa, gestão pública e cooperação internacional.',
		ogTitle: 'nealab — serviços de inteligência geoespacial',
		ogDesc: 'Plataforma pública de inteligência geoespacial aberta. Análise reproduzível, acesso aberto, ciência cidadã. Hospedado em spatia.ar.',
		kicker: 'Inteligência geoespacial aberta · Nordeste argentino e regiões transfronteiriças',
		subtitle: 'Plataforma de análise geoespacial orientada ao nordeste argentino e suas regiões transfronteiriças. Dados, métodos e código abertos. Hospedado em <a href="/">spatia.ar</a>.',
		queEsTitle: 'O que é nealab',
		queEsP1: '<strong>nealab</strong> é uma plataforma de <strong>inteligência geoespacial aberta</strong> desenvolvida no âmbito do <strong>Conselho Nacional de Pesquisas Científicas e Técnicas (CONICET, Argentina)</strong>, da <strong>Secretaria de Pesquisa e Pós-graduação (SINVyP)</strong> da <strong>Faculdade de Humanidades e Ciências Sociais (FHyCS)</strong> da <strong>Universidade Nacional de Misiones (UNaM)</strong>, e com acesso de nível de pesquisa ao <strong>Google Earth Engine (GEE) Partner Tier</strong>. Reúne mais de vinte camadas de análise sobre o nordeste argentino e suas regiões transfronteiriças para explorar de forma interativa o estado ecológico, social, produtivo e de infraestrutura da região.',
		queEsP2: 'Não constitui um sistema de recomendação, nem um substituto do julgamento especializado ou da decisão política. É uma ferramenta para visualizar camadas de informação pública, confrontá-las entre si e enriquecer diagnósticos com evidências quantitativas reproduzíveis.',
		marcoTitle: 'Marco institucional',
		marcoP1: 'O desenvolvimento do nealab se insere no projeto de pesquisa <em>Evolução das desigualdades sociais em torno das Áreas Naturais Protegidas Transfronteiriças da Argentina, Brasil e Paraguai</em> (código 16/H1710-FE, SINVyP FHyCS-UNaM), dirigido pelo Dr. Raimundo Elias Gomez, e desenvolvido com o apoio do CONICET. Este projeto integra o <strong>Programa de Pesquisas Interdisciplinares sobre Regiões de Fronteira (INREFRO)</strong> da FHyCS-UNaM.',
		principiosTitle: 'Princípios',
		principios: [
			'<strong>Acesso aberto.</strong> Todos os dados integrados pela plataforma provêm de fontes públicas declaradas na ficha metodológica de cada camada — entre outras: o Instituto Nacional de Estatística e Censos (INDEC), o Instituto Geográfico Nacional (IGN), OpenStreetMap (OSM), MapBiomas, Cadastro, o Joint Research Centre (JRC) da Comissão Europeia, Hansen Global Forest Change (GFC) e MODIS (Moderate Resolution Imaging Spectroradiometer). Qualquer pessoa pode consultar essas fontes originais e reproduzir as análises seguindo o pipeline documentado.',
			'<strong>Rastreabilidade metodológica.</strong> Cada camada possui sua ficha técnica com fontes, resolução, pipeline de processamento, pressupostos e limitações conhecidas. As fichas estão vinculadas a partir do painel lateral de cada análise.',
			'<strong>Reprodutibilidade.</strong> O pipeline completo está documentado em um repositório público. As análises podem ser reproduzidas e adaptadas a outras jurisdições com base nas mesmas fontes de dados abertos.',
			'<strong>Atualização contínua.</strong> As camadas atualizáveis — dinâmica de desmatamento, risco hídrico, atividade produtiva, conforto climático, entre outras — são regeneradas automaticamente a partir das fontes originais. Os pipelines rodam programados sem intervenção manual, de modo que os dados visualizados refletem o estado mais recente disponível a cada momento.',
			'<strong>Acesso aberto a ferramentas técnicas.</strong> A plataforma permite que governos locais, organizações de pesquisa e instituições técnicas acessem as mesmas ferramentas de análise utilizadas por organismos multilaterais, e incorporem evidências geoespaciais reproduzíveis a seus diagnósticos.',
			'<strong>Interoperabilidade.</strong> Qualquer visualização ou zona pode ser exportada para CSV ou GeoJSON. Integra-se sem fricção com fluxos de trabalho existentes em governo, academia e consultoria.',
		],
		queOfreceTitle: 'O que oferece',
		queOfreceIntro: 'nealab organiza suas análises em quatro grandes questões ou "lentes", que podem ser combinadas entre si:',
		queOfrece: [
			'<strong>Habitar.</strong> Risco de inundação (JRC Global Surface Water + Sentinel-1 SAR — radar de abertura sintética, satélites da Agência Espacial Europeia — ESA), carência de serviços básicos (censo 2022), qualidade edilícia, acessibilidade à saúde e educação, cadastro de parcelas.',
			'<strong>Produzir.</strong> Aptidão edafoclimática agrícola, aptidão florestal comercial, saúde da vegetação, estoque de carbono e balanço de emissões, dinâmica de desmatamento, qualidade do ar (PM2,5 — material particulado fino com diâmetro ≤ 2,5 micrômetros) e conformidade com o Regulamento de Desmatamento da União Europeia (EUDR) para commodities.',
			'<strong>Servir.</strong> Capital educacional, fluxo do sistema educacional, acesso à saúde, isolamento geoespacial e perfil sociodemográfico, com crosswalk dassimétrico para hexágonos H3.',
			'<strong>Investir.</strong> Valor locacional, pressão de mudança urbana, conforto climático, infraestrutura elétrica e classificação de tipos geoespaciais para embasar decisões de localização.',
		],
		queOfreceFootnote: 'Todas as camadas são projetadas sobre uma grade hexagonal <strong>H3</strong> (sistema de indexação geoespacial de código aberto desenvolvido pela Uber Technologies) de resolução 9 (~0,1 km² por hexágono, ~320.000 hexágonos por território analisado), com crosswalks documentados para setores censitários e parcelas cadastrais para análises cruzadas.',
		paraQuienesTitle: 'Para quem',
		paraQuienes: [
			'<strong>Organismos multilaterais</strong> — Programa das Nações Unidas para o Desenvolvimento (PNUD), Banco Interamericano de Desenvolvimento (BID), Banco Mundial, Organização das Nações Unidas para a Alimentação e a Agricultura (FAO), Comissão Econômica para a América Latina e o Caribe (CEPAL) — que necessitem de diagnósticos geoespaciais rápidos e reproduzíveis sobre o nordeste argentino e suas regiões transfronteiriças, com dados curados e pipelines auditáveis.',
			'<strong>Governos provinciais e municipais</strong> que busquem visualizar simultaneamente indicadores ambientais, sociais e de infraestrutura para planejamento setorial ou negociação com terceiros.',
			'<strong>Pesquisa acadêmica</strong> com necessidade de dados curados prontos para análise, especialmente em ecologia, geografia, economia ecológica, ciências sociais e saúde pública.',
			'<strong>Organizações da sociedade civil</strong> que desejem fundamentar denúncias, propostas de política ou campanhas de incidência com evidências quantitativas rigorosas.',
			'<strong>Consultorias ambientais, agrícolas e florestais</strong> que necessitem de due diligence geoespacial verificável, particularmente para conformidade com o EUDR em exportações para a União Europeia.',
			'<strong>Docentes e estudantes</strong> que desejem introduzir-se à análise geoespacial com uma plataforma em espanhol, com metodologias explicadas e dados reais.',
		],
		serviciosTitle: 'Serviços disponíveis',
		servicios: [
			'<strong>Assessoria geoespacial aplicada.</strong> Acompanhamento técnico a projetos específicos de diagnóstico, planejamento, avaliação de impacto ou elaboração de políticas.',
			'<strong>Relatórios temáticos por departamento ou zona.</strong> Fichas sintéticas que integram todas as camadas relevantes sobre um recorte espacial solicitado, com interpretação contextualizada.',
			'<strong>Análise de conformidade EUDR.</strong> Due diligence geoespacial sobre áreas de origem de commodities (soja, carne, madeira, café, cacau, borracha, óleo de palma) conforme o Regulamento UE 2023/1115, combinando Hansen GFC, MODIS MCD64A1 e geometrias de parcelas.',
			'<strong>Integração com sistemas existentes.</strong> Conexão do nealab com Sistemas de Informação Geográfica (SIG) institucionais, painéis de Business Intelligence (BI), interfaces de programação (API) de terceiros e fluxos internos mediante DuckDB, Parquet ou GeoJSON.',
		],
		limitesTitle: 'Sobre os limites desta análise',
		limitesWarning: 'Esta seção é importante e pedimos que seja lida com atenção antes de utilizar o nealab em qualquer decisão com consequências reais.',
		limitesP1: '<strong>nealab é uma ferramenta analítica, não prescritiva.</strong> Nenhuma análise nesta plataforma constitui uma recomendação de ação, certificação técnica ou consultoria profissional. Os scores, tipologias e rankings são sínteses quantitativas de variáveis observáveis por percepção remota, censos e fontes administrativas. Não substituem o julgamento especializado nem a responsabilidade de quem decide.',
		limitesP2: '<strong>Sem garantia de exatidão.</strong> A plataforma e todas as informações que contém são fornecidas no estado em que se encontram (as-is), sem garantias expressas ou implícitas de exatidão, completude, atualidade ou adequação a qualquer finalidade específica. Os dados satelitais, censitários e administrativos podem conter erros, defasagens temporais ou limitações metodológicas documentadas na ficha técnica de cada camada.',
		limitesP3: '<strong>Nenhuma análise geoespacial substitui o trabalho de campo.</strong> A percepção remota captura condições físicas médias em janelas temporais definidas; não captura processos sociais, conflitos de uso, restrições jurídicas ou mudanças recentes ainda não incorporadas aos dados. As camadas do nealab requerem validação em campo por técnicos e responsáveis que conheçam a situação local.',
		limitesP4: 'Uma área classificada com alta aptidão agrícola pode ter restrições de uso, regimes de posse ou condições locais não refletidos nos dados disponíveis. Uma área com baixo risco histórico de inundação pode estar experimentando mudanças hidrológicas recentes. Em todos os casos, a análise geoespacial é um insumo diagnóstico, não um resultado de política.',
		limitesP5: '<strong>Cada classificação disponível no nealab deve ser entendida como uma hipótese a ser testada, não como um resultado definitivo.</strong> O uso responsável implica ler a ficha metodológica de cada camada, reconhecer suas limitações e complementar a análise com validação de campo.',
		liabilityText: '<strong>Responsabilidade.</strong> Em nenhuma circunstância o autor, o CONICET ou a UNaM serão responsáveis por danos diretos, indiretos, incidentais ou consequentes decorrentes do uso do nealab. Quem utilizar esta plataforma em um contexto de gestão, investimento, pesquisa ou política pública assume a responsabilidade por esse uso e deve complementá-lo com validação profissional independente.',
		termsLink: 'Ler termos e condições completos →',
		fuentesTitle: 'Fontes e colaborações',
		fuentesP1: 'nealab integra dados de fontes públicas, entre elas: INDEC (Censo Nacional de População, Domicílios e Moradias 2022), IGN, Diretoria-Geral de Cadastro de Misiones, JRC Global Surface Water, Hansen Global Forest Change, MODIS, MapBiomas (Argentina e Paraguai), CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data), ERA5 (reanálise climática do Centro Europeu de Previsão de Tempo de Médio Prazo — ECMWF, 5.ª geração), VIIRS (Visible Infrared Imaging Radiometer Suite, sensor NOAA/NASA), GHSL (Global Human Settlement Layer, Centro Conjunto de Pesquisa da União Europeia), SoilGrids (ISRIC — International Soil Reference and Information Centre), missões Sentinel da Agência Espacial Europeia (ESA) / programa Copernicus, Global Building Atlas (GBA; Zhu et al., 2025, Earth System Science Data — ESSD), Overture Maps Foundation, OpenStreetMap, Meta / World Resources Institute (WRI) Canopy Height, GEDI L4B (Global Ecosystem Dynamics Investigation — NASA), ESA CCI Biomass (Iniciativa de Mudança Climática da ESA), Global Forest Watch (GFW), conjunto de dados PM2,5 da Universidade de Dalhousie (ACAG — Atmospheric Composition Analysis Group), EMSA (Empresa Misionera de Energía), Oxford MAP (Malaria Atlas Project), Dirección General de Estadística, Encuestas y Censos de Paraguai (DGEEC) e Instituto Brasileiro de Geografia e Estatística (IBGE), entre outras. O processamento é realizado no Google Earth Engine como plataforma de computação, com acesso ao <strong>Google Earth Engine Partner Tier</strong>.',
		contactoTitle: 'Contato',
		contactoContent: '<strong>Raimundo Elias Gomez</strong><br />Pesquisador CONICET · Faculdade de Humanidades e Ciências Sociais, Universidade Nacional de Misiones (Argentina)<br /><a href="mailto:nealab@spatia.ar">nealab@spatia.ar</a>',
		citationLabel: 'Citação sugerida',
		affil: 'CONICET · FHyCS-UNaM · Google Earth Engine Partner Tier',
		printGenerated: 'Documento gerado em {date} a partir de spatia.ar/servicios',
	},

	gn: {
		pageTitle: 'nealab — inteligencia geoespacial abierta noreste argentino ha ñembyatyrã rehegua',
		metaDesc: 'nealab oñemboguapy inteligencia geoespacial abierta-pe, noreste argentino ha ñembyatyrã oñondivekuéra rehegua. Oñembyatyrõ mbovymi análisis satelital, censal ha ambiental investigación, gestión pública ha cooperación internacional hag̃ua.',
		ogTitle: 'nealab — servicios de inteligencia geoespacial',
		ogDesc: 'Plataforma pública de inteligencia geoespacial abierta. Análisis reproducible, acceso abierto, ciencia ciudadana. Hospedado spatia.ar-pe.',
		kicker: 'Inteligencia geoespacial abierta · Noreste argentino ha ñembyatyrã',
		subtitle: 'Plataforma de análisis geoespacial noreste argentino ha ñembyatyrã oñondivekuéra rehegua. Mba\'ekuaa, método ha código ojejapóva oñembyaikuaáva. Oñepytyvõ <a href="/">spatia.ar</a>-pe.',
		queEsTitle: 'Mba\'épa nealab',
		queEsP1: '<strong>nealab</strong> oĩ <strong>inteligencia geoespacial abierta</strong> rehegua, oñemboguapy <strong>Consejo Nacional de Investigaciones Científicas y Técnicas (CONICET, Argentina)</strong>, <strong>Secretaría de Investigación y Posgrado (SINVyP)</strong> pegua <strong>Facultad de Humanidades y Ciencias Sociales (FHyCS)</strong> pegua <strong>Universidad Nacional de Misiones (UNaM)</strong>-pe, ha <strong>Google Earth Engine (GEE) Partner Tier</strong> reheve. Oñembyatyrõ mbovymi análisis noreste argentino ha ñembyatyrã oñondivekuéra rehegua, jechaukávo mba\'éichapa oĩ yvy rekoha ecológico, social, productivo ha infraestructura ñande yvypy pype.',
		queEsP2: 'Ndoikóri sistema de recomendación, ni oñembyaikuaávape experto rekotee ha decisión política. Oĩ herramienta información pública rekave, oñeñombohovake, ha diagnósticos ojehupytyvo evidencia cuantitativa reproducible rupive.',
		marcoTitle: 'Marco institucional',
		marcoP1: 'Nealab oñemboguapy investigación <em>Evolución de las desigualdades sociales en torno a las Áreas Naturales Protegidas Transfronterizas de Argentina, Brasil y Paraguay</em> (16/H1710-FE, SINVyP FHyCS-UNaM) rehegua, Dr. Raimundo Elias Gomez omboaty, ha CONICET oñepytyvõ. Ko proyecto oñemboguapy <strong>Programa de Investigaciones Interdisciplinarias sobre Regiones de Frontera (INREFRO)</strong> FHyCS-UNaM pegua pype.',
		principiosTitle: 'Principios',
		principios: [
			'<strong>Acceso abierto.</strong> Mba\'ekuaa oĩporúva plataforma-pe oú fuentes públicas-gui, ojehechakuaáva ficha metodológica pegua análisis apytépe — oĩ: INDEC, IGN, OpenStreetMap, MapBiomas, Catastro, JRC ha MODIS. Mba\'e peteĩ avave ikatu ohecha upe mba\'ekuaa ha oñembohejakuaa análisis pipeline documentado rupive.',
			'<strong>Trazabilidad metodológica.</strong> Análisis apytépe oĩ su ficha técnica fuentes, resolución, pipeline, supuestos ha limitaciones oñembyaikuaáva rehegua. Fichas oñehenói panel lateral análisis-pe.',
			'<strong>Reproducibilidad.</strong> Pipeline ojehechakuaa repositorio público-pe. Análisis ikatu oñembohejakuaa ha oñeikuaaukávo otras jurisdicciones-pe fuentes abiertas rupive.',
			'<strong>Actualización continua.</strong> Capas actualizables — deforestación, riesgo hídrico, actividad productiva, confort climático — oñemosakã fuentes originales-gui. Pipelines oñemboguapy sin intervención manual, upévare mba\'ekuaa ojehechaúva oñeñombyasy jepi.',
			'<strong>Acceso abierto a herramientas técnicas.</strong> Plataforma oñepytyvõ gobiernos locales, organizaciones de investigación ha instituciones técnicas-pe oikuaávo mba\'eichaha herramientas organismos multilaterales ojeporu, ha oñemboguapy evidencia geoespacial reproducible diagnósticos pegua pype.',
			'<strong>Interoperabilidad.</strong> Mba\'e peteĩ vista térã zona ikatu oñemoheẽ CSV térã GeoJSON-pe. Oñemboikuaa sin dificultad workflows existentes gobierno, academia ha consultoría-pe.',
		],
		queOfreceTitle: 'Mba\'épa ofrece',
		queOfreceIntro: 'nealab oñemboguapy análisis-kuéra mba\'e ñepyrũ ára peteĩ "lentes" irundy reheve, oñemboikuaa jey:',
		queOfrece: [
			'<strong>Tekohása.</strong> Riesgo de inundación (JRC + Sentinel-1 SAR), carencia de servicios básicos (censo 2022), calidad edilicia, accesibilidad a salud ha educación, catastro parcelario.',
			'<strong>Mbosako\'i.</strong> Aptitud agrícola edafoclimática, aptitud forestal, vegetación salud, stock de carbono ha balance de emisiones, deforestación dinámica, calidad del aire (PM2,5) ha cumplimiento EUDR commodities rehegua.',
			'<strong>Mboepykuéra.</strong> Capital educativo, sistema educativo flujo, acceso a salud, aislamiento geoespacial ha perfil sociodemográfico, crosswalk dasimétrico H3 hexágonos-pe.',
			'<strong>Inversión.</strong> Valor posicional, presión de cambio urbano, confort climático, infraestructura eléctrica ha tipos geoespaciales clasificación decisiones de localización rehegua.',
		],
		queOfreceFootnote: 'Capas oĩva oñemboguapy grilla hexagonal <strong>H3</strong> (sistema geoespacial Uber Technologies ojejapóva) resolución 9 (~0,1 km² hexágono apytépe, ~320 000 hexágonos territorio-pe), crosswalks radios censales ha parcelas catastrales-pe análisis cruzados hag̃ua.',
		paraQuienesTitle: 'Mávape',
		paraQuienes: [
			'<strong>Organismos multilaterales</strong> — PNUD, BID, Banco Mundial, FAO, CEPAL — ojehekáva diagnósticos geoespaciales noreste argentino ha ñembyatyrã rehegua, mba\'ekuaa curado ha pipelines auditables ndive.',
			'<strong>Gobiernos provinciales ha municipales</strong> ojehekáva indicadores ambientales, sociales ha infraestructura planificación sectorial hag̃ua.',
			'<strong>Investigación académica</strong> ojehekáva mba\'ekuaa curado análisis hag̃ua, ecología, geografía, economía ecológica, ciencias sociales ha salud pública-pe.',
			'<strong>Organizaciones de la sociedad civil</strong> oñehekáva evidencia cuantitativa denuncias, propuestas ha campañas hag̃ua.',
			'<strong>Consultoras ambientales, agrícolas ha forestales</strong> ojehekáva due-diligence geoespacial verificable, cumplimiento EUDR Unión Europea-pe exportaciones hag̃ua.',
			'<strong>Mbo\'ehára ha estudiantes</strong> oñeikuaávo análisis geoespacial plataforma castellano-pe ojejapóva, metodologías ha mba\'ekuaa reales ndive.',
		],
		serviciosTitle: 'Servicios oĩva',
		servicios: [
			'<strong>Asesoría geoespacial aplicada.</strong> Acompañamiento técnico proyectos específicos diagnóstico, planificación, evaluación de impacto ha diseño de políticas-pe.',
			'<strong>Informes temáticos departamento térã zona-pe.</strong> Fichas sintéticas capas relevantes oñemboikuaáva zona solicitado-pe, interpretación contextualizada ndive.',
			'<strong>Análisis de cumplimiento EUDR.</strong> Due diligence geoespacial commodities origin áreas-pe (soja, carne, madera, café, cacao, caucho, aceite de palma) Regulación UE 2023/1115 reheve.',
			'<strong>Integración sistemas existentes ndive.</strong> nealab oñemboikuaa SIG institucionales, tableros BI, APIs ha flujos internos DuckDB, Parquet térã GeoJSON rupive.',
		],
		limitesTitle: 'Análisis límites rehegua',
		limitesWarning: 'Ko sección oĩporúva ha ojerure ojelee mba\'e peteĩ pyahúpe nealab ojeporu mboyve mba\'e peteĩ decisión consecuencias reales oĩva rehegua.',
		limitesP1: '<strong>nealab oĩ herramienta analítica, no prescriptiva.</strong> Mba\'e peteĩ análisis plataforma-pe ndoikói recomendación de acción, certificación técnica ni consultoría profesional. Scores, tipologías ha rankings oĩ síntesis cuantitativa variables observables percepción remota, censos ha fuentes administrativas-gui. Ndoñemoĩri experto rekotee ni responsabilidad de quien decide.</p>',
		limitesP2: '<strong>Sin garantía de exactitud.</strong> Plataforma ha información oĩva oñemoĩ as-is, sin garantías exactitud, completitud, actualización ha idoneidad propósito particular-pe. Mba\'ekuaa satelital, censal ha administrativo ikatu oĩ errores, desfasajes temporales ha limitaciones metodológicas ficha técnica-pe oñembyaikuaáva.',
		limitesP3: '<strong>Mba\'e peteĩ análisis geoespacial ndoñembyaikuaái trabajo de campo.</strong> Percepción remota oipuru condiciones físicas promedio ventanas temporales-pe; ndoipuruĩ procesos sociales, conflictos de uso, restricciones jurídicas ha cambios recientes. Capas nealab-pe ojejerure validación técnicos-pe ha responsables-pe situación local oikuaáva.',
		limitesP4: 'Zona oñemboguapýva alta aptitud agrícola oĩ ikatu restricciones de uso, regímenes de tenencia ha condiciones locales mba\'ekuaa disponible-pe ndoĩhágui. Zona bajo riesgo histórico de inundación ikatu oĩ cambios hidrológicos recientes. Mba\'e apytépe, análisis geoespacial oĩ insumo diagnóstico, no resultado de política.',
		limitesP5: '<strong>Mba\'e peteĩ clasificación nealab-pe ojehechakuaáva oĩ hipótesis ojehekáva, no resultado definitivo.</strong> Uso responsable ojerure ojelee ficha metodológica análisis apytépe, ojekuaahéta limitaciones, ha oñemboikuaa análisis validación de campo ndive.',
		liabilityText: '<strong>Responsabilidad.</strong> Mba\'e peteĩ ñepyrũ ára oĩháre autor, CONICET ha UNaM ndoikói responsables daños directos, indirectos, incidentales ha consecuentes nealab ojeporu haguégui. Avave ojeporu plataforma gestión, inversión, investigación ha política pública-pe oñemboguapy responsabilidad upe uso haguégui ha ojejerure validación profesional independiente ndive.',
		termsLink: 'Términos y condiciones ojehecha →',
		fuentesTitle: 'Fuentes ha colaboraciones',
		fuentesP1: 'nealab oñemboikuaa mba\'ekuaa fuentes públicas-gui, oĩva: INDEC (Censo Nacional 2022), IGN, Catastro Misiones, JRC Global Surface Water, Hansen Global Forest Change, MODIS, MapBiomas, CHIRPS, ERA5, VIIRS, GHSL, SoilGrids, Sentinel/ESA/Copernicus, Global Building Atlas, Overture Maps, OpenStreetMap, Meta/WRI Canopy Height, GEDI L4B, ESA CCI Biomass, Global Forest Watch, PM2.5 Dalhousie/ACAG, EMSA, Oxford MAP, DGEEC Paraguay ha IBGE Brasil, ambuéva. Procesamiento Google Earth Engine-pe oñemboguapy, acceso <strong>Google Earth Engine Partner Tier</strong>-pe.',
		contactoTitle: 'Contacto',
		contactoContent: '<strong>Raimundo Elias Gomez</strong><br />Investigador CONICET · Facultad de Humanidades y Ciencias Sociales, Universidad Nacional de Misiones (Argentina)<br /><a href="mailto:nealab@spatia.ar">nealab@spatia.ar</a>',
		citationLabel: 'Omombe hag̃ua rehegua',
		affil: 'CONICET · FHyCS-UNaM · Google Earth Engine Partner Tier',
		printGenerated: 'Documento oñemosẽ {date}-pe spatia.ar/servicios-gui',
	},
};
