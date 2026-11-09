import { randomUUID } from "node:crypto";
import { MAX_LIVE_SESSIONS, type LiveQuality } from "@devone/contracts";
import { type Db, transaction, lockMedia, audit } from "./db.js";
import { identify, requirePermission, type Identity } from "./auth.js";
import { ApiFailure, unauthorized } from "./errors.js";
import type { MediaGateway } from "./gateways.js";

interface MediaRow {
  id: string;
  login_id: string;
  state: "STARTING" | "ACTIVE" | "REVOKING";
  native_location: string | null;
  created_at: Date;
}
export class MediaService {
  private reconciling = false;
  constructor(
    private db: Db,
    private gateway: MediaGateway,
  ) {}
  async create(
    token: string,
    sdp: string,
    quality: LiveQuality = "source",
  ): Promise<{ id: string; sdp: string }> {
    const id = randomUUID();
    await transaction(this.db, async (tx) => {
      await lockMedia(tx);
      const identity = await identify(tx, token);
      requirePermission(identity, "canLive");
      const counts = (
        await tx.query<{ total: number; own: number }>(
          `SELECT count(*)::int AS total,
        count(*) FILTER(WHERE user_id=$1)::int AS own FROM media_sessions`,
          [identity.user.id],
        )
      ).rows[0];
      if (!counts || counts.total >= MAX_LIVE_SESSIONS)
        throw new ApiFailure(
          409,
          "LIVE_CAPACITY",
          "Đã đủ 200 phiên xem. Vui lòng thử lại sau.",
        );
      if (counts.own >= identity.user.maxLiveSessions)
        throw new ApiFailure(
          409,
          "ACCOUNT_CAPACITY",
          "Tài khoản đã đạt giới hạn phiên xem.",
        );
      await tx.query(
        `INSERT INTO media_sessions(id,user_id,login_id,state,expires_at) VALUES($1,$2,$3,'STARTING',$4)`,
        [id, identity.user.id, identity.loginId, identity.expiresAt],
      );
    });
    try {
      const native = await this.gateway.create(id, sdp, quality);
      // Persist the native handle even if a concurrent logout has revoked this reservation.
      await this.db.query(
        "UPDATE media_sessions SET native_location=$2 WHERE id=$1",
        [id, native.location],
      );
      await transaction(this.db, async (tx) => {
        await lockMedia(tx);
        const identity = await identify(tx, token);
        requirePermission(identity, "canLive");
        const result = await tx.query(
          `UPDATE media_sessions SET state='ACTIVE' WHERE id=$1 AND login_id=$2 AND state='STARTING' RETURNING id`,
          [id, identity.loginId],
        );
        if (result.rowCount !== 1) throw unauthorized();
      });
      return { id, sdp: native.sdp };
    } catch (error) {
      await this.db.query(
        "UPDATE media_sessions SET state='REVOKING' WHERE id=$1",
        [id],
      );
      // An upstream timeout may have created a native session. Keep the slot
      // until reconcile confirms closure; never blindly delete the reservation.
      throw error;
    }
  }
  async revoke(id: string, identity: Identity, admin = false): Promise<void> {
    const result = await transaction(this.db, async (tx) => {
      await lockMedia(tx);
      const result = await tx.query<MediaRow>(
        `UPDATE media_sessions SET state='REVOKING'
        WHERE id=$1 AND ($2::boolean OR login_id=$3) RETURNING *`,
        [id, admin, identity.loginId],
      );
      if (result.rows[0])
        await audit(
          tx,
          identity.user.id,
          admin ? "ADMIN_KICK" : "LIVE_CLOSE",
          id,
        );
      return result.rows[0];
    });
    if (result?.native_location) {
      try {
        await this.gateway.close(result.native_location);
      } catch {
        /* Durable REVOKING state is retried by reconciliation. */
      }
    }
    await this.reconcile();
  }
  async reconcile(): Promise<void> {
    if (this.reconciling) return;
    this.reconciling = true;
    try {
      await this.db
        .query(`UPDATE media_sessions m SET state='REVOKING' FROM login_sessions s,users u
        WHERE m.login_id=s.id AND m.user_id=u.id AND (s.revoked_at IS NOT NULL OR s.expires_at<=now() OR NOT u.is_active OR NOT u.can_live)`);
      const native = await this.gateway.sessions();
      const rows = (
        await this.db.query<MediaRow>("SELECT * FROM media_sessions")
      ).rows;
      const byId = new Map(rows.map((row) => [row.id, row]));
      // The server's live path belongs exclusively to this application.
      // Unknown native readers also consume capacity and must be closed.
      for (let offset = 0; offset < native.length; offset += 10) {
        await Promise.all(
          native.slice(offset, offset + 10).map(async (item) => {
            const row = item.appSession ? byId.get(item.appSession) : undefined;
            if (
              !row ||
              row.state === "REVOKING" ||
              (row.state === "STARTING" &&
                Date.now() - row.created_at.getTime() > 15000)
            )
              await this.gateway.kick(item.id);
          }),
        );
      }
      const remaining = await this.gateway.sessions();
      const active = new Set(remaining.map((item) => item.appSession));
      await transaction(this.db, async (tx) => {
        await lockMedia(tx);
        for (const row of rows) {
          if (active.has(row.id)) continue;
          // Never release a request that could still be completing its POST.
          if (
            !row.native_location &&
            Date.now() - row.created_at.getTime() < 15000
          )
            continue;
          await tx.query(
            "DELETE FROM media_sessions WHERE id=$1 AND (native_location IS NOT NULL OR created_at<now()-interval '15 seconds')",
            [row.id],
          );
        }
      });
    } finally {
      this.reconciling = false;
    }
  }
}
