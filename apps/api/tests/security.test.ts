import { test, before, after, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { TOTP, Secret } from "otpauth";
import { testDatabase } from "./database.js";
import { configSchema } from "../src/config.js";
import { buildApp } from "../src/app.js";
import { hashPassword, hashToken, newToken, encrypt } from "../src/crypto.js";
import { identify, logout } from "../src/auth.js";
import type {
  MediaGateway,
  AirGateway,
  NativeSession,
} from "../src/gateways.js";

class Media implements MediaGateway {
  peers = new Map<string, string>();
  qualities: string[] = [];
  standardOnline = true;
  fail = false;
  wait: Promise<void> | null = null;
  async standardReady() {
    return this.standardOnline;
  }
  async create(id: string, _sdp: string, quality?: string) {
    if (quality) this.qualities.push(quality);
    if (this.wait) await this.wait;
    const native = randomUUID();
    this.peers.set(native, id);
    if (this.fail) throw new Error("Lost native response");
    return { sdp: "v=0\r\n", location: `/live/whep/${native}` };
  }
  async close(location: string) {
    this.peers.delete(location.split("/").pop() ?? "");
  }
  async sessions(): Promise<NativeSession[]> {
    return [...this.peers].map(([id, appSession]) => ({ id, appSession }));
  }
  async kick(id: string) {
    this.peers.delete(id);
  }
}
class Air implements AirGateway {
  online = true;
  paused = false;
  latched = false;
  observed = true;
  writes: boolean[] = [];
  async status() {
    if (!this.online) throw new Error("Offline");
    return {
      observed: this.observed,
      isOnline: true,
      isPaused: this.paused,
      authLatched: this.latched,
      availableBytes: 30 * 1024 ** 3,
      updatedAt: new Date().toISOString(),
    };
  }
  async setRecording(desired: boolean) {
    this.writes.push(desired);
    this.observed = desired;
  }
  async intervals() {
    if (!this.online) throw new Error("Offline");
    return [{ start: "2026-11-02T00:00:00Z", duration: 60 }];
  }
  async playback() {
    return new Response("synthetic-mp4", {
      headers: { "Accept-Ranges": "none" },
    });
  }
}
const config = configSchema.parse({
  databaseUrl: "unused",
  origin: "http://127.0.0.1:3000",
  encryptionKey: "a".repeat(64),
  mediaOrigin: "http://127.0.0.1:8889",
  mediaApiOrigin: "http://127.0.0.1:9997",
  mediaUser: "backend",
  mediaPassword: "b".repeat(32),
  airOrigin: "http://127.0.0.1:19996",
  airToken: "c".repeat(32),
  allowInsecureLocalhost: true,
});
let database: Awaited<ReturnType<typeof testDatabase>>,
  service: Awaited<ReturnType<typeof buildApp>>,
  media: Media,
  air: Air,
  passwordHash: string;
const password = "Local-test-password-123!";
const totpSecret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP";
async function user(
  admin = false,
  permissions = { live: true, playback: true, download: false },
) {
  const id = randomUUID(),
    name = "user-" + id.slice(0, 8),
    token = newToken(),
    loginId = randomUUID();
  await database.db.query(
    `INSERT INTO users(id,username,password_hash,role,can_live,can_playback,can_download,totp_secret)
    VALUES($1,$2,$3,$4,$5,$6,$7,$8)`,
    [
      id,
      name,
      passwordHash,
      admin ? "ADMIN" : "VIEWER",
      permissions.live,
      permissions.playback,
      permissions.download,
      admin ? encrypt(totpSecret, config.encryptionKey) : null,
    ],
  );
  await database.db.query(
    "INSERT INTO login_sessions(id,token_hash,user_id,expires_at) VALUES($1,$2,$3,now()+interval '1 hour')",
    [loginId, hashToken(token), id],
  );
  const session = await service.app.inject({
    url: "/api/auth/session",
    cookies: { devone_session: token },
  });
  return {
    id,
    name,
    token,
    loginId,
    headers: {
      origin: config.origin,
      "x-csrf-token": session.json().csrfToken as string,
    },
    cookies: { devone_session: token },
  };
}
before(async () => {
  database = await testDatabase();
  passwordHash = await hashPassword(password);
});
beforeEach(async () => {
  if (service) await service.app.close();
  await database.db.query("TRUNCATE users,audit_events,auth_limits CASCADE");
  await database.db.query(
    "INSERT INTO recording_intent(id,desired) VALUES(1,true) ON CONFLICT(id) DO UPDATE SET desired=true,revision=0,actor_id=NULL",
  );
  media = new Media();
  air = new Air();
  service = await buildApp(config, database.db, media, air);
});
after(async () => {
  if (service) await service.app.close();
  if (database) await database.close();
});
test("operational status is Admin-only and never reads private status for a viewer", async () => {
  await service.app.close();
  let reads = 0;
  service = await buildApp(config, database.db, media, air, async () => {
    reads++;
    return { available: false, reason: "stale" };
  });
  const admin = await user(true),
    viewer = await user();
  assert.equal(
    (await service.app.inject({ url: "/api/admin/service-status" })).statusCode,
    401,
  );
  assert.equal(
    (
      await service.app.inject({
        url: "/api/admin/service-status",
        cookies: viewer.cookies,
      })
    ).statusCode,
    403,
  );
  assert.equal(reads, 0);
  const response = await service.app.inject({
    url: "/api/admin/service-status",
    cookies: admin.cookies,
  });
  assert.equal(response.statusCode, 200);
  assert.equal(reads, 1);
  assert.deepEqual(response.json().operations, {
    available: false,
    reason: "stale",
  });
  assert.doesNotMatch(response.body, /status\.json|password|token|\/var\//);
});

test("auth cookies, MFA replay, current permissions, CSRF and safe errors", async () => {
  const admin = await user(true),
    viewer = await user();
  const missing = await service.app.inject({ url: "/api/admin/users" });
  assert.equal(missing.statusCode, 401);
  const forbidden = await service.app.inject({
    url: "/api/admin/users",
    cookies: viewer.cookies,
  });
  assert.equal(forbidden.statusCode, 403);
  const csrf = await service.app.inject({
    method: "POST",
    url: "/api/auth/logout",
    cookies: viewer.cookies,
    headers: { origin: config.origin },
  });
  assert.equal(csrf.statusCode, 403);
  const otp = new TOTP({ secret: Secret.fromBase32(totpSecret) }).generate();
  const auth = () =>
    service.app.inject({
      method: "POST",
      url: "/api/auth/login",
      headers: { origin: config.origin },
      payload: { username: admin.name, password, otp },
    });
  const first = await auth();
  assert.equal(first.statusCode, 200);
  assert.match(
    String(first.headers["set-cookie"]),
    /HttpOnly; SameSite=Strict/i,
  );
  assert.equal((await auth()).statusCode, 401);
  const updated = await service.app.inject({
    method: "PATCH",
    url: "/api/admin/users/" + viewer.id,
    headers: admin.headers,
    cookies: admin.cookies,
    payload: { isActive: false },
  });
  assert.equal(updated.statusCode, 200);
  assert.equal(
    (
      await service.app.inject({
        url: "/api/auth/session",
        cookies: viewer.cookies,
      })
    ).statusCode,
    401,
  );
  assert.doesNotMatch(first.body, /password_hash|totp_secret|token_hash/);
});
test("200 concurrent reservations admitted, 201st rejected, independent of native timing", async () => {
  const viewers = await Promise.all(Array.from({ length: 201 }, () => user()));
  const results = await Promise.allSettled(
    viewers.map((v) => service.media.create(v.token, "v=0\r\n")),
  );
  assert.equal(results.filter((r) => r.status === "fulfilled").length, 200);
  const failed = results.filter((r) => r.status === "rejected");
  assert.equal(failed.length, 1);
  if (failed[0]?.status === "rejected")
    assert.equal(failed[0].reason.code, "LIVE_CAPACITY");
  assert.equal(media.peers.size, 200);
});
test("live quality shares permissions and quota and preserves the default route", async () => {
  await service.app.close();
  service = await buildApp(
    { ...config, standardLiveEnabled: true },
    database.db,
    media,
    air,
  );
  const viewer = await user();
  const denied = await user(false, {
    live: false,
    playback: true,
    download: false,
  });
  const list = (principal: typeof viewer) =>
    service.app.inject({
      url: "/api/live/qualities",
      cookies: principal.cookies,
    });
  const open = (principal: typeof viewer, query = "") =>
    service.app.inject({
      method: "POST",
      url: "/api/live/sessions" + query,
      headers: { ...principal.headers, "content-type": "application/sdp" },
      cookies: principal.cookies,
      payload: "v=0\r\n",
    });
  assert.equal((await list(denied)).statusCode, 403);
  assert.deepEqual((await list(viewer)).json(), {
    qualities: ["standard", "source"],
  });
  assert.equal((await open(denied, "?quality=standard")).statusCode, 403);
  assert.equal((await open(viewer, "?quality=other")).statusCode, 422);
  assert.equal(
    (await open(viewer, "?quality=standard&quality=source")).statusCode,
    422,
  );
  assert.equal((await open(viewer)).statusCode, 201);
  media.standardOnline = false;
  assert.deepEqual((await list(viewer)).json(), { qualities: ["source"] });
  assert.equal(
    (await open(viewer, "?quality=standard")).json().error.code,
    "LIVE_QUALITY_UNAVAILABLE",
  );
  media.standardOnline = true;
  const standard = await open(viewer, "?quality=standard");
  assert.equal(standard.statusCode, 201);
  assert.match(
    String(standard.headers.location),
    /^\/api\/live\/sessions\/[a-f0-9-]{36}$/,
  );
  assert.equal(
    (await open(viewer, "?quality=source")).json().error.code,
    "ACCOUNT_CAPACITY",
  );
  assert.deepEqual(media.qualities, ["source", "standard"]);
});
test("logout during native creation cannot activate an unauthorized stream", async () => {
  const viewer = await user();
  let release: () => void = () => {};
  media.wait = new Promise<void>((r) => {
    release = r;
  });
  const result = service.media.create(viewer.token, "v=0").then(
    () => null,
    (e) => e,
  );
  for (let i = 0; i < 100; i++) {
    if ((await database.db.query("SELECT 1 FROM media_sessions")).rowCount)
      break;
    await new Promise((r) => setTimeout(r, 5));
  }
  await logout(database.db, await identify(database.db, viewer.token));
  release();
  assert.equal((await result).status, 401);
  await service.media.reconcile();
  assert.equal(media.peers.size, 0);
});
test("lost POST response retains capacity until the native orphan is confirmed closed", async () => {
  const viewer = await user();
  media.fail = true;
  await assert.rejects(service.media.create(viewer.token, "v=0"));
  assert.equal(media.peers.size, 1);
  assert.equal(
    (await database.db.query("SELECT state FROM media_sessions")).rows[0].state,
    "REVOKING",
  );
  await service.media.reconcile();
  assert.equal(media.peers.size, 0);
  assert.equal(
    (await database.db.query("SELECT 1 FROM media_sessions")).rowCount,
    1,
  );
  await database.db.query(
    "UPDATE media_sessions SET created_at=now()-interval '20 seconds'",
  );
  await service.media.reconcile();
  assert.equal(
    (await database.db.query("SELECT 1 FROM media_sessions")).rowCount,
    0,
  );
});
test("viewer cannot download; playback binds to login and preserves native no-range response", async () => {
  const viewer = await user(),
    other = await user();
  const create = (download: boolean) =>
    service.app.inject({
      method: "POST",
      url: "/api/playback/sessions",
      headers: viewer.headers,
      cookies: viewer.cookies,
      payload: { start: "2026-11-02T00:00:00Z", duration: 60, download },
    });
  assert.equal((await create(true)).statusCode, 403);
  const session = await create(false);
  assert.equal(session.statusCode, 201);
  assert.equal(
    (
      await service.app.inject({
        url: session.json().url,
        cookies: other.cookies,
      })
    ).statusCode,
    404,
  );
  const video = await service.app.inject({
    url: session.json().url,
    cookies: viewer.cookies,
    headers: { range: "bytes=0-" },
  });
  assert.equal(video.statusCode, 200);
  assert.equal(video.headers["accept-ranges"], "none");
  assert.equal(video.body, "synthetic-mp4");
});
test("recording observes existing Air on first install; offline desired survives and safety guard wins", async () => {
  const admin = await user(true),
    identity = await identify(database.db, admin.token);
  air.observed = false;
  await service.recording.reconcile();
  assert.deepEqual(air.writes, []);
  air.online = false;
  const state = await service.recording.set(identity, false);
  assert.equal(state.isOnline, false);
  assert.equal(state.desired, false);
  air.online = true;
  air.observed = true;
  await service.recording.reconcile();
  assert.deepEqual(air.writes, [false]);
  air.paused = true;
  await assert.rejects(service.recording.set(identity, true), {
    code: "AIR_SAFETY_STOP",
  });
  assert.deepEqual(air.writes, [false]);
});

test("logout aborts an already streaming playback on a real HTTP connection", async () => {
  const viewer = await user();
  let cancelled = false;
  air.playback = async () =>
    new Response(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode("first-video-chunk"));
        },
        cancel() {
          cancelled = true;
        },
      }),
    );
  const created = await service.app.inject({
    method: "POST",
    url: "/api/playback/sessions",
    headers: viewer.headers,
    cookies: viewer.cookies,
    payload: { start: "2026-11-02T00:00:00Z", duration: 60 },
  });
  assert.equal(created.statusCode, 201);
  const origin = await service.app.listen({ host: "127.0.0.1", port: 0 });
  const response = await fetch(origin + created.json().url, {
    headers: { Cookie: "devone_session=" + viewer.token },
    signal: AbortSignal.timeout(5000),
  });
  assert.equal(response.status, 200);
  const reader = response.body?.getReader();
  assert.ok(reader);
  assert.equal(
    new TextDecoder().decode((await reader.read()).value),
    "first-video-chunk",
  );
  const loggedOut = await service.app.inject({
    method: "POST",
    url: "/api/auth/logout",
    headers: viewer.headers,
    cookies: viewer.cookies,
  });
  assert.equal(loggedOut.statusCode, 204);
  const finished = await reader.read().then(
    (result) => result.done,
    () => true,
  );
  assert.equal(finished, true);
  assert.equal(cancelled, true);
});

