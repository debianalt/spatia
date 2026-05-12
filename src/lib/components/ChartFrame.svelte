<script lang="ts">
	import type { Snippet } from 'svelte';
	import { exportSvgAsPng, exportSvgAsSvg, downloadCsvFromRows } from '$lib/utils/data-export';

	let {
		title,
		children,
		csvRows,
		csvColumns,
		csvFilename = 'spatia_chart',
		initialSize = { w: 900, h: 600 },
	}: {
		title: string;
		children: Snippet;
		csvRows?: () => Array<Record<string, unknown>>;
		csvColumns?: string[];
		csvFilename?: string;
		initialSize?: { w: number; h: number };
	} = $props();

	let expanded = $state(false);
	let exportMenuOpen = $state(false);
	let pos = $state({ x: 120, y: 80 });
	let size = $state({ w: initialSize.w, h: initialSize.h });
	let host: HTMLDivElement | undefined = $state();

	// Move DOM node to document.body when expanded, restore on collapse.
	// Critical: keeps Svelte component state (brush selections, computed values)
	// intact — using {#if}{:else} would remount and reset.
	function portal(node: HTMLElement, active: boolean) {
		const placeholder = document.createComment('chart-frame-portal');
		const originalParent = node.parentElement;
		const originalNext = node.nextSibling;

		function update(active: boolean) {
			if (active) {
				if (!placeholder.parentNode && originalParent) {
					originalParent.insertBefore(placeholder, node);
				}
				if (node.parentElement !== document.body) {
					document.body.appendChild(node);
				}
			} else {
				if (placeholder.parentNode) {
					placeholder.parentNode.insertBefore(node, placeholder);
					placeholder.parentNode.removeChild(placeholder);
				} else if (originalParent && node.parentElement !== originalParent) {
					originalParent.insertBefore(node, originalNext);
				}
			}
		}

		update(active);

		return {
			update(newActive: boolean) { update(newActive); },
			destroy() {
				if (placeholder.parentNode) placeholder.parentNode.removeChild(placeholder);
			}
		};
	}

	function findSvg(): SVGElement | null {
		return host?.querySelector('.chart-frame-body svg') ?? null;
	}

	function timestamp(): string {
		const d = new Date();
		const pad = (n: number) => String(n).padStart(2, '0');
		return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
	}

	async function handleExportPng() {
		const svg = findSvg();
		if (!svg) return;
		await exportSvgAsPng(svg, `${csvFilename}_${timestamp()}.png`);
		exportMenuOpen = false;
	}

	function handleExportSvg() {
		const svg = findSvg();
		if (!svg) return;
		exportSvgAsSvg(svg, `${csvFilename}_${timestamp()}.svg`);
		exportMenuOpen = false;
	}

	function handleExportCsv() {
		if (!csvRows) return;
		const rows = csvRows();
		if (rows.length === 0) {
			exportMenuOpen = false;
			return;
		}
		const cols = csvColumns ?? Object.keys(rows[0]);
		downloadCsvFromRows(rows, cols, `${csvFilename}_${timestamp()}.csv`);
		exportMenuOpen = false;
	}

	function startDrag(e: MouseEvent) {
		if (!expanded) return;
		const startX = e.clientX, startY = e.clientY;
		const startPos = { ...pos };
		const onMove = (ev: MouseEvent) => {
			const maxX = window.innerWidth - 200;
			const maxY = window.innerHeight - 80;
			pos.x = Math.max(-size.w + 200, Math.min(maxX, startPos.x + (ev.clientX - startX)));
			pos.y = Math.max(0, Math.min(maxY, startPos.y + (ev.clientY - startY)));
		};
		const onUp = () => {
			window.removeEventListener('mousemove', onMove);
			window.removeEventListener('mouseup', onUp);
		};
		window.addEventListener('mousemove', onMove);
		window.addEventListener('mouseup', onUp);
	}

	$effect(() => {
		if (!expanded) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				expanded = false;
				exportMenuOpen = false;
			}
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});

	$effect(() => {
		if (!exportMenuOpen) return;
		const onClick = (e: MouseEvent) => {
			const target = e.target as Node;
			if (host && !host.querySelector('.chart-frame-export-wrap')?.contains(target)) {
				exportMenuOpen = false;
			}
		};
		// Defer to skip the click that opened the menu
		const id = setTimeout(() => window.addEventListener('click', onClick), 0);
		return () => {
			clearTimeout(id);
			window.removeEventListener('click', onClick);
		};
	});
</script>

<div
	bind:this={host}
	class="chart-frame"
	class:chart-frame-expanded={expanded}
	style:--pos-x="{pos.x}px"
	style:--pos-y="{pos.y}px"
	style:--size-w="{size.w}px"
	style:--size-h="{size.h}px"
	use:portal={expanded}
