// The only new persisted study-plan state (plan 09 §4.1, D3). A per-account
// PlanConfig — target cluster/level, competition date, and first-run flags —
// lives on `profiles.plan_config jsonb` (migration 0003) so the target follows
// the user across devices. Because the plan is account-only (D10) there is no
// guest config; the auth provider owns the profiles read/write and exposes
// `planConfig` + `setPlanConfig` (mirroring how session/username already flow).
//
// This module is the pure data layer: the PlanConfig shape, a validator/coercer
// for the schemaless jsonb column, and a per-uid localStorage cache that avoids a
// blank-dashboard flash between the session resolving and the profiles row
// arriving. No React, no Supabase — client-safe TS.

import type { Level } from "@/lib/deca";
import type { MixPreset } from "@/lib/question-bank";

// ---- shared task vocabulary (persisted, so it lives in the data layer) ------

export type DifficultyHint = "build" | "mixed" | "challenge";

/** The recommendation categories — the same set the "Add a task" menu offers. */
export type PlanTaskType =
  | "warmup"
  | "weak-drill"
  | "coverage"
  | "fix-misses"
  | "challenge"
  | "milestone";

/** A discriminated launch target — how a task's Start opens an existing surface. */
export type LaunchRef =
  | { kind: "drill"; cluster: string; level: Level; pi: string; area: string; count: number }
  | { kind: "quiz"; cluster: string; level: Level; mix: MixPreset; count: number }
  | { kind: "review" };

/**
 * A user-added task for a single day. Unlike a free-text to-do, an added task is a
 * fully-materialized instance of a recommendation TYPE (picked from the add menu),
 * so it generates the right questions and tracks progress exactly like a
 * recommended task of that type — no manual completion.
 */
export interface CustomTask {
  id: string;
  type: PlanTaskType;
  title: string;
  subtitle: string;
  size: number;
  difficultyHint: DifficultyHint;
  target?: { cluster: string; level: Level; pi?: string; area?: string };
  launch: LaunchRef;
  /** For a fix-misses task: the snapshot of miss questionIds this batch owns.
   *  Completion tracks only these — new misses form a separate batch. */
  missIds?: string[];
}

/**
 * The user's edits to TODAY's plan (plan 09 follow-up). Kept per-day and stamped
 * with `date` (local YYYY-MM-DD) so it self-prunes: on a new day the stale
 * override is ignored and the plan regenerates fresh. Synced with the rest of
 * PlanConfig on the profiles row (D3).
 */
export interface DayPlan {
  date: string;
  /** Recommended-task ids the user removed today (not re-recommended today). */
  dismissed: string[];
  /** User-added tasks for today (materialized recommendation-type instances). */
  custom: CustomTask[];
  /** taskId → session ids launched FROM that task's Start today. Lets a task's
   *  progress count only its own attempts (not any matching attempt elsewhere). */
  sessions?: Record<string, string[]>;
  /** taskId → the persisted question-id set for that task's quiz, so pressing Start
   *  again RESUMES the same quiz instead of generating a new one. */
  quizzes?: Record<string, string[]>;
  /** The day's FROZEN recommended-task set (specs). Captured once, the first time
   *  the plan is built for this day, so the recommended list stays fixed for the
   *  rest of the day — progress/done still update live, but no new recommended
   *  tasks appear as stats shift (the user still adds their own via "Add a task").
   *  undefined = not yet frozen today. An EMPTY array means the same thing (issue
   *  #66): freezing zero tasks would strand the day's plan empty until local
   *  midnight, so both the read side and the coercer collapse [] to undefined and
   *  let the plan re-derive. */
  recommended?: CustomTask[];
  /** The AUTO fix-misses batch's miss-questionId snapshot. Created when misses
   *  first appear and GROWS while in progress (absorbs newly-appeared misses), then
   *  freezes once fully cleared — a completed batch stays done, and later misses go
   *  to a freshly-added task. undefined = not yet created today. */
  fixMissesAuto?: string[];
}

