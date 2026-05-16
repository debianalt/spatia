import boundaries from '$lib/data/ar_dept_boundaries.json';

const features = (boundaries as any).features as any[];

export function findDeptFeature(deptName: string, territoryPrefix: string): any | null {
	if (!deptName) return null;
	const provincePrefix = territoryPrefix === 'corrientes/' ? '18'
		: territoryPrefix === '' ? '54'
		: null;
	if (!provincePrefix) return null;
	return features.find(f =>
		f.properties.nombre === deptName &&
		String(f.properties.redcode).startsWith(provincePrefix)
	) || null;
}
