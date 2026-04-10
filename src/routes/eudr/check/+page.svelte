<script lang="ts">
	import { i18n } from '$lib/stores/i18n.svelte';
	import EudrMap from '$lib/components/EudrMap.svelte';

	let mapComponent: EudrMap;

	// Input state
	let latInput = $state('');
	let lonInput = $state('');
	let loading = $state(false);
	let error = $state('');

	// Result state
	interface EudrResult {
		id: string;
		lat: number;
		lon: number;
		h3_cell: string;
		province: string;
		forest_cover_2020_pct: number | null;
		forest_cover_current_pct: number | null;
		loss_post_2020_pct: number | null;
		fire_post_2020_pct: number | null;
		risk_score: number | null;
		risk_level: string;
		deforestation_post_2020: boolean;
		eudr_assessment: string;
	}

	let result: EudrResult | null = $state(null);
	let remainingChecks: number | null = $state(null);

	function getRiskColor(level: string): string {
		switch (level) {
			case 'critical': return '#991b1b';
			case 'high': return '#ef4444';
			case 'medium': return '#f59e0b';
			case 'low': return '#22c55e';
			default: return '#6b7280';
		}
	}

	function getAssessmentColor(assessment: string): string {
		switch (assessment) {
			case 'NON_COMPLIANT': return '#ef4444';
			case 'HIGH_RISK': return '#f59e0b';
			case 'MEDIUM_RISK': return '#eab308';
			case 'LOW_RISK': return '#22c55e';
			default: return '#6b7280';
		}
	}

	function getAssessmentLabel(assessment: string): string {
		const labels: Record<string, Record<string, string>> = {
			NON_COMPLIANT: { es: 'NO CUMPLE', en: 'NON-COMPLIANT' },
			HIGH_RISK: { es: 'RIESGO ALTO', en: 'HIGH RISK' },
			MEDIUM_RISK: { es: 'RIESGO MEDIO', en: 'MEDIUM RISK' },
			LOW_RISK: { es: 'RIESGO BAJO', en: 'LOW RISK' },
			OUTSIDE_COVERAGE: { es: 'FUERA DE COBERTURA', en: 'OUTSIDE COVERAGE' },
		};
		return labels[assessment]?.[i18n.locale] || assessment;
	}

	async function checkCoordinates(lat: number, lon: number) {
		loading = true;
		error = '';
		result = null;

		try {
			const res = await fetch('/api/eudr/check', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					coordinates: [{ lat, lon, id: 'manual' }],
				}),
			});

			const text = await res.text();
			if (!text) {
				throw new Error(`Empty response (HTTP ${res.status})`);
			}

			let data: any;
			try {
				data = JSON.parse(text);
			} catch {
				throw new Error(`Invalid response (HTTP ${res.status})`);
			}

			if (!res.ok) {
				throw new Error(data.error || `HTTP ${res.status}`);
			}

			if (data.meta?.remaining_checks !== undefined) {
				remainingChecks = data.meta.remaining_checks;
			}
			if (data.results && data.results.length > 0) {
				result = data.results[0];
			}
		} catch (e: any) {
			error = e.message || 'Error checking coordinates';
		} finally {
			loading = false;
		}
	}

	function handleSubmit() {
		const lat = parseFloat(latInput);
		const lon = parseFloat(lonInput);

		if (isNaN(lat) || isNaN(lon)) {
			error = i18n.t('eudr.check.error_invalid');
			return;
		}

		if (lat < -35 || lat > -21 || lon < -70 || lon > -53) {
			error = i18n.t('eudr.check.error_bounds');
			return;
		}

		mapComponent?.setMarker(lat, lon);
		mapComponent?.flyTo(lat, lon, 9);
		checkCoordinates(lat, lon);
	}

	function handleMapClick(lat: number, lon: number, h3index: string) {
		latInput = lat.toFixed(6);
		lonInput = lon.toFixed(6);
		checkCoordinates(lat, lon);
	}

	function handlePaste() {
		// Support pasting "lat, lon" format
		setTimeout(() => {
			const val = latInput.trim();
			if (val.includes(',')) {
				const parts = val.split(',').map(s => s.trim());
				if (parts.length === 2 && !isNaN(parseFloat(parts[0])) && !isNaN(parseFloat(parts[1]))) {
					latInput = parts[0];
					lonInput = parts[1];
				}
			}
		}, 50);
	}

	function tryExample() {
		latInput = '-27.36';
		lonInput = '-55.90';
		handleSubmit();
	}

	function fmt(v: number | null, decimals = 1): string {
		if (v === null || v === undefined) return '--';
		return v.toFixed(decimals);
	}
</script>

