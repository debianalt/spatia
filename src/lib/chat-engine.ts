/**
 * Client-side chat engine — calls Claude API directly from the browser,
 * executes tools against DuckDB-WASM (already loaded) + embedded data.
 */

import { query, isReady } from '$lib/stores/duckdb';
import { PARQUETS } from '$lib/config';
import barrios from '$lib/data/barrios.json';
import centroids from '$lib/data/centroids.json';

// ── Types ──

interface MapAction {
	type: 'highlight' | 'flyTo' | 'choropleth' | 'hex_choropleth';
	redcodes?: string[];
	h3indices?: string[];
	values?: number[];
	indicator?: string;
	lat?: number;
	lng?: number;
	zoom?: number;
}

interface ChartDataSet {
	title: string;
	type: 'bar' | 'ranking';
	data: Array<{ label: string; value: number }>;
	unit?: string;
}

export interface ChatResponse {
	text: string;
	mapActions: MapAction[];
	chartData: ChartDataSet[];
	toolCalls: Array<{ name: string; elapsed: number }>;
}

// ── System prompt ──

const SYSTEM_PROMPT = `Sos Spatia, asistente de inteligencia territorial de Misiones, Argentina.
Tenés acceso a datos del Censo Nacional 2022, imágenes satelitales (NDVI), edificaciones detectadas por IA, indicadores socioeconómicos para los 2.012 radios censales de la provincia, y datos satelitales de riesgo hídrico por hexágono H3 (Sentinel-1 SAR).

INTEGRACIÓN CON MAPA:
- Estás integrado en un mapa interactivo 3D. Cuando usás tools, los radios se resaltan automáticamente en el mapa y la cámara vuela hacia ellos.
- NUNCA digas que no podés mostrar mapas, visualizar en mapa, o mostrar ubicaciones. El mapa está integrado y responde automáticamente a tus tool calls.
- Los rankings con múltiples radios se muestran como choropleth (gradiente de colores) en el mapa.

CIUDADES Y DEPARTAMENTOS:
- Posadas = departamento Capital, Oberá = Oberá, Eldorado = Eldorado, Puerto Iguazú = Iguazú, Jardín América = San Ignacio, Montecarlo = Montecarlo, Apóstoles = Apóstoles.
- Para preguntas sobre una ciudad, usá el filtro departamento correspondiente.

CONSULTAS SUPERLATIVAS ("el más", "el menos", "el peor", "el mejor", "el mayor", "el menor"):
ALGORITMO OBLIGATORIO — seguí estos pasos en orden:
1. Identificá el indicador (pobreza → pct_nbi, empleo → tasa_empleo, etc.)
2. Llamá ranking(indicator=X, order="desc"/"asc", limit=1, departamento=Y)
3. Con el redcode del resultado, llamá get_stats(redcodes=[redcode])
4. Respondé con narrativa incluyendo los datos clave
PROHIBIDO: NO llames search_places, filter_radios, ni múltiples rankings para consultas superlativas. UNA sola llamada a ranking + UNA a get_stats.

BARRIOS:
- No tenés datos a nivel barrio. Trabajás exclusivamente con radios censales.
- Si el usuario pregunta por el "barrio más X", explicá que no tenés datos de barrios pero que el radio censal con mayor/menor X es tal, y reportá sus estadísticas clave.

REGLAS:
- SIEMPRE usá tools para responder preguntas sobre datos. NUNCA inventes números.
- Respondé en el mismo idioma del usuario (español por defecto).
- Ante CUALQUIER mención geográfica (barrio, localidad, departamento, radio, zona, ciudad, colonia, pueblo), SIEMPRE usá una tool para resolverla a redcodes. Usá search_places para barrios/localidades, get_stats o ranking con filtro departamento para departamentos.
- Para comparar departamentos entre sí, usá compare_departments.
- Cuando no encuentres un barrio, explicá que trabajás con radios censales y sugerí buscar por departamento.
- Si no estás seguro qué indicadores existen, usá search_indicators primero.
- Sé conciso pero informativo. Mencioná las fuentes (Censo 2022, NDVI satelital, edificaciones IA).
- Cuando reportes rankings, mencioná el departamento de cada radio para dar contexto geográfico.
- Para preguntas sobre pobreza o vulnerabilidad, usá pct_nbi (NBI = Necesidades Básicas Insatisfechas).
- Para preguntas sobre inundación, riesgo hídrico, o zonas inundables, usá get_flood_risk. Los datos son hexágonos H3 basados en Sentinel-1 SAR con score de riesgo 0-100. Los hexágonos se muestran como choropleth en el mapa.
- Usá formato Markdown para listas y énfasis cuando mejore la legibilidad.

FLUJO DE CONSULTA GEOGRÁFICA:
- Cuando encuentres un lugar o radio específico (vía search_places o ranking), SIEMPRE hacé un get_stats para obtener sus estadísticas detalladas y reportá los valores clave en tu respuesta narrativa (población, NBI, empleo, servicios).

FORMATO DE RESPUESTA:
- Respondé de forma narrativa, clara y directa.
- Cuando sea útil, incluí datos numéricos específicos.
- Si hay múltiples radios relevantes, mencioná los más destacados.`;

