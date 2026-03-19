/**
 * Tool definitions and executors for Spatia chat.
 * Each tool queries D1 and returns structured results + optional map actions.
 */

// ── Types ──

export interface MapAction {
	type: 'highlight' | 'flyTo' | 'choropleth';
	redcodes?: string[];
	values?: number[];     // parallel array to redcodes, for choropleth color mapping
	indicator?: string;    // label for the choropleth legend
	lat?: number;
	lng?: number;
	zoom?: number;
}

export interface ToolResult {
	data: any;
	mapActions: MapAction[];
}

// ── Tool Definitions (Claude API format) ──

export const TOOL_DEFINITIONS = [
	{
		name: 'search_indicators',
		description:
			'Search the indicator catalog to find what data is available. Use this when unsure which column names or indicators exist.',
		input_schema: {
			type: 'object' as const,
			properties: {
				query: {
					type: 'string',
					description: 'Search term (e.g. "empleo", "agua", "vegetacion")'
				},
				theme: {
					type: 'string',
					description:
						'Optional theme filter: demografia, economia, vulnerabilidad, servicios, educacion, habitat, ambiente, infraestructura, geografia'
				}
			},
			required: ['query']
		}
	},
	{
		name: 'ranking',
		description:
			'Get a ranking of radios by a specific indicator. Returns top/bottom radios sorted by the given indicator.',
		input_schema: {
			type: 'object' as const,
			properties: {
				indicator: {
					type: 'string',
					description: 'Column name from radio_stats (e.g. "pct_nbi", "densidad_hab_km2", "tasa_empleo")'
				},
				order: {
					type: 'string',
					enum: ['asc', 'desc'],
					description: 'Sort order: "desc" for highest first, "asc" for lowest first'
				},
				limit: {
					type: 'number',
					description: 'Number of results (default 10, max 50)'
				},
				departamento: {
					type: 'string',
					description: 'Optional: filter by departamento name'
				}
			},
			required: ['indicator', 'order']
		}
	},
	{
		name: 'search_places',
		description:
			'Search for barrios (neighborhoods) by name. Returns matching places with their associated radio censal codes.',
		input_schema: {
			type: 'object' as const,
			properties: {
				name: {
					type: 'string',
					description: 'Place name to search (e.g. "villa cabello", "itaembe mini")'
				}
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
				redcodes: {
					type: 'array',
					items: { type: 'string' },
					description: 'Array of radio censal codes'
				},
				departamento: {
					type: 'string',
					description: 'Departamento name (alternative to redcodes)'
				},
				indicators: {
					type: 'array',
					items: { type: 'string' },
					description: 'Specific columns to return (default: all)'
				}
			}
		}
	},
	{
		name: 'filter_radios',
		description:
			'Filter radios by an indicator condition (e.g. NBI > 30%). Returns matching radios with the indicator value.',
		input_schema: {
			type: 'object' as const,
			properties: {
				indicator: {
					type: 'string',
					description: 'Column name from radio_stats'
				},
				operator: {
					type: 'string',
					enum: ['>', '<', '>=', '<=', '='],
					description: 'Comparison operator'
				},
				value: {
					type: 'number',
					description: 'Threshold value'
				},
				departamento: {
					type: 'string',
					description: 'Optional: filter by departamento'
				},
				limit: {
					type: 'number',
					description: 'Max results (default 20, max 100)'
				}
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
				redcode: {
					type: 'string',
					description: 'Specific radio censal code'
				},
				departamento: {
					type: 'string',
					description: 'Departamento name (returns average across all radios)'
				}
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
				indicator: {
					type: 'string',
					description: 'Column name from radio_stats (e.g. "pct_nbi", "tasa_empleo")'
				},
				order: {
					type: 'string',
					enum: ['asc', 'desc'],
					description: 'Sort order: "desc" for highest first, "asc" for lowest first'
				},
				limit: {
					type: 'number',
					description: 'Number of top departamentos to return (default 5, max 17)'
				}
			},
			required: ['indicator', 'order']
		}
	}
];

