import type { AsyncDuckDB, AsyncDuckDBConnection } from '@duckdb/duckdb-wasm';
import type { Table } from 'apache-arrow';

let db: AsyncDuckDB | null = null;
let conn: AsyncDuckDBConnection | null = null;
let initPromise: Promise<void> | null = null;
let initError: string | null = null;

const INIT_TIMEOUT_MS = 20_000;

async function createWorkerBlob(url: string): Promise<Worker> {
	const res = await fetch(url);
	const blob = new Blob([await res.text()], { type: 'application/javascript' });
	return new Worker(URL.createObjectURL(blob), { type: 'module' });
}

export async function initDuckDB(): Promise<void> {
	if (db) return;
	if (initPromise) return initPromise;

	initPromise = Promise.race([
		(async () => {
			const duckdb = await import('@duckdb/duckdb-wasm');

			const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();
			const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);

			// Create worker via blob URL to avoid cross-origin restriction
			const worker = await createWorkerBlob(bundle.mainWorker!);
			const logger = new duckdb.ConsoleLogger();

			db = new duckdb.AsyncDuckDB(logger, worker);
			await db.instantiate(bundle.mainModule, bundle.pthreadWorker);

			conn = await db.connect();

			// Install and load httpfs for remote Parquet access
			await conn.query(`INSTALL httpfs`);
			await conn.query(`LOAD httpfs`);
		})(),
		new Promise<void>((_, reject) =>
			setTimeout(() => reject(new Error('DuckDB init timeout')), INIT_TIMEOUT_MS)
		),
	]).catch((e) => {
		initError = e instanceof Error ? e.message : 'Error initializing data engine';
		initPromise = null;
		throw e;
	});

	return initPromise;
}

export async function query(sql: string): Promise<Table> {
	if (!conn) throw new Error('DuckDB not initialized. Call initDuckDB() first.');
	return await conn.query(sql);
}

export function isReady(): boolean {
	return db !== null && conn !== null;
}

export function getInitError(): string | null {
	return initError;
}
