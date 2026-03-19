<script lang="ts">
	import { tweened } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';

	let {
		values,
		labels,
		color,
		overlayValues,
		overlayColor,
		size = 240
	}: {
		values: number[];
		labels: string[];
		color: string;
		overlayValues?: number[];
		overlayColor?: string;
		size?: number;
	} = $props();

	const r = $derived(size / 2);
	const cx = $derived(r);
	const cy = $derived(r);
	const maxR = $derived(r * 0.78);

	// Animated values
	const animVals = tweened([0, 0, 0, 0, 0, 0], { duration: 400, easing: cubicOut });
	const animOverlay = tweened([0, 0, 0, 0, 0, 0], { duration: 400, easing: cubicOut });

	$effect(() => { animVals.set(values); });
	$effect(() => { animOverlay.set(overlayValues ?? [0, 0, 0, 0, 0, 0]); });

	const angles = [0, 1, 2, 3, 4, 5].map(i => (Math.PI * 2 * i) / 6 - Math.PI / 2);

	function petalPath(vals: number[]): string {
		const pts: string[] = [];
		for (let i = 0; i < 6; i++) {
			const v = Math.max(vals[i] ?? 0, 0) / 100;
			const dist = v * maxR;
			const angle = angles[i];
			const tipX = cx + Math.cos(angle) * dist;
			const tipY = cy + Math.sin(angle) * dist;

			// Control points perpendicular to axis for petal width
			const w = maxR * 0.18;
			const prevAngle = angles[(i + 5) % 6];
			const nextAngle = angles[(i + 1) % 6];
			const midPrev = (angle + prevAngle) / 2;
			const midNext = (angle + nextAngle) / 2;
			const cp1x = cx + Math.cos(midPrev) * dist * 0.5;
			const cp1y = cy + Math.sin(midPrev) * dist * 0.5;
			const cp2x = cx + Math.cos(midNext) * dist * 0.5;
			const cp2y = cy + Math.sin(midNext) * dist * 0.5;

			pts.push(`Q ${cp1x},${cp1y} ${tipX},${tipY} Q ${cp2x},${cp2y}`);
		}
		// Close path by returning to first point
		const v0 = Math.max(vals[0] ?? 0, 0) / 100;
		const startX = cx + Math.cos(angles[0]) * v0 * maxR;
		const startY = cy + Math.sin(angles[0]) * v0 * maxR;

		// Simpler approach: connect center → tip for each petal as segments
		return buildPolygonPath(vals);
	}

	function buildPolygonPath(vals: number[]): string {
		const points: [number, number][] = [];
		for (let i = 0; i < 6; i++) {
			const v = Math.max(vals[i] ?? 0, 0) / 100;
			const dist = v * maxR;
			const angle = angles[i];
			points.push([cx + Math.cos(angle) * dist, cy + Math.sin(angle) * dist]);
		}
		// Build smooth closed path with bezier curves through petal tips
		let d = `M ${points[0][0]},${points[0][1]}`;
		for (let i = 0; i < 6; i++) {
			const curr = points[i];
			const next = points[(i + 1) % 6];
			// Curve through center-ish for petal effect
			const cpDist = maxR * 0.12;
			const midAngle = (angles[i] + angles[(i + 1) % 6]) / 2;
			// Control point pulled towards center
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

<svg width={size} height={size} viewBox="0 0 {size} {size}" overflow="visible" class="petal-chart">
	<!-- Background circles -->
	{#each [0.25, 0.5, 0.75, 1.0] as frac}
		<circle cx={cx} cy={cy} r={maxR * frac}
			fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="0.7" />
	{/each}

	<!-- Axes -->
	{#each [0, 1, 2, 3, 4, 5] as i}
		{@const end = axisEndpoint(i)}
		<line x1={cx} y1={cy} x2={end.x} y2={end.y}
			stroke="rgba(255,255,255,0.12)" stroke-width="0.6" />
	{/each}

	<!-- Overlay petal (comparison) -->
	{#if overlayValues}
		<path d={buildPolygonPath($animOverlay)}
			fill={overlayColor ?? '#94a3b8'} fill-opacity="0.2"
			stroke={overlayColor ?? '#94a3b8'} stroke-width="1" stroke-opacity="0.5" />
	{/if}

	<!-- Main petal -->
	<path d={buildPolygonPath($animVals)}
		fill={color} fill-opacity="0.35"
		stroke={color} stroke-width="1.5" stroke-opacity="0.9" />

	<!-- Dot at each tip -->
	{#each [0, 1, 2, 3, 4, 5] as i}
		{@const v = Math.max($animVals[i] ?? 0, 0) / 100}
		<circle
			cx={cx + Math.cos(angles[i]) * v * maxR}
			cy={cy + Math.sin(angles[i]) * v * maxR}
			r="3" fill={color} />
	{/each}

	<!-- Labels -->
	{#each [0, 1, 2, 3, 4, 5] as i}
		{@const pos = labelPos(i)}
		<text x={pos.x} y={pos.y}
			text-anchor={pos.anchor} dominant-baseline="middle"
			fill="#94a3b8" font-size="9" font-family="Inter, sans-serif">
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
