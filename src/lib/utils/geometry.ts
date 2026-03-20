/**
 * Point-in-polygon test (ray casting algorithm).
 * Point and polygon vertices are [lng, lat] pairs.
 */
export function pointInPolygon(point: [number, number], polygon: [number, number][]): boolean {
	let inside = false;
	for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
		const [xi, yi] = polygon[i], [xj, yj] = polygon[j];
		if ((yi > point[1]) !== (yj > point[1]) &&
			point[0] < (xj - xi) * (point[1] - yi) / (yj - yi) + xi)
			inside = !inside;
	}
	return inside;
}
