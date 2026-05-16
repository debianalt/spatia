import { pointInPolygon } from '$lib/utils/geometry';
import boundary from '$lib/data/alto_parana_boundary.json';

const ring: [number, number][] = (boundary as any).geometry.coordinates[0] as [number, number][];

export function isInsideAltoParana(lat: number, lng: number): boolean {
	return pointInPolygon([lng, lat], ring);
}
