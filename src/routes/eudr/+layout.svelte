<script lang="ts">
	import '../../app.css';
	let { children } = $props();
</script>

<div class="min-h-screen bg-bg text-text font-mono">
	<header class="sticky top-0 z-50 border-b border-border" style="background: rgba(10,12,18,0.88); backdrop-filter: blur(8px);">
		<div class="px-4 py-2.5 flex items-center gap-3">
			<a href="/" class="text-[17px] font-bold text-white tracking-wide hover:text-white/80 transition-colors">nealab</a>
			<span class="text-white/20">&middot;</span>
			<a href="/" class="text-[13px] text-white/40 hover:text-white transition-colors">&larr; Mapa</a>
		</div>
	</header>
	<main class="max-w-6xl mx-auto px-6">
		{@render children()}
	</main>
</div>