// ── Tool definitions (Claude API format) ──

const TOOL_DEFINITIONS = [
	{
		name: 'search_indicators',
		description:
			'Search the indicator catalog to find what data is available. Use this when unsure which column names or indicators exist.',
		input_schema: {
			type: 'object' as const,
			properties: {
				query: { type: 'string', description: 'Search term (e.g. "empleo", "agua", "vegetacion")' },
				theme: { type: 'string', description: 'Optional theme filter: demografia, economia, vulnerabilidad, servicios, educacion, habitat, ambiente, infraestructura, geografia' }
			},
			required: ['query']
		}
	},
	{
		name: 'ranking',
		description:
			'Get a ranking of radios by a specific indicator. Returns top/bottom radios sorted by the given indicator. For superlative queries ("el más", "el mejor"), use limit=1.',
		input_schema: {
			type: 'object' as const,
			properties: {
				indicator: { type: 'string', description: 'Column name from radio_stats (e.g. "pct_nbi", "densidad_hab_km2", "tasa_empleo")' },
				order: { type: 'string', enum: ['asc', 'desc'], description: 'Sort order: "desc" for highest first, "asc" for lowest first' },
				limit: { type: 'number', description: 'Number of results (default 10, max 50)' },
				departamento: { type: 'string', description: 'Optional: filter by departamento name' }
			},
			required: ['indicator', 'order']
		}
	},
	{
		name: 'search_places',
		description:
			'Search for barrios (neighborhoods) by name. Returns matching places with their associated radio censal codes. Do NOT use for superlative queries ("el más", "el mejor", etc.). Only for specific neighborhood name searches.',
		input_schema: {
			type: 'object' as const,
			properties: {
				name: { type: 'string', description: 'Place name to search (e.g. "villa cabello", "itaembe mini")' }
			},
			required: ['name']
		}
	},
	{
		name: 'get_stats',
		description:
			'Get detailed statistics for specific radios or a departamento. Returns all available indicators for the requested areas.',
		input_schema: {
			type: 'object' as const,
			properties: {
				redcodes: { type: 'array', items: { type: 'string' }, description: 'Array of radio censal codes' },
				departamento: { type: 'string', description: 'Departamento name (alternative to redcodes)' },
				indicators: { type: 'array', items: { type: 'string' }, description: 'Specific columns to return (default: all)' }
			}
		}
	},
	{
		name: 'filter_radios',
		description:
			'Filter radios by an indicator condition (e.g. NBI > 30%). Returns matching radios with the indicator value. Do NOT use for superlatives ("el más", "el mejor"). Use ranking with limit=1 instead.',
		input_schema: {
			type: 'object' as const,
			properties: {
				indicator: { type: 'string', description: 'Column name from radio_stats' },
				operator: { type: 'string', enum: ['>', '<', '>=', '<=', '='], description: 'Comparison operator' },
				value: { type: 'number', description: 'Threshold value' },
				departamento: { type: 'string', description: 'Optional: filter by departamento' },
				limit: { type: 'number', description: 'Max results (default 20, max 100)' }
			},
			required: ['indicator', 'operator', 'value']
		}
	},
	{
		name: 'time_series',
		description:
			'Get NDVI vegetation index time series data. Can query by specific radio or aggregate by departamento.',
		input_schema: {
			type: 'object' as const,
			properties: {
				redcode: { type: 'string', description: 'Specific radio censal code' },
				departamento: { type: 'string', description: 'Departamento name (returns average across all radios)' }
			}
		}
	},
	{
		name: 'compare_departments',
		description:
			'Compare departamentos by an indicator. Returns a ranking of departamentos with their average value, number of radios, and highlights the top departamento on the map as a choropleth.',
		input_schema: {
			type: 'object' as const,
			properties: {
				indicator: { type: 'string', description: 'Column name from radio_stats (e.g. "pct_nbi", "tasa_empleo")' },
				order: { type: 'string', enum: ['asc', 'desc'], description: 'Sort order: "desc" for highest first, "asc" for lowest first' },
				limit: { type: 'number', description: 'Number of top departamentos to return (default 5, max 17)' }
			},
			required: ['indicator', 'order']
		}
	},
	{
		name: 'get_flood_risk',
		description:
			'Get satellite-based flood risk data for hexagonal zones (H3 resolution 9). Returns flood recurrence, current flood extent, and composite risk score (0-100). Data from Sentinel-1 SAR radar. Shows hexagonal choropleth on the map.',
		input_schema: {
			type: 'object' as const,
			properties: {
				departamento: { type: 'string', description: 'Filter by departamento name' },
				min_risk_score: { type: 'number', description: 'Minimum risk score threshold (0-100)' },
				limit: { type: 'number', description: 'Max results (default 20, max 100)' }
			},
			required: ['departamento']
		}
	}
];

