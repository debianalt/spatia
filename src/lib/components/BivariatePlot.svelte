<script lang="ts">
	import { query } from '$lib/stores/duckdb';
	import { ANALYSIS_REGISTRY, HEX_LAYER_REGISTRY, getSatGlobalUrl } from '$lib/config';
	import { i18n } from '$lib/stores/i18n.svelte';
	import ChartFrame from './ChartFrame.svelte';

	let {
		data = new Map() as Map<string, Record<string, any>>,
		variable = '',
		xLabel = 'score',
		analysisId = '',
		territoryPrefix = '',
		onBrushSelect = (_h3s: string[]) => {},
	}: {
		data: Map<string, Record<string, any>>;
		variable: string;
		xLabel?: string;
		analysisId?: string;
		territoryPrefix?: string;
		onBrushSelect?: (h3s: string[]) => void;
	} = $props();

	const PAD_L = 28, PAD_R = 8, PAD_T = 8, PAD_B = 22;
	const SVG_W = 260, SVG_H = 200;
	const plotW = SVG_W - PAD_L - PAD_R;
	const plotH = SVG_H - PAD_T - PAD_B;

	const comparableAnalyses = $derived(
		ANALYSIS_REGISTRY.filter(a => a.comparable && a.id !== analysisId)
	);

	let selectedB = $state('');
	let bData = $state(new Map<string, number>());
	let bLoading = $state(false);
	let bError = $state(false);

	$effect(() => {
		const b = selectedB;
		if (!b) { bData = new Map(); return; }
		const layer = HEX_LAYER_REGISTRY[b];
		if (!layer) return;
		const url = getSatGlobalUrl(b, territoryPrefix);
		const bVar = layer.primaryVariable;
		bLoading = true;
		bError = false;
		query(`SELECT h3index, "${bVar}" as val FROM read_parquet('${url}')`)
			.then(result => {
				const m = new Map<string, number>();
				for (let i = 0; i < result.numRows; i++) {
					const row = result.get(i)!.toJSON();
					const v = Number(row.val);
					if (isFinite(v)) m.set(String(row.h3index), v);
				}
				bData = m;
				bLoading = false;
			})
			.catch(() => {
				bError = true;
				bLoading = false;
			});
	});

	const yLabel = $derived.by(() => {
		if (!selectedB) return '';
		const layer = HEX_LAYER_REGISTRY[selectedB];
		if (!layer) return 'score /100';
		return layer.variables.some(v => v.unit === 'percentil') ? 'percentil prov.' : 'score /100';
	});

	const allPoints = $derived.by(() => {
		if (!selectedB || bData.size === 0) return [] as { x: number; y: number; h3: string }[];
		const pts: { x: number; y: number; h3: string }[] = [];
		for (const [h3, row] of data) {
			const x = Number(row[variable]);
			const y = bData.get(h3);
			if (y !== undefined && isFinite(x) && isFinite(y)) {
				pts.push({ x, y, h3 });
			}
		}
		return pts;
	});

	const renderedPoints = $derived.by(() => {
		const MAX = 2500;
		if (allPoints.length <= MAX) return allPoints;
		const stride = Math.ceil(allPoints.length / MAX);
		return allPoints.filter((_, i) => i % stride === 0);
	});

	function svgX(v: number): number { return PAD_L + (v / 100) * plotW; }
	function svgY(v: number): number { return PAD_T + (1 - v / 100) * plotH; }

	function clientToData(clientX: number, clientY: number, rect: DOMRect): [number, number] {
		const scaleX = SVG_W / rect.width;
		const scaleY = SVG_H / rect.height;
		const lx = (clientX - rect.left) * scaleX;
		const ly = (clientY - rect.top) * scaleY;
		const px = Math.max(0, Math.min(100, (lx - PAD_L) / plotW * 100));
		const py = Math.max(0, Math.min(100, (1 - (ly - PAD_T) / plotH) * 100));
		return [px, py];
	}

	let brushRect: { x0: number; y0: number; x1: number; y1: number } | null = $state(null);
	let selectedCount = $state(0);

	function startBrush(e: MouseEvent) {
		if (!selectedB || bData.size === 0) return;
		const svgEl = e.currentTarget as SVGElement;
		const rect = svgEl.getBoundingClientRect();
		const [sx, sy] = clientToData(e.clientX, e.clientY, rect);
		let ex = sx, ey = sy;
		brushRect = { x0: sx, y0: sy, x1: sx, y1: sy };

		const onMove = (ev: MouseEvent) => {
			[ex, ey] = clientToData(ev.clientX, ev.clientY, rect);
			brushRect = {
				x0: Math.min(sx, ex), y0: Math.min(sy, ey),
				x1: Math.max(sx, ex), y1: Math.max(sy, ey),
			};
		};

		const onUp = () => {
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
			const br = brushRect;
			if (!br || (br.x1 - br.x0 < 2 && br.y1 - br.y0 < 2)) {
				clearBrush();
				return;
			}
			const h3s: string[] = [];
			for (const pt of allPoints) {
				if (pt.x >= br.x0 && pt.x <= br.x1 && pt.y >= br.y0 && pt.y <= br.y1) {
					h3s.push(pt.h3);
				}
			}
			selectedCount = h3s.length;
			onBrushSelect(h3s);
		};

		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
	}

	function clearBrush() {
		brushRect = null;
		selectedCount = 0;
		onBrushSelect([]);
	}

	$effect(() => {
		void data.size;
		void variable;
		void selectedB;
		brushRect = null;
		selectedCount = 0;
	});

	function csvRows() {
		return allPoints.map(p => ({ h3index: p.h3, x: p.x.toFixed(2), y: p.y.toFixed(2) }));
	}
