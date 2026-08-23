// The one persistence seam for the whole analytics feature (plan 08 §4,
// sub-plan §4). Every read and write goes through this interface; no analytics
// UI ever knows which implementation is behind it. Phase 1 ships the IndexedDB
// impl; Phase 4 adds a Supabase impl (wrapped by a SyncingStore) behind the
// *same* interface, so that swap is additive, not a rewrite.
//
// Mastery / streaks / XP are selectors over this store in later phases — never
// stored here as source of truth.

import type {
  Attempt,
  AttemptFilter,
  Session,
  SessionFilter,
} from "@/lib/progress/types";

export interface ProgressStore {
  /** Batch or single; idempotent by `id` (put, not add) so replays never double-count. */
  recordAttempts(a: Attempt[]): Promise<void>;
  /** Upsert a session at start; safe to call again with the same id. */
  startSession(s: Session): Promise<void>;
  /** Patch a session on finish/abandon (endedTs + rolled-up counts). */
  endSession(id: string, patch: Partial<Session>): Promise<void>;

  getAttempts(filter?: AttemptFilter): Promise<Attempt[]>;
  getSessions(filter?: SessionFilter): Promise<Session[]>;

  /** Wipe all attempts + sessions (the "reset progress" action). Irreversible. */
  clear(): Promise<void>;

  // Migration / sync primitives — correct now, only exercised by a future
  // SyncingStore in Phase 4.
  exportAll(): Promise<{ attempts: Attempt[]; sessions: Session[] }>;
  /** Idempotent by `id`: existing ids overwrite identical data, new ids insert. */
  importAll(data: { attempts: Attempt[]; sessions: Session[] }): Promise<void>;
}