// ── Indicator catalog (embedded) ──

const INDICATOR_CATALOG = [
	{ id: 'total_personas', nombre: 'Poblacion total', tema: 'demografia', unidad: 'personas', descripcion: 'Total de personas segun Censo 2022' },
	{ id: 'varones', nombre: 'Varones', tema: 'demografia', unidad: 'personas', descripcion: 'Total de varones segun Censo 2022' },
	{ id: 'mujeres', nombre: 'Mujeres', tema: 'demografia', unidad: 'personas', descripcion: 'Total de mujeres segun Censo 2022' },
	{ id: 'area_km2', nombre: 'Area', tema: 'geografia', unidad: 'km2', descripcion: 'Superficie del radio censal' },
	{ id: 'densidad_hab_km2', nombre: 'Densidad poblacional', tema: 'demografia', unidad: 'hab/km2', descripcion: 'Habitantes por km2' },
	{ id: 'pct_nbi', nombre: 'NBI', tema: 'vulnerabilidad', unidad: '%', descripcion: 'Porcentaje de hogares con necesidades basicas insatisfechas' },
	{ id: 'pct_hacinamiento', nombre: 'Hacinamiento', tema: 'vulnerabilidad', unidad: '%', descripcion: 'Porcentaje de hogares con hacinamiento critico' },
	{ id: 'tasa_empleo', nombre: 'Tasa de empleo', tema: 'economia', unidad: '%', descripcion: 'Tasa de empleo de la poblacion en edad de trabajar' },
	{ id: 'tasa_desocupacion', nombre: 'Tasa de desocupacion', tema: 'economia', unidad: '%', descripcion: 'Tasa de desocupacion abierta' },
	{ id: 'tasa_actividad', nombre: 'Tasa de actividad', tema: 'economia', unidad: '%', descripcion: 'Tasa de actividad economica' },
	{ id: 'pct_agua_red', nombre: 'Sin red de agua', tema: 'servicios', unidad: '%', descripcion: 'Porcentaje de hogares sin provision de agua por red publica' },
	{ id: 'pct_cloacas', nombre: 'Cloacas', tema: 'servicios', unidad: '%', descripcion: 'Porcentaje de hogares conectados a red cloacal' },
	{ id: 'pct_universitario', nombre: 'Nivel universitario', tema: 'educacion', unidad: '%', descripcion: 'Porcentaje de poblacion con nivel universitario completo' },
	{ id: 'pct_secundario_comp', nombre: 'Secundario completo', tema: 'educacion', unidad: '%', descripcion: 'Porcentaje de poblacion con secundario completo' },
	{ id: 'tamano_medio_hogar', nombre: 'Tamano medio del hogar', tema: 'habitat', unidad: 'personas', descripcion: 'Promedio de personas por hogar' },
	{ id: 'n_buildings', nombre: 'Edificaciones', tema: 'infraestructura', unidad: 'unidades', descripcion: 'Cantidad de edificaciones detectadas por IA satelital' },
	{ id: 'ndvi_mean', nombre: 'NDVI medio', tema: 'ambiente', unidad: 'indice', descripcion: 'Indice de vegetacion normalizado promedio anual' },
	{ id: 'vulnerability_score', nombre: 'Indice de vulnerabilidad', tema: 'vulnerabilidad', unidad: 'indice', descripcion: 'Score compuesto de vulnerabilidad socioeconomica' },
	{ id: 'vulnerability_class', nombre: 'Clase de vulnerabilidad', tema: 'vulnerabilidad', unidad: 'categoria', descripcion: 'Clasificacion de vulnerabilidad (baja/media/alta/muy alta)' }
];

