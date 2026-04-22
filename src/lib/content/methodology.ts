export interface MethodologyContent {
	howToRead: string;
	implications: string;
	method: string;
}

export const METHOD_COMPARABLE =
	'Normalización comparable: cada variable se normaliza con umbrales fijos (goalpost normalization, metodología UNDP-HDI) calculados sobre el universo pooled de ~490.000 hexágonos de ambos territorios. Un valor de 0 representa el umbral mínimo y 100 el máximo, independientemente del territorio. Esto garantiza que un score de 60 en Misiones tiene el mismo significado que un 60 en Itapúa.\n\nTipos (clusters): las variables normalizadas se procesan con PCA para validar independencia (se descartan variables con |r| > 0.70). Luego k-means agrupa hexágonos con perfiles multivariados similares. Cada hexágono se asigna al tipo cuyo centroide es más cercano. La calidad se valida con coeficiente de silueta. Los tipos no son un ranking — son perfiles cualitativos distintos.';

export const METHOD_COMMON =
	'Valores por variable (0–100): cada variable se convierte a percentil dentro del territorio analizado. 50 = mediana del territorio, 100 = valor más alto del territorio.\n\nTipos (clusters): las variables estandarizadas se procesan con PCA para validar independencia (se descartan variables con |r| > 0.70). Luego k-means agrupa hexágonos con perfiles multivariados similares. Cada hexágono se asigna al tipo cuyo centroide es más cercano. La calidad se valida con coeficiente de silueta. Los tipos no son un ranking — son perfiles cualitativos distintos.';

