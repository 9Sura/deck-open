// The offline-first store for signed-in users (sub-plan §6 — the real
// engineering). Wraps a local IndexedDbStore (cache + outbox) and a SupabaseStore
// (remote). Reads are always local (fast, offline). Writes hit local + the
// durable outbox immediately, then a fire-and-forget flusher drains the outbox to
// Supabase. Consumers never learn which store is active — the ProgressStore seam.
//
// Flusher contract:
// - Drains FIFO; each op maps to an idempotent SupabaseStore call (upsert/patch
//   by client id, or the delete-all `reset`). Success -> delete the entry.
// - On a TRANSIENT failure (network down / 5xx — usually queue-wide): bump tries,
//   schedule an exponential backoff, and STOP, preserving order. This never
//   dead-letters, so a long outage can't nuke a perfectly good pending write.
// - On a PERMANENT failure (a 4xx / a Postgres constraint or data error — retrying
//   will always fail): DEAD-LETTER the op and advance past it, so one poison op
//   can't head-of-line-block every write queued behind it forever (issue #5). An
//   unclassifiable failure that persists MAX_TRIES times is dead-lettered too, as
//   a backstop. Every dead-letter fires onSyncError so the failure isn't silent.
// - After a successful drain (and on load / focus / online, D9) it pulls:
//   remote.exportAll() -> local.importAll() (put-by-id merge) -> onChange(), so
//   useProgressData re-reads and the dashboard reflects other-device activity.
//   A pull NEVER imports while a `reset` op is still queued: the merge would put
//   the rows the user just deleted back into the wiped local cache, and because
//   it's a merge, the post-wipe pull of an empty server can't take them out again.

import type { ProgressStore } from "@/lib/progress/store";
import type {
  Attempt,
  AttemptFilter,
  Session,
  SessionFilter,
} from "@/lib/progress/types";
import type { IndexedDbStore } from "@/lib/progress/idb-store";
import type { SupabaseStore } from "@/lib/progress/supabase-store";
import type { Outbox, OutboxEntry } from "@/lib/progress/outbox";
import {
  backoffMs,
  classifyError,
  failureMessage,
} from "@/lib/progress/sync-failure";

// Dead-letter backstop for UNCLASSIFIABLE failures only (permanent errors are
// dead-lettered on the first try; transient/network errors are NEVER dead-lettered,
// however long they persist). Set well past the point the backoff caps out (tries
// >= 5 all wait the backoff ceiling), so a mystery error gets many retries —
// spanning a plausible transient blip — before we give up on it. The tradeoff: a
// truly novel transient error class we fail to recognize could be dropped after
// MAX_TRIES; the write still lives in the local cache and the dead entry is
// retained for inspection.
const MAX_TRIES = 8;

/** What surfaces to the UI when the flusher gives up on an op (issue #5). */
export interface SyncErrorInfo {
  /** Which op was dropped (attempts / session-start / session-end / reset). */
  op: OutboxEntry["op"];
  /** The remote error message — for a log line or a support hint. */
  message: string;
}

// `classifyError` / `backoffMs` used to live here. They moved to `sync-failure.ts`
// when the study-plan config writer needed the same retry judgement (issue #181) —
// which error shapes are worth retrying is a property of the backend, not of the
// caller, so a second copy would have drifted.

export class SyncingStore implements ProgressStore {
  private flushing = false;
  private pending = false; // a write arrived mid-flush → drain again
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  /** Consecutive flushes that died on a LOCAL storage fault — drives the backoff
   *  for that path (the per-op counters live on the outbox entries). */
  private localFailures = 0;
  /** Bumped by every clear(). A pull whose snapshot was fetched before a reset
   *  landed must not import that (now-deleted) data back into the wiped cache. */
  private resetGen = 0;
  /** True from the synchronous start of clear() until its `reset` op is durably
   *  queued (or the enqueue fails). Outside that sliver the outbox itself answers
   *  "is a wipe still pending?" — see `resetPending` (issue #62). */
  private resetQueuing = false;

  constructor(
    private readonly local: IndexedDbStore,
    private readonly remote: SupabaseStore,
    private readonly outbox: Outbox,
    /** Bumps the provider's `version` so useProgressData re-reads (pull updates). */
    private readonly onChange: () => void,
    /** Fired when an op is dead-lettered, so the UI can surface "sync paused"
     *  instead of silently losing cross-device sync (issue #5). */
    private readonly onSyncError: (info: SyncErrorInfo) => void = () => {},
    /** Fired when the LOCAL store/outbox itself fails (issue #9 follow-up). Distinct
     *  from onSyncError: that one means "saved here, not on your account", this one
     *  means "this device isn't saving at all". */
    private readonly onStorageError: (err: unknown) => void = () => {},
  ) {}

  // ---- lifecycle -----------------------------------------------------------

  private onlineHandler = () => void this.flush();
  private visibilityHandler = () => {
    if (document.visibilityState === "visible") void this.flush();
  };

