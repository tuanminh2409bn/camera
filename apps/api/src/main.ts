import { loadConfig } from "./config.js";
import { openDb } from "./db.js";
import { buildApp } from "./app.js";
import { HttpAirGateway, HttpMediaGateway } from "./gateways.js";

async function main() {
  const config = loadConfig(),
    db = openDb(config.databaseUrl);
  const lease = await db.connect();
  const exclusive = (
    await lease.query<{ locked: boolean }>(
      "SELECT pg_try_advisory_lock(6400004) AS locked",
    )
  ).rows[0]?.locked;
  if (!exclusive)
    throw new Error("Only one API instance may own native media on this host");
  lease.on("error", () => {
    process.stderr.write("Database ownership lost; stopping service.\n");
    process.exit(1);
  });
  const service = await buildApp(
    config,
    db,
    new HttpMediaGateway(config),
    new HttpAirGateway(config),
  );
  await db.query("SELECT version FROM schema_migrations WHERE version=1");
  await db.query("DELETE FROM playback_sessions");
  await service.app.listen({ host: "127.0.0.1", port: config.port });
  service.startWorker();
  let closing = false;
  async function shutdown(code: number) {
    if (closing) return;
    closing = true;
    clearInterval(watchdog);
    const deadline = setTimeout(() => process.exit(1), 5000);
    deadline.unref();
    await service.app.close();
    lease.release();
    await db.end();
    process.exit(code);
  }
  // The production service manager binds MediaMTX to this process. Losing the
  // ability to reconcile authorization must stop native media, not leave it live.
  const watchdog = setInterval(() => {
    if (!service.healthy()) {
      process.stderr.write(
        "Media authorization worker unavailable; stopping service.\n",
      );
      void shutdown(1);
    }
  }, 1000);
  process.on("SIGTERM", () => {
    void shutdown(0);
  });
  process.on("SIGINT", () => {
    void shutdown(0);
  });
  process.stdout.write("DEV.ONE API listening on loopback.\n");
}
main().catch(() => {
  process.stderr.write(
    "API startup or lifecycle failed; details omitted to protect private configuration.\n",
  );
  process.exit(1);
});
