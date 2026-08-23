// The Error Log engine (plan 08 §7, phase 3 sub-plan §3). A pure function from the
// Attempt log to the browsable, grouped set of missed questions + a mistake-pattern
// classifier. RECOMPUTED, NEVER STORED (D1) — like the mastery engine, every export
// here is a pure selector over its inputs; the hook memoizes them, nothing persists.
//
// A miss = an attempt with `correct === false`. The same question can be missed
// repeatedly; we group by questionId and keep the miss count + last-miss time so a
// card can read "missed 3×, last …".
//
// There is no "skipped" miss: skipping a question in the quiz UI is navigation, it
// writes no Attempt at all, so every miss here carries a real pick (#107). `chosen`
// stays nullable to match the stored row, and the few null guards below are type
// formalities kept honest — not a state any surface advertises.
//
// The log stores only tags + questionId (never question text) — showing a real card is
// the resolver's job (resolver.ts). This module is tag-only, client-safe pure TS.

import type { Attempt, Choice } from "@/lib/progress/types";
import type { Difficulty } from "@/lib/question-bank";
import type { Level } from "@/lib/deca";
import { piKey } from "@/lib/progress/mastery";

// ---------------------------------------------------------------- constants
// First-guess, tunable in one place (D4/D7). Timing baselines are the USER's own
// per-difficulty median elapsedMs (relative, pace-robust). Below MIN_TIMED_SAMPLES
// graded picks at a difficulty, we fall back to the ABSOLUTE_* constants so a thin
// early sample doesn't mislabel a normal answer as "careless" or "slow".

export const MIN_TIMED_SAMPLES = 8;
export const ABSOLUTE_FAST_MS = 12_000; // "careless" fallback ceiling (answered faster ⇒ rushed)
export const ABSOLUTE_SLOW_MS = 45_000; // "slow" fallback floor (answered slower ⇒ laboured)

// ------------------------------------------------------------------- types

export type MistakePattern =
  | "careless-on-easy" // wrong PICK on an easy item, faster than the user's median easy time
  | "slow-and-wrong-on-hard" // wrong on a hard item, slower than the user's median hard time
  | "missed"; // any other wrong answer (the catch-all)

// `chose-the-seductive-distractor` is intentionally absent (D4): it needs a per-option
// trap tag the bank doesn't emit, and we won't touch the backend this phase. This union
// is the extension point — add the case here + a bank tag in a later, separate pass.
// `skipped` was removed for the same reason in reverse (#107): it was a member no writer
// could ever produce, so /review rendered a section that was permanently empty. Re-add it
// only together with the code that logs a skip as an Attempt.

export interface PatternThresholds {
  /** Careless ceiling: a wrong easy answer faster than this reads as rushed. */
  medianEasyMs: number;
  /** Slow floor: a wrong hard answer slower than this reads as laboured. */
  medianHardMs: number;
}

export interface ErrorItem {
  questionId: string;
  cluster: string;
  level: Level;
  instructionalArea: string;
  performanceIndicator: string;
  difficulty: Difficulty;
  misses: number; // count of wrong attempts
  lastMissTs: number;
  lastAttemptTs: number; // ts of the most recent attempt (miss or recovery) on this question
  latestPattern: MistakePattern; // classification of the most-recent miss
  lastChosen: Choice | null; // pick on the most-recent miss (null is unreachable — see header)
  resolved: boolean; // answered correctly AFTER the last miss (a "recovered" error)
}

// ----------------------------------------------------------- classifier

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 === 0 ? (s[mid - 1] + s[mid]) / 2 : s[mid];
}

/**
 * Per-difficulty pace baselines from the user's own graded picks (a pickless row is
 * excluded — its elapsedMs isn't "how long you took to answer"). Under MIN_TIMED_SAMPLES
 * picks at a difficulty, the baseline folds in the absolute fallback so `classify`
 * needs no separate branch.
 */
export function patternThresholds(attempts: Attempt[]): PatternThresholds {
  const easy: number[] = [];
  const hard: number[] = [];
  for (const a of attempts) {
    if (a.chosen === null) continue; // pace baseline = real answers only
    if (a.difficulty === "easy") easy.push(a.elapsedMs);
    else if (a.difficulty === "hard") hard.push(a.elapsedMs);
  }
  return {
    medianEasyMs: easy.length >= MIN_TIMED_SAMPLES ? median(easy) : ABSOLUTE_FAST_MS,
    medianHardMs: hard.length >= MIN_TIMED_SAMPLES ? median(hard) : ABSOLUTE_SLOW_MS,
  };
}

