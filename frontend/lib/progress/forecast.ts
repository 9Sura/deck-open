// The 3-day plan forecast (plan 09 §9). A PURE projection that runs the SAME plan
// brain (buildStudyPlan) forward one simulated day at a time — it is NOT a second
// model. Nothing here is stored (plan-08 D8 / BD2): the caller re-derives it every
// load, so finishing tasks and today's accuracy visibly bend +1 / +2.
//
// The model (§9.1):
//  - Day 0 IS the Phase-A plan (passed in verbatim — never recomputed a second way,
//    so the calendar and Today's-Plan can never disagree).
//  - Days +1 / +2 are PROJECTED: take the prior day's plan, SIMULATE completing its
//    not-yet-done tasks (append synthetic attempts for each task's target PI/area,
//    correct at the user's recent per-difficulty accuracy), advance the mastery /
//    coverage / readiness / error roll-ups by re-running the engines over the
//    projected log, then re-run buildStudyPlan with `now` advanced k CALENDAR days.
//  - Today's ACTUAL results are already in the log, and only the REMAINING work is
//    simulated (task.size − progress.current) — so partial completion + how well you
//    did today reshape tomorrow. The simulation is COARSE (per-task, not per-question)
//    so it stays cheap: a few brain runs over a synthetic log.
//
// PURITY (React Compiler is strict): deterministic, seeded off the day index, `now`
// injected. No Date.now()/argless new Date() — `new Date(ms)` and the local-time
// `new Date(y, m, d, …)` (both ARG forms) are fine. Synthetic ids are index-derived,
// never random.

import type { Attempt } from "@/lib/progress/types";
import type { Difficulty } from "@/lib/question-bank";
import type { Level } from "@/lib/deca";
import {
  accuracySummary,
  areaMastery,
  areasForClusterWithDrift,
  groupByPI,
  readiness,
  weakestPIs,
  type WeakPI,
} from "@/lib/progress/mastery";
import { errorLog } from "@/lib/progress/errors";
import { buildStudyPlan, type Pacing, type PlanTask, type StudyPlan } from "@/lib/progress/plan";
import { localDateKey, type DifficultyHint, type PlanConfig } from "@/lib/progress/plan-config";

const DIFFS: Difficulty[] = ["easy", "medium", "hard"];

/**
 * `ms` advanced by `k` LOCAL CALENDAR days, keeping the time of day.
 *
 * NOT `ms + k * 86_400_000` (issue #122). A fixed 24h step is wrong on a DST
 * boundary: a fall-back day is 25h long, so +24h lands back inside the SAME local
 * day and two DayForecasts get the same `date` — which plan-calendar's last-wins
 * `byDate` map then resolves to the projected day instead of the live one. (A
 * spring-forward day is 23h, so the 48h step overshoots and skips a day.) Building
 * the timestamp from the local-time Date constructor makes each day's key distinct
 * by construction, exactly as msUntilNextLocalDay does in plan-config.
 */
function addLocalDays(ms: number, k: number): number {
  const d = new Date(ms);
  return new Date(
    d.getFullYear(),
    d.getMonth(),
    d.getDate() + k,
    d.getHours(),
    d.getMinutes(),
    d.getSeconds(),
    d.getMilliseconds(),
  ).getTime();
}

/** One day of the rolling forecast. Derived, never stored (BD2). `dayOffset` 0 is
 *  today (live), 1/2 are projected + read-only (BD3). `ts` carries the simulated
 *  day's epoch for weekday formatting in the view. */
export interface DayForecast {
  date: string;
  ts: number;
  dayOffset: number;
  tasks: PlanTask[];
  pacing: Pacing;
  projected: boolean;
}

export interface ForecastInput {
  /** The already-built day-0 plan — forecast[0] IS this (never recomputed, §9.2). */
  plan: StudyPlan;
  /** The FULL (unscoped) attempt log — the simulation's starting point; every
   *  future day's roll-ups recompute from this + synthetic attempts. */
  attempts: Attempt[];
  config: PlanConfig;
  now: number;
  /** Number of days in the window, including today (default 3 → today, +1, +2). */
  horizon?: number;
  /** The SAME bank-supply caps day 0 was built with (issue #160). Without them the
   *  projected days fall back to the nominal targets inside buildStudyPlan, so a
   *  Learn card the bank can supply once reads ×1 in Today's Plan and ×3 in the
   *  Tomorrow cell — two surfaces disagreeing about one task on one screen — and a
   *  zero-supply card day 0 DROPS (`drawable`) still previews with a "planned" chip
   *  and no Start, i.e. work that can never be launched.
   *
   *  These are a SNAPSHOT of today and are passed through unchanged, so the cap is
   *  slightly generous on +1/+2: the weak-drill half (a PI's total question count)
   *  genuinely doesn't move, but the Learn half (UNANSWERED questions in an area)
   *  shrinks as the simulation consumes them, and a PI that only becomes weak
   *  tomorrow has no entry at all and falls back to nominal. Rebuilding the map per
   *  projected day would need the raw per-area / per-PI counts and a second copy of
   *  the caller's seen/unseen rule — a silent-drift risk for precision the calendar
   *  already disclaims ("expected · firms up each day"). Deliberate. */
  availabilityByPI?: Record<string, number>;
  bankTotal?: number;
}