// ── Column whitelist ──

const ALLOWED_COLUMNS = new Set([
	'redcode', 'departamento', 'total_personas', 'varones', 'mujeres',
	'area_km2', 'densidad_hab_km2', 'pct_nbi', 'pct_hacinamiento',
	'tasa_empleo', 'tasa_desocupacion', 'tasa_actividad', 'pct_agua_red',
	'pct_cloacas', 'pct_universitario', 'pct_secundario_comp',
	'tamano_medio_hogar', 'n_buildings', 'ndvi_mean',
	'vulnerability_score', 'vulnerability_class'
]);

function validateColumn(col: string): string {
	if (!ALLOWED_COLUMNS.has(col)) throw new Error(`Unknown indicator: ${col}`);
	return col;
}

function validateOperator(op: string): string {
	if (!['>', '<', '>=', '<=', '='].includes(op)) throw new Error(`Invalid operator: ${op}`);
	return op;
}

// ── Centroid helper (embedded data) ──

const centroidMap = centroids as Record<string, [number, number]>;

function getCentroid(redcodes: string[]): { lat: number; lng: number } | null {
	let sumLat = 0, sumLng = 0, count = 0;
	for (const rc of redcodes) {
		const c = centroidMap[rc];
		if (c) { sumLat += c[0]; sumLng += c[1]; count++; }
	}
	return count > 0 ? { lat: sumLat / count, lng: sumLng / count } : null;
}

// ── DuckDB query helper ──

async function duckQuery(sql: string): Promise<any[]> {
	if (!isReady()) throw new Error('DuckDB not ready');
	const table = await query(sql);
	const rows: any[] = [];
	for (let i = 0; i < table.numRows; i++) {
		rows.push(table.get(i)!.toJSON());
	}
	return rows;
}

// ── Tool executors ──

interface ToolResult {
	data: any;
	mapActions: MapAction[];
}

async function executeTool(toolName: string, input: any): Promise<ToolResult> {
	switch (toolName) {
		case 'search_indicators': return execSearchIndicators(input);
		case 'ranking': return execRanking(input);
		case 'search_places': return execSearchPlaces(input);
		case 'get_stats': return execGetStats(input);
		case 'filter_radios': return execFilterRadios(input);
		case 'time_series': return execTimeSeries(input);
		case 'compare_departments': return execCompareDepartments(input);
		case 'get_flood_risk': return execGetFloodRisk(input);
		default: throw new Error(`Unknown tool: ${toolName}`);
	}
}

function execSearchIndicators(input: { query: string; theme?: string }): ToolResult {
	const q = input.query.toLowerCase();
	let results = INDICATOR_CATALOG.filter(
		ic => ic.id.includes(q) || ic.nombre.toLowerCase().includes(q) || ic.descripcion.toLowerCase().includes(q)
	);
	if (input.theme) results = results.filter(ic => ic.tema === input.theme);
	return { data: results, mapActions: [] };
}