export interface PlanConfig {
  /** Target exam cluster (CLUSTERS[].value). */
  cluster: string;
  /** Target competition level. */
  level: Level;
  /** Competition date as epoch ms, or null for "no date set" (soft pacing). */
  eventDate: number | null;
  /** Optional daily question goal (Phase B pacing input; unused in A). */
  dailyGoal?: number;
  /** When the plan was created — the pacing ramp's origin (epoch ms). */
  createdTs: number;
  /** True once the first-run diagnostic was taken or explicitly skipped. */
  diagnosticDone?: boolean;
  /** The user's edits to today's plan (dismissals + custom tasks); self-pruning. */
  today?: DayPlan;
}

const LEVELS: Level[] = ["District", "Association", "ICDC"];

/** Local YYYY-MM-DD for an epoch ms (the day key for per-day overrides). */
export function localDateKey(ms: number): string {
  const d = new Date(ms);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * Milliseconds from `ms` until the next LOCAL midnight — how long a still-open
 * dashboard has before its day key rolls over (issue #32). Built from the
 * local-time Date constructor, so month/year ends and DST shifts come out right
 * (a local midnight that doesn't exist normalizes forward, still landing on the
 * next day). Always > 0 and under ~26h, so it fits setTimeout's 32-bit delay.
 */
export function msUntilNextLocalDay(ms: number): number {
  const d = new Date(ms);
  const next = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1, 0, 0, 0, 0);
  return next.getTime() - ms;
}

export interface DayOverrides {
  dismissed: string[];
  custom: CustomTask[];
  sessions: Record<string, string[]>;
  quizzes: Record<string, string[]>;
  fixMissesAuto: string[];
  /** The day's frozen recommended set, or undefined when not yet frozen today
   *  (an empty stored set reads as not-frozen — see DayPlan.recommended). */
  recommended?: CustomTask[];
}

/**
 * The active overrides for `dateKey` — the stored day plan when it's for that day,
 * otherwise empty (a stale override from a previous day is ignored, so the plan
 * regenerates fresh each day).
 */
export function overridesFor(config: PlanConfig | null, dateKey: string): DayOverrides {
  const t = config?.today;
  if (!t || t.date !== dateKey)
    return { dismissed: [], custom: [], sessions: {}, quizzes: {}, fixMissesAuto: [] };
  return {
    dismissed: t.dismissed,
    custom: t.custom,
    sessions: t.sessions ?? {},
    quizzes: t.quizzes ?? {},
    fixMissesAuto: t.fixMissesAuto ?? [],
    ...(t.recommended?.length ? { recommended: t.recommended } : {}),
  };
}

/**
 * Fold an edit into `config.today` for `dateKey` — the write-side counterpart of
 * `overridesFor`, so a day's state is only ever read and mutated under the SAME
 * key (issue #32: the dashboard rendered from a stamped `now` while its handlers
 * read the clock directly, and past local midnight the two disagreed — the write
 * reseeded a day the screen wasn't showing, blanking the plan on screen).
 *
 * Returns the config UNCHANGED (same object) when the mutator is a no-op on an
 * already-current day, so identity-based bail-outs upstream can skip a redundant
 * render + network write. A stale (or missing) `today` still reseeds, which is
 * the intended per-day reset.
 */
export function applyDayEdit(
  config: PlanConfig | null,
  dateKey: string,
  mut: (day: DayPlan) => DayPlan,
): PlanConfig | null {
  if (!config) return config;
  const base: DayPlan =
    config.today && config.today.date === dateKey
      ? config.today
      : { date: dateKey, dismissed: [], custom: [] };
  const next = mut(base);
  if (next === config.today) return config; // no-op edit on the current day
  return { ...config, today: next };
}

const asStringArray = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];

