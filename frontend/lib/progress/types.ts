// The record contract for the progress engine (plan 08 §2, sub-plan §3).
//
// Two authored record types — Attempt (one answered question) and Session (one
// run of a quiz). Everything else in later phases (mastery, streaks, XP, the
// error log) is a pure *derived* function over the Attempt log, never authored
// here. `Level`/`Difficulty` are sourced from their existing home modules so
// there is exactly one definition of each across the app.

import type { Level } from "@/lib/deca";
import type { Difficulty } from "@/lib/question-bank";
import type { BankQuestion } from "@/lib/question-bank";
import { uuid } from "@/lib/progress/ids";

/** The letter a student locked in. */
export type Choice = "A" | "B" | "C" | "D";

/** Where an attempt happened. `browse` is reserved for forward-compat (deferred). */
export type AttemptSource =
  | "focus"
  | "test-gen"
  | "review-lab"
  | "diagnostic"
  | "browse";

/** The atomic unit: one answered question, from anywhere in the app. */
export interface Attempt {
  id: string; // uuid — the dedupe key for migration/sync
  ts: number; // epoch ms, when answered
  questionId: string; // BankQuestion.id — the join back to the bank tags
  cluster: string;
  level: Level;
  instructionalArea: string;
  performanceIndicator: string;
  difficulty: Difficulty;
  // Nullable in the schema (local + Postgres) for a future pickless attempt, but no
  // surface writes one today: skipping a question records nothing at all (#107). Read
  // a null as "no pick to judge", never as a state the app can produce.
  chosen: Choice | null;
  correct: boolean;
  elapsedMs: number; // per-question view→answer time — a confidence signal
  source: AttemptSource;
  sessionId: string; // FK → Session.id
}

/** One run of a quiz/test. `endedTs === null` until finished or abandoned. */
export interface Session {
  id: string;
  ts: number; // start
  endedTs: number | null; // null = still open / abandoned until patched
  cluster: string;
  level: Level;
  source: AttemptSource;
  total: number; // questions presented
  answered: number;
  correct: number;
  elapsedMs: number; // wall-clock start→end
}

// Filters — defined now so the ProgressStore interface is stable for Phase 2,
// even though Phase 1 never calls the read side.
export interface AttemptFilter {
  cluster?: string;
  level?: Level;
  performanceIndicator?: string;
  since?: number;
  source?: AttemptSource;
}

export interface SessionFilter {
  cluster?: string;
  level?: Level;
  since?: number;
}

/**
 * Build an Attempt from a BankQuestion + a chosen letter. Every field except
 * chosen/correct/elapsedMs/ts/source/sessionId/id maps straight off the
 * question, so focus, test-gen, and any future surface build attempts
 * identically. A `null` chosen would grade `correct: false`; nothing passes one
 * today (#107).
 */
export function toAttempt(
  q: BankQuestion,
  chosen: Choice | null,
  elapsedMs: number,
  ctx: { sessionId: string; source: AttemptSource },
): Attempt {
  return {
    id: uuid(),
    ts: Date.now(),
    questionId: q.id,
    cluster: q.cluster,
    level: q.level,
    instructionalArea: q.instructionalArea,
    performanceIndicator: q.performanceIndicator,
    difficulty: q.difficulty,
    chosen,
    correct: chosen === q.answer,
    elapsedMs,
    source: ctx.source,
    sessionId: ctx.sessionId,
  };
}
