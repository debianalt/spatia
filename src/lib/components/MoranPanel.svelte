<script lang="ts">
	import * as d3 from 'd3';
	import { gridDisk } from 'h3-js';

	let {
		data = new Map() as Map<string, Record<string, any>>,
		variable = '',
		boundaryCache = new Map() as Map<string, number[][]>,
		onShowLisa = (_entries: { h3index: string; value: number; boundary?: number[][] }[]) => {},
		onBrushSelect = (_h3s: string[]) => {},
	} = $props();

	const allH3s = $derived([...data.keys()]);

	let container: HTMLDivElement;
	let open = $state(true);
	let computing = $state(false);
	let brushCount = $state(0);
	let lisaMode = $state(false);
	let result = $state<{
		I: number; expected: number; variance: number; z: number; p: number; n: number;
		points: { h3: string; std: number; lag: number; quad: string }[];
	} | null>(null);

	$effect(() => {
		if (open && variable && data.size > 0 && allH3s.length > 0) compute();
	});

	$effect(() => {
		if (result && container) draw();
	});

	function compute() {
		computing = true;
		result = null;

		requestAnimationFrame(() => {
			const vals = new Map<string, number>();
			let sum = 0, n = 0;

			for (const h3 of allH3s) {
				const row = data.get(h3);
				const v = row?.[variable];
				if (typeof v === 'number' && !isNaN(v)) { vals.set(h3, v); sum += v; n++; }
			}
			if (n < 10) { computing = false; return; }

			const mean = sum / n;
			let variance = 0;
			for (const v of vals.values()) variance += (v - mean) ** 2;
			variance /= n;
			const sd = Math.sqrt(variance);
			if (sd < 1e-10) { computing = false; return; }

			const std = new Map<string, number>();
			for (const [h3, v] of vals) std.set(h3, (v - mean) / sd);

			const lag = new Map<string, number>();
			let W = 0;
			let sumWZiZj = 0;

			for (const h3 of vals.keys()) {
				const neighbors = gridDisk(h3, 1).filter(nb => nb !== h3 && vals.has(nb));
				if (neighbors.length === 0) continue;
				const zi = std.get(h3)!;
				let lagSum = 0;
				for (const nb of neighbors) {
					lagSum += std.get(nb)!;
					sumWZiZj += zi * std.get(nb)!;
					W++;
				}
				lag.set(h3, lagSum / neighbors.length);
			}

			let sumZ2 = 0;
			for (const z of std.values()) sumZ2 += z * z;

			const I = W > 0 ? (n / W) * sumWZiZj / sumZ2 : 0;
			const expected = -1 / (n - 1);
			const varI = 1 / (n - 1) - expected * expected;
			const z = varI > 0 ? (I - expected) / Math.sqrt(varI) : 0;
			const p = 2 * (1 - normalCDF(Math.abs(z)));

			const points: { h3: string; std: number; lag: number; quad: string }[] = [];
			for (const h3 of vals.keys()) {
				const zi = std.get(h3)!;
				const li = lag.get(h3);
				if (li === undefined) continue;
				let quad: string;
				if (zi > 0 && li > 0) quad = 'HH';
				else if (zi < 0 && li < 0) quad = 'LL';
				else if (zi > 0 && li < 0) quad = 'HL';
				else quad = 'LH';
				points.push({ h3, std: zi, lag: li, quad });
			}

			result = { I, expected, variance: varI, z, p, n, points };
			computing = false;
		});
	}

	function normalCDF(x: number): number {
		const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429;
		const p = 0.3275911;
		const sign = x < 0 ? -1 : 1;
		x = Math.abs(x) / Math.sqrt(2);
		const t = 1 / (1 + p * x);
		const y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
		return 0.5 * (1 + sign * y);
	}

	const QUAD_COLORS: Record<string, string> = {
		'HH': '#ef4444', 'LL': '#3b82f6', 'HL': '#f97316', 'LH': '#60a5fa'
	};

	function draw() {
		if (!result || !container) return;
		brushCount = 0;
		onBrushSelect([]);
		const { I, points } = result;

		const W = container.clientWidth;
		const H = container.clientHeight;
		const m = { top: 10, right: 12, bottom: 28, left: 40 };
		const w = W - m.left - m.right;
		const h = H - m.top - m.bottom;

		d3.select(container).selectAll('*').remove();
		const svg = d3.select(container).append('svg').attr('width', W).attr('height', H);
		const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);

		const sample = points.length > 2000
			? points.filter((_, i) => i % Math.ceil(points.length / 2000) === 0)
			: points;

		const xExt = d3.extent(sample, p => p.std) as [number, number];
		const yExt = d3.extent(sample, p => p.lag) as [number, number];
		const ext = Math.max(Math.abs(xExt[0]), Math.abs(xExt[1]), Math.abs(yExt[0]), Math.abs(yExt[1])) * 1.1;

		const x = d3.scaleLinear().domain([-ext, ext]).range([0, w]);
		const y = d3.scaleLinear().domain([-ext, ext]).range([h, 0]);

		g.append('rect').attr('x', x(0)).attr('y', 0).attr('width', w - x(0)).attr('height', y(0))
			.attr('fill', '#ef44441a');
		g.append('rect').attr('x', 0).attr('y', y(0)).attr('width', x(0)).attr('height', h - y(0))
			.attr('fill', '#3b82f61a');
		g.append('rect').attr('x', x(0)).attr('y', y(0)).attr('width', w - x(0)).attr('height', h - y(0))
			.attr('fill', '#f973161a');
		g.append('rect').attr('x', 0).attr('y', 0).attr('width', x(0)).attr('height', y(0))
			.attr('fill', '#60a5fa1a');

		g.append('line').attr('x1', 0).attr('x2', w).attr('y1', y(0)).attr('y2', y(0))
			.attr('stroke', '#334155').attr('stroke-width', 0.5);
		g.append('line').attr('x1', x(0)).attr('x2', x(0)).attr('y1', 0).attr('y2', h)
			.attr('stroke', '#334155').attr('stroke-width', 0.5);

		g.append('line')
			.attr('x1', x(-ext)).attr('y1', y(-ext * I))
			.attr('x2', x(ext)).attr('y2', y(ext * I))
			.attr('stroke', '#f59e0b').attr('stroke-width', 1.5)
			.attr('stroke-dasharray', '6,4').attr('opacity', 0.7);

		const dots = g.selectAll('circle').data(sample).join('circle')
			.attr('cx', d => x(d.std)).attr('cy', d => y(d.lag))
			.attr('r', 2).attr('fill', d => QUAD_COLORS[d.quad]).attr('opacity', 0.5);

		const fontSize = '9px';
		g.append('text').attr('x', w - 4).attr('y', 12)
			.attr('text-anchor', 'end').attr('fill', '#ef4444').attr('font-size', fontSize).text('HH (alta)');
		g.append('text').attr('x', 4).attr('y', h - 4)
			.attr('fill', '#3b82f6').attr('font-size', fontSize).text('LL (baja)');
		g.append('text').attr('x', w - 4).attr('y', h - 4)
			.attr('text-anchor', 'end').attr('fill', '#f97316').attr('font-size', fontSize).text('HL');
		g.append('text').attr('x', 4).attr('y', 12)
			.attr('fill', '#60a5fa').attr('font-size', fontSize).text('LH');

		svg.append('text').attr('x', W / 2).attr('y', H - 2)
			.attr('text-anchor', 'middle').attr('fill', '#a3a3a3').attr('font-size', '9px').text(`z(${variable})`);
		svg.append('text').attr('x', 10).attr('y', H / 2)
			.attr('text-anchor', 'middle').attr('fill', '#a3a3a3').attr('font-size', '9px')
			.attr('transform', `rotate(-90,10,${H / 2})`).text('Spatial lag');

		g.append('g').attr('transform', `translate(0,${h})`)
			.call(d3.axisBottom(x).ticks(5))
			.call(g => g.selectAll('text').attr('fill', '#a3a3a3').attr('font-size', '8px'))
			.call(g => g.selectAll('line,path').attr('stroke', '#334155'));
		g.append('g')
			.call(d3.axisLeft(y).ticks(5))
			.call(g => g.selectAll('text').attr('fill', '#a3a3a3').attr('font-size', '8px'))
			.call(g => g.selectAll('line,path').attr('stroke', '#334155'));

		// Manual brush — d3.brush can be blocked by overflow:auto scroll containers
		let bx0 = 0, by0 = 0, bx1 = 0, by1 = 0;
		const brushRect = g.append('rect')
			.attr('class', 'brush-rect')
			.attr('fill', 'rgba(251,191,36,0.1)')
			.attr('stroke', '#fbbf24')
			.attr('stroke-width', 0.8)
			.attr('pointer-events', 'none')
			.style('display', 'none');

		g.append('rect')
			.attr('class', 'brush-overlay')
			.attr('x', 0).attr('y', 0)
			.attr('width', w).attr('height', h)
			.attr('fill', 'none')
			.attr('pointer-events', 'all')
			.attr('cursor', 'crosshair')
			.on('mousedown', function(event: MouseEvent) {
				event.preventDefault();
				[bx0, by0] = d3.pointer(event);
				bx1 = bx0; by1 = by0;
				brushRect.style('display', null).attr('x', bx0).attr('y', by0).attr('width', 0).attr('height', 0);

				function onMove(e: MouseEvent) {
					const [mx, my] = d3.pointer(e, g.node()!);
					bx1 = Math.max(0, Math.min(w, mx));
					by1 = Math.max(0, Math.min(h, my));
					brushRect
						.attr('x', Math.min(bx0, bx1)).attr('y', Math.min(by0, by1))
						.attr('width', Math.abs(bx1 - bx0)).attr('height', Math.abs(by1 - by0));
				}

				function onUp() {
					window.removeEventListener('mousemove', onMove);
					window.removeEventListener('mouseup', onUp);
					if (Math.abs(bx1 - bx0) < 3 && Math.abs(by1 - by0) < 3) {
						brushRect.style('display', 'none');
						dots.attr('opacity', 0.5).attr('r', 2);
						brushCount = 0;
						onBrushSelect([]);
						return;
					}
					const x0 = x.invert(Math.min(bx0, bx1));
					const x1 = x.invert(Math.max(bx0, bx1));
					const y0 = y.invert(Math.max(by0, by1));
					const y1 = y.invert(Math.min(by0, by1));
					const selectedSet = new Set(
						result!.points
							.filter(p => p.std >= x0 && p.std <= x1 && p.lag >= y0 && p.lag <= y1)
							.map(p => p.h3)
					);
					dots.each(function(d: any) {
						const inside = selectedSet.has(d.h3);
						d3.select(this).attr('opacity', inside ? 1 : 0.08).attr('r', inside ? 3 : 2);
					});
					brushCount = selectedSet.size;
					onBrushSelect([...selectedSet]);
				}

				window.addEventListener('mousemove', onMove);
				window.addEventListener('mouseup', onUp);
			});
	}

	function clearBrush() {
		if (container) {
			d3.select(container).selectAll<SVGCircleElement, unknown>('circle')
				.attr('opacity', 0.5).attr('r', 2);
			d3.select(container).select('.brush-rect').style('display', 'none');
			brushCount = 0;
			onBrushSelect([]);
		}
	}

	function toggleLisa() {
		if (lisaMode) {
			lisaMode = false;
			onShowLisa([]);
			return;
		}
		if (!result) return;
		const LISA_COLORS: Record<string, number> = { 'HH': 4, 'LL': 1, 'HL': 3, 'LH': 2 };
		const entries = result.points.map(p => ({
			h3index: p.h3,
			value: LISA_COLORS[p.quad] ?? 0,
			boundary: boundaryCache.get(p.h3),
		}));
		lisaMode = true;
		onShowLisa(entries);
	}

	function exportCSV() {
		if (!result) return;
		const counts = { HH: 0, LL: 0, HL: 0, LH: 0 };
		for (const p of result.points) counts[p.quad as keyof typeof counts]++;
		const pStr = result.p < 0.001 ? '<0.001' : result.p.toFixed(4);
		const header = 'variable,I,E[I],z,p,n,HH,LL,HL,LH';
		const row = [variable, result.I.toFixed(6), result.expected.toFixed(6), result.z.toFixed(4), pStr, result.n, counts.HH, counts.LL, counts.HL, counts.LH].join(',');
		const csv = [header, row].join('\n');
		const blob = new Blob([csv], { type: 'text/csv' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `moran_${variable}_${new Date().toISOString().slice(0, 10)}.csv`;
		a.click();
		URL.revokeObjectURL(url);
	}
</script>

<div class="moran-wrap">
	<button class="moran-toggle" onclick={() => { open = !open; }}>
		<span class="moran-arrow">{open ? '▾' : '▸'}</span>
		Autocorrelación espacial
		{#if result && !open}
			<span class="moran-badge">I = {result.I.toFixed(3)}</span>
		{/if}
	</button>

	{#if open}
		<div class="moran-body">
			{#if computing}
				<div class="moran-loading">
					<div class="moran-spinner"></div>
					Calculando Moran's I...
				</div>
			{:else if result}
				<div class="moran-stats">
					<span class="moran-I">I = {result.I.toFixed(4)}</span>
					<span class="moran-dim">E[I] = {result.expected.toFixed(4)}</span>
					<span class="moran-dim">z = {result.z.toFixed(2)}</span>
					<span class="{result.p < 0.05 ? 'moran-sig' : 'moran-insig'}">p {result.p < 0.001 ? '< 0.001' : '= ' + result.p.toFixed(3)}</span>
					<span class="moran-dim">n = {result.n}</span>
					{#if brushCount > 0}
						<span class="moran-sel">{brushCount} sel.</span>
						<button class="moran-btn-clear" onclick={clearBrush}>✕</button>
					{/if}
					<button class="moran-btn-csv" onclick={exportCSV}>CSV</button>
				</div>
				<div class="moran-mapview">
					<span class="moran-dim">Mapa:</span>
					<button class="moran-view-btn" class:moran-view-btn-active={!lisaMode}
						onclick={() => { if (lisaMode) { lisaMode = false; onShowLisa([]); } }}>
						coropleta
					</button>
					<button class="moran-view-btn" class:moran-view-btn-active={lisaMode}
						onclick={() => { if (!lisaMode) toggleLisa(); }}>
						LISA
					</button>
				</div>
				<div bind:this={container} class="moran-plot"></div>
				<div class="moran-quads">
					{#each ['HH', 'LL', 'HL', 'LH'] as q}
						<span style="color: {QUAD_COLORS[q]}">{q}: {result.points.filter(p => p.quad === q).length}</span>
					{/each}
				</div>
			{:else if data.size > 0}
				<div class="moran-empty">Datos insuficientes para calcular autocorrelación</div>
			{:else}
				<div class="moran-empty">Cargá una capa para calcular autocorrelación espacial</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.moran-wrap {
		margin-top: 10px;
		border-top: 1px solid rgba(255,255,255,0.07);
		padding-top: 6px;
	}
	.moran-toggle {
		display: flex;
		align-items: center;
		gap: 5px;
		font-size: 10px;
		color: #a3a3a3;
		background: none;
		border: none;
		cursor: pointer;
		padding: 2px 0;
		width: 100%;
		text-align: left;
		transition: color 0.15s;
	}
	.moran-toggle:hover { color: #d4d4d4; }
	.moran-arrow { font-size: 8px; }
	.moran-badge {
		margin-left: auto;
		font-family: monospace;
		font-size: 9px;
		color: #f59e0b;
	}
	.moran-body {
		margin-top: 6px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.moran-loading {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 10px;
		color: #737373;
		padding: 8px 0;
	}
	.moran-spinner {
		width: 10px;
		height: 10px;
		border: 2px solid #6366f1;
		border-top-color: transparent;
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}
	@keyframes spin { to { transform: rotate(360deg); } }
	.moran-stats {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
		font-size: 10px;
		font-family: monospace;
	}
	.moran-I { color: #f59e0b; font-weight: bold; }
	.moran-dim { color: #737373; }
	.moran-sig { color: #4ade80; }
	.moran-insig { color: #f87171; }
	.moran-sel { color: #fbbf24; font-size: 9px; }
	.moran-btn-clear {
		font-size: 9px;
		color: #fbbf24;
		background: none;
		border: none;
		cursor: pointer;
		padding: 0 2px;
		transition: color 0.15s;
	}
	.moran-btn-clear:hover { color: #fde68a; }
	.moran-btn-csv {
		margin-left: auto;
		font-size: 9px;
		color: #737373;
		background: none;
		border: none;
		cursor: pointer;
		padding: 0 2px;
		transition: color 0.15s;
	}
	.moran-btn-csv:hover { color: #6366f1; }
	.moran-mapview {
		display: flex;
		align-items: center;
		gap: 5px;
	}
	.moran-view-btn {
		font-size: 9px;
		padding: 2px 8px;
		border: 1px solid #334155;
		border-radius: 3px;
		background: none;
		color: #737373;
		cursor: pointer;
		font-family: monospace;
		transition: all 0.12s;
	}
	.moran-view-btn:hover { color: #d4d4d4; border-color: #4b5563; }
	.moran-view-btn-active {
		background: rgba(99,102,241,0.15);
		border-color: #6366f1;
		color: #a5b4fc;
	}
	.moran-plot {
		width: 100%;
		height: 180px;
		user-select: none;
	}
	.moran-quads {
		display: flex;
		gap: 8px;
		font-size: 9px;
	}
	.moran-empty {
		font-size: 10px;
		color: #525252;
		padding: 6px 0;
	}
</style>
