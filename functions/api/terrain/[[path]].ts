export const onRequestGet: PagesFunction = async ({ params }) => {
	const path = Array.isArray(params.path) ? params.path.join('/') : params.path;
	const tileUrl = `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${path}`;

	const tileResponse = await fetch(tileUrl, {
		cf: { cacheTtl: 86400, cacheEverything: true }
	});

	if (!tileResponse.ok) {
		return new Response('Tile not found', { status: tileResponse.status });
	}

	return new Response(tileResponse.body, {
		headers: {
			'Content-Type': 'image/png',
			'Access-Control-Allow-Origin': '*',
			'Cache-Control': 'public, max-age=86400, s-maxage=604800'
		}
	});
};
