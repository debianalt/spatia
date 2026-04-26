<script lang="ts">
	import * as d3 from 'd3';
	import { gridDisk } from 'h3-js';

	let {
		data = new Map() as Map<string, Record<string, any>>,
		variable = '',
		boundaryCache = new Map() as Map<string, number[][]>,
		onShowLisa = (_entries: { h3index: string; value: number; boundary?: number[][] }[]) => {},
	} = $props();

	const allH3s = $derived([...data.keys()]);

	let container: HTMLDivElement;
	let open = $state(false);
	let computing = $state(false);
	let result = $state<{
		I: number; expected: number; variance: number; z: number; p: number; n: number;
		points: { h3: string; std: number; lag: number; quad: string }[];
	} | null>(null);

	$effect(() => {
		if (open && variable && data.size > 0 && allH3s.length > 0) compute();
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

			requestAnimationFrame(() => { if (container) draw(); });
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

		g.selectAll('circle').data(sample).join('circle')
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
	}

	function showLisaOnMap() {
		if (!result) return;
		const LISA_COLORS: Record<string, number> = { 'HH': 4, 'LL': 1, 'HL': 3, 'LH': 2 };
		const entries = result.points.map(p => ({
			h3index: p.h3,
			value: LISA_COLORS[p.quad] ?? 0,
			boundary: boundaryCache.get(p.h3),
		}));
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
					<button class="moran-btn-csv" onclick={exportCSV}>CSV</button>
					<button class="moran-btn-lisa" onclick={showLisaOnMap}>LISA ↗</button>
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
	.moran-btn-lisa {
		font-size: 9px;
		color: #6366f1;
		background: none;
		border: none;
		cursor: pointer;
		padding: 0 2px;
		transition: color 0.15s;
	}
	.moran-btn-lisa:hover { color: #a5b4fc; }
	.moran-plot {
		width: 100%;
		height: 180px;
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
