import { readFile } from "node:fs/promises";
import pg from "pg";
export type Db = pg.Pool;
export type Tx = pg.PoolClient;
export const MEDIA_LOCK = 6400001;
export function openDb(
  connectionString: string,
  reportConnectionError: (code: string) => void = (code) => {
    process.stderr.write(`Database pool connection unavailable (${code}).\n`);
  },
): Db {
  const pool = new pg.Pool({
    connectionString,
    max: 12,
    connectionTimeoutMillis: 3000,
    statement_timeout: 5000,
    idle_in_transaction_session_timeout: 10000,
  });
  // Checked-out clients no longer have pg-pool's idle error listener. Handle
  // those events too without replacing ownership/fail-closed callbacks.
  // Never log the Client or raw errors; both can expose connection details.
  const report = (error: unknown) => {
    const code =
      typeof error === "object" &&
      error !== null &&
      "code" in error &&
      typeof error.code === "string" &&
      /^[0-9A-Z]{5}$/.test(error.code)
        ? error.code
        : "transport";
    reportConnectionError(code);
  };
  pool.on("connect", (client) => client.on("error", report));
  pool.on("error", report);
  return pool;
}
export async function transaction<T>(
  db: Db,
  work: (tx: Tx) => Promise<T>,
): Promise<T> {
  const tx = await db.connect();
  try {
    await tx.query("BEGIN");
    const result = await work(tx);
    await tx.query("COMMIT");
    return result;
  } catch (error) {
    await tx.query("ROLLBACK");
    throw error;
  } finally {
    tx.release();
  }
}
export async function lockMedia(tx: Tx): Promise<void> {
  await tx.query("SELECT pg_advisory_xact_lock($1)", [MEDIA_LOCK]);
}
export async function audit(
  tx: Tx | Db,
  actor: string | null,
  action: string,
  target: string | null = null,
): Promise<void> {
  await tx.query(
    "INSERT INTO audit_events(actor_id,action,target_id) VALUES($1,$2,$3)",
    [actor, action, target],
  );
}
export async function migrate(db: Db): Promise<void> {
  const sql = await readFile(
    new URL("../migrations/001_initial.sql", import.meta.url),
    "utf8",
  );
  await transaction(db, async (tx) => {
    await tx.query("SELECT pg_advisory_xact_lock(6400000)");
    await tx.query(
      "CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())",
    );
    if (
      (await tx.query("SELECT version FROM schema_migrations WHERE version=1"))
        .rowCount === 0
    ) {
      await tx.query(sql);
      await tx.query("INSERT INTO schema_migrations(version) VALUES(1)");
    }
  });
}
