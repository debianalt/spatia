<script lang="ts">
	import { query, isReady } from '$lib/stores/duckdb';
	import { PARQUETS, getParquetUrl } from '$lib/config';

	const SCHEMA_CONTEXT = `Available Parquet tables (query via DuckDB SQL using full URLs):

1. '${PARQUETS.censo_radios}' — Census 2022 data per radio censal
   Columns: redcode (text, radio ID), departamento (text), poblacion (int), viviendas (int), area_km2 (float), densidad_hab_km2 (float)

2. '${PARQUETS.censo_departamentos}' — Census 2022 aggregated per departamento
   Columns: cod_depto (text), departamento (text), poblacion (int), viviendas (int), superficie_km2 (float)

3. '${PARQUETS.magyp_estimaciones}' — Agricultural production estimates (MAGyP)
   Columns: campana (text, e.g. "2022/23"), cultivo (text, crop name), departamento (text), superficie_ha (float), produccion_t (float), rendimiento_kg_ha (float)

4. '${PARQUETS.ndvi_annual}' — Annual mean NDVI satellite vegetation index (2000-2025)
   Columns: redcode (text), year (int), mean_ndvi (float)

5. '${PARQUETS.buildings_stats}' — Building footprint statistics per radio
   Columns: redcode (text), n_buildings (int), total_area_m2 (float), avg_height_m (float)

6. '${PARQUETS.localidades}' — Localities/towns
   Columns: nombre (text), cod_depto (text), tipo (text)

7. '${PARQUETS.barrios}' — Neighborhoods
   Columns: nombre (text), localidad (text), departamento (text), tipo (text)

8. '${PARQUETS.radio_stats_master}' — Master table with ~200 columns per radio censal (census, NDVI, buildings, land use, accessibility, etc.)
   Key columns: redcode (text), dpto (text), total_personas (int), n_buildings (int), area_km2 (float), densidad_hab_km2 (float), mean_ndvi (float), and many more

All data is for Misiones province, Argentina. Return ONLY the SQL query, no explanation. Use single quotes for the full Parquet URL. Use DuckDB SQL syntax. Important: text columns may contain Spanish accents (e.g. "Oberá"), so use unaccent() or accent-insensitive matching when filtering text. DuckDB has no unaccent by default, so use REPLACE chains or exact accented values when you know them.`;

	const PRESET_QUERIES = [
		{
			label: 'Población por departamento',
			sql: `SELECT departamento, SUM(poblacion) as pop, COUNT(*) as radios\nFROM '${PARQUETS.censo_radios}'\nGROUP BY departamento ORDER BY pop DESC`
		},
		{
			label: 'Top 10 radios más densos',
			sql: `SELECT redcode, poblacion, area_km2,\n  ROUND(poblacion / NULLIF(area_km2, 0), 1) as densidad_hab_km2\nFROM '${PARQUETS.censo_radios}'\nORDER BY densidad_hab_km2 DESC NULLS LAST LIMIT 10`
		},
		{
			label: 'Producción agrícola por cultivo',
			sql: `SELECT cultivo, SUM(superficie_ha) as ha, SUM(produccion_t) as t\nFROM '${PARQUETS.magyp_estimaciones}'\nGROUP BY cultivo ORDER BY ha DESC LIMIT 10`
		}
	];

	let mode = $state<'presets' | 'nl' | 'sql'>('nl');
	let selectedIdx = $state(0);
	let nlInput = $state('');
	let sqlInput = $state('');
	let generatedSql = $state('');
	let rows = $state<Record<string, any>[]>([]);
	let columns = $state<string[]>([]);
	let elapsed = $state<number | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(false);
	let apiKey = $state('');
	let showSettings = $state(false);
	let collapsed = $state(true);
	let duckdbStatus = $state<'loading' | 'ready' | 'error'>('loading');
	let duckdbError = $state('');

	// Load API key from localStorage
	if (typeof window !== 'undefined') {
		apiKey = localStorage.getItem('neahub_claude_key') || '';
		// Monitor DuckDB readiness
		const checkReady = setInterval(() => {
			if (isReady()) { duckdbStatus = 'ready'; clearInterval(checkReady); }
		}, 500);
		setTimeout(() => { if (duckdbStatus === 'loading') { duckdbStatus = 'error'; duckdbError = 'DuckDB failed to initialize'; clearInterval(checkReady); } }, 30000);
	}

	function saveKey() {
		localStorage.setItem('neahub_claude_key', apiKey);
		showSettings = false;
	}

	async function nlToSql(question: string): Promise<string> {
		if (!apiKey) throw new Error('Set your Claude API key first (click ⚙)');

		const res = await fetch('/api/chat', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'x-api-key': apiKey
			},
			body: JSON.stringify({
				model: 'claude-haiku-4-5-20251001',
				max_tokens: 512,
				messages: [{
					role: 'user',
					content: `${SCHEMA_CONTEXT}\n\nQuestion: ${question}`
				}]
			})
		});

		if (!res.ok) {
			const body = await res.text();
			throw new Error(`API error ${res.status}: ${body}`);
		}

		const data = await res.json();
		let sql = data.content[0].text.trim();
		// Strip markdown code fences if present
		sql = sql.replace(/^```(?:sql)?\n?/i, '').replace(/\n?```$/,'');
		return sql.trim();
	}

	async function run() {
		if (!isReady()) { error = 'DuckDB no está listo. Esperá unos segundos o recargá la página.'; return; }
		loading = true;
		error = null;
		rows = [];
		columns = [];
		elapsed = null;
		generatedSql = '';

		try {
			let sql: string;

			if (mode === 'presets') {
				sql = PRESET_QUERIES[selectedIdx].sql;
			} else if (mode === 'nl') {
				if (!nlInput.trim()) { error = 'Type a question'; loading = false; return; }
				sql = await nlToSql(nlInput.trim());
				generatedSql = sql;
			} else {
				if (!sqlInput.trim()) { error = 'Type a SQL query'; loading = false; return; }
				sql = sqlInput.trim();
			}

			// DuckDB-WASM needs absolute URLs (worker can't use Vite proxy)
			sql = sql.replace(/['"]\/r2\//g, (m) => m[0] + 'https://pub-580c676bec7f4eeb96d7d30559a3cab7.r2.dev/');

			const t0 = performance.now();
			const result = await query(sql);
			elapsed = Math.round(performance.now() - t0);

			columns = result.schema.fields.map(f => f.name);
			rows = result.toArray().map(r => {
				const obj: Record<string, any> = {};
				for (const col of columns) obj[col] = r[col];
				return obj;
			});
		} catch (e: any) {
			error = e.message || String(e);
		} finally {
			loading = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			run();
		}
	}

	function fmt(v: any): string {
		if (v == null) return '\u2014';
		if (typeof v === 'number') return v.toLocaleString('en-US', { maximumFractionDigits: 2 });
		if (typeof v === 'bigint') return v.toLocaleString('en-US');
		return String(v);
	}
</script>

<div class="absolute bottom-4 left-3 z-10 rounded-lg border border-border transition-all"
	style="background: var(--color-panel); backdrop-filter: blur(8px); width: min(840px, calc(100vw - 24px));">

	<!-- Collapsed bar -->
	<button class="w-full flex items-center justify-between px-4 py-2 cursor-pointer bg-transparent border-none text-left"
		onclick={() => collapsed = !collapsed}>
		<span class="text-[10px] uppercase tracking-widest text-text-dim">Query
			{#if duckdbStatus === 'loading'}<span style="color:#f59e0b"> ⏳</span>{:else if duckdbStatus === 'error'}<span style="color:#ef4444"> ✗</span>{:else}<span style="color:#22c55e"> ✓</span>{/if}
		</span>
		<span class="text-text-dim text-xs">{collapsed ? '▲' : '▼'}</span>
	</button>

	{#if !collapsed}
	<div class="px-4 pb-3">
		<!-- Mode tabs + settings -->
		<div class="flex items-center gap-1 mb-2">
			{#each [['nl', 'Ask'], ['presets', 'Presets'], ['sql', 'SQL']] as [m, label]}
				<button
					class="px-2 py-0.5 text-[10px] rounded border cursor-pointer transition-all {mode === m ? 'bg-accent-active border-accent text-accent' : 'bg-btn-bg border-btn-border text-text-muted'}"
					onclick={() => mode = m as any}>
					{label}
				</button>
			{/each}
			<button class="ml-auto text-text-dim text-xs cursor-pointer bg-transparent border-none hover:text-text"
				onclick={() => showSettings = !showSettings} title="API key settings">⚙</button>
		</div>

		<!-- Settings panel -->
		{#if showSettings}
			<div class="mb-2 p-2 rounded border border-border bg-bg">
				<label class="text-[10px] text-text-dim block mb-1">Claude API Key</label>
				<div class="flex gap-1">
					<input type="password" bind:value={apiKey} placeholder="sk-ant-..."
						class="flex-1 bg-btn-bg border border-btn-border text-text rounded px-2 py-1 text-[11px]" />
					<button onclick={saveKey}
						class="bg-accent-active border border-accent text-accent rounded px-2 py-1 text-[10px] cursor-pointer">
						Save
					</button>
				</div>
				<p class="text-text-dim text-[9px] mt-1">Stored in localStorage. Used client-side only.</p>
			</div>
		{/if}

		<!-- Input area -->
		{#if mode === 'nl'}
			<div class="flex gap-1.5">
				<input type="text" bind:value={nlInput} placeholder="e.g. ¿cuánta población tiene Oberá?"
					class="flex-1 bg-btn-bg border border-btn-border text-text rounded-md px-2.5 py-1.5 text-[11px]"
					onkeydown={handleKeydown} />
				<button onclick={run} disabled={loading}
					class="bg-accent-active border border-accent text-accent rounded-md px-3 py-1.5 text-[11px] font-semibold cursor-pointer disabled:opacity-50">
					{loading ? '...' : '→'}
				</button>
			</div>
		{:else if mode === 'presets'}
			<div class="flex gap-1.5">
				<select bind:value={selectedIdx}
					class="flex-1 bg-btn-bg border border-btn-border text-text rounded-md px-2 py-1.5 text-[11px] cursor-pointer">
					{#each PRESET_QUERIES as q, i}
						<option value={i}>{q.label}</option>
					{/each}
				</select>
				<button onclick={run} disabled={loading}
					class="bg-accent-active border border-accent text-accent rounded-md px-3 py-1.5 text-[11px] font-semibold cursor-pointer disabled:opacity-50">
					{loading ? '...' : '→'}
				</button>
			</div>
		{:else}
			<div class="flex gap-1.5">
				<textarea bind:value={sqlInput} placeholder="SELECT ... FROM '...parquet'"
					rows="2"
					class="flex-1 bg-btn-bg border border-btn-border text-text rounded-md px-2.5 py-1.5 text-[11px] font-mono resize-none"
					onkeydown={handleKeydown}></textarea>
				<button onclick={run} disabled={loading}
					class="bg-accent-active border border-accent text-accent rounded-md px-3 py-1.5 text-[11px] font-semibold cursor-pointer disabled:opacity-50 self-end">
					{loading ? '...' : '→'}
				</button>
			</div>
		{/if}

		<!-- Generated SQL preview -->
		{#if generatedSql}
			<pre class="mt-1.5 p-2 bg-bg rounded border border-border text-[10px] text-text-muted font-mono overflow-x-auto whitespace-pre-wrap">{generatedSql}</pre>
		{/if}

		<!-- Error -->
		{#if error}
			<p class="mt-1.5 text-[11px]" style="color: #f59e0b;">{error}</p>
		{/if}

		<!-- Results -->
		{#if elapsed !== null}
			<div class="mt-1.5 flex items-center gap-2">
				<span class="text-text-dim text-[10px]">{rows.length} rows</span>
				<span class="text-text-dim text-[10px]">{elapsed} ms</span>
			</div>
		{/if}
		{#if rows.length > 0}
			<div class="mt-1 overflow-x-auto max-h-[30vh] overflow-y-auto">
				<table class="w-full text-[11px] border-collapse">
					<thead class="sticky top-0">
						<tr style="background: var(--color-panel);">
							{#each columns as col}
								<th class="text-left text-text-muted font-semibold py-1 px-2 border-b border-border whitespace-nowrap">{col}</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each rows as row}
							<tr class="hover:bg-white/5">
								{#each columns as col}
									<td class="py-0.5 px-2 text-text whitespace-nowrap">{fmt(row[col])}</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
	{/if}
</div>
