<script lang="ts">
	import { loadDeptSummary } from '$lib/utils/deptSummaries';

	let {
		activeAnalysisId = '',
		selectedDept = null,
		territoryPrefix = '',
	}: {
		activeAnalysisId?: string;
		selectedDept?: string | null;
		territoryPrefix?: string;
	} = $props();

	const REFERENCE = [
		'environmental_risk', 'flood_risk', 'forest_health',
		'agri_potential', 'accessibility', 'territorial_scores',
	];

	// Analyses where higher score = worse outcome → rank ascending (lowest score = rank #1 = best)
	const RANK_ASCENDING = new Set([
		'environmental_risk', 'flood_risk', 'accessibility',
		'change_pressure', 'climate_vulnerability', 'service_deprivation', 'deforestation_dynamics',
	]);

	const SHORT_LABEL: Record<string, string> = {
		environmental_risk: 'Amb.',     flood_risk: 'Inund.',   forest_health: 'Forest.',
		agri_potential: 'Agri.',        accessibility: 'Acceso', territorial_scores: 'Comp.',
		climate_comfort: 'Clima',       change_pressure: 'Cambio', green_capital: 'Verde',
		service_deprivation: 'Serv.',   territorial_isolation: 'Aisla.', health_access: 'Salud',
		education_capital: 'Educ.',     education_flow: 'E.Flow', land_use: 'Suelo',
		carbon_stock: 'Carbono',        deforestation_dynamics: 'Defor.', productive_activity: 'Prod.',
		climate_vulnerability: 'C.Vul.', sociodemographic: 'Socio.',
	};

	const SVG_W = 260, SVG_H = 200;
	const PAD_T = 34, PAD_B = 14, PAD_L = 22, PAD_R = 8;
	const plotW = SVG_W - PAD_L - PAD_R;
	const plotH = SVG_H - PAD_T - PAD_B;

	type DeptEntry = { name: string; score: number; rank: number };
	type AnalysisCol = { analysisId: string; label: string; depts: DeptEntry[] };

	let rankings = $state<AnalysisCol[]>([]);
	let loading = $state(true);

	$effect(() => {
		const active = activeAnalysisId;
		const prefix = territoryPrefix;
		const ids = [...new Set([...REFERENCE, active])].filter(Boolean).slice(0, 7) as string[];
		loading = true;
		rankings = [];
		Promise.all(
			ids.map(id =>
				loadDeptSummary(id, prefix)
					.then(d => ({ id, d }))
					.catch(() => ({ id, d: null }))
			)
		).then(results => {
			rankings = results
				.filter(r => r.d?.departments?.length > 0)
				.map(({ id, d }) => ({
					analysisId: id,
					label: SHORT_LABEL[id] ?? id.slice(0, 6),
					depts: [...(d.departments as any[])]
						.sort((a: any, b: any) => RANK_ASCENDING.has(id)
							? a.avg_score - b.avg_score   // ascending: lowest risk = rank 1 = best
							: b.avg_score - a.avg_score)  // descending: highest potential = rank 1 = best
						.map((dept: any, i: number) => ({
							name: (dept.dpto ?? dept.distrito ?? '') as string,
							score: Number(dept.avg_score ?? 0),
							rank: i + 1,
						})),
				}));
			loading = false;
		});
	});

	const nCols = $derived(rankings.length);
	const totalDepts = $derived(rankings[0]?.depts.length ?? 0);

	const activeColIdx = $derived(rankings.findIndex(r => r.analysisId === activeAnalysisId));

	const selectedEntry = $derived(
		selectedDept && activeColIdx >= 0
			? (rankings[activeColIdx]?.depts.find(d => d.name === selectedDept) ?? null)
			: null
	);

	const allDeptNames = $derived.by(() => {
		const s = new Set<string>();
		for (const r of rankings) for (const d of r.depts) s.add(d.name);
		return [...s];
	});

	// Hover state
	let hoverDept = $state<string | null>(null);
	let hoverColIdx = $state<number | null>(null);

	const hoverInfo = $derived.by(() => {
		if (hoverDept === null || hoverColIdx === null) return null;
		const col = rankings[hoverColIdx];
		if (!col) return null;
		const entry = col.depts.find(d => d.name === hoverDept);
		if (!entry) return null;
		return { dept: hoverDept, label: col.label, score: entry.score, rank: entry.rank, total: col.depts.length };
	});

	function colX(i: number): number {
		return PAD_L + (nCols > 1 ? (i * plotW) / (nCols - 1) : plotW / 2);
	}

	// Rank 1 = top, rank N = bottom
	function rankY(rank: number): number {
		return PAD_T + ((rank - 1) / Math.max(totalDepts - 1, 1)) * plotH;
	}

	function deptPoints(name: string): string {
		const pts: string[] = [];
		rankings.forEach((col, i) => {
			const e = col.depts.find(d => d.name === name);
			if (e) pts.push(`${colX(i).toFixed(1)},${rankY(e.rank).toFixed(1)}`);
		});
		return pts.join(' ');
	}

	function handleMouseMove(e: MouseEvent) {
		const svg = e.currentTarget as SVGElement;
		const rect = svg.getBoundingClientRect();
		const scaleX = SVG_W / rect.width;
		const scaleY = SVG_H / rect.height;
		const mx = (e.clientX - rect.left) * scaleX;
		const my = (e.clientY - rect.top) * scaleY;

		if (mx < PAD_L - 4 || mx > PAD_L + plotW + 4 || my < PAD_T - 4 || my > PAD_T + plotH + 4) {
			hoverDept = null; hoverColIdx = null; return;
		}

		// Nearest column
		let nearestCol = 0, minDX = Infinity;
		for (let i = 0; i < nCols; i++) {
			const dx = Math.abs(colX(i) - mx);
			if (dx < minDX) { minDX = dx; nearestCol = i; }
		}

		// Nearest dept by rank Y distance
		const col = rankings[nearestCol];
		let nearestDept: string | null = null, minDY = Infinity;
		for (const d of col.depts) {
			const dy = Math.abs(rankY(d.rank) - my);
			if (dy < minDY) { minDY = dy; nearestDept = d.name; }
		}

		hoverColIdx = nearestCol;
		hoverDept = nearestDept;
	}

	function handleMouseLeave() {
		hoverDept = null;
		hoverColIdx = null;
	}
