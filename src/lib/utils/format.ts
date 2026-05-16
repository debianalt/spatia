/**
 * Display-only Title Case for district/department names.
 *
 * Itapúa (GAUL) names are already Title Case ("Cambyreta", "Bella Vista");
 * Alto Paraná (INE 2022 cartography) names are UPPER ("HERNANDARIAS",
 * "JUAN E. O'LEARY"). This normalizes the *display* so both territories
 * look consistent. The underlying values (join keys in crosswalk / censo /
 * nbi / district_stats / PMTiles) stay verbatim — NEVER format those.
 *
 * Idempotent on already-Title-Case input. Unicode-safe (preserves
 * accents/ñ via locale-less toLowerCase/toUpperCase). Capitalizes after
 * an apostrophe ("O'LEARY" -> "O'Leary").
 */
export function formatDept(name: string | null | undefined): string {
	if (!name) return '';
	return String(name)
		.toLowerCase()
		.replace(/(^|[\s'.-])(\p{L})/gu, (_m, sep, ch) => sep + ch.toUpperCase());
}