/** Whether the timing baselines are still on absolute fallbacks (UI honesty note). */
export function timingProvisional(attempts: Attempt[]): { easy: boolean; hard: boolean } {
  let easy = 0;
  let hard = 0;
  for (const a of attempts) {
    if (a.chosen === null) continue;
    if (a.difficulty === "easy") easy++;
    else if (a.difficulty === "hard") hard++;
  }
  return { easy: easy < MIN_TIMED_SAMPLES, hard: hard < MIN_TIMED_SAMPLES };
}

/**
 * Classify a single MISS (`correct === false`). A fast wrong easy is `careless-on-easy`,
 * a slow wrong hard is `slow-and-wrong-on-hard`, and everything else is the plain
 * `missed` bucket. A pickless row (which no writer produces) falls to `missed` rather
 * than being timed, since its elapsedMs isn't "how long you took to answer".
 */
export function classify(a: Attempt, t: PatternThresholds): MistakePattern {
  if (a.chosen === null) return "missed";
  if (a.difficulty === "easy" && a.elapsedMs < t.medianEasyMs) return "careless-on-easy";
  if (a.difficulty === "hard" && a.elapsedMs > t.medianHardMs) return "slow-and-wrong-on-hard";
  return "missed";
}

// --------------------------------------------------------- error selectors

/**
 * The Error Log: one ErrorItem per questionId that has ≥1 miss, newest-miss first.
 * Thresholds are computed once over the whole (pre-filtered) set so patterns are
 * judged against a stable pace baseline.
 */
export function errorLog(attempts: Attempt[]): ErrorItem[] {
  const thresholds = patternThresholds(attempts);

  // Group every attempt by question so we can read a question's miss history.
  const byQuestion = new Map<string, Attempt[]>();
  for (const a of attempts) {
    const list = byQuestion.get(a.questionId);
    if (list) list.push(a);
    else byQuestion.set(a.questionId, [a]);
  }

  const items: ErrorItem[] = [];
  for (const [questionId, list] of byQuestion) {
    const misses = list.filter((a) => !a.correct);
    if (misses.length === 0) continue; // never missed ⇒ not an error

    // The most-recent miss drives the card's pattern + shown pick, and the most
    // recent attempt of any kind decides whether it has been recovered. Both
    // reduce with `>=` so a TIE resolves to the LAST attempt in log order, which
    // is the only ordering signal two attempts sharing a `ts` have (issue #111).
    const latestMiss = misses.reduce((m, a) => (a.ts >= m.ts ? a : m));
    const latestAttempt = list.reduce((m, a) => (a.ts >= m.ts ? a : m));
    const lastMissTs = latestMiss.ts;
    const lastAttemptTs = latestAttempt.ts;

    items.push({
      questionId,
      cluster: latestMiss.cluster,
      level: latestMiss.level,
      instructionalArea: latestMiss.instructionalArea,
      performanceIndicator: latestMiss.performanceIndicator,
      difficulty: latestMiss.difficulty,
      misses: misses.length,
      lastMissTs,
      lastAttemptTs,
      latestPattern: classify(latestMiss, thresholds),
      lastChosen: latestMiss.chosen,
      // "Answered correctly after the last miss" is exactly "the newest attempt
      // on this question is correct" — read it off the attempt rather than
      // comparing timestamps, so a recovery logged in the SAME millisecond as
      // the miss (an import, a migration, a seeded fixture) still clears the
      // card. A strict `>` left it stuck on /review forever (issue #111).
      resolved: latestAttempt.correct,
    });
  }

  return items.sort((a, b) => b.lastMissTs - a.lastMissTs);
}

/** Error items grouped by PI (piKey — matches the mastery engine's grouping). */
export function errorsByPI(attempts: Attempt[]): Map<string, ErrorItem[]> {
  const map = new Map<string, ErrorItem[]>();
  for (const item of errorLog(attempts)) {
    const k = piKey(item.cluster, item.instructionalArea, item.performanceIndicator);
    const list = map.get(k);
    if (list) list.push(item);
    else map.set(k, [item]);
  }
  return map;
}

/** Error items grouped by their latest mistake pattern. */
export function errorsByPattern(attempts: Attempt[]): Map<MistakePattern, ErrorItem[]> {
  const map = new Map<MistakePattern, ErrorItem[]>();
  for (const item of errorLog(attempts)) {
    const list = map.get(item.latestPattern);
    if (list) list.push(item);
    else map.set(item.latestPattern, [item]);
  }
  return map;
}
