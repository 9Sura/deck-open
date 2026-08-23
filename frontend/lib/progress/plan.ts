// The study-plan brain (plan 09 §4.2). A PURE selector that ranks + sequences the
// work the app can already launch into a short, ordered daily plan, plus a
// date-based pacing read. Nothing here is stored (plan-08 D8 holds): the caller
// re-derives this from the live synced log every load, so finishing a task
// instantly reshapes the plan — the same wiring that makes /progress update live.
//
// PURITY (React Compiler is strict): no Date.now()/argless new Date() — the caller
// stamps `now` and passes it in. `new Date(now)` WITH an argument is deterministic
// and allowed (used only to find the local-midnight "done today" boundary).
//
// The ranking reuses the existing engines rather than inventing a new score:
// weakestPIs() already interleaves confident-low-mastery PIs with never-practiced
// ones; errorLog() already surfaces unresolved misses; readiness() already blends
// area mastery. This module just turns those into launchable task cards.

import type { Attempt } from "@/lib/progress/types";
import type { AreaMastery, Readiness, WeakPI } from "@/lib/progress/mastery";
import type { ErrorItem } from "@/lib/progress/errors";
import type { Level } from "@/lib/deca";
import type {
  CustomTask,
  DayOverrides,
  DifficultyHint,
  LaunchRef,
  PlanConfig,
  PlanTaskType,
} from "@/lib/progress/plan-config";

export type { LaunchRef, PlanTaskType } from "@/lib/progress/plan-config";

// ---------------------------------------------------------------- constants
// First-guess heuristics, tunable in one place (mirrors mastery.ts's stance).

/** The readiness the pacing ramp targets by the competition date. */
export const TARGET_READINESS = 0.82;
/** ± band around expected readiness that still counts as "on track". */
export const PACING_BAND = 0.06;
/** Below this backing-sample size the plan bootstraps (warm-up first). */
export const COLD_SAMPLE = 12;
/** Actual readiness at/above which a challenge task is offered. */
export const CHALLENGE_READINESS = 0.6;
/** Actual readiness at/above which a full milestone test is offered. */
export const MILESTONE_READINESS = 0.75;
/** Within this many days of the date, always offer a milestone test. */
export const MILESTONE_DAYS = 10;
/** Soft cap on recommended tasks/day; each user-added custom task lowers it by 1. */
export const TASK_BUDGET = 5;

const DAY = 86_400_000;
const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));

/** Below this per-PI mastery a weak-PI drill eases in on confidence-building
 *  questions; at/above it the drill tilts to a mixed set (Phase B #2 — a task's
 *  difficulty adapts to how the student is actually doing on that PI). */
export const DRILL_BUILD_CEILING = 0.4;

/** Adaptive difficulty for a weak-PI drill from its recency-weighted mastery. */
export const drillHint = (mastery: number): DifficultyHint =>
  mastery < DRILL_BUILD_CEILING ? "build" : "mixed";

// -------------------------------------------------------------------- types

export interface PlanTask {
  id: string;
  type: PlanTaskType;
  title: string;
  subtitle: string;
  target?: { cluster: string; level: Level; pi?: string; area?: string };
  size: number;
  difficultyHint: DifficultyHint;
  launch: LaunchRef;
  /** True for user-added tasks (delete), false/undefined for recommended (dismiss). */
  added?: boolean;
  /** For a fix-misses task: the snapshot of miss questionIds this batch owns —
   *  carried through from its stored spec so freezing the day's set (`toSpec`)
   *  can put it back. Absent on every other task type. */
  missIds?: string[];
  /** Progress toward completion, derived from TODAY's attempts — never persisted.
   *  `current`/`total` drive the per-task status bar; done ⇔ current >= total. */
  progress: { current: number; total: number };
  /** Derived from TODAY's attempts (local-midnight boundary) — never persisted. */
  done: boolean;
}

export interface Pacing {
  daysLeft: number | null;
  expectedReadiness: number;
  actualReadiness: number;
  status: "ahead" | "on-track" | "behind" | "no-date";
}

