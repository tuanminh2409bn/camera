import { randomUUID } from "node:crypto";
import type { User } from "@devone/contracts";
import type { Config } from "./config.js";
import { type Db, type Tx, transaction, lockMedia, audit } from "./db.js";
import { ApiFailure, unauthorized, forbidden } from "./errors.js";
import {
  hashToken,
  newToken,
  verifyPassword,
  decrypt,
  totpStep,
} from "./crypto.js";

export interface UserRow {
  id: string;
  username: string;
  password_hash: string;
  role: "ADMIN" | "VIEWER";
  is_active: boolean;
  can_live: boolean;
  can_playback: boolean;
  can_download: boolean;
  max_live_sessions: number;
  totp_secret: string | null;
  last_totp_step: string;
}
export interface Identity {
  user: User;
  loginId: string;
  expiresAt: Date;
}
export function publicUser(row: UserRow): User {
  return {
    id: row.id,
    username: row.username,
    role: row.role,
    isActive: row.is_active,
    canLive: row.can_live,
    canPlayback: row.can_playback,
    canDownload: row.can_download,
    maxLiveSessions: row.max_live_sessions,
  };
}
export async function identify(db: Db | Tx, token: string): Promise<Identity> {
  if (!/^[A-Za-z0-9_-]{43}$/.test(token)) throw unauthorized();
  const result = await db.query<
    UserRow & { login_id: string; expires_at: Date }
  >(
    `SELECT u.*, s.id AS login_id, s.expires_at FROM login_sessions s JOIN users u ON u.id=s.user_id
     WHERE s.token_hash=$1 AND s.revoked_at IS NULL AND s.expires_at>now() AND u.is_active`,
    [hashToken(token)],
  );
  const row = result.rows[0];
  if (!row) throw unauthorized();
  return {
    user: publicUser(row),
    loginId: row.login_id,
    expiresAt: row.expires_at,
  };
}
export function requirePermission(
  identity: Identity,
  permission: "canLive" | "canPlayback" | "canDownload" | "admin",
): void {
  if (
    permission === "admin"
      ? identity.user.role !== "ADMIN"
      : !identity.user[permission]
  )
    throw forbidden();
}
export async function rateLimitLogin(
  db: Db,
  ip: string,
  username: string,
): Promise<void> {
  // Shared PostgreSQL counters also apply if the API later has multiple workers.
  for (const [key, limit] of [
    [`ip:${ip}`, 1000],
    [`user:${username.toLowerCase()}`, 10],
  ] as const) {
    const result = await db.query<{ attempts: number }>(
      `INSERT INTO auth_limits(key,attempts,resets_at) VALUES($1,1,now()+interval '15 minutes')
       ON CONFLICT(key) DO UPDATE SET attempts=CASE WHEN auth_limits.resets_at<=now() THEN 1 ELSE auth_limits.attempts+1 END,
       resets_at=CASE WHEN auth_limits.resets_at<=now() THEN now()+interval '15 minutes' ELSE auth_limits.resets_at END RETURNING attempts`,
      [hashToken(key)],
    );
    if ((result.rows[0]?.attempts ?? limit + 1) > limit)
      throw new ApiFailure(
        429,
        "LOGIN_RATE_LIMIT",
        "Đã thử đăng nhập quá nhiều lần. Vui lòng thử lại sau 15 phút.",
      );
  }
}
export async function login(
  db: Db,
  config: Config,
  input: { username: string; password: string; otp?: string },
  ip: string,
  dummyHash: string,
): Promise<{ token: string; identity: Identity }> {
  await rateLimitLogin(db, ip, input.username);
  const row = (
    await db.query<UserRow>("SELECT * FROM users WHERE username=$1", [
      input.username.toLowerCase(),
    ])
  ).rows[0];
  const matches = await verifyPassword(
    row?.password_hash ?? dummyHash,
    input.password,
  );
  if (!matches || !row?.is_active)
    throw new ApiFailure(
      401,
      "LOGIN_FAILED",
      "Tên đăng nhập, mật khẩu hoặc mã xác thực không đúng.",
    );
  let step: number | null = null;
  if (row.role === "ADMIN") {
    step =
      row.totp_secret && input.otp
        ? totpStep(decrypt(row.totp_secret, config.encryptionKey), input.otp)
        : null;
    if (step === null)
      throw new ApiFailure(
        401,
        "LOGIN_FAILED",
        "Tên đăng nhập, mật khẩu hoặc mã xác thực không đúng.",
      );
  }
  const token = newToken();
  return transaction(db, async (tx) => {
    await lockMedia(tx);
    const current = (
      await tx.query<UserRow>("SELECT * FROM users WHERE id=$1 FOR UPDATE", [
        row.id,
      ])
    ).rows[0];
    if (
      !current?.is_active ||
      current.password_hash !== row.password_hash ||
      current.totp_secret !== row.totp_secret
    )
      throw unauthorized();
    if (current.role === "ADMIN") {
      if (step === null || step <= Number(current.last_totp_step))
        throw new ApiFailure(
          401,
          "LOGIN_FAILED",
          "Tên đăng nhập, mật khẩu hoặc mã xác thực không đúng.",
        );
      await tx.query("UPDATE users SET last_totp_step=$2 WHERE id=$1", [
        row.id,
        step,
      ]);
    }
    // Bound stored login sessions per account; evicted logins revoke their media too.
    await tx.query(
      `UPDATE login_sessions SET revoked_at=now() WHERE id IN
      (SELECT id FROM login_sessions WHERE user_id=$1 AND revoked_at IS NULL ORDER BY created_at DESC OFFSET 4)`,
      [row.id],
    );
    await tx.query(
      `UPDATE media_sessions SET state='REVOKING' WHERE login_id IN
      (SELECT id FROM login_sessions WHERE user_id=$1 AND revoked_at IS NOT NULL)`,
      [row.id],
    );
    const id = randomUUID();
    const result = await tx.query<{ expires_at: Date }>(
      `INSERT INTO login_sessions(id,token_hash,user_id,expires_at)
      VALUES($1,$2,$3,now()+($4 * interval '1 hour')) RETURNING expires_at`,
      [
        id,
        hashToken(token),
        row.id,
        current.role === "ADMIN"
          ? Math.min(config.loginHours, 8)
          : config.loginHours,
      ],
    );
    const expiresAt = result.rows[0]?.expires_at;
    if (!expiresAt) throw new Error("Session insert failed");
    await audit(tx, row.id, "LOGIN");
    return {
      token,
      identity: { user: publicUser(current), loginId: id, expiresAt },
    };
  });
}
export async function logout(db: Db, identity: Identity): Promise<void> {
  await transaction(db, async (tx) => {
    await lockMedia(tx);
    await tx.query("UPDATE login_sessions SET revoked_at=now() WHERE id=$1", [
      identity.loginId,
    ]);
    await tx.query(
      "UPDATE media_sessions SET state='REVOKING' WHERE login_id=$1",
      [identity.loginId],
    );
    await tx.query("DELETE FROM playback_sessions WHERE login_id=$1", [
      identity.loginId,
    ]);
    await audit(tx, identity.user.id, "LOGOUT");
  });
}