</script>

<div class="bump-panel">
	<div class="bump-header">
		<span class="bump-title">Perfil comparativo</span>
		{#if hoverInfo}
			<span class="bump-hover">{hoverInfo.dept} · {hoverInfo.label}: #{hoverInfo.rank}/{hoverInfo.total} ({hoverInfo.score.toFixed(1)})</span>
		{:else if selectedDept && selectedEntry}
			<span class="bump-rank">#{selectedEntry.rank}/{totalDepts} · {selectedEntry.score.toFixed(1)} · {selectedDept}</span>
		{:else if loading}
			<span class="bump-hint">cargando…</span>
		{:else}
			<span class="bump-hint">pasá el mouse para explorar</span>
		{/if}
	</div>

	{#if !loading && nCols >= 2}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<svg
			width="100%"
			viewBox="0 0 {SVG_W} {SVG_H}"
			preserveAspectRatio="xMidYMid meet"
			style="display: block; cursor: crosshair;"
			onmousemove={handleMouseMove}
			onmouseleave={handleMouseLeave}
		>
			<!-- Active column highlight -->
			{#if activeColIdx >= 0}
				<rect
					x={colX(activeColIdx) - 9} y={PAD_T - 2}
					width={18} height={plotH + 4}
					fill="rgba(167,139,250,0.08)" rx="2"
				/>
			{/if}

			<!-- Hover column highlight -->
			{#if hoverColIdx !== null && hoverColIdx !== activeColIdx}
				<rect
					x={colX(hoverColIdx) - 9} y={PAD_T - 2}
					width={18} height={plotH + 4}
					fill="rgba(255,255,255,0.04)" rx="2"
				/>
			{/if}

			<!-- Y axis labels: #1 top (mejor), #N bottom (peor) -->
			<text x={PAD_L - 3} y={rankY(1) + 3} text-anchor="end"
				fill="rgba(255,255,255,0.22)" font-size="7" font-family="system-ui, sans-serif">#1</text>
			<text x={PAD_L - 3} y={rankY(totalDepts) + 3} text-anchor="end"
				fill="rgba(255,255,255,0.22)" font-size="7" font-family="system-ui, sans-serif">#{totalDepts}</text>

			<!-- Grey context lines -->
			{#each allDeptNames as name}
				{#if name !== selectedDept && name !== hoverDept}
					<polyline points={deptPoints(name)} fill="none"
						stroke="#94a3b8" stroke-width="1" opacity="0.14" stroke-linejoin="round" />
				{/if}
			{/each}

			<!-- Hovered dept line (not selected) -->
			{#if hoverDept && hoverDept !== selectedDept}
				<polyline points={deptPoints(hoverDept)} fill="none"
					stroke="#e2e8f0" stroke-width="1.5" opacity="0.75" stroke-linejoin="round" />
				{#each rankings as col, i}
					{@const entry = col.depts.find(d => d.name === hoverDept)}
					{#if entry}
						<circle cx={colX(i)} cy={rankY(entry.rank)} r="2.5"
							fill="#e2e8f0" opacity="0.75" />
					{/if}
				{/each}
			{/if}

			<!-- Selected dept line -->
			{#if selectedDept}
				<polyline points={deptPoints(selectedDept)} fill="none"
					stroke="#a78bfa" stroke-width="2" opacity="0.9" stroke-linejoin="round" />
				{#each rankings as col, i}
					{@const entry = col.depts.find(d => d.name === selectedDept)}
					{#if entry}
						<circle cx={colX(i)} cy={rankY(entry.rank)} r="2.5"
							fill="#a78bfa" opacity="0.9" />
					{/if}
				{/each}
			{/if}

			<!-- Column labels -->
			{#each rankings as col, i}
				<text
					x={colX(i)} y={PAD_T - 6}
					text-anchor="middle"
					fill={col.analysisId === activeAnalysisId
						? '#a78bfa'
						: (i === hoverColIdx ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.28)')}
					font-size="6.5"
					font-weight={col.analysisId === activeAnalysisId ? '700' : '400'}
					font-family="system-ui, sans-serif"
				>{col.label}</text>
			{/each}

			<!-- Bottom axis: rank label -->
			<text x={PAD_L + plotW / 2} y={SVG_H - 2}
				text-anchor="middle" fill="rgba(255,255,255,0.18)"
				font-size="6.5" font-family="system-ui, sans-serif">posición relativa (#1 = mejor)</text>
		</svg>
		<div class="bump-note">
			#1 = mejor posición siempre · En <em>riesgo/aislamiento</em> (Inund., Amb., Acceso): #1 = menos expuesto · En <em>potencial</em> (resto): #1 = mayor valor
		</div>
	{:else if !loading}
		<div class="bump-state">sin datos comparables disponibles</div>
	{/if}
</div>

<style>
	.bump-panel {
		margin: 8px 0 4px;
		padding: 6px 0 2px;
		border-top: 1px solid rgba(255,255,255,0.1);
	}
	.bump-header {
		display: flex;
		align-items: baseline;
		gap: 6px;
		margin-bottom: 2px;
		padding: 0 2px;
		min-height: 14px;
	}
	.bump-title {
		font-size: 9px;
		font-weight: 700;
		color: rgba(255,255,255,0.45);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		white-space: nowrap;
	}
	.bump-rank {
		font-size: 8px;
		color: #a78bfa;
	}
	.bump-hover {
		font-size: 8px;
		color: rgba(255,255,255,0.7);
	}
	.bump-hint {
		font-size: 8px;
		color: rgba(255,255,255,0.18);
		font-style: italic;
	}
	.bump-state {
		font-size: 9px;
		color: rgba(255,255,255,0.28);
		text-align: center;
		padding: 12px 0;
		font-style: italic;
	}
	.bump-note {
		font-size: 7.5px;
		color: rgba(255,255,255,0.22);
		line-height: 1.5;
		padding: 3px 2px 2px;
		border-top: 1px solid rgba(255,255,255,0.06);
		margin-top: 1px;
	}
	.bump-note em {
		font-style: normal;
		color: rgba(255,255,255,0.38);
	}
</style>