export interface PlanInput {
  /** Attempts already filtered to config.cluster + config.level. */
  attempts: Attempt[];
  /** weakestPIs(attempts, { cluster, level }) — ranked weakest-first. */
  weakness: WeakPI[];
  /** errorLog(attempts) — the miss log for the fix-your-misses task. */
  errors: ErrorItem[];
  /** readiness(cluster, level, attempts) — headline + pacing input. */
  readiness: Readiness;
  /** Per-area roll-ups (for challenge target flavour); optional. */
  areaRollups?: AreaMastery[];
  config: PlanConfig;
  /** Today's user edits: dismissed recommended ids + custom tasks (plan follow-up). */
  overrides?: DayOverrides;
  /** PI → how many questions its drill could actually assemble right now (a Learn
   *  card: unanswered questions in that PI's area; a weak-area drill: questions for
   *  that PI). Lets a card show its TRUE size before launch — never 8 when only 4
   *  exist. Async-loaded by the caller; absent ⇒ fall back to the nominal target. */
  availabilityByPI?: Record<string, number>;
  /** Total candidate questions for this cluster×level — the ceiling for the quiz-type
   *  tasks (warm-up / challenge / milestone) that draw from the whole cluster. Lets
   *  those cards be honest too if the cluster is thin. Absent ⇒ nominal target. */
  bankTotal?: number;
  now: number;
}

export interface StudyPlan {
  tasks: PlanTask[];
  pacing: Pacing;
  /** The recommended-task specs to freeze for the day. On the first build of a day
   *  this is the freshly-derived set; the caller persists it (config.today.recommended)
   *  so later builds render this fixed set instead of re-deriving. Idempotent once
   *  frozen. Excludes user-added tasks (those live in config.today.custom). */
  freeze: CustomTask[];
  /** True when the backing sample is too thin to derive a real plan (< COLD_SAMPLE),
   *  so this build is the warm-up-only bootstrap. A cold plan is meant to be
   *  RE-DERIVED as the first attempts land — the caller must never freeze it for the
   *  day (issue #61: freezing before the log loaded pinned a full-history user to a
   *  single warm-up card until local midnight). */
  cold: boolean;
}

// ------------------------------------------------------------- the brain

/**
 * Turn the live mastery/error roll-ups + the plan config into an ordered daily
 * plan and a pacing read. Ordering is intentional: bootstrap → confident
 * weaknesses → coverage gaps → fix misses → stretch (challenge / milestone).
 * Intensity (task count / difficulty tilt) scales with the date and pacing.
 */
