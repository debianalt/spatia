export const ssr = false;
export const prerender = true;

import { listMethodologyIds } from '$lib/content/methodology';
import { ANALYSIS_REGISTRY, LENS_CONFIG } from '$lib/config';
import type { LensId } from '$lib/config';

export function load() {
	const ids = new Set(listMethodologyIds());

	const byLens = (Object.keys(LENS_CONFIG) as LensId[]).map((lensId) => ({
		lensId,
		color: LENS_CONFIG[lensId].color,
		label: LENS_CONFIG[lensId].label.es,
		analyses: ANALYSIS_REGISTRY.filter(
			(a) => a.lensId === lensId && ids.has(a.id) && a.status === 'available'
		).map((a) => ({ id: a.id, titleKey: a.titleKey, descKey: a.descKey }))
	})).filter((g) => g.analyses.length > 0);

	return { byLens };
}
