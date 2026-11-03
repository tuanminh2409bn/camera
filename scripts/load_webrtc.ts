/** Opt-in media load harness. One shard owns at most 25 real browser peers. */
import { chromium, type BrowserContext, type Page } from "@playwright/test";
import { readPrivateJson } from "../apps/api/src/config.js";
import { z } from "zod";
import { mkdir, mkdtemp, appendFile } from "node:fs/promises";
import { join, resolve } from "node:path";

const input = z
  .object({
    origin: z.url(),
    startAt: z.iso.datetime({ offset: true }),
    durationSeconds: z.number().int().min(60).max(28800),
    accounts: z
      .array(z.object({ username: z.string(), password: z.string() }))
      .min(1)
      .max(25),
  })
  .strict();
if (process.argv[2] !== "--run" || !process.argv[3])
  throw new Error(
    "Usage: tsx scripts/load_webrtc.ts --run PRIVATE_SHARD_CONFIG_JSON",
  );
const config = input.parse(readPrivateJson(process.argv[3]));
const scheduled = Date.parse(config.startAt);
if (scheduled < Date.now() + 60000 || scheduled > Date.now() + 3600000)
  throw new Error(
    "Use one shared startAt between 1 and 60 minutes in the future for every shard",
  );
const origin = new URL(config.origin);
if (
  origin.username ||
  origin.password ||
  origin.pathname !== "/" ||
  origin.search ||
  origin.hash ||
  origin.protocol !== "https:"
)
  throw new Error("An authorized HTTPS origin is required");
const root = resolve(".local/load-tests");
await mkdir(root, { recursive: true, mode: 0o700 });
const directory = await mkdtemp(join(root, "shard-"));
const output = join(directory, "metrics.jsonl");
const browser = await chromium.launch({ channel: "chrome", headless: true });
const viewers: Array<{
  context: BrowserContext;
  page: Page;
  previousBytes: number;
  previousFrames: number;
}> = [];
let interrupted = false;
process.on("SIGINT", () => {
  interrupted = true;
});
process.on("SIGTERM", () => {
  interrupted = true;
});
let failure = false;
try {
  for (const account of config.accounts) {
    if (interrupted) break;
    const context = await browser.newContext();
    const page = await context.newPage();
    viewers.push({ context, page, previousBytes: 0, previousFrames: 0 });
    // Track the product's actual peer without changing its SDP/transport.
    await page.addInitScript(() => {
      const Original = window.RTCPeerConnection;
      const peers: RTCPeerConnection[] = [];
      Object.defineProperty(window, "loadPeers", { value: peers });
      window.RTCPeerConnection = class extends Original {
        constructor(configuration?: RTCConfiguration) {
          super(configuration);
          peers.push(this);
        }
      };
    });
    await page.goto(origin.origin);
    await page
      .getByLabel("Tên đăng nhập", { exact: true })
      .fill(account.username);
    await page.getByLabel("Mật khẩu", { exact: true }).fill(account.password);
    await page.getByRole("button", { name: "Đăng nhập", exact: false }).click();
    await page
      .getByRole("button", { name: "Kết nối camera", exact: false })
      .click();
    await page.waitForFunction(
      () => {
        const video = document.querySelector("video");
        return video && video.getVideoPlaybackQuality().totalVideoFrames > 5;
      },
      {},
      { timeout: 30000 },
    );
  }
  if (Date.now() >= scheduled)
    throw new Error("Shard missed the shared start barrier");
  await appendFile(
    output,
    JSON.stringify({
      event: "ready",
      at: new Date().toISOString(),
      startAt: config.startAt,
      peers: viewers.length,
      durationSeconds: config.durationSeconds,
    }) + "\n",
    { mode: 0o600 },
  );
  while (!interrupted && Date.now() < scheduled)
    await new Promise((r) =>
      setTimeout(r, Math.min(1000, scheduled - Date.now())),
    );
  const started = scheduled;
  while (!interrupted && Date.now() - started < config.durationSeconds * 1000) {
    await new Promise((r) => setTimeout(r, 5000));
    const peers = await Promise.all(
      viewers.map(async (viewer, index) => {
        const stats = await viewer.page.evaluate(async () => {
          const connections = (
            window as unknown as { loadPeers: RTCPeerConnection[] }
          ).loadPeers;
          const connection = connections[connections.length - 1];
          if (!connection)
            return {
              state: "missing",
              bytes: 0,
              frames: 0,
              packetsLost: 0,
              freezeCount: 0,
            };
          const result = {
            state: connection.connectionState,
            bytes: 0,
            frames: 0,
            packetsLost: 0,
            freezeCount: 0,
          };
          (await connection.getStats()).forEach((report) => {
            if (report.type === "inbound-rtp" && report.kind === "video") {
              result.bytes += report.bytesReceived ?? 0;
              result.frames += report.framesDecoded ?? 0;
              result.packetsLost += report.packetsLost ?? 0;
              result.freezeCount += report.freezeCount ?? 0;
            }
          });
          return result;
        });
        const advancing =
          stats.state === "connected" &&
          stats.bytes > viewer.previousBytes &&
          stats.frames > viewer.previousFrames;
        viewer.previousBytes = stats.bytes;
        viewer.previousFrames = stats.frames;
        if (!advancing) failure = true;
        return { peer: index, ...stats, advancing };
      }),
    );
    await appendFile(
      output,
      JSON.stringify({
        at: new Date().toISOString(),
        elapsedSeconds: (Date.now() - started) / 1000,
        peers,
      }) + "\n",
      { mode: 0o600 },
    );
  }
  if (interrupted) failure = true;
} catch {
  failure = true;
  process.stderr.write(
    "Load shard failed; inspect private metrics and server health. No credentials logged.\n",
  );
} finally {
  for (const viewer of viewers) {
    try {
      await viewer.page
        .getByRole("button", { name: "Dừng xem", exact: true })
        .click({ timeout: 3000 });
      await viewer.page
        .getByRole("button", { name: "Đăng xuất", exact: true })
        .click({ timeout: 3000 });
    } catch {}
    await viewer.context.close();
  }
  await browser.close();
}
process.stdout.write(
  JSON.stringify({
    result: failure ? "FAIL" : "PASS",
    peers: viewers.length,
    metrics: output,
    scope: "this shard only; not aggregate 200-peer acceptance",
  }) + "\n",
);
process.exitCode = failure ? 1 : 0;