async function execRanking(input: { indicator: string; order: string; limit?: number; departamento?: string }): Promise<ToolResult> {
	const col = validateColumn(input.indicator);
	const dir = input.order === 'asc' ? 'ASC' : 'DESC';
	const limit = Math.min(input.limit || 10, 50);

	let where = `${col} IS NOT NULL`;
	if (input.departamento) where += ` AND departamento = '${input.departamento.replace(/'/g, "''")}'`;

	const rows = await duckQuery(
		`SELECT redcode, departamento, ${col} AS value FROM '${PARQUETS.radio_stats_master}' WHERE ${where} ORDER BY value ${dir} LIMIT ${limit}`
	);

	const redcodes = rows.map(r => String(r.redcode));
	const values = rows.map(r => Number(r.value));
	const mapActions: MapAction[] = [];

	if (redcodes.length > 1) {
		mapActions.push({ type: 'choropleth', redcodes, values, indicator: input.indicator });
	} else if (redcodes.length === 1) {
		mapActions.push({ type: 'highlight', redcodes });
	}

	const center = getCentroid(redcodes);
	if (center) mapActions.push({ type: 'flyTo', ...center, zoom: input.departamento ? 11 : 9 });

	return { data: rows, mapActions };
}

function execSearchPlaces(input: { name: string }): ToolResult {
	const normalized = input.name.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
	const results = (barrios as any[]).filter(
		b => b.nombre_lower.includes(normalized)
	);

	const mapActions: MapAction[] = [];
	const allRedcodes: string[] = [];
	for (const r of results) {
		if (Array.isArray(r.redcodes)) allRedcodes.push(...r.redcodes);
	}

	if (allRedcodes.length > 0) {
		mapActions.push({ type: 'highlight', redcodes: allRedcodes });
		const center = getCentroid(allRedcodes);
		if (center) mapActions.push({ type: 'flyTo', ...center, zoom: 14 });
	}

	return {
		data: results.map(r => ({
			nombre: r.nombre,
			localidad: r.localidad,
			departamento: r.departamento,
			tipo: r.tipo,
			redcodes: JSON.stringify(r.redcodes)
		})),
		mapActions
	};
}

async function execGetStats(input: { redcodes?: string[]; departamento?: string; indicators?: string[] }): Promise<ToolResult> {
	let cols = '*';
	if (input.indicators && input.indicators.length > 0) {
		const validated = input.indicators.map(validateColumn);
		cols = ['redcode', 'departamento', ...validated].join(', ');
	}

	let where: string;
	if (input.redcodes && input.redcodes.length > 0) {
		const quoted = input.redcodes.map(r => `'${r.replace(/'/g, "''")}'`).join(',');
		where = `redcode IN (${quoted})`;
	} else if (input.departamento) {
		where = `departamento = '${input.departamento.replace(/'/g, "''")}'`;
	} else {
		return { data: [], mapActions: [] };
	}

	const rows = await duckQuery(`SELECT ${cols} FROM '${PARQUETS.radio_stats_master}' WHERE ${where}`);
	const redcodes = rows.map(r => String(r.redcode));
	const mapActions: MapAction[] = [];

	if (redcodes.length > 0) {
		mapActions.push({ type: 'highlight', redcodes });
		const center = getCentroid(redcodes);
		if (center) mapActions.push({ type: 'flyTo', ...center, zoom: 13 });
	}

	return { data: rows, mapActions };
}

async function execFilterRadios(input: { indicator: string; operator: string; value: number; departamento?: string; limit?: number }): Promise<ToolResult> {
	const col = validateColumn(input.indicator);
	const op = validateOperator(input.operator);
	const limit = Math.min(input.limit || 20, 100);

	let where = `${col} ${op} ${input.value}`;
	if (input.departamento) where += ` AND departamento = '${input.departamento.replace(/'/g, "''")}'`;

	const rows = await duckQuery(
		`SELECT redcode, departamento, ${col} AS value FROM '${PARQUETS.radio_stats_master}' WHERE ${where} ORDER BY value ${op.includes('>') ? 'DESC' : 'ASC'} LIMIT ${limit}`
	);

	const redcodes = rows.map(r => String(r.redcode));
	const mapActions: MapAction[] = [];

	if (redcodes.length > 0) {
		mapActions.push({ type: 'highlight', redcodes });
		const center = getCentroid(redcodes);
		if (center) mapActions.push({ type: 'flyTo', ...center, zoom: 10 });
	}

	return { data: rows, mapActions };
}