// A concrete target a synthetic attempt is attributed to.
interface SimTarget {
  cluster: string;
  level: Level;
  area: string;
  pi: string;
}

// How a task's difficulty hint spreads its simulated questions across difficulties.
// Mirrors the spirit of the bank mix presets (build = easy-leaning confidence work;
// mixed = balanced; challenge = hard-heavy).
const HINT_MIX: Record<DifficultyHint, Record<Difficulty, number>> = {
  build: { easy: 0.5, medium: 0.4, hard: 0.1 },
  mixed: { easy: 0.25, medium: 0.5, hard: 0.25 },
  challenge: { easy: 0.1, medium: 0.4, hard: 0.5 },
};

/**
 * Recent per-difficulty accuracy over the scoped log (a window of the newest
 * attempts). This is the rate the projection assumes you'll keep — "if you keep
 * pace at your current level." Thin difficulties fall back to overall, then to a
 * neutral 0.5, so a cold start projects modestly rather than wildly.
 */
function accuracyByDifficulty(scoped: Attempt[], window = 80): Record<Difficulty, number> {
  const recent = [...scoped].sort((a, b) => b.ts - a.ts).slice(0, window);
  const overall = accuracySummary(recent);
  const out = {} as Record<Difficulty, number>;
  for (const d of DIFFS) {
    const s = accuracySummary(recent.filter((a) => a.difficulty === d));
    out[d] =
      s.answered >= 3 ? s.accuracy : overall.answered >= 3 ? overall.accuracy : 0.5;
  }
  return out;
}

/** Largest-remainder split of `n` questions across the difficulty mix (integers). */
function allocate(n: number, mix: Record<Difficulty, number>): Record<Difficulty, number> {
  if (n <= 0) return { easy: 0, medium: 0, hard: 0 };
  const raw = DIFFS.map((d) => n * mix[d]);
  const counts = raw.map((v) => Math.floor(v));
  let used = counts.reduce((s, v) => s + v, 0);
  const order = DIFFS.map((_, i) => ({ i, rem: raw[i] - counts[i] })).sort(
    (a, b) => b.rem - a.rem,
  );
  let k = 0;
  while (used < n) {
    counts[order[k % DIFFS.length].i]++;
    used++;
    k++;
  }
  const out = {} as Record<Difficulty, number>;
  DIFFS.forEach((d, i) => (out[d] = counts[i]));
  return out;
}

/**
 * The PIs a task's simulated attempts attribute to. A PI-scoped drill targets its
 * one PI; a cluster-wide quiz (warm-up / challenge / milestone) spreads across the
 * day's weakest PIs — which already interleave never-practiced ones, so a mixed
 * quiz realistically both raises weak spots and fills coverage.
 */
function targetsForTask(task: PlanTask, weakness: WeakPI[]): SimTarget[] {
  const t = task.target;
  if (t?.pi && t.area) {
    return [{ cluster: t.cluster, level: t.level, area: t.area, pi: t.pi }];
  }
  return weakness
    .slice(0, 6)
    .map((w) => ({ cluster: w.cluster, level: w.level, area: w.area, pi: w.pi }));
}

/** Synthetic attempts standing in for completing `remaining` of a practice task. */
function syntheticAttempts(
  task: PlanTask,
  remaining: number,
  targets: SimTarget[],
  acc: Record<Difficulty, number>,
  baseTs: number,
  dayIndex: number,
  seqStart: number,
): { attempts: Attempt[]; nextSeq: number } {
  if (remaining <= 0 || targets.length === 0) return { attempts: [], nextSeq: seqStart };
  const alloc = allocate(remaining, HINT_MIX[task.difficultyHint]);
  const out: Attempt[] = [];
  let seq = seqStart;
  for (const d of DIFFS) {
    const count = alloc[d];
    if (count === 0) continue;
    // Deterministic: the first round(count·accuracy) in this bucket are correct.
    const correctCount = Math.round(count * acc[d]);
    for (let i = 0; i < count; i++) {
      const target = targets[seq % targets.length];
      const correct = i < correctCount;
      const id = `sim-${dayIndex}-${seq}`;
      out.push({
        id,
        ts: baseTs + seq * 1000,
        questionId: id,
        cluster: target.cluster,
        level: target.level,
        instructionalArea: target.area,
        performanceIndicator: target.pi,
        difficulty: d,
        chosen: correct ? "A" : "B",
        correct,
        elapsedMs: 20_000,
        source: "focus",
        sessionId: `sim-session-${dayIndex}`,
      });
      seq++;
    }
  }
  return { attempts: out, nextSeq: seq };
}

