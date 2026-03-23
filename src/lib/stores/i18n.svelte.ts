export type Locale = 'es' | 'en' | 'gn';

const dict: Record<string, Record<Locale, string>> = {
	// Header
	'header.title': { es: 'spatia.ar', en: 'spatia.ar', gn: 'spatia.ar' },
	'header.subtitle': { es: 'Inteligencia Territorial para Misiones', en: 'Territorial Intelligence for Misiones', gn: "Yvy Rekokatu Misiones-pe" },

	// Controls
	'ctrl.tilt': { es: 'Inclinación', en: 'Tilt', gn: "Je'apy" },
	'ctrl.clear': { es: 'Limpiar', en: 'Clear', gn: "Mopotĩ" },

	// Sidebar
	'side.hover': { es: 'Scroll para zoom · Click derecho + arrastrar para rotar el mapa', en: 'Scroll to zoom · Right-click + drag to rotate the map', gn: "Scroll zoom hag̃ua · Click derecho + arrastrar mapa mbojere hag̃ua" },
	'side.deselect': { es: 'Click para quitar', en: 'Click to remove', gn: "Ehesakutu emboguete hag̃ua" },

	// Radio stats sections
	'stats.buildingEstimates': { es: 'Estimaciones por edificaciones', en: 'Building estimates', gn: "Óga rehegua" },
	'stats.census': { es: 'Censo 2022', en: 'Census 2022', gn: "Papapy 2022" },
	'stats.socioeconomic': { es: 'Socioeconómico', en: 'Socioeconomic', gn: "Teko porã" },
	'stats.comparison': { es: 'Comparación', en: 'Comparison', gn: "Jojaha" },
	'stats.selection': { es: 'Selección', en: 'Selection', gn: 'Jeporavo' },

	// Stat labels
	'label.population': { es: 'Población', en: 'Population', gn: 'Yvypóra' },
	'label.males': { es: 'Varones', en: 'Males', gn: "Kuimba'e" },
	'label.females': { es: 'Mujeres', en: 'Females', gn: 'Kuña' },
	'label.dwellings': { es: 'Viviendas', en: 'Dwellings', gn: 'Óga' },
	'label.households': { es: 'Hogares', en: 'Households', gn: 'Ógape' },
	'label.area': { es: 'Área', en: 'Area', gn: "Yvy" },
	'label.activityRate': { es: 'Tasa de actividad', en: 'Econ. activity rate', gn: "Tembiapo jeku'e" },
	'label.employmentRate': { es: 'Tasa de empleo', en: 'Employment rate', gn: "Tembiapo reko" },
	'label.unemploymentRate': { es: 'Tasa de desocupación', en: 'Unemployment rate', gn: "Tembiapo'ỹ" },
	'label.avgHousehold': { es: 'Tamaño medio hogar', en: 'Avg household size', gn: "Óga tuichakue" },
	'label.ubn': { es: 'NBI (%)', en: 'UBN (%)', gn: "NBI (%)" },
	'label.overcrowding': { es: 'Hacinamiento (%)', en: 'Overcrowding (%)', gn: "Ñembyaty (%)" },
	'label.masculinityRate': { es: 'Tasa de masculinidad', en: 'Masculinity rate', gn: "Kuimba'e jeku'e" },
	'label.coverage': { es: 'Cobertura', en: 'Coverage', gn: "Joapy" },
	'label.buildings': { es: 'Edificaciones', en: 'Buildings', gn: 'Óga' },
	'label.totalArea': { es: 'Área total', en: 'Total area', gn: 'Yvy opavave' },
	'label.avgHeight': { es: 'Altura promedio (pond.)', en: 'Avg height (weighted)', gn: "Yvatekue" },

	// Tooltip
	'tip.building': { es: 'Edificación:', en: 'Building:', gn: 'Óga:' },
	'tip.height': { es: 'Altura', en: 'Height', gn: 'Yvate' },
	'tip.area': { es: 'Área', en: 'Area', gn: 'Yvy' },
	'tip.estPersons': { es: 'Personas est.:', en: 'Est. persons:', gn: "Yvypóra:" },
	'tip.radio': { es: 'Radio', en: 'Radio', gn: 'Radio' },
	'tip.pop': { es: 'Pob.:', en: 'Pop:', gn: "Yvypóra:" },
	'tip.density': { es: 'Densidad:', en: 'Density:', gn: "Yvypóra/km\u00B2:" },

	// Legend
	'legend.estPersons': { es: 'Población estimada por edificación', en: 'Est. population per building', gn: "Yvypóra óga pegua" },

	// Language selector
	'lang.note': { es: '', en: '', gn: '* Ñe\'ẽ guaraní: traducción aproximada' },

	// Partial warning
	'warn.partial': { es: '\u26A0 Algunas edificaciones pueden estar fuera de la vista actual.', en: '\u26A0 Some buildings may be outside the current view.', gn: "\u26A0 Oĩ óga oimeraẽva okápe." },

	// Chart
	'chart.absolute': { es: 'Valores absolutos', en: 'Absolute values', gn: "Papapy" },
	'chart.rates': { es: 'Tasas (%)', en: 'Rates (%)', gn: "Jeku'e (%)" },

	// Chat
	'chat.placeholder': { es: 'Preguntale a Spatia...', en: 'Ask Spatia...', gn: "Eporandu Spatia-pe..." },
	'chat.thinking': { es: 'Pensando', en: 'Thinking', gn: "Oñeha'ã" },
	'chat.searching': { es: 'Buscando', en: 'Searching', gn: "Oheka" },
	'chat.error': { es: 'Error al procesar la consulta', en: 'Error processing query', gn: "Javy oĩ" },
	'chat.noKey': { es: 'Configurá tu API key primero (click ⚙)', en: 'Set your API key first (click ⚙)', gn: "Emoĩ ne API key (⚙)" },
	'chat.send': { es: 'Enviar', en: 'Send', gn: "Mondo" },
	'chat.emptyHint': { es: 'Explorá los datos de Misiones', en: 'Explore Misiones data', gn: "Ehecha Misiones mba'ekuaa" },
	'chat.errorApiKey': { es: 'API key inválida. Revisala en ⚙', en: 'Invalid API key. Check ⚙', gn: "API key ndoikói" },
	'chat.retry': { es: 'Reintentar', en: 'Retry', gn: "Eñeha'ã jey" },
	'label.waterNetwork': { es: 'Sin red de agua (%)', en: 'No water network (%)', gn: 'Y juru ỹre (%)' },
	'label.sewerage': { es: 'Cloacas (%)', en: 'Sewerage (%)', gn: 'Ykuaa (%)' },
	'label.dependencyIndex': { es: 'Índ. dependencia', en: 'Dependency index', gn: "Ñemomba'e" },
	'label.university': { es: 'Universitario (%)', en: 'University (%)', gn: "Mbo'ehára (%)" },
	'label.healthCoverage': { es: 'Cobertura salud (%)', en: 'Health coverage (%)', gn: "Tesãi joapy (%)" },
	'label.teenMotherhood': { es: 'Maternidad (%)', en: 'Motherhood (%)', gn: "Sy reko (%)" },

	// ── Lens system ──────────────────────────────────────────────────────────
	'lens.counter': { es: '{n} oportunidades diferenciales', en: '{n} differential opportunities', gn: '{n} oportunidade iñambuéva' },
	'lens.none': { es: 'Sin lente activa', en: 'No active lens', gn: "Lente'ỹ" },
	'lens.selectRadio': { es: 'Seleccioná un radio iluminado', en: 'Select a highlighted radio', gn: 'Eiporavo peteĩ radio' },
	'lens.comparePrompt': { es: 'Seleccioná otro radio en el mapa', en: 'Select another radio on the map', gn: 'Eiporavo ambue radio' },

	// Invertir sub-labels
	'lens.inv.s1': { es: 'Aptitud', en: 'Suitability', gn: 'Oĩporã' },
	'lens.inv.s2': { es: 'Ambiente', en: 'Environment', gn: 'Tekoha' },
	'lens.inv.s3': { es: 'Infraestructura', en: 'Infrastructure', gn: 'Mba\'apo' },
	'lens.inv.s4': { es: 'Accesibilidad', en: 'Access', gn: 'Jeike' },
	'lens.inv.s5': { es: 'Precio', en: 'Price', gn: 'Hepy' },
	'lens.inv.s6': { es: 'Atractivo', en: 'Attract.', gn: 'Hecharã' },

	// Producir sub-labels
	'lens.prod.s1': { es: 'Suelo', en: 'Soil', gn: 'Yvy' },
	'lens.prod.s2': { es: 'Clima', en: 'Climate', gn: 'Ára' },
	'lens.prod.s3': { es: 'Regulación', en: 'Regulation', gn: 'Léi' },
	'lens.prod.s4': { es: 'Riesgo', en: 'Risk', gn: 'Mba\'asy' },
	'lens.prod.s5': { es: 'Logística', en: 'Logistics', gn: 'Rape' },
	'lens.prod.s6': { es: 'Cultivo', en: 'Crop', gn: 'Temity' },

	// Servir sub-labels
	'lens.serv.s1': { es: 'Salud', en: 'Health', gn: 'Tesãi' },
	'lens.serv.s2': { es: 'Educación', en: 'Education', gn: 'Mbo\'e' },
	'lens.serv.s3': { es: 'Vulnerabilidad', en: 'Vulnerability', gn: 'Mba\'asy' },
	'lens.serv.s4': { es: 'Poder adq.', en: 'Purchase power', gn: 'Viru' },
	'lens.serv.s5': { es: 'Crecimiento', en: 'Growth', gn: 'Kasõ' },
	'lens.serv.s6': { es: 'Accesibilidad', en: 'Access', gn: 'Jeike' },

	// Vivir sub-labels
	'lens.viv.s1': { es: 'Servicios', en: 'Services', gn: 'Pytyvõ' },
	'lens.viv.s2': { es: 'Ambiente', en: 'Environment', gn: 'Tekoha' },
	'lens.viv.s3': { es: 'Seguridad', en: 'Safety', gn: 'Tekorosã' },
	'lens.viv.s4': { es: 'Conectividad', en: 'Connectivity', gn: 'Joaju' },
	'lens.viv.s5': { es: 'Costo', en: 'Cost', gn: 'Hepy' },
	'lens.viv.s6': { es: 'Comunidad', en: 'Community', gn: 'Tetã' },

	// Opportunity card sections
	'card.territory': { es: 'Huella territorial', en: 'Territorial footprint', gn: 'Yvy rapykuere' },
	'card.whyHere': { es: 'Por qué aquí', en: 'Why here', gn: "Mba'érepa ápe" },
	'card.advantage': { es: 'Ventaja comparativa', en: 'Comparative advantage', gn: 'Oñembojovakéva' },
	'card.risk': { es: 'Riesgo', en: 'Risk', gn: 'Mba\'asy' },
	'card.compare': { es: 'Comparar con otra zona', en: 'Compare with another zone', gn: 'Ñembojoja ambue hendápe' },
	'card.download': { es: 'Descargar análisis', en: 'Download analysis', gn: 'Emboguejy' },
	'card.score': { es: 'Score', en: 'Score', gn: 'Score' },
	'card.difference': { es: 'Diferencia más notable', en: 'Most notable difference', gn: 'Mba\'e iñambuéva' },
	'card.back': { es: '← Volver a ficha', en: '← Back to card', gn: '← Ejevy' },

	// Chat paywall
	'chat.paywall.title': { es: 'Análisis IA Premium', en: 'Premium AI Analysis', gn: 'IA Premium' },
	'chat.paywall.soon': { es: 'Próximamente', en: 'Coming soon', gn: 'Oguerahátama' },

	// Department drill-down
	'lens.departments': { es: 'Departamentos', en: 'Departments', gn: 'Departamento kuéra' },
	'lens.backToDepts': { es: '← Departamentos', en: '← Departments', gn: '← Departamento kuéra' },
	'lens.opportunities': { es: 'oportunidades', en: 'opportunities', gn: 'oportunidade' },
	'lens.avgScore': { es: 'Score promedio', en: 'Avg score', gn: 'Score mbytekue' },
	'lens.loading': { es: 'Cargando...', en: 'Loading...', gn: 'Oñemyenyhẽ...' },
	'lens.dptoRadios': { es: 'Radios en {dpto}', en: 'Radios in {dpto}', gn: 'Radio {dpto}-pe' },

	// ── Analysis system ─────────────────────────────────────────────────────
	'analysis.menu.title': { es: 'Análisis disponibles', en: 'Available analyses', gn: "Mba'ekuaa oĩva" },
	'analysis.status.available': { es: 'Disponible', en: 'Available', gn: 'Oĩma' },
	'analysis.status.comingSoon': { es: 'En desarrollo', en: 'Coming soon', gn: 'Oguerahátama' },
	'analysis.back': { es: '← Análisis', en: '← Analyses', gn: "← Mba'ekuaa" },
	'analysis.noData': { es: 'Sin datos para este radio', en: 'No data for this radio', gn: "Mba'ekuaa'ỹ ko radio-pe" },
	'analysis.loading': { es: 'Cargando datos...', en: 'Loading data...', gn: "Oñemyenyhẽ mba'ekuaa..." },
	'analysis.comingSoon.body': { es: 'Este análisis está en desarrollo. Próximamente disponible con datos actualizados.', en: 'This analysis is under development. Coming soon with updated data.', gn: "Ko mba'ekuaa oñemoĩhína. Oguerahátama." },

	// Analysis titles
	'analysis.realEstate.title': { es: 'Mercado inmobiliario', en: 'Real estate market', gn: "Yvy ha óga rape" },
	'analysis.realEstate.desc': { es: 'Precios, avisos y tipos de propiedad por radio censal', en: 'Prices, listings and property types by census tract', gn: "Hepy, óga ha yvy radio pegua" },
	'analysis.realEstate.legend': { es: 'Mediana USD/m²', en: 'Median USD/m²', gn: 'USD/m² mbytekue' },
	'analysis.buildingSuitability.title': { es: 'Aptitud constructiva', en: 'Building suitability', gn: "Óga apópe oĩporãva" },
	'analysis.buildingSuitability.desc': { es: 'Pendiente, suelo, riesgo e infraestructura existente', en: 'Slope, soil, risk and existing infrastructure', gn: "Yvy, mba'asy ha mba'apo oĩva" },
	'analysis.territorialProfile.title': { es: 'Perfil territorial', en: 'Territorial profile', gn: 'Yvy rekokatu' },
	'analysis.territorialProfile.desc': { es: 'Resumen multidimensional con 6 ejes temáticos', en: 'Multidimensional summary with 6 thematic axes', gn: "Mba'ekuaa 6 rape rupi" },
	'analysis.buildingPermits.title': { es: 'Permisos de construcción', en: 'Building permits', gn: "Óga apo ñemoneĩ" },
	'analysis.buildingPermits.desc': { es: 'Permisos otorgados por municipio y año', en: 'Permits granted by municipality and year', gn: "Ñemoneĩ táva ha ary rupi" },
	'analysis.vehicleRegistrations.title': { es: 'Patentamientos', en: 'Vehicle registrations', gn: "Mba'yru ñemoneĩ" },
	'analysis.vehicleRegistrations.desc': { es: 'Patentamientos de automotores por departamento', en: 'Vehicle registrations by department', gn: "Mba'yru moĩ departamento rupi" },
	'analysis.mortgageCredit.title': { es: 'Créditos hipotecarios', en: 'Mortgage credit', gn: "Viru ñeme'ẽ" },
	'analysis.mortgageCredit.desc': { es: 'Volumen y accesibilidad de créditos hipotecarios', en: 'Volume and accessibility of mortgage loans', gn: "Viru ñeme'ẽ tuichakue" },

	// Producir analyses
	'analysis.cropProduction.title': { es: 'Producción por cultivo', en: 'Crop production', gn: "Temity rembiapokue" },
	'analysis.cropProduction.desc': { es: 'Series anuales: yerba, té, tabaco, cítricos, granos', en: 'Annual series: yerba mate, tea, tobacco, citrus, grains', gn: "Ka'a, té, petỹ, narã, avati" },
	'analysis.soilSuitability.title': { es: 'Aptitud de suelos', en: 'Soil suitability', gn: 'Yvy iporãva' },
	'analysis.soilSuitability.desc': { es: 'pH, carbono orgánico, textura y capacidad del suelo', en: 'pH, organic carbon, texture and soil capacity', gn: "Yvy rekokatu" },
	'analysis.cropSuitability.title': { es: 'Aptitud de cultivos', en: 'Crop suitability', gn: "Temity oĩporãva" },
	'analysis.cropSuitability.desc': { es: 'Score de aptitud por especie y radio censal', en: 'Suitability score by species and census tract', gn: "Temity oĩporãva radio rupi" },
	'analysis.forestry.title': { es: 'Plantaciones forestales', en: 'Forest plantations', gn: "Ka'aguy ñemitỹ" },
	'analysis.forestry.desc': { es: 'Yerba mate (INTA), pino y eucalipto georeferenciados', en: 'Yerba mate (INTA), pine and eucalyptus geolocated', gn: "Ka'a, pino ha eucalipto" },
	'analysis.commodityPrices.title': { es: 'Precios de commodities', en: 'Commodity prices', gn: "Hepy mba'e oñemba'apóva" },
	'analysis.commodityPrices.desc': { es: 'Precios de referencia MAGyP y FAO', en: 'Reference prices from MAGyP and FAO', gn: "Hepy MAGyP ha FAO" },

	// Servir analyses
	'analysis.healthCoverage.title': { es: 'Cobertura de salud', en: 'Health coverage', gn: 'Tesãi joapy' },
	'analysis.healthCoverage.desc': { es: 'Centros, distancia a hospital, cobertura obra social', en: 'Facilities, hospital distance, social insurance coverage', gn: "Tesãirenda, hospita'i, joapy" },
	'analysis.educationCoverage.title': { es: 'Cobertura educativa', en: 'Education coverage', gn: "Mbo'e joapy" },
	'analysis.educationCoverage.desc': { es: 'Escuelas, distancia a secundaria, asistencia escolar', en: 'Schools, distance to secondary, school attendance', gn: "Mbo'ehao, mbo'e jehe'a" },
	'analysis.socialVulnerability.title': { es: 'Vulnerabilidad social', en: 'Social vulnerability', gn: "Teko'asy" },
	'analysis.socialVulnerability.desc': { es: 'NBI, hacinamiento, empleo, fecundidad adolescente', en: 'UBN, overcrowding, employment, teen fertility', gn: "NBI, ñembyaty, tembiapo" },
	'analysis.waterNetwork.title': { es: 'Red de agua', en: 'Water network', gn: 'Y juru' },
	'analysis.waterNetwork.desc': { es: '17K segmentos de red, pozos, tanques por radio', en: '17K network segments, wells, tanks by tract', gn: "Y juru, ykuaa radio rupi" },

	// Flood risk analysis
	'analysis.floodRisk.title': { es: 'Riesgo hídrico', en: 'Flood risk', gn: "Y tuicha mba'asy" },
	'analysis.floodRisk.desc': { es: 'Presencia histórica de agua (JRC 1984–2021) e inundación actual (Sentinel-1 SAR) por hexágono H3', en: 'Historical water presence (JRC 1984–2021) and current flooding (Sentinel-1 SAR) per H3 hexagon', gn: "Y rehegua historia guive (JRC 1984–2021) ha ko'ag̃a ysoguy (Sentinel-1 SAR) H3 rupi" },
	'analysis.floodRisk.legend': { es: 'Riesgo hídrico (0–100)', en: 'Flood risk (0–100)', gn: "Y tuicha mba'asy (0–100)" },
	'analysis.flood.riskScore': { es: 'Score de riesgo', en: 'Risk score', gn: "Mba'asy score" },
	'analysis.flood.recurrence': { es: 'Recurrencia', en: 'Recurrence', gn: 'Jey' },
	'analysis.flood.recurrenceDesc': { es: '% de meses con agua detectada', en: '% of months with water detected', gn: '% jasy y reheve' },
	'analysis.flood.jrcOccurrence': { es: 'Presencia histórica (%)', en: 'Historical presence (%)', gn: "Y rehegua historia (%)" },
	'analysis.flood.jrcOccurrenceDesc': { es: '% del tiempo con agua detectada (Landsat 1984–2021)', en: '% of time with water detected (Landsat 1984–2021)', gn: '% ára y reheve (Landsat 1984–2021)' },
	'analysis.flood.jrcRecurrence': { es: 'Recurrencia interanual (%)', en: 'Year-to-year recurrence (%)', gn: 'Jey ary ha ary (%)' },
	'analysis.flood.jrcRecurrenceDesc': { es: '% de años en que el agua vuelve a aparecer', en: '% of years water reappears', gn: '% ary y ojekuaa jey' },
	'analysis.flood.jrcSeasonality': { es: 'Estacionalidad (meses)', en: 'Seasonality (months)', gn: "Ára reípe (jasy)" },
	'analysis.flood.jrcSeasonalityDesc': { es: 'Cantidad de meses con agua por año', en: 'Number of months with water per year', gn: 'Mboy jasy y reheve ary pe' },
	'analysis.flood.currentExtent': { es: 'Extensión actual', en: 'Current extent', gn: "Ko'ãga tuichakue" },
	'analysis.flood.currentExtentDesc': { es: '% del hexágono inundado', en: '% of hexagon flooded', gn: '% hexágono y guýpe' },
	'analysis.flood.riskHigh': { es: 'Riesgo alto', en: 'High risk', gn: "Mba'asy guasu" },
	'analysis.flood.riskMedium': { es: 'Riesgo medio', en: 'Medium risk', gn: "Mba'asy mbyte" },
	'analysis.flood.riskLow': { es: 'Riesgo bajo', en: 'Low risk', gn: "Mba'asy michĩ" },
	'analysis.flood.totalHex': { es: 'Hexágonos', en: 'Hexagons', gn: 'Hexágono' },
	'analysis.flood.highRecurrence': { es: 'Recurrencia >10%', en: 'Recurrence >10%', gn: 'Jey >10%' },
	'analysis.flood.avgScore': { es: 'Score promedio', en: 'Avg score', gn: 'Score mbytekue' },
	'analysis.flood.topDepts': { es: 'Departamentos por riesgo', en: 'Departments by risk', gn: "Departamento mba'asy rupi" },
	'analysis.flood.clickHint': { es: 'Hacé click en un hexágono para ver detalle', en: 'Click a hexagon for details', gn: 'Ehesakutu hexágono ehecha hag̃ua' },
	'analysis.flood.source': { es: 'Fuente: JRC Global Surface Water (Landsat, 1984–2021) + Sentinel-1 SAR (Copernicus)', en: 'Source: JRC Global Surface Water (Landsat, 1984–2021) + Sentinel-1 SAR (Copernicus)', gn: 'Moñe\'ẽha: JRC Global Surface Water (Landsat, 1984–2021) + Sentinel-1 SAR (Copernicus)' },
	'data.source.censo': { es: 'Fuente: INDEC — Censo Nacional de Población 2022', en: 'Source: INDEC — National Population Census 2022', gn: "Moñe'ẽha: INDEC — Censo Nacional 2022" },
	'data.source.realEstate': { es: 'Fuente: Relevamiento de mercado inmobiliario', en: 'Source: Real estate market survey', gn: "Moñe'ẽha: Relevamiento óga ñemuhague" },
	'data.source.buildings': { es: 'Fuente: Detección por IA sobre imágenes satelitales', en: 'Source: AI detection on satellite imagery', gn: "Moñe'ẽha: IA ohechaukáva satélite ra'ãnga rupi" },
	'data.source.catastro': { es: 'Fuente: Dirección General de Catastro, Misiones', en: 'Source: Dirección General de Catastro, Misiones', gn: "Moñe'ẽha: Catastro, Misiones" },
	'analysis.catastro.title': { es: 'Catastro parcelario', en: 'Cadastral parcels', gn: "Yvy ñemohenda" },
	'analysis.catastro.desc': { es: 'Densidad de parcelas urbanas y rurales, áreas medias y presión inmobiliaria (parcelas nuevas)', en: 'Urban and rural parcel density, average areas and real estate pressure (new parcels)', gn: "Yvy ñemohenda táva ha ka'aguy rupi" },
	'analysis.catastro.legend': { es: 'Parcelas urbanas por radio', en: 'Urban parcels per tract', gn: "Yvy táva rupi" },
	'analysis.catastro.totalUrban': { es: 'Parcelas urbanas', en: 'Urban parcels', gn: "Yvy táva" },
	'analysis.catastro.totalRural': { es: 'Parcelas rurales', en: 'Rural parcels', gn: "Yvy ka'aguy" },
	'analysis.catastro.avgAreaUrban': { es: 'Área media urbana', en: 'Avg urban area', gn: "Yvy mbytekue táva" },
	'analysis.catastro.avgAreaRural': { es: 'Área media rural', en: 'Avg rural area', gn: "Yvy mbytekue ka'aguy" },
	'analysis.catastro.newParcels': { es: 'Nuevas (90 días)', en: 'New (90 days)', gn: "Ipyahu (90 ára)" },
	'analysis.catastro.topDepts': { es: 'Departamentos por parcelas', en: 'Departments by parcels', gn: "Departamento yvy rupi" },
	'analysis.catastro.vsAvg': { es: 'vs promedio provincial', en: 'vs provincial average', gn: 'vs tetã mbytekue' },
	'analysis.catastro.pressure': { es: 'Presión inmobiliaria', en: 'Real estate pressure', gn: "Yvy ñemuha reko" },
	'analysis.catastro.parcels': { es: 'parcelas', en: 'parcels', gn: 'yvy' },
	'analysis.catastro.updateFreq': { es: 'Actualización quincenal', en: 'Biweekly update', gn: "Oñembopyahu 15 ára" },
	'analysis.catastro.clickDept': { es: 'Parcelas visibles en el mapa — hacé click en un radio para detalle', en: 'Parcels visible on map — click a tract for detail', gn: "Yvy ojehecha mapápe — eñemí peteĩ radio-pe" },
	'analysis.catastro.thisRadio': { es: 'Este radio', en: 'This tract', gn: 'Ko radio' },
	'analysis.catastro.deptAvg': { es: 'Prom. depto', en: 'Dept avg', gn: 'Depto mbytekue' },
	'analysis.catastro.provAvg': { es: 'Prom. provincia', en: 'Province avg', gn: 'Tetã mbytekue' },
	'analysis.catastro.housingTitle': { es: 'Calidad habitacional', en: 'Housing quality', gn: "Óga rekoporã" },
	'analysis.catastro.h.agua': { es: 'Sin agua red', en: 'No water net.', gn: "Y'ỹ oĩva" },
	'analysis.catastro.h.cloacas': { es: 'Sin cloacas', en: 'No sewerage', gn: "Ysyry'ỹ" },
	'analysis.catastro.h.alumbrado': { es: 'Alumbrado', en: 'Street lights', gn: "Tape rendy" },
	'analysis.catastro.h.pavimento': { es: 'Pavimento', en: 'Paved roads', gn: "Tape porã" },
	'analysis.catastro.h.hacinamiento': { es: 'Hacinamiento', en: 'Overcrowding', gn: "Hetaiterei" },
	'analysis.catastro.h.nbi': { es: 'NBI', en: 'Unmet needs', gn: "Oikotevẽva" },
	'analysis.catastro.petalHint': { es: 'Pétalo: más grande = mejor · punteada = prom. provincial', en: 'Petal: larger = better · dashed = prov. avg', gn: "Pétalo: tuichavéva = iporãvéva" },
	'analysis.catastro.clearAll': { es: 'Limpiar', en: 'Clear all', gn: "Mopotĩ" },
	'data.updatedAt': { es: 'Procesado al', en: 'Processed', gn: 'Oñembopyahu' },
	'analysis.flood.methodTitle': { es: 'Metodologia', en: 'Methodology', gn: "Mba'eichapa" },
	'analysis.flood.methodRecurrence': {
		es: 'Presencia histórica de agua derivada de JRC Global Surface Water (Landsat, 1984–2021). Occurrence indica el % del tiempo con agua detectada; recurrence indica el % de años en que el agua vuelve a aparecer; estacionalidad indica cuántos meses al año hay agua.',
		en: 'Historical water presence from JRC Global Surface Water (Landsat, 1984–2021). Occurrence indicates % of time with water detected; recurrence indicates % of years water reappears; seasonality indicates months of water per year.',
		gn: "Y rehegua historia guive JRC Global Surface Water (Landsat, 1984–2021). Occurrence he'ise % ára y reheve; recurrence he'ise % ary y ojekuaa jey; estacionalidad he'ise mboy jasy y reheve ary pe."
	},
	'analysis.flood.methodExtent': {
		es: 'Porcentaje del hexagono cubierto por agua en la observacion mas reciente (ultima imagen SAR procesada). Mide cuanto del hexagono esta inundado actualmente.',
		en: 'Percentage of the hexagon covered by water in the most recent observation (latest processed SAR image). Measures how much of the hexagon is currently flooded.',
		gn: "Mboy % hexagono y guype oime ko'ag̃a imagen SAR ipahague rupi."
	},
	'analysis.flood.methodScore': {
		es: 'Índice compuesto 0–100: 50% presencia histórica (JRC) + 20% recurrencia interanual (JRC) + 30% extensión actual (Sentinel-1 SAR). Un hexágono permanentemente sobre un río tendrá score alto; un hexágono seco con inundación actual también.',
		en: 'Composite index 0–100: 50% historical presence (JRC) + 20% year-to-year recurrence (JRC) + 30% current extent (Sentinel-1 SAR). A hexagon permanently on a river scores high; a dry hexagon with current flooding also scores high.',
		gn: "Índice 0–100: 50% y rehegua (JRC) + 20% jey ary ha ary (JRC) + 30% ko'ag̃a tuichakue (Sentinel-1 SAR)."
	},

	// Vivir analyses
	'analysis.environment.title': { es: 'Ambiente y vegetación', en: 'Environment & vegetation', gn: "Ka'aguy ha ñu" },
	'analysis.environment.desc': { es: 'NDVI/EVI series, canopy cover, deforestación, OTBN', en: 'NDVI/EVI series, canopy cover, deforestation, OTBN', gn: "Ka'aguy rekokatu" },
	'analysis.naturalRisks.title': { es: 'Riesgos naturales', en: 'Natural risks', gn: "Mba'asy yvy rehegua" },
	'analysis.naturalRisks.desc': { es: 'Fuego, inundación, deslizamiento, erosión', en: 'Fire, flood, landslide, erosion', gn: "Tata, y tuicha, yvy resay" },
	'analysis.transport.title': { es: 'Transporte', en: 'Transport', gn: "Mba'yru rape" },
	'analysis.transport.desc': { es: '223 rutas CNRT, densidad vial, tiempos de viaje', en: '223 CNRT routes, road density, travel times', gn: "Rape, mba'yru oñondive" },
	'analysis.digitalConnectivity.title': { es: 'Conectividad digital', en: 'Digital connectivity', gn: 'Joaju digital' },
	'analysis.digitalConnectivity.desc': { es: 'Internet y móvil por radio (ENACOM)', en: 'Internet and mobile by tract (ENACOM)', gn: "Internet ha celular radio rupi" },

	// Real estate analysis labels
	'analysis.re.provincial': { es: 'Resumen provincial', en: 'Provincial summary', gn: "Tetã guasu rehegua" },
	'analysis.re.listings': { es: 'Avisos activos', en: 'Active listings', gn: "Mba'e oñevendéva" },
	'analysis.re.medianPrice': { es: 'Precio mediano USD/m²', en: 'Median price USD/m²', gn: 'Hepy mbytekue USD/m²' },
	'analysis.re.medianTotal': { es: 'Precio mediano USD', en: 'Median price USD', gn: 'Hepy mbytekue USD' },
	'analysis.re.houses': { es: 'Casas', en: 'Houses', gn: 'Óga' },
	'analysis.re.apartments': { es: 'Departamentos', en: 'Apartments', gn: "Óga guasu" },
	'analysis.re.lots': { es: 'Lotes', en: 'Lots', gn: 'Yvy' },
	'analysis.re.avgArea': { es: 'Superficie promedio', en: 'Average area', gn: "Yvy tuichakue" },
	'analysis.re.vsMedian': { es: 'vs. mediana departamental', en: 'vs. department median', gn: 'vs. departamento mbytekue' },
	'analysis.re.topDepts': { es: 'Top departamentos', en: 'Top departments', gn: 'Departamento iporãvéva' },
	'analysis.re.radioDetail': { es: 'Detalle del radio', en: 'Radio detail', gn: 'Radio rehegua' },
	'analysis.re.propertyTypes': { es: 'Tipos de propiedad', en: 'Property types', gn: "Mba'e lája" },

	// ── Lasso / Zones ──────────────────────────────────────────────────────
	'lasso.toggle': { es: 'Lazo', en: 'Lasso', gn: 'Lazo' },
	'lasso.drawing': { es: 'Dibujando zona...', en: 'Drawing zone...', gn: 'Oñembosako\'i...' },
	'lasso.cancel': { es: 'Cancelar lazo', en: 'Cancel lasso', gn: 'Eheja lazo' },
	'lasso.clearZones': { es: 'Limpiar zonas', en: 'Clear zones', gn: 'Emopotĩ zona' },
	'side.radios': { es: 'Radios censales', en: 'Census tracts', gn: 'Radio censal' },
	'side.clearRadios': { es: 'Limpiar', en: 'Clear', gn: 'Emopotĩ' },
	'source.title': { es: 'Fuentes', en: 'Sources', gn: "Moñe'ẽha" },
	'source.census': { es: 'Datos: INDEC — Censo Nacional de Población 2022', en: 'Data: INDEC — National Population Census 2022', gn: 'Datos: INDEC — Censo Nacional 2022' },
	'source.buildings': { es: 'Edificaciones: Google Open Buildings 2025 + VIDA', en: 'Buildings: Google Open Buildings 2025 + VIDA', gn: 'Óga: Google Open Buildings 2025 + VIDA' },
	'source.basemap': { es: 'Mapa: CARTO Dark Matter (© OpenStreetMap)', en: 'Basemap: CARTO Dark Matter (© OpenStreetMap)', gn: 'Mapa: CARTO Dark Matter (© OpenStreetMap)' },
	'source.terrain': { es: 'Relieve: AWS Terrain Tiles (Mapzen)', en: 'Terrain: AWS Terrain Tiles (Mapzen)', gn: 'Relieve: AWS Terrain Tiles (Mapzen)' },
	'lasso.hint': { es: 'Dibujá una zona arrastrando sobre el mapa. El cálculo tarda unos segundos.', en: 'Draw a zone by dragging on the map. Calculation takes a few seconds.', gn: "Embosako'i zona mapa ári. Ohasa segundos." },
	'zone.title': { es: 'Zona', en: 'Zone', gn: 'Zona' },
	'zone.population': { es: 'Población', en: 'Population', gn: 'Yvypóra' },
	'zone.area': { es: 'Área km²', en: 'Area km²', gn: 'Yvy km²' },
	'zone.radios': { es: 'Radios', en: 'Radios', gn: 'Radio' },
	'zone.noRadios': { es: 'Sin radios en la selección', en: 'No radios in selection', gn: "Radio'ỹ jeporavópe" },
	'zone.petalNote': { es: 'Relativo al promedio provincial (línea punteada = promedio)', en: 'Relative to provincial average (dashed line = average)', gn: 'Tetã guasu mbytekue rehe (línea = mbytekue)' },

	// ── Hex comparison / hex zones ──────────────────────────────────────
	'hex.comparison': { es: 'Comparación de hexágonos', en: 'Hexagon comparison', gn: 'Hexágono jojaha' },
	'hex.hexCount': { es: 'Hexágonos', en: 'Hexagons', gn: 'Hexágono' },
	'hexZone.title': { es: 'Zonas hexagonales', en: 'Hex zones', gn: 'Hexágono zona' },
	'hex.resolution': { es: 'Resolución H3', en: 'H3 resolution', gn: 'H3 tuichakue' },
	'hex.loading': { es: 'Cargando hexágonos...', en: 'Loading hexagons...', gn: 'Oñemyenyhẽ hexágono...' },
	'hex.provAvg': { es: 'prom. provincial', en: 'prov. avg', gn: 'tetã guasu mbytekue' },

	// ── Welcome panel ─────────────────────────────────────────────────────
	'side.welcome.status': { es: 'En desarrollo', en: 'Under development', gn: 'Oñemoĩhína' },
	'side.welcome.desc': {
		es: 'Datos ambientales, sociales y económicos actualizados para cada zona de Misiones. Seleccioná un área, compará indicadores y descargá diagnósticos listos para decisiones.',
		en: 'Up-to-date environmental, social and economic data for every zone in Misiones. Select an area, compare indicators and download decision-ready diagnostics.',
		gn: "Tekoha, teko porã ha teko economía mba'ekuaa pyahu Misiones pegua. Eiporavo peteĩ área, ñembojoja indicador ha emboguejy diagnóstico."
	},
	'side.welcome.pro': { es: 'Spatia Pro', en: 'Spatia Pro', gn: 'Spatia Pro' },
	'side.welcome.pro.ia': { es: 'Asistente IA con contexto territorial completo', en: 'AI assistant with full territorial context', gn: "IA pytyvõhára yvy rekokatu reheve" },
	'side.welcome.pro.pdf': { es: 'Reportes PDF automáticos por zona o radio', en: 'Automatic PDF reports by zone or tract', gn: "PDF reporte zona térã radio rupi" },
	'side.welcome.pro.method': { es: 'Metodología y fuentes documentadas en cada reporte', en: 'Documented methodology and sources in every report', gn: "Mba'eichapa ha moñe'ẽha reporte pepápe" },
	'side.welcome.pro.multi': { es: 'Análisis multi-capa con exportación de datos', en: 'Multi-layer analysis with data export', gn: "Mba'ekuaa heta capa ndive, exporta mba'ekuaa" },
	'side.welcome.pro.support': { es: 'Soporte técnico prioritario', en: 'Priority technical support', gn: "Pytyvõ técnico tenondegua" },
	'side.welcome.pro.cta': { es: 'Solicitar acceso', en: 'Request access', gn: 'Ejerure jeike' },
	'side.welcome.backed': { es: 'Con el apoyo de', en: 'Supported by', gn: 'Pytyvõ reheve' },
} as any;

class I18nStore {
	locale: Locale = $state('es');

	t(key: string): string {
		const entry = dict[key];
		if (!entry) return key;
		return entry[this.locale] ?? entry['en'] ?? key;
	}

	setLocale(l: Locale) {
		this.locale = l;
	}
}

export const i18n = new I18nStore();
export function t(key: string): string { return i18n.t(key); }
