import Fastify, { type FastifyRequest } from "fastify";
import cookie from "@fastify/cookie";
import { Readable } from "node:stream";
import type { ReadableStream as NodeReadableStream } from "node:stream/web";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import {
  loginInput,
  createViewerInput,
  updateViewerInput,
  pageInput,
  playbackInput,
  recordingInput,
  uuid,
} from "@devone/contracts";
import type { Config } from "./config.js";
import { type Db, transaction, lockMedia, audit } from "./db.js";
import {
  identify,
  requirePermission,
  login,
  logout,
  publicUser,
  type UserRow,
} from "./auth.js";
import { hashPassword, newToken, csrfFor, equalToken } from "./crypto.js";
import { ApiFailure, unauthorized, forbidden, offline } from "./errors.js";
import { MediaService } from "./media.js";
import { RecordingService } from "./recording.js";
import type { MediaGateway, AirGateway } from "./gateways.js";
import { readOperations } from "./operations.js";

export async function buildApp(
  config: Config,
  db: Db,
  mediaGateway: MediaGateway,
  air: AirGateway,
  operations = readOperations,
) {
  const app = Fastify({
    logger: false,
    bodyLimit: 65536,
    trustProxy: ["127.0.0.1", "::1"],
    requestTimeout: 15000,
  });
  const media = new MediaService(db, mediaGateway),
    recording = new RecordingService(db, air);
  const dummyHash = await hashPassword(newToken());
  const cookieName = config.allowInsecureLocalhost
    ? "devone_session"
    : "__Host-devone_session";
  const rawToken = (request: FastifyRequest): string =>
    request.cookies[cookieName] ?? "";
  const authenticate = (request: FastifyRequest) =>
    identify(db, rawToken(request));
  const playbackControllers = new Map<
    string,
    { controller: AbortController; loginId: string; userId: string }
  >();
  await app.register(cookie);
  app.addContentTypeParser(
    "application/sdp",
    { parseAs: "string", bodyLimit: 65536 },
    (_req, body, done) => done(null, body),
  );
  app.setErrorHandler((error, _request, reply) => {
    const failure =
      error instanceof ApiFailure
        ? error
        : error instanceof z.ZodError
          ? new ApiFailure(422, "INVALID_INPUT", "Dữ liệu nhập không hợp lệ.")
          : null;
    if (failure)
      return reply
        .code(failure.status)
        .send({ error: { code: failure.code, message: failure.message } });
    const code =
      typeof error === "object" && error !== null && "code" in error
        ? error.code
        : undefined;
    if (code === "23505")
      return reply.code(409).send({
        error: { code: "CONFLICT", message: "Tên đăng nhập đã tồn tại." },
      });
    if (typeof code === "string" && code.startsWith("FST_ERR_CTP_"))
      return reply
        .code(code === "FST_ERR_CTP_BODY_TOO_LARGE" ? 413 : 400)
        .send({
          error: {
            code: "INVALID_BODY",
            message: "Nội dung yêu cầu không hợp lệ.",
          },
        });
    return reply.code(500).send({
      error: {
        code: "INTERNAL_ERROR",
        message: "Dịch vụ chưa thể xử lý yêu cầu. Vui lòng thử lại.",
      },
    });
  });
  app.addHook("onRequest", async (request, reply) => {
    reply
      .header("Cache-Control", "no-store")
      .header("X-Content-Type-Options", "nosniff")
      .header("Referrer-Policy", "no-referrer");
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
      if (request.headers.origin !== config.origin) throw forbidden();
      if (request.url.split("?")[0] !== "/api/auth/login") {
        const token = rawToken(request),
          csrf = request.headers["x-csrf-token"];
        if (
          !token ||
          typeof csrf !== "string" ||
          !equalToken(csrf, csrfFor(token, config.encryptionKey))
        )
          throw forbidden();
      }
    }
  });
  app.get("/api/health", async () => {
    await db.query("SELECT 1");
    if (Date.now() - mediaHealthyAt >= 15000) throw offline();
    return { status: "ok" };
  });
  app.post("/api/auth/login", async (request, reply) => {
    const result = await login(
      db,
      config,
      loginInput.parse(request.body),
      request.ip,
      dummyHash,
    );
    reply.setCookie(cookieName, result.token, {
      path: "/",
      httpOnly: true,
      secure: !config.allowInsecureLocalhost,
      sameSite: "strict",
      expires: result.identity.expiresAt,
    });
    return {
      user: result.identity.user,
      csrfToken: csrfFor(result.token, config.encryptionKey),
      expiresAt: result.identity.expiresAt.toISOString(),
    };
  });
  app.get("/api/auth/session", async (request) => {
    const identity = await authenticate(request);
    return {
      user: identity.user,
      csrfToken: csrfFor(rawToken(request), config.encryptionKey),
      expiresAt: identity.expiresAt.toISOString(),
    };
  });
  app.post("/api/auth/logout", async (request, reply) => {
    const identity = await authenticate(request);
    await logout(db, identity);
    for (const item of playbackControllers.values())
      if (item.loginId === identity.loginId) item.controller.abort();
    try {
      await media.reconcile();
    } catch {
      /* Durable revocations retry in the worker. */
    }
    reply.clearCookie(cookieName, { path: "/" });
    return reply.code(204).send();
  });
  app.get("/api/admin/users", async (request) => {
    requirePermission(await authenticate(request), "admin");
    const { page, pageSize } = pageInput.parse(request.query);
    const rows = await db.query<UserRow>(
      "SELECT * FROM users ORDER BY created_at,id LIMIT $1 OFFSET $2",
      [pageSize, (page - 1) * pageSize],
    );
    const total =
      (
        await db.query<{ count: number }>(
          "SELECT count(*)::int AS count FROM users",
        )
      ).rows[0]?.count ?? 0;
    return { data: rows.rows.map(publicUser), page, pageSize, total };
  });
  app.post("/api/admin/users", async (request, reply) => {
    const identity = await authenticate(request);
    requirePermission(identity, "admin");
    const input = createViewerInput.parse(request.body),
      id = randomUUID(),
      passwordHash = await hashPassword(input.password);
    const user = await transaction(db, async (tx) => {
      const rows = await tx.query<UserRow>(
        `INSERT INTO users(id,username,password_hash,role,can_live,can_playback,can_download,max_live_sessions)
        VALUES($1,$2,$3,'VIEWER',$4,$5,$6,$7) RETURNING *`,
        [
          id,
          input.username.toLowerCase(),
          passwordHash,
          input.canLive,
          input.canPlayback,
          input.canDownload,
          input.maxLiveSessions,
        ],
      );
      await audit(tx, identity.user.id, "USER_CREATE", id);
      if (!rows.rows[0]) throw new Error("User insert failed");
      return publicUser(rows.rows[0]);
    });
    return reply.code(201).send(user);
  });
  app.patch("/api/admin/users/:id", async (request) => {
    const identity = await authenticate(request);
    requirePermission(identity, "admin");
    const { id } = z.object({ id: uuid }).parse(request.params),
      input = updateViewerInput.parse(request.body);
    const passwordHash = input.password
      ? await hashPassword(input.password)
      : null;
    const user = await transaction(db, async (tx) => {
      await lockMedia(tx);
      const result = await tx.query<UserRow>(
        `UPDATE users SET is_active=COALESCE($2,is_active),can_live=COALESCE($3,can_live),
        can_playback=COALESCE($4,can_playback),can_download=COALESCE($5,can_download),max_live_sessions=COALESCE($6,max_live_sessions),
        password_hash=COALESCE($7,password_hash) WHERE id=$1 AND role='VIEWER' RETURNING *`,
        [
          id,
          input.isActive ?? null,
          input.canLive ?? null,
          input.canPlayback ?? null,
          input.canDownload ?? null,
          input.maxLiveSessions ?? null,
          passwordHash,
        ],
      );
      if (!result.rows[0])
        throw new ApiFailure(
          404,
          "USER_NOT_FOUND",
          "Không tìm thấy tài khoản người xem.",
        );
      await tx.query(
        "UPDATE login_sessions SET revoked_at=now() WHERE user_id=$1 AND revoked_at IS NULL",
        [id],
      );
      await tx.query(
        "UPDATE media_sessions SET state='REVOKING' WHERE user_id=$1",
        [id],
      );
      await tx.query("DELETE FROM playback_sessions WHERE user_id=$1", [id]);
      await audit(tx, identity.user.id, "USER_UPDATE_REVOKE", id);
      return publicUser(result.rows[0]);
    });
    for (const item of playbackControllers.values())
      if (item.userId === id) item.controller.abort();
    try {
      await media.reconcile();
    } catch {
      /* Retried by worker. */
    }
    return user;
  });
  app.post("/api/live/sessions", async (request, reply) => {
    await authenticate(request);
    if (typeof request.body !== "string" || !request.body.startsWith("v=0"))
      throw new ApiFailure(422, "INVALID_SDP", "Yêu cầu video không hợp lệ.");
    const result = await media.create(rawToken(request), request.body);
    return reply
      .code(201)
      .header("Location", `/api/live/sessions/${result.id}`)
      .type("application/sdp")
      .send(result.sdp);
  });
  app.delete("/api/live/sessions/:id", async (request, reply) => {
    const identity = await authenticate(request),
      { id } = z.object({ id: uuid }).parse(request.params);
    await media.revoke(id, identity);
    return reply.code(204).send();
  });
  app.get("/api/admin/sessions", async (request) => {
    requirePermission(await authenticate(request), "admin");
    const { page, pageSize } = pageInput.parse(request.query);
    const result = await db.query(
      `SELECT m.id,u.username,m.state,m.created_at AS "createdAt",m.expires_at AS "expiresAt"
      FROM media_sessions m JOIN users u ON u.id=m.user_id ORDER BY m.created_at,m.id LIMIT $1 OFFSET $2`,
      [pageSize, (page - 1) * pageSize],
    );
    const total =
      (
        await db.query<{ count: number }>(
          "SELECT count(*)::int AS count FROM media_sessions",
        )
      ).rows[0]?.count ?? 0;
    return { data: result.rows, page, pageSize, total, capacity: 200 };
  });
  app.delete("/api/admin/sessions/:id", async (request, reply) => {
    const identity = await authenticate(request);
    requirePermission(identity, "admin");
    const { id } = z.object({ id: uuid }).parse(request.params);
    await media.revoke(id, identity, true);
    return reply.code(204).send();
  });
  app.get("/api/admin/audit", async (request) => {
    requirePermission(await authenticate(request), "admin");
    const { page, pageSize } = pageInput.parse(request.query);
    const result = await db.query(
      'SELECT a.id::text,a.actor_id AS "actorId",u.username AS "actorUsername",a.action,a.target_id AS "targetId",a.created_at AS "createdAt" FROM audit_events a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT $1 OFFSET $2',
      [pageSize, (page - 1) * pageSize],
    );
    const total =
      (
        await db.query<{ count: number }>(
          "SELECT count(*)::int AS count FROM audit_events",
        )
      ).rows[0]?.count ?? 0;
    return { data: result.rows, page, pageSize, total };
  });
  app.get("/api/admin/recording", async (request) => {
    requirePermission(await authenticate(request), "admin");
    return recording.status();
  });
  app.put("/api/admin/recording", async (request) => {
    const identity = await authenticate(request);
    requirePermission(identity, "admin");
    return recording.set(identity, recordingInput.parse(request.body).desired);
  });
  app.get("/api/recordings", async (request) => {
    const identity = await authenticate(request);
    if (!identity.user.canPlayback && !identity.user.canDownload)
      throw forbidden();
    return { data: await air.intervals() };
  });
  app.post("/api/playback/sessions", async (request, reply) => {
    const identity = await authenticate(request),
      input = playbackInput.parse(request.body),
      id = randomUUID();
    requirePermission(identity, input.download ? "canDownload" : "canPlayback");
    await transaction(db, async (tx) => {
      await lockMedia(tx);
      const fresh = await identify(tx, rawToken(request));
      requirePermission(fresh, input.download ? "canDownload" : "canPlayback");
      await tx.query(
        "DELETE FROM playback_sessions WHERE expires_at<=now() AND NOT streaming",
      );
      const count =
        (
          await tx.query<{ count: number }>(
            "SELECT count(*)::int AS count FROM playback_sessions",
          )
        ).rows[0]?.count ?? 0;
      if (count >= config.maxPlaybackSessions)
        throw new ApiFailure(
          409,
          "PLAYBACK_CAPACITY",
          "Đã đủ phiên xem lại. Vui lòng thử lại sau.",
        );
      await tx.query(
        `INSERT INTO playback_sessions(id,user_id,login_id,start_at,duration_seconds,is_download,expires_at)
        VALUES($1,$2,$3,$4,$5,$6,LEAST($7,now()+interval '10 minutes'))`,
        [
          id,
          fresh.user.id,
          fresh.loginId,
          input.start,
          Math.floor(input.duration),
          input.download,
          fresh.expiresAt,
        ],
      );
      await audit(
        tx,
        fresh.user.id,
        input.download ? "DOWNLOAD_START" : "PLAYBACK_START",
        id,
      );
    });
    return reply
      .code(201)
      .send({ id, url: `/api/playback/sessions/${id}/video` });
  });
  app.get("/api/playback/sessions/:id/video", async (request, reply) => {
    const identity = await authenticate(request),
      { id } = z.object({ id: uuid }).parse(request.params);
    const row = (
      await db.query<{
        start_at: Date;
        duration_seconds: number;
        is_download: boolean;
        expires_at: Date;
      }>(
        `UPDATE playback_sessions SET streaming=true
      WHERE id=$1 AND login_id=$2 AND expires_at>now() AND NOT streaming RETURNING *`,
        [id, identity.loginId],
      )
    ).rows[0];
    if (!row)
      throw new ApiFailure(
        404,
        "PLAYBACK_NOT_FOUND",
        "Phiên xem lại không còn khả dụng hoặc đang được sử dụng.",
      );
    const controller = new AbortController();
    playbackControllers.set(id, {
      controller,
      loginId: identity.loginId,
      userId: identity.user.id,
    });
    const abort = () => controller.abort();
    reply.raw.once("close", abort);
    const timer = setTimeout(
      abort,
      Math.max(1, Math.min(330000, row.expires_at.getTime() - Date.now())),
    );
    timer.unref();
    const release = async () => {
      clearTimeout(timer);
      playbackControllers.delete(id);
      reply.raw.off("close", abort);
      await db.query(
        "UPDATE playback_sessions SET streaming=false WHERE id=$1",
        [id],
      );
    };
    try {
      requirePermission(
        identity,
        row.is_download ? "canDownload" : "canPlayback",
      );
      const range = request.headers.range;
      if (range && !/^bytes=\d*-\d*$/.test(range))
        throw new ApiFailure(
          416,
          "INVALID_RANGE",
          "Khoảng dữ liệu không hợp lệ.",
        );
      const response = await air.playback(
        row.start_at.toISOString(),
        row.duration_seconds,
        range,
        controller.signal,
      );
      if (controller.signal.aborted) {
        await response.body?.cancel();
        throw unauthorized();
      }
      if (![200, 206].includes(response.status) || !response.body) {
        await response.body?.cancel();
        throw offline();
      }
      reply.code(response.status).type("video/mp4");
      for (const key of ["content-length", "content-range", "accept-ranges"]) {
        const value = response.headers.get(key);
        if (value) reply.header(key, value);
      }
      if (row.is_download)
        reply.header(
          "Content-Disposition",
          `attachment; filename="camera-${row.start_at.toISOString().replace(/[:.]/g, "-")}.mp4"`,
        );
      const stream = Readable.fromWeb(
        response.body as NodeReadableStream<Uint8Array>,
      );
      stream.once("close", () => {
        void release().catch(() => {});
      });
      controller.signal.addEventListener("abort", () => stream.destroy(), {
        once: true,
      });
      if (controller.signal.aborted) stream.destroy();
      return reply.send(stream);
    } catch (error) {
      controller.abort();
      await release();
      throw error;
    }
  });
  app.delete("/api/playback/sessions/:id", async (request, reply) => {
    const identity = await authenticate(request),
      { id } = z.object({ id: uuid }).parse(request.params);
    const result = await db.query(
      "DELETE FROM playback_sessions WHERE id=$1 AND login_id=$2 RETURNING id",
      [id, identity.loginId],
    );
    if (result.rowCount) playbackControllers.get(id)?.controller.abort();
    return reply.code(204).send();
  });
  let worker: ReturnType<typeof setInterval> | undefined;
  let workerBusy = false;
  let mediaHealthyAt = Date.now();
  let airHealthy = false;
  const tick = async () => {
    if (workerBusy) return;
    workerBusy = true;
    try {
      const results = await Promise.allSettled([
        media.reconcile(),
        recording.reconcile(),
      ]);
      if (results[0]?.status === "fulfilled") mediaHealthyAt = Date.now();
      airHealthy = results[1]?.status === "fulfilled";
      if (playbackControllers.size) {
        try {
          const result = await db.query<{
            id: string;
          }>(`SELECT p.id FROM playback_sessions p JOIN login_sessions s ON s.id=p.login_id
            JOIN users u ON u.id=p.user_id WHERE s.revoked_at IS NULL AND s.expires_at>now() AND p.expires_at>now() AND u.is_active
            AND CASE WHEN p.is_download THEN u.can_download ELSE u.can_playback END`);
          const valid = new Set(result.rows.map((r) => r.id));
          for (const [id, item] of playbackControllers)
            if (!valid.has(id)) item.controller.abort();
        } catch {
          for (const item of playbackControllers.values())
            item.controller.abort();
        }
      }
    } finally {
      workerBusy = false;
    }
  };
  app.addHook("onClose", async () => {
    if (worker) clearInterval(worker);
    for (const item of playbackControllers.values()) item.controller.abort();
  });
  app.get("/api/admin/service-status", async (request) => {
    requirePermission(await authenticate(request), "admin");
    return {
      mediaHealthy: Date.now() - mediaHealthyAt < 15000,
      airHealthy,
      operations: await operations(),
    };
  });
  return {
    app,
    media,
    recording,
    tick,
    healthy: () => Date.now() - mediaHealthyAt < 15000,
    startWorker: () => {
      if (!worker) {
        worker = setInterval(() => {
          void tick().catch(() => {});
        }, 1000);
        worker.unref();
      }
    },
  };
}
