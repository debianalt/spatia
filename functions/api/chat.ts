import Anthropic from '@anthropic-ai/sdk';

interface Env {}

export const onRequestPost: PagesFunction<Env> = async (context) => {
	const apiKey = context.request.headers.get('x-api-key');
	if (!apiKey) {
		return new Response(JSON.stringify({ error: 'Missing API key' }), {
			status: 401,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	try {
		const body = await context.request.json<{
			model?: string;
			max_tokens?: number;
			messages: { role: string; content: string }[];
		}>();

		const client = new Anthropic({ apiKey });

		const message = await client.messages.create({
			model: body.model || 'claude-haiku-4-5-20251001',
			max_tokens: body.max_tokens || 512,
			messages: body.messages
		});

		return new Response(JSON.stringify(message), {
			headers: { 'Content-Type': 'application/json' }
		});
	} catch (e: any) {
		const status = e.status || 500;
		const msg = e.message || String(e);
		return new Response(JSON.stringify({ error: msg }), {
			status,
			headers: { 'Content-Type': 'application/json' }
		});
	}
};