/** Coerce a jsonb value into a Record<string, string[]> (drops empty entries). */
function coerceIdMap(raw: unknown): Record<string, string[]> | undefined {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return undefined;
  const out: Record<string, string[]> = {};
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    const ids = asStringArray(v);
    if (ids.length > 0) out[k] = ids;
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

const TASK_TYPES: PlanTaskType[] = [
  "warmup",
  "weak-drill",
  "coverage",
  "fix-misses",
  "challenge",
  "milestone",
];
const HINTS: DifficultyHint[] = ["build", "mixed", "challenge"];
const MIXES: MixPreset[] = ["exam-real", "balanced", "challenge"];

function coerceLaunch(raw: unknown): LaunchRef | null {
  if (!raw || typeof raw !== "object") return null;
  const l = raw as Record<string, unknown>;
  if (l.kind === "review") return { kind: "review" };
  const cluster = typeof l.cluster === "string" ? l.cluster : null;
  const level =
    typeof l.level === "string" && LEVELS.includes(l.level as Level) ? (l.level as Level) : null;
  const count =
    typeof l.count === "number" && Number.isFinite(l.count) && l.count > 0 ? l.count : null;
  if (!cluster || !level || !count) return null;
  if (l.kind === "drill" && typeof l.pi === "string" && typeof l.area === "string") {
    return { kind: "drill", cluster, level, pi: l.pi, area: l.area, count };
  }
  if (l.kind === "quiz" && typeof l.mix === "string" && MIXES.includes(l.mix as MixPreset)) {
    return { kind: "quiz", cluster, level, mix: l.mix as MixPreset, count };
  }
  return null;
}

function coerceCustomTask(raw: unknown): CustomTask | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.id !== "string") return null;
  if (typeof r.type !== "string" || !TASK_TYPES.includes(r.type as PlanTaskType)) return null;
  if (typeof r.title !== "string" || !r.title.trim()) return null;
  const launch = coerceLaunch(r.launch);
  if (!launch) return null;
  const difficultyHint = HINTS.includes(r.difficultyHint as DifficultyHint)
    ? (r.difficultyHint as DifficultyHint)
    : "mixed";
  const size = typeof r.size === "number" && Number.isFinite(r.size) && r.size > 0 ? r.size : 1;
  let target: CustomTask["target"];
  if (r.target && typeof r.target === "object") {
    const t = r.target as Record<string, unknown>;
    if (typeof t.cluster === "string" && typeof t.level === "string" && LEVELS.includes(t.level as Level)) {
      target = {
        cluster: t.cluster,
        level: t.level as Level,
        ...(typeof t.pi === "string" ? { pi: t.pi } : {}),
        ...(typeof t.area === "string" ? { area: t.area } : {}),
      };
    }
  }
  return {
    id: r.id,
    type: r.type as PlanTaskType,
    title: r.title,
    subtitle: typeof r.subtitle === "string" ? r.subtitle : "",
    size,
    difficultyHint,
    launch,
    ...(target ? { target } : {}),
    ...(Array.isArray(r.missIds) ? { missIds: asStringArray(r.missIds) } : {}),
  };
}

function coerceDayPlan(raw: unknown): DayPlan | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const r = raw as Record<string, unknown>;
  if (typeof r.date !== "string" || !r.date) return undefined;
  const custom = Array.isArray(r.custom)
    ? r.custom.map(coerceCustomTask).filter((t): t is CustomTask => t !== null)
    : [];
  const sessions = coerceIdMap(r.sessions);
  const quizzes = coerceIdMap(r.quizzes);
  // A stored set that coerces to nothing — an empty array, or N specs that all fail
  // validation (schema drift) — is NOT a freeze: it reads back as undefined so the
  // day re-derives, rather than pinning an empty plan until midnight (issue #66).
  const coercedRec = Array.isArray(r.recommended)
    ? r.recommended.map(coerceCustomTask).filter((t): t is CustomTask => t !== null)
    : undefined;
  const recommended = coercedRec?.length ? coercedRec : undefined;
  return {
    date: r.date,
    dismissed: asStringArray(r.dismissed),
    custom,
    ...(sessions ? { sessions } : {}),
    ...(quizzes ? { quizzes } : {}),
    ...(Array.isArray(r.fixMissesAuto) ? { fixMissesAuto: asStringArray(r.fixMissesAuto) } : {}),
    ...(recommended ? { recommended } : {}),
  };
}

