<script lang="ts">
	import ChartFrame from './ChartFrame.svelte';

	let {
		data = new Map() as Map<string, Record<string, any>>,
		temporalPeriods = null as { baseline: string; current: string } | null,
		onBrushSelect = (_h3s: string[]) => {},
	}: {
		data: Map<string, Record<string, any>>;
		temporalPeriods?: { baseline: string; current: string } | null;
		onBrushSelect?: (h3s: string[]) => void;
	} = $props();

	const SVG_W = 260, SVG_H = 150;
	const BAND_W = 40, PAD_T = 22, PAD_B = 8;
	const LEFT_X = 18, RIGHT_X = SVG_W - 18 - BAND_W;
	const MID_X = SVG_W / 2;
	const plotH = SVG_H - PAD_T - PAD_B;

	const BAND_LABELS = ['Bajo', 'Medio', 'Alto'];
	const BAND_COLORS = ['#fb923c', '#f59e0b', '#22d3ee'];

	function toBand(s: number): 0 | 1 | 2 {
		if (s >= 67) return 2;
		if (s >= 33) return 1;
		return 0;
	}

	type FlowEntry = { h3: string; from: 0 | 1 | 2; to: 0 | 1 | 2 };

	const entries = $derived.by(() => {
		const result: FlowEntry[] = [];
		for (const [h3, row] of data) {
			const s  = Number(row['score']);
			const sb = Number(row['score_baseline']);
			if (!isFinite(s) || !isFinite(sb)) continue;
			result.push({ h3, from: toBand(sb), to: toBand(s) });
		}
		return result;
	});

	const matrix = $derived.by(() => {
		const m: string[][][] = [[[], [], []], [[], [], []], [[], [], []]];
		for (const e of entries) m[e.from][e.to].push(e.h3);
		return m;
	});

	const total      = $derived(entries.length);
	const fromTotals = $derived([0, 1, 2].map(i => entries.filter(e => e.from === i).length));
	const toTotals   = $derived([0, 1, 2].map(i => entries.filter(e => e.to   === i).length));
	const improved   = $derived(entries.filter(e => e.to > e.from).length);
	const worsened   = $derived(entries.filter(e => e.to < e.from).length);
	const stable     = $derived(entries.filter(e => e.to === e.from).length);

	// Band Y positions: Alto(2) at top, Bajo(0) at bottom
	const leftBandY = $derived.by((): Record<number, number> => {
		if (total === 0) return { 0: PAD_T + plotH * 2/3, 1: PAD_T + plotH / 3, 2: PAD_T };
		const h2 = (fromTotals[2] / total) * plotH;
		const h1 = (fromTotals[1] / total) * plotH;
		return { 2: PAD_T, 1: PAD_T + h2, 0: PAD_T + h2 + h1 };
	});
	const leftBandH = $derived(
		[0, 1, 2].map(i => total > 0 ? (fromTotals[i] / total) * plotH : plotH / 3)
	);

	const rightBandY = $derived.by((): Record<number, number> => {
		if (total === 0) return { 0: PAD_T + plotH * 2/3, 1: PAD_T + plotH / 3, 2: PAD_T };
		const h2 = (toTotals[2] / total) * plotH;
		const h1 = (toTotals[1] / total) * plotH;
		return { 2: PAD_T, 1: PAD_T + h2, 0: PAD_T + h2 + h1 };
	});
	const rightBandH = $derived(
		[0, 1, 2].map(i => total > 0 ? (toTotals[i] / total) * plotH : plotH / 3)
	);

	type FlowVis = {
		from: number; to: number; count: number; h3s: string[];
		y1: number; y2: number; strokeW: number; color: string;
	};

	const visFlows = $derived.by(() => {
		if (total === 0) return [] as FlowVis[];
		const lc: Record<number, number> = {
			0: leftBandY[0], 1: leftBandY[1], 2: leftBandY[2],
		};
		const rc: Record<number, number> = {
			0: rightBandY[0], 1: rightBandY[1], 2: rightBandY[2],
		};
		const result: FlowVis[] = [];
		for (let from = 2; from >= 0; from--) {
			for (let to = 2; to >= 0; to--) {
				const h3s = matrix[from][to];
				if (!h3s.length) continue;
				const fh = (h3s.length / total) * plotH;
				const color = to > from ? '#22d3ee' : to < from ? '#f87171' : 'rgba(255,255,255,0.28)';
				result.push({
					from, to, count: h3s.length, h3s,
					y1: lc[from] + fh / 2,
					y2: rc[to]   + fh / 2,
					strokeW: Math.max(1.5, fh * 0.85),
					color,
				});
				lc[from] += fh;
				rc[to]   += fh;
			}
		}
		return result;
	});

	let activeFlow = $state<[number, number] | null>(null);
	let activeSide = $state<'from' | 'to' | null>(null);
	let activeBand = $state<number | null>(null);

	function selectFlow(from: number, to: number) {
		if (activeFlow?.[0] === from && activeFlow?.[1] === to) {
			activeFlow = null; onBrushSelect([]); return;
		}
		activeFlow = [from, to]; activeSide = null; activeBand = null;
		onBrushSelect(matrix[from][to]);
	}

	function selectBand(side: 'from' | 'to', band: number) {
		if (activeSide === side && activeBand === band) {
			activeSide = null; activeBand = null; onBrushSelect([]); return;
		}
		activeSide = side; activeBand = band; activeFlow = null;
		const h3s = side === 'from'
			? entries.filter(e => e.from === band).map(e => e.h3)
			: entries.filter(e => e.to   === band).map(e => e.h3);
		onBrushSelect(h3s);
	}

	$effect(() => {
		void data.size;
		activeFlow = null; activeSide = null; activeBand = null;
	});

	function csvRows() {
		return entries.map(e => ({
			h3index: e.h3,
			band_from: BAND_LABELS[e.from],
			band_to: BAND_LABELS[e.to],
		}));
	}
