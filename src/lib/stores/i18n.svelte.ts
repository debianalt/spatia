export type Locale = 'es' | 'en' | 'gn';

const dict: Record<string, Record<Locale, string>> = {
	// Header
	'header.title': { es: 'Spatia', en: 'Spatia', gn: 'Spatia' },
	'header.subtitle': { es: 'Inteligencia Territorial para Misiones', en: 'Territorial Intelligence for Misiones', gn: "Yvy Rekokatu Misiones-pe" },

	// Controls
	'ctrl.tilt': { es: 'Inclinación', en: 'Tilt', gn: "Je'apy" },
	'ctrl.clear': { es: 'Limpiar', en: 'Clear', gn: "Mopotĩ" },

	// Sidebar
	'side.hover': { es: 'Posicionar para ver detalles. Click para comparar radios.', en: 'Hover for details. Click to compare radios.', gn: "Eha'ã he'i hag̃ua. Ehesakutu jojaha hag̃ua." },
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
	'label.waterNetwork': { es: 'Red de agua (%)', en: 'Water network (%)', gn: 'Y juru (%)' },
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

	// Legend lens mode
	'legend.lensOpportunity': { es: 'Oportunidad diferencial', en: 'Differential opportunity', gn: 'Oportunidade iñambuéva' },
	'legend.lensRest': { es: 'Sin oportunidad destacada', en: 'No highlighted opportunity', gn: "Oportunidade'ỹ" },

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
