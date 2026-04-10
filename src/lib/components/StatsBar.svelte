<script lang="ts">
	import type { HexStore } from '$lib/stores/hex.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let { hexStore, bottom = '0px' }: { hexStore: HexStore; bottom?: string } = $props();

	const layer = $derived(hexStore.activeLayer);
	const isCategorical = $derived(layer?.colorScale === 'categorical');
	const isTemporal = $derived(!!layer?.temporal);
	const mode = $derived(hexStore.temporalMode);
	const isDelta = $derived(isTemporal && mode === 'delta');

	const primaryLabel = $derived.by(() => {
		if (!layer?.primaryVariable) return '';
		const v = layer.variables.find((x) => x.col === layer.primaryVariable);
		return v?.labelKey ? i18n.t(v.labelKey) : layer.primaryVariable;
	});

	let cachedVersion = -1;
	let cachedStats: {
		count: number;
		avg: number;
		max: number;
		dominantType?: { label: string; pct: number };
	} | null = null;

	const stats = $derived.by(() => {
		const v = hexStore.dataVersion;
		if (v === cachedVersion && cachedStats) return cachedStats;
		cachedVersion = v;

		const entries = hexStore.choroplethEntries;
		if (entries.length === 0) {
			cachedStats = null;
			return null;
		}

		if (isCategorical) {
			const counts = new Map<string, number>();
			for (const e of entries) {
				const raw = e.properties.type_label as unknown as string | undefined;
				const lbl = raw ?? `Tipo ${e.properties.type ?? '?'}`;
				counts.set(lbl, (counts.get(lbl) ?? 0) + 1);
			}
			let topLabel = '';
			let topN = 0;
			for (const [k, n] of counts) {
				if (n > topN) {
					topN = n;
					topLabel = k;
				}
			}
			cachedStats = {
				count: entries.length,
				avg: 0,
				max: 0,
				dominantType: { label: topLabel, pct: (topN / entries.length) * 100 }
			};
			return cachedStats;
		}

		let max = -Infinity;
		let sum = 0;
		for (const e of entries) {
			if (e.value > max) max = e.value;
			sum += e.value;
		}
		cachedStats = { count: entries.length, avg: sum / entries.length, max };
		return cachedStats;
	});

	function fmt(n: number, signed = false): string {
		if (!Number.isFinite(n)) return '—';
		const sign = signed && n > 0 ? '+' : '';
		const abs = Math.abs(n);
		if (abs >= 1_000_000) return sign + (n / 1_000_000).toFixed(1) + 'M';
		if (abs >= 1_000) return sign + (n / 1_000).toFixed(1) + 'K';
		if (n % 1 === 0) return sign + n.toString();
		return sign + n.toFixed(2);
	}
</script>

{#if stats && layer}
	<div
		class="absolute left-0 right-0 z-40 transition-all duration-200 pointer-events-none"
		style="bottom: {bottom}"
	>
		<div
			class="bg-panel/85 border-t border-border backdrop-blur-sm px-3 md:px-6 py-2.5 flex items-center justify-center gap-4 md:gap-8 pointer-events-auto"
		>
			<div class="flex items-baseline gap-1.5">
				<span class="text-xl font-bold font-mono text-accent">{fmt(stats.count)}</span>
				<span class="text-[10px] text-text-dim uppercase">{i18n.t('stats.hexagons')}</span>
			</div>

			{#if isCategorical && stats.dominantType}
				<div class="w-px h-6 bg-border"></div>
				<div class="flex items-baseline gap-1.5">
					<span class="text-xl font-bold font-mono text-text truncate max-w-[140px]">
						{stats.dominantType.label}
					</span>
					<span class="text-[10px] text-text-dim uppercase">
						{stats.dominantType.pct.toFixed(0)}% · {i18n.t('stats.dominant')}
					</span>
				</div>
			{:else if layer.primaryVariable}
				<div class="w-px h-6 bg-border"></div>
				<div class="flex items-baseline gap-1.5">
					<span class="text-xl font-bold font-mono text-text">{fmt(stats.avg, isDelta)}</span>
					<span class="text-[10px] text-text-dim uppercase truncate max-w-[140px]">
						{i18n.t('stats.avg')} {primaryLabel}
					</span>
				</div>
				<div class="w-px h-6 bg-border hidden min-[480px]:block"></div>
				<div class="hidden min-[480px]:flex items-baseline gap-1.5">
					<span class="text-xl font-bold font-mono text-cyan">{fmt(stats.max, isDelta)}</span>
					<span class="text-[10px] text-text-dim uppercase">{i18n.t('stats.max')}</span>
				</div>
			{/if}

			{#if isTemporal && mode !== 'current'}
				<div class="w-px h-6 bg-border"></div>
				<span
					class="px-2 py-0.5 rounded text-[10px] font-semibold uppercase {isDelta
						? 'bg-amber/20 text-amber'
						: 'bg-cyan/20 text-cyan'}"
				>
					{isDelta ? 'Δ ' : ''}{i18n.t(isDelta ? 'temporal.delta' : 'temporal.baseline')}
				</span>
			{/if}
		</div>
	</div>
{/if}
