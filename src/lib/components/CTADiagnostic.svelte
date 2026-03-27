<script lang="ts">
	import { i18n } from '$lib/stores/i18n.svelte';

	let {
		analysisName = '',
		department = '',
	}: {
		analysisName?: string;
		department?: string;
	} = $props();

	const EMAIL = 'spatia.unused740@passinbox.com';

	const mailtoUrl = $derived.by(() => {
		const subject = encodeURIComponent('Consulta diagnóstico territorial — Spatia');
		let body = 'Hola, estoy usando Spatia (spatia.ar) y me interesa un diagnóstico territorial.';
		if (analysisName || department) {
			body += '\n\n';
			if (analysisName) body += `Estaba viendo: ${analysisName}\n`;
			if (department) body += `Departamento: ${department}\n`;
		}
		body += '\n¿Podrían enviarme más información sobre el servicio?';
		return `mailto:${EMAIL}?subject=${subject}&body=${encodeURIComponent(body)}`;
	});
</script>

<div class="cta-box">
	<div class="cta-label">{i18n.t('cta.diagnostic.label')}</div>
	<a href={mailtoUrl} class="cta-btn">
		<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 4 12 13 2 4"/>
		</svg>
		{i18n.t('cta.diagnostic.button')}
	</a>
</div>

<style>
	.cta-box {
		margin-top: 14px;
		padding: 10px 12px;
		background: rgba(59, 130, 246, 0.06);
		border: 1px solid rgba(59, 130, 246, 0.18);
		border-radius: 6px;
		text-align: center;
	}
	.cta-label {
		font-size: 9px;
		color: rgba(255, 255, 255, 0.5);
		margin-bottom: 8px;
		line-height: 1.4;
	}
	.cta-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 7px 14px;
		background: rgba(59, 130, 246, 0.15);
		color: #93c5fd;
		border: 1px solid rgba(59, 130, 246, 0.25);
		border-radius: 4px;
		font-size: 10px;
		font-weight: 600;
		text-decoration: none;
		cursor: pointer;
		transition: all 0.15s;
	}
	.cta-btn:hover {
		background: rgba(59, 130, 246, 0.25);
		border-color: rgba(59, 130, 246, 0.4);
		color: #bfdbfe;
	}
</style>
