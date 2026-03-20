<script lang="ts">
	import { tweened } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';

	let {
		layers,
		labels,
		size = 240
	}: {
		layers: Array<{values: number[], color: string}>;
		labels: string[];
		size?: number;
	} = $props();

	const pad = 70; // space for labels outside the chart
	const vw = $derived(size + 2 * pad);
	const vh = $derived(size + 2 * pad);
	const cx = $derived(vw / 2);
	const cy = $derived(vh / 2);
	const maxR = $derived(size / 2 * 0.78);

	// Flatten all layer values into a single tweened array, then slice per layer
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

	$effect(() => {
		const flat: number[] = [];
		for (const layer of layers) {
			for (let i = 0; i < 6; i++) flat.push(layer.values[i] ?? 0);
		}
		animAll.set(flat);
	});

	function layerValues(layerIdx: number): number[] {
		const start = layerIdx * 6;
		return $animAll.slice(start, start + 6);
	}

	const angles = [0, 1, 2, 3, 4, 5].map(i => (Math.PI * 2 * i) / 6 - Math.PI / 2);

	function buildPolygonPath(vals: number[]): string {
		const points: [number, number][] = [];
		for (let i = 0; i < 6; i++) {
			const v = Math.max(vals[i] ?? 0, 0) / 100;
			const dist = v * maxR;
			const angle = angles[i];
			points.push([cx + Math.cos(angle) * dist, cy + Math.sin(angle) * dist]);
		}
		let d = `M ${points[0][0]},${points[0][1]}`;
		for (let i = 0; i < 6; i++) {
			const next = points[(i + 1) % 6];
			const cpDist = maxR * 0.12;
			const midAngle = (angles[i] + angles[(i + 1) % 6]) / 2;
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
</script>

<svg width="100%" viewBox="0 0 {vw} {vh}" preserveAspectRatio="xMidYMid meet" class="petal-chart">
	<!-- Background circles -->
	{#each [0.25, 0.5, 0.75, 1.0] as frac}
		<circle cx={cx} cy={cy} r={maxR * frac}
			fill="none" stroke="rgba(255,255,255,0.3)" stroke-width="0.8" />
	{/each}

	<!-- Axes -->
	{#each [0, 1, 2, 3, 4, 5] as i}
		{@const end = axisEndpoint(i)}
		<line x1={cx} y1={cy} x2={end.x} y2={end.y}
			stroke="rgba(255,255,255,0.25)" stroke-width="0.7" />
	{/each}

	<!-- Layers: first drawn first (bottom), last on top -->
	{#each layers as layer, li}
		{@const vals = layerValues(li)}
		<path d={buildPolygonPath(vals)}
			fill={layer.color} fill-opacity="0.25"
			stroke={layer.color} stroke-width="1.5" stroke-opacity="0.7" />
	{/each}

	<!-- Dots only for first layer -->
	{#if layers.length > 0}
		{@const vals0 = layerValues(0)}
		{#each [0, 1, 2, 3, 4, 5] as i}
			{@const v = Math.max(vals0[i] ?? 0, 0) / 100}
			<circle
				cx={cx + Math.cos(angles[i]) * v * maxR}
				cy={cy + Math.sin(angles[i]) * v * maxR}
				r="3" fill={layers[0].color} />
		{/each}
	{/if}

	<!-- Labels -->
	{#each [0, 1, 2, 3, 4, 5] as i}
		{@const pos = labelPos(i)}
		<text x={pos.x} y={pos.y}
			text-anchor={pos.anchor} dominant-baseline="middle"
			fill="#e2e8f0" font-size="12" font-weight="500" font-family="JetBrains Mono, monospace">
			{labels[i] ?? ''}
		</text>
	{/each}
</svg>

<style>
	.petal-chart {
		display: block;
		margin: 0 auto;
	}
</style>
