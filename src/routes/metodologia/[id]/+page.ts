import { error } from '@sveltejs/kit';
import { getMethodologyContent, listMethodologyIds } from '$lib/content/methodology';
import { HEX_LAYER_REGISTRY, getAnalysisById } from '$lib/config';

export const ssr = false;
export const prerender = true;

export function entries() {
	return listMethodologyIds().map((id) => ({ id }));
}

export function load({ params }: { params: { id: string } }) {
	const content = getMethodologyContent(params.id);
	if (!content) throw error(404, `Metodología no encontrada: ${params.id}`);

	const layerCfg = HEX_LAYER_REGISTRY[params.id];
	const analysis = getAnalysisById(params.id);

	return {
		id: params.id,
		content,
		titleKey: layerCfg?.titleKey ?? analysis?.titleKey ?? params.id,
		descKey: analysis?.descKey,
		variables: layerCfg?.variables ?? [],
		colorScale: layerCfg?.colorScale,
	};
}
