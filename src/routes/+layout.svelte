<script lang="ts">
	import '../app.css';
	let { children } = $props();
</script>

<div class="relative w-full h-screen bg-bg">
	{@render children()}
</div>
