import {
  randomBytes,
  createHash,
  createHmac,
  timingSafeEqual,
  createCipheriv,
  createDecipheriv,
} from "node:crypto";
import argon2 from "argon2";
import { TOTP, Secret } from "otpauth";
import { ApiFailure } from "./errors.js";

let passwordWork = 0;
const passwordQueue: Array<() => void> = [];
async function boundedPassword<T>(work: () => Promise<T>): Promise<T> {
  if (passwordWork >= 4) {
    if (passwordQueue.length >= 256)
      throw new ApiFailure(
        503,
        "AUTH_BUSY",
        "Đang có nhiều người đăng nhập. Vui lòng thử lại.",
      );
    await new Promise<void>((resolve) => passwordQueue.push(resolve));
  } else passwordWork++;
  try {
    return await work();
  } finally {
    const next = passwordQueue.shift();
    if (next) next();
    else passwordWork--;
  }
}

export const hashToken = (value: string): string =>
  createHash("sha256").update(value).digest("hex");
export const newToken = (): string => randomBytes(32).toString("base64url");
export const hashPassword = (value: string): Promise<string> =>
  boundedPassword(() =>
    argon2.hash(value, {
      type: argon2.argon2id,
      memoryCost: 65536,
      timeCost: 3,
      parallelism: 1,
    }),
  );
export const verifyPassword = (hash: string, value: string): Promise<boolean> =>
  boundedPassword(() => argon2.verify(hash, value));
export function equalToken(a: string, b: string): boolean {
  const av = Buffer.from(a),
    bv = Buffer.from(b);
  return av.length === bv.length && timingSafeEqual(av, bv);
}
export const csrfFor = (token: string, key: string): string =>
  createHmac("sha256", Buffer.from(key, "hex"))
    .update("csrf:" + token)
    .digest("base64url");
export function encrypt(value: string, key: string): string {
  const iv = randomBytes(12),
    cipher = createCipheriv("aes-256-gcm", Buffer.from(key, "hex"), iv);
  const body = Buffer.concat([cipher.update(value, "utf8"), cipher.final()]);
  return Buffer.concat([iv, cipher.getAuthTag(), body]).toString("base64url");
}
export function decrypt(value: string, key: string): string {
  const data = Buffer.from(value, "base64url");
  const decipher = createDecipheriv(
    "aes-256-gcm",
    Buffer.from(key, "hex"),
    data.subarray(0, 12),
  );
  decipher.setAuthTag(data.subarray(12, 28));
  return Buffer.concat([
    decipher.update(data.subarray(28)),
    decipher.final(),
  ]).toString("utf8");
}
export function totpStep(
  secret: string,
  code: string,
  now = Date.now(),
): number | null {
  const totp = new TOTP({
    secret: Secret.fromBase32(secret),
    algorithm: "SHA1",
    digits: 6,
    period: 30,
  });
  const delta = totp.validate({ token: code, timestamp: now, window: 1 });
  return delta === null ? null : Math.floor(now / 30000) + delta;
}
