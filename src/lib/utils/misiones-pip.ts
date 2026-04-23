import { pointInPolygon } from '$lib/utils/geometry';
import boundary from '$lib/data/misiones_boundary.json';

// Outer rings of the Misiones MultiPolygon — coords are [lng, lat] (GeoJSON)
const rings: [number, number][][] = (boundary as any).features[0].geometry.coordinates
	.map((poly: number[][][]) => poly[0] as [number, number][]);

export function isInsideMisiones(lat: number, lng: number): boolean {
	return rings.some(ring => pointInPolygon([lng, lat], ring));
}
