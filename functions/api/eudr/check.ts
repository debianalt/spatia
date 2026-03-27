/**
 * EUDR Deforestation Check API
 *
 * POST /api/eudr/check
 *
 * Accepts coordinates and returns deforestation risk assessment
 * based on Hansen Global Forest Change + MODIS fire data.
 *
 * Regulation: EU 2023/1115 (EUDR)
 * Cutoff date: 31 December 2020
 */

import { latLngToCell } from 'h3-js';

interface Env {
	DB: D1Database;
}

interface CoordinateInput {
	lat: number;
	lon: number;
	id?: string;
}

interface CheckRequest {
	coordinates: CoordinateInput[];
	commodity?: 'soya' | 'cattle' | 'wood';
}

interface DeforestationResult {
	id: string;
	lat: number;
	lon: number;
	h3_cell: string;
	h3_resolution: number;
	province: string;
	forest_cover_2020_pct: number | null;
	forest_cover_current_pct: number | null;
	loss_total_pct: number | null;
	loss_post_2020_pct: number | null;
	loss_pre_2020_pct: number | null;
	fire_post_2020_pct: number | null;
	risk_score: number | null;
	risk_level: string;
	deforestation_post_2020: boolean;
	eudr_assessment: string;
	data_sources: string[];
	data_vintage: string;
}

interface CheckResponse {
	results: DeforestationResult[];
	meta: {
		processing_time_ms: number;
		coordinate_count: number;
		h3_resolution: number;
		spatial_precision_km: number;
		disclaimer: string;
		daily_limit: number;
		remaining_checks: number;
	};
}

const H3_RESOLUTION = 7;
const SPATIAL_PRECISION_KM = 2.27; // res-7 edge length
const MAX_COORDINATES = 100; // rate limit per request
const DATA_VINTAGE = '2024-12-31';
const DATA_SOURCES = [
	'Hansen/UMD Global Forest Change v1.12 (30m, Landsat)',
	'MODIS MCD64A1 Burned Area (500m)',
];

const DISCLAIMER =
	'This assessment is based on satellite-derived data and is indicative only. ' +
	'It does not constitute legal compliance certification under EU Regulation 2023/1115. ' +
	'Operators must perform their own due diligence as required by Articles 8-11 of the Regulation.';

// IP-based rate limiting (in-memory, resets on worker restart)
const rateLimits = new Map<string, { count: number; resetAt: number }>();
const RATE_LIMIT_PER_DAY = 100;

function checkRateLimit(ip: string): boolean {
	const now = Date.now();
	const entry = rateLimits.get(ip);

	if (!entry || now > entry.resetAt) {
		rateLimits.set(ip, { count: 1, resetAt: now + 86400000 });
		return true;
	}

	if (entry.count >= RATE_LIMIT_PER_DAY) {
		return false;
	}

	entry.count++;
	return true;
}

function getRiskLevel(score: number | null): string {
	if (score === null) return 'unknown';
	if (score >= 75) return 'critical';
	if (score >= 50) return 'high';
	if (score >= 25) return 'medium';
	return 'low';
}

function getEudrAssessment(deforested: boolean, riskScore: number | null): string {
	if (deforested) return 'NON_COMPLIANT';
	if (riskScore !== null && riskScore >= 50) return 'HIGH_RISK';
	if (riskScore !== null && riskScore >= 25) return 'MEDIUM_RISK';
	return 'LOW_RISK';
}

function corsHeaders(): Record<string, string> {
	return {
		'Access-Control-Allow-Origin': '*',
		'Access-Control-Allow-Methods': 'POST, OPTIONS',
		'Access-Control-Allow-Headers': 'Content-Type, x-api-key',
		'Content-Type': 'application/json',
	};
}

export const onRequestOptions: PagesFunction = async () => {
	return new Response(null, { status: 204, headers: corsHeaders() });
};

