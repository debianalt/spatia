<script lang="ts">
	import { tweened } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';

	let {
		layers,
		labels,
		size = 240,
	}: {
		layers: Array<{values: number[], color: string}>;
		labels: string[];
		size?: number;
	} = $props();

	const pad = 75;
	const vw = $derived(size + 2 * pad);
	const vh = $derived(size + 2 * pad);
	const cx = $derived(vw / 2);
	const cy = $derived(vh / 2);
	const maxR = $derived(size / 2 * 0.85);

	const animAll = tweened([] as number[], {
		duration: 400,
		easing: cubicOut,
		interpolate: (a, b) => (t) => {
			const len = Math.max(a.length, b.length);
			const result = new Array(len);
			for (let i = 0; i < len; i++) {
				const from = a[i] ?? 0;
				const to = b[i] ?? 0;
				result[i] = from + (to - from) * t;
			}
			return result;
		}
	});

	const axisCount = $derived(labels.length || 6);

	$effect(() => {
		const flat: number[] = [];
		for (const layer of layers) {
			for (let i = 0; i < axisCount; i++) flat.push(layer.values[i] ?? 0);
		}
		animAll.set(flat);
	});

	function layerValues(layerIdx: number): number[] {
		const start = layerIdx * axisCount;
		return $animAll.slice(start, start + axisCount);
	}

	const angles = $derived(Array.from({length: axisCount}, (_, i) => (Math.PI * 2 * i) / axisCount - Math.PI / 2));

	function buildPolygonPath(vals: number[]): string {
		const n = axisCount;
		const points: [number, number][] = [];
		for (let i = 0; i < n; i++) {
			const v = Math.max(vals[i] ?? 0, 0) / 100;
			const dist = v * maxR;
			const angle = angles[i];
			points.push([cx + Math.cos(angle) * dist, cy + Math.sin(angle) * dist]);
		}
		let d = `M ${points[0][0]},${points[0][1]}`;
		for (let i = 0; i < n; i++) {
			const next = points[(i + 1) % n];
			const cpDist = maxR * 0.12;
			const midAngle = (angles[i] + angles[(i + 1) % n]) / 2;
			const cpx = cx + Math.cos(midAngle) * cpDist;
			const cpy = cy + Math.sin(midAngle) * cpDist;
			d += ` Q ${cpx},${cpy} ${next[0]},${next[1]}`;
		}
		d += ' Z';
		return d;
	}

	function axisEndpoint(i: number): { x: number; y: number } {
		return {
			x: cx + Math.cos(angles[i]) * maxR,
			y: cy + Math.sin(angles[i]) * maxR
		};
	}

	function labelPos(i: number): { x: number; y: number; anchor: string } {
		const dist = maxR * 1.15;
		const x = cx + Math.cos(angles[i]) * dist;
		const y = cy + Math.sin(angles[i]) * dist;
		const anchor = Math.abs(Math.cos(angles[i])) < 0.3 ? 'middle'
			: Math.cos(angles[i]) > 0 ? 'start' : 'end';
		return { x, y, anchor };
	}

	const LINE_MAX = 14;

	function splitLabel(text: string): string[] {
		if (text.length <= LINE_MAX) return [text];
		const words = text.split(' ');
		const lines: string[] = [];
		let cur = '';
		for (const w of words) {
			if (cur && (cur + ' ' + w).length > LINE_MAX) {
				lines.push(cur);
				cur = w;
			} else {
				cur = cur ? cur + ' ' + w : w;
			}
		}
		if (cur) lines.push(cur);
		return lines;
	}

	// Provincial average reference circle (50 in normalized scale)
	const refR = $derived(maxR * 0.5);
</script>

<svg width="100%" viewBox="0 0 {vw} {vh}" preserveAspectRatio="xMidYMid meet" class="petal-chart">
	<!-- Background circles -->
	{#each [0.25, 0.5, 0.75, 1.0] as frac}
		<circle cx={cx} cy={cy} r={maxR * frac}
			fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="0.6" />
	{/each}

	<!-- Provincial average reference (50 = avg) -->
	<circle cx={cx} cy={cy} r={refR}
		fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="1" stroke-dasharray="4 3" />
	<text x={cx + refR + 4} y={cy - 4}
		fill="rgba(255,255,255,0.45)" font-size="8" font-family="system-ui, sans-serif">
		prov.
	</text>

	<!-- Axes -->
	{#each Array.from({length: axisCount}, (_, i) => i) as i}
		{@const end = axisEndpoint(i)}
		<line x1={cx} y1={cy} x2={end.x} y2={end.y}
			stroke="rgba(255,255,255,0.25)" stroke-width="0.7" />
	{/each}

	<!-- Layers -->
	{#each layers as layer, li}
		{@const vals = layerValues(li)}
		<path d={buildPolygonPath(vals)}
			fill={layer.color} fill-opacity="0.25"
			stroke={layer.color} stroke-width="1.5" stroke-opacity="0.7" />
	{/each}

	<!-- Dots for all layers -->
	{#each layers as layer, li}
		{@const vals = layerValues(li)}
		{#each Array.from({length: axisCount}, (_, i) => i) as i}
			{@const v = Math.max(vals[i] ?? 0, 0) / 100}
			<circle
				cx={cx + Math.cos(angles[i]) * v * maxR}
				cy={cy + Math.sin(angles[i]) * v * maxR}
				r="3.5" fill={layer.color} stroke="#0a0c12" stroke-width="1" />
		{/each}
	{/each}

	<!-- Labels -->
	{#each Array.from({length: axisCount}, (_, i) => i) as i}
		{@const pos = labelPos(i)}
		{@const lines = splitLabel(labels[i] ?? '')}
		{@const offsetY = -(lines.length - 1) * 7}
		<text x={pos.x} y={pos.y + offsetY}
			text-anchor={pos.anchor} dominant-baseline="middle"
			fill="#e2e8f0" font-size="11" font-weight="500" font-family="system-ui, sans-serif">
			{#each lines as line, li}
				<tspan x={pos.x} dy={li === 0 ? 0 : 15}>{line}</tspan>
			{/each}
		</text>
	{/each}
</svg>

<style>
	.petal-chart {
		display: block;
		margin: 0 auto;
	}
</style>
