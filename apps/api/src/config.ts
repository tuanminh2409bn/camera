import { readFileSync, lstatSync } from "node:fs";
import { z } from "zod";

const loopbackUrl = z.url().refine((value) => {
  const u = new URL(value);
  return (
    u.protocol === "http:" &&
    u.hostname === "127.0.0.1" &&
    !u.username &&
    !u.password &&
    u.pathname === "/" &&
    !u.search &&
    !u.hash
  );
}, "Upstream must be a fixed loopback HTTP origin");
export const configSchema = z
  .object({
    databaseUrl: z.string().min(1),
    origin: z.url(),
    port: z.number().int().min(1024).max(65535).default(3001),
    encryptionKey: z.string().regex(/^[0-9a-f]{64}$/),
    mediaOrigin: loopbackUrl,
    mediaApiOrigin: loopbackUrl,
    mediaUser: z.string().min(1),
    mediaPassword: z.string().min(16),
    standardLiveEnabled: z.boolean().default(false),
    airOrigin: loopbackUrl,
    airToken: z.string().min(32),
    loginHours: z.number().int().min(1).max(12).default(12),
    maxPlaybackSessions: z.number().int().min(1).max(20).default(5),
    allowInsecureLocalhost: z.boolean().default(false),
  })
  .strict()
  .superRefine((c, ctx) => {
    const u = new URL(c.origin);
    if (u.username || u.password || u.pathname !== "/" || u.search || u.hash)
      ctx.addIssue({
        code: "custom",
        message: "origin must be an origin only",
      });
    if (
      u.protocol !== "https:" &&
      !(
        c.allowInsecureLocalhost &&
        u.protocol === "http:" &&
        ["127.0.0.1", "localhost"].includes(u.hostname)
      )
    )
      ctx.addIssue({ code: "custom", message: "HTTPS is required" });
    if (
      c.allowInsecureLocalhost &&
      !["127.0.0.1", "localhost"].includes(u.hostname)
    )
      ctx.addIssue({
        code: "custom",
        message: "Insecure mode is only available on localhost",
      });
  });
export type Config = z.infer<typeof configSchema>;
export function readPrivateJson(path: string): unknown {
  const st = lstatSync(path);
  if (!st.isFile() || st.isSymbolicLink() || (st.mode & 0o777) !== 0o600)
    throw new Error("Private input must be a regular file with mode 0600");
  try {
    return JSON.parse(readFileSync(path, "utf8")) as unknown;
  } catch {
    throw new Error("Private JSON could not be parsed; values omitted");
  }
}
export function loadConfig(): Config {
  const path = process.env.DEVONE_CONFIG;
  if (!path)
    throw new Error("Set DEVONE_CONFIG to the private server JSON file");
  const result = configSchema.safeParse(readPrivateJson(path));
  if (!result.success)
    throw new Error(
      "Invalid server configuration; consult the example (values omitted)",
    );
  return { ...result.data, origin: new URL(result.data.origin).origin };
}