async function execTimeSeries(input: { redcode?: string; departamento?: string }): Promise<ToolResult> {
	const mapActions: MapAction[] = [];
	let rows: any[];

	if (input.redcode) {
		rows = await duckQuery(
			`SELECT year, mean_ndvi FROM '${PARQUETS.ndvi_annual}' WHERE redcode = '${input.redcode}' ORDER BY year`
		);
		const center = getCentroid([input.redcode]);
		if (center) {
			mapActions.push({ type: 'highlight', redcodes: [input.redcode] });
			mapActions.push({ type: 'flyTo', ...center, zoom: 14 });
		}
	} else if (input.departamento) {
		const dept = input.departamento.replace(/'/g, "''");
		rows = await duckQuery(
			`SELECT n.year, AVG(n.mean_ndvi) as mean_ndvi FROM '${PARQUETS.ndvi_annual}' n JOIN '${PARQUETS.radio_stats_master}' r ON n.redcode = r.redcode WHERE r.departamento = '${dept}' GROUP BY n.year ORDER BY n.year`
		);
		const deptRows = await duckQuery(
			`SELECT redcode FROM '${PARQUETS.radio_stats_master}' WHERE departamento = '${dept}'`
		);
		const deptRedcodes = deptRows.map(r => String(r.redcode));
		if (deptRedcodes.length > 0) {
			mapActions.push({ type: 'highlight', redcodes: deptRedcodes });
			const center = getCentroid(deptRedcodes);
			if (center) mapActions.push({ type: 'flyTo', ...center, zoom: 10 });
		}
	} else {
		rows = await duckQuery(
			`SELECT year, AVG(mean_ndvi) as mean_ndvi FROM '${PARQUETS.ndvi_annual}' GROUP BY year ORDER BY year`
		);
	}

	return { data: rows, mapActions };
}

async function execCompareDepartments(input: { indicator: string; order: string; limit?: number }): Promise<ToolResult> {
	const col = validateColumn(input.indicator);
	const dir = input.order === 'asc' ? 'ASC' : 'DESC';
	const limit = Math.min(input.limit || 5, 17);

	const rows = await duckQuery(
		`SELECT departamento, AVG(${col}) AS value, COUNT(*) AS n_radios FROM '${PARQUETS.radio_stats_master}' WHERE ${col} IS NOT NULL GROUP BY departamento ORDER BY value ${dir} LIMIT ${limit}`
	);

	const mapActions: MapAction[] = [];

	if (rows.length > 0) {
		const deptNames = rows.map(r => r.departamento as string);
		const inList = deptNames.map(d => `'${d.replace(/'/g, "''")}'`).join(',');

		const radioRows = await duckQuery(
			`SELECT redcode, departamento, ${col} AS value FROM '${PARQUETS.radio_stats_master}' WHERE departamento IN (${inList}) AND ${col} IS NOT NULL`
		);

		const redcodes = radioRows.map(r => String(r.redcode));
		const values = radioRows.map(r => Number(r.value));

		if (redcodes.length > 0) {
			mapActions.push({ type: 'choropleth', redcodes, values, indicator: input.indicator });
			const topRedcodes = radioRows.filter(r => r.departamento === deptNames[0]).map(r => String(r.redcode));
			const center = getCentroid(topRedcodes.length > 0 ? topRedcodes : redcodes);
			if (center) mapActions.push({ type: 'flyTo', ...center, zoom: 9 });
		}
	}

	return { data: rows, mapActions };
}

async function execGetFloodRisk(input: { departamento: string; min_risk_score?: number; limit?: number }): Promise<ToolResult> {
	const dept = input.departamento.replace(/'/g, "''");
	const minScore = input.min_risk_score ?? 0;
	const limit = Math.min(input.limit || 20, 100);

	const rows = await duckQuery(
		`SELECT f.h3index, f.jrc_occurrence, f.jrc_recurrence, f.flood_extent_pct, f.flood_risk_score,
		        r.departamento
		 FROM '${PARQUETS.hex_flood_risk}' f
		 JOIN '${PARQUETS.h3_radio_crosswalk}' c ON f.h3index = c.h3index
		 JOIN '${PARQUETS.radio_stats_master}' r ON c.redcode = r.redcode
		 WHERE r.departamento = '${dept}'
		   AND f.flood_risk_score >= ${minScore}
		   AND f.flood_risk_score IS NOT NULL
		 ORDER BY f.flood_risk_score DESC
		 LIMIT ${limit}`
	);

	const mapActions: MapAction[] = [];

	if (rows.length > 0) {
		const h3indices = rows.map(r => String(r.h3index));
		const values = rows.map(r => Number(r.flood_risk_score));
		mapActions.push({ type: 'hex_choropleth', h3indices, values });

		// Fly to department area
		const deptRows = await duckQuery(
			`SELECT redcode FROM '${PARQUETS.radio_stats_master}' WHERE departamento = '${dept}'`
		);
		const deptRedcodes = deptRows.map(r => String(r.redcode));
		const center = getCentroid(deptRedcodes);
		if (center) mapActions.push({ type: 'flyTo', ...center, zoom: 10 });
	}

	// Summary stats
	const summary = {
		departamento: input.departamento,
		hexagons_returned: rows.length,
		avg_risk_score: rows.length > 0 ? rows.reduce((s, r) => s + Number(r.flood_risk_score), 0) / rows.length : 0,
		high_risk_count: rows.filter(r => Number(r.flood_risk_score) >= 70).length,
		medium_risk_count: rows.filter(r => Number(r.flood_risk_score) >= 40 && Number(r.flood_risk_score) < 70).length,
		top_hexagons: rows.slice(0, 5).map(r => ({
			h3index: r.h3index,
			flood_risk_score: Number(r.flood_risk_score).toFixed(1),
			jrc_occurrence: Number(r.jrc_occurrence).toFixed(1) + '%',
			jrc_recurrence: Number(r.jrc_recurrence).toFixed(1) + '%',
			current_extent: Number(r.flood_extent_pct).toFixed(1) + '%',
		}))
	};

	return { data: summary, mapActions };
}

// ── Deduplication ──

function deduplicateMapActions(actions: MapAction[]): MapAction[] {
	const allRedcodes = new Set<string>();
	let lastFlyTo: MapAction | null = null;
	let lastChoropleth: MapAction | null = null;
	let lastHexChoropleth: MapAction | null = null;

	for (const a of actions) {
		if (a.type === 'highlight' && a.redcodes) {
			for (const rc of a.redcodes) allRedcodes.add(rc);
		} else if (a.type === 'flyTo') {
			lastFlyTo = a;
		} else if (a.type === 'choropleth') {
			lastChoropleth = a;
		} else if (a.type === 'hex_choropleth') {
			lastHexChoropleth = a;
		}
	}

	const result: MapAction[] = [];
	if (lastHexChoropleth) {
		result.push(lastHexChoropleth);
	}
	if (lastChoropleth) {
		result.push(lastChoropleth);
	} else if (allRedcodes.size > 0) {
		result.push({ type: 'highlight', redcodes: [...allRedcodes] });
	}
	if (lastFlyTo) result.push(lastFlyTo);
	return result;
}

// ── Main chat engine ──

const MAX_ITERATIONS = 8;

export async function sendChat(
	apiKey: string,
	message: string,
	history: Array<{ role: 'user' | 'assistant'; content: string }>,
	onToolStart?: (toolName: string) => void
): Promise<ChatResponse> {
	// Build messages array
	const messages: any[] = [];
	for (const msg of history) {
		messages.push({ role: msg.role, content: msg.content });
	}
	messages.push({ role: 'user', content: message });

	const allMapActions: MapAction[] = [];
	const allChartData: ChartDataSet[] = [];
	const allToolCalls: Array<{ name: string; elapsed: number }> = [];

	let currentMessages = messages;
	let finalText = '';

	for (let i = 0; i < MAX_ITERATIONS; i++) {
		const res = await fetch('https://api.anthropic.com/v1/messages', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'x-api-key': apiKey,
				'anthropic-version': '2023-06-01',
				'anthropic-dangerous-direct-browser-access': 'true'
			},
			body: JSON.stringify({
				model: 'claude-haiku-4-5-20251001',
				max_tokens: 1024,
				system: SYSTEM_PROMPT,
				tools: TOOL_DEFINITIONS,
				messages: currentMessages
			})
		});

		if (!res.ok) {
			const body = await res.json().catch(() => ({ error: { message: `HTTP ${res.status}` } }));
			const msg = body.error?.message || `Error ${res.status}`;
			throw new Error(msg);
		}

		const response = await res.json();

		const toolUseBlocks: any[] = [];
		const textParts: string[] = [];

		for (const block of response.content) {
			if (block.type === 'text') {
				textParts.push(block.text);
			} else if (block.type === 'tool_use') {
				toolUseBlocks.push(block);
			}
		}

		// No tool calls → done
		if (toolUseBlocks.length === 0) {
			finalText = textParts.join('\n');
			break;
		}

		// Execute tools
		const toolResults: any[] = [];

		for (const toolBlock of toolUseBlocks) {
			onToolStart?.(toolBlock.name);
			const t0 = Date.now();
			try {
				const result = await executeTool(toolBlock.name, toolBlock.input);
				allMapActions.push(...result.mapActions);

				// Chart data from get_stats (1-5 radios → indicator bar chart)
				if (toolBlock.name === 'get_stats' && Array.isArray(result.data) && result.data.length > 0 && result.data.length <= 5) {
					const rateKeys = ['tasa_empleo', 'tasa_actividad', 'tasa_desocupacion', 'pct_nbi', 'pct_agua_red', 'pct_cloacas'];
					const row = result.data[0];
					const rateData = rateKeys
						.filter(k => row[k] != null)
						.map(k => ({ label: k.replace('pct_', '').replace('tasa_', ''), value: Number(row[k]) }));
					if (rateData.length > 0) {
						allChartData.push({ title: 'Indicadores', type: 'bar', data: rateData, unit: '%' });
					}
				}

				// Chart data from ranking/filter
				if ((toolBlock.name === 'ranking' || toolBlock.name === 'filter_radios') && Array.isArray(result.data) && result.data.length > 0) {
					allChartData.push({
						title: toolBlock.input.indicator || toolBlock.name,
						type: 'ranking',
						data: result.data.map((r: any) => ({
							label: `${r.departamento || ''} (${String(r.redcode).slice(-4)})`,
							value: r.value
						}))
					});
				}

				// Chart data from compare_departments
				if (toolBlock.name === 'compare_departments' && Array.isArray(result.data) && result.data.length > 0) {
					allChartData.push({
						title: toolBlock.input.indicator || 'compare_departments',
						type: 'ranking',
						data: result.data.map((r: any) => ({ label: r.departamento, value: r.value }))
					});
				}

				// Flood risk → ranking chart
				if (toolBlock.name === 'get_flood_risk' && result.data?.top_hexagons?.length > 0) {
					allChartData.push({
						title: `Flood risk — ${result.data.departamento}`,
						type: 'ranking',
						data: result.data.top_hexagons.map((h: any) => ({
							label: `${h.h3index.slice(-6)}`,
							value: Number(h.flood_risk_score)
						}))
					});
				}

				// Time series → bar chart
				if (toolBlock.name === 'time_series' && Array.isArray(result.data) && result.data.length > 0) {
					allChartData.push({
						title: 'NDVI',
						type: 'bar',
						data: result.data.map((r: any) => ({ label: String(r.year), value: r.mean_ndvi })),
						unit: 'NDVI'
					});
				}

				toolResults.push({
					type: 'tool_result',
					tool_use_id: toolBlock.id,
					content: JSON.stringify(result.data)
				});

				allToolCalls.push({ name: toolBlock.name, elapsed: Date.now() - t0 });
			} catch (err: any) {
				toolResults.push({
					type: 'tool_result',
					tool_use_id: toolBlock.id,
					content: JSON.stringify({ error: err.message || String(err) }),
					is_error: true
				});
				allToolCalls.push({ name: toolBlock.name, elapsed: Date.now() - t0 });
			}
		}

		// Next iteration
		currentMessages = [
			...currentMessages,
			{ role: 'assistant', content: response.content },
			{ role: 'user', content: toolResults }
		];

		if (response.stop_reason === 'end_turn') {
			finalText = textParts.join('\n');
			break;
		}
	}

	return {
		text: finalText,
		mapActions: deduplicateMapActions(allMapActions),
		chartData: allChartData,
		toolCalls: allToolCalls
	};
}
