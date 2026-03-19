<script lang="ts">
	import { LENS_CONFIG } from '$lib/config';
	import type { LensStore } from '$lib/stores/lens.svelte';
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		lensStore,
		onSelectDpto,
		onSelectRadio
	}: {
		lensStore: LensStore;
		onSelectDpto: (dpto: string) => void;
		onSelectRadio: (redcode: string) => void;
	} = $props();

	const cfg = $derived(lensStore.activeLens ? LENS_CONFIG[lensStore.activeLens] : null);
	const summary = $derived(lensStore.departmentSummary);
	const maxCount = $derived(summary.length > 0 ? summary[0].count : 1);
	const dptoRadios = $derived(lensStore.selectedDpto ? [...lensStore.dptoOpportunities.entries()].sort((a, b) => {
		if (!lensStore.activeLens) return 0;
		const scoreCol = LENS_CONFIG[lensStore.activeLens].scoreCol;
		return (b[1][scoreCol] ?? 0) - (a[1][scoreCol] ?? 0);
	}) : []);
</script>

{#if cfg}
	{#if lensStore.selectedDpto}
		<!-- Department detail: list of radios -->
		<div class="dpto-detail">
			<button class="back-btn" onclick={() => lensStore.clearDpto()}>
				{i18n.t('lens.backToDepts')}
			</button>
			<div class="dpto-header">
				<span class="dpto-name">{lensStore.selectedDpto}</span>
				<span class="dpto-badge" style:background={cfg.color}>{lensStore.dptoOpportunities.size}</span>
			</div>
			<div class="radio-list">
				{#each dptoRadios as [redcode, row]}
					{@const score = row[cfg.scoreCol] ?? 0}
					<button class="radio-row" onclick={() => onSelectRadio(redcode)}>
						<span class="radio-code">{redcode}</span>
						<span class="radio-score" style:color={cfg.color}>{score.toFixed(2)}</span>
					</button>
				{/each}
			</div>
		</div>
	{:else}
		<!-- Department list -->
		<div class="dpto-list">
			<div class="dpto-list-header">
				<span class="header-icon">{cfg.icon}</span>
				<span class="header-label">{cfg.label[i18n.locale as 'es' | 'en' | 'gn']}</span>
				<span class="header-count" style:color={cfg.color}>{lensStore.opportunityCount} {i18n.t('lens.opportunities')}</span>
			</div>
			<div class="dpto-items">
				{#each summary as dept}
					<button class="dpto-row" onclick={() => onSelectDpto(dept.dpto)}>
						<div class="dpto-row-top">
							<span class="dpto-name">{dept.dpto}</span>
							<span class="dpto-badge" style:background={cfg.color}>{dept.count}</span>
						</div>
						<div class="dpto-bar-bg">
							<div class="dpto-bar" style:width="{(dept.count / maxCount) * 100}%" style:background={cfg.color}></div>
						</div>
					</button>
				{/each}
			</div>
		</div>
	{/if}
{/if}

<style>
	.dpto-list-header {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-bottom: 8px;
		flex-wrap: wrap;
	}
	.header-icon { font-size: 14px; }
	.header-label { font-size: 11px; font-weight: 600; color: #e2e8f0; }
	.header-count { font-size: 10px; font-weight: 500; opacity: 0.85; margin-left: auto; }
	.dpto-items {
		display: flex;
		flex-direction: column;
		gap: 2px;
		max-height: calc(100vh - 200px);
		overflow-y: auto;
		scrollbar-width: thin;
		scrollbar-color: #334155 transparent;
	}
	.dpto-items::-webkit-scrollbar { width: 4px; }
	.dpto-items::-webkit-scrollbar-track { background: transparent; }
	.dpto-items::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }
	.dpto-row {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 5px 8px;
		border-radius: 6px;
		border: none;
		background: rgba(255,255,255,0.03);
		cursor: pointer;
		transition: background 0.15s;
		text-align: left;
		width: 100%;
	}
	.dpto-row:hover { background: rgba(255,255,255,0.08); }
	.dpto-row-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.dpto-name { font-size: 10px; color: #cbd5e1; font-weight: 500; }
	.dpto-badge {
		font-size: 9px;
		font-weight: 700;
		color: #0f172a;
		padding: 1px 6px;
		border-radius: 9999px;
		min-width: 20px;
		text-align: center;
	}
	.dpto-bar-bg {
		height: 3px;
		background: rgba(255,255,255,0.06);
		border-radius: 2px;
		overflow: hidden;
	}
	.dpto-bar {
		height: 100%;
		border-radius: 2px;
		transition: width 0.3s ease;
	}

	/* Department detail */
	.dpto-detail { display: flex; flex-direction: column; gap: 6px; }
	.back-btn {
		font-size: 10px;
		color: #94a3b8;
		background: none;
		border: none;
		cursor: pointer;
		padding: 2px 0;
		text-align: left;
		transition: color 0.15s;
	}
	.back-btn:hover { color: #e2e8f0; }
	.dpto-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-bottom: 4px;
		border-bottom: 1px solid rgba(255,255,255,0.06);
	}
	.dpto-header .dpto-name { font-size: 12px; font-weight: 600; color: #e2e8f0; }
	.radio-list {
		display: flex;
		flex-direction: column;
		gap: 1px;
		max-height: calc(100vh - 220px);
		overflow-y: auto;
		scrollbar-width: thin;
		scrollbar-color: #334155 transparent;
	}
	.radio-list::-webkit-scrollbar { width: 4px; }
	.radio-list::-webkit-scrollbar-track { background: transparent; }
	.radio-list::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }
	.radio-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 4px 8px;
		border-radius: 4px;
		border: none;
		background: transparent;
		cursor: pointer;
		transition: background 0.15s;
		width: 100%;
	}
	.radio-row:hover { background: rgba(255,255,255,0.06); }
	.radio-code { font-size: 10px; color: #94a3b8; font-family: monospace; }
	.radio-score { font-size: 10px; font-weight: 600; }
</style>
