// The durable pending-mutation queue (sub-plan §6). A third object store in the
// per-user IndexedDB DB holding ordered writes that still need to reach Supabase.
// Because it's persisted, a write survives a reload/crash while offline — the
// reason "practice never blocks on the network and works offline" is actually
// true and not just a fire-and-forget promise.
//
// Ordering: entries key on an autoincrement `seq`, so `list()` returns them in
// enqueue order (FIFO). Each op maps 1:1 to a SupabaseStore call, all idempotent
// (upsert / patch by client id), so replaying the queue never double-counts.

import type { Attempt, Session } from "@/lib/progress/types";
import { OUTBOX, reqToPromise, tx } from "@/lib/progress/idb-store";

/** One pending remote mutation. Discriminated on `op`.
 *
 *  `reset` is the durable "wipe my account's rows" op (issue #8). It carries no
 *  payload — it deletes every row for the user — and, like the others, it's
 *  idempotent, so replaying it after a partial success is harmless. Queuing the
 *  reset (rather than calling `remote.clear()` inline) is what makes an OFFLINE
 *  "reset progress" stick instead of resurrecting on the next pull. */
export type OutboxOp =
  | { op: "attempts"; payload: Attempt[] }
  | { op: "session-start"; payload: Session }
  | { op: "session-end"; payload: { id: string; patch: Partial<Session> } }
  | { op: "reset"; payload: null };

/** A queued op as stored: the op + its autoincrement seq + a retry counter. */
export interface OutboxEntry {
  seq: number;
  op: OutboxOp["op"];
  payload: OutboxOp["payload"];
  tries: number;
  /** Marked when the flusher gives up on this op (poison / permanent failure).
   *  Dead entries are retained for inspection but skipped by `list()`, so one
   *  bad op can never block the ops queued behind it. */
  dead?: boolean;
}

const hasIDB = () => typeof indexedDB !== "undefined";

export class Outbox {
  constructor(private readonly dbName: string) {}

  /** Append a pending mutation (tries starts at 0; seq is assigned by IDB). */
  async enqueue(op: OutboxOp): Promise<void> {
    if (!hasIDB()) return;
    await tx(this.dbName, OUTBOX, "readwrite", (os) => {
      os.add({ op: op.op, payload: op.payload, tries: 0 });
    });
  }

  /** Live pending entries in FIFO (seq) order — dead-lettered ones are skipped
   *  so the flusher advances past a poison op instead of stalling on it. */
  async list(): Promise<OutboxEntry[]> {
    if (!hasIDB()) return [];
    const all = (await tx(this.dbName, OUTBOX, "readonly", (os) =>
      reqToPromise(os.getAll()),
    )) as OutboxEntry[];
    return all.filter((e) => !e.dead);
  }

  /** Dead-lettered entries retained for inspection (audit trail / support). */
  async listDead(): Promise<OutboxEntry[]> {
    if (!hasIDB()) return [];
    const all = (await tx(this.dbName, OUTBOX, "readonly", (os) =>
      reqToPromise(os.getAll()),
    )) as OutboxEntry[];
    return all.filter((e) => e.dead);
  }

  /** Drop an entry after it has successfully flushed. */
  async remove(seq: number): Promise<void> {
    if (!hasIDB()) return;
    await tx(this.dbName, OUTBOX, "readwrite", (os) => os.delete(seq));
  }

  /** Record a failed attempt (leaves the entry queued for backoff/retry). */
  async bumpTries(seq: number, tries: number): Promise<void> {
    if (!hasIDB()) return;
    await tx(this.dbName, OUTBOX, "readwrite", async (os) => {
      const entry = (await reqToPromise(os.get(seq))) as OutboxEntry | undefined;
      if (!entry) return;
      os.put({ ...entry, tries });
    });
  }

  /** Give up on an entry: flag it dead (skipped by `list()`) but keep it around
   *  so a permanently-failing op stops blocking the queue without vanishing. */
  async markDead(seq: number): Promise<void> {
    if (!hasIDB()) return;
    await tx(this.dbName, OUTBOX, "readwrite", async (os) => {
      const entry = (await reqToPromise(os.get(seq))) as OutboxEntry | undefined;
      if (!entry) return;
      os.put({ ...entry, dead: true });
    });
  }

  /** Empty the queue (part of a reset). */
  async clear(): Promise<void> {
    if (!hasIDB()) return;
    await tx(this.dbName, OUTBOX, "readwrite", (os) => os.clear());
  }
}
