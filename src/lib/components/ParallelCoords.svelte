<script lang="ts">
	let {
		data = new Map() as Map<string, Record<string, any>>,
		variables = [] as { col: string; labelKey: string; unit?: string }[],
		onBrushSelect = (_h3s: string[]) => {},
	}: {
		data: Map<string, Record<string, any>>;
		variables: { col: string; labelKey: string; unit?: string }[];
		onBrushSelect?: (h3s: string[]) => void;
	} = $props();

	const SVG_W = 260, SVG_H = 180;
	const PAD_T = 28, PAD_B = 12, PAD_L = 14, PAD_R = 14;
	const plotW = SVG_W - PAD_L - PAD_R;
	const plotH = SVG_H - PAD_T - PAD_B;
	const AXIS_HIT = 18;
	const CLEAR_R  = 6; // radius of the per-axis × button (SVG units)

	const SHORT: Record<string, string> = {
		flood_risk_score: 'Riesgo',  score: 'Score',
		jrc_occurrence: 'Ocur.',     jrc_recurrence: 'Recur.',
		jrc_seasonality: 'Estac.',   flood_extent_pct: 'Ext.%',
		travel_min_capital: 'T.Cap', travel_min_cabecera: 'T.Cab',
		dist_nearest_hospital_km: 'Hosp.', dist_nearest_secundaria_km: 'Esc.',
		dist_primary_m: 'Ruta',
		c_ndvi_trend: 'NDVI', c_loss_ratio: 'Pérd.', c_fire: 'Fuego',
		c_gpp: 'GPP',  c_et: 'ET',
		c_soc: 'SOC',  c_ph_optimal: 'pH', c_clay: 'Arcil.',
		c_precipitation: 'Lluv.', c_gdd: 'GDD', c_slope: 'Pend.',
	};

	function shortLabel(col: string): string {
		if (SHORT[col]) return SHORT[col];
		const c = col.startsWith('c_') ? col.slice(2) : col;
		return c.slice(0, 6);
	}

	const numericVars = $derived(
		variables.filter(v =>
			v.col !== 'type' && !v.col.endsWith('_label') &&
			v.col !== 'pca_1' && v.col !== 'pca_2'
		)
	);
	const nAxes = $derived(numericVars.length);

	type Point = { h3: string; vals: Record<string, number> };

	const allPoints = $derived.by(() => {
		if (numericVars.length < 2 || data.size === 0) return [] as Point[];
		const pts: Point[] = [];
		for (const [h3, row] of data) {
			const vals: Record<string, number> = {};
			let valid = true;
			for (const v of numericVars) {
				const x = Number(row[v.col]);
				if (!isFinite(x)) { valid = false; break; }
				vals[v.col] = x;
			}
			if (valid) pts.push({ h3, vals });
		}
		return pts;
	});

	const renderedPoints = $derived.by(() => {
		const MAX = 1500;
		if (allPoints.length <= MAX) return allPoints;
		const stride = Math.ceil(allPoints.length / MAX);
		return allPoints.filter((_, i) => i % stride === 0);
	});

	const extents = $derived.by(() => {
		const ext: Record<string, [number, number]> = {};
		for (const v of numericVars) {
			let lo = Infinity, hi = -Infinity;
			for (const pt of allPoints) {
				const x = pt.vals[v.col];
				if (x < lo) lo = x;
				if (x > hi) hi = x;
			}
			ext[v.col] = [lo === Infinity ? 0 : lo, hi === -Infinity ? 100 : hi];
		}
		return ext;
	});

	function axisX(i: number): number {
		return PAD_L + (nAxes > 1 ? (i * plotW) / (nAxes - 1) : plotW / 2);
	}

	function valueY(col: string, val: number): number {
		const [lo, hi] = extents[col] ?? [0, 100];
		return PAD_T + (1 - (val - lo) / Math.max(hi - lo, 1)) * plotH;
	}

	// Y of the × button for a given axis (just above the brush top, clamped inside plot)
	function clearBtnY(col: string): number {
		const [, bhi] = brushes.get(col) ?? [0, 0];
		const top = valueY(col, bhi);
		return Math.max(PAD_T + CLEAR_R + 1, top - CLEAR_R - 2);
	}

	let brushes = $state<Map<string, [number, number]>>(new Map());
	let selectedCount = $state(0);
	let hoverIdx   = $state<number | null>(null);
	let hoverClear = $state<number | null>(null); // index of axis whose × is hovered
	let dragging   = $state(false);

	function isSelected(pt: Point): boolean {
		for (const [col, [lo, hi]] of brushes) {
			const v = pt.vals[col];
			if (v === undefined || v < lo || v > hi) return false;
		}
		return true;
	}

	function fireBrush() {
		if (brushes.size === 0) { selectedCount = 0; onBrushSelect([]); return; }
		const h3s: string[] = [];
		for (const pt of allPoints) if (isSelected(pt)) h3s.push(pt.h3);
		selectedCount = h3s.length;
		onBrushSelect(h3s);
	}

	function clearAll() {
		brushes = new Map(); selectedCount = 0; onBrushSelect([]);
	}

	function clearAxis(col: string) {
		const nb = new Map(brushes); nb.delete(col); brushes = nb; fireBrush();
	}

	function svgXY(e: MouseEvent, svgEl: SVGElement) {
		const r = svgEl.getBoundingClientRect();
		return {
			x: (e.clientX - r.left) * (SVG_W / r.width),
			y: (e.clientY - r.top)  * (SVG_H / r.height),
			scaleY: SVG_H / r.height,
			top: r.top,
		};
	}

	function nearestAxis(svgX: number) {
		let idx = 0, minDx = Infinity;
		for (let i = 0; i < nAxes; i++) {
			const dx = Math.abs(axisX(i) - svgX);
			if (dx < minDx) { minDx = dx; idx = i; }
		}
		return { idx, dx: minDx };
	}

	// Returns index of axis whose × button is hit, or -1
	function hitClearBtn(svgX: number, svgY: number): number {
		for (let i = 0; i < nAxes; i++) {
			const col = numericVars[i].col;
			if (!brushes.has(col)) continue;
			const cx = axisX(i), cy = clearBtnY(col);
			if (Math.hypot(svgX - cx, svgY - cy) <= CLEAR_R + 2) return i;
		}
		return -1;
	}

	function handleMouseMove(e: MouseEvent) {
		if (dragging) return;
		const svgEl = e.currentTarget as SVGElement;
		const { x, y } = svgXY(e, svgEl);

		// Check × buttons first
		const ci = hitClearBtn(x, y);
		if (ci >= 0) { hoverClear = ci; hoverIdx = null; return; }
		hoverClear = null;

		if (y < PAD_T - 4 || y > PAD_T + plotH + 4) { hoverIdx = null; return; }
		const { idx, dx } = nearestAxis(x);
		hoverIdx = dx <= AXIS_HIT ? idx : null;
	}

	function handleMouseLeave() {
		if (!dragging) { hoverIdx = null; hoverClear = null; }
	}

	function startBrush(e: MouseEvent) {
		if (nAxes < 2 || allPoints.length === 0) return;
		const svgEl = e.currentTarget as SVGElement;
		const { x, y, scaleY, top } = svgXY(e, svgEl);

		// × button hit → clear that axis
		const ci = hitClearBtn(x, y);
		if (ci >= 0) {
			e.preventDefault();
			clearAxis(numericVars[ci].col);
			return;
		}

		if (y < PAD_T - 4 || y > PAD_T + plotH + 4) return;
		const { idx, dx } = nearestAxis(x);
		if (dx > AXIS_HIT) return;

		e.preventDefault();
		dragging = true;

		const col = numericVars[idx].col;
		const [lo, hi] = extents[col] ?? [0, 100];
		const startClientY = e.clientY;

		function clientYToVal(clientY: number): number {
			const sy = (clientY - top) * scaleY;
			return lo + (1 - (sy - PAD_T) / plotH) * (hi - lo);
		}

		const startVal = clientYToVal(startClientY);

		const onMove = (ev: MouseEvent) => {
			const endVal = clientYToVal(ev.clientY);
			const nb = new Map(brushes);
			nb.set(col, [Math.min(startVal, endVal), Math.max(startVal, endVal)]);
			brushes = nb;
		};

		const onUp = (ev: MouseEvent) => {
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
			dragging = false;
			if (Math.abs(ev.clientY - startClientY) < 5) {
				// plain click → clear that axis
				clearAxis(col);
			} else {
				fireBrush();
			}
		};

		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
	}

	$effect(() => {
		const cols = variables.map(v => v.col).join(',');
		void cols; brushes = new Map(); selectedCount = 0;
	});

	const svgCursor = $derived(
		hoverClear !== null ? 'pointer' :
		(hoverIdx !== null || dragging) ? 'ns-resize' : 'default'
	);