// ── Allowed columns (whitelist to prevent injection) ──

const ALLOWED_COLUMNS = new Set([
	'redcode',
	'departamento',
	'total_personas',
	'varones',
	'mujeres',
	'area_km2',
	'densidad_hab_km2',
	'pct_nbi',
	'pct_hacinamiento',
	'tasa_empleo',
	'tasa_desocupacion',
	'tasa_actividad',
	'pct_agua_red',
	'pct_cloacas',
	'pct_universitario',
	'pct_secundario_comp',
	'tamano_medio_hogar',
	'n_buildings',
	'ndvi_mean',
	'vulnerability_score',
	'vulnerability_class'
]);

function validateColumn(col: string): string {
	if (!ALLOWED_COLUMNS.has(col)) {
		throw new Error(`Unknown indicator: ${col}`);
	}
	return col;
}

function validateOperator(op: string): string {
	if (!['>', '<', '>=', '<=', '='].includes(op)) {
		throw new Error(`Invalid operator: ${op}`);
	}
	return op;
}

// ── Centroid lookup helper ──

async function getCentroid(
	db: D1Database,
	redcodes: string[]
): Promise<{ lat: number; lng: number } | null> {
	if (redcodes.length === 0) return null;
	const placeholders = redcodes.map(() => '?').join(',');
	const result = await db
		.prepare(`SELECT AVG(lat) as lat, AVG(lng) as lng FROM radio_centroids WHERE redcode IN (${placeholders})`)
		.bind(...redcodes)
		.first<{ lat: number; lng: number }>();
	return result && result.lat != null ? result : null;
}

// ── Tool Executors ──

export async function executeTool(
	db: D1Database,
	toolName: string,
	input: any
): Promise<ToolResult> {
	switch (toolName) {
		case 'search_indicators':
			return executeSearchIndicators(db, input);
		case 'ranking':
			return executeRanking(db, input);
		case 'search_places':
			return executeSearchPlaces(db, input);
		case 'get_stats':
			return executeGetStats(db, input);
		case 'filter_radios':
			return executeFilterRadios(db, input);
		case 'time_series':
			return executeTimeSeries(db, input);
		case 'compare_departments':
			return executeCompareDepartments(db, input);
		default:
			throw new Error(`Unknown tool: ${toolName}`);
	}
}

async function executeSearchIndicators(db: D1Database, input: { query: string; theme?: string }): Promise<ToolResult> {
	const term = `%${input.query}%`;
	let sql = 'SELECT * FROM indicator_catalog WHERE (nombre LIKE ?1 OR descripcion LIKE ?1 OR id LIKE ?1)';
	const binds: any[] = [term];

	if (input.theme) {
		sql += ' AND tema = ?2';
		binds.push(input.theme);
	}

	const { results } = await db.prepare(sql).bind(...binds).all();
	return { data: results, mapActions: [] };
}

async function executeRanking(
	db: D1Database,
	input: { indicator: string; order: string; limit?: number; departamento?: string }
): Promise<ToolResult> {
	const col = validateColumn(input.indicator);
	const dir = input.order === 'asc' ? 'ASC' : 'DESC';
	const limit = Math.min(input.limit || 10, 50);

	let sql = `SELECT redcode, departamento, ${col} AS value FROM radio_stats WHERE ${col} IS NOT NULL`;
	const binds: any[] = [];

	if (input.departamento) {
		sql += ' AND departamento = ?1';
		binds.push(input.departamento);
	}

	sql += ` ORDER BY value ${dir} LIMIT ${limit}`;

	const { results } = await db.prepare(sql).bind(...binds).all();
	const redcodes = (results || []).map((r: any) => r.redcode);
	const values = (results || []).map((r: any) => r.value as number);
	const mapActions: MapAction[] = [];

	if (redcodes.length > 0) {
		if (redcodes.length > 1) {
			// Choropleth for multiple radios — color by value
			mapActions.push({ type: 'choropleth', redcodes, values, indicator: input.indicator });
		} else {
			mapActions.push({ type: 'highlight', redcodes });
		}
		const center = await getCentroid(db, redcodes);
		if (center) {
			mapActions.push({
				type: 'flyTo',
				lat: center.lat,
				lng: center.lng,
				zoom: input.departamento ? 11 : 9
			});
		}
	}

	return { data: results, mapActions };
}

