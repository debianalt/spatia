import { pointInPolygon } from '$lib/utils/geometry';
import boundary from '$lib/data/corrientes_boundary.json';

const outerRing: [number, number][] = (boundary as any).geometry.coordinates[0];
const holeRings: [number, number][][] = (boundary as any).geometry.coordinates.slice(1);

export function isInsideCorrientes(lat: number, lng: number): boolean {
	if (!pointInPolygon([lng, lat], outerRing)) return false;
	return !holeRings.some(ring => pointInPolygon([lng, lat], ring));
}
