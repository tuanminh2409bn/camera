import { z } from "zod";
import { intervalsOutput, type RecordingStatus } from "@devone/contracts";
import type { Config } from "./config.js";
import { offline } from "./errors.js";

export interface NativeSession {
  id: string;
  appSession: string | null;
}
export interface MediaGateway {
  create(id: string, sdp: string): Promise<{ sdp: string; location: string }>;
  close(location: string): Promise<void>;
  sessions(): Promise<NativeSession[]>;
  kick(id: string): Promise<void>;
}
export interface AirGateway {
  status(): Promise<Omit<RecordingStatus, "desired">>;
  setRecording(desired: boolean): Promise<void>;
  intervals(): Promise<z.infer<typeof intervalsOutput>>;
  playback(
    start: string,
    duration: number,
    range: string | undefined,
    signal: AbortSignal,
  ): Promise<Response>;
}
const nativeLocation =
  /^\/live\/whep\/[0-9a-f-]{36}(?:\?appSession=[0-9a-f-]{36})?$/;
export class HttpMediaGateway implements MediaGateway {
  private auth: string;
  constructor(private config: Config) {
    this.auth =
      "Basic " +
      Buffer.from(`${config.mediaUser}:${config.mediaPassword}`).toString(
        "base64",
      );
  }
  private async request(
    origin: string,
    path: string,
    init: RequestInit = {},
  ): Promise<Response> {
    try {
      return await fetch(new URL(path, origin), {
        ...init,
        redirect: "error",
        signal: AbortSignal.timeout(4000),
        headers: { Authorization: this.auth, ...init.headers },
      });
    } catch {
      throw offline();
    }
  }
  async create(
    id: string,
    sdp: string,
  ): Promise<{ sdp: string; location: string }> {
    const response = await this.request(
      this.config.mediaOrigin,
      `/live/whep?appSession=${id}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/sdp" },
        body: sdp,
      },
    );
    if (response.status !== 201) {
      await response.body?.cancel();
      throw offline();
    }
    const location = response.headers.get("location");
    if (!location || !nativeLocation.test(location)) {
      await response.body?.cancel();
      throw offline();
    }
    const answer = await response.text();
    if (!answer.startsWith("v=0") || answer.length > 131072) throw offline();
    return { sdp: answer, location };
  }
  async close(location: string): Promise<void> {
    if (!nativeLocation.test(location))
      throw new Error("Invalid stored native location");
    const response = await this.request(this.config.mediaOrigin, location, {
      method: "DELETE",
    });
    await response.body?.cancel();
    if (![200, 204, 404, 410].includes(response.status)) throw offline();
  }
  async sessions(): Promise<NativeSession[]> {
    const result: NativeSession[] = [];
    const response = await this.request(
      this.config.mediaApiOrigin,
      "/v3/webrtcsessions/list?page=0&itemsPerPage=1000",
    );
    if (!response.ok) throw offline();
    const parsed = z
      .object({
        // One snapshot avoids offsets shifting while sessions close/open.
        // More than 1000 sessions on a 200-reader server is a fault, not a
        // reason to release capacity from an incomplete paginated inventory.
        pageCount: z.number().int().min(0).max(1),
        items: z
          .array(
            z.object({ id: z.uuid(), query: z.string(), state: z.string() }),
          )
          .max(1000),
      })
      .safeParse(await response.json());
    if (!parsed.success) throw offline();
    for (const item of parsed.data.items) {
      if (item.state === "read") {
        const id = new URLSearchParams(item.query).get("appSession");
        result.push({
          id: item.id,
          appSession: id && z.uuid().safeParse(id).success ? id : null,
        });
      }
    }
    return result;
  }
  async kick(id: string): Promise<void> {
    if (!z.uuid().safeParse(id).success) throw new Error("Invalid native ID");
    const response = await this.request(
      this.config.mediaApiOrigin,
      `/v3/webrtcsessions/kick/${id}`,
      { method: "POST" },
    );
    await response.body?.cancel();
    if (![200, 404].includes(response.status)) throw offline();
  }
}
export class HttpAirGateway implements AirGateway {
  private intervalCache:
    { expires: number; data: z.infer<typeof intervalsOutput> } | undefined;
  private intervalRequest: Promise<z.infer<typeof intervalsOutput>> | undefined;
  constructor(private config: Config) {}
  private async request(
    path: string,
    init: RequestInit = {},
  ): Promise<Response> {
    try {
      return await fetch(new URL(path, this.config.airOrigin), {
        ...init,
        redirect: "error",
        signal: init.signal ?? AbortSignal.timeout(4000),
        headers: {
          Authorization: `Bearer ${this.config.airToken}`,
          ...init.headers,
        },
      });
    } catch {
      throw offline();
    }
  }
  async status(): Promise<Omit<RecordingStatus, "desired">> {
    const response = await this.request("/status");
    if (!response.ok) throw offline();
    const parsed = z
      .object({
        observed: z.boolean().nullable(),
        isOnline: z.boolean(),
        isPaused: z.boolean(),
        authLatched: z.boolean(),
        availableBytes: z.number().nullable(),
        updatedAt: z.string().nullable(),
      })
      .safeParse(await response.json());
    if (!parsed.success) throw offline();
    return parsed.data;
  }
  async setRecording(desired: boolean): Promise<void> {
    const response = await this.request("/recording", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ desired }),
    });
    await response.body?.cancel();
    if (!response.ok) throw offline();
  }
  async intervals(): Promise<z.infer<typeof intervalsOutput>> {
    if (this.intervalCache && this.intervalCache.expires > Date.now())
      return this.intervalCache.data;
    if (this.intervalRequest) return this.intervalRequest;
    this.intervalRequest = this.loadIntervals();
    try {
      const data = await this.intervalRequest;
      this.intervalCache = { expires: Date.now() + 10000, data };
      return data;
    } finally {
      this.intervalRequest = undefined;
    }
  }
  private async loadIntervals(): Promise<z.infer<typeof intervalsOutput>> {
    const response = await this.request("/recordings");
    if (!response.ok) throw offline();
    const parsed = intervalsOutput.safeParse(await response.json());
    if (!parsed.success) throw offline();
    return parsed.data;
  }
  async playback(
    start: string,
    duration: number,
    range: string | undefined,
    signal: AbortSignal,
  ): Promise<Response> {
    const query = new URLSearchParams({ start, duration: String(duration) });
    const headerDeadline = new AbortController();
    const timer = setTimeout(() => headerDeadline.abort(), 8000);
    timer.unref();
    try {
      return await this.request(`/playback?${query}`, {
        signal: AbortSignal.any([signal, headerDeadline.signal]),
        headers: range ? { Range: range } : {},
      });
    } finally {
      clearTimeout(timer);
    }
  }
}