export const onRequestPost: PagesFunction<Env> = async (context) => {
	const startTime = Date.now();
	const headers = corsHeaders();

	// Rate limiting
	const ip = context.request.headers.get('cf-connecting-ip') || 'unknown';
	if (!checkRateLimit(ip)) {
		return new Response(
			JSON.stringify({
				error: 'Rate limit exceeded. Maximum 100 requests per day.',
				retry_after_seconds: 86400,
			}),
			{ status: 429, headers: { ...headers, 'Retry-After': '86400' } }
		);
	}

	// Parse request
	const db = context.env.DB;
	if (!db) {
		return new Response(
			JSON.stringify({ error: 'Database not available' }),
			{ status: 500, headers }
		);
	}

	let body: CheckRequest;
	try {
		body = await context.request.json();
	} catch {
		return new Response(
			JSON.stringify({ error: 'Invalid JSON body' }),
			{ status: 400, headers }
		);
	}

	if (!body.coordinates || !Array.isArray(body.coordinates) || body.coordinates.length === 0) {
		return new Response(
			JSON.stringify({ error: 'Missing or empty coordinates array' }),
			{ status: 400, headers }
		);
	}

	if (body.coordinates.length > MAX_COORDINATES) {
		return new Response(
			JSON.stringify({ error: `Maximum ${MAX_COORDINATES} coordinates per request` }),
			{ status: 400, headers }
		);
	}

	// Process each coordinate
	const results: DeforestationResult[] = [];

	for (let i = 0; i < body.coordinates.length; i++) {
		const coord = body.coordinates[i];

		if (typeof coord.lat !== 'number' || typeof coord.lon !== 'number') {
			return new Response(
				JSON.stringify({ error: `Invalid coordinate at index ${i}: lat and lon must be numbers` }),
				{ status: 400, headers }
			);
		}

		// Convert to H3 cell
		const h3Cell = latLngToCell(coord.lat, coord.lon, H3_RESOLUTION);

		// Query D1
		const row = await db
			.prepare('SELECT * FROM eudr_deforestation WHERE h3index = ?')
			.bind(h3Cell)
			.first();

		if (row) {
			const deforested = Boolean(row.deforestation_post_2020);
			const riskScore = row.risk_score as number | null;

			results.push({
				id: coord.id || `point_${i}`,
				lat: coord.lat,
				lon: coord.lon,
				h3_cell: h3Cell,
				h3_resolution: H3_RESOLUTION,
				province: row.province as string,
				forest_cover_2020_pct: row.forest_cover_2020 as number | null,
				forest_cover_current_pct: row.forest_cover_current as number | null,
				loss_total_pct: row.loss_total_pct as number | null,
				loss_post_2020_pct: row.loss_post_2020_pct as number | null,
				loss_pre_2020_pct: row.loss_pre_2020_pct as number | null,
				fire_post_2020_pct: row.fire_post_2020_pct as number | null,
				risk_score: riskScore,
				risk_level: getRiskLevel(riskScore),
				deforestation_post_2020: deforested,
				eudr_assessment: getEudrAssessment(deforested, riskScore),
				data_sources: DATA_SOURCES,
				data_vintage: DATA_VINTAGE,
			});
		} else {
			// Coordinate outside EUDR coverage area
			results.push({
				id: coord.id || `point_${i}`,
				lat: coord.lat,
				lon: coord.lon,
				h3_cell: h3Cell,
				h3_resolution: H3_RESOLUTION,
				province: '',
				forest_cover_2020_pct: null,
				forest_cover_current_pct: null,
				loss_total_pct: null,
				loss_post_2020_pct: null,
				loss_pre_2020_pct: null,
				fire_post_2020_pct: null,
				risk_score: null,
				risk_level: 'outside_coverage',
				deforestation_post_2020: false,
				eudr_assessment: 'OUTSIDE_COVERAGE',
				data_sources: DATA_SOURCES,
				data_vintage: DATA_VINTAGE,
			});
		}
	}

	const ipEntry = rateLimits.get(ip);
	const remaining = ipEntry ? Math.max(0, RATE_LIMIT_PER_DAY - ipEntry.count) : RATE_LIMIT_PER_DAY;

	const response: CheckResponse = {
		results,
		meta: {
			processing_time_ms: Date.now() - startTime,
			coordinate_count: body.coordinates.length,
			h3_resolution: H3_RESOLUTION,
			spatial_precision_km: SPATIAL_PRECISION_KM,
			disclaimer: DISCLAIMER,
			daily_limit: RATE_LIMIT_PER_DAY,
			remaining_checks: remaining,
		},
	};

	return new Response(JSON.stringify(response), { status: 200, headers });
};
