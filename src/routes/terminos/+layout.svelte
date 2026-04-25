<script lang="ts">
	import '../../app.css';
	let { children } = $props();
</script>

<div class="relative w-full min-h-screen bg-bg">
	{@render children()}
</div>