  /** Register freshness triggers + do the initial drain/pull. Idempotent-ish. */
  start(): void {
    if (typeof window === "undefined") return;
    window.addEventListener("online", this.onlineHandler);
    document.addEventListener("visibilitychange", this.visibilityHandler);
    void this.flush(); // load: drain anything left over, then pull
  }

  /** Detach listeners + cancel retries (sign-out / account switch — D7). */
  dispose(): void {
    if (typeof window === "undefined") return;
    window.removeEventListener("online", this.onlineHandler);
    document.removeEventListener("visibilitychange", this.visibilityHandler);
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
  }

  // ---- writes: local-first + enqueue + async flush -------------------------

  async recordAttempts(a: Attempt[]): Promise<void> {
    if (a.length === 0) return;
    await this.local.recordAttempts(a);
    await this.outbox.enqueue({ op: "attempts", payload: a });
    void this.flush();
  }

  async startSession(s: Session): Promise<void> {
    await this.local.startSession(s);
    await this.outbox.enqueue({ op: "session-start", payload: s });
    void this.flush();
  }

  async endSession(id: string, patch: Partial<Session>): Promise<void> {
    await this.local.endSession(id, patch);
    // Enqueue the FULL finalized session (re-read from the local cache after the
    // merge above), not just the delta, so the remote upsert can insert a complete
    // NOT-NULL-satisfying row if the session-start op never reached the server
    // (dropped/dead-lettered, or a partial reset between start and end — issue #11).
    // If the session isn't in the local cache there's nothing meaningful to sync
    // (mirrors local.endSession's no-op on a missing session), so skip the enqueue.
    const full = await this.getLocalSession(id);
    if (!full) return;
    await this.outbox.enqueue({ op: "session-end", payload: { id, patch: full } });
    void this.flush();
  }

  /** Read a single session from the local cache by id (used to hand the remote
   *  upsert a complete row on endSession). Sessions are few, so a scan is cheap. */
  private async getLocalSession(id: string): Promise<Session | undefined> {
    const all = await this.local.getSessions();
    return all.find((s) => s.id === id);
  }

  // ---- reads: always local (fast, offline) ---------------------------------

  getAttempts(filter?: AttemptFilter): Promise<Attempt[]> {
    return this.local.getAttempts(filter);
  }

  getSessions(filter?: SessionFilter): Promise<Session[]> {
    return this.local.getSessions(filter);
  }

  // ---- reset + migration primitives ----------------------------------------

  /** Wipe everything, locally and on the account (D12 reset) — durably, so it
   *  survives being offline (issue #8). Calling `remote.clear()` inline used to
   *  drop the remote wipe entirely when it threw offline: local + outbox were
   *  already empty, the reset looked done, and the next `pull()` repopulated
   *  local from the untouched server rows. */
  async clear(): Promise<void> {
    // Bump FIRST (synchronously, before any await) so a pull already in flight
    // can't write its pre-reset snapshot back into the cache we're about to wipe.
    this.resetGen += 1;
    // Same beat, for the OTHER half of the race: a pull that starts *after* this
    // bump but before the wipe below has landed in the outbox would see a matching
    // gen and an empty queue, and import the still-un-wiped server rows (#62). Hold
    // the flag until the enqueue is durable; from there the queue is the authority.
    this.resetQueuing = true;
    try {
      // 1. Drop every queued op: they describe progress that no longer exists, and
      //    replaying them after the remote wipe would resurrect it.
      await this.outbox.clear();
      // 2. Queue the remote wipe as a durable op, retried across backoff and
      //    reloads like any other write instead of being lost on a throw. While it
      //    sits there, pull() refuses to import, so the still-present remote rows
      //    can't repopulate local in the meantime.
      await this.outbox.enqueue({ op: "reset", payload: null });
    } finally {
      // On success the outbox now carries the reset and answers for it; on failure
      // nothing was queued, so leaving this set would block pulls forever.
      this.resetQueuing = false;
    }
    // 3. Wipe the local cache — local.clear() touches attempts/sessions only, so
    //    the reset op we just queued survives it.
    await this.local.clear();
    // 4. Drain now, so an ordinary (online) reset still completes remotely within
    //    this call. Offline, this fails quietly and the backoff/online/focus
    //    triggers retry it later.
    await this.flush();
  }

  exportAll(): Promise<{ attempts: Attempt[]; sessions: Session[] }> {
    return this.local.exportAll();
  }

  async importAll(data: {
    attempts: Attempt[];
    sessions: Session[];
  }): Promise<void> {
    // Merge into the local cache. Pushing this set up to remote is the migration's
    // job (4c), which drives remote + local directly.
    await this.local.importAll(data);
  }

  // ---- the flusher ---------------------------------------------------------

