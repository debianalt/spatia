import { query, isReady } from '$lib/stores/duckdb';
import { PARQUETS } from '$lib/config';

export const PETAL_VARS = [
	{ col: 'tasa_actividad', labelKey: 'label.activityRate' },
	{ col: 'tasa_empleo', labelKey: 'label.employmentRate' },
	{ col: 'pct_universitario', labelKey: 'label.university' },
	{ col: 'pct_nbi', labelKey: 'label.ubn' },
	{ col: 'pct_hacinamiento', labelKey: 'label.overcrowding' },
	{ col: 'pct_agua_red', labelKey: 'label.waterNetwork' },
];

/** (value / provincialAvg) * 50, clamped [0, 100]. 50 = provincial average. */
export function normalizeValues(rawValues: number[], provAvg: number[]): number[] {
	return rawValues.map((v, i) => {
		const avg = provAvg[i];
		if (avg === 0) return 50;
		return Math.min(100, Math.max(0, (v / avg) * 50));
	});
}

let _cachedProvAvg: number[] | null = null;

/** Weighted provincial averages for PETAL_VARS (cached after first call). */
export async function getProvincialAvg(): Promise<number[]> {
	if (_cachedProvAvg) return _cachedProvAvg;
	if (!isReady()) throw new Error('DuckDB not ready');

	const cols = PETAL_VARS.map(v =>
		`SUM(${v.col} * total_personas) / NULLIF(SUM(total_personas), 0) as avg_${v.col}`
	).join(', ');

	const sql = `SELECT ${cols} FROM '${PARQUETS.radio_stats_master}' WHERE total_personas > 0`;
	const result = await query(sql);
	const row = result.get(0)!.toJSON() as Record<string, any>;

	_cachedProvAvg = PETAL_VARS.map(v => Number(row[`avg_${v.col}`]) || 1);
	return _cachedProvAvg;
}

type RadioVars = typeof PETAL_VARS;
type RadioPop = { data: Map<string, Record<string, any>>; vars: RadioVars };

// Per-territory census source. Corrientes lacks pct_agua_red; rest identical.
const CENSUS_SRC: Record<string, { parquet: string; vars: RadioVars }> = {
	misiones:   { parquet: PARQUETS.radio_stats_master,     vars: PETAL_VARS },
	corrientes: { parquet: PARQUETS.radio_stats_corrientes, vars: PETAL_VARS.filter(v => v.col !== 'pct_agua_red') },
};

const _radioPopCache = new Map<string, RadioPop>();

/**
 * Full radio-level census population for a territory, keyed by redcode, plus
 * the variable set actually available there (6 for Misiones, 5 for Corrientes).
 * Cached module-level per territory (mirrors getProvincialAvg). Read-only:
 * the returned Map is never mutated by callers.
 */
export async function loadRadioPopulation(territory: string): Promise<RadioPop> {
	const cached = _radioPopCache.get(territory);
	if (cached) return cached;

	const src = CENSUS_SRC[territory];
	if (!src) throw new Error(`No census source for territory: ${territory}`);
	if (!isReady()) throw new Error('DuckDB not ready');

	const cols = src.vars.map(v => v.col).join(', ');
	const sql = `SELECT redcode, ${cols} FROM '${src.parquet}' WHERE total_personas > 0`;
	const result = await query(sql);

	const m = new Map<string, Record<string, any>>();
	for (let i = 0; i < result.numRows; i++) {
		const row = result.get(i)!.toJSON() as Record<string, any>;
		for (const v of src.vars) row[v.col] = Number(row[v.col]);
		m.set(String(row.redcode), row);
	}

	const out: RadioPop = { data: m, vars: src.vars };
	_radioPopCache.set(territory, out);
	return out;
}
