// Shared dept summary loaders — used by OvertureAnalysis and ComparisonPanel.
// Each loader returns the bundled JSON for a given analysis × territory.

const SAT_SUMMARIES: Record<string, () => Promise<any>> = {
	environmental_risk:   () => import('$lib/data/sat_environmental_risk_dept_summary.json'),
	climate_comfort:      () => import('$lib/data/sat_climate_comfort_dept_summary.json'),
	green_capital:        () => import('$lib/data/sat_green_capital_dept_summary.json'),
	change_pressure:      () => import('$lib/data/sat_change_pressure_dept_summary.json'),
	location_value:       () => import('$lib/data/sat_location_value_dept_summary.json'),
	agri_potential:       () => import('$lib/data/sat_agri_potential_dept_summary.json'),
	forest_health:        () => import('$lib/data/sat_forest_health_dept_summary.json'),
	forestry_aptitude:    () => import('$lib/data/sat_forestry_aptitude_dept_summary.json'),
	service_deprivation:  () => import('$lib/data/sat_service_deprivation_dept_summary.json'),
	territorial_isolation: () => import('$lib/data/sat_territorial_isolation_dept_summary.json'),
	health_access:        () => import('$lib/data/sat_health_access_dept_summary.json'),
	education_capital:    () => import('$lib/data/sat_education_capital_dept_summary.json'),
	education_flow:       () => import('$lib/data/sat_education_flow_dept_summary.json'),
	land_use:             () => import('$lib/data/sat_land_use_dept_summary.json'),
	territorial_types:    () => import('$lib/data/sat_territorial_types_dept_summary.json'),
	flood_risk:           () => import('$lib/data/flood_dept_summary.json'),
	territorial_scores:   () => import('$lib/data/scores_dept_summary.json'),
	sociodemographic:     () => import('$lib/data/sat_sociodemographic_dept_summary.json'),
	economic_activity:    () => import('$lib/data/sat_economic_activity_dept_summary.json'),
	accessibility:        () => import('$lib/data/sat_accessibility_dept_summary.json'),
	climate_vulnerability: () => import('$lib/data/sat_climate_vulnerability_dept_summary.json'),
	carbon_stock:         () => import('$lib/data/sat_carbon_stock_dept_summary.json'),
	pm25_drivers:         () => import('$lib/data/sat_pm25_drivers_dept_summary.json'),
	productive_activity:  () => import('$lib/data/sat_productive_activity_dept_summary.json'),
	deforestation_dynamics: () => import('$lib/data/sat_deforestation_dynamics_dept_summary.json'),
	soil_water:             () => import('$lib/data/sat_soil_water_dept_summary.json'),
};

const ITAPUA_SUMMARIES: Record<string, () => Promise<any>> = {
	environmental_risk:     () => import('$lib/data/itapua_py_sat_environmental_risk_summary.json'),
	climate_comfort:        () => import('$lib/data/itapua_py_sat_climate_comfort_summary.json'),
	green_capital:          () => import('$lib/data/itapua_py_sat_green_capital_summary.json'),
	change_pressure:        () => import('$lib/data/itapua_py_sat_change_pressure_summary.json'),
	forest_health:          () => import('$lib/data/itapua_py_sat_forest_health_summary.json'),
	deforestation_dynamics: () => import('$lib/data/itapua_py_sat_deforestation_dynamics_summary.json'),
	agri_potential:         () => import('$lib/data/itapua_py_sat_agri_potential_summary.json'),
	carbon_stock:           () => import('$lib/data/itapua_py_sat_carbon_stock_summary.json'),
	climate_vulnerability:  () => import('$lib/data/itapua_py_sat_climate_vulnerability_summary.json'),
	pm25_drivers:           () => import('$lib/data/itapua_py_sat_pm25_drivers_summary.json'),
	productive_activity:    () => import('$lib/data/itapua_py_sat_productive_activity_summary.json'),
	forestry_aptitude:      () => import('$lib/data/itapua_py_sat_forestry_aptitude_summary.json'),
	land_use:               () => import('$lib/data/itapua_py_sat_land_use_summary.json'),
	accessibility:          () => import('$lib/data/itapua_py_sat_accessibility_summary.json'),
	flood_risk:             () => import('$lib/data/itapua_py_flood_dept_summary.json'),
	territorial_scores:     () => import('$lib/data/itapua_py_scores_dept_summary.json'),
	soil_water:             () => import('$lib/data/itapua_py_sat_soil_water_summary.json'),
};