</script>

<ChartFrame title="Evolución" csvRows={csvRows} csvFilename="spatia_flow">
	<div class="fc-panel">
	<div class="fc-subheader">
		{#if activeFlow !== null}
			<span class="fc-active">
				{BAND_LABELS[activeFlow[0]]}→{BAND_LABELS[activeFlow[1]]}: {matrix[activeFlow[0]][activeFlow[1]].length.toLocaleString()} hex
				<button class="fc-clear" onclick={() => { activeFlow = null; onBrushSelect([]); }}>× quitar</button>
			</span>
		{:else if activeSide !== null && activeBand !== null}
			<span class="fc-active">
				{BAND_LABELS[activeBand]} ({activeSide === 'from' ? 'baseline' : 'actual'}): {(activeSide === 'from' ? fromTotals : toTotals)[activeBand].toLocaleString()} hex
				<button class="fc-clear" onclick={() => { activeSide = null; activeBand = null; onBrushSelect([]); }}>× quitar</button>
			</span>
		{:else if total > 0}
			<span class="fc-hint">↑{improved.toLocaleString()} mejoraron · ↓{worsened.toLocaleString()} empeoraron · ={stable.toLocaleString()} estables</span>
		{:else}
			<span class="fc-hint">seleccioná un departamento</span>
		{/if}
	</div>

	{#if total > 0}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<svg
			width="100%"
			viewBox="0 0 {SVG_W} {SVG_H}"
			preserveAspectRatio="xMidYMid meet"
			style="display:block"
		>
			<!-- Flows (rendered behind bands) -->
			{#each visFlows as f}
				{@const isActive = activeFlow?.[0] === f.from && activeFlow?.[1] === f.to}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<path
					d="M {LEFT_X + BAND_W} {f.y1} C {MID_X} {f.y1}, {MID_X} {f.y2}, {RIGHT_X} {f.y2}"
					fill="none"
					stroke={f.color}
					stroke-width={f.strokeW}
					opacity={activeFlow !== null ? (isActive ? 0.9 : 0.07) : 0.5}
					style="cursor:pointer"
					onclick={() => selectFlow(f.from, f.to)}
				/>
			{/each}

			<!-- Left bands (baseline) -->
			{#each [2, 1, 0] as band}
				{#if leftBandH[band] > 0.5}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<rect
						x={LEFT_X} y={leftBandY[band]}
						width={BAND_W} height={leftBandH[band]}
						fill={BAND_COLORS[band]}
						opacity={activeSide === 'from' && activeBand === band ? 1 : 0.6}
						rx="2"
						style="cursor:pointer"
						onclick={() => selectBand('from', band)}
					/>
					{#if leftBandH[band] > 10}
						<text
							x={LEFT_X + BAND_W / 2} y={leftBandY[band] + leftBandH[band] / 2 + 2.5}
							text-anchor="middle" fill="rgba(0,0,0,0.75)"
							font-size="5.5" font-weight="700" font-family="system-ui,sans-serif"
							pointer-events="none"
						>{BAND_LABELS[band]}</text>
					{/if}
				{/if}
			{/each}

			<!-- Right bands (actual) -->
			{#each [2, 1, 0] as band}
				{#if rightBandH[band] > 0.5}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<rect
						x={RIGHT_X} y={rightBandY[band]}
						width={BAND_W} height={rightBandH[band]}
						fill={BAND_COLORS[band]}
						opacity={activeSide === 'to' && activeBand === band ? 1 : 0.6}
						rx="2"
						style="cursor:pointer"
						onclick={() => selectBand('to', band)}
					/>
					{#if rightBandH[band] > 10}
						<text
							x={RIGHT_X + BAND_W / 2} y={rightBandY[band] + rightBandH[band] / 2 + 2.5}
							text-anchor="middle" fill="rgba(0,0,0,0.75)"
							font-size="5.5" font-weight="700" font-family="system-ui,sans-serif"
							pointer-events="none"
						>{BAND_LABELS[band]}</text>
					{/if}
				{/if}
			{/each}

			<!-- Period labels -->
			<text x={LEFT_X + BAND_W / 2} y={PAD_T - 7} text-anchor="middle"
				fill="rgba(255,255,255,0.32)" font-size="6" font-family="system-ui,sans-serif"
			>{temporalPeriods?.baseline ?? 'Baseline'}</text>
			<text x={RIGHT_X + BAND_W / 2} y={PAD_T - 7} text-anchor="middle"
				fill="rgba(255,255,255,0.32)" font-size="6" font-family="system-ui,sans-serif"
			>{temporalPeriods?.current ?? 'Actual'}</text>
		</svg>
		<div class="fc-note">
			Flujo de hexágonos entre bandas: <em>Bajo</em> (&lt;33) · <em>Medio</em> (33–67) · <em>Alto</em> (≥67) · Clic en un flujo o banda para ver esos hexágonos en el mapa
		</div>
	{/if}
	</div>
</ChartFrame>

<style>
	.fc-panel {
		padding: 2px 0;
	}
	.fc-subheader {
		display: flex;
		align-items: baseline;
		gap: 6px;
		margin-bottom: 2px;
		padding: 0 2px;
		min-height: 14px;
		flex-wrap: wrap;
	}
	.fc-active {
		font-size: 8px;
		color: #a78bfa;
		display: flex;
		align-items: baseline;
		gap: 5px;
	}
	.fc-hint {
		font-size: 8px;
		color: rgba(255,255,255,0.25);
		font-style: italic;
	}
	.fc-clear {
		font-size: 7.5px;
		color: rgba(255,255,255,0.3);
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		line-height: 1;
	}
	.fc-clear:hover { color: #f87171; }
	.fc-note {
		font-size: 7.5px;
		color: rgba(255,255,255,0.22);
		line-height: 1.5;
		padding: 3px 2px 2px;
		border-top: 1px solid rgba(255,255,255,0.06);
		margin-top: 1px;
	}
	.fc-note em {
		font-style: normal;
		color: rgba(255,255,255,0.42);
	}
</style>