test("expiry, account limits and disabled permission prevent admission", async () => {
  const viewer = await user();
  await service.media.create(viewer.token, "v=0");
  await service.media.create(viewer.token, "v=0");
  await assert.rejects(service.media.create(viewer.token, "v=0"), {
    code: "ACCOUNT_CAPACITY",
  });
  await database.db.query(
    "UPDATE login_sessions SET expires_at=now()-interval '1 second' WHERE id=$1",
    [viewer.loginId],
  );
  await assert.rejects(service.media.create(viewer.token, "v=0"), {
    status: 401,
  });
  await service.media.reconcile();
  assert.equal(media.peers.size, 0);
  const noLive = await user(false, {
    live: false,
    playback: true,
    download: false,
  });
  await assert.rejects(service.media.create(noLive.token, "v=0"), {
    status: 403,
  });
});
test("confirmed native closure immediately frees the account slot for reconnect", async () => {
  const viewer = await user(),
    identity = await identify(database.db, viewer.token);
  for (let attempt = 0; attempt < 3; attempt++) {
    const session = await service.media.create(viewer.token, "v=0");
    await service.media.revoke(session.id, identity);
    assert.equal(media.peers.size, 0);
    assert.equal(
      (await database.db.query("SELECT 1 FROM media_sessions")).rowCount,
      0,
    );
  }
});
