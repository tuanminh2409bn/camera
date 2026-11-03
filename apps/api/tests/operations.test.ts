import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, chmod, symlink, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { operationCodes } from "@devone/contracts";
import { readOperations } from "../src/operations.js";

test("operational snapshot rejects stale, unsafe, unknown and private payloads", async () => {
  const directory = await mkdtemp(join(tmpdir(), "camera-operations-"));
  const path = join(directory, "status.json");
  const now = Date.now();
  const snapshot = {
    updatedAt: new Date(now).toISOString(),
    checks: operationCodes.map((code) => ({
      code,
      status: "ok",
      since: null,
      value: null,
    })),
    events: [],
    traffic: null,
  };
  async function save(value: unknown) {
    await writeFile(path, JSON.stringify(value), { mode: 0o600 });
  }
  try {
    assert.deepEqual(await readOperations(path, now), {
      available: false,
      reason: "unavailable",
    });
    await save(snapshot);
    assert.equal((await readOperations(path, now)).available, true);
    assert.deepEqual(await readOperations(path, now + 180001), {
      available: false,
      reason: "stale",
    });
    assert.deepEqual(await readOperations(path, now - 60001), {
      available: false,
      reason: "stale",
    });
    await chmod(path, 0o644);
    assert.equal((await readOperations(path, now)).available, false);
    await chmod(path, 0o600);
    const link = join(directory, "link");
    await symlink(path, link);
    assert.equal((await readOperations(link, now)).available, false);
    await save({ ...snapshot, secret: "must-never-reach-admin" });
    assert.equal((await readOperations(path, now)).available, false);
    await save({
      ...snapshot,
      checks: snapshot.checks.map(() => snapshot.checks[0]),
    });
    assert.equal((await readOperations(path, now)).available, false);
    await save({
      ...snapshot,
      checks: [
        { code: "PRIVATE_UNKNOWN", status: "firing", since: null, value: null },
      ],
    });
    assert.equal((await readOperations(path, now)).available, false);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