async function executeSearchPlaces(db: D1Database, input: { name: string }): Promise<ToolResult> {
	// Normalize search: lowercase, remove common accents
	const normalized = input.name
		.toLowerCase()
		.normalize('NFD')
		.replace(/[\u0300-\u036f]/g, '');
	const term = `%${normalized}%`;

	const { results } = await db
		.prepare('SELECT nombre, localidad, departamento, tipo, fuente, redcodes FROM barrios_lookup WHERE nombre_lower LIKE ?1')
		.bind(term)
		.all();

	const mapActions: MapAction[] = [];

	if (results && results.length > 0) {
		// Collect all redcodes from all matching places
		const allRedcodes: string[] = [];
		for (const r of results as any[]) {
			try {
				const codes = JSON.parse(r.redcodes);
				allRedcodes.push(...codes);
			} catch { /* skip invalid JSON */ }
		}

		if (allRedcodes.length > 0) {
			mapActions.push({ type: 'highlight', redcodes: allRedcodes });
			const center = await getCentroid(db, allRedcodes);
			if (center) {
				mapActions.push({ type: 'flyTo', lat: center.lat, lng: center.lng, zoom: 14 });
			}
		}
	}

	return { data: results, mapActions };
}

async function executeGetStats(
	db: D1Database,
	input: { redcodes?: string[]; departamento?: string; indicators?: string[] }
): Promise<ToolResult> {
	let cols = '*';
	if (input.indicators && input.indicators.length > 0) {
		const validated = input.indicators.map(validateColumn);
		cols = ['redcode', 'departamento', ...validated].join(', ');
	}

	let sql: string;
	let binds: any[] = [];

	if (input.redcodes && input.redcodes.length > 0) {
		const placeholders = input.redcodes.map((_, i) => `?${i + 1}`).join(',');
		sql = `SELECT ${cols} FROM radio_stats WHERE redcode IN (${placeholders})`;
		binds = input.redcodes;
	} else if (input.departamento) {
		sql = `SELECT ${cols} FROM radio_stats WHERE departamento = ?1`;
		binds = [input.departamento];
	} else {
		return { data: [], mapActions: [] };
	}

	const { results } = await db.prepare(sql).bind(...binds).all();
	const redcodes = (results || []).map((r: any) => r.redcode);
	const mapActions: MapAction[] = [];

	if (redcodes.length > 0) {
		mapActions.push({ type: 'highlight', redcodes });
		const center = await getCentroid(db, redcodes);
		if (center) {
			mapActions.push({ type: 'flyTo', lat: center.lat, lng: center.lng, zoom: 13 });
		}
	}

	return { data: results, mapActions };
}

async function executeFilterRadios(
	db: D1Database,
	input: { indicator: string; operator: string; value: number; departamento?: string; limit?: number }
): Promise<ToolResult> {
	const col = validateColumn(input.indicator);
	const op = validateOperator(input.operator);
	const limit = Math.min(input.limit || 20, 100);

	let sql = `SELECT redcode, departamento, ${col} AS value FROM radio_stats WHERE ${col} ${op} ?1`;
	const binds: any[] = [input.value];

	if (input.departamento) {
		sql += ' AND departamento = ?2';
		binds.push(input.departamento);
	}

	sql += ` ORDER BY value ${op.includes('>') ? 'DESC' : 'ASC'} LIMIT ${limit}`;

	const { results } = await db.prepare(sql).bind(...binds).all();
	const redcodes = (results || []).map((r: any) => r.redcode);
	const mapActions: MapAction[] = [];

	if (redcodes.length > 0) {
		mapActions.push({ type: 'highlight', redcodes });
		const center = await getCentroid(db, redcodes);
		if (center) {
			mapActions.push({ type: 'flyTo', lat: center.lat, lng: center.lng, zoom: 10 });
		}
	}

	return { data: results, mapActions };
}

