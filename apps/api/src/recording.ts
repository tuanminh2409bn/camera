import type { RecordingStatus } from "@devone/contracts";
import { type Db, transaction, audit } from "./db.js";
import type { AirGateway } from "./gateways.js";
import type { Identity } from "./auth.js";
import { ApiFailure } from "./errors.js";

export class RecordingService {
  private busy = false;
  constructor(
    private db: Db,
    private air: AirGateway,
  ) {}
  async status(): Promise<RecordingStatus> {
    const intent = (
      await this.db.query<{ desired: boolean }>(
        "SELECT desired FROM recording_intent WHERE id=1",
      )
    ).rows[0];
    if (!intent) throw new Error("Missing recording intent");
    try {
      return { desired: intent.desired, ...(await this.air.status()) };
    } catch {
      return {
        desired: intent.desired,
        observed: null,
        isOnline: false,
        isPaused: false,
        authLatched: false,
        availableBytes: null,
        updatedAt: null,
      };
    }
  }
  async set(identity: Identity, desired: boolean): Promise<RecordingStatus> {
    await transaction(this.db, async (tx) => {
      await tx.query(
        "UPDATE recording_intent SET desired=$1,revision=revision+1,actor_id=$2,updated_at=now() WHERE id=1",
        [desired, identity.user.id],
      );
      await audit(
        tx,
        identity.user.id,
        desired ? "RECORDING_ENABLE" : "RECORDING_DISABLE",
      );
    });
    try {
      await this.reconcile();
    } catch {
      /* Intent is durable; status below reports offline/pending. */
    }
    const state = await this.status();
    if (desired && (state.isPaused || state.authLatched))
      throw new ApiFailure(
        409,
        "AIR_SAFETY_STOP",
        "NUC đang khóa ghi do dung lượng hoặc xác thực. Cần xử lý tại máy trước khi bật lại.",
      );
    return state;
  }
  async reconcile(): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    try {
      // A database lock serializes the external effect across API instances.
      await transaction(this.db, async (tx) => {
        await tx.query("SELECT pg_advisory_xact_lock(6400002)");
        const intent = (
          await tx.query<{ desired: boolean; revision: string }>(
            "SELECT desired,revision FROM recording_intent WHERE id=1 FOR UPDATE",
          )
        ).rows[0];
        if (!intent) throw new Error("Missing recording intent");
        const state = await this.air.status();
        // Initial install observes the existing recorder without changing it.
        // Only an explicit administrator action enables reconciliation.
        if (Number(intent.revision) === 0) return;
        if (
          !state.isOnline ||
          state.observed === null ||
          state.observed === intent.desired
        )
          return;
        if (
          intent.desired &&
          (state.isPaused ||
            state.authLatched ||
            state.availableBytes === null ||
            state.availableBytes < 15 * 1024 ** 3)
        )
          return;
        await this.air.setRecording(intent.desired);
      });
    } finally {
      this.busy = false;
    }
  }
}