</script>

<div class="pc-panel">
	<div class="pc-header">
		<span class="pc-title">Variables</span>
		{#if selectedCount > 0}
			<span class="pc-count">{selectedCount.toLocaleString()} hex</span>
			<button class="pc-clear-btn" onclick={clearAll}>× limpiar todo</button>
		{:else if brushes.size > 0}
			<span class="pc-count">0 hex en intersección</span>
			<button class="pc-clear-btn" onclick={clearAll}>× limpiar todo</button>
		{:else if nAxes >= 2 && allPoints.length > 0}
			<span class="pc-hint">pasá el mouse sobre una variable y arrastrá</span>
		{:else}
			<span class="pc-hint">cargando…</span>
		{/if}
	</div>

	{#if nAxes >= 2 && allPoints.length > 0}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<svg
			width="100%"
			viewBox="0 0 {SVG_W} {SVG_H}"
			preserveAspectRatio="xMidYMid meet"
			style="display:block; cursor:{svgCursor}; user-select:none;"
			onmousedown={startBrush}
			onmousemove={handleMouseMove}
			onmouseleave={handleMouseLeave}
		>
			<!-- Context lines -->
			{#each renderedPoints as pt}
				{@const sel = brushes.size > 0 && isSelected(pt)}
				<polyline
					points={numericVars.map((v, i) =>
						`${axisX(i).toFixed(1)},${valueY(v.col, pt.vals[v.col]).toFixed(1)}`
					).join(' ')}
					fill="none"
					stroke={brushes.size > 0 ? (sel ? '#22d3ee' : '#94a3b8') : '#94a3b8'}
					stroke-width={sel ? 1.2 : 0.6}
					opacity={brushes.size > 0 ? (sel ? 0.7 : 0.04) : 0.12}
					pointer-events="none"
				/>
			{/each}

			{#each numericVars as v, i}
				{@const isHov  = hoverIdx === i}
				{@const isCHov = hoverClear === i}
				{@const hasBrush = brushes.has(v.col)}

				<!-- hover / active zone background -->
				{#if isHov || hasBrush}
					<rect
						x={axisX(i) - AXIS_HIT} y={PAD_T}
						width={AXIS_HIT * 2} height={plotH}
						fill={hasBrush ? 'rgba(34,211,238,0.05)' : 'rgba(255,255,255,0.04)'}
						rx="2" pointer-events="none"
					/>
				{/if}

				<!-- axis line -->
				<line
					x1={axisX(i)} x2={axisX(i)} y1={PAD_T} y2={PAD_T + plotH}
					stroke={hasBrush ? '#22d3ee' : (isHov ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.22)')}
					stroke-width={isHov || hasBrush ? 2 : 1}
					pointer-events="none"
				/>

				<!-- brush range rect -->
				{#if hasBrush}
					{@const [blo, bhi] = brushes.get(v.col)!}
					<rect
						x={axisX(i) - 7} y={valueY(v.col, bhi)}
						width={14}
						height={Math.max(3, valueY(v.col, blo) - valueY(v.col, bhi))}
						fill="#22d3ee" opacity="0.22"
						stroke="#22d3ee" stroke-width="1" stroke-opacity="0.8"
						pointer-events="none"
					/>

					<!-- × clear button for this axis -->
					{@const cy = clearBtnY(v.col)}
					<circle
						cx={axisX(i)} cy={cy} r={CLEAR_R}
						fill={isCHov ? 'rgba(248,113,113,0.3)' : 'rgba(34,211,238,0.18)'}
						stroke={isCHov ? '#f87171' : '#22d3ee'}
						stroke-width="0.8"
						pointer-events="none"
					/>
					<text
						x={axisX(i)} y={cy + 2.5}
						text-anchor="middle" font-size="7"
						fill={isCHov ? '#f87171' : '#22d3ee'}
						font-family="system-ui, sans-serif"
						pointer-events="none"
					>×</text>
				{/if}

				<!-- axis label -->
				<text
					x={axisX(i)} y={PAD_T - 5}
					text-anchor="start"
					fill={hasBrush ? '#22d3ee' : (isHov ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.38)')}
					font-size="6.5" font-family="system-ui, sans-serif"
					font-weight={hasBrush || isHov ? '600' : '400'}
					transform={`rotate(-35, ${axisX(i)}, ${PAD_T - 5})`}
					pointer-events="none"
				>{shortLabel(v.col)}</text>

				<!-- max / min ticks -->
				<text x={axisX(i) - 2} y={PAD_T + 3.5} text-anchor="end"
					fill="rgba(255,255,255,0.18)" font-size="5" font-family="system-ui, sans-serif"
					pointer-events="none">{extents[v.col]?.[1].toFixed(0)}</text>
				<text x={axisX(i) - 2} y={PAD_T + plotH + 1.5} text-anchor="end"
					fill="rgba(255,255,255,0.18)" font-size="5" font-family="system-ui, sans-serif"
					pointer-events="none">{extents[v.col]?.[0].toFixed(0)}</text>
			{/each}
		</svg>
		<div class="pc-note">
			Pasá el mouse sobre una variable y <em>arrastrá para filtrar</em> por rango · El <em>×</em> sobre cada filtro activo lo limpia individualmente · "Limpiar todo" quita todos los filtros
		</div>
	{/if}
</div>

<style>
	.pc-panel {
		margin: 8px 0 4px;
		padding: 6px 0 2px;
		border-top: 1px solid rgba(255,255,255,0.1);
	}
	.pc-header {
		display: flex;
		align-items: baseline;
		gap: 6px;
		margin-bottom: 2px;
		padding: 0 2px;
		min-height: 14px;
		flex-wrap: wrap;
	}
	.pc-title {
		font-size: 9px;
		font-weight: 700;
		color: rgba(255,255,255,0.45);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		white-space: nowrap;
	}
	.pc-count { font-size: 8px; color: #22d3ee; }
	.pc-hint  { font-size: 8px; color: rgba(255,255,255,0.18); font-style: italic; }
	.pc-clear-btn {
		font-size: 8px;
		color: rgba(255,255,255,0.32);
		background: none; border: none; cursor: pointer; padding: 0; line-height: 1;
	}
	.pc-clear-btn:hover { color: #f87171; }
	.pc-note {
		font-size: 7.5px;
		color: rgba(255,255,255,0.22);
		line-height: 1.5;
		padding: 3px 2px 2px;
		border-top: 1px solid rgba(255,255,255,0.06);
		margin-top: 1px;
	}
	.pc-note em { font-style: normal; color: rgba(255,255,255,0.42); }
</style>
