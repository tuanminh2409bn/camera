import EmbeddedPostgres from "embedded-postgres";
import { mkdir, mkdtemp, chmod, readFile, rm } from "node:fs/promises";
import { resolve, join } from "node:path";
import { createServer } from "node:net";
import { randomBytes } from "node:crypto";
import { openDb, migrate } from "../src/db.js";

export async function testDatabase() {
  const root = resolve(".local/test-databases");
  await mkdir(root, { recursive: true, mode: 0o700 });
  const directory = await mkdtemp(join(root, "postgres-"));
  await chmod(directory, 0o700);
  // The reviewed package hydrator must never create links outside its package.
  const packageRoot = resolve(
    `node_modules/@embedded-postgres/${process.platform}-${process.arch}`,
  );
  const links = JSON.parse(
    await readFile(join(packageRoot, "native/pg-symlinks.json"), "utf8"),
  ) as { source: string; target: string }[];
  for (const link of links)
    for (const value of [link.source, link.target])
      if (!resolve(packageRoot, value).startsWith(packageRoot + "/"))
        throw new Error("Unsafe package symlink");
  const probe = createServer();
  await new Promise<void>((r) => probe.listen(0, "127.0.0.1", r));
  const address = probe.address();
  if (!address || typeof address === "string") throw new Error("Missing port");
  const port = address.port;
  await new Promise<void>((r, j) => probe.close((e) => (e ? j(e) : r())));
  const password = randomBytes(24).toString("hex");
  const server = new EmbeddedPostgres({
    databaseDir: directory,
    port,
    user: "devone_test",
    password,
    authMethod: "scram-sha-256",
    persistent: false,
    createPostgresUser: false,
    autoRehydrateSymlinks: true,
    postgresFlags: ["-h", "127.0.0.1", "-k", directory],
    onLog: () => {},
    onError: () => {},
  });
  await server.initialise();
  await server.start();
  const ownedPid = Number(
    (await readFile(join(directory, "postmaster.pid"), "utf8")).split("\n")[0],
  );
  if (!Number.isSafeInteger(ownedPid) || ownedPid <= 1)
    throw new Error("Invalid disposable database process");
  const url = `postgresql://devone_test:${password}@127.0.0.1:${port}/postgres`;
  const db = openDb(url);
  try {
    await migrate(db);
  } catch (error) {
    await db.end();
    await server.stop();
    throw error;
  }
  return {
    db,
    url,
    close: async () => {
      await db.end();
      let alive = true;
      try {
        process.kill(ownedPid, 0);
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code === "ESRCH") alive = false;
        else throw error;
      }
      // Playwright signals the whole process group. The package's stop() waits
      // for a future exit event, so skip it if that child has already exited.
      if (alive) await server.stop();
      await rm(directory, { recursive: true, force: true });
    },
  };
}
