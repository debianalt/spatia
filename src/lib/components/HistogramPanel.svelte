<script lang="ts">
	let {
		data = new Map() as Map<string, Record<string, any>>,
		variable = '',
		xLabel = 'score',
		onBrushSelect = (_h3s: string[]) => {},
	}: {
		data: Map<string, Record<string, any>>;
		variable: string;
		xLabel?: string;
		onBrushSelect?: (h3s: string[]) => void;
	} = $props();

	const BINS = 20;
	const PAD_L = 28, PAD_R = 8, PAD_T = 6, PAD_B = 20;
	const SVG_W = 260, SVG_H = 90;
	const plotW = SVG_W - PAD_L - PAD_R;
	const plotH = SVG_H - PAD_T - PAD_B;

	const histogram = $derived.by(() => {
		const bins = new Array(BINS).fill(0);
		for (const row of data.values()) {
			const v = Number(row[variable]);
			if (!isFinite(v)) continue;
			const bin = Math.min(Math.floor(v / (100 / BINS)), BINS - 1);
			bins[bin]++;
		}
		return bins;
	});

	const maxCount = $derived(Math.max(...histogram, 1));
	const totalHexes = $derived(data.size);

	let brushLo: number | null = $state(null);
	let brushHi: number | null = $state(null);
	let selectedCount = $state(0);

	function svgX(pct: number): number {
		return PAD_L + (pct / 100) * plotW;
	}

	const BIN_W = 100 / BINS; // 5 units per bin

	// Account for SVG viewBox scaling: PAD_L/plotW are in viewBox units, clientX in screen px
	function pctFromClientX(clientX: number, rect: DOMRect): number {
		const scale = SVG_W / rect.width; // viewBox units per screen pixel
		const localX = (clientX - rect.left) * scale;
		return Math.max(0, Math.min(100, ((localX - PAD_L) / plotW) * 100));
	}

	function startBrush(e: MouseEvent) {
		const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
		const start = pctFromClientX(e.clientX, rect);
		let end = start;
		brushLo = start;
		brushHi = start;

		const onMove = (ev: MouseEvent) => {
			end = pctFromClientX(ev.clientX, rect);
			brushLo = Math.min(start, end);
			brushHi = Math.max(start, end);
		};

		const onUp = () => {
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
			let lo = Math.min(start, end);
			let hi = Math.max(start, end);
			// Click or tiny drag → snap to the containing bin
			if (hi - lo < BIN_W * 0.8) {
				const binIdx = Math.min(Math.floor(lo / BIN_W), BINS - 1);
				lo = binIdx * BIN_W;
				hi = (binIdx + 1) * BIN_W;
			}
			brushLo = lo;
			brushHi = hi;
			const h3s: string[] = [];
			for (const [h3, row] of data) {
				const v = Number(row[variable]);
				if (isFinite(v) && v >= lo && v <= hi) h3s.push(h3);
			}
			selectedCount = h3s.length;
			onBrushSelect(h3s);
		};

		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
	}

	function clearBrush() {
		brushLo = null;
		brushHi = null;
		selectedCount = 0;
		onBrushSelect([]);
	}

	// Clear brush when data changes (dept switch, analysis change)
	$effect(() => {
		void data.size;
		void variable;
		brushLo = null;
		brushHi = null;
		selectedCount = 0;
	});
</script>

<div class="hpanel">
	<div class="hpanel-header">
		<span class="hpanel-title">Distribución</span>
		<span class="hpanel-unit">{xLabel} 0–100</span>
		{#if brushLo !== null}
			<span class="hpanel-count">{selectedCount.toLocaleString()} hex · doble-clic para limpiar</span>
		{:else}
			<span class="hpanel-hint">arrastrá para seleccionar rango</span>
		{/if}
	</div>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<svg
		width="100%"
		viewBox="0 0 {SVG_W} {SVG_H}"
		preserveAspectRatio="xMidYMid meet"
		onmousedown={startBrush}
		ondblclick={clearBrush}
		style="cursor: crosshair; display: block;"
	>
		<!-- Reference line at 50 -->
		<line
			x1={svgX(50)} x2={svgX(50)}
			y1={PAD_T} y2={PAD_T + plotH}
			stroke="rgba(255,255,255,0.18)" stroke-width="1" stroke-dasharray="3 2"
		/>

		<!-- Bars -->
		{#each histogram as count, i}
			{@const bw = plotW / BINS}
			{@const bx = PAD_L + i * bw}
			{@const bh = (count / maxCount) * plotH}
			{@const by = PAD_T + plotH - bh}
			{@const binLo = i * (100 / BINS)}
			{@const binHi = (i + 1) * (100 / BINS)}
			{@const inBrush = brushLo !== null && brushHi !== null && binHi > brushLo && binLo < brushHi}
			<rect
				x={bx + 0.5} y={by}
				width={bw - 1} height={bh}
				fill={inBrush ? '#34d399' : '#94a3b8'}
				opacity={brushLo !== null && !inBrush ? 0.2 : 0.85}
			/>
		{/each}

		<!-- Brush rect overlay -->
		{#if brushLo !== null && brushHi !== null}
			<rect
				x={svgX(brushLo)} y={PAD_T}
				width={Math.max(0, svgX(brushHi) - svgX(brushLo))} height={plotH}
				fill="#34d399" opacity="0.07"
				stroke="#34d399" stroke-width="1" stroke-opacity="0.35"
				pointer-events="none"
			/>
		{/if}

		<!-- X axis labels -->
		{#each [0, 25, 50, 75, 100] as tick}
			<text
				x={svgX(tick)} y={SVG_H - 4}
				text-anchor="middle" fill="rgba(255,255,255,0.28)"
				font-size="8" font-family="system-ui, sans-serif"
			>{tick}</text>
		{/each}


		<!-- N total (top-left) -->
		<text
			x={PAD_L - 3} y={PAD_T + 5}
			text-anchor="end" fill="rgba(255,255,255,0.22)"
			font-size="7" font-family="system-ui, sans-serif"
		>{totalHexes > 999 ? (totalHexes / 1000).toFixed(0) + 'k' : totalHexes}</text>
	</svg>
</div>

<style>
	.hpanel {
		margin: 8px 0 4px;
		padding: 6px 0 2px;
		border-top: 1px solid rgba(255,255,255,0.06);
	}
	.hpanel-header {
		display: flex;
		align-items: baseline;
		gap: 6px;
		margin-bottom: 2px;
		padding: 0 2px;
	}
	.hpanel-title {
		font-size: 9px;
		font-weight: 700;
		color: rgba(255,255,255,0.45);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}
	.hpanel-count {
		font-size: 8px;
		color: #34d399;
	}
	.hpanel-unit {
		font-size: 8px;
		color: rgba(255,255,255,0.2);
		margin-left: auto;
	}
	.hpanel-hint {
		font-size: 8px;
		color: rgba(255,255,255,0.18);
		font-style: italic;
	}
</style>
