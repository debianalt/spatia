import type { Locale } from '$lib/stores/i18n.svelte';

export interface LocalizedMethodologyContent {
	howToRead: Record<Locale, string>;
	implications: Record<Locale, string>;
	method: { es: string; en: string };
}

export const METHOD_COMPARABLE = {
	es: 'Normalización comparable: cada variable se normaliza con umbrales fijos (goalpost normalization, metodología UNDP-HDI) calculados sobre el universo pooled de ~490.000 hexágonos de ambos territorios. Un valor de 0 representa el umbral mínimo y 100 el máximo, independientemente del territorio. Esto garantiza que un score de 60 en Misiones tiene el mismo significado que un 60 en Itapúa.\n\nTipos (clusters): las variables normalizadas se procesan con PCA para validar independencia (se descartan variables con |r| > 0.70). Luego k-means agrupa hexágonos con perfiles multivariados similares. Cada hexágono se asigna al tipo cuyo centroide es más cercano. La calidad se valida con coeficiente de silueta. Los tipos no son un ranking — son perfiles cualitativos distintos.',
	en: 'Comparable normalisation: each variable is normalised using fixed goalposts (goalpost normalisation, UNDP-HDI methodology) calculated over the pooled universe of ~490,000 hexagons from both territories. A value of 0 represents the minimum threshold and 100 the maximum, regardless of territory. This ensures that a score of 60 in Misiones carries the same meaning as a 60 in Itapúa.\n\nTypes (clusters): normalised variables are processed with PCA to validate independence (variables with |r| > 0.70 are discarded). K-means then groups hexagons with similar multivariate profiles. Each hexagon is assigned to the type whose centroid is nearest. Quality is validated using the silhouette coefficient. Types are not a ranking — they are qualitatively distinct profiles.',
};

export const METHOD_COMMON = {
	es: 'Valores por variable (0–100): cada variable se convierte a percentil dentro del territorio analizado. 50 = mediana del territorio, 100 = valor más alto del territorio.\n\nTipos (clusters): las variables estandarizadas se procesan con PCA para validar independencia (se descartan variables con |r| > 0.70). Luego k-means agrupa hexágonos con perfiles multivariados similares. Cada hexágono se asigna al tipo cuyo centroide es más cercano. La calidad se valida con coeficiente de silueta. Los tipos no son un ranking — son perfiles cualitativos distintos.',
	en: 'Values per variable (0–100): each variable is converted to a percentile within the analysed territory. 50 = territory median, 100 = highest value in the territory.\n\nTypes (clusters): standardised variables are processed with PCA to validate independence (variables with |r| > 0.70 are discarded). K-means then groups hexagons with similar multivariate profiles. Each hexagon is assigned to the type whose centroid is nearest. Quality is validated using the silhouette coefficient. Types are not a ranking — they are qualitatively distinct profiles.',
};