/**
 * Validate/coerce the schemaless jsonb column (or a cached blob) into a
 * PlanConfig, or null when it isn't a usable config. Defensive: a partial or
 * malformed value reads as "no plan yet" rather than throwing.
 */
export function coercePlanConfig(raw: unknown): PlanConfig | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.cluster !== "string" || !r.cluster) return null;
  if (typeof r.level !== "string" || !LEVELS.includes(r.level as Level)) return null;
  const eventDate =
    typeof r.eventDate === "number" && Number.isFinite(r.eventDate)
      ? r.eventDate
      : null;
  const createdTs =
    typeof r.createdTs === "number" && Number.isFinite(r.createdTs)
      ? r.createdTs
      : 0;
  return {
    cluster: r.cluster,
    level: r.level as Level,
    eventDate,
    dailyGoal:
      typeof r.dailyGoal === "number" && Number.isFinite(r.dailyGoal)
        ? r.dailyGoal
        : undefined,
    createdTs,
    diagnosticDone: r.diagnosticDone === true,
    today: coerceDayPlan(r.today),
  };
}

// ---- per-uid localStorage cache (flash avoidance) --------------------------

const cacheKey = (uid: string) => `deck-plan-config:${uid}`;

/** Read the cached config for a uid, or null (missing / blocked / corrupt). */
export function readPlanConfigCache(uid: string): PlanConfig | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const raw = localStorage.getItem(cacheKey(uid));
    return raw ? coercePlanConfig(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

/** Write (or, with null, clear) the cached config for a uid. Best-effort. */
export function writePlanConfigCache(uid: string, cfg: PlanConfig | null): void {
  if (typeof localStorage === "undefined") return;
  try {
    if (cfg) localStorage.setItem(cacheKey(uid), JSON.stringify(cfg));
    else localStorage.removeItem(cacheKey(uid));
  } catch {
    /* storage blocked — the cache just won't persist this session */
  }
}

// ---- per-uid "cache is ahead of the row" marker (issue #181) ---------------
//
// The cache above is written OPTIMISTICALLY, before the profiles row has accepted
// the edit. This marker records that the cached config is AHEAD of the row, so the
// load path can tell "the server has the newest config" from "the server has a
// STALE config because my write never landed" — without it, a failed write is
// silently reverted on the next load and the user loses a session attribution, a
// saved quiz set, or the day's frozen plan.
//
// It is a marker, not a queue. PlanConfig is a single last-write-wins blob, so the
// only thing worth re-sending is the NEWEST cached value; replaying superseded
// snapshots (what the attempt-log outbox does, correctly, for an append-only log)
// would be wrong here. It also lives beside the cache rather than in IndexedDB
// because it is only ever meaningful together with the cached value it describes.

const dirtyKey = (uid: string) => `deck-plan-config-dirty:${uid}`;

/** True when this uid's cached config holds an edit not known to have landed. */
export function readPlanConfigDirty(uid: string): boolean {
  if (typeof localStorage === "undefined") return false;
  try {
    return localStorage.getItem(dirtyKey(uid)) === "1";
  } catch {
    return false;
  }
}

/** Set/clear the unsynced-edit marker for a uid. Best-effort.
 *
 *  When storage is blocked this silently does nothing, and the behaviour degrades
 *  to exactly what it was before the marker existed (an in-flight write is still
 *  retried for the life of the tab; only the survives-a-reload guarantee is lost).
 *  That is the right failure mode: the marker exists to protect an edit, so being
 *  unable to record it must never block making it. */
export function writePlanConfigDirty(uid: string, dirty: boolean): void {
  if (typeof localStorage === "undefined") return;
  try {
    if (dirty) localStorage.setItem(dirtyKey(uid), "1");
    else localStorage.removeItem(dirtyKey(uid));
  } catch {
    /* storage blocked — see above */
  }
}
