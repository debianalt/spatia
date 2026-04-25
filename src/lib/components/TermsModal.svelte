<script lang="ts">
	import { terms } from '$lib/stores/terms.svelte';
</script>

<div class="overlay">
	<div class="modal">
		<div class="kicker">Condiciones de uso · nealab / spatia.ar</div>
		<h1 class="title">Antes de continuar</h1>

		<p class="intro">
			nealab es una plataforma de análisis geoespacial académico de acceso abierto. Para usarla, leé
			y aceptá las siguientes condiciones.
		</p>

		<ul class="points">
			<li>
				<span class="label">Herramienta analítica, no prescriptiva.</span>
				Ningún análisis constituye una recomendación de acción, certificación ni consultoría profesional.
			</li>
			<li>
				<span class="label">Sin garantía de exactitud.</span>
				Los datos se proveen tal cual (as-is), sin garantías expresas ni implícitas sobre exactitud,
				completitud o actualización.
			</li>
			<li>
				<span class="label">Sin responsabilidad institucional.</span>
				CONICET y UNaM son el marco académico de la investigación. No avalan los análisis como
				documentos oficiales y no asumen responsabilidad por el uso de terceros.
			</li>
			<li>
				<span class="label">Responsabilidad del usuario.</span>
				Quien use nealab en decisiones de gestión, inversión, investigación o política pública
				asume la responsabilidad de ese uso y debe complementarlo con validación independiente.
			</li>
			<li>
				<span class="label">Ley aplicable.</span>
				Estos términos se rigen por las leyes de la República Argentina. Jurisdicción: tribunales
				ordinarios de Posadas, Misiones.
			</li>
		</ul>

		<div class="actions">
			<a class="btn-secondary" href="/terminos">Leer términos completos →</a>
			<button class="btn-primary" onclick={() => terms.accept()}>
				Acepto — entrar a nealab
			</button>
		</div>
	</div>
</div>

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.88);
		backdrop-filter: blur(4px);
		z-index: 9999;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 32px 24px;
		overflow-y: auto;
	}

	.modal {
		background: #111111;
		border: 1px solid rgba(255, 255, 255, 0.15);
		max-width: 560px;
		width: 100%;
		padding: 48px 40px 40px;
		font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
		max-height: calc(100vh - 64px);
		overflow-y: auto;
		display: flex;
		flex-direction: column;
	}

	.kicker {
		font-size: 10px;
		color: rgba(255, 255, 255, 0.4);
		text-transform: uppercase;
		letter-spacing: 0.12em;
		margin-bottom: 12px;
	}

	.title {
		font-size: 22px;
		font-weight: 700;
		color: #ffffff;
		margin: 0 0 16px;
		line-height: 1.2;
	}

	.intro {
		font-size: 12px;
		color: rgba(255, 255, 255, 0.65);
		margin: 0 0 20px;
		line-height: 1.6;
	}

	.points {
		list-style: none;
		padding: 0;
		margin: 0 0 32px;
		display: flex;
		flex-direction: column;
		gap: 12px;
		flex: 1;
	}

	.points li {
		font-size: 12px;
		color: rgba(255, 255, 255, 0.7);
		line-height: 1.55;
		padding-left: 14px;
		position: relative;
	}

	.points li::before {
		content: '—';
		position: absolute;
		left: 0;
		color: rgba(255, 255, 255, 0.3);
	}

	.label {
		color: #ffffff;
		font-weight: 700;
	}

	.actions {
		display: flex;
		flex-direction: column;
		gap: 10px;
		position: sticky;
		bottom: 0;
		background: #111111;
		padding-top: 20px;
		margin-top: auto;
	}

	.btn-primary {
		background: #ffffff;
		color: #000000;
		border: none;
		padding: 12px 20px;
		font-family: inherit;
		font-size: 12px;
		font-weight: 700;
		letter-spacing: 0.04em;
		cursor: pointer;
		text-align: center;
		transition: opacity 0.15s;
	}

	.btn-primary:hover {
		opacity: 0.85;
	}

	.btn-secondary {
		display: block;
		border: 1px solid rgba(255, 255, 255, 0.25);
		color: rgba(255, 255, 255, 0.6);
		padding: 10px 20px;
		font-family: inherit;
		font-size: 11px;
		letter-spacing: 0.04em;
		text-decoration: none;
		text-align: center;
		transition: all 0.15s;
	}

	.btn-secondary:hover {
		border-color: rgba(255, 255, 255, 0.6);
		color: #ffffff;
	}
</style>
