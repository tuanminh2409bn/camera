import { z } from "zod";

export const MAX_LIVE_SESSIONS = 200;
export const liveQuality = z.enum(["standard", "source"]);
export type LiveQuality = z.infer<typeof liveQuality>;
export const uuid = z.uuid();
export const username = z
  .string()
  .min(3)
  .max(64)
  .regex(/^[a-zA-Z0-9._-]+$/);
export const password = z.string().min(12).max(256);
const viewerPassword = z.string().min(6).max(256);
export const loginInput = z
  .object({
    username,
    password: z.string().min(1).max(256),
    otp: z
      .string()
      .regex(/^\d{6}$/)
      .optional(),
  })
  .strict();
export const permissions = z.object({
  canLive: z.boolean(),
  canPlayback: z.boolean(),
  canDownload: z.boolean(),
});
export const createViewerInput = permissions
  .extend({
    username,
    password: viewerPassword,
    maxLiveSessions: z.number().int().min(1).max(10).default(2),
  })
  .strict();
export const updateViewerInput = permissions
  .partial()
  .extend({
    isActive: z.boolean().optional(),
    password: viewerPassword.optional(),
    maxLiveSessions: z.number().int().min(1).max(10).optional(),
  })
  .strict()
  .refine((v) => Object.keys(v).length > 0);
export const pageInput = z
  .object({
    page: z.coerce.number().int().min(1).default(1),
    pageSize: z.coerce.number().int().min(1).max(100).default(25),
  })
  .strict();
export const playbackInput = z
  .object({
    start: z.iso.datetime({ offset: true }),
    duration: z.number().min(1).max(300),
    download: z.boolean().default(false),
  })
  .strict();
export const recordingInput = z.object({ desired: z.boolean() }).strict();
export const userOutput = permissions.extend({
  id: uuid,
  username,
  role: z.enum(["ADMIN", "VIEWER"]),
  isActive: z.boolean(),
  maxLiveSessions: z.number().int(),
});
export const authOutput = z.object({
  user: userOutput,
  csrfToken: z.string(),
  expiresAt: z.string(),
});
export const intervalsOutput = z.array(
  z.object({ start: z.string(), duration: z.number().nonnegative() }),
);
export type User = z.infer<typeof userOutput>;
export type Auth = z.infer<typeof authOutput>;
export type ViewerInput = z.infer<typeof createViewerInput>;
export type ViewerUpdate = z.infer<typeof updateViewerInput>;
export type PlaybackInput = z.infer<typeof playbackInput>;
export interface ApiError {
  error: { code: string; message: string };
}
export interface RecordingStatus {
  desired: boolean;
  observed: boolean | null;
  isOnline: boolean;
  isPaused: boolean;
  authLatched: boolean;
  availableBytes: number | null;
  updatedAt: string | null;
}
export interface LiveSession {
  id: string;
  username: string;
  state: string;
  createdAt: string;
  expiresAt: string;
}
export interface AuditEvent {
  id: string;
  actorId: string | null;
  actorUsername: string | null;
  action: string;
  targetId: string | null;
  createdAt: string;
}

export const operationCodes = [
  "API",
  "WEB_TLS",
  "MEDIA",
  "AUDIO",
  "MEDIA_PROGRESS",
  "AIR",
  "AIR_AUTH",
  "AIR_DISK",
  "RECORDING",
  "SERVER_DISK",
  "BACKUP",
  "BACKUP_TIMER",
] as const;
export const operationCode = z.enum(operationCodes);
export const operationSnapshot = z
  .object({
    updatedAt: z.iso.datetime({ offset: true }),
    checks: z
      .array(
        z
          .object({
            code: operationCode,
            status: z.enum(["ok", "pending", "firing", "recovering"]),
            since: z.iso.datetime({ offset: true }).nullable(),
            value: z.number().finite().min(-1e18).max(1e18).nullable(),
          })
          .strict(),
      )
      .length(operationCodes.length)
      .refine(
        (items) =>
          new Set(items.map((x) => x.code)).size === operationCodes.length,
      ),
    events: z
      .array(
        z
          .object({
            code: operationCode,
            at: z.iso.datetime({ offset: true }),
            kind: z.enum(["firing", "resolved"]),
          })
          .strict(),
      )
      .max(50),
    traffic: z
      .object({
        month: z.string().regex(/^\d{4}-\d{2}$/),
        since: z.iso.datetime({ offset: true }),
        bytes: z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER),
      })
      .strict()
      .nullable(),
  })
  .strict();
export type OperationCode = z.infer<typeof operationCode>;
export type OperationSnapshot = z.infer<typeof operationSnapshot>;
export type OperationsStatus =
  | ({ available: true } & OperationSnapshot)
  | { available: false; reason: "unavailable" | "stale" };
export interface ServiceStatus {
  mediaHealthy: boolean;
  airHealthy: boolean;
  operations: OperationsStatus;
}