>
	<div
		class="chart-frame-header"
		onmousedown={startDrag}
		role="presentation"
	>
		<span class="chart-frame-title">{title}</span>
		<div class="chart-frame-actions">
			<div class="chart-frame-export-wrap">
				<button
					class="chart-frame-btn"
					title="Exportar"
					onclick={() => { exportMenuOpen = !exportMenuOpen; }}
					aria-label="Exportar"
				>↓</button>
				{#if exportMenuOpen}
					<div class="chart-frame-export-menu">
						<button class="chart-frame-export-item" onclick={handleExportPng}>↓ PNG</button>
						<button class="chart-frame-export-item" onclick={handleExportSvg}>↓ SVG</button>
						{#if csvRows}
							<button class="chart-frame-export-item" onclick={handleExportCsv}>↓ CSV</button>
						{/if}
					</div>
				{/if}
			</div>
			<button
				class="chart-frame-btn"
				title={expanded ? 'Contraer (Esc)' : 'Expandir'}
				onclick={() => { expanded = !expanded; exportMenuOpen = false; }}
				aria-label={expanded ? 'Contraer' : 'Expandir'}
			>{expanded ? '×' : '⤢'}</button>
		</div>
	</div>
	<div class="chart-frame-body">
		{@render children()}
	</div>
</div>

<style>
	.chart-frame {
		display: flex;
		flex-direction: column;
		background: rgba(15, 23, 42, 0.5);
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 6px;
		margin: 6px 0;
		overflow: hidden;
	}

	.chart-frame-expanded {
		position: fixed;
		top: var(--pos-y);
		left: var(--pos-x);
		width: var(--size-w);
		height: var(--size-h);
		min-width: 320px;
		min-height: 200px;
		max-width: 95vw;
		max-height: 92vh;
		z-index: 1000;
		background: #0a0e1a;
		border: 1px solid rgba(255, 255, 255, 0.18);
		box-shadow: 0 12px 40px rgba(0, 0, 0, 0.7);
		resize: both;
		overflow: hidden;
		margin: 0;
	}

	.chart-frame-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 5px 8px;
		background: rgba(255, 255, 255, 0.04);
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
		font-size: 10px;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.75);
		flex-shrink: 0;
	}

	.chart-frame-expanded .chart-frame-header {
		cursor: grab;
		padding: 8px 12px;
		font-size: 12px;
	}
	.chart-frame-expanded .chart-frame-header:active { cursor: grabbing; }

	.chart-frame-title {
		text-transform: uppercase;
		letter-spacing: 0.04em;
		pointer-events: none;
	}

	.chart-frame-actions {
		display: flex;
		align-items: center;
		gap: 4px;
		pointer-events: auto;
	}

	.chart-frame-btn {
		background: none;
		border: 1px solid transparent;
		color: rgba(255, 255, 255, 0.55);
		font-size: 12px;
		line-height: 1;
		padding: 3px 7px;
		border-radius: 3px;
		cursor: pointer;
		font-family: inherit;
		transition: all 0.12s;
	}
	.chart-frame-btn:hover {
		color: #fff;
		background: rgba(255, 255, 255, 0.08);
		border-color: rgba(255, 255, 255, 0.18);
	}

	.chart-frame-export-wrap {
		position: relative;
	}

	.chart-frame-export-menu {
		position: absolute;
		top: calc(100% + 4px);
		right: 0;
		background: rgba(10, 14, 26, 0.98);
		border: 1px solid rgba(255, 255, 255, 0.15);
		border-radius: 5px;
		padding: 3px;
		display: flex;
		flex-direction: column;
		gap: 1px;
		z-index: 1001;
		min-width: 90px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
	}

	.chart-frame-export-item {
		background: none;
		border: none;
		color: rgba(255, 255, 255, 0.85);
		font-family: inherit;
		font-size: 10px;
		text-align: left;
		padding: 5px 10px;
		cursor: pointer;
		border-radius: 3px;
		transition: background 0.1s;
	}
	.chart-frame-export-item:hover { background: rgba(255, 255, 255, 0.08); }

	.chart-frame-body {
		flex: 1;
		overflow: auto;
		min-height: 0;
		padding: 4px 6px 6px;
	}

	.chart-frame-expanded .chart-frame-body {
		padding: 10px 14px 14px;
	}

	/* Charts have fixed-aspect SVGs by default; scale them up when expanded */
	.chart-frame-expanded .chart-frame-body :global(svg) {
		width: 100%;
		height: auto;
		max-height: calc(100% - 20px);
	}
</style>