</script>

<ChartFrame title="Bivariado" csvRows={csvRows} csvFilename="spatia_bivariate">
	<div class="bvpanel">
	<div class="bvpanel-subheader">
		{#if brushRect !== null}
			<span class="bvpanel-count">{selectedCount.toLocaleString()} hex · doble-clic para limpiar</span>
		{:else if selectedB && allPoints.length > 0}
			<span class="bvpanel-hint">{allPoints.length.toLocaleString()} pts · arrastrá para seleccionar</span>
		{:else}
			<span class="bvpanel-hint">elegí un eje Y abajo</span>
		{/if}
	</div>

	<div class="bvpanel-picker">
		<span class="picker-label">Eje Y:</span>
		<select bind:value={selectedB} class="picker-select">
			<option value="">— seleccionar —</option>
			{#each comparableAnalyses as a}
				<option value={a.id}>{i18n.t(a.titleKey)}</option>
			{/each}
		</select>
	</div>

	{#if bLoading}
		<div class="bvpanel-state">cargando…</div>
	{:else if bError}
		<div class="bvpanel-state bvpanel-error">error al cargar datos</div>
	{:else if !selectedB}
		<div class="bvpanel-empty-prompt">
			Seleccioná un segundo análisis en "Eje Y" para explorar correlaciones y seleccionar hexágonos en el mapa.
		</div>
	{:else if selectedB && allPoints.length === 0 && bData.size > 0}
		<div class="bvpanel-state">sin hexágonos en común</div>
	{:else if selectedB && allPoints.length > 0}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<svg
			width="100%"
			viewBox="0 0 {SVG_W} {SVG_H}"
			preserveAspectRatio="xMidYMid meet"
			onmousedown={startBrush}
			ondblclick={clearBrush}
			style="cursor: crosshair; display: block;"
		>
			<!-- Quadrant guide lines -->
			<line x1={svgX(50)} x2={svgX(50)} y1={PAD_T} y2={PAD_T + plotH}
				stroke="rgba(255,255,255,0.14)" stroke-width="1" stroke-dasharray="3 2" />
			<line x1={PAD_L} x2={PAD_L + plotW} y1={svgY(50)} y2={svgY(50)}
				stroke="rgba(255,255,255,0.14)" stroke-width="1" stroke-dasharray="3 2" />

			<!-- Faint quadrant labels -->
			<text x={svgX(25)} y={svgY(75) + 4} text-anchor="middle"
				fill="rgba(255,255,255,0.09)" font-size="7" font-family="system-ui, sans-serif">B/A</text>
			<text x={svgX(75)} y={svgY(75) + 4} text-anchor="middle"
				fill="rgba(255,255,255,0.09)" font-size="7" font-family="system-ui, sans-serif">A/A</text>
			<text x={svgX(25)} y={svgY(25) + 4} text-anchor="middle"
				fill="rgba(255,255,255,0.09)" font-size="7" font-family="system-ui, sans-serif">B/B</text>
			<text x={svgX(75)} y={svgY(25) + 4} text-anchor="middle"
				fill="rgba(255,255,255,0.09)" font-size="7" font-family="system-ui, sans-serif">A/B</text>

			<!-- Scatter points -->
			{#each renderedPoints as pt}
				{@const inBrush = brushRect !== null && pt.x >= brushRect.x0 && pt.x <= brushRect.x1 && pt.y >= brushRect.y0 && pt.y <= brushRect.y1}
				<circle
					cx={svgX(pt.x)} cy={svgY(pt.y)}
					r="1.4"
					fill={inBrush ? '#fb923c' : '#94a3b8'}
					opacity={brushRect !== null && !inBrush ? 0.1 : 0.5}
				/>
			{/each}

			<!-- Brush overlay rect -->
			{#if brushRect !== null}
				<rect
					x={svgX(brushRect.x0)} y={svgY(brushRect.y1)}
					width={Math.max(0, svgX(brushRect.x1) - svgX(brushRect.x0))}
					height={Math.max(0, svgY(brushRect.y0) - svgY(brushRect.y1))}
					fill="#fb923c" opacity="0.07"
					stroke="#fb923c" stroke-width="1" stroke-opacity="0.4"
					pointer-events="none"
				/>
			{/if}

			<!-- X axis ticks -->
			{#each [0, 50, 100] as tick}
				<text x={svgX(tick)} y={SVG_H - 5}
					text-anchor="middle" fill="rgba(255,255,255,0.25)"
					font-size="8" font-family="system-ui, sans-serif">{tick}</text>
			{/each}

			<!-- Y axis ticks -->
			{#each [0, 50, 100] as tick}
				<text x={PAD_L - 3} y={svgY(tick) + 3}
					text-anchor="end" fill="rgba(255,255,255,0.25)"
					font-size="8" font-family="system-ui, sans-serif">{tick}</text>
			{/each}

			<!-- X axis label -->
			<text x={PAD_L + plotW / 2} y={SVG_H - 1}
				text-anchor="middle" fill="rgba(255,255,255,0.18)"
				font-size="6.5" font-family="system-ui, sans-serif">{xLabel}</text>

			<!-- Y axis label (rotated) -->
			<text
				x={6} y={PAD_T + plotH / 2}
				text-anchor="middle" fill="rgba(255,255,255,0.18)"
				font-size="6.5" font-family="system-ui, sans-serif"
				transform={`rotate(-90, 6, ${PAD_T + plotH / 2})`}
			>{yLabel}</text>
		</svg>
	{/if}
	</div>
</ChartFrame>

<style>
	.bvpanel {
		padding: 2px 0;
	}
	.bvpanel-subheader {
		display: flex;
		align-items: baseline;
		gap: 6px;
		margin-bottom: 4px;
		padding: 0 2px;
	}
	.bvpanel-count {
		font-size: 8px;
		color: #fb923c;
	}
	.bvpanel-hint {
		font-size: 8px;
		color: rgba(255,255,255,0.18);
		font-style: italic;
	}
	.bvpanel-picker {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-bottom: 4px;
		padding: 0 2px;
	}
	.picker-label {
		font-size: 8px;
		color: rgba(255,255,255,0.35);
		white-space: nowrap;
	}
	.picker-select {
		flex: 1;
		background: rgba(255,255,255,0.04);
		border: 1px solid rgba(255,255,255,0.12);
		border-radius: 3px;
		color: rgba(255,255,255,0.72);
		font-size: 9px;
		font-family: inherit;
		padding: 2px 4px;
		cursor: pointer;
		min-width: 0;
	}
	.picker-select:focus {
		outline: none;
		border-color: rgba(255,255,255,0.28);
	}
	.picker-select option {
		background: #1e293b;
		color: #e2e8f0;
	}
	.bvpanel-state {
		font-size: 9px;
		color: rgba(255,255,255,0.28);
		text-align: center;
		padding: 16px 0;
		font-style: italic;
	}
	.bvpanel-error { color: #f87171; }
	.bvpanel-empty-prompt {
		font-size: 9px;
		color: rgba(255,255,255,0.22);
		padding: 8px 2px 10px;
		line-height: 1.5;
		border: 1px dashed rgba(255,255,255,0.1);
		border-radius: 4px;
		padding: 10px 8px;
		margin: 2px 0 4px;
		font-style: italic;
	}
</style>
