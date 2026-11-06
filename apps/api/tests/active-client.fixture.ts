// Disposable database only. The parent passes its URL on stdin, never argv.
import assert from "node:assert/strict";
import { openDb, type Tx } from "../src/db.js";

const chunks: Buffer[] = [];
for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
const { url, ownerListener } = JSON.parse(
  Buffer.concat(chunks).toString("utf8"),
) as { url: string; ownerListener: boolean };
const codes: string[] = [];
const db = openDb(url, (code) => codes.push(code));
let leased: Tx | undefined;
let ownerEvents = 0;
try {
  leased = await db.connect();
  if (ownerListener) leased.on("error", () => ownerEvents++);
  const pid = (
    await leased.query<{ pid: number }>("SELECT pg_backend_pid() AS pid")
  ).rows[0]!.pid;
  const terminated = await db.query<{ stopped: boolean }>(
    "SELECT pg_terminate_backend($1) AS stopped",
    [pid],
  );
  assert.equal(terminated.rows[0]!.stopped, true);
  for (let attempt = 0; attempt < 50 && !codes.includes("57P01"); attempt++)
    await new Promise((resolve) => setTimeout(resolve, 20));
  assert.ok(codes.includes("57P01"));
  if (ownerListener) assert.ok(ownerEvents > 0);
  leased.release(true);
  leased = undefined;
  assert.equal((await db.query("SELECT 1 AS healthy")).rows[0].healthy, 1);
  process.stdout.write(JSON.stringify({ codes, ownerEvents, healthy: true }));
} finally {
  leased?.release(true);
  await db.end();
}
