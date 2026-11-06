// Isolated browser fixture: synthetic MediaMTX, disposable PostgreSQL, fake Air.
import { randomUUID } from "node:crypto";
import { mkdir, mkdtemp, writeFile, chmod } from "node:fs/promises";
import { unlinkSync } from "node:fs";
import { resolve, join } from "node:path";
import { spawn } from "node:child_process";
import { testDatabase } from "../../apps/api/tests/database.js";
import { buildApp } from "../../apps/api/src/app.js";
import { operationCodes } from "@devone/contracts";
import { configSchema } from "../../apps/api/src/config.js";
import { hashPassword, encrypt, newToken } from "../../apps/api/src/crypto.js";
import {
  HttpMediaGateway,
  type AirGateway,
} from "../../apps/api/src/gateways.js";

const root = resolve(".local/browser-tests");
await mkdir(root, { recursive: true, mode: 0o700 });
const directory = await mkdtemp(join(root, "run-"));
await chmod(directory, 0o700);
const database = await testDatabase();
const config = configSchema.parse({
  databaseUrl: database.url,
  origin: "http://127.0.0.1:3000",
  encryptionKey: "d".repeat(64),
  mediaOrigin: "http://127.0.0.1:18889",
  mediaApiOrigin: "http://127.0.0.1:19997",
  mediaUser: "browser-test",
  mediaPassword: newToken(),
  airOrigin: "http://127.0.0.1:19996",
  airToken: newToken(),
  allowInsecureLocalhost: true,
});
const accessFile = join(root, "native-access.json");
await writeFile(
  accessFile,
  JSON.stringify({ user: config.mediaUser, password: config.mediaPassword }),
  { mode: 0o600 },
);
const mediaConfig = {
  logLevel: "error",
  api: true,
  apiAddress: "127.0.0.1:19997",
  rtsp: false,
  rtmp: false,
  hls: false,
  srt: false,
  moq: false,
  playback: false,
  metrics: false,
  pprof: false,
  webrtc: true,
  webrtcAddress: "127.0.0.1:18889",
  webrtcLocalUDPAddress: "127.0.0.1:18189",
  webrtcIPsFromInterfaces: false,
  webrtcAdditionalHosts: ["127.0.0.1"],
  webrtcICEServers2: [],
  authMethod: "internal",
  authInternalUsers: [
    {
      user: config.mediaUser,
      pass: config.mediaPassword,
      ips: ["127.0.0.1"],
      permissions: [{ action: "read", path: "live" }, { action: "api" }],
    },
  ],
  paths: {
    live: {
      source: "publisher",
      alwaysAvailable: true,
      alwaysAvailableTracks: [{ codec: "H264" }, { codec: "Opus" }],
      record: false,
      maxReaders: 200,
    },
  },
};
const nativeConfig = join(directory, "mediamtx.json");
await writeFile(nativeConfig, JSON.stringify(mediaConfig), { mode: 0o600 });
const native = spawn(
  resolve(".local/tools/mediamtx-1.21.3/mediamtx"),
  [nativeConfig],
  { stdio: ["ignore", "ignore", "ignore"] },
);
let stopped = false;
const air: AirGateway = {
  async status() {
    return {
      observed: true,
      isOnline: true,
      isPaused: false,
      authLatched: false,
      availableBytes: 90 * 1024 ** 3,
      updatedAt: new Date().toISOString(),
    };
  },
  async setRecording() {},
  async intervals() {
    return [{ start: "2026-11-02T00:00:00Z", duration: 3600 }];
  },
  async playback() {
    return new Response(null, { status: 503 });
  },
};
const app = await buildApp(
  config,
  database.db,
  new HttpMediaGateway(config),
  air,
  async () => ({
    available: true,
    updatedAt: new Date().toISOString(),
    checks: operationCodes.map((code) => ({
      code,
      status: "ok",
      since: null,
      value: null,
    })),
    events: [],
    traffic: null,
  }),
);
for (let i = 0; i < 50; i++) {
  try {
    await new HttpMediaGateway(config).sessions();
    break;
  } catch {
    if (native.exitCode !== null) throw new Error("Synthetic native failed");
    await new Promise((r) => setTimeout(r, 100));
  }
}
const passwordHash = await hashPassword("Browser-fixture-only-123!");
for (const principal of [
  { role: "ADMIN", username: "fixture-admin" },
  { role: "ADMIN", username: "fixture-monitor-admin" },
  { role: "VIEWER", username: "fixture-viewer" },
] as const)
  await database.db.query(
    `INSERT INTO users(id,username,password_hash,role,can_live,can_playback,can_download,totp_secret)
  VALUES($1,$2,$3,$4,true,true,$5,$6)`,
    [
      randomUUID(),
      principal.username,
      passwordHash,
      principal.role,
      principal.role === "ADMIN",
      principal.role === "ADMIN"
        ? encrypt("JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP", config.encryptionKey)
        : null,
    ],
  );
await app.app.listen({ host: "127.0.0.1", port: 3001 });
app.startWorker();
async function stop() {
  if (stopped) return;
  stopped = true;
  // Delete fixture credentials before the embedded database's signal hook can
  // finish process shutdown. This file belongs only to this fixture instance.
  unlinkSync(accessFile);
  await app.app.close();
  native.kill("SIGTERM");
  await database.close();
  process.exit(0);
}
process.on("SIGINT", () => void stop());
process.on("SIGTERM", () => void stop());
process.stdout.write("Isolated browser fixture ready.\n");