async function executeTimeSeries(
	db: D1Database,
	input: { redcode?: string; departamento?: string }
): Promise<ToolResult> {
	let sql: string;
	let binds: any[] = [];
	const mapActions: MapAction[] = [];

	if (input.redcode) {
		sql = 'SELECT year, mean_ndvi FROM ndvi_annual WHERE redcode = ?1 ORDER BY year';
		binds = [input.redcode];
		const center = await getCentroid(db, [input.redcode]);
		if (center) {
			mapActions.push({ type: 'highlight', redcodes: [input.redcode] });
			mapActions.push({ type: 'flyTo', lat: center.lat, lng: center.lng, zoom: 14 });
		}
	} else if (input.departamento) {
		sql = `SELECT n.year, AVG(n.mean_ndvi) as mean_ndvi
			FROM ndvi_annual n
			JOIN radio_stats r ON n.redcode = r.redcode
			WHERE r.departamento = ?1
			GROUP BY n.year
			ORDER BY n.year`;
		binds = [input.departamento];
		// Highlight all radios of the departamento and fly to it
		const deptRadios = await db
			.prepare('SELECT redcode FROM radio_stats WHERE departamento = ?1')
			.bind(input.departamento)
			.all();
		const deptRedcodes = (deptRadios.results || []).map((r: any) => r.redcode);
		if (deptRedcodes.length > 0) {
			mapActions.push({ type: 'highlight', redcodes: deptRedcodes });
			const center = await getCentroid(db, deptRedcodes);
			if (center) {
				mapActions.push({ type: 'flyTo', lat: center.lat, lng: center.lng, zoom: 10 });
			}
		}
	} else {
		sql = 'SELECT year, AVG(mean_ndvi) as mean_ndvi FROM ndvi_annual GROUP BY year ORDER BY year';
	}

	const { results } = await db.prepare(sql).bind(...binds).all();
	return { data: results, mapActions };
}

async function executeCompareDepartments(
	db: D1Database,
	input: { indicator: string; order: string; limit?: number }
): Promise<ToolResult> {
	const col = validateColumn(input.indicator);
	const dir = input.order === 'asc' ? 'ASC' : 'DESC';
	const limit = Math.min(input.limit || 5, 17);

	// Aggregate by departamento
	const { results } = await db
		.prepare(
			`SELECT departamento, AVG(${col}) AS value, COUNT(*) AS n_radios
			 FROM radio_stats WHERE ${col} IS NOT NULL
			 GROUP BY departamento ORDER BY value ${dir} LIMIT ${limit}`
		)
		.all();

	const mapActions: MapAction[] = [];

	if (results && results.length > 0) {
		// Get all redcodes + values for a choropleth across ALL ranked departamentos
		const deptNames = results.map((r: any) => r.departamento as string);
		const deptPlaceholders = deptNames.map((_, i) => `?${i + 1}`).join(',');

		const radiosResult = await db
			.prepare(
				`SELECT redcode, departamento, ${col} AS value FROM radio_stats
				 WHERE departamento IN (${deptPlaceholders}) AND ${col} IS NOT NULL`
			)
			.bind(...deptNames)
			.all();

		const radioRows = radiosResult.results || [];
		const redcodes = radioRows.map((r: any) => r.redcode as string);
		const values = radioRows.map((r: any) => r.value as number);

		if (redcodes.length > 0) {
			mapActions.push({ type: 'choropleth', redcodes, values, indicator: input.indicator });

			// Fly to the top departamento
			const topDeptRedcodes = radioRows
				.filter((r: any) => r.departamento === deptNames[0])
				.map((r: any) => r.redcode as string);
			const center = await getCentroid(db, topDeptRedcodes.length > 0 ? topDeptRedcodes : redcodes);
			if (center) {
				mapActions.push({ type: 'flyTo', lat: center.lat, lng: center.lng, zoom: 9 });
			}
		}
	}

	return { data: results, mapActions };
}
