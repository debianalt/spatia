<script lang="ts">
	import { i18n } from '$lib/stores/i18n.svelte';
	import { sendChat, type ChatResponse } from '$lib/chat-engine';
	import ResponseChart from './ResponseChart.svelte';
	import type { ChartDataSet } from './ResponseChart.svelte';

	interface MapAction {
		type: 'highlight' | 'flyTo';
		redcodes?: string[];
		lat?: number;
		lng?: number;
		zoom?: number;
	}

	interface ToolCall {
		name: string;
		elapsed: number;
	}

	interface ChatMessage {
		id: number;
		role: 'user' | 'assistant';
		content: string;
		chartData?: ChartDataSet[];
		toolCalls?: ToolCall[];
	}

	let {
		onResponse,
		collapsed = $bindable(false)
	}: {
		onResponse: (response: ChatResponse) => void;
		collapsed: boolean;
	} = $props();

	let input = $state('');
	let messages = $state<ChatMessage[]>([]);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let apiKey = $state('');
	let showSettings = $state(false);
	let activeTools = $state<string[]>([]);
	let lastUserMessage = $state('');
	let messagesEnd: HTMLDivElement;
	let inputEl: HTMLInputElement;
	let nextId = 0;

	const TOOL_LABELS: Record<string, string> = {
		search_indicators: 'Buscando indicadores',
		ranking: 'Generando ranking',
		search_places: 'Buscando lugares',
		get_stats: 'Consultando estadísticas',
		filter_radios: 'Filtrando radios',
		time_series: 'Consultando series temporales',
		compare_departments: 'Comparando departamentos'
	};

	// Load API key from localStorage
	if (typeof window !== 'undefined') {
		apiKey = localStorage.getItem('neahub_claude_key') || '';
	}

	function saveKey() {
		localStorage.setItem('neahub_claude_key', apiKey);
		showSettings = false;
	}

	function scrollToBottom() {
		setTimeout(() => messagesEnd?.scrollIntoView({ behavior: 'smooth' }), 50);
	}

	function deleteMessage(id: number) {
		messages = messages.filter(m => m.id !== id);
	}

	function clearAllMessages() {
		messages = [];
	}

	async function send(text?: string) {
		const msg = (text || input).trim();
		if (!msg) return;

		if (!apiKey) {
			showSettings = true;
			error = i18n.t('chat.noKey');
			return;
		}

		input = '';
		error = null;
		lastUserMessage = msg;
		collapsed = false;
		messages = [...messages, { id: nextId++, role: 'user', content: msg }];
		loading = true;
		activeTools = ['thinking'];
		scrollToBottom();

		try {
			const history = messages.slice(-10).map((m) => ({
				role: m.role,
				content: m.content
			}));

			const data = await sendChat(
				apiKey,
				msg,
				history.slice(0, -1),
				(toolName) => { activeTools = [...activeTools.filter(t => t !== 'thinking'), toolName]; }
			);

			messages = [
				...messages,
				{
					id: nextId++,
					role: 'assistant',
					content: data.text,
					chartData: data.chartData,
					toolCalls: data.toolCalls
				}
			];

			onResponse(data);
		} catch (e: any) {
			const errMsg = e.message || String(e);
			if (errMsg.includes('401') || errMsg.includes('api_key') || errMsg.includes('API key') || errMsg.includes('authentication')) {
				error = i18n.t('chat.errorApiKey');
			} else {
				error = errMsg;
			}
		} finally {
			loading = false;
			activeTools = [];
			scrollToBottom();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			send();
		}
	}
</script>

