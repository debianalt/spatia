import boundary from '$lib/data/misiones_boundary.json';

// Extract outer rings from MultiPolygon (GeoJSON coords are [lng, lat])
const rings: number[][][] = (boundary as any).features[0].geometry.coordinates
	.map((poly: number[][][]) => poly[0]);

function pointInRing(lat: number, lng: number, ring: number[][]): boolean {
	let inside = false;
	for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
		const lngi = ring[i][0], lati = ring[i][1];
		const lngj = ring[j][0], latj = ring[j][1];
		if ((lati > lat) !== (latj > lat) &&
			lng < (lngj - lngi) * (lat - lati) / (latj - lati) + lngi) {
			inside = !inside;
		}
	}
	return inside;
}

export function isInsideMisiones(lat: number, lng: number): boolean {
	return rings.some(ring => pointInRing(lat, lng, ring));
}