export function buildStudyPlan(input: PlanInput): StudyPlan {
  const { attempts, weakness, errors, readiness, areaRollups, config, now } = input;
  const overrides: DayOverrides = input.overrides ?? {
    dismissed: [],
    custom: [],
    sessions: {},
    quizzes: {},
    fixMissesAuto: [],
  };
  const { cluster, level } = config;

  // ---- pacing -------------------------------------------------------------
  const actual = readiness.readiness;
  const daysLeft =
    config.eventDate != null
      ? Math.max(0, Math.ceil((config.eventDate - now) / DAY))
      : null;

  let expected = actual;
  let status: Pacing["status"] = "no-date";
  if (config.eventDate != null) {
    const span = config.eventDate - config.createdTs;
    const frac = span > 0 ? clamp((now - config.createdTs) / span, 0, 1) : 1;
    expected = TARGET_READINESS * frac;
    const diff = actual - expected;
    status =
      diff > PACING_BAND ? "ahead" : diff < -PACING_BAND ? "behind" : "on-track";
  }
  const pacing: Pacing = {
    daysLeft,
    expectedReadiness: expected,
    actualReadiness: actual,
    status,
  };

  // ---- completion boundary ------------------------------------------------
  // A launchable task's progress counts ONLY the attempts from the session(s) its
  // own Start launched (tracked in overrides.sessions[taskId]) — NOT any matching
  // attempt elsewhere. So answering questions in another task (or /review, or a
  // quick action) never bleeds into this one. Clamped so a bar never overfills.
  const prog = (current: number, total: number) => ({
    current: Math.min(current, total),
    total,
  });
  const countInSessions = (taskId: string) => {
    const ids = overrides.sessions?.[taskId];
    if (!ids || ids.length === 0) return 0;
    const set = new Set(ids);
    return attempts.filter((a) => set.has(a.sessionId)).length;
  };

  // A task's TRUE size: once its quiz has been generated, the bank may have had
  // fewer questions for that PI than the nominal target, so the persisted set is
  // the real total (fixes "the task shows more questions than the bank has" and
  // makes a thin-PI task actually reachable). Before first launch we show the
  // nominal estimate.
  const sizeFor = (taskId: string, nominal: number) => {
    const saved = overrides.quizzes?.[taskId]?.length ?? 0;
    return saved > 0 ? saved : nominal;
  };

  // A PI drill's nominal size, capped by how many questions it could actually draw
  // right now (per input.availabilityByPI) — so a weak-area or Learn card shows its
  // TRUE size before launch (e.g. 4, not 8) instead of correcting only after Start.
  // Once the quiz is generated, sizeFor's saved-length wins over this estimate.
  const availNominal = (pi: string | undefined, target: number) => {
    const avail = pi != null ? input.availabilityByPI?.[pi] : undefined;
    return avail != null ? Math.min(target, avail) : target;
  };
  // Same idea for cluster-wide quiz tasks (warm-up / challenge / milestone): cap the
  // target by the total questions available, so a thin cluster shows an honest count.
  const availQuiz = (target: number) =>
    input.bankTotal != null ? Math.min(target, input.bankTotal) : target;

  // A task the bank can't supply a single question for (a PI the inventory lists
  // that this level's files no longer carry, or a Learn card whose area the user
  // has already answered out) must never reach the UI: size 0 makes `current >=
  // size` trivially true, painting a ✓ "0/0" card with no Start button for work
  // that was never done. Dropping it is safe — `sizeFor` pins a launched task's
  // size to its persisted question set, so only a NEVER-STARTED task can be 0
  // here and no progress can be hidden. A fix-misses task's size IS its snapshot
  // length (fixMissesFrom), so the same rule holds for it: a batch with no ids
  // owns nothing, can never reach `done` (which requires total > 0), and has no
  // questions to launch — drop it rather than strand a permanent 0/1 card.
  const drawable = (t: PlanTask) => t.size > 0;

  // Fix-misses is BATCH-based: a task owns a snapshot of miss questionIds and
  // completes when all of them are RESOLVED — then it stays done and its count is
  // frozen, even as new misses appear (a new batch is handled by adding a task).
  // A snapshot id no longer in the error log (e.g. progress reset) counts cleared.
  const missResolved = new Map(errors.map((e) => [e.questionId, e.resolved]));
  const clearedIn = (ids: string[]) =>
    ids.filter((id) => missResolved.get(id) !== false).length;
  const fixMissesFrom = (
    id: string,
    ids: string[],
  ): { progress: PlanTask["progress"]; done: boolean; title: string; subtitle: string; size: number } => {
    const total = ids.length;
    const cleared = clearedIn(ids);
    const remaining = total - cleared;
    return {
      title:
        remaining > 0
          ? `Fix ${remaining} miss${remaining === 1 ? "" : "es"}`
          : "Misses cleared",
      subtitle:
        remaining > 0
          ? "Re-answer the questions you got wrong"
          : "This batch is all cleared",
      size: total,
      progress: { current: cleared, total: Math.max(total, 1) },
      done: total > 0 && remaining === 0,
    };
  };

  // Materialize a stored task SPEC (a user-added task, or a frozen recommended one)
  // into a live PlanTask: session-based progress like a recommended task of that
  // kind, or its own miss-batch snapshot for fix-misses, with the size reconciled to
  // the actual generated set. `added` distinguishes the two for the UI (delete vs
  // dismiss); the tracking is identical.
  const materialize = (c: CustomTask, added: boolean): PlanTask => {
    if (c.type === "fix-misses") {
      const f = fixMissesFrom(c.id, c.missIds ?? []);
      return {
        id: c.id,
        type: c.type,
        title: f.title,
        subtitle: f.subtitle,
        ...(c.target ? { target: c.target } : {}),
        size: f.size,
        difficultyHint: c.difficultyHint,
        launch: c.launch,
        // Keep the snapshot on the live task so `toSpec` can freeze it back —
        // without it a frozen batch re-materializes empty and strands at 0/1.
        ...(c.missIds ? { missIds: c.missIds } : {}),
        progress: f.progress,
        done: f.done,
        ...(added ? { added: true } : {}),
      };
    }
    const nominal =
      c.type === "coverage" || c.type === "weak-drill"
        ? availNominal(c.target?.pi, c.size)
        : c.type === "warmup" || c.type === "challenge" || c.type === "milestone"
          ? availQuiz(c.size)
          : c.size;
    const size = sizeFor(c.id, nominal);
    const current = countInSessions(c.id);
    return {
      id: c.id,
      type: c.type,
      title: c.title,
      subtitle: c.subtitle,
      ...(c.target ? { target: c.target } : {}),
      size,
      difficultyHint: c.difficultyHint,
      launch: c.launch,
      progress: prog(current, size),
      done: size > 0 && current >= size,
      ...(added ? { added: true } : {}),
    };
  };

  // ---- intensity ----------------------------------------------------------
  const cold = readiness.sampleN < COLD_SAMPLE;
  const behind = status === "behind";
  const weakCount = behind ? 3 : 2;
  const coverCount = cold ? 0 : behind ? 2 : 1;

  const tasks: PlanTask[] = [];

  // 1) Bootstrap warm-up when there's little/no evidence yet.
  if (cold) {
    const size = sizeFor("warmup", availQuiz(10));
    const current = countInSessions("warmup");
    tasks.push({
      id: "warmup",
      type: "warmup",
      title: "Warm-up quiz",
      subtitle: `A quick ${size}-question mixed set to seed your plan`,
      target: { cluster, level },
      size,
      difficultyHint: "mixed",
      launch: { kind: "quiz", cluster, level, mix: "balanced", count: size },
      progress: prog(current, size),
      done: size > 0 && current >= size,
    });
  }

  // 2) Confident weaknesses — low-mastery PIs you've actually shown you're weak on.
  //    Each drill's difficulty ADAPTS to that PI's mastery (Phase B #2): a rock-
  //    bottom PI eases in ("build"), a nearly-there one gets a "mixed" set.
  const seenWeak = weakness.filter((w) => w.seen && w.mastery < 0.6);
  for (const w of seenWeak.slice(0, weakCount)) {
    const size = sizeFor(`weak-${w.pi}`, availNominal(w.pi, 8));
    const current = countInSessions(`weak-${w.pi}`);
    tasks.push({
      id: `weak-${w.pi}`,
      type: "weak-drill",
      title: `Drill: ${w.pi}`,
      subtitle: `${w.area} · weak spot`,
      target: { cluster: w.cluster, level: w.level, pi: w.pi, area: w.area },
      size,
      difficultyHint: drillHint(w.mastery),
      launch: { kind: "drill", cluster: w.cluster, level: w.level, pi: w.pi, area: w.area, count: size },
      progress: prog(current, size),
      done: size > 0 && current >= size,
    });
  }

  // 3) Coverage gaps — never-practiced PIs (the drill falls back to the area).
  //    Ordered weakest-MEASURED-AREA first (Phase B #3): the diagnostic seeds
  //    area mastery, so early coverage fills the areas that baseline flagged
  //    weakest rather than an arbitrary uncovered PI.
  const areaMasteryByName = new Map((areaRollups ?? []).map((a) => [a.area, a.mastery]));
  const uncovered = weakness
    .filter((w) => !w.seen)
    .sort(
      (a, b) => (areaMasteryByName.get(a.area) ?? 1) - (areaMasteryByName.get(b.area) ?? 1),
    );
  for (const w of uncovered.slice(0, coverCount)) {
    // Learning drills are short (3) and draw from the "remaining bank" — questions
    // the student hasn't answered yet — so they stay fresh (see launchTaskQuiz). The
    // target is capped by what the area can actually supply, so the card is honest.
    const size = sizeFor(`cover-${w.pi}`, availNominal(w.pi, 3));
    const current = countInSessions(`cover-${w.pi}`);
    tasks.push({
      id: `cover-${w.pi}`,
      type: "coverage",
      title: `Learn: ${w.pi}`,
      subtitle: `${w.area} · never practiced`,
      target: { cluster: w.cluster, level: w.level, pi: w.pi, area: w.area },
      size,
      difficultyHint: "mixed",
      launch: { kind: "drill", cluster: w.cluster, level: w.level, pi: w.pi, area: w.area, count: size },
      progress: prog(current, size),
      done: size > 0 && current >= size,
    });
  }

  // 4) Fix your misses is NO LONGER auto-added (that error-driven insertion is what
  //    made "extra tests" appear mid-day). The day's recommended set is frozen once
  //    (see the folding below); a user who wants to grind misses adds a fix-misses
  //    task explicitly from the "Add a task" menu (materialized like any recommended
  //    task and tracked the same way). If it is ever re-added here, the pushed task
  //    MUST carry `missIds` — that snapshot is what `toSpec` freezes and what the
  //    next build re-materializes from (a batch frozen without it draws nothing).

  // 5) Stretch — a challenge set once you're solid enough to be pushed.
  if (!cold && actual >= CHALLENGE_READINESS) {
    const strongest = strongestArea(areaRollups);
    const size = sizeFor("challenge", availQuiz(10));
    const current = countInSessions("challenge");
    tasks.push({
      id: "challenge",
      type: "challenge",
      title: strongest ? `Challenge: ${strongest}` : "Challenge set",
      subtitle: "Hard-heavy mix to push your ceiling",
      target: { cluster, level, area: strongest ?? undefined },
      size,
      difficultyHint: "challenge",
      launch: { kind: "quiz", cluster, level, mix: "challenge", count: size },
      progress: prog(current, size),
      done: size > 0 && current >= size,
    });
  }

  // 6) Milestone — a full-length test as the date nears or you're near-ready.
  const nearDate = daysLeft != null && daysLeft <= MILESTONE_DAYS;
  if (!cold && (nearDate || actual >= MILESTONE_READINESS)) {
    const size = sizeFor("milestone", availQuiz(50));
    const current = countInSessions("milestone");
    tasks.push({
      id: "milestone",
      type: "milestone",
      title: "Milestone test",
      subtitle: `Exam-real ${size}-question check-in`,
      target: { cluster, level },
      size,
      difficultyHint: "mixed",
      launch: { kind: "quiz", cluster, level, mix: "exam-real", count: size },
      progress: prog(current, size),
      done: size > 0 && current >= size,
    });
  }

  // ---- fold in the user's edits for today (plan follow-up) ----------------
  // The recommended set is FROZEN for the day: once `overrides.recommended` is
  // captured (the first build of the day — the caller persists `freeze`), later
  // builds render that fixed set (progress recomputed live) instead of re-deriving,
  // so no new recommended tasks appear as stats shift during the day. `tasks` (the
  // fresh derivation) is what gets frozen on that first build. An EMPTY frozen set
  // is treated as "not frozen" and falls through to the fresh derivation — freezing
  // nothing would otherwise pin an empty plan for the rest of the day (issue #66).
  const recommendedSource: PlanTask[] = (
    overrides.recommended?.length ? overrides.recommended.map((c) => materialize(c, false)) : tasks
  ).filter(drawable);

  // Added tasks are materialized recommendation-type instances, tracked exactly
  // like recommended ones of that type. They lead the list. Recommended tasks the
  // user dismissed drop out (no backfill); the recommended count is trimmed by how
  // many were added so the day doesn't overload; and a recommended task is deduped
  // away when an added task already covers the same category/target.
  const customTasks: PlanTask[] = overrides.custom
    .map((c) => materialize(c, true))
    .filter(drawable);

  // Dedupe key: a PI-scoped drill keys by type+PI; fix-misses batches are distinct
  // (each owns its own miss snapshot) so they key by id and never collapse; other
  // singletons key by type.
  const keyOf = (t: { id: string; type: PlanTaskType; target?: { pi?: string } }) =>
    t.type === "fix-misses" ? t.id : t.target?.pi ? `${t.type}:${t.target.pi}` : t.type;
  const customKeys = new Set(overrides.custom.map(keyOf));
  const dismissed = new Set(overrides.dismissed);
  const recommended = recommendedSource
    .filter((t) => !dismissed.has(t.id))
    .filter((t) => !customKeys.has(keyOf(t)))
    .slice(0, Math.max(0, TASK_BUDGET - customTasks.length));

  // The specs to freeze for the day — the recommended source in stored form. On the
  // first build this is the fresh set; once frozen it round-trips unchanged.
  const freeze: CustomTask[] = recommendedSource.map(toSpec);

  return { tasks: [...customTasks, ...recommended], pacing, freeze, cold };
}

/** A recommended PlanTask reduced to its stored spec (for freezing the day's set). */
function toSpec(t: PlanTask): CustomTask {
  return {
    id: t.id,
    type: t.type,
    title: t.title,
    subtitle: t.subtitle,
    size: t.size,
    difficultyHint: t.difficultyHint,
    launch: t.launch,
    ...(t.target ? { target: t.target } : {}),
    // A fix-misses task's miss snapshot is the thing it tracks completion against;
    // dropping it here would freeze a batch that owns nothing.
    ...(t.missIds ? { missIds: t.missIds } : {}),
  };
}

/** The strongest (highest-mastery, actually-seen) area name, for challenge flavour. */
function strongestArea(rollups?: AreaMastery[]): string | null {
  if (!rollups || rollups.length === 0) return null;
  const seen = rollups.filter((a) => a.seenPICount > 0);
  if (seen.length === 0) return null;
  return seen.reduce((best, a) => (a.mastery > best.mastery ? a : best)).area;
}
