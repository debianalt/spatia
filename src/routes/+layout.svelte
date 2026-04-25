<script lang="ts">
	import '../app.css';
	import TermsModal from '$lib/components/TermsModal.svelte';
	import { terms } from '$lib/stores/terms.svelte';
	import { page } from '$app/stores';
	let { children } = $props();

	const EXCLUDED = ['/terminos', '/servicios'];
</script>

<div class="relative w-full min-h-screen bg-bg">
	{#if !terms.accepted && !EXCLUDED.includes($page.url.pathname)}
		<TermsModal />
	{/if}
	{@render children()}
</div>