  /** Drain the outbox to Supabase, then pull. Single in-flight; re-runs if a
   *  write queued during a successful drain. No-op re-entrant call while busy.
   *
   *  NEVER REJECTS. Every caller invokes this as `void this.flush()` (start, the
   *  online/visibility handlers, each write, the retry timer), so an escaping
   *  rejection would land as an unhandled promise rejection in the console — the
   *  one place no user looks — and, worse, would skip `scheduleRetry`, leaving sync
   *  down until a page reload. */
  async flush(): Promise<void> {
    if (this.flushing) {
      this.pending = true;
      return;
    }
    this.flushing = true;
    try {
      let again = true;
      while (again) {
        again = false;
        this.pending = false;
        const drained = await this.drain();
        if (drained) {
          await this.pull();
          if (this.pending) again = true; // new writes arrived mid-drain
        }
        // On failure we don't loop — the backoff timer retries later.
      }
      this.localFailures = 0; // a clean pass ⇒ local storage is healthy again
    } catch (err) {
      // Reaching here means the OUTBOX ITSELF failed (reading the queue in
      // `drain`, or a bookkeeping write like markDead/bumpTries) — a LOCAL storage
      // fault, not a remote one. drain()'s transient/permanent classification only
      // covers errors thrown by the remote calls, so this path has to do its own
      // backoff. Retry on the same curve so sync resumes once storage recovers.
      this.localFailures += 1;
      this.scheduleRetry(this.localFailures);
      this.reportStorageError(err);
    } finally {
      this.flushing = false;
    }
  }

  /** Apply each queued op FIFO. A transient failure stops the drain and backs off
   *  (preserving order); a permanent/poison failure is dead-lettered and skipped so
   *  it can't head-of-line-block everything behind it (issue #5). Returns true when
   *  it reaches the end of the queue — including after dead-lettering, since a
   *  successful drain-to-end means we're online and a pull should follow. */
  private async drain(): Promise<boolean> {
    const entries = await this.outbox.list();
    for (const e of entries) {
      try {
        await this.apply(e);
        await this.outbox.remove(e.seq);
      } catch (err) {
        const kind = classifyError(err);
        const nextTries = e.tries + 1;
        if (kind === "permanent" || (kind === "unknown" && nextTries >= MAX_TRIES)) {
          // Give up on this op: retain it dead-lettered, surface the failure, and
          // advance to the next entry so the rest of the queue still drains.
          await this.outbox.markDead(e.seq);
          this.reportSyncError(e, err);
          continue;
        }
        // Transient (or not-yet-exhausted unknown): usually the whole queue is
        // unreachable — bump for backoff, schedule a retry, and stop in order.
        await this.outbox.bumpTries(e.seq, nextTries);
        this.scheduleRetry(nextTries);
        return false;
      }
    }
    return true;
  }

  /** Surface a local-storage fault to the provider (best-effort; never throws). */
  private reportStorageError(err: unknown): void {
    try {
      this.onStorageError(err);
    } catch {
      // A misbehaving subscriber must not break the flusher.
    }
  }

  /** Surface a dead-lettered op to the provider (best-effort; never throws). */
  private reportSyncError(e: OutboxEntry, err: unknown): void {
    const message = failureMessage(err);
    try {
      this.onSyncError({ op: e.op, message });
    } catch {
      // A misbehaving subscriber must not break the flusher.
    }
  }

  private apply(e: OutboxEntry): Promise<void> {
    switch (e.op) {
      case "attempts":
        return this.remote.recordAttempts(e.payload as Attempt[]);
      case "session-start":
        return this.remote.startSession(e.payload as Session);
      case "session-end": {
        const p = e.payload as { id: string; patch: Partial<Session> };
        return this.remote.endSession(p.id, p.patch);
      }
      case "reset":
        return this.remote.clear();
    }
  }

  /** Pull the remote union into the local cache and notify subscribers. */
  private async pull(): Promise<void> {
    const gen = this.resetGen;
    try {
      const server = await this.remote.exportAll();
      // A reset landed while this snapshot was in flight: it describes rows the
      // user just deleted, so importing it would undo the wipe (issue #8). The
      // reset op is queued behind us and the next drain re-pulls afterwards.
      if (gen !== this.resetGen) return;
      // ...and the same snapshot is stale for a reset that landed BEFORE this pull
      // began but hasn't drained yet — `gen` matches, but the server hasn't been
      // wiped, so importing would resurrect the whole log locally (issue #62).
      // importAll is a put-by-id MERGE, so the later "server is empty now" pull
      // deletes nothing and the device never self-heals. Skip until the wipe lands.
      if (await this.resetPending()) return;
      await this.local.importAll(server);
      this.onChange();
    } catch {
      // Offline / transient — the next trigger (online/focus/retry) tries again.
    }
  }

  /** Is a "wipe my account" op still waiting to reach Supabase? The durable queue
   *  is the source of truth (so this survives a reload, and a dead-lettered reset
   *  — skipped by `list()` — stops blocking pulls forever), plus the in-memory
   *  flag for the sliver of clear() before the op is written. */
  private async resetPending(): Promise<boolean> {
    if (this.resetQueuing) return true;
    const queued = await this.outbox.list();
    return queued.some((e) => e.op === "reset");
  }

  private scheduleRetry(tries: number): void {
    if (this.retryTimer || typeof window === "undefined") return;
    const delay = backoffMs(tries);
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      void this.flush();
    }, delay);
  }
}
