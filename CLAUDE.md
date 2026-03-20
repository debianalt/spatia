# Spatia — Inteligencia Territorial para Misiones

## Tech Stack
- SvelteKit 5 + adapter-static
- Svelte 5 (runes syntax: `$state`, `$derived`, `$effect`)
- TypeScript
- TailwindCSS 4
- Cloudflare: Pages, Workers, R2, D1
- DuckDB-WASM (parquet queries from R2)
- MapLibre GL 5 + PMTiles
- Claude SDK (Haiku) via Pages Function proxy (`functions/api/chat.ts`)

## Critical Rules
- **Nunca romper funcionalidad existente al implementar features nuevas.**
- Antes de editar archivos compartidos (chat, comparison, map components), listar qué funciona actualmente y verificar que sigue funcionando después de los cambios.
- Para bugs de radio/click: simular el escenario de first-click.
- Para chat flows: verificar cadena completa (user input → LLM → tool call → map action → response).

## Development Practices
- Después de implementar features UI/mapa, describir qué debería ser visible y pedir confirmación visual antes de avanzar.
- Antes de escribir scripts de ingestión, verificar si los datos ya existen en la DB.
- Consultar tablas y columnas existentes en PostgreSQL/PostGIS local (db: `posadas`) antes de crear scripts.

## Deployment
- **Production branch:** `main` (push con `git push origin master:main`)
- **Deploy:** `npm run deploy` (build + wrangler pages deploy --project-name neahub --branch main)
- **R2 uploads:** SIEMPRE usar `--remote` flag
- **CORS R2:** PascalCase (AllowedOrigins, AllowedMethods) — como en `cors-rules.json`
- **URLs:** https://www.spatia.ar / https://neahub.pages.dev
- **NUNCA deployar a preview branch salvo que se pida explícitamente.**

## Database
- PostgreSQL/PostGIS local (db: `posadas`)
- Antes de crear scripts de ingestión, consultar tablas existentes y columnas disponibles.