const CORRIENTES_SUMMARIES: Record<string, () => Promise<any>> = {
	environmental_risk:     () => import('$lib/data/corrientes_sat_environmental_risk_summary.json'),
	climate_comfort:        () => import('$lib/data/corrientes_sat_climate_comfort_summary.json'),
	green_capital:          () => import('$lib/data/corrientes_sat_green_capital_summary.json'),
	change_pressure:        () => import('$lib/data/corrientes_sat_change_pressure_summary.json'),
	agri_potential:         () => import('$lib/data/corrientes_sat_agri_potential_summary.json'),
	forest_health:          () => import('$lib/data/corrientes_sat_forest_health_summary.json'),
	accessibility:          () => import('$lib/data/corrientes_sat_accessibility_summary.json'),
	carbon_stock:           () => import('$lib/data/corrientes_sat_carbon_stock_summary.json'),
	climate_vulnerability:  () => import('$lib/data/corrientes_sat_climate_vulnerability_summary.json'),
	pm25_drivers:           () => import('$lib/data/corrientes_sat_pm25_drivers_summary.json'),
	land_use:               () => import('$lib/data/corrientes_sat_land_use_summary.json'),
	soil_water:             () => import('$lib/data/corrientes_sat_soil_water_summary.json'),
	sociodemographic:       () => import('$lib/data/corrientes_sat_sociodemographic_summary.json'),
	economic_activity:      () => import('$lib/data/corrientes_sat_economic_activity_summary.json'),
	flood_risk:             () => import('$lib/data/corrientes_flood_dept_summary.json'),
	territorial_scores:     () => import('$lib/data/corrientes_scores_dept_summary.json'),
	service_deprivation:    () => import('$lib/data/corrientes_sat_service_deprivation_summary.json'),
	territorial_isolation:  () => import('$lib/data/corrientes_sat_territorial_isolation_summary.json'),
	health_access:          () => import('$lib/data/corrientes_sat_health_access_summary.json'),
	education_capital:      () => import('$lib/data/corrientes_sat_education_capital_summary.json'),
	education_flow:         () => import('$lib/data/corrientes_sat_education_flow_summary.json'),
};

const TERRITORY_SUMMARIES: Record<string, Record<string, () => Promise<any>>> = {
	'itapua_py/': ITAPUA_SUMMARIES,
	'corrientes/': CORRIENTES_SUMMARIES,
};

export async function loadDeptSummary(analysisId: string, territoryPrefix: string): Promise<any> {
	const summaries = territoryPrefix ? (TERRITORY_SUMMARIES[territoryPrefix] ?? null) : SAT_SUMMARIES;
	if (!summaries) return null;
	const loader = summaries[analysisId];
	if (!loader) return null;
	try {
		const mod = await loader();
		return mod.default ?? mod;
	} catch {
		return null;
	}
}

export interface DeptItem {
	name: string;
	parquetKey: string;
}

export async function loadDeptList(analysisId: string, territoryPrefix: string): Promise<DeptItem[]> {
	const summary = await loadDeptSummary(analysisId, territoryPrefix);
	if (!summary?.departments) return [];
	return (summary.departments as any[])
		.map(d => ({ name: (d.dpto ?? d.distrito ?? '') as string, parquetKey: d.parquetKey as string }))
		.filter(d => d.name && d.parquetKey)
		.sort((a, b) => a.name.localeCompare(b.name));
}
