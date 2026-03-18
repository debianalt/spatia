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
