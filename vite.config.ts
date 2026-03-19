import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		{
			name: 'geojson-loader',
			transform(code, id) {
				if (id.endsWith('.geojson')) {
					return { code: `export default ${code}`, map: null };
				}
			}
		},
		tailwindcss(),
		sveltekit()
	],
	optimizeDeps: {
		exclude: ['@duckdb/duckdb-wasm']
	},
	worker: {
		format: 'es'
	},
	build: {
		target: 'esnext'
	},
	server: {
		proxy: {
			'/r2': {
				target: 'https://pub-580c676bec7f4eeb96d7d30559a3cab7.r2.dev',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/r2/, '')
			},
			'/api': {
				target: 'http://localhost:8788',
				changeOrigin: true
			}
		}
	}
});