/** Synthetic correct answers that RESOLVE up to `remaining` still-open misses —
 *  reusing each miss's real questionId so errorLog() marks it resolved. */
function resolveMisses(
  log: Attempt[],
  remaining: number,
  baseTs: number,
  dayIndex: number,
  seqStart: number,
): { attempts: Attempt[]; nextSeq: number } {
  if (remaining <= 0) return { attempts: [], nextSeq: seqStart };
  const open = errorLog(log)
    .filter((e) => !e.resolved)
    .slice(0, remaining);
  const out: Attempt[] = [];
  let seq = seqStart;
  for (const e of open) {
    out.push({
      id: `sim-fix-${dayIndex}-${seq}`,
      ts: baseTs + seq * 1000,
      questionId: e.questionId,
      cluster: e.cluster,
      level: e.level,
      instructionalArea: e.instructionalArea,
      performanceIndicator: e.performanceIndicator,
      difficulty: e.difficulty,
      chosen: "A",
      correct: true,
      elapsedMs: 20_000,
      source: "review-lab",
      sessionId: `sim-session-${dayIndex}`,
    });
    seq++;
  }
  return { attempts: out, nextSeq: seq };
}

/**
 * Advance the log by simulating completion of `dayTasks`. Only NOT-done tasks and
 * their REMAINING questions are simulated (today's real results already sit in the
 * log). Returns the projected log for the next day.
 */
function simulateDay(
  log: Attempt[],
  dayTasks: PlanTask[],
  acc: Record<Difficulty, number>,
  weakness: WeakPI[],
  baseTs: number,
  dayIndex: number,
): Attempt[] {
  const synth: Attempt[] = [];
  let seq = 0;
  for (const task of dayTasks) {
    if (task.done) continue;
    const remaining = task.size - task.progress.current;
    if (remaining <= 0) continue;
    if (task.type === "fix-misses") {
      const r = resolveMisses([...log, ...synth], remaining, baseTs, dayIndex, seq);
      synth.push(...r.attempts);
      seq = r.nextSeq;
    } else {
      const r = syntheticAttempts(
        task,
        remaining,
        targetsForTask(task, weakness),
        acc,
        baseTs,
        dayIndex,
        seq,
      );
      synth.push(...r.attempts);
      seq = r.nextSeq;
    }
  }
  return synth.length > 0 ? [...log, ...synth] : log;
}

/**
 * Project the plan across a rolling window. forecast[0] is the live Phase-A plan;
 * each later day is the same brain re-run over a log advanced by simulating the
 * prior day's completion at the user's recent accuracy (§9.1).
 */
export function forecastPlan(input: ForecastInput): DayForecast[] {
  const { plan, attempts, config, now } = input;
  const horizon = input.horizon ?? 3;
  const { cluster, level } = config;

  const scoped0 = attempts.filter((a) => a.cluster === cluster && a.level === level);
  const acc = accuracyByDifficulty(scoped0);

  const days: DayForecast[] = [
    {
      date: localDateKey(now),
      ts: now,
      dayOffset: 0,
      tasks: plan.tasks,
      pacing: plan.pacing,
      projected: false,
    },
  ];

  let log = attempts;
  let weakness = weakestPIs(log, { cluster, level });
  let dayTasks = plan.tasks;

  for (let k = 1; k < horizon; k++) {
    const dayTs = addLocalDays(now, k);
    // Simulate completing the PRIOR day's remaining tasks, then re-derive.
    log = simulateDay(log, dayTasks, acc, weakness, dayTs, k);
    const scoped = log.filter((a) => a.cluster === cluster && a.level === level);
    const byPI = groupByPI(scoped);
    weakness = weakestPIs(log, { cluster, level });
    const errors = errorLog(log);
    const read = readiness(cluster, level, log);
    const areaRollups = areasForClusterWithDrift(cluster, level, byPI).map((a) =>
      areaMastery(cluster, a, level, byPI),
    );
    const projected = buildStudyPlan({
      attempts: scoped,
      weakness,
      errors,
      readiness: read,
      areaRollups,
      config,
      // Same supply caps as day 0 (#160) — NOT `overrides`, which is today's user
      // edits and correctly stays out of a projection.
      availabilityByPI: input.availabilityByPI,
      bankTotal: input.bankTotal,
      now: dayTs,
    });
    days.push({
      date: localDateKey(dayTs),
      ts: dayTs,
      dayOffset: k,
      tasks: projected.tasks,
      pacing: projected.pacing,
      projected: true,
    });
    dayTasks = projected.tasks;
  }

  return days;
}