export const ANALYSIS_CONTENT: Record<string, MethodologyContent> = {
	flood_risk: {
		howToRead:
			'Los colores representan el riesgo hídrico de cada hexágono, combinando la presencia histórica de agua (JRC, 1984–2021) y la detección actual de inundación (Sentinel-1 SAR). Azul oscuro = riesgo bajo; amarillo = riesgo medio; rojo = riesgo alto. Comparable entre Misiones e Itapúa con umbrales fijos (ocurrencia 0–100%, recurrencia 0–100%, extensión 0–100%). Selecciona un departamento para ver el detalle.',
		implications:
			'Las zonas de riesgo alto pueden enfrentar anegamientos recurrentes, afectando el valor inmobiliario, la habitabilidad y la infraestructura de servicios básicos (agua, cloacas). La recurrencia interanual distingue inundaciones estacionales predecibles de eventos extremos esporádicos.',
		method:
			'Índice compuesto 0–100: media geométrica de presencia histórica de agua (JRC Global Surface Water, Landsat 1984–2021), recurrencia interanual (JRC) y extensión actual (Sentinel-1 SAR, última imagen procesada). Normalización goalpost con umbrales fijos: ocurrencia [0, 100]%, recurrencia [0, 100]%, extensión [0, 100]%. Fuentes: JRC v1.4 + Copernicus Sentinel-1. Resolución: H3 resolución 9.',
	},
	territorial_scores: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de consolidación urbana según 8 indicadores derivados de Overture Maps: pavimentación, consolidación, acceso a servicios, vitalidad comercial, conectividad vial, mezcla edilicia, urbanización y exposición hídrica. Cada color representa un perfil urbano distinto.',
		implications:
			'Los tipos permiten distinguir núcleos urbanos consolidados, periferias en expansión con servicios incompletos, y zonas rurales sin infraestructura urbana. La clasificación multivariada evita reducir la complejidad urbana a un único indicador de "desarrollo".',
		method: `${METHOD_COMPARABLE} 8 variables: paving_index, urban_consolidation, service_access, commercial_vitality, road_connectivity, building_mix, urbanization, water_exposure. Fuente: Overture Maps Foundation (CC BY 4.0, release 2026-03-18) vía walkthru.earth. k=5 tipos.`,
	},
	environmental_risk: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de riesgo ambiental según la co-ocurrencia de frecuencia de fuego, deforestación, amplitud térmica, pendiente y altura sobre drenaje. Cada color representa un tipo distinto de configuración de riesgo. Comparable entre Misiones e Itapúa.',
		implications:
			'Los tipos permiten identificar configuraciones de riesgo cualitativamente distintas: zonas de alta pendiente con baja deforestación difieren estructuralmente de zonas planas con alta pérdida forestal, aunque ambas puedan tener "riesgo" similar en un índice único.',
		method: `${METHOD_COMPARABLE} 5 variables con goalposts fijos: frecuencia de fuego [0, 8] eventos/año, deforestación total [0, 15]%, amplitud térmica LST [2, 25]°C, pendiente [0, 30]°, HAND [0, 200] m. Fuentes: MODIS MCD64A1 (fuego), Hansen GFC v1.12 (deforestación), ERA5 (LST), FABDEM 30m (pendiente), MERIT Hydro (HAND). Período: 2019–2024.`,
	},
	climate_comfort: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos climáticos según la co-ocurrencia de temperatura diurna, precipitación, heladas y estrés hídrico. Cada color representa un régimen climático distinto. Comparable entre Misiones e Itapúa.',
		implications:
			'Los tipos climáticos revelan gradientes geoespaciales que un índice único no captura: zonas cálidas y húmedas difieren estructuralmente de zonas frescas y secas, con implicancias distintas para habitabilidad y producción.',
		method: `${METHOD_COMPARABLE} 4 variables con goalposts fijos: temperatura diurna LST [15, 50]°C, precipitación anual [1444, 1961] mm/año, días de helada [0, 60] días/año, ratio ET/PET [0, 1]. Fuentes: ERA5 (temperatura, heladas), CHIRPS (precipitación), MODIS (ET/PET). Período: 2019–2024.`,
	},
	green_capital: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de productividad vegetal según la co-ocurrencia de verdor estacional (NDVI), cobertura arbórea, productividad primaria (NPP) y área foliar (LAI). Los valores altos no distinguen bosque nativo de cultivos: la soja en plena temporada puntúa igual o más que el monte secundario. Comparable entre Misiones e Itapúa.',
		implications:
			'La capa mide biomasa activa y productividad fotosintética, no calidad ecológica ni servicios ecosistémicos. Un distrito con alta productividad vegetal puede ser un cinturón sojero; uno con baja productividad puede tener suelo desnudo por estacionalidad. Usar junto con deforestation_dynamics para contextualizar.',
		method: `${METHOD_COMPARABLE} 4 variables con goalposts fijos: NDVI [0.05, 0.90], cobertura arbórea [0, 100]%, NPP [0.52, 1.51] kgC/m²/8d, LAI [0, 7] m²/m². Fuentes: MODIS 250m (NDVI), Hansen GFC 2000 (treecover), MODIS MOD17A3 (NPP), MODIS MOD15A2H (LAI). Período: 2019–2024.`,
	},
	change_pressure: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de presión de cambio según la co-ocurrencia de tendencia de urbanización, expansión construida, pérdida forestal y cambio de vegetación. Comparable entre Misiones e Itapúa.',
		implications:
			'Los tipos separan urbanización activa de deforestación agrícola y de zonas estables. Un municipio con "alta presión" por urbanización requiere políticas distintas a uno con "alta presión" por avance de frontera agraria.',
		method: `${METHOD_COMPARABLE} 4 variables con goalposts fijos: tendencia VIIRS [−2, 5] nW/cm²/año, cambio GHSL [0, 42]%, pérdida forestal Hansen [0, 20]%, tendencia NDVI [−0.070, 0.090] /año. Fuentes: NOAA VIIRS 500m (2016–2025), JRC GHSL (2000 vs 2020), Hansen GFC v1.12 (2001–2024), MODIS NDVI (2019–2024).`,
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
			'El mapa clasifica cada hexágono en tipos de aptitud agrícola según la co-ocurrencia de calidad del suelo, régimen hídrico, acumulación térmica y topografía. Comparable entre Misiones e Itapúa.',
		implications:
			'Los tipos reflejan configuraciones edafoclimáticas distintas: suelos ácidos con alta lluvia (aptitud para yerba mate), suelos neutros con calor acumulado (aptitud para tabaco/cítricos), y zonas con limitaciones múltiples.',
		method: `${METHOD_COMPARABLE} 5 variables con goalposts fijos: carbono orgánico del suelo [0, 472] g/dm³, distancia a pH óptimo [0, 1.0], arcilla [0, 590] g/kg, precipitación anual [1444, 1961] mm/año, GDD base 10°C [3589, 4587] °C·día. Fuentes: SoilGrids v2 (ISRIC, 0–5cm), CHIRPS (precipitación), ERA5 (GDD), FABDEM (pendiente). Período: 2019–2024.`,
	},
	forest_health: {
		howToRead:
			'El mapa clasifica cada hexágono en tipos de integridad forestal según la co-ocurrencia de tendencia de verdor, ratio de pérdida arbórea, productividad fotosintética y evapotranspiración. Comparable entre Misiones e Itapúa.',
		implications:
			'Los tipos separan bosque sano y productivo, bosque en degradación con pérdida activa, y zonas sin cobertura forestal significativa. Esta clasificación permite priorizar intervenciones de restauración donde la degradación es incipiente.',
		method: `${METHOD_COMPARABLE} 4 variables con goalposts fijos: tendencia NDVI [−0.070, 0.090] /año, ratio pérdida/cobertura [0, 50]%, GPP [0.026, 0.065] kgC/m²/8d, ET [14.05, 30.79] mm/8d. Fuentes: MODIS NDVI 250m (tendencia 5 años), Hansen GFC v1.12 (loss/treecover2000), MODIS MOD17A2 (GPP), TerraClimate (ET). Período: 2019–2024.`,
	},
	forestry_aptitude: {
		howToRead:
			'El mapa muestra la similitud biofísica de cada hexágono con las plantaciones forestales que ya existen y prosperan en Misiones (Argentina). El valor es la probabilidad (0–100) estimada por un modelo de distribución de especie (SDM). Para Itapúa (Paraguay), el score es una extrapolación bioclimática del modelo entrenado en Misiones: indica qué tan similares son las condiciones de clima, suelo y terreno a las zonas silvícolas de Misiones, no una predicción calibrada con presencia local. Hexágonos sobre agua o urbano quedan sin pintar.',
		implications:
			'Score alto = condiciones análogas a zonas donde la silvicultura ya funciona en Misiones. Para Itapúa, interpretar como indicador de afinidad bioclimática transfronteriza. Es una capa descriptiva, no prescriptiva: NO dice dónde se puede plantar legalmente (eso depende de normativa nacional, tenencia, comunidades), ni garantiza rendimiento comercial, ni reemplaza estudios de campo.',
		method: `Random Forest (sklearn, 400 árboles, class_weight balanced) entrenado como SDM presencia-background con datos de Misiones: presencia = hexágonos MapBiomas Argentina clase silvicultura ≥50% (~27.600 hexes); background = muestra aleatoria (ratio 1:3). 23 covariables biofísicas a resolución H3: clima (ERA5 GDD, temperatura y radiación; CHIRPS precipitación y eventos extremos; TerraClimate déficit hídrico, VPD, humedad del suelo), suelo (SoilGrids arcilla/limo/arena/pH/SOC; HWSD drenaje, textura, profundidad radicular, AWC), terreno (SRTM pendiente, elevación, TWI, rugosidad), vegetación contextual (NDVI medio) y accesibilidad (tiempo a ciudad 50k). Heladas excluidas: en Misiones son 0–2 días/año, aportan ruido sin señal. Validación: Group K-Fold espacial (5 folds, bloques H3 res 5), AUC = 0.883 ± 0.010. Aplicación a otros territorios: extrapolación con las mismas covariables satelitales globales (no requiere presencia local). Tipos: k-means k=4 sobre covariables biofísicas de hexágonos con score ≥ 40.`,
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
			'El mapa clasifica cada hexágono según su cobertura dominante: selva nativa, plantación forestal, pastizal, agricultura, agua, humedal o urbano. Misiones usa MapBiomas Argentina Col. 1 (Landsat 30m); Itapúa usa MapBiomas Paraguay Col. 1. Nota: MapBiomas Paraguay Col. 1 no distingue plantación forestal, urbano ni mosaico agropecuario — estas clases aparecen como 0% en Itapúa. Las plantaciones forestales se incluyen dentro de bosque nativo; las áreas urbanas no se clasifican separadamente.',
		implications:
			'Misiones: selva nativa domina (~73% de hexes), con plantaciones forestales (~12%) y mosaicos agrícolas en el este y sur. Itapúa (PY): cultivos/soja (~40%) y pastizal natural (~14%) dominan, con selva nativa residual (~20%) concentrada en el norte y corredores riparios. La comparación revela el contraste entre la Selva Atlántica conservada y el frente agrícola paraguayo. Plantación forestal, urbano y mosaico muestran 0% en Itapúa por limitaciones de la clasificación MapBiomas Paraguay (ver nota arriba).',
		method: `${METHOD_COMPARABLE} Fuente: MapBiomas Argentina Collection 1 (Landsat 30m, 2022) para Misiones; MapBiomas Paraguay Collection 1 para Itapúa. Misiones: PCA + k=6 k-means sobre fracciones de cobertura por polígono H3 (silueta=0.62). Itapúa: muestreo centroide H3 + k=6 k-means (silueta=0.91). Clases unificadas: bosque nativo (incl. bosque inundable), plantación, pastizal, pastizal natural, agricultura, mosaico, humedal, urbano, agua, suelo desnudo.`,
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
			'El mapa clasifica cada hexágono en tipos de accesibilidad según la co-ocurrencia de tiempo de viaje a la capital departamental, a la ciudad más cercana, distancia a hospital, escuela y ruta principal. Cada color representa un nivel de conectividad distinto. Comparable entre Misiones e Itapúa: mismas fuentes y metodología.',
		implications:
			'Los tipos distinguen conectividad plena (cercanía a servicios y rutas), accesibilidad parcial (cerca de ruta pero lejos de servicios especializados), y aislamiento funcional (lejos de todo). La comparación entre territorios revela diferencias estructurales en conectividad según topografía y densidad vial.',
		method: `${METHOD_COMPARABLE} 5 variables con goalposts fijos: tiempo a capital [5, 500] min, tiempo a ciudad ≥50k [5, 350] min, distancia a hospital [0, 35] km, distancia a escuela [0, 20] km, distancia a ruta principal [0, 25] km. Capital = Posadas (MIS) / Encarnación (ITA), calculado vía MCP_Geometric sobre superficie de fricción Oxford MAP 2019. Fuentes: Oxford MAP friction_surface_2019 + accessibility_to_cities_2015 + OpenStreetMap (hospitales, escuelas, rutas).`,
	},
	carbon_stock: {
		howToRead:
			'El mapa muestra el stock de carbono total por hexágono (biomasa aérea + subterránea + carbono del suelo) y el balance anual de emisiones/remociones. Colores más intensos indican mayor stock. Los valores se muestran en unidades físicas (tC/ha, MgCO2/ha). Comparable entre Misiones e Itapúa.',
		implications:
			'Las zonas de alto stock con balance neto negativo (sumidero) son candidatas para créditos de carbono por conservación. Las zonas de alto stock con balance positivo (emisor) son prioridad para intervención REDD+. Las zonas de bajo stock con alta productividad (NPP) tienen potencial de restauración y secuestro futuro. *Valor teórico del carbono: estimación de referencia calculada como stock total x 3.67 (conversión C a CO2) x USD 10/tCO2e (mediana del mercado voluntario 2024, Ecosystem Marketplace 2024). No representa un precio de venta ni el valor realizable de un predio. La monetización efectiva requiere un proyecto certificado (VCS, Gold Standard) con línea base, adicionalidad demostrada y costos de transacción que reducen significativamente el valor neto.',
		method: `${METHOD_COMPARABLE} Score compuesto: media geométrica de biomasa aérea [0, 300] Mg/ha, carbono total [0, 400] tC/ha, carbono orgánico del suelo [0, 472] g/dm³ y flujo neto [−100, 100] MgCO2/ha. Biomasa aérea: ESA CCI Biomass v6 (100m, Santoro et al. 2024) + GEDI L4B lidar (1km, validación). Biomasa subterránea: Cairns et al. (1997): BGB = 0.489 × AGB^0.89. SOC: SoilGrids v2 (ISRIC, 0–30cm). Flujo de carbono: Harris et al. (2021) / Global Forest Watch (emisiones + remociones + balance neto, 30m, 2001–2024). Productividad: MODIS MOD17A3HGF NPP (500m, 2019–2024). Total carbon = AGB × 0.47 + BGB × 0.47 + SOC. Precio de referencia: Ecosystem Marketplace (2024).`,
	},
	climate_vulnerability: {
		howToRead:
			'El mapa clasifica cada hexágono según su vulnerabilidad climática integrada (framework IPCC AR5). Colores cálidos indican mayor vulnerabilidad: alta exposición a eventos extremos, alta sensibilidad ambiental, o baja capacidad adaptativa de la población. Comparable entre Misiones e Itapúa para las dimensiones de exposición y sensibilidad (fuentes satelitales). Nota: para territorios sin datos censales (ej. Itapúa), la capacidad adaptativa usa un valor neutral (50/100) — los componentes de aislamiento y privación de servicios requieren censos nacionales no disponibles para Paraguay.',
		implications:
			'Las zonas de alta vulnerabilidad integral requieren atención prioritaria en planes de adaptación climática. Las zonas con alta exposición pero buena capacidad adaptativa pueden absorber shocks; las zonas con baja capacidad adaptativa son vulnerables incluso ante exposición moderada. Este índice es el insumo estándar para fondos climáticos (GCF, GEF, Banco Mundial).',
		method: `${METHOD_COMPARABLE} 8 variables agrupadas en 3 dimensiones IPCC: Exposición (estrés térmico MODIS LST, riesgo inundación JRC/S1, estrés hídrico ET/PET, frecuencia fuego MODIS MCD64A1), Sensibilidad (pérdida forestal Hansen GFC, desprotección vegetal Hansen treecover), Capacidad Adaptativa (aislamiento geoespacial Oxford MAP, privación de servicios INDEC 2022 — solo Argentina; para otros territorios se asigna valor neutral 50/100). Sub-índices: media geométrica por dimensión. Score final: media geométrica de las 3 dimensiones. PCA + k-means para tipología.`,
	},
	pm25_drivers: {
		howToRead:
			'El mapa muestra la calidad del aire en cada hexágono, medida como concentración media de PM2.5 (partículas finas < 2.5 µm) y descompuesta en cuatro drivers: fuego regional, clima, terreno y vegetación. Score alto (colores fríos) = mejor calidad del aire; score bajo (colores cálidos) = mayor concentración de PM2.5. Comparable entre Misiones e Itapúa. Selecciona un departamento para ver la contribución relativa de cada driver.',
		implications:
			'La intensidad de fuego regional es el driver dominante de PM2.5: las quemas agrícolas y forestales en provincias vecinas y países limítrofes elevan la concentración de partículas finas incluso en zonas sin deforestación local. Las zonas con alta contribución climática son sensibles a eventos de inversión térmica que atrapan contaminantes. La vegetación actúa como filtro natural — la pérdida de cobertura arbórea reduce la capacidad de depuración del aire.',
		method:
			`Score de exposición normalizado con goalpost fijo: concentración media PM2.5 [5, 30] µg/m³ (0 = aire limpio, 100 = alta exposición). Descomposición por machine learning (LightGBM, SHAP feature attribution). Fuente primaria: Atmospheric Composition Analysis Group (ACAG) V6.GL.02 (Dalhousie University, van Donkelaar et al. 2021), panel 1998–2022, resolución 0.01° (~1 km). Modelo entrenado con 31 covariables ambientales (R² = 0.93 en validación cruzada espacial leave-one-department-out). Drivers agrupados por SHAP: fuego regional (contribución dominante, ΔR² = 0.195), clima (precipitación, temperatura), terreno (elevación, pendiente) y vegetación (NDVI, NPP). El toggle temporal compara periodo 2001–2010 vs 2013–2022. Resolución espacial: H3 resolución 9.`,
	},
	productive_activity: {
		howToRead:
			'El mapa muestra la intensidad de actividad productiva medida por luces nocturnas satelitales (VIIRS). Colores cálidos = mayor radiancia nocturna = mayor actividad económica. Al hacer click se ven 6 indicadores en valores reales: luces, productividad vegetal, verdor, superficie construida, conversión forestal y temperatura. El toggle temporal compara con el periodo base (2014–2017 para VIIRS, 2005–2012 para otros indicadores). Comparable entre Misiones e Itapúa.',
		implications:
			'Las zonas con alta radiancia nocturna y crecimiento positivo (delta > 0) son polos económicos en expansión. Zonas con alta productividad vegetal (NPP) pero baja radiancia son áreas rurales productivas pero no urbanizadas. Un aumento de temperatura superficial (LST) junto con aumento de superficie construida indica urbanización activa. La conversión forestal alta combinada con baja actividad económica puede indicar deforestación sin desarrollo productivo asociado.',
		method:
			`Score de actividad normalizado con goalpost fijo: radiancia nocturna VIIRS [0, 15] nW/cm²/sr (0 = sin actividad, 100 = alta actividad). Seis indicadores satelitales en valores físicos reales: VIIRS nightlights (NOAA, 500m, 2014–2025): radiancia media nocturna. NPP (MODIS, 1km, 2005–2024): productividad primaria neta en gC/m²/año. NDVI (MODIS, 250m, 2005–2024): índice de vegetación. GHSL built surface (JRC, 10m, epochs 2000/2020): fracción construida. Hansen forest loss (UMD/Landsat, 30m, 2001–2024): pérdida acumulada. LST (MODIS, 1km, 2005–2024): temperatura superficial diurna °C. Muestreo bilinear al centroide de cada hexágono H3 resolución 9 (~0.1 km²).`,
	},
	deforestation_dynamics: {
		howToRead:
			'Cada hexágono muestra la tasa de pérdida forestal observada en ese punto exacto (pixel Landsat 30m). Colores cálidos = mayor pérdida forestal reciente (2015–2024). El toggle temporal permite comparar con la línea base (2001–2010): el modo "Cambio" muestra si la deforestación aceleró (rojo) o frenó (verde) respecto al periodo base. Comparable entre Misiones e Itapúa.',
		implications:
			'Las zonas con alta tasa de pérdida sostenida representan frentes de deforestación activos donde la conversión del bosque nativo continúa. Las zonas donde la deforestación frenó (delta negativo) pueden reflejar el efecto de regulación ambiental (Ley de Bosques en Argentina, leyes forestales en Paraguay) o el agotamiento del recurso. Las zonas que aceleraron requieren atención prioritaria de fiscalización.',
		method:
			`Score de deforestación normalizado con goalpost fijo: tasa de pérdida anual [0, 5] %/año (0 = sin pérdida, 100 = pérdida máxima). Fuente: Hansen Global Forest Change v1.12 (University of Maryland / Google), derivado de series temporales Landsat a 30m, cobertura 2001–2024. Estadísticas zonales verdaderas: cada hexágono H3 resolución 9 (~0.1 km²) recibe el conteo de píxeles de pérdida por año dentro de su polígono (no centroide). La tasa se calcula como fracción de píxeles con pérdida detectada en cada periodo. Línea base: 2001–2010; actual: 2015–2024. Pérdida acumulada goalpost: [0, 40]%. Actualización automática vía GitHub Actions cuando Hansen publica nuevos datos (~abril de cada año).`,
	},
};

export function getMethodologyContent(analysisId: string): MethodologyContent | null {
	return ANALYSIS_CONTENT[analysisId] ?? null;
}

export function listMethodologyIds(): string[] {
	return Object.keys(ANALYSIS_CONTENT);
}
