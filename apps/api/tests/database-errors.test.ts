import { test } from "node:test";
import assert from "node:assert/strict";
import { openDb } from "../src/db.js";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { testDatabase } from "./database.js";
test("idle connection errors report SQLSTATE without client credentials or raw messages", async () => {
  const reported: string[] = [];
  const pool = openDb("postgresql://unused@127.0.0.1:1/unused", (code) =>
    reported.push(code),
  );
  pool.emit(
    "error",
    Object.assign(new Error("private-canary-password"), { code: "57P01" }),
    { password: "private-canary-password" },
  );
  pool.emit(
    "error",
    Object.assign(new Error("private-canary-password"), {
      code: "private-canary-password",
    }),
    { password: "private-canary-password" },
  );
  assert.deepEqual(reported, ["57P01", "transport"]);
  await pool.end();
});
test("checked-out client termination is handled safely and retains owner error listeners", async () => {
  const database = await testDatabase();
  try {
    for (const ownerListener of [false, true]) {
      const result = spawnSync(
        process.execPath,
        [
          "--import",
          "tsx",
          fileURLToPath(new URL("./active-client.fixture.ts", import.meta.url)),
        ],
        {
          input: JSON.stringify({ url: database.url, ownerListener }),
          encoding: "utf8",
          timeout: 15000,
          maxBuffer: 1024 * 1024,
        },
      );
      assert.equal(
        result.status,
        0,
        `Checked-out client recovery failed (owner listener: ${ownerListener}, exit: ${result.status}, backend termination observed: ${result.stderr.includes("terminating connection due to administrator command")}).`,
      );
      assert.ok(!result.stderr.includes(new URL(database.url).password));
      assert.ok(
        !result.stderr.includes(
          "terminating connection due to administrator command",
        ),
      );
      const report = JSON.parse(result.stdout) as {
        codes: string[];
        ownerEvents: number;
        healthy: boolean;
      };
      assert.ok(report.codes.includes("57P01"));
      assert.equal(report.healthy, true);
      if (ownerListener) assert.ok(report.ownerEvents > 0);
    }
  } finally {
    await database.close();
  }
});
