<script lang="ts">
	import { i18n, type Locale } from '$lib/stores/i18n.svelte';

	let { variant = 'map' }: { variant: 'map' | 'mono' } = $props();
	const langs: Locale[] = ['es', 'en', 'gn', 'pt'];
</script>

{#if variant === 'map'}
	<div class="flex items-center gap-0.5">
		{#each langs as lang}
			<button
				class="px-2.5 py-1 text-[11px] font-semibold rounded-full cursor-pointer border transition-all {i18n.locale === lang ? 'bg-white/10 text-white border-white/30' : 'bg-transparent text-white/50 border-transparent hover:text-white'}"
				onclick={() => i18n.setLocale(lang)}>
				{lang === 'pt' ? 'BR' : lang.toUpperCase()}
			</button>
		{/each}
	</div>
{:else}
	<div class="lang-switcher">
		{#each langs as lang}
			<button
				class:active={i18n.locale === lang}
				onclick={() => i18n.setLocale(lang)}>
				{lang === 'pt' ? 'BR' : lang.toUpperCase()}
			</button>
		{/each}
	</div>
{/if}

<style>
	.lang-switcher {
		display: flex;
		align-items: center;
		gap: 2px;
	}
	.lang-switcher button {
		padding: 4px 8px;
		font-size: 10px;
		font-weight: 600;
		letter-spacing: 0.05em;
		background: transparent;
		border: 1px solid transparent;
		border-radius: 4px;
		color: rgba(255, 255, 255, 0.4);
		cursor: pointer;
		font-family: inherit;
		transition: all 0.15s;
	}
	.lang-switcher button:hover {
		color: rgba(255, 255, 255, 0.8);
	}
	.lang-switcher button.active {
		background: rgba(255, 255, 255, 0.08);
		border-color: rgba(255, 255, 255, 0.2);
		color: rgba(255, 255, 255, 0.9);
	}
</style>