{#if collapsed}
	<!-- Collapsed: just a button -->
	<div class="chat-collapsed">
		<button
			class="collapse-btn"
			onclick={() => { collapsed = false; setTimeout(() => inputEl?.focus(), 100); }}
			title="Spatia Chat — Asistente territorial con IA"
		>
			<span class="chat-icon">IA</span>
			<span class="chat-label">Chat</span>
		</button>
	</div>
{:else}
	<!-- Expanded: full chat column -->
	<div class="chat-column">
		<!-- Header -->
		<div class="chat-header">
			<span class="text-[10px] uppercase tracking-widest text-text-dim">
				Spatia Chat
			</span>
			<div class="flex items-center gap-1">
				<button
					class="text-text-dim text-xs cursor-pointer bg-transparent border-none hover:text-text"
					onclick={() => (showSettings = !showSettings)}
					title="API key">⚙</button>
				<button
					class="text-text-dim text-xs cursor-pointer bg-transparent border-none hover:text-text"
					onclick={() => (collapsed = true)}
					title="Colapsar">◀</button>
			</div>
		</div>

		<!-- Settings -->
		{#if showSettings}
			<div class="mx-3 mt-2 p-2 rounded border border-border bg-bg">
				<label class="text-[10px] text-text-dim block mb-1">Claude API Key</label>
				<div class="flex gap-1">
					<input
						type="password"
						bind:value={apiKey}
						placeholder="sk-ant-..."
						class="flex-1 bg-btn-bg border border-btn-border text-text rounded px-2 py-1 text-[11px]"
					/>
					<button
						onclick={saveKey}
						class="bg-accent-active border border-accent text-accent rounded px-2 py-1 text-[10px] cursor-pointer"
					>
						Save
					</button>
				</div>
				<p class="text-text-dim text-[9px] mt-1">Stored in localStorage.</p>
			</div>
		{/if}

		<!-- Messages area -->
		<div class="messages-area">
			{#if messages.length === 0}
				<div class="empty-hint">
					<p class="text-text-dim text-[11px]">{i18n.t('chat.emptyHint')}</p>
				</div>
			{:else}
				<!-- Full history -->
				{#each messages as msg (msg.id)}
					<div class="message {msg.role}">
						{#if msg.role === 'user'}
							<div class="msg-row">
								<div class="msg-bubble user-bubble">{msg.content}</div>
								<button class="delete-msg" onclick={() => deleteMessage(msg.id)} title="Borrar">✕</button>
							</div>
						{:else}
							<div class="msg-row">
								<div class="msg-bubble assistant-bubble">
									{@html formatMarkdown(msg.content)}
									{#if msg.toolCalls && msg.toolCalls.length > 0}
										<div class="tool-pills">
											{#each msg.toolCalls as tc}
												<span class="tool-pill">{TOOL_LABELS[tc.name] || tc.name} ({tc.elapsed}ms)</span>
											{/each}
										</div>
									{/if}
									{#if msg.chartData && msg.chartData.length > 0}
										{#each msg.chartData as chart}
											<ResponseChart {chart} />
										{/each}
									{/if}
								</div>
								<button class="delete-msg" onclick={() => deleteMessage(msg.id)} title="Borrar">✕</button>
							</div>
						{/if}
					</div>
				{/each}
				<div class="flex justify-center py-2">
					<button
						class="text-[10px] text-red-400 border border-red-400/30 rounded px-3 py-1 cursor-pointer bg-transparent hover:bg-red-400/10 transition-all"
						onclick={clearAllMessages}
					>Borrar todo</button>
				</div>
			{/if}

			<!-- Loading indicator -->
			{#if loading}
				<div class="message assistant">
					<div class="msg-bubble assistant-bubble loading-bubble">
						<span class="loading-text">
							{#if activeTools.length > 0}
								{@const lastTool = activeTools[activeTools.length - 1]}
								{lastTool === 'thinking'
									? i18n.t('chat.thinking')
									: TOOL_LABELS[lastTool] || lastTool}...
							{:else}
								{i18n.t('chat.thinking')}...
							{/if}
						</span>
					</div>
				</div>
			{/if}

			<!-- Error -->
			{#if error}
				<div class="message assistant">
					<div class="msg-bubble error-bubble">
						{error}
						{#if lastUserMessage}
							<button class="retry-btn" onclick={() => send(lastUserMessage)}>
								{i18n.t('chat.retry')}
							</button>
						{/if}
					</div>
				</div>
			{/if}

			<div bind:this={messagesEnd}></div>
		</div>

		<!-- Input bar (fixed at bottom) -->
		<div class="chat-input-area">
			{#if !apiKey}
				<!-- Paywall overlay -->
				<div class="paywall">
					<div class="paywall-title">{i18n.t('chat.paywall.title')}</div>
					<div class="paywall-price">$5/día — $20/semana</div>
					<div class="paywall-soon">{i18n.t('chat.paywall.soon')}</div>
					<button
						class="text-text-dim text-[10px] mt-1 cursor-pointer bg-transparent border border-btn-border rounded px-3 py-1 hover:text-text"
						onclick={() => (showSettings = true)}
					>
						¿Tenés API key? Ingresala aquí
					</button>
				</div>
			{:else}
				<div class="flex gap-1.5">
					<input
						bind:this={inputEl}
						bind:value={input}
						type="text"
						placeholder={i18n.t('chat.placeholder')}
						class="flex-1 bg-btn-bg border border-btn-border text-text rounded-md px-2.5 py-1.5 text-[11px]"
						onkeydown={handleKeydown}
						disabled={loading}
					/>
					<button
						onclick={() => send()}
						disabled={loading || !input.trim()}
						class="bg-accent-active border border-accent text-accent rounded-md px-3 py-1.5 text-[11px] font-semibold cursor-pointer disabled:opacity-50"
					>
						{loading ? '...' : i18n.t('chat.send')}
					</button>
				</div>
			{/if}
		</div>
	</div>
{/if}

<script lang="ts" module>
	export function formatMarkdown(text: string): string {
		if (!text) return '';
		return text
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
			.replace(/\*(.+?)\*/g, '<em>$1</em>')
			.replace(/^- (.+)$/gm, '<span style="display:block;padding-left:8px;">• $1</span>')
			.replace(/\n/g, '<br>');
	}
</script>

<style>
	.chat-collapsed {
		width: 48px;
		height: 100%;
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding-top: 12px;
		border-right: 1px solid var(--color-border);
		background: var(--color-panel);
	}
	.collapse-btn {
		width: 36px;
		border-radius: 8px;
		border: 1px solid var(--color-border);
		background: rgba(255, 255, 255, 0.04);
		cursor: pointer;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 4px;
		padding: 8px 0;
		transition: all 0.15s;
	}
	.collapse-btn:hover {
		border-color: var(--color-accent);
		background: rgba(96, 165, 250, 0.1);
	}
	.chat-icon {
		font-size: 10px;
		font-weight: 800;
		color: #60a5fa;
		letter-spacing: -0.5px;
	}
	.chat-label {
		font-size: 7px;
		color: #737373;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.chat-column {
		width: 320px;
		height: 100%;
		display: flex;
		flex-direction: column;
		border-right: 1px solid var(--color-border);
		background: var(--color-panel);
	}

	.chat-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 12px;
		border-bottom: 1px solid var(--color-border);
		flex-shrink: 0;
	}

	.messages-area {
		flex: 1;
		overflow-y: auto;
		min-height: 0;
		padding: 8px 12px;
		scrollbar-width: thin;
		scrollbar-color: #334155 transparent;
	}
	.messages-area::-webkit-scrollbar {
		width: 4px;
	}
	.messages-area::-webkit-scrollbar-thumb {
		background: #334155;
		border-radius: 2px;
	}

	.chat-input-area {
		padding: 8px 12px;
		border-top: 1px solid var(--color-border);
		flex-shrink: 0;
	}

	.empty-hint {
		display: flex;
		justify-content: center;
		padding: 24px 4px;
	}

	.message {
		margin-bottom: 8px;
	}
	.message.user {
		display: flex;
		justify-content: flex-end;
	}
	.message.assistant {
		display: flex;
		justify-content: flex-start;
	}

	.msg-row {
		display: flex;
		align-items: flex-start;
		gap: 4px;
		max-width: 100%;
	}
	.message.user .msg-row {
		flex-direction: row-reverse;
	}

	.delete-msg {
		flex-shrink: 0;
		width: 18px;
		height: 18px;
		border-radius: 50%;
		border: none;
		background: transparent;
		color: #a3a3a3;
		font-size: 10px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		opacity: 0;
		transition: all 0.15s;
		margin-top: 2px;
	}
	.msg-row:hover .delete-msg {
		opacity: 1;
	}
	.delete-msg:hover {
		background: rgba(239, 68, 68, 0.2);
		color: #fca5a5;
	}

	.msg-bubble {
		max-width: 90%;
		padding: 6px 10px;
		border-radius: 8px;
		font-size: 12px;
		line-height: 1.5;
		min-width: 0;
		word-break: break-word;
	}
	.user-bubble {
		background: rgba(96, 165, 250, 0.2);
		color: #e0e0e0;
		border: 1px solid rgba(96, 165, 250, 0.3);
	}
	.assistant-bubble {
		background: rgba(255, 255, 255, 0.04);
		color: #cbd5e1;
		border: 1px solid #1e293b;
	}
	.error-bubble {
		background: rgba(239, 68, 68, 0.15);
		color: #fca5a5;
		border: 1px solid rgba(239, 68, 68, 0.3);
		font-size: 11px;
	}
	.loading-bubble {
		display: flex;
		align-items: center;
	}
	.loading-text {
		font-size: 9px;
		color: #737373;
		font-style: italic;
	}
	@keyframes dot-pulse {
		0%,
		80%,
		100% {
			opacity: 0.3;
		}
		40% {
			opacity: 1;
			transform: scale(1);
		}
	}

	.tool-pills {
		display: flex;
		flex-wrap: wrap;
		gap: 3px;
		margin-top: 4px;
	}
	.tool-pill {
		display: inline-block;
		padding: 1px 6px;
		border-radius: 9999px;
		font-size: 9px;
		background: rgba(96, 165, 250, 0.1);
		color: #a3a3a3;
		border: 1px solid #1e293b;
	}
	.tool-pill.active {
		color: #60a5fa;
		border-color: rgba(96, 165, 250, 0.3);
	}
	.active-tools {
		display: flex;
		gap: 3px;
	}

	.retry-btn {
		display: inline-block;
		margin-top: 6px;
		padding: 2px 10px;
		border-radius: 9999px;
		border: 1px solid rgba(239, 68, 68, 0.4);
		background: rgba(239, 68, 68, 0.1);
		color: #fca5a5;
		font-size: 10px;
		cursor: pointer;
		transition: all 0.15s;
	}
	.retry-btn:hover {
		background: rgba(239, 68, 68, 0.2);
		border-color: rgba(239, 68, 68, 0.6);
	}

	.paywall {
		text-align: center;
		padding: 8px 4px;
	}
	.paywall-title {
		font-size: 12px;
		font-weight: 600;
		color: #f59e0b;
		margin-bottom: 4px;
	}
	.paywall-price {
		font-size: 11px;
		color: #d4d4d4;
		margin-bottom: 2px;
	}
	.paywall-soon {
		font-size: 10px;
		color: #a3a3a3;
		font-style: italic;
		margin-bottom: 6px;
	}
</style>