export const ANALYSIS_CONTENT: Record<string, LocalizedMethodologyContent> = {
	flood_risk: {
		howToRead: {
			es: 'Los colores representan el riesgo hídrico de cada hexágono, combinando la presencia histórica de agua (JRC, 1984–2021) y la detección actual de inundación (Sentinel-1 SAR). Azul oscuro = riesgo bajo; amarillo = riesgo medio; rojo = riesgo alto. Comparable entre Misiones e Itapúa con umbrales fijos (ocurrencia 0–100%, recurrencia 0–100%, extensión 0–100%). Selecciona un departamento para ver el detalle.',
			en: 'Colours represent the flood risk of each hexagon, combining historical water presence (JRC, 1984–2021) with current flood detection (Sentinel-1 SAR). Dark blue = low risk; yellow = medium risk; red = high risk. Comparable between Misiones and Itapúa using fixed thresholds (occurrence 0–100%, recurrence 0–100%, extent 0–100%). Select a department to view details.',
			gn: "Pytã, sovy, sa'y ohechauka y-mandu'a riesgo hexágono ndive. Azul oscuro = michĩ riesgo; amarillo = mbyte riesgo; rojo = yvate riesgo. Ojoguáva Misiones ha Itapúa. Eiporavo departamento ehecha hag̃ua mba'ekuaa.",
			pt: 'As cores representam o risco hídrico de cada hexágono, combinando a presença histórica de água (JRC, 1984–2021) e a detecção atual de inundação (Sentinel-1 SAR). Azul escuro = baixo risco; amarelo = risco médio; vermelho = alto risco. Comparável entre Misiones e Itapúa com limiares fixos (ocorrência 0–100%, recorrência 0–100%, extensão 0–100%). Selecione um departamento para ver os detalhes.',
		},
		implications: {
			es: 'Las zonas de riesgo alto pueden enfrentar anegamientos recurrentes, afectando el valor inmobiliario, la habitabilidad y la infraestructura de servicios básicos (agua, cloacas). La recurrencia interanual distingue inundaciones estacionales predecibles de eventos extremos esporádicos.',
			en: 'High-risk zones may face recurrent flooding, affecting property values, habitability and basic service infrastructure (water, sanitation). Inter-annual recurrence distinguishes predictable seasonal floods from sporadic extreme events.',
			gn: "Yvate riesgo ndive oĩva pytu'u ikuai ko'ãva, imba'ete renda, óga oikohaguépe ha ykuaa joapy. Y oú jey jey ohechauka aramboty ymemoranduha mbarete.",
			pt: 'Zonas de alto risco podem enfrentar alagamentos recorrentes, afetando o valor imobiliário, a habitabilidade e a infraestrutura de serviços básicos (água, esgoto). A recorrência interanual distingue inundações sazonais previsíveis de eventos extremos esporádicos.',
		},
		method: {
			es: 'Índice compuesto 0–100: media geométrica de presencia histórica de agua (JRC Global Surface Water, Landsat 1984–2021), recurrencia interanual (JRC) y extensión actual (Sentinel-1 SAR, última imagen procesada). Normalización goalpost con umbrales fijos: ocurrencia [0, 100]%, recurrencia [0, 100]%, extensión [0, 100]%. Fuentes: JRC v1.4 + Copernicus Sentinel-1. Resolución: H3 resolución 9.',
			en: 'Composite index 0–100: geometric mean of historical water presence (JRC Global Surface Water, Landsat 1984–2021), inter-annual recurrence (JRC) and current extent (Sentinel-1 SAR, last processed image). Goalpost normalisation with fixed thresholds: occurrence [0, 100]%, recurrence [0, 100]%, extent [0, 100]%. Sources: JRC v1.4 + Copernicus Sentinel-1. Resolution: H3 resolution 9.',
		},
	},
	territorial_scores: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de consolidación urbana según 8 indicadores derivados de Overture Maps: pavimentación, consolidación, acceso a servicios, vitalidad comercial, conectividad vial, mezcla edilicia, urbanización y exposición hídrica. Cada color representa un perfil urbano distinto.',
			en: 'The map classifies each hexagon into urban consolidation types based on 8 indicators derived from Overture Maps: paving, consolidation, service access, commercial vitality, road connectivity, building mix, urbanisation and water exposure. Each colour represents a distinct urban profile.',
			gn: "Mapa oipurúva oñemomba'e hexágono tëtã mba'e rehegua 8 indicadores Overture Maps ndive: pavimentación, consolidación, servicios, vitalidad comercial, tape, óga, urbanización ha y-riesgo. Peteĩ-peteĩ pytã ohechauka peteĩ perfil tëtã.",
			pt: 'O mapa classifica cada hexágono em tipos de consolidação urbana com base em 8 indicadores derivados do Overture Maps: pavimentação, consolidação, acesso a serviços, vitalidade comercial, conectividade viária, mescla edilícia, urbanização e exposição hídrica. Cada cor representa um perfil urbano distinto.',
		},
		implications: {
			es: 'Los tipos permiten distinguir núcleos urbanos consolidados, periferias en expansión con servicios incompletos, y zonas rurales sin infraestructura urbana. La clasificación multivariada evita reducir la complejidad urbana a un único indicador de "desarrollo".',
			en: 'Types allow the identification of consolidated urban cores, expanding peripheries with incomplete services, and rural zones without urban infrastructure. The multivariate classification avoids reducing urban complexity to a single "development" indicator.',
			gn: "Laja ohechauka tëtã consolidado, jeike mba'aporã ỹ, ha yvoty yvy kuéra. Ojeporavo variables hetaháicha jeheja oñemboikuaa peteĩháicha.",
			pt: 'Os tipos permitem distinguir núcleos urbanos consolidados, periferias em expansão com serviços incompletos e zonas rurais sem infraestrutura urbana. A classificação multivariada evita reduzir a complexidade urbana a um único indicador de "desenvolvimento".',
		},
		method: {
			es: `${METHOD_COMPARABLE.es} 8 variables: paving_index, urban_consolidation, service_access, commercial_vitality, road_connectivity, building_mix, urbanization, water_exposure. Fuente: Overture Maps Foundation (CC BY 4.0, release 2026-03-18) vía walkthru.earth. k=5 tipos.`,
			en: `${METHOD_COMPARABLE.en} 8 variables: paving_index, urban_consolidation, service_access, commercial_vitality, road_connectivity, building_mix, urbanization, water_exposure. Source: Overture Maps Foundation (CC BY 4.0, release 2026-03-18) via walkthru.earth. k=5 types.`,
		},
	},
	environmental_risk: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de riesgo ambiental según la co-ocurrencia de frecuencia de fuego, deforestación, amplitud térmica, pendiente y altura sobre drenaje. Cada color representa un tipo distinto de configuración de riesgo. Comparable entre Misiones e Itapúa.',
			en: 'The map classifies each hexagon into environmental risk types based on the co-occurrence of fire frequency, deforestation, thermal amplitude, slope and height above drainage. Each colour represents a distinct risk configuration type. Comparable between Misiones and Itapúa.',
			gn: "Mapa oñemomba'e hexágono kuéra tata-ayvu, ka'aguy reiguáva, ñembohasa riesgo rehegua. Ojoguáva Misiones ha Itapúa.",
			pt: 'O mapa classifica cada hexágono em tipos de risco ambiental conforme a co-ocorrência de frequência de fogo, desmatamento, amplitude térmica, declividade e altura acima da drenagem. Cada cor representa um tipo distinto de configuração de risco. Comparável entre Misiones e Itapúa.',
		},
		implications: {
			es: 'Los tipos permiten identificar configuraciones de riesgo cualitativamente distintas: zonas de alta pendiente con baja deforestación difieren estructuralmente de zonas planas con alta pérdida forestal, aunque ambas puedan tener "riesgo" similar en un índice único.',
			en: 'Types enable the identification of qualitatively distinct risk configurations: high-slope zones with low deforestation differ structurally from flat zones with high forest loss, even if both score similarly on a composite index.',
			gn: "Laja ohechauka riesgo kuéra ndojeguaa: yvate yvy ha michĩ ka'aguy reiguáva ojejuhu ambue rupa-pe, mba'etépa peteĩ índice rehegua.",
			pt: 'Os tipos permitem identificar configurações de risco qualitativamente distintas: zonas de alta declividade com baixo desmatamento diferem estruturalmente de zonas planas com alta perda florestal, mesmo que ambas possam apresentar "risco" similar em um índice único.',
		},
		method: {
			es: `${METHOD_COMPARABLE.es} 5 variables con goalposts fijos: frecuencia de fuego [0, 8] eventos/año, deforestación total [0, 15]%, amplitud térmica LST [2, 25]°C, pendiente [0, 30]°, HAND [0, 200] m. Fuentes: MODIS MCD64A1 (fuego), Hansen GFC v1.12 (deforestación), ERA5 (LST), FABDEM 30m (pendiente), MERIT Hydro (HAND). Período: 2019–2024.`,
			en: `${METHOD_COMPARABLE.en} 5 variables with fixed goalposts: fire frequency [0, 8] events/year, total deforestation [0, 15]%, LST thermal amplitude [2, 25]°C, slope [0, 30]°, HAND [0, 200] m. Sources: MODIS MCD64A1 (fire), Hansen GFC v1.12 (deforestation), ERA5 (LST), FABDEM 30m (slope), MERIT Hydro (HAND). Period: 2019–2024.`,
		},
	},
	climate_comfort: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos climáticos según la co-ocurrencia de temperatura diurna, precipitación, heladas y estrés hídrico. Cada color representa un régimen climático distinto. Comparable entre Misiones e Itapúa.',
			en: 'The map classifies each hexagon into climate types based on the co-occurrence of daytime temperature, precipitation, frost and water stress. Each colour represents a distinct climate regime. Comparable between Misiones and Itapúa.',
			gn: "Mapa oñemomba'e hexágono kuéra ára porã rehegua, temperatura, ama, ro ha y-mandu'a. Ojoguáva Misiones ha Itapúa.",
			pt: 'O mapa classifica cada hexágono em tipos climáticos conforme a co-ocorrência de temperatura diurna, precipitação, geadas e estresse hídrico. Cada cor representa um regime climático distinto. Comparável entre Misiones e Itapúa.',
		},
		implications: {
			es: 'Los tipos climáticos revelan gradientes geoespaciales que un índice único no captura: zonas cálidas y húmedas difieren estructuralmente de zonas frescas y secas, con implicancias distintas para habitabilidad y producción.',
			en: 'Climate types reveal geospatial gradients that a single index cannot capture: warm, humid zones differ structurally from cool, dry zones, with distinct implications for habitability and production.',
			gn: "Laja ára ohechauka gradiente rehegua ndohecháiva peteĩ índice: yvate ha ama oguejy ha tuja ha toro ojejuhu ambue rupa-pe.",
			pt: 'Os tipos climáticos revelam gradientes geoespaciais que um índice único não captura: zonas quentes e úmidas diferem estruturalmente de zonas frescas e secas, com implicações distintas para habitabilidade e produção.',
		},
		method: {
			es: `${METHOD_COMPARABLE.es} 4 variables con goalposts fijos: temperatura diurna LST [15, 50]°C, precipitación anual [1444, 1961] mm/año, días de helada [0, 60] días/año, ratio ET/PET [0, 1]. Fuentes: ERA5 (temperatura, heladas), CHIRPS (precipitación), MODIS (ET/PET). Período: 2019–2024.`,
			en: `${METHOD_COMPARABLE.en} 4 variables with fixed goalposts: daytime LST [15, 50]°C, annual precipitation [1444, 1961] mm/year, frost days [0, 60] days/year, ET/PET ratio [0, 1]. Sources: ERA5 (temperature, frost), CHIRPS (precipitation), MODIS (ET/PET). Period: 2019–2024.`,
		},
	},
	green_capital: {
		howToRead: {
			es: "El mapa clasifica cada hexágono en tipos de productividad vegetal según la co-ocurrencia de verdor estacional (NDVI), cobertura arbórea, productividad primaria (NPP) y área foliar (LAI). Los valores altos no distinguen bosque nativo de cultivos: la soja en plena temporada puntúa igual o más que el monte secundario. Comparable entre Misiones e Itapúa.",
			en: 'The map classifies each hexagon into vegetation productivity types based on the co-occurrence of seasonal greenness (NDVI), tree cover, primary productivity (NPP) and leaf area (LAI). High values do not distinguish native forest from crops: soybean at peak season scores as high or higher than secondary woodland. Comparable between Misiones and Itapúa.',
			gn: "Mapa oñemomba'e hexágono kuéra ka'aguy produktividad rehegua: NDVI, yvyra hendápe, NPP ha LAI. Yvate score ndohecháiha ka'aguy porã soja rehegua. Ojoguáva Misiones ha Itapúa.",
			pt: 'O mapa classifica cada hexágono em tipos de produtividade vegetal conforme a co-ocorrência de verdor sazonal (NDVI), cobertura arbórea, produtividade primária (NPP) e área foliar (LAI). Valores altos não distinguem floresta nativa de cultivos: a soja em plena temporada pontua tanto quanto ou mais do que o bosque secundário. Comparável entre Misiones e Itapúa.',
		},
		implications: {
			es: "La capa mide biomasa activa y productividad fotosintética, no calidad ecológica ni servicios ecosistémicos. Un distrito con alta productividad vegetal puede ser un cinturón sojero; uno con baja productividad puede tener suelo desnudo por estacionalidad. Usar junto con deforestation_dynamics para contextualizar.",
			en: "This layer measures active biomass and photosynthetic productivity, not ecological quality or ecosystem services. A district with high vegetation productivity may be a soybean belt; one with low productivity may have bare soil due to seasonality. Use alongside deforestation_dynamics for context.",
			gn: "Capa oñemoĩva oipuru biomasa mba'ehekápe, ndaha'éi calidad ecológica. Umi tetã yvate NDVIháva ikuai soja cinturón; michĩháva suelo desnudo. Ojeporavo ha deforestation_dynamics.",
			pt: 'A camada mede biomassa ativa e produtividade fotossintética, não qualidade ecológica nem serviços ecossistêmicos. Um distrito com alta produtividade vegetal pode ser um cinturão sojeiro; um com baixa produtividade pode ter solo exposto por sazonalidade. Usar em conjunto com deforestation_dynamics para contextualizar.',
		},
		method: {
			es: `${METHOD_COMPARABLE.es} 4 variables con goalposts fijos: NDVI [0.05, 0.90], cobertura arbórea [0, 100]%, NPP [0.52, 1.51] kgC/m²/8d, LAI [0, 7] m²/m². Fuentes: MODIS 250m (NDVI), Hansen GFC 2000 (treecover), MODIS MOD17A3 (NPP), MODIS MOD15A2H (LAI). Período: 2019–2024.`,
			en: `${METHOD_COMPARABLE.en} 4 variables with fixed goalposts: NDVI [0.05, 0.90], tree cover [0, 100]%, NPP [0.52, 1.51] kgC/m²/8d, LAI [0, 7] m²/m². Sources: MODIS 250m (NDVI), Hansen GFC 2000 (treecover), MODIS MOD17A3 (NPP), MODIS MOD15A2H (LAI). Period: 2019–2024.`,
		},
	},
	change_pressure: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de presión de cambio según la co-ocurrencia de tendencia de urbanización, expansión construida, pérdida forestal y cambio de vegetación. Comparable entre Misiones e Itapúa.',
			en: 'The map classifies each hexagon into change pressure types based on the co-occurrence of urbanisation trend, built-up expansion, forest loss and vegetation change. Comparable between Misiones and Itapúa.',
			gn: "Mapa oñemomba'e hexágono kuéra tendencia-pe: oĩvove tëtã, óga pyahu, ka'aguy oguejy ha yvoty jepota. Ojoguáva Misiones ha Itapúa.",
			pt: 'O mapa classifica cada hexágono em tipos de pressão de mudança conforme a co-ocorrência de tendência de urbanização, expansão construída, perda florestal e mudança de vegetação. Comparável entre Misiones e Itapúa.',
		},
		implications: {
			es: 'Los tipos separan urbanización activa de deforestación agrícola y de zonas estables. Un municipio con "alta presión" por urbanización requiere políticas distintas a uno con "alta presión" por avance de frontera agraria.',
			en: 'Types separate active urbanisation from agricultural deforestation and stable zones. A municipality under "high pressure" due to urbanisation requires different policies from one under "high pressure" due to advancing agricultural frontier.',
			gn: "Laja oñemboikuaa tëtã ojehúva, ka'aguy oguejy, ha tetã ikatupyryvéva. Tëtã yvate presión urbanización rupive oguereko política ambue.",
			pt: 'Os tipos separam urbanização ativa de desmatamento agrícola e de zonas estáveis. Um município com "alta pressão" por urbanização requer políticas distintas de um com "alta pressão" por avanço de fronteira agrária.',
		},
		method: {
			es: `${METHOD_COMPARABLE.es} 4 variables con goalposts fijos: tendencia VIIRS [−2, 5] nW/cm²/año, cambio GHSL [0, 42]%, pérdida forestal Hansen [0, 20]%, tendencia NDVI [−0.070, 0.090] /año. Fuentes: NOAA VIIRS 500m (2016–2025), JRC GHSL (2000 vs 2020), Hansen GFC v1.12 (2001–2024), MODIS NDVI (2019–2024).`,
			en: `${METHOD_COMPARABLE.en} 4 variables with fixed goalposts: VIIRS trend [−2, 5] nW/cm²/year, GHSL change [0, 42]%, Hansen forest loss [0, 20]%, NDVI trend [−0.070, 0.090] /year. Sources: NOAA VIIRS 500m (2016–2025), JRC GHSL (2000 vs 2020), Hansen GFC v1.12 (2001–2024), MODIS NDVI (2019–2024).`,
		},
	},
	location_value: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de valor posicional según la co-ocurrencia de accesibilidad, conectividad a salud, actividad económica, topografía y distancia a rutas.',
			en: 'The map classifies each hexagon into positional value types based on the co-occurrence of accessibility, health connectivity, economic activity, topography and road distance.',
			gn: "Mapa oñemomba'e hexágono kuéra valor posicional rehegua: jeike, tesãi-rape, tembiapo, yvy ha tape-guará.",
			pt: 'O mapa classifica cada hexágono em tipos de valor posicional conforme a co-ocorrência de acessibilidade, conectividade à saúde, atividade econômica, topografia e distância às vias.',
		},
		implications: {
			es: 'Los tipos distinguen núcleos urbanos bien conectados, periferias accesibles pero poco activas, y zonas rurales aisladas. El valor posicional emergente de la clasificación es más informativo que un ranking lineal.',
			en: 'Types distinguish well-connected urban cores, accessible but less active peripheries, and isolated rural zones. The positional value emerging from the classification is more informative than a linear ranking.',
			gn: "Laja oñemboikuaa tëtã jeike porãva, jeike ayvúva ha yvy rembe'ýva. Valor posicional kuéra iporãvéva peteĩ ranking oñepyrũha.",
			pt: 'Os tipos distinguem núcleos urbanos bem conectados, periferias acessíveis mas pouco ativas e zonas rurais isoladas. O valor posicional emergente da classificação é mais informativo do que um ranking linear.',
		},
		method: {
			es: `${METHOD_COMMON.es} Variables: tiempo a ciudad 20k Nelson, acceso a salud Oxford, radiancia VIIRS, pendiente FABDEM, distancia a ruta OSM. k=4 tipos, silueta=0.43.`,
			en: `${METHOD_COMMON.en} Variables: travel time to 20k city (Nelson), health access (Oxford), VIIRS radiance, FABDEM slope, distance to OSM road. k=4 types, silhouette=0.43.`,
		},
	},
	agri_potential: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de aptitud agrícola según la co-ocurrencia de calidad del suelo, régimen hídrico, acumulación térmica y topografía. Comparable entre Misiones e Itapúa.',
			en: 'The map classifies each hexagon into agricultural suitability types based on the co-occurrence of soil quality, water regime, heat accumulation and topography. Comparable between Misiones and Itapúa.',
			gn: "Mapa oñemomba'e hexágono kuéra temity-rehe oĩva: yvy porã, y, ñembohasa tataypy ha yvy rupa. Ojoguáva Misiones ha Itapúa.",
			pt: 'O mapa classifica cada hexágono em tipos de aptidão agrícola conforme a co-ocorrência de qualidade do solo, regime hídrico, acumulação de calor e topografia. Comparável entre Misiones e Itapúa.',
		},
		implications: {
			es: 'Los tipos reflejan configuraciones edafoclimáticas distintas: suelos ácidos con alta lluvia (aptitud para yerba mate), suelos neutros con calor acumulado (aptitud para tabaco/cítricos), y zonas con limitaciones múltiples.',
			en: 'Types reflect distinct edaphoclimatic configurations: acidic soils with high rainfall (suited for yerba mate), neutral soils with accumulated heat (suited for tobacco/citrus), and zones with multiple constraints.',
			gn: "Laja ohechauka yvy rehegua ambue ambue: yvai pH ka'aguyetépe (yerba mate), neutro GDD (tabaco/cítrico), ha yvy limitaciones hetáva.",
			pt: 'Os tipos refletem configurações edafoclimáticas distintas: solos ácidos com alta precipitação (aptidão para erva-mate), solos neutros com calor acumulado (aptidão para tabaco/cítricos) e zonas com limitações múltiplas.',
		},
		method: {
			es: `${METHOD_COMPARABLE.es} 5 variables con goalposts fijos: carbono orgánico del suelo [0, 472] g/dm³, distancia a pH óptimo [0, 1.0], arcilla [0, 590] g/kg, precipitación anual [1444, 1961] mm/año, GDD base 10°C [3589, 4587] °C·día. Fuentes: SoilGrids v2 (ISRIC, 0–5cm), CHIRPS (precipitación), ERA5 (GDD), FABDEM (pendiente). Período: 2019–2024.`,
			en: `${METHOD_COMPARABLE.en} 5 variables with fixed goalposts: soil organic carbon [0, 472] g/dm³, distance to optimal pH [0, 1.0], clay [0, 590] g/kg, annual precipitation [1444, 1961] mm/year, GDD base 10°C [3589, 4587] °C·day. Sources: SoilGrids v2 (ISRIC, 0–5cm), CHIRPS (precipitation), ERA5 (GDD), FABDEM (slope). Period: 2019–2024.`,
		},
	},
	forest_health: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de integridad forestal según la co-ocurrencia de tendencia de verdor, ratio de pérdida arbórea, productividad fotosintética y evapotranspiración. Comparable entre Misiones e Itapúa.',
			en: 'The map classifies each hexagon into forest integrity types based on the co-occurrence of greenness trend, tree loss ratio, photosynthetic productivity and evapotranspiration. Comparable between Misiones and Itapúa.',
			gn: "Mapa oñemomba'e hexágono kuéra ka'aguy porãve rehegua: tendencia NDVI, pérdida yvyra, GPP ha ET. Ojoguáva Misiones ha Itapúa.",
			pt: 'O mapa classifica cada hexágono em tipos de integridade florestal conforme a co-ocorrência de tendência de verdor, razão de perda arbórea, produtividade fotossintética e evapotranspiração. Comparável entre Misiones e Itapúa.',
		},
		implications: {
			es: 'Los tipos separan bosque sano y productivo, bosque en degradación con pérdida activa, y zonas sin cobertura forestal significativa. Esta clasificación permite priorizar intervenciones de restauración donde la degradación es incipiente.',
			en: 'Types separate healthy and productive forest, degrading forest with active loss, and zones without significant tree cover. This classification allows prioritising restoration interventions where degradation is incipient.',
			gn: "Laja oñemboikuaa ka'aguy porã, ka'aguy degradáva ha yvy ka'aguy ỹre. Ohechauka mávape oñemboguata restauración.",
			pt: 'Os tipos separam floresta saudável e produtiva, floresta em degradação com perda ativa e zonas sem cobertura florestal significativa. Esta classificação permite priorizar intervenções de restauração onde a degradação é incipiente.',
		},
		method: {
			es: `${METHOD_COMPARABLE.es} 4 variables con goalposts fijos: tendencia NDVI [−0.070, 0.090] /año, ratio pérdida/cobertura [0, 50]%, GPP [0.026, 0.065] kgC/m²/8d, ET [14.05, 30.79] mm/8d. Fuentes: MODIS NDVI 250m (tendencia 5 años), Hansen GFC v1.12 (loss/treecover2000), MODIS MOD17A2 (GPP), TerraClimate (ET). Período: 2019–2024.`,
			en: `${METHOD_COMPARABLE.en} 4 variables with fixed goalposts: NDVI trend [−0.070, 0.090] /year, loss/cover ratio [0, 50]%, GPP [0.026, 0.065] kgC/m²/8d, ET [14.05, 30.79] mm/8d. Sources: MODIS NDVI 250m (5-year trend), Hansen GFC v1.12 (loss/treecover2000), MODIS MOD17A2 (GPP), TerraClimate (ET). Period: 2019–2024.`,
		},
	},
	forestry_aptitude: {
		howToRead: {
			es: "El mapa muestra la similitud biofísica de cada hexágono con las plantaciones forestales que ya existen y prosperan en Misiones (Argentina). El valor es la probabilidad (0–100) estimada por un modelo de distribución de especie (SDM). Para Itapúa (Paraguay), el score es una extrapolación bioclimática del modelo entrenado en Misiones: indica qué tan similares son las condiciones de clima, suelo y terreno a las zonas silvícolas de Misiones, no una predicción calibrada con presencia local. Hexágonos sobre agua o urbano quedan sin pintar.",
			en: 'The map shows the biophysical similarity of each hexagon to the forestry plantations that already exist and thrive in Misiones (Argentina). The value is the probability (0–100) estimated by a species distribution model (SDM). For Itapúa (Paraguay), the score is a bioclimatic extrapolation of the model trained in Misiones: it indicates how similar the climate, soil and terrain conditions are to the forestry zones of Misiones, not a prediction calibrated with local presence. Hexagons over water or urban land are unpainted.',
			gn: "Mapa ohechauka hexágono rehegua similitud biofísica plantación silvícola Misiones ndive. Score = probabilidad (0–100) modelo SDM rupive. Itapúa-pe, score bioclimático extrapolado Misiones-gua. Hexágono y-ári ha tëtã-pe oikéiva ndaipytãi.",
			pt: 'O mapa mostra a similaridade biofísica de cada hexágono com as plantações florestais que já existem e prosperam em Misiones (Argentina). O valor é a probabilidade (0–100) estimada por um modelo de distribuição de espécies (SDM). Para Itapúa (Paraguai), o score é uma extrapolação bioclimática do modelo treinado em Misiones: indica quão similares são as condições de clima, solo e terreno às zonas silvícolas de Misiones, não uma previsão calibrada com presença local. Hexágonos sobre água ou área urbana ficam sem cor.',
		},
		implications: {
			es: "Score alto = condiciones análogas a zonas donde la silvicultura ya funciona en Misiones. Para Itapúa, interpretar como indicador de afinidad bioclimática transfronteriza. Es una capa descriptiva, no prescriptiva: NO dice dónde se puede plantar legalmente (eso depende de normativa nacional, tenencia, comunidades), ni garantiza rendimiento comercial, ni reemplaza estudios de campo.",
			en: "High score = conditions analogous to zones where forestry already works in Misiones. For Itapúa, interpret as an indicator of cross-border bioclimatic affinity. This is a descriptive layer, not a prescriptive one: it does NOT indicate where planting is legally permitted (that depends on national regulation, land tenure and communities), nor does it guarantee commercial yields, nor does it replace field surveys.",
			gn: "Yvate score = condiciones ojoguáva Misiones silvicultura ohupytýva. Itapúa-pe, ohechauka afinidad bioclimática transfronteriza. Capa descriptiva, ndaha'éi prescriptiva: ndohechái mávape oñemomba'éva ley rupive.",
			pt: 'Score alto = condições análogas às zonas onde a silvicultura já funciona em Misiones. Para Itapúa, interpretar como indicador de afinidade bioclimática transfronteiriça. É uma camada descritiva, não prescritiva: NÃO indica onde se pode plantar legalmente (isso depende de normativa nacional, posse de terra e comunidades), nem garante rendimento comercial, nem substitui estudos de campo.',
		},
		method: {
			es: `Random Forest (sklearn, 400 árboles, class_weight balanced) entrenado como SDM presencia-background con datos de Misiones: presencia = hexágonos MapBiomas Argentina clase silvicultura ≥50% (~27.600 hexes); background = muestra aleatoria (ratio 1:3). 23 covariables biofísicas a resolución H3: clima (ERA5 GDD, temperatura y radiación; CHIRPS precipitación y eventos extremos; TerraClimate déficit hídrico, VPD, humedad del suelo), suelo (SoilGrids arcilla/limo/arena/pH/SOC; HWSD drenaje, textura, profundidad radicular, AWC), terreno (SRTM pendiente, elevación, TWI, rugosidad), vegetación contextual (NDVI medio) y accesibilidad (tiempo a ciudad 50k). Heladas excluidas: en Misiones son 0–2 días/año, aportan ruido sin señal. Validación: Group K-Fold espacial (5 folds, bloques H3 res 5), AUC = 0.883 ± 0.010. Aplicación a otros territorios: extrapolación con las mismas covariables satelitales globales (no requiere presencia local). Tipos: k-means k=4 sobre covariables biofísicas de hexágonos con score ≥ 40.`,
			en: `Random Forest (sklearn, 400 trees, class_weight balanced) trained as a presence-background SDM using Misiones data: presence = hexagons classified as silviculture ≥50% in MapBiomas Argentina (~27,600 hexes); background = random sample (1:3 ratio). 23 biophysical covariates at H3 resolution: climate (ERA5 GDD, temperature and radiation; CHIRPS precipitation and extreme events; TerraClimate water deficit, VPD, soil moisture), soil (SoilGrids clay/silt/sand/pH/SOC; HWSD drainage, texture, root depth, AWC), terrain (SRTM slope, elevation, TWI, roughness), contextual vegetation (mean NDVI) and accessibility (travel time to 50k city). Frost excluded: in Misiones 0–2 days/year, adding noise without signal. Validation: Spatial Group K-Fold (5 folds, H3 res-5 blocks), AUC = 0.883 ± 0.010. Application to other territories: extrapolation using the same global satellite covariates (no local presence required). Types: k-means k=4 on biophysical covariates of hexagons with score ≥ 40.`,
		},
	},
	service_deprivation: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de carencia de servicios básicos según NBI, acceso a cloacas, calidad del piso, hacinamiento y acceso digital. Solo se muestran hexágonos con edificaciones detectadas (crosswalk dasimétrico). Cada color representa un perfil de carencia distinto.',
			en: 'The map classifies each hexagon into basic service deprivation types based on UBN, sanitation access, floor quality, overcrowding and digital access. Only hexagons with detected buildings (dasymetric crosswalk) are shown. Each colour represents a distinct deprivation profile.',
			gn: "Mapa oñemomba'e hexágono kuéra carencia servicios básicos rehegua: NBI, ykuaa, piso, ñembyaty ha computadora. Opyta hexágono óga oĩhaguépe. Peteĩ-peteĩ pytã ohechauka perfil carencia.",
			pt: 'O mapa classifica cada hexágono em tipos de carência de serviços básicos conforme NBI, acesso a esgoto, qualidade do piso, superlotação e acesso digital. Apenas hexágonos com edificações detectadas (crosswalk dasimétrico) são exibidos. Cada cor representa um perfil de carência distinto.',
		},
		implications: {
			es: 'Los tipos separan carencia habitacional (piso inadecuado + hacinamiento), carencia de infraestructura (sin cloacas), y brecha digital (sin computadora). Cada configuración demanda intervenciones distintas: vivienda social, extensión de red cloacal, o programas de inclusión digital.',
			en: 'Types separate housing deprivation (inadequate floor + overcrowding), infrastructure deprivation (no sanitation), and digital divide (no computer). Each configuration calls for distinct interventions: social housing, sewerage extension, or digital inclusion programmes.',
			gn: "Laja oñemboikuaa carencia óga (piso vai + ñembyaty), ykuaa ỹre, ha computadora ỹre. Peteĩ-peteĩ configuración oguereko tembiapo ambue.",
			pt: 'Os tipos separam carência habitacional (piso inadequado + superlotação), carência de infraestrutura (sem esgoto) e exclusão digital (sem computador). Cada configuração demanda intervenções distintas: habitação social, extensão de rede de esgoto ou programas de inclusão digital.',
		},
		method: {
			es: `${METHOD_COMMON.es} 6 variables Censo Nacional 2022 (INDEC): NBI, sin cloacas (100 - pct_cloacas), piso inadecuado, hacinamiento, hacinamiento crítico, sin computadora (100 - pct_computadora). Crosswalk dasimétrico ponderado por edificios (2.8M footprints). KMO=0.73.`,
			en: `${METHOD_COMMON.en} 6 variables from the National Census 2022 (INDEC): UBN, no sewerage (100 − pct_sewerage), inadequate floor, overcrowding, critical overcrowding, no computer (100 − pct_computer). Dasymetric crosswalk weighted by buildings (2.8M footprints). KMO=0.73.`,
		},
	},
	territorial_isolation: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de aislamiento geoespacial según tiempo de viaje a ciudades y centros de salud, distancia a rutas, densidad vial, luces nocturnas y densidad poblacional. Cobertura completa de la provincia (crosswalk híbrido).',
			en: 'The map classifies each hexagon into geospatial isolation types based on travel time to cities and health centres, road distance, road density, night lights and population density. Full provincial coverage (hybrid crosswalk).',
			gn: "Mapa oñemomba'e hexágono kuéra aislamiento rehegua: tape, tëtã ha tesãi-renda ojehúvo, luces nocturnas ha yvypóra. Cobertura opytáva provincia-pe.",
			pt: 'O mapa classifica cada hexágono em tipos de isolamento geoespacial conforme o tempo de viagem a cidades e centros de saúde, distância às vias, densidade viária, luzes noturnas e densidade populacional. Cobertura completa da província (crosswalk híbrido).',
		},
		implications: {
			es: 'Los tipos distinguen aislamiento por distancia (lejos de rutas y ciudades), aislamiento funcional (cerca de ruta pero sin servicios), y conectividad plena. Las zonas aisladas enfrentan costos de transporte, acceso limitado a salud y educación, y menor oportunidad económica.',
			en: 'Types distinguish distance-based isolation (far from roads and cities), functional isolation (near a road but lacking services), and full connectivity. Isolated zones face transport costs, limited health and education access, and fewer economic opportunities.',
			gn: "Laja oñemboikuaa mombyry (tape ka'aguy-pe), funcional (tape ípe nda'iha servicios), ha jeike opytáva. Yvy rembe'ýva oguereko costo transporte, tesãi ha mbo'e.",
			pt: 'Os tipos distinguem isolamento por distância (longe de vias e cidades), isolamento funcional (próximo a uma via, mas sem serviços) e conectividade plena. As zonas isoladas enfrentam custos de transporte, acesso limitado à saúde e à educação e menores oportunidades econômicas.',
		},
		method: {
			es: `${METHOD_COMMON.es} 6 variables: acceso a ciudades y salud (Oxford MAP 2019, fricción motorizada), distancia a ruta primaria y densidad vial (OSM), radiancia VIIRS 2022-2024, densidad poblacional Censo 2022. Crosswalk híbrido (dasimétrico + areal). KMO=0.87.`,
			en: `${METHOD_COMMON.en} 6 variables: city and health access (Oxford MAP 2019, motorised friction), distance to primary road and road density (OSM), VIIRS radiance 2022–2024, population density Census 2022. Hybrid crosswalk (dasymetric + areal). KMO=0.87.`,
		},
	},
	health_access: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de acceso a salud según tiempo al centro de salud, cobertura sanitaria, vulnerabilidad social (NBI), presión demográfica (ancianos y menores) y densidad poblacional. Solo hexágonos con edificaciones.',
			en: 'The map classifies each hexagon into health access types based on travel time to the nearest health facility, health coverage, social vulnerability (UBN), demographic pressure (elderly and children) and population density. Only hexagons with buildings.',
			gn: "Mapa oñemomba'e hexágono kuéra tesãi-rape rehegua: tape tesãi-renda-pe, joapy, NBI, ñembojekuaa ha yvypóra. Hexágono óga oĩhaguépe.",
			pt: 'O mapa classifica cada hexágono em tipos de acesso à saúde conforme o tempo ao centro de saúde mais próximo, cobertura sanitária, vulnerabilidade social (NBI), pressão demográfica (idosos e crianças) e densidade populacional. Apenas hexágonos com edificações.',
		},
		implications: {
			es: 'Los tipos separan déficit por distancia (zonas rurales lejanas), déficit por saturación (zonas densas con alta proporción de población vulnerable), y déficit por cobertura (alto NBI con baja cobertura sanitaria). Cada configuración requiere respuestas distintas del sistema de salud.',
			en: 'Types separate distance-based deficit (remote rural zones), saturation-based deficit (dense zones with high vulnerable population shares), and coverage-based deficit (high UBN with low health coverage). Each configuration requires distinct responses from the health system.',
			gn: "Laja oñemboikuaa déficit tesãi: tape mombyry, yvypóra hetáva ha cobertura michĩva. Peteĩ-peteĩ configuración oguereko respuesta ambue.",
			pt: 'Os tipos separam déficit por distância (zonas rurais remotas), déficit por saturação (zonas densas com alta proporção de população vulnerável) e déficit por cobertura (alto NBI com baixa cobertura sanitária). Cada configuração requer respostas distintas do sistema de saúde.',
		},
		method: {
			es: `${METHOD_COMMON.es} 6 variables: tiempo motorizado a salud (Oxford MAP 2019), cobertura sanitaria, NBI, % adultos mayores, % menores 18, densidad poblacional (Censo 2022). Crosswalk dasimétrico. KMO=0.60.`,
			en: `${METHOD_COMMON.en} 6 variables: motorised travel time to health (Oxford MAP 2019), health coverage, UBN, % elderly, % under 18, population density (Census 2022). Dasymetric crosswalk. KMO=0.60.`,
		},
	},
	education_capital: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de capital educativo según el nivel de instrucción acumulado: sin instrucción, secundario completo o más, educación superior (terciario + universitario), y universitario. Solo hexágonos con edificaciones.',
			en: 'The map classifies each hexagon into educational capital types based on accumulated instruction level: no formal education, secondary complete or above, higher education (tertiary + university), and university. Only hexagons with buildings.',
			gn: "Mapa oñemomba'e hexágono kuéra mbo'e capital rehegua: mbo'e ỹre, secundario opytáva, terciario + universitario, ha universitario. Hexágono óga oĩhaguépe.",
			pt: 'O mapa classifica cada hexágono em tipos de capital educacional conforme o nível de instrução acumulado: sem instrução, ensino médio completo ou mais, educação superior (terciário + universitário) e universitário. Apenas hexágonos com edificações.',
		},
		implications: {
			es: 'Los tipos distinguen zonas con alto capital humano (universidades cercanas, alta formación), zonas de educación media (secundario completo pero sin terciario), y zonas de bajo capital (alta proporción sin instrucción). El capital educativo es predictor de ingresos, salud y participación cívica.',
			en: 'Types distinguish zones with high human capital (nearby universities, high educational attainment), intermediate education zones (secondary complete but no tertiary), and low capital zones (high proportion with no formal education). Educational capital predicts income, health and civic participation.',
			gn: "Laja oñemboikuaa tëtã yvate capital educativo, mbyte ha michĩ. Mbo'e capital ohechauka ingreso, tesãi ha tetã-mba'e.",
			pt: 'Os tipos distinguem zonas com alto capital humano (universidades próximas, alta formação), zonas de educação média (ensino médio completo, sem terciário) e zonas de baixo capital (alta proporção sem instrução). O capital educacional prediz renda, saúde e participação cívica.',
		},
		method: {
			es: `${METHOD_COMMON.es} 4 variables Censo 2022: % sin instrucción, % secundario completo o más (umbral acumulativo), % educación superior (terciario + universitario), % universitario. Terciario y universitario son tracks paralelos en el sistema argentino. Crosswalk dasimétrico. KMO=0.71.`,
			en: `${METHOD_COMMON.en} 4 variables from Census 2022: % no formal education, % secondary complete or above (cumulative threshold), % higher education (tertiary + university), % university. Tertiary and university are parallel tracks in the Argentine system. Dasymetric crosswalk. KMO=0.71.`,
		},
	},
	education_flow: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de desempeño del sistema educativo según inasistencia escolar primaria (6-12), secundaria (13-18) y maternidad adolescente. Solo hexágonos con edificaciones.',
			en: 'The map classifies each hexagon into education system performance types based on primary school non-attendance (6–12), secondary non-attendance (13–18) and adolescent motherhood. Only hexagons with buildings.',
			gn: "Mapa oñemomba'e hexágono kuéra mbo'e sistema rehegua: oñeikéiva michĩ (6-12), yvate (13-18) ha sy adolescente. Hexágono óga oĩhaguépe.",
			pt: 'O mapa classifica cada hexágono em tipos de desempenho do sistema educacional conforme a não frequência escolar no ensino fundamental (6–12), médio (13–18) e maternidade adolescente. Apenas hexágonos com edificações.',
		},
		implications: {
			es: 'Los tipos separan deserción temprana (primaria), deserción tardía (secundaria) y embarazo adolescente como factor de exclusión educativa. La inasistencia primaria indica fallas básicas del sistema; la secundaria indica problemas de retención; la maternidad adolescente indica vulnerabilidad de género intersectada con pobreza.',
			en: "Types separate early drop-out (primary), late drop-out (secondary) and adolescent pregnancy as a factor of educational exclusion. Primary non-attendance signals basic system failures; secondary signals retention problems; adolescent motherhood signals gender vulnerability intersected with poverty.",
			gn: "Laja oñemboikuaa: mbo'e oñeikéiha (primaria), oñeikéiha (secundaria) ha sy adolescente. Primaria ohechauka falla básica; secundaria retención; maternidad adolescente vulnerabilidad.",
			pt: 'Os tipos separam evasão precoce (ensino fundamental), evasão tardia (ensino médio) e gravidez na adolescência como fator de exclusão educacional. A não frequência no fundamental indica falhas básicas do sistema; no médio, problemas de retenção; a maternidade adolescente, vulnerabilidade de gênero interseccionada com pobreza.',
		},
		method: {
			es: `${METHOD_COMMON.es} 3 variables Censo 2022: tasa de inasistencia 6-12 años, tasa de inasistencia 13-18 años, tasa de maternidad adolescente. Variables directas (mayor = peor flujo). Crosswalk dasimétrico. KMO=0.61.`,
			en: `${METHOD_COMMON.en} 3 variables from Census 2022: non-attendance rate 6–12 years, non-attendance rate 13–18 years, adolescent motherhood rate. Direct variables (higher = worse performance). Dasymetric crosswalk. KMO=0.61.`,
		},
	},
	land_use: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono según su cobertura dominante: selva nativa, plantación forestal, pastizal, agricultura, agua, humedal o urbano. Misiones usa MapBiomas Argentina Col. 1 (Landsat 30m); Itapúa usa MapBiomas Paraguay Col. 1. Nota: MapBiomas Paraguay Col. 1 no distingue plantación forestal, urbano ni mosaico agropecuario — estas clases aparecen como 0% en Itapúa. Las plantaciones forestales se incluyen dentro de bosque nativo; las áreas urbanas no se clasifican separadamente.',
			en: 'The map classifies each hexagon by its dominant cover: native forest, forestry plantation, grassland, agriculture, water, wetland or urban. Misiones uses MapBiomas Argentina Col. 1 (Landsat 30m); Itapúa uses MapBiomas Paraguay Col. 1. Note: MapBiomas Paraguay Col. 1 does not distinguish forestry plantations, urban areas or mixed agricultural mosaics — these classes appear as 0% in Itapúa. Forestry plantations are included within native forest; urban areas are not classified separately.',
			gn: "Mapa oñemomba'e hexágono kuéra cobertura dominante rehegua: ka'aguy, plantación, pastizal, temity, y, humedal ha tëtã. Misiones MapBiomas Argentina; Itapúa MapBiomas Paraguay. Nota: MapBiomas Paraguay ndohecháiha plantación ha tëtã.",
			pt: 'O mapa classifica cada hexágono conforme sua cobertura dominante: floresta nativa, plantação florestal, pastagem, agricultura, água, área úmida ou urbano. Misiones usa MapBiomas Argentina Col. 1 (Landsat 30m); Itapúa usa MapBiomas Paraguai Col. 1. Nota: MapBiomas Paraguai Col. 1 não distingue plantações florestais, áreas urbanas ou mosaicos agropecuários — essas classes aparecem como 0% em Itapúa. Plantações florestais são incluídas dentro de floresta nativa; áreas urbanas não são classificadas separadamente.',
		},
		implications: {
			es: 'Misiones: selva nativa domina (~73% de hexes), con plantaciones forestales (~12%) y mosaicos agrícolas en el este y sur. Itapúa (PY): cultivos/soja (~40%) y pastizal natural (~14%) dominan, con selva nativa residual (~20%) concentrada en el norte y corredores riparios. La comparación revela el contraste entre la Selva Atlántica conservada y el frente agrícola paraguayo. Plantación forestal, urbano y mosaico muestran 0% en Itapúa por limitaciones de la clasificación MapBiomas Paraguay (ver nota arriba).',
			en: "Misiones: native forest dominates (~73% of hexes), with forestry plantations (~12%) and agricultural mosaics in the east and south. Itapúa (PY): crops/soy (~40%) and natural grassland (~14%) dominate, with residual native forest (~20%) concentrated in the north and riparian corridors. The comparison reveals the contrast between the conserved Atlantic Forest and the Paraguayan agricultural frontier. Forestry, urban and mosaic classes show 0% in Itapúa due to MapBiomas Paraguay classification limitations (see note above).",
			gn: "Misiones: ka'aguy opytáva (~73%), plantación (~12%) ha mosaico agrícola. Itapúa: soja (~40%) ha pastizal (~14%), ka'aguy residual (~20%). Oñembojoaju Selva Atlántica ha fronteira Paraguay.",
			pt: 'Misiones: floresta nativa domina (~73% dos hexes), com plantações florestais (~12%) e mosaicos agrícolas no leste e sul. Itapúa (PY): cultivos/soja (~40%) e pastagem natural (~14%) dominam, com floresta nativa residual (~20%) concentrada no norte e corredores ripários. A comparação revela o contraste entre a Mata Atlântica conservada e a fronteira agrícola paraguaia. Plantação florestal, urbano e mosaico mostram 0% em Itapúa pelas limitações da classificação MapBiomas Paraguai (ver nota acima).',
		},
		method: {
			es: `${METHOD_COMPARABLE.es} Fuente: MapBiomas Argentina Collection 1 (Landsat 30m, 2022) para Misiones; MapBiomas Paraguay Collection 1 para Itapúa. Misiones: PCA + k=6 k-means sobre fracciones de cobertura por polígono H3 (silueta=0.62). Itapúa: muestreo centroide H3 + k=6 k-means (silueta=0.91). Clases unificadas: bosque nativo (incl. bosque inundable), plantación, pastizal, pastizal natural, agricultura, mosaico, humedal, urbano, agua, suelo desnudo.`,
			en: `${METHOD_COMPARABLE.en} Source: MapBiomas Argentina Collection 1 (Landsat 30m, 2022) for Misiones; MapBiomas Paraguay Collection 1 for Itapúa. Misiones: PCA + k=6 k-means on H3 polygon cover fractions (silhouette=0.62). Itapúa: H3 centroid sampling + k=6 k-means (silhouette=0.91). Unified classes: native forest (incl. floodplain forest), plantation, grassland, natural grassland, agriculture, mosaic, wetland, urban, water, bare soil.`,
		},
	},
	powerline_density: {
		howToRead: {
			es: 'Mapa de densidad de líneas de media y alta tensión. Hexágonos más claros = mayor densidad de infraestructura eléctrica. Score basado en longitud total y cantidad de líneas dentro de cada hexágono.',
			en: 'Map of medium and high-voltage transmission line density. Lighter hexagons = higher electrical infrastructure density. Score based on total length and number of lines within each hexagon.',
			gn: "Mapa línea eléctrica densidad. Hexágono sovy = yvate densidad eléctrica. Score oñemboguapýva longitud ha papapy línea ndive.",
			pt: 'Mapa de densidade de linhas de média e alta tensão. Hexágonos mais claros = maior densidade de infraestrutura elétrica. Score baseado no comprimento total e na quantidade de linhas dentro de cada hexágono.',
		},
		implications: {
			es: 'La cobertura eléctrica condiciona toda actividad productiva y residencial. Zonas con baja densidad de líneas requieren extensión de red para habilitar nuevos emprendimientos. La distancia a líneas existentes es el principal factor de costo de electrificación rural.',
			en: 'Electrical coverage conditions all productive and residential activity. Zones with low line density require network extension to enable new enterprises. Distance to existing lines is the main cost factor for rural electrification.',
			gn: "Cobertura eléctrica ohechauka opaichagua tembiapo. Yvy michĩ densidadháva ikuai oguereko red pyahu. Mombyry línea = yvate costo electrificación rural.",
			pt: 'A cobertura elétrica condiciona toda atividade produtiva e residencial. Zonas com baixa densidade de linhas requerem extensão de rede para viabilizar novos empreendimentos. A distância às linhas existentes é o principal fator de custo da eletrificação rural.',
		},
		method: {
			es: `Fuente: EMSA (Secretaría de Energía, datos.energia.gob.ar, abril 2024). Líneas de media y alta tensión georreferenciadas, intersectadas con grilla H3 resolución 9. Score = longitud total de líneas / área del hexágono, normalizado 0-100.`,
			en: `Source: EMSA (Secretaría de Energía, datos.energia.gob.ar, April 2024). Medium and high-voltage transmission lines georeferenced, intersected with H3 resolution 9 grid. Score = total line length / hexagon area, normalised 0–100.`,
		},
	},
	territorial_types: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos geoespaciales según su metabolismo ecosistémico: productividad, apropiación humana y dinámica de cambio. Cada color representa un tipo cualitativamente distinto de territorio.',
			en: 'The map classifies each hexagon into geospatial types based on its ecosystem metabolism: productivity, human appropriation and change dynamics. Each colour represents a qualitatively distinct territory type.',
			gn: "Mapa oñemomba'e hexágono kuéra ecosistema metabolismo rehegua: produktividad, yvypóra rehegua ha kambio. Peteĩ-peteĩ pytã ohechauka tipo territorio ambue.",
			pt: 'O mapa classifica cada hexágono em tipos geoespaciais conforme seu metabolismo ecossistêmico: produtividade, apropriação humana e dinâmica de mudança. Cada cor representa um tipo qualitativamente distinto de território.',
		},
		implications: {
			es: 'Los tipos geoespaciales sintetizan 13 variables satelitales en una clasificación interpretable. Permiten identificar selva productiva intacta, mosaicos agro-forestales en transición, zonas agrícolas consolidadas, periurbanos en expansión y núcleos urbanos — cada uno con necesidades de gestión distintas.',
			en: 'Geospatial types synthesise 13 satellite variables into an interpretable classification. They identify intact productive forest, transitional agro-forestry mosaics, consolidated agricultural zones, expanding peri-urban areas and urban cores — each with distinct management needs.',
			gn: "Tipos geoespaciales oñemomba'e 13 variables satelitales peteĩ clasificación-pe. Ohechauka ka'aguy, mosaico agro-forestal, temity, periurbano ha tëtã — peteĩ-peteĩ oguereko necesidades ambue.",
			pt: 'Os tipos geoespaciais sintetizam 13 variáveis satelitais em uma classificação interpretável. Permitem identificar floresta produtiva intacta, mosaicos agroflorestais em transição, zonas agrícolas consolidadas, periurbanos em expansão e núcleos urbanos — cada um com necessidades de gestão distintas.',
		},
		method: {
			es: `${METHOD_COMMON.es} 13 variables: NPP, NDVI, cobertura arbórea, fracción arboles/cultivos/construido, deforestación, luces nocturnas, tendencia VIIRS, expansión GHSL, precipitación. k=8 tipos. Fuentes: MODIS, Hansen GFC, VIIRS, GHSL, CHIRPS.`,
			en: `${METHOD_COMMON.en} 13 variables: NPP, NDVI, tree cover, fraction trees/crops/built, deforestation, night lights, VIIRS trend, GHSL expansion, precipitation. k=8 types. Sources: MODIS, Hansen GFC, VIIRS, GHSL, CHIRPS.`,
		},
	},
	sociodemographic: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos sociodemográficos según la co-ocurrencia de densidad poblacional, pobreza (NBI), hacinamiento, tenencia de vivienda, tamaño de hogar y acceso digital. Cada color representa un perfil censal distinto.',
			en: 'The map classifies each hexagon into sociodemographic types based on the co-occurrence of population density, poverty (UBN), overcrowding, housing tenure, household size and digital access. Each colour represents a distinct census profile.',
			gn: "Mapa oñemomba'e hexágono kuéra sociodemográfico rehegua: densidad, NBI, ñembyaty, óga tenencia, óga tuichakue ha computadora. Peteĩ-peteĩ pytã ohechauka perfil censal.",
			pt: 'O mapa classifica cada hexágono em tipos sociodemográficos conforme a co-ocorrência de densidade populacional, pobreza (NBI), superlotação, regime de posse da habitação, tamanho do domicílio e acesso digital. Cada cor representa um perfil censitário distinto.',
		},
		implications: {
			es: 'Los tipos distinguen zonas urbanas densas con bajo NBI, periferias con hacinamiento y pobreza, y zonas rurales dispersas con alta propiedad pero baja conectividad. Esta clasificación multivariada evita reducir la complejidad social a un solo indicador.',
			en: 'Types distinguish dense urban zones with low UBN, peripheries with overcrowding and poverty, and sparse rural zones with high home ownership but low connectivity. This multivariate classification avoids reducing social complexity to a single indicator.',
			gn: "Laja oñemboikuaa tëtã denso NBI michĩháva, periferia ñembyaty ha NBI yvateháva, ha yvy rembe'ý propietarióva. Ojeporavo variables hetaháicha.",
			pt: 'Os tipos distinguem zonas urbanas densas com baixo NBI, periferias com superlotação e pobreza e zonas rurais dispersas com alta propriedade mas baixa conectividade. Esta classificação multivariada evita reduzir a complexidade social a um único indicador.',
		},
		method: {
			es: `${METHOD_COMMON.es} 6 variables del Censo Nacional 2022 (INDEC): densidad hab/km², % NBI, % hacinamiento, % propietarios, tamaño medio hogar, % computadora. Variables a nivel radio censal, agregadas a H3 vía crosswalk ponderado por área.`,
			en: `${METHOD_COMMON.en} 6 variables from the National Census 2022 (INDEC): population density (hab/km²), % UBN, % overcrowding, % home ownership, mean household size, % computer ownership. Variables at census tract level, aggregated to H3 via area-weighted crosswalk.`,
		},
	},
	economic_activity: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de actividad económica según la co-ocurrencia de empleo, actividad económica, formación universitaria, luces nocturnas y densidad edilicia. Cada color representa un nivel de dinamismo distinto.',
			en: 'The map classifies each hexagon into economic activity types based on the co-occurrence of employment, economic activity rate, university education, night lights and building density. Each colour represents a distinct level of dynamism.',
			gn: "Mapa oñemomba'e hexágono kuéra tembiapo rehegua: empleo, actividad, universitario, luces ha densidad óga. Peteĩ-peteĩ pytã ohechauka nivel ambue.",
			pt: 'O mapa classifica cada hexágono em tipos de atividade econômica conforme a co-ocorrência de emprego, atividade econômica, formação universitária, luzes noturnas e densidade edilícia. Cada cor representa um nível de dinamismo distinto.',
		},
		implications: {
			es: 'Los tipos separan centros económicos consolidados (alto empleo + universitarios + luces), periferias activas con posible informalidad (alta actividad, bajo empleo formal), y zonas rurales de baja actividad económica. La radiancia nocturna (VIIRS) es un proxy robusto de actividad que complementa los datos censales.',
			en: 'Types separate consolidated economic centres (high employment + university graduates + night lights), active peripheries with possible informality (high activity, low formal employment), and rural zones with low economic activity. Night-time radiance (VIIRS) is a robust proxy for activity that complements census data.',
			gn: "Laja oñemboikuaa centro económico, periferia activa informalidad ndive, ha yvy michĩ actividad. VIIRS oñepyrũ proxy robusta mba'e tembiapo-pe.",
			pt: 'Os tipos separam centros econômicos consolidados (alto emprego + universitários + luzes), periferias ativas com possível informalidade (alta atividade, baixo emprego formal) e zonas rurais de baixa atividade econômica. A radiância noturna (VIIRS) é um proxy robusto de atividade que complementa os dados censitários.',
		},
		method: {
			es: `${METHOD_COMMON.es} 5 variables: tasa de empleo y actividad (Censo 2022 INDEC, 14+ años), % universitarios (Censo 2022), radiancia media VIIRS 500m (2022-2024), densidad edilicia Global Building Atlas 2025. Variables censales agregadas a H3 vía crosswalk.`,
			en: `${METHOD_COMMON.en} 5 variables: employment rate and activity rate (Census 2022 INDEC, 14+ years), % university graduates (Census 2022), mean VIIRS 500m radiance (2022–2024), building density Global Building Atlas 2025. Census variables aggregated to H3 via crosswalk.`,
		},
	},
	eudr: {
		howToRead: {
			es: 'El mapa muestra el riesgo de deforestación post-2020 por hexágono (H3 res-7, ~5 km²). Score alto (rojo) = mayor pérdida forestal o actividad de fuego después del cutoff EUDR (31/12/2020). Cobertura: 10 provincias del NOA y NEA argentino.',
			en: 'The map shows post-2020 deforestation risk per hexagon (H3 res-7, ~5 km²). High score (red) = greater forest loss or fire activity after the EUDR cut-off date (31/12/2020). Coverage: 10 provinces of Northwest and Northeast Argentina.',
			gn: "Mapa ohechauka riesgo deforestación post-2020 hexágono ndive (H3 res-7, ~5 km²). Score yvate (pyta) = yvate pérdida forestal o tata post EUDR cutoff (31/12/2020). Cobertura: 10 provincias NOA ha NEA.",
			pt: 'O mapa mostra o risco de desmatamento pós-2020 por hexágono (H3 res-7, ~5 km²). Score alto (vermelho) = maior perda florestal ou atividade de fogo após o cutoff EUDR (31/12/2020). Cobertura: 10 províncias do NOA e NEA argentino.',
		},
		implications: {
			es: 'Hexágonos con deforestación post-2020 representan riesgo de no-conformidad bajo la Regulación (UE) 2023/1115. Exportaciones de commodities (soja, carne, madera) originados en estas zonas requieren due diligence reforzado. Este análisis es orientativo — la verificación formal requiere geometría parcelaria exacta.',
			en: 'Hexagons with post-2020 deforestation represent non-compliance risk under Regulation (EU) 2023/1115. Commodity exports (soy, beef, timber) originating from these zones require enhanced due diligence. This analysis is indicative — formal verification requires precise parcel geometry.',
			gn: "Hexágono deforestación post-2020 ndive oñemomba'e riesgo Regulación UE 2023/1115 rehegua. Commodity (soja, mburu, yvyra) ojehova koápe oguereko due diligence reforzado. Ko análisis orientativo — verificación formal ikuai geometría parcelaria exacta rehegua.",
			pt: 'Hexágonos com desmatamento pós-2020 representam risco de não conformidade sob o Regulamento (UE) 2023/1115. Exportações de commodities (soja, carne, madeira) originadas dessas zonas requerem due diligence reforçado. Esta análise é indicativa — a verificação formal requer geometria parcelária precisa.',
		},
		method: {
			es: `Score compuesto 0-100: 70% pérdida forestal post-2020 (Hansen GFC v1.12, Landsat 30m) + 20% área quemada post-2020 (MODIS MCD64A1, 500m) + 10% pérdida de cobertura previa. Cutoff EUDR: 31/12/2020. Resolución espacial: H3 resolución 7 (~5.16 km²). Cobertura: Salta, Jujuy, Tucumán, Catamarca, Sgo. del Estero, Formosa, Chaco, Corrientes, Misiones, Entre Ríos.`,
			en: `Composite score 0–100: 70% post-2020 forest loss (Hansen GFC v1.12, Landsat 30m) + 20% post-2020 burned area (MODIS MCD64A1, 500m) + 10% prior cover loss. EUDR cut-off: 31/12/2020. Spatial resolution: H3 resolution 7 (~5.16 km²). Coverage: Salta, Jujuy, Tucumán, Catamarca, Santiago del Estero, Formosa, Chaco, Corrientes, Misiones, Entre Ríos.`,
		},
	},
	accessibility: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono en tipos de accesibilidad según la co-ocurrencia de tiempo de viaje a la capital departamental, a la ciudad más cercana, distancia a hospital, escuela y ruta principal. Cada color representa un nivel de conectividad distinto. Comparable entre Misiones e Itapúa: mismas fuentes y metodología.',
			en: 'The map classifies each hexagon into accessibility types based on the co-occurrence of travel time to the department capital, the nearest city, distance to hospital, school and primary road. Each colour represents a distinct connectivity level. Comparable between Misiones and Itapúa: same sources and methodology.',
			gn: "Mapa oñemomba'e hexágono kuéra accesibilidad rehegua: tape capital, tëtã, hospital, mbo'ehóga ha ruta. Ojoguáva Misiones ha Itapúa: oñepyrũ fuentes.",
			pt: 'O mapa classifica cada hexágono em tipos de acessibilidade conforme a co-ocorrência de tempo de viagem à capital departamental, à cidade mais próxima, distância ao hospital, à escola e à via principal. Cada cor representa um nível de conectividade distinto. Comparável entre Misiones e Itapúa: mesmas fontes e metodologia.',
		},
		implications: {
			es: 'Los tipos distinguen conectividad plena (cercanía a servicios y rutas), accesibilidad parcial (cerca de ruta pero lejos de servicios especializados), y aislamiento funcional (lejos de todo). La comparación entre territorios revela diferencias estructurales en conectividad según topografía y densidad vial.',
			en: 'Types distinguish full connectivity (proximity to services and roads), partial accessibility (near a road but distant from specialised services), and functional isolation (far from everything). Cross-territory comparison reveals structural differences in connectivity according to topography and road density.',
			gn: "Laja oñemboikuaa jeike opyta, jeike ayvúva ha jy mombyry. Oñembojoaju territorios ohechauka ambue ambue connectividad.",
			pt: 'Os tipos distinguem conectividade plena (proximidade a serviços e vias), acessibilidade parcial (próximo a uma via, mas distante de serviços especializados) e isolamento funcional (longe de tudo). A comparação entre territórios revela diferenças estruturais em conectividade conforme a topografia e a densidade viária.',
		},
		method: {
			es: `${METHOD_COMPARABLE.es} 5 variables con goalposts fijos: tiempo a capital [5, 500] min, tiempo a ciudad ≥50k [5, 350] min, distancia a hospital [0, 35] km, distancia a escuela [0, 20] km, distancia a ruta principal [0, 25] km. Capital = Posadas (MIS) / Encarnación (ITA), calculado vía MCP_Geometric sobre superficie de fricción Oxford MAP 2019. Fuentes: Oxford MAP friction_surface_2019 + accessibility_to_cities_2015 + OpenStreetMap (hospitales, escuelas, rutas).`,
			en: `${METHOD_COMPARABLE.en} 5 variables with fixed goalposts: time to department capital [5, 500] min, time to city ≥50k [5, 350] min, distance to hospital [0, 35] km, distance to school [0, 20] km, distance to primary road [0, 25] km. Capital = Posadas (MIS) / Encarnación (ITA), calculated via MCP_Geometric over Oxford MAP 2019 friction surface. Sources: Oxford MAP friction_surface_2019 + accessibility_to_cities_2015 + OpenStreetMap (hospitals, schools, roads).`,
		},
	},
	carbon_stock: {
		howToRead: {
			es: 'El mapa muestra el stock de carbono total por hexágono (biomasa aérea + subterránea + carbono del suelo) y el balance anual de emisiones/remociones. Colores más intensos indican mayor stock. Los valores se muestran en unidades físicas (tC/ha, MgCO2/ha). Comparable entre Misiones e Itapúa.',
			en: 'The map shows the total carbon stock per hexagon (above-ground + below-ground biomass + soil carbon) and the annual emissions/removals balance. More intense colours indicate higher stock. Values are shown in physical units (tC/ha, MgCO₂/ha). Comparable between Misiones and Itapúa.',
			gn: "Mapa ohechauka carbono stock hexágono-pe (biomasa + suelo) ha balance emisiones/remociones. Pytã mombyry = yvate stock. Ojoguáva Misiones ha Itapúa.",
			pt: 'O mapa mostra o estoque total de carbono por hexágono (biomassa aérea + subterrânea + carbono do solo) e o balanço anual de emissões/remoções. Cores mais intensas indicam maior estoque. Os valores são exibidos em unidades físicas (tC/ha, MgCO₂/ha). Comparável entre Misiones e Itapúa.',
		},
		implications: {
			es: 'Las zonas de alto stock con balance neto negativo (sumidero) son candidatas para créditos de carbono por conservación. Las zonas de alto stock con balance positivo (emisor) son prioridad para intervención REDD+. Las zonas de bajo stock con alta productividad (NPP) tienen potencial de restauración y secuestro futuro. *Valor teórico del carbono: estimación de referencia calculada como stock total x 3.67 (conversión C a CO2) x USD 10/tCO2e (mediana del mercado voluntario 2024, Ecosystem Marketplace 2024). No representa un precio de venta ni el valor realizable de un predio. La monetización efectiva requiere un proyecto certificado (VCS, Gold Standard) con línea base, adicionalidad demostrada y costos de transacción que reducen significativamente el valor neto.',
			en: 'High-stock zones with a net negative balance (carbon sink) are candidates for conservation carbon credits. High-stock zones with a positive balance (carbon source) are a priority for REDD+ intervention. Low-stock zones with high productivity (NPP) have restoration potential and future sequestration capacity. *Theoretical carbon value: reference estimate calculated as total stock × 3.67 (C to CO₂ conversion) × USD 10/tCO₂e (voluntary market median 2024, Ecosystem Marketplace 2024). This does not represent a sale price or the realisable value of any property. Effective monetisation requires a certified project (VCS, Gold Standard) with a documented baseline, demonstrated additionality and transaction costs that significantly reduce net value.',
			gn: "Yvate stock, balance negativo (sumidero) = candidato crédito carbono. Yvate stock, balance positivo (emisor) = prioridad REDD+. Michĩ stock, yvate NPP = potencial restauración. *Valor carbono: stock × 3.67 × USD 10/tCO2e (mediana mercado voluntario 2024). Ndahéi precio venta.",
			pt: 'Zonas de alto estoque com balanço líquido negativo (sumidouro) são candidatas a créditos de carbono por conservação. Zonas de alto estoque com balanço positivo (fonte) são prioridade para intervenção REDD+. Zonas de baixo estoque com alta produtividade (NPP) têm potencial de restauração e sequestro futuro. *Valor teórico do carbono: estimativa de referência calculada como estoque total × 3,67 (conversão C para CO₂) × USD 10/tCO₂e (mediana do mercado voluntário 2024, Ecosystem Marketplace 2024). Não representa um preço de venda nem o valor realizável de um imóvel. A monetização efetiva requer um projeto certificado (VCS, Gold Standard) com linha de base, adicionalidade demonstrada e custos de transação que reduzem significativamente o valor líquido.',
		},
		method: {
			es: `${METHOD_COMPARABLE.es} Score compuesto: media geométrica de biomasa aérea [0, 300] Mg/ha, carbono total [0, 400] tC/ha, carbono orgánico del suelo [0, 472] g/dm³ y flujo neto [−100, 100] MgCO2/ha. Biomasa aérea: ESA CCI Biomass v6 (100m, Santoro et al. 2024) + GEDI L4B lidar (1km, validación). Biomasa subterránea: Cairns et al. (1997): BGB = 0.489 × AGB^0.89. SOC: SoilGrids v2 (ISRIC, 0–30cm). Flujo de carbono: Harris et al. (2021) / Global Forest Watch (emisiones + remociones + balance neto, 30m, 2001–2024). Productividad: MODIS MOD17A3HGF NPP (500m, 2019–2024). Total carbon = AGB × 0.47 + BGB × 0.47 + SOC. Precio de referencia: Ecosystem Marketplace (2024).`,
			en: `${METHOD_COMPARABLE.en} Composite score: geometric mean of above-ground biomass [0, 300] Mg/ha, total carbon [0, 400] tC/ha, soil organic carbon [0, 472] g/dm³ and net flux [−100, 100] MgCO₂/ha. Above-ground biomass: ESA CCI Biomass v6 (100m, Santoro et al. 2024) + GEDI L4B lidar (1km, validation). Below-ground biomass: Cairns et al. (1997): BGB = 0.489 × AGB^0.89. SOC: SoilGrids v2 (ISRIC, 0–30cm). Carbon flux: Harris et al. (2021) / Global Forest Watch (emissions + removals + net balance, 30m, 2001–2024). Productivity: MODIS MOD17A3HGF NPP (500m, 2019–2024). Total carbon = AGB × 0.47 + BGB × 0.47 + SOC. Reference price: Ecosystem Marketplace (2024).`,
		},
	},
	climate_vulnerability: {
		howToRead: {
			es: 'El mapa clasifica cada hexágono según su vulnerabilidad climática integrada (framework IPCC AR5). Colores cálidos indican mayor vulnerabilidad: alta exposición a eventos extremos, alta sensibilidad ambiental, o baja capacidad adaptativa de la población. Comparable entre Misiones e Itapúa para las dimensiones de exposición y sensibilidad (fuentes satelitales). Nota: para territorios sin datos censales (ej. Itapúa), la capacidad adaptativa usa un valor neutral (50/100) — los componentes de aislamiento y privación de servicios requieren censos nacionales no disponibles para Paraguay.',
			en: 'The map classifies each hexagon according to its integrated climate vulnerability (IPCC AR5 framework). Warm colours indicate higher vulnerability: high exposure to extreme events, high environmental sensitivity, or low adaptive capacity of the population. Comparable between Misiones and Itapúa for the exposure and sensitivity dimensions (satellite sources). Note: for territories without census data (e.g. Itapúa), adaptive capacity uses a neutral value (50/100) — the isolation and service deprivation components require national censuses not available for Paraguay.',
			gn: "Mapa oñemomba'e hexágono kuéra vulnerabilidad climática IPCC AR5 rehegua. Pytã yvate = yvate vulnerabilidad: exposición, sensibilidad ha capacidad adaptativa. Ojoguáva Misiones ha Itapúa exposición ha sensibilidad rehegua.",
			pt: 'O mapa classifica cada hexágono conforme sua vulnerabilidade climática integrada (framework IPCC AR5). Cores quentes indicam maior vulnerabilidade: alta exposição a eventos extremos, alta sensibilidade ambiental ou baixa capacidade adaptativa da população. Comparável entre Misiones e Itapúa para as dimensões de exposição e sensibilidade (fontes satelitais). Nota: para territórios sem dados censitários (ex. Itapúa), a capacidade adaptativa usa um valor neutro (50/100) — os componentes de isolamento e privação de serviços requerem censos nacionais não disponíveis para o Paraguai.',
		},
		implications: {
			es: 'Las zonas de alta vulnerabilidad integral requieren atención prioritaria en planes de adaptación climática. Las zonas con alta exposición pero buena capacidad adaptativa pueden absorber shocks; las zonas con baja capacidad adaptativa son vulnerables incluso ante exposición moderada. Este índice es el insumo estándar para fondos climáticos (GCF, GEF, Banco Mundial).',
			en: 'Zones of high integrated vulnerability require priority attention in climate adaptation plans. Zones with high exposure but good adaptive capacity can absorb shocks; zones with low adaptive capacity are vulnerable even to moderate exposure. This index is the standard input for climate funds (GCF, GEF, World Bank).',
			gn: "Yvy yvate vulnerabilidad oguereko prioridad planes adaptación climática-pe. Alta exposición, buena capacidad = oñembyatypa shock; michĩ capacidad = vulnerable mba'eichagua exposición. Ko índice ojeporúva GCF, GEF, Banco Mundial-pe.",
			pt: 'Zonas de alta vulnerabilidade integrada requerem atenção prioritária em planos de adaptação climática. Zonas com alta exposição mas boa capacidade adaptativa podem absorver choques; zonas com baixa capacidade adaptativa são vulneráveis mesmo ante exposição moderada. Este índice é o insumo padrão para fundos climáticos (GCF, GEF, Banco Mundial).',
		},
		method: {
			es: `${METHOD_COMPARABLE.es} 8 variables agrupadas en 3 dimensiones IPCC: Exposición (estrés térmico MODIS LST, riesgo inundación JRC/S1, estrés hídrico ET/PET, frecuencia fuego MODIS MCD64A1), Sensibilidad (pérdida forestal Hansen GFC, desprotección vegetal Hansen treecover), Capacidad Adaptativa (aislamiento geoespacial Oxford MAP, privación de servicios INDEC 2022 — solo Argentina; para otros territorios se asigna valor neutral 50/100). Sub-índices: media geométrica por dimensión. Score final: media geométrica de las 3 dimensiones. PCA + k-means para tipología.`,
			en: `${METHOD_COMPARABLE.en} 8 variables grouped in 3 IPCC dimensions: Exposure (thermal stress MODIS LST, flood risk JRC/S1, water stress ET/PET, fire frequency MODIS MCD64A1), Sensitivity (Hansen GFC forest loss, Hansen treecover vegetation exposure), Adaptive Capacity (geospatial isolation Oxford MAP, service deprivation INDEC 2022 — Argentina only; neutral value 50/100 for other territories). Sub-indices: geometric mean per dimension. Final score: geometric mean of 3 dimensions. PCA + k-means for typology.`,
		},
	},
	pm25_drivers: {
		howToRead: {
			es: 'El mapa muestra la calidad del aire en cada hexágono, medida como concentración media de PM2.5 (partículas finas < 2.5 µm) y descompuesta en cuatro drivers: fuego regional, clima, terreno y vegetación. Score alto (colores fríos) = mejor calidad del aire; score bajo (colores cálidos) = mayor concentración de PM2.5. Comparable entre Misiones e Itapúa. Selecciona un departamento para ver la contribución relativa de cada driver.',
			en: 'The map shows air quality in each hexagon, measured as mean PM2.5 concentration (fine particles < 2.5 µm) and decomposed into four drivers: regional fire, climate, terrain and vegetation. High score (cool colours) = better air quality; low score (warm colours) = higher PM2.5 concentration. Comparable between Misiones and Itapúa. Select a department to view the relative contribution of each driver.',
			gn: "Mapa ohechauka tyre'ỹ aire hexágono-pe, PM2.5 mba'épe ha drivers: tata, ára, yvy ha ka'aguy. Score yvate (sovy) = porã aire; michĩ (pyta) = yvate PM2.5. Ojoguáva Misiones ha Itapúa.",
			pt: 'O mapa mostra a qualidade do ar em cada hexágono, medida como concentração média de PM2.5 (partículas finas < 2,5 µm) e decomposta em quatro drivers: fogo regional, clima, terreno e vegetação. Score alto (cores frias) = melhor qualidade do ar; score baixo (cores quentes) = maior concentração de PM2.5. Comparável entre Misiones e Itapúa. Selecione um departamento para ver a contribuição relativa de cada driver.',
		},
		implications: {
			es: 'La intensidad de fuego regional es el driver dominante de PM2.5: las quemas agrícolas y forestales en provincias vecinas y países limítrofes elevan la concentración de partículas finas incluso en zonas sin deforestación local. Las zonas con alta contribución climática son sensibles a eventos de inversión térmica que atrapan contaminantes. La vegetación actúa como filtro natural — la pérdida de cobertura arbórea reduce la capacidad de depuración del aire.',
			en: 'Regional fire intensity is the dominant PM2.5 driver: agricultural and forest burns in neighbouring provinces and countries raise fine particle concentrations even in zones without local deforestation. Zones with high climate contribution are sensitive to thermal inversion events that trap pollutants. Vegetation acts as a natural filter — tree cover loss reduces air purification capacity.',
			gn: "Tata regional = driver dominante PM2.5: tata agrícola ha forestal provincias ha países ndive oñemboyvate partículas. Ára ohechauka inversión térmica. Ka'aguy = filtro natural; oguejyvo yvyra cobertura oguejy capacidad aire.",
			pt: 'A intensidade do fogo regional é o driver dominante do PM2.5: as queimadas agrícolas e florestais em províncias vizinhas e países limítrofes elevam a concentração de partículas finas mesmo em zonas sem desmatamento local. As zonas com alta contribuição climática são sensíveis a eventos de inversão térmica que aprisionam poluentes. A vegetação atua como filtro natural — a perda de cobertura arbórea reduz a capacidade de purificação do ar.',
		},
		method: {
			es: `Score de exposición normalizado con goalpost fijo: concentración media PM2.5 [5, 30] µg/m³ (0 = aire limpio, 100 = alta exposición). Descomposición por machine learning (LightGBM, SHAP feature attribution). Fuente primaria: Atmospheric Composition Analysis Group (ACAG) V6.GL.02 (Dalhousie University, van Donkelaar et al. 2021), panel 1998–2022, resolución 0.01° (~1 km). Modelo entrenado con 31 covariables ambientales (R² = 0.93 en validación cruzada espacial leave-one-department-out). Drivers agrupados por SHAP: fuego regional (contribución dominante, ΔR² = 0.195), clima (precipitación, temperatura), terreno (elevación, pendiente) y vegetación (NDVI, NPP). El toggle temporal compara periodo 2001–2010 vs 2013–2022. Resolución espacial: H3 resolución 9.`,
			en: `Normalised exposure score with fixed goalpost: mean PM2.5 concentration [5, 30] µg/m³ (0 = clean air, 100 = high exposure). Machine-learning decomposition (LightGBM, SHAP feature attribution). Primary source: Atmospheric Composition Analysis Group (ACAG) V6.GL.02 (Dalhousie University, van Donkelaar et al. 2021), panel 1998–2022, resolution 0.01° (~1 km). Model trained with 31 environmental covariates (R² = 0.93 in spatial leave-one-department-out cross-validation). Drivers grouped by SHAP: regional fire (dominant contribution, ΔR² = 0.195), climate (precipitation, temperature), terrain (elevation, slope) and vegetation (NDVI, NPP). Temporal toggle compares period 2001–2010 vs 2013–2022. Spatial resolution: H3 resolution 9.`,
		},
	},
	productive_activity: {
		howToRead: {
			es: 'El mapa muestra la intensidad de actividad productiva medida por luces nocturnas satelitales (VIIRS). Colores cálidos = mayor radiancia nocturna = mayor actividad económica. Al hacer click se ven 6 indicadores en valores reales: luces, productividad vegetal, verdor, superficie construida, conversión forestal y temperatura. El toggle temporal compara con el periodo base (2014–2017 para VIIRS, 2005–2012 para otros indicadores). Comparable entre Misiones e Itapúa.',
			en: 'The map shows the intensity of productive activity measured by satellite night lights (VIIRS). Warm colours = greater night-time radiance = higher economic activity. Clicking reveals 6 indicators in real values: lights, vegetation productivity, greenness, built surface, forest conversion and temperature. The temporal toggle compares with the baseline period (2014–2017 for VIIRS, 2005–2012 for other indicators). Comparable between Misiones and Itapúa.',
			gn: "Mapa ohechauka tembiapo intensidad luces nocturnas (VIIRS). Pytã = yvate radiancia = yvate actividad económica. Click reheve ohecháva 6 indicadores. Toggle temporal oñembojoaju base (2014–2017 VIIRS). Ojoguáva Misiones ha Itapúa.",
			pt: 'O mapa mostra a intensidade de atividade produtiva medida por luzes noturnas satelitais (VIIRS). Cores quentes = maior radiância noturna = maior atividade econômica. Ao clicar, veem-se 6 indicadores em valores reais: luzes, produtividade vegetal, verdor, superfície construída, conversão florestal e temperatura. O toggle temporal compara com o período base (2014–2017 para VIIRS, 2005–2012 para outros indicadores). Comparável entre Misiones e Itapúa.',
		},
		implications: {
			es: 'Las zonas con alta radiancia nocturna y crecimiento positivo (delta > 0) son polos económicos en expansión. Zonas con alta productividad vegetal (NPP) pero baja radiancia son áreas rurales productivas pero no urbanizadas. Un aumento de temperatura superficial (LST) junto con aumento de superficie construida indica urbanización activa. La conversión forestal alta combinada con baja actividad económica puede indicar deforestación sin desarrollo productivo asociado.',
			en: 'Zones with high night-time radiance and positive growth (delta > 0) are expanding economic poles. Zones with high vegetation productivity (NPP) but low radiance are productive but non-urbanised rural areas. An increase in surface temperature (LST) together with an increase in built surface indicates active urbanisation. High forest conversion combined with low economic activity may indicate deforestation without associated productive development.',
			gn: "Yvate radiancia ha crecimiento positivo = polo económico ojehúva. Yvate NPP ha michĩ radiancia = yvy produktivo ndatëtãvéima. LST yvate + superficie construida = urbanización activa. Yvate conversión forestal + michĩ actividad = deforestación sin desarrollo.",
			pt: 'Zonas com alta radiância noturna e crescimento positivo (delta > 0) são polos econômicos em expansão. Zonas com alta produtividade vegetal (NPP) mas baixa radiância são áreas rurais produtivas, mas não urbanizadas. Um aumento de temperatura superficial (LST) junto com aumento de superfície construída indica urbanização ativa. Alta conversão florestal combinada com baixa atividade econômica pode indicar desmatamento sem desenvolvimento produtivo associado.',
		},
		method: {
			es: `Score de actividad normalizado con goalpost fijo: radiancia nocturna VIIRS [0, 15] nW/cm²/sr (0 = sin actividad, 100 = alta actividad). Seis indicadores satelitales en valores físicos reales: VIIRS nightlights (NOAA, 500m, 2014–2025): radiancia media nocturna. NPP (MODIS, 1km, 2005–2024): productividad primaria neta en gC/m²/año. NDVI (MODIS, 250m, 2005–2024): índice de vegetación. GHSL built surface (JRC, 10m, epochs 2000/2020): fracción construida. Hansen forest loss (UMD/Landsat, 30m, 2001–2024): pérdida acumulada. LST (MODIS, 1km, 2005–2024): temperatura superficial diurna °C. Muestreo bilineal al centroide de cada hexágono H3 resolución 9 (~0.1 km²).`,
			en: `Normalised activity score with fixed goalpost: VIIRS night-time radiance [0, 15] nW/cm²/sr (0 = no activity, 100 = high activity). Six satellite indicators in real physical values: VIIRS nightlights (NOAA, 500m, 2014–2025): mean night-time radiance. NPP (MODIS, 1km, 2005–2024): net primary productivity in gC/m²/year. NDVI (MODIS, 250m, 2005–2024): vegetation index. GHSL built surface (JRC, 10m, epochs 2000/2020): built fraction. Hansen forest loss (UMD/Landsat, 30m, 2001–2024): cumulative loss. LST (MODIS, 1km, 2005–2024): daytime surface temperature °C. Bilinear sampling to H3 resolution 9 centroid (~0.1 km²).`,
		},
	},
	deforestation_dynamics: {
		howToRead: {
			es: 'Cada hexágono muestra la tasa de pérdida forestal observada en ese punto exacto (pixel Landsat 30m). Colores cálidos = mayor pérdida forestal reciente (2015–2024). El toggle temporal permite comparar con la línea base (2001–2010): el modo "Cambio" muestra si la deforestación aceleró (rojo) o frenó (verde) respecto al periodo base. Comparable entre Misiones e Itapúa.',
			en: 'Each hexagon shows the forest loss rate observed at that exact point (Landsat 30m pixel). Warm colours = greater recent forest loss (2015–2024). The temporal toggle allows comparison with the baseline (2001–2010): "Change" mode shows whether deforestation accelerated (red) or slowed (green) relative to the baseline period. Comparable between Misiones and Itapúa.',
			gn: "Peteĩ-peteĩ hexágono ohechauka ka'aguy reiguáva tasa pixel Landsat 30m-pe. Pytã = yvate pérdida forestal (2015–2024). Toggle temporal oñembojoaju línea base (2001–2010). Ojoguáva Misiones ha Itapúa.",
			pt: 'Cada hexágono mostra a taxa de perda florestal observada naquele ponto exato (pixel Landsat 30m). Cores quentes = maior perda florestal recente (2015–2024). O toggle temporal permite comparar com a linha de base (2001–2010): o modo "Mudança" mostra se o desmatamento acelerou (vermelho) ou desacelerou (verde) em relação ao período base. Comparável entre Misiones e Itapúa.',
		},
		implications: {
			es: "Las zonas con alta tasa de pérdida sostenida representan frentes de deforestación activos donde la conversión del bosque nativo continúa. Las zonas donde la deforestación frenó (delta negativo) pueden reflejar el efecto de regulación ambiental (Ley de Bosques en Argentina, leyes forestales en Paraguay) o el agotamiento del recurso. Las zonas que aceleraron requieren atención prioritaria de fiscalización.",
			en: "Zones with a sustained high loss rate represent active deforestation fronts where native forest conversion continues. Zones where deforestation slowed (negative delta) may reflect environmental regulation (Argentina's Forest Law, Paraguay's forestry laws) or resource depletion. Zones that accelerated require priority enforcement attention.",
			gn: "Yvate pérdida forestal sostenida = frente deforestación activo. Delta negativo = regulación ambiental (Ley Bosques) o agotamiento. Yvate aceleración = fiscalización prioritaria.",
			pt: 'Zonas com alta taxa de perda sustentada representam frentes de desmatamento ativos onde a conversão da floresta nativa continua. Zonas onde o desmatamento desacelerou (delta negativo) podem refletir o efeito da regulação ambiental (Lei de Florestas na Argentina, leis florestais no Paraguai) ou o esgotamento do recurso. Zonas que aceleraram requerem atenção prioritária de fiscalização.',
		},
		method: {
			es: `Score de deforestación normalizado con goalpost fijo: tasa de pérdida anual [0, 5] %/año (0 = sin pérdida, 100 = pérdida máxima). Fuente: Hansen Global Forest Change v1.12 (University of Maryland / Google), derivado de series temporales Landsat a 30m, cobertura 2001–2024. Estadísticas zonales verdaderas: cada hexágono H3 resolución 9 (~0.1 km²) recibe el conteo de píxeles de pérdida por año dentro de su polígono (no centroide). La tasa se calcula como fracción de píxeles con pérdida detectada en cada periodo. Línea base: 2001–2010; actual: 2015–2024. Pérdida acumulada goalpost: [0, 40]%. Actualización automática vía GitHub Actions cuando Hansen publica nuevos datos (~abril de cada año).`,
			en: `Normalised deforestation score with fixed goalpost: annual loss rate [0, 5] %/year (0 = no loss, 100 = maximum loss). Source: Hansen Global Forest Change v1.12 (University of Maryland / Google), derived from Landsat time series at 30m, coverage 2001–2024. True zonal statistics: each H3 resolution 9 hexagon (~0.1 km²) receives the pixel count of annual loss within its polygon (not centroid). Rate calculated as the fraction of pixels with detected loss in each period. Baseline: 2001–2010; current: 2015–2024. Cumulative loss goalpost: [0, 40]%. Automatic update via GitHub Actions when Hansen releases new data (~April each year).`,
		},
	},
};

export function getMethodologyContent(analysisId: string): LocalizedMethodologyContent | null {
	return ANALYSIS_CONTENT[analysisId] ?? null;
}

export function listMethodologyIds(): string[] {
	return Object.keys(ANALYSIS_CONTENT);
}