<svelte:head>
	<title>EUDR Check &mdash; Spatia</title>
	<meta name="description" content={i18n.t('eudr.check.empty_desc')} />
	<meta property="og:title" content="EUDR Check — Spatia" />
	<meta property="og:description" content={i18n.t('eudr.check.empty_desc')} />
	<meta property="og:image" content="https://spatia.ar/og-image.png" />
	<meta property="og:url" content="https://spatia.ar/eudr/check" />
	<meta property="og:type" content="website" />
</svelte:head>

<div class="py-6">
	<h1 class="text-xl font-bold text-white mb-6">{i18n.t('eudr.check.title')}</h1>

	<div class="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6 lg:h-[calc(100vh-200px)]" style="min-height: 500px;">
		<!-- Map -->
		<div class="relative rounded-lg overflow-hidden border border-border min-h-[350px] lg:min-h-0">
			<EudrMap bind:this={mapComponent} onCellClick={handleMapClick} />
			<div class="absolute bottom-3 left-3 bg-black/70 backdrop-blur-sm px-3 py-1.5 rounded text-[10px] text-white/50">
				{i18n.t('eudr.check.click_map')}
			</div>
		</div>

		<!-- Input + Results Panel -->
		<div class="flex flex-col gap-4 overflow-y-auto">
			<!-- Coordinate Input -->
			<div class="border border-border rounded-lg p-4 bg-white/[0.02]">
				<h3 class="text-sm font-bold text-white mb-3">{i18n.t('eudr.check.input_title')}</h3>
				<div class="grid grid-cols-2 gap-2 mb-3">
					<div>
						<label class="text-[10px] text-white/40 uppercase">Lat</label>
						<input type="text" inputmode="decimal" bind:value={latInput} onpaste={handlePaste}
							placeholder="-27.5"
							class="w-full bg-white/5 border border-border rounded px-3 py-2 text-[13px] text-white placeholder-white/20 focus:outline-none focus:border-accent" />
					</div>
					<div>
						<label class="text-[10px] text-white/40 uppercase">Lon</label>
						<input type="text" inputmode="decimal" bind:value={lonInput}
							placeholder="-60.5"
							class="w-full bg-white/5 border border-border rounded px-3 py-2 text-[13px] text-white placeholder-white/20 focus:outline-none focus:border-accent" />
					</div>
				</div>
				<button onclick={handleSubmit} disabled={loading}
					class="w-full py-2 bg-accent text-black font-bold text-[13px] rounded-lg hover:bg-accent/80 transition-colors disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed flex items-center justify-center gap-2">
					{#if loading}
						<svg class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
							<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-linecap="round" class="opacity-25"></circle>
							<path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="3" stroke-linecap="round"></path>
						</svg>
					{/if}
					{loading ? i18n.t('eudr.check.checking') : i18n.t('eudr.check.check_btn')}
				</button>
				<button onclick={tryExample} class="mt-1 w-full text-[11px] text-white/30 hover:text-white/60 transition-colors py-1 bg-transparent border-0 cursor-pointer">
					{i18n.t('eudr.check.try_example')} →
				</button>

				{#if error}
					<p class="mt-2 text-[12px] text-red-400">{error}</p>
				{/if}

				{#if remainingChecks !== null && remainingChecks <= 20}
					<div class="mt-2 text-[11px] text-center {remainingChecks === 0 ? 'text-red-400' : 'text-white/40'}">
						{#if remainingChecks === 0}
							{i18n.t('eudr.check.limit_reached')} &mdash;
							<button onclick={() => navigator.clipboard.writeText('contacto@spatia.ar')} class="text-accent hover:text-white underline cursor-pointer bg-transparent border-0 p-0 font-inherit text-[11px]">{i18n.t('eudr.check.limit_cta')}</button>
						{:else}
							{remainingChecks} {i18n.t('eudr.check.remaining')}
						{/if}
					</div>
				{/if}
			</div>

			<!-- Loading skeleton -->
			{#if loading && !result}
				<div class="border border-border rounded-lg p-4 bg-white/[0.02] flex-1 space-y-3">
					<div class="h-4 w-24 bg-white/5 rounded animate-pulse"></div>
					<div class="h-8 w-full bg-white/5 rounded animate-pulse"></div>
					<div class="grid grid-cols-2 gap-3">
						<div class="h-16 bg-white/5 rounded animate-pulse"></div>
						<div class="h-16 bg-white/5 rounded animate-pulse"></div>
						<div class="h-16 bg-white/5 rounded animate-pulse"></div>
						<div class="h-16 bg-white/5 rounded animate-pulse"></div>
					</div>
					<div class="space-y-2 mt-2">
						<div class="h-3 w-full bg-white/5 rounded animate-pulse"></div>
						<div class="h-3 w-3/4 bg-white/5 rounded animate-pulse"></div>
					</div>
				</div>
			{/if}

			<!-- Empty state -->
			{#if !result && !loading}
				<div class="border border-border/50 rounded-lg p-6 bg-white/[0.01] flex-1 flex flex-col items-center justify-center text-center gap-3">
					<svg class="w-10 h-10 text-white/20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
						<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
					</svg>
					<h3 class="text-sm font-bold text-white/50">{i18n.t('eudr.check.empty_title')}</h3>
					<p class="text-[12px] text-white/30 max-w-[260px]">{i18n.t('eudr.check.empty_desc')}</p>
					<button onclick={tryExample}
						class="mt-2 px-4 py-1.5 border border-white/20 text-white/60 text-[12px] font-semibold rounded-lg hover:border-white/40 hover:text-white transition-colors cursor-pointer">
						{i18n.t('eudr.check.try_example')}
					</button>
				</div>
			{/if}

			<!-- Results -->
			{#if result}
				<div class="border border-border rounded-lg p-4 bg-white/[0.02] flex-1">
					<!-- Assessment Badge -->
					<div class="flex items-center justify-between mb-4">
						<h3 class="text-sm font-bold text-white">{i18n.t('eudr.check.result_title')}</h3>
						<span class="text-[11px] font-bold uppercase tracking-wider px-3 py-1 rounded-full"
							style="background: {getAssessmentColor(result.eudr_assessment)}20; color: {getAssessmentColor(result.eudr_assessment)};">
							{getAssessmentLabel(result.eudr_assessment)}
						</span>
					</div>

					<!-- Risk Score Gauge -->
					{#if result.risk_score !== null}
						<div class="mb-4">
							<div class="flex items-center justify-between text-[11px] text-white/50 mb-1">
								<span>{i18n.t('eudr.check.risk_score')}</span>
								<span class="text-lg font-bold" style="color: {getRiskColor(result.risk_level)};">
									{fmt(result.risk_score, 0)}
								</span>
							</div>
							<div class="w-full h-2 bg-white/5 rounded-full overflow-hidden">
								<div class="h-full rounded-full transition-all"
									style="width: {result.risk_score}%; background: {getRiskColor(result.risk_level)};"></div>
							</div>
							<div class="flex justify-between text-[9px] text-white/30 mt-0.5">
								<span>0</span><span>25</span><span>50</span><span>75</span><span>100</span>
							</div>
						</div>
					{/if}

					<!-- Metrics Grid -->
					<div class="grid grid-cols-2 gap-3 mb-4">
						<div class="bg-white/[0.03] rounded p-3">
							<div class="text-[10px] text-white/40 uppercase mb-1">{i18n.t('eudr.check.forest_2020')}</div>
							<div class="text-lg font-bold text-white">{fmt(result.forest_cover_2020_pct)}%</div>
						</div>
						<div class="bg-white/[0.03] rounded p-3">
							<div class="text-[10px] text-white/40 uppercase mb-1">{i18n.t('eudr.check.forest_current')}</div>
							<div class="text-lg font-bold text-white">{fmt(result.forest_cover_current_pct)}%</div>
						</div>
						<div class="bg-white/[0.03] rounded p-3">
							<div class="text-[10px] text-white/40 uppercase mb-1">{i18n.t('eudr.check.loss_post_2020')}</div>
							<div class="text-lg font-bold" style="color: {(result.loss_post_2020_pct ?? 0) > 0 ? '#ef4444' : '#22c55e'};">
								{fmt(result.loss_post_2020_pct)}%
							</div>
						</div>
						<div class="bg-white/[0.03] rounded p-3">
							<div class="text-[10px] text-white/40 uppercase mb-1">{i18n.t('eudr.check.fire_post_2020')}</div>
							<div class="text-lg font-bold" style="color: {(result.fire_post_2020_pct ?? 0) > 0 ? '#f59e0b' : '#22c55e'};">
								{fmt(result.fire_post_2020_pct)}%
							</div>
						</div>
					</div>

					<!-- Details -->
					<div class="space-y-2 text-[11px] text-white/50">
						<div class="flex justify-between">
							<span>H3 cell</span>
							<span class="font-mono text-white/70">{result.h3_cell}</span>
						</div>
						<div class="flex justify-between">
							<span>{i18n.t('eudr.check.province')}</span>
							<span class="text-white/70">{result.province || '--'}</span>
						</div>
						<div class="flex justify-between">
							<span>{i18n.t('eudr.check.coordinates')}</span>
							<span class="font-mono text-white/70">{result.lat.toFixed(4)}, {result.lon.toFixed(4)}</span>
						</div>
					</div>

					<!-- Disclaimer -->
					<div class="mt-4 pt-3 border-t border-border text-[10px] text-white/25 leading-relaxed">
						{i18n.t('eudr.disclaimer_short')}
					</div>
				</div>
			{/if}
		</div>
	</div>
</div>
