export function isInsideCorrientes(lat: number, lng: number): boolean {
	return lat >= -30.80 && lat <= -27.20 && lng >= -59.80 && lng <= -55.50;
}
