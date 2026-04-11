export interface MethodologyContent {
	howToRead: string;
	implications: string;
	method: string;
}

export const METHOD_COMMON =
	'Clasificación por PCA (análisis de componentes principales) seguido de k-means clustering sobre las variables estandarizadas. Cada hexágono se asigna al tipo cuyo centroide multivariado es más cercano. La validación se realiza mediante coeficiente de silueta. Los valores por variable van de 0 a 100 y representan el percentil provincial: 50 = mediana de Misiones, 100 = valor más alto de la provincia. Los tipos (clusters) agrupan hexágonos con perfiles similares — no son un ranking lineal.';

export const ANALYSIS_CONTENT: Record<string, MethodologyContent> = {
	flood_risk: {
		howToRead:
			'Los colores representan el riesgo hídrico de cada hexágono, combinando la presencia histórica de agua (JRC, 1984–2021) y la detección actual de inundación (Sentinel-1 SAR). Azul oscuro = riesgo bajo; amarillo = riesgo medio; rojo = riesgo alto. Selecciona un departamento para ver el detalle.',
		implications:
			'Las zonas de riesgo alto pueden enfrentar anegamientos recurrentes, afectando el valor inmobiliario, la habitabilidad y la infraestructura de servicios básicos (agua, cloacas). La recurrencia interanual distingue inundaciones estacionales predecibles de eventos extremos esporádicos.',
		method:
			'Índice compuesto 0–100 (donde 0 = sin riesgo y 100 = máximo riesgo provincial): 50% presencia histórica de agua (JRC Global Surface Water, Landsat 1984–2021) + 20% recurrencia interanual (JRC) + 30% extensión actual (Sentinel-1 SAR, última imagen procesada). Fuentes: JRC v1.4 + Copernicus Sentinel-1. Resolución: H3 resolución 9.',
	},
	territorial_scores: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de consolidación urbana según 8 indicadores derivados de Overture Maps: pavimentación, consolidación, acceso a servicios, vitalidad comercial, conectividad vial, mezcla edilicia, urbanización y exposición hídrica. Cada color representa un perfil urbano distinto.',
		implications:
			'Los tipos permiten distinguir núcleos urbanos consolidados, periferias en expansión con servicios incompletos, y zonas rurales sin infraestructura urbana. La clasificación multivariada evita reducir la complejidad urbana a un único indicador de "desarrollo".',
		method: `${METHOD_COMMON} 8 variables: paving_index, urban_consolidation, service_access, commercial_vitality, road_connectivity, building_mix, urbanization, water_exposure. Fuente: Overture Maps Foundation (CC BY 4.0, release 2026-03-18) vía walkthru.earth. k=5 tipos.`,
	},
	environmental_risk: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de riesgo ambiental según la co-ocurrencia de deforestación, amplitud térmica, pendiente y altura sobre drenaje. Cada color representa un tipo distinto de configuración de riesgo.',
		implications:
			'Los tipos permiten identificar configuraciones de riesgo cualitativamente distintas: zonas de alta pendiente con baja deforestación difieren estructuralmente de zonas planas con alta pérdida forestal, aunque ambas puedan tener "riesgo" similar en un índice único.',
		method: `${METHOD_COMMON} Variables: deforestación Hansen GFC, amplitud térmica LST MODIS, pendiente FABDEM 30m, HAND MERIT Hydro. k=5 tipos, silueta=0.33.`,
	},
	climate_comfort: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos climáticos según la co-ocurrencia de temperatura diurna, nocturna, precipitación, heladas y estrés hídrico. Cada color representa un régimen climático distinto.',
		implications:
			'Los tipos climáticos revelan gradientes geoespaciales que un índice único no captura: zonas cálidas y húmedas difieren estructuralmente de zonas frescas y secas, con implicancias distintas para habitabilidad y producción.',
		method: `${METHOD_COMMON} Variables: LST diurno/nocturno MODIS, precipitación CHIRPS, heladas ERA5, ratio ET/PET MODIS. k=4 tipos, silueta=0.40.`,
	},
	green_capital: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de capital verde según la co-ocurrencia de verdor, cobertura arbórea, productividad primaria, área foliar y fracción de vegetación. Cada color representa un estado ecosistémico distinto.',
		implications:
			'Los tipos distinguen selva densa de alta productividad, bosque secundario con cobertura residual, y zonas deforestadas con baja vegetación. Esta distinción cualitativa informa mejor las políticas de conservación que un gradiente continuo.',
		method: `${METHOD_COMMON} Variables: NDVI MODIS 250m, cobertura arbórea Hansen 2000, NPP MODIS, LAI MODIS, VCF MODIS. k=3 tipos, silueta=0.46.`,
	},
	change_pressure: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de presión de cambio según la co-ocurrencia de tendencia de urbanización, expansión construida, pérdida forestal y cambio de vegetación.',
		implications:
			'Los tipos separan urbanización activa de deforestación agrícola y de zonas estables. Un municipio con "alta presión" por urbanización requiere políticas distintas a uno con "alta presión" por avance de frontera agraria.',
		method: `${METHOD_COMMON} Variables: tendencia VIIRS 2016-2025, cambio GHSL 2000-2020, pérdida Hansen, tendencia NDVI. k=5 tipos, silueta=0.34.`,
	},
	location_value: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de valor posicional según la co-ocurrencia de accesibilidad, conectividad a salud, actividad económica, topografía y distancia a rutas.',
		implications:
			'Los tipos distinguen núcleos urbanos bien conectados, periferias accesibles pero poco activas, y zonas rurales aisladas. El valor posicional emergente de la clasificación es más informativo que un ranking lineal.',
		method: `${METHOD_COMMON} Variables: tiempo a ciudad 20k Nelson, acceso a salud Oxford, radiancia VIIRS, pendiente FABDEM, distancia a ruta OSM. k=4 tipos, silueta=0.43.`,
	},
	agri_potential: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de aptitud agrícola según la co-ocurrencia de calidad del suelo, régimen hídrico, acumulación térmica y topografía.',
		implications:
			'Los tipos reflejan configuraciones edafoclimáticas distintas: suelos ácidos con alta lluvia (aptitud para yerba mate), suelos neutros con calor acumulado (aptitud para tabaco/cítricos), y zonas con limitaciones múltiples.',
		method: `${METHOD_COMMON} Variables: carbono orgánico SoilGrids, pH óptimo, arcilla, precipitación CHIRPS, GDD ERA5, pendiente FABDEM. k=3 tipos, silueta=0.32.`,
	},
	forest_health: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de integridad forestal según la co-ocurrencia de tendencia de verdor, pérdida arbórea, productividad fotosintética y evapotranspiración.',
		implications:
			'Los tipos separan bosque sano y productivo, bosque en degradación con pérdida activa, y zonas sin cobertura forestal significativa. Esta clasificación permite priorizar intervenciones de restauración donde la degradación es incipiente.',
		method: `${METHOD_COMMON} Variables: tendencia NDVI 5 años, ratio pérdida/cobertura Hansen, GPP MODIS, ET MODIS. k=4 tipos, silueta=0.38.`,
	},
	forestry_aptitude: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de aptitud forestal comercial según la co-ocurrencia de acidez del suelo, precipitación, pendiente, y accesibilidad logística.',
		implications:
			'Los tipos identifican zonas óptimas para plantaciones de pino/eucalipto (suelo ácido, lluvia suficiente, pendiente mecanizable, cerca de rutas) frente a zonas marginales donde la forestación comercial no es viable. Este análisis evalúa aptitud del suelo y clima — no reemplaza la verificación de restricciones legales (áreas protegidas, comunidades indígenas, Ley de Bosques 26.331).',
		method: `${METHOD_COMMON} Variables: pH SoilGrids, arcilla, precipitación CHIRPS, pendiente FABDEM, distancia a ruta OSM, accesibilidad Nelson. k=3 tipos, silueta=0.33.`,
	},
	service_deprivation: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de carencia de servicios básicos según NBI, acceso a cloacas, calidad del piso, hacinamiento y acceso digital. Solo se muestran hexágonos con edificaciones detectadas (crosswalk dasimétrico). Cada color representa un perfil de carencia distinto.',
		implications:
			'Los tipos separan carencia habitacional (piso inadecuado + hacinamiento), carencia de infraestructura (sin cloacas), y brecha digital (sin computadora). Cada configuración demanda intervenciones distintas: vivienda social, extensión de red cloacal, o programas de inclusión digital.',
		method: `${METHOD_COMMON} 6 variables Censo Nacional 2022 (INDEC): NBI, sin cloacas (100 - pct_cloacas), piso inadecuado, hacinamiento, hacinamiento crítico, sin computadora (100 - pct_computadora). Crosswalk dasimétrico ponderado por edificios (2.8M footprints). KMO=0.73.`,
	},
	territorial_isolation: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de aislamiento geoespacial según tiempo de viaje a ciudades y centros de salud, distancia a rutas, densidad vial, luces nocturnas y densidad poblacional. Cobertura completa de la provincia (crosswalk híbrido).',
		implications:
			'Los tipos distinguen aislamiento por distancia (lejos de rutas y ciudades), aislamiento funcional (cerca de ruta pero sin servicios), y conectividad plena. Las zonas aisladas enfrentan costos de transporte, acceso limitado a salud y educación, y menor oportunidad económica.',
		method: `${METHOD_COMMON} 6 variables: acceso a ciudades y salud (Oxford MAP 2019, fricción motorizada), distancia a ruta primaria y densidad vial (OSM), radiancia VIIRS 2022-2024, densidad poblacional Censo 2022. Crosswalk híbrido (dasimétrico + areal). KMO=0.87.`,
	},
	health_access: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de acceso a salud según tiempo al centro de salud, cobertura sanitaria, vulnerabilidad social (NBI), presión demográfica (ancianos y menores) y densidad poblacional. Solo hexágonos con edificaciones.',
		implications:
			'Los tipos separan déficit por distancia (zonas rurales lejanas), déficit por saturación (zonas densas con alta proporción de población vulnerable), y déficit por cobertura (alto NBI con baja cobertura sanitaria). Cada configuración requiere respuestas distintas del sistema de salud.',
		method: `${METHOD_COMMON} 6 variables: tiempo motorizado a salud (Oxford MAP 2019), cobertura sanitaria, NBI, % adultos mayores, % menores 18, densidad poblacional (Censo 2022). Crosswalk dasimétrico. KMO=0.60.`,
	},
	education_capital: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de capital educativo según el nivel de instrucción acumulado: sin instrucción, secundario completo o más, educación superior (terciario + universitario), y universitario. Solo hexágonos con edificaciones.',
		implications:
			'Los tipos distinguen zonas con alto capital humano (universidades cercanas, alta formación), zonas de educación media (secundario completo pero sin terciario), y zonas de bajo capital (alta proporción sin instrucción). El capital educativo es predictor de ingresos, salud y participación cívica.',
		method: `${METHOD_COMMON} 4 variables Censo 2022: % sin instrucción, % secundario completo o más (umbral acumulativo), % educación superior (terciario + universitario), % universitario. Terciario y universitario son tracks paralelos en el sistema argentino. Crosswalk dasimétrico. KMO=0.71.`,
	},
	education_flow: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de desempeño del sistema educativo según inasistencia escolar primaria (6-12), secundaria (13-18) y maternidad adolescente. Solo hexágonos con edificaciones.',
		implications:
			'Los tipos separan deserción temprana (primaria), deserción tardía (secundaria) y embarazo adolescente como factor de exclusión educativa. La inasistencia primaria indica fallas básicas del sistema; la secundaria indica problemas de retención; la maternidad adolescente indica vulnerabilidad de género intersectada con pobreza.',
		method: `${METHOD_COMMON} 3 variables Censo 2022: tasa de inasistencia 6-12 años, tasa de inasistencia 13-18 años, tasa de maternidad adolescente. Variables directas (mayor = peor flujo). Crosswalk dasimétrico. KMO=0.61.`,
	},
	land_use: {
		howToRead:
			'El mapa clasifica cada hexágono según su cobertura dominante: selva nativa, plantación forestal, pastizal, agricultura, agua o urbano. La fuente es MapBiomas Argentina (Landsat 30m, 2022) que distingue bosque nativo de silvicultura.',
		implications:
			'La separación entre selva nativa (73%) y plantación forestal (12%) permite evaluar el estado de conservación real: los pinares/eucaliptos no son selva paranaense aunque Dynamic World los clasifique igual. Los mosaicos agropecuarios indican zonas de transición activa.',
		method: `${METHOD_COMMON} Fuente: MapBiomas Argentina Collection 1 (Landsat 30m, 2022). Clases remapeadas: bosque nativo, plantación, pastizal, agricultura, mosaico, humedal, urbano, agua. k=6 tipos, silueta=0.62.`,
	},
	powerline_density: {
		howToRead:
			'Mapa de densidad de líneas de media y alta tensión. Hexágonos más claros = mayor densidad de infraestructura eléctrica. Score basado en longitud total y cantidad de líneas dentro de cada hexágono.',
		implications:
			'La cobertura eléctrica condiciona toda actividad productiva y residencial. Zonas con baja densidad de líneas requieren extensión de red para habilitar nuevos emprendimientos. La distancia a líneas existentes es el principal factor de costo de electrificación rural.',
		method:
			'Fuente: EMSA (Secretaría de Energía, datos.energia.gob.ar, abril 2024). Líneas de media y alta tensión georreferenciadas, intersectadas con grilla H3 resolución 9. Score = longitud total de líneas / área del hexágono, normalizado 0-100.',
	},
	territorial_types: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos geoespaciales según su metabolismo ecosistémico: productividad, apropiación humana y dinámica de cambio. Cada color representa un tipo cualitativamente distinto de territorio.',
		implications:
			'Los tipos geoespaciales sintetizan 13 variables satelitales en una clasificación interpretable. Permiten identificar selva productiva intacta, mosaicos agro-forestales en transición, zonas agrícolas consolidadas, periurbanos en expansión y núcleos urbanos — cada uno con necesidades de gestión distintas.',
		method: `${METHOD_COMMON} 13 variables: NPP, NDVI, cobertura arbórea, fracción arboles/cultivos/construido, deforestación, luces nocturnas, tendencia VIIRS, expansión GHSL, precipitación. k=8 tipos. Fuentes: MODIS, Hansen GFC, VIIRS, GHSL, CHIRPS.`,
	},
	sociodemographic: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos sociodemográficos según la co-ocurrencia de densidad poblacional, pobreza (NBI), hacinamiento, tenencia de vivienda, tamaño de hogar y acceso digital. Cada color representa un perfil censal distinto.',
		implications:
			'Los tipos distinguen zonas urbanas densas con bajo NBI, periferias con hacinamiento y pobreza, y zonas rurales dispersas con alta propiedad pero baja conectividad. Esta clasificación multivariada evita reducir la complejidad social a un solo indicador.',
		method: `${METHOD_COMMON} 6 variables del Censo Nacional 2022 (INDEC): densidad hab/km², % NBI, % hacinamiento, % propietarios, tamaño medio hogar, % computadora. Variables a nivel radio censal, agregadas a H3 vía crosswalk ponderado por área.`,
	},
	economic_activity: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de actividad económica según la co-ocurrencia de empleo, actividad económica, formación universitaria, luces nocturnas y densidad edilicia. Cada color representa un nivel de dinamismo distinto.',
		implications:
			'Los tipos separan centros económicos consolidados (alto empleo + universitarios + luces), periferias activas con posible informalidad (alta actividad, bajo empleo formal), y zonas rurales de baja actividad económica. La radiancia nocturna (VIIRS) es un proxy robusto de actividad que complementa los datos censales.',
		method: `${METHOD_COMMON} 5 variables: tasa de empleo y actividad (Censo 2022 INDEC, 14+ años), % universitarios (Censo 2022), radiancia media VIIRS 500m (2022-2024), densidad edilicia Global Building Atlas 2025. Variables censales agregadas a H3 vía crosswalk.`,
	},
	eudr: {
		howToRead:
			'El mapa muestra el riesgo de deforestación post-2020 por hexágono (H3 res-7, ~5 km²). Score alto (rojo) = mayor pérdida forestal o actividad de fuego después del cutoff EUDR (31/12/2020). Cobertura: 10 provincias del NOA y NEA argentino.',
		implications:
			'Hexágonos con deforestación post-2020 representan riesgo de no-conformidad bajo la Regulación (UE) 2023/1115. Exportaciones de commodities (soja, carne, madera) originados en estas zonas requieren due diligence reforzado. Este análisis es orientativo — la verificación formal requiere geometría parcelaria exacta.',
		method:
			'Score compuesto 0-100: 70% pérdida forestal post-2020 (Hansen GFC v1.12, Landsat 30m) + 20% área quemada post-2020 (MODIS MCD64A1, 500m) + 10% pérdida de cobertura previa. Cutoff EUDR: 31/12/2020. Resolución espacial: H3 resolución 7 (~5.16 km²). Cobertura: Salta, Jujuy, Tucumán, Catamarca, Sgo. del Estero, Formosa, Chaco, Corrientes, Misiones, Entre Ríos.',
	},
	accessibility: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de accesibilidad según la co-ocurrencia de tiempo de viaje a Posadas, a la cabecera departamental, distancia a hospital, escuela secundaria y ruta principal. Cada color representa un nivel de conectividad distinto.',
		implications:
			'Los tipos distinguen conectividad plena (cercanía a servicios y rutas), accesibilidad parcial (cerca de ruta pero lejos de servicios especializados), y aislamiento funcional (lejos de todo). Cada configuración requiere estrategias de inversión en infraestructura distintas.',
		method: `${METHOD_COMMON} 5 variables: tiempo motorizado a Posadas y cabecera (Nelson et al. 2019, superficie de fricción Oxford MAP), distancia euclidiana a hospital, escuela secundaria y ruta primaria (OSM). Fuente: Nelson 2019 + Oxford MAP 2019 + OSM.`,
	},
	carbon_stock: {
		howToRead:
			'El mapa muestra el stock de carbono total por hexágono (biomasa aérea + subterránea + carbono del suelo) y el balance anual de emisiones/remociones. Colores más intensos indican mayor stock. Los valores se muestran en unidades físicas (tC/ha, MgCO2/ha).',
		implications:
			'Las zonas de alto stock con balance neto negativo (sumidero) son candidatas para créditos de carbono por conservación. Las zonas de alto stock con balance positivo (emisor) son prioridad para intervención REDD+. Las zonas de bajo stock con alta productividad (NPP) tienen potencial de restauración y secuestro futuro. *Valor teórico del carbono: estimación de referencia calculada como stock total x 3.67 (conversión C a CO2) x USD 10/tCO2e (mediana del mercado voluntario 2024, Ecosystem Marketplace 2024). No representa un precio de venta ni el valor realizable de un predio. La monetización efectiva requiere un proyecto certificado (VCS, Gold Standard) con línea base, adicionalidad demostrada y costos de transacción que reducen significativamente el valor neto.',
		method: `${METHOD_COMMON} 10 variables: biomasa aérea ESA CCI Biomass v6 (100m, Santoro et al. 2024) + GEDI L4B lidar (1km, validación). Biomasa subterránea vía Cairns et al. (1997): BGB = 0.489 x AGB^0.89. Carbono orgánico del suelo: SoilGrids v2 (ISRIC, 0-30cm extrapolado). Flujo de carbono: Harris et al. (2021) Nature Climate Change / Global Forest Watch (emisiones brutas + remociones + balance neto, 30m, 2001-2024). Productividad: MODIS MOD17A3HGF NPP (500m, 2019-2024). Total carbon = AGB x 0.47 + BGB x 0.47 + SOC. Precio de referencia: Ecosystem Marketplace (2024) State of the Voluntary Carbon Markets.`,
	},
	climate_vulnerability: {
		howToRead:
			'El mapa clasifica cada hexágono según su vulnerabilidad climática integrada (framework IPCC AR5). Colores cálidos indican mayor vulnerabilidad: alta exposición a eventos extremos, alta sensibilidad ambiental, o baja capacidad adaptativa de la población. Cada tipo representa una configuración distinta de estos tres factores.',
		implications:
			'Las zonas de alta vulnerabilidad integral requieren atención prioritaria en planes de adaptación climática. Las zonas con alta exposición pero buena capacidad adaptativa pueden absorber shocks; las zonas con baja capacidad adaptativa son vulnerables incluso ante exposición moderada. Este índice es el insumo estándar para fondos climáticos (GCF, GEF, Banco Mundial).',
		method: `${METHOD_COMMON} 8 variables agrupadas en 3 dimensiones IPCC: Exposición (estrés térmico MODIS LST, riesgo inundación JRC/S1, estrés hídrico ET/PET, frecuencia fuego MODIS MCD64A1), Sensibilidad (pérdida forestal Hansen GFC, desprotección vegetal Hansen treecover), Capacidad Adaptativa (aislamiento geoespacial Oxford MAP, privación de servicios INDEC 2022). Sub-índices: media geométrica por dimensión. Score final: media geométrica de las 3 dimensiones. PCA + k-means para tipología.`,
	},
	pm25_drivers: {
		howToRead:
			'El mapa muestra la calidad del aire en cada hexágono, medida como concentración media de PM2.5 (partículas finas < 2.5 µm) y descompuesta en cuatro drivers: fuego regional, clima, terreno y vegetación. Score alto (colores fríos) = mejor calidad del aire; score bajo (colores cálidos) = mayor concentración de PM2.5. Selecciona un departamento para ver la contribución relativa de cada driver.',
		implications:
			'La intensidad de fuego regional es el driver dominante de PM2.5 en Misiones: las quemas agrícolas y forestales en provincias vecinas y países limítrofes elevan la concentración de partículas finas incluso en zonas sin deforestación local. Las zonas con alta contribución climática son sensibles a eventos de inversión térmica que atrapan contaminantes. La vegetación actúa como filtro natural — la pérdida de cobertura arbórea reduce la capacidad de depuración del aire.',
		method:
			'Descomposición por machine learning (LightGBM, SHAP feature attribution) de la concentración media anual de PM2.5. Fuente primaria: Atmospheric Composition Analysis Group (ACAG) V6.GL.02 (Dalhousie University, van Donkelaar et al. 2021), panel 1998-2022, resolución 0.01 deg (~1 km). Modelo entrenado con 31 covariables ambientales (R2 = 0.93 en validación cruzada espacial leave-one-department-out). Drivers agrupados por SHAP: fuego regional (contribución dominante, dR2 = 0.195), clima (precipitación, temperatura), terreno (elevación, pendiente) y vegetación (NDVI, NPP). El toggle temporal compara periodo 2001-2010 vs 2013-2022. Resolución espacial: H3 resolución 9.',
	},
	productive_activity: {
		howToRead:
			'El mapa muestra la intensidad de actividad productiva medida por luces nocturnas satelitales (VIIRS). Colores cálidos = mayor radiancia nocturna = mayor actividad económica. Al hacer click se ven 6 indicadores en valores reales: luces, productividad vegetal, verdor, superficie construida, conversión forestal y temperatura. El toggle temporal compara con el periodo base (2014-2017 para VIIRS, 2005-2012 para otros indicadores).',
		implications:
			'Las zonas con alta radiancia nocturna y crecimiento positivo (delta > 0) son polos económicos en expansión. Zonas con alta productividad vegetal (NPP) pero baja radiancia son áreas rurales productivas pero no urbanizadas. Un aumento de temperatura superficial (LST) junto con aumento de superficie construida indica urbanización activa. La conversión forestal alta combinada con baja actividad económica puede indicar deforestación sin desarrollo productivo asociado.',
		method:
			'Seis indicadores satelitales en valores físicos reales (sin scores compuestos ni índices artificiales). VIIRS nightlights (NOAA, 500m, 2014-2025): radiancia media nocturna en nW/cm²/sr. NPP (MODIS, 1km, 2005-2024): productividad primaria neta en gC/m²/año. NDVI (MODIS, 250m, 2005-2024): índice de vegetación normalizado. GHSL built surface (JRC, 10m, epochs 2000/2020): fracción de superficie construida. Hansen forest loss (UMD/Landsat, 30m, 2001-2024): pérdida acumulada. LST (MODIS, 1km, 2005-2024): temperatura superficial diurna en grados Celsius. Cada hexágono H3 res-9 recibe el valor ponderado por la fracción de área del radio censal que lo cubre (crosswalk dasimétrico areal). El color del mapa representa el percentil provincial de la radiancia nocturna.',
	},
	deforestation_dynamics: {
		howToRead:
			'Cada hexágono muestra la tasa de pérdida forestal observada en ese punto exacto (pixel Landsat 30m). Colores cálidos = mayor pérdida forestal reciente (2015-2024). El toggle temporal permite comparar con la línea base (2001-2010): el modo "Cambio" muestra si la deforestación aceleró (rojo) o frenó (verde) respecto al periodo base.',
		implications:
			'Las zonas con alta tasa de pérdida sostenida representan frentes de deforestación activos donde la conversión del bosque nativo continúa. Las zonas donde la deforestación frenó (delta negativo) pueden reflejar el efecto de la Ley de Bosques (26.331/OTBN, vigente desde 2007) o el agotamiento del recurso. Las zonas que aceleraron post-2015 a pesar de la regulación requieren atención prioritaria de fiscalización.',
		method:
			'Fuente: Hansen Global Forest Change v1.12 (University of Maryland / Google), derivado de series temporales Landsat a 30m de resolución, cobertura 2001-2024. Cada hexágono H3 resolución 9 (~0.1 km²) recibe el valor del pixel de pérdida en su centroide — no hay promedio por radio censal. La tasa de pérdida se calcula como fracción de años con pérdida detectada en cada periodo. Línea base: 2001-2010; actual: 2015-2024. Actualización automática vía GitHub Actions cuando Hansen publica nuevos datos (~abril de cada año).',
	},
};

export function getMethodologyContent(analysisId: string): MethodologyContent | null {
	return ANALYSIS_CONTENT[analysisId] ?? null;
}

export function listMethodologyIds(): string[] {
	return Object.keys(ANALYSIS_CONTENT);
}
