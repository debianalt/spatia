import Anthropic from '@anthropic-ai/sdk';
import { SYSTEM_PROMPT } from '../lib/system-prompt';
import { TOOL_DEFINITIONS, executeTool, type MapAction } from '../lib/tools';

interface Env {
	DB: D1Database;
}

interface ChatRequest {
	message: string;
	history?: Array<{ role: 'user' | 'assistant'; content: string }>;
}

interface ChartDataSet {
	title: string;
	type: 'bar' | 'ranking';
	data: Array<{ label: string; value: number }>;
	unit?: string;
}

interface ChatResponse {
	text: string;
	mapActions: MapAction[];
	chartData: ChartDataSet[];
	toolCalls: Array<{ name: string; elapsed: number }>;
}

const MAX_ITERATIONS = 8;

export const onRequestPost: PagesFunction<Env> = async (context) => {
	const apiKey = context.request.headers.get('x-api-key');
	if (!apiKey) {
		return new Response(JSON.stringify({ error: 'Missing API key' }), {
			status: 401,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	const db = context.env.DB;
	if (!db) {
		return new Response(JSON.stringify({ error: 'Database not configured. Check D1 binding in wrangler.toml.' }), {
			status: 500,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	try {
		const body = await context.request.json<ChatRequest>();
		const client = new Anthropic({ apiKey });

		// Build message history
		const messages: Anthropic.MessageParam[] = [];
		if (body.history) {
			for (const msg of body.history) {
				messages.push({ role: msg.role, content: msg.content });
			}
		}
		messages.push({ role: 'user', content: body.message });

		// Accumulate results across iterations
		const allMapActions: MapAction[] = [];
		const allChartData: ChartDataSet[] = [];
		const allToolCalls: Array<{ name: string; elapsed: number }> = [];

		// Tool use loop
		let currentMessages = messages;
		let finalText = '';

		for (let i = 0; i < MAX_ITERATIONS; i++) {
			const response = await client.messages.create({
				model: 'claude-haiku-4-5-20251001',
				max_tokens: 1024,
				system: SYSTEM_PROMPT,
				tools: TOOL_DEFINITIONS as any,
				messages: currentMessages
			});

			// Process response content blocks
			const toolUseBlocks: Anthropic.ToolUseBlock[] = [];
			const textParts: string[] = [];

			for (const block of response.content) {
				if (block.type === 'text') {
					textParts.push(block.text);
				} else if (block.type === 'tool_use') {
					toolUseBlocks.push(block);
				}
			}

			// If no tool calls, we're done
			if (toolUseBlocks.length === 0) {
				finalText = textParts.join('\n');
				break;
			}

			// Execute each tool call
			const toolResults: Anthropic.ToolResultBlockParam[] = [];

			for (const toolBlock of toolUseBlocks) {
				const t0 = Date.now();
				try {
					const result = await executeTool(db, toolBlock.name, toolBlock.input);

					// Accumulate map actions
					allMapActions.push(...result.mapActions);

					// Generate chart data from ranking/filter results
					if (
						(toolBlock.name === 'ranking' || toolBlock.name === 'filter_radios') &&
						Array.isArray(result.data) &&
						result.data.length > 0
					) {
						const input = toolBlock.input as any;
						allChartData.push({
							title: input.indicator || toolBlock.name,
							type: 'ranking',
							data: result.data.map((r: any) => ({
								label: `${r.departamento || ''} (${(r.redcode as string).slice(-4)})`,
								value: r.value
							})),
							unit: undefined
						});
					}

					// Generate chart data from compare_departments
					if (
						toolBlock.name === 'compare_departments' &&
						Array.isArray(result.data) &&
						result.data.length > 0
					) {
						const input = toolBlock.input as any;
						allChartData.push({
							title: input.indicator || 'compare_departments',
							type: 'ranking',
							data: result.data.map((r: any) => ({
								label: r.departamento,
								value: r.value
							})),
							unit: undefined
						});
					}

					// Time series → bar chart
					if (
						toolBlock.name === 'time_series' &&
						Array.isArray(result.data) &&
						result.data.length > 0
					) {
						allChartData.push({
							title: 'NDVI',
							type: 'bar',
							data: result.data.map((r: any) => ({
								label: String(r.year),
								value: r.mean_ndvi
							})),
							unit: 'NDVI'
						});
					}

					toolResults.push({
						type: 'tool_result',
						tool_use_id: toolBlock.id,
						content: JSON.stringify(result.data)
					});

					allToolCalls.push({ name: toolBlock.name, elapsed: Date.now() - t0 });
				} catch (err: any) {
					toolResults.push({
						type: 'tool_result',
						tool_use_id: toolBlock.id,
						content: JSON.stringify({ error: err.message || String(err) }),
						is_error: true
					});
					allToolCalls.push({ name: toolBlock.name, elapsed: Date.now() - t0 });
				}
			}

			// Prepare next iteration: add assistant response + tool results
			currentMessages = [
				...currentMessages,
				{ role: 'assistant' as const, content: response.content },
				{ role: 'user' as const, content: toolResults }
			];

			// If stop_reason is end_turn after tool processing, capture any text
			if (response.stop_reason === 'end_turn') {
				finalText = textParts.join('\n');
				break;
			}
		}

		// Deduplicate map actions: merge highlight redcodes, keep last flyTo
		const mergedMapActions = deduplicateMapActions(allMapActions);

		const result: ChatResponse = {
			text: finalText,
			mapActions: mergedMapActions,
			chartData: allChartData,
			toolCalls: allToolCalls
		};

		return new Response(JSON.stringify(result), {
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

function deduplicateMapActions(actions: MapAction[]): MapAction[] {
	const allRedcodes = new Set<string>();
	let lastFlyTo: MapAction | null = null;
	let lastChoropleth: MapAction | null = null;

	for (const a of actions) {
		if (a.type === 'highlight' && a.redcodes) {
			for (const rc of a.redcodes) allRedcodes.add(rc);
		} else if (a.type === 'flyTo') {
			lastFlyTo = a;
		} else if (a.type === 'choropleth') {
			lastChoropleth = a;
		}
	}

	const result: MapAction[] = [];
	// Choropleth takes priority over simple highlight
	if (lastChoropleth) {
		result.push(lastChoropleth);
	} else if (allRedcodes.size > 0) {
		result.push({ type: 'highlight', redcodes: [...allRedcodes] });
	}
	if (lastFlyTo) {
		result.push(lastFlyTo);
	}
	return result;
}
