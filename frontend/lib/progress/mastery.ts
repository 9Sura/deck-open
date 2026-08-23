// The mastery engine (plan 08 §3, phase 2 sub-plan §3). A pure, transparent
// function from the Attempt log (+ the PI inventory) to per-PI / per-area /
// readiness numbers a student could understand if shown the formula.
//
// RECOMPUTED, NEVER STORED (D1): every selector here is pure over its inputs;
// the dashboard memoizes them, nothing is persisted. All tunable constants are
// named exports (D7) — these are first-guess heuristics, not a calibrated model.
//
// Granularity is cluster × level × area (locked): the PI universe (the coverage
// denominator) is level-scoped, so readiness/coverage reflect the actual exam
// level. A `level` of "all" unions the universe across levels and blends.
//
// Client-safe: pure TS, no React.

import type { Attempt, Session } from "@/lib/progress/types";
import type { Difficulty } from "@/lib/question-bank";
import type { Level } from "@/lib/deca";
import { bankClusters, clusterBlueprint } from "@/lib/question-bank";
import { areasForCluster, piUniverse, type LevelScope } from "@/lib/progress/inventory";
import { localDateKey } from "@/lib/progress/plan-config";

// ---------------------------------------------------------------- constants
// First-guess, tunable in one place (D7 / parent §10-Q3). Ship and calibrate
// against real attempt data — do not treat these as psychometrically settled.

/** A correct hard answer proves more than a correct easy one; a wrong easy one hurts more. */
export const DIFFICULTY_WEIGHT: Record<Difficulty, number> = {
  easy: 1.0,
  medium: 1.5,
  hard: 2.25,
};
/** Recency decay per rank (0 = newest). λ≈0.9 ⇒ the last ~10 attempts dominate. */
export const LAMBDA = 0.9;
/** Weak neutral Beta prior — a single lucky correct must not read as "100%". */
export const PRIOR_ALPHA = 1.5;
export const PRIOR_BETA = 1.5;
/** Effective sample size (Σw) below this ⇒ the estimate renders as "provisional". */
export const PROVISIONAL_EFFN = 3;
/** Σw at which a PI counts as fully covered (its coverage weight → 1). */
export const FULL_COVERAGE_EFFN = 4;
/** Weakness score assigned to an uncovered (never-attempted) PI — interleaves it
 *  among seen PIs on the weak-area board ("never practiced" is a real weakness). */
export const UNCOVERED_WEAKNESS = 0.55;
/** Provisional (thin-evidence) weaknesses are damped so one unlucky attempt
 *  doesn't dominate the board. */
export const PROVISIONAL_DAMPEN = 0.7;

// -------------------------------------------------------------------- types

export interface PIStats {
  mastery: number; // point estimate ∈ (0,1)
  coverage: number; // how "seen" this PI is ∈ [0,1]
  effectiveN: number; // Σw — effective sample size
  attempts: number; // raw attempt count
  provisional: boolean; // effectiveN < PROVISIONAL_EFFN
  lastTs: number; // most recent attempt ts (0 if none)
}

export interface PIMastery extends PIStats {
  cluster: string;
  area: string;
  pi: string;
}

export interface AreaMastery {
  cluster: string;
  area: string;
  mastery: number; // coverage-weighted over the WHOLE PI universe
  coverage: number; // fraction of the universe touched ∈ [0,1]
  piCount: number; // |universe| (incl. any seen-but-uncatalogued PIs)
  seenPICount: number;
  provisional: boolean;
}

export interface Readiness {
  cluster: string | "all";
  level: LevelScope;
  readiness: number; // blueprint-weighted blend of area masteries ∈ [0,1]
  sampleN: number; // number of attempts backing it (0 ⇒ "no data", not NaN)
}

export interface TrajectoryPoint {
  ts: number; // session.endedTs — the x-axis
  readiness: number;
}

export interface WeakPI extends PIMastery {
  seen: boolean; // has ≥1 attempt
  level: Level; // a concrete level to launch a Practice-this drill at
  weakness: number; // ranking score (higher = show first)
}

// --------------------------------------------------------------- indexing

/**
 * The separator for the grouping keys below. NUL can't occur in bank data, which
 * is what makes those keys unambiguously splittable — instructional areas and PIs
 * both contain spaces (15 of the 21 areas are multi-word), so a space separator
 * would make `Financial Analysis` indistinguishable from an area `Financial` with
 * a PI starting `Analysis`. Written as an escape, NOT a literal NUL byte: a raw
 * one makes git/grep treat this file as binary and file readers render it as a
 * space, which reads as a truncation bug that isn't there (issue #28).
 */
const KEY_SEP = "\u0000";

/** The grouping key for one PI's attempts. Level is intentionally NOT in the key —
 *  attempts are pre-filtered to the level scope before grouping. Split it only on
 *  `KEY_SEP`; never on a space. */
export const piKey = (cluster: string, area: string, pi: string): string =>
  `${cluster}${KEY_SEP}${area}${KEY_SEP}${pi}`;

/** Group a (pre-filtered) attempt set by PI once, for reuse across roll-ups (§3.5). */
export function groupByPI(attempts: Attempt[]): Map<string, Attempt[]> {
  const map = new Map<string, Attempt[]>();
  for (const a of attempts) {
    const k = piKey(a.cluster, a.instructionalArea, a.performanceIndicator);
    const list = map.get(k);
    if (list) list.push(a);
    else map.set(k, [a]);
  }
  return map;
}

// --------------------------------------------------------------- per-PI

const EMPTY_STATS: PIStats = {
  mastery: 0,
  coverage: 0,
  effectiveN: 0,
  attempts: 0,
  provisional: true,
  lastTs: 0,
};

/**
 * Difficulty-weighted, recency-weighted accuracy with a Beta prior, over the
 * attempts of a single PI. Any wrong attempt adds to Σw (evidence of not-knowing)
 * but never to ΣwC. Empty input ⇒ zeroed, provisional.
 */
export function piStats(attemptsForPI: Attempt[]): PIStats {
  if (attemptsForPI.length === 0) return { ...EMPTY_STATS };
  // Newest first so rank 0 (the most recent attempt) gets the heaviest λ.
  const sorted = [...attemptsForPI].sort((a, b) => b.ts - a.ts);
  let sumW = 0;
  let sumWC = 0;
  for (let rank = 0; rank < sorted.length; rank++) {
    const a = sorted[rank];
    const w = DIFFICULTY_WEIGHT[a.difficulty] * Math.pow(LAMBDA, rank);
    sumW += w;
    if (a.correct) sumWC += w;
  }
  return {
    mastery: (PRIOR_ALPHA + sumWC) / (PRIOR_ALPHA + PRIOR_BETA + sumW),
    coverage: Math.min(1, sumW / FULL_COVERAGE_EFFN),
    effectiveN: sumW,
    attempts: sorted.length,
    provisional: sumW < PROVISIONAL_EFFN,
    lastTs: sorted[0].ts,
  };
}

// --------------------------------------------------------------- area

/**
 * The effective PI universe for a cluster × area at a level scope: the inventory
 * universe plus any PIs actually attempted here that the inventory doesn't list
 * (bank re-authored after the attempt — never drop real history, §12 drift).
 */
function effectiveUniverse(
  cluster: string,
  area: string,
  level: LevelScope,
  byPI: Map<string, Attempt[]>,
): string[] {
  const universe = new Set(piUniverse(cluster, area, level));
  // Add seen-but-uncatalogued PIs for this cluster×area from the attempt index.
  const prefix = `${cluster}${KEY_SEP}${area}${KEY_SEP}`;
  for (const k of byPI.keys()) {
    if (k.startsWith(prefix)) universe.add(k.slice(prefix.length));
  }
  return [...universe];
}

/**
 * Area mastery = coverage-weighted mean over the WHOLE PI universe, so unseen PIs
 * (coverage 0) drag it down — coverage, not just accuracy, drives it (parent §3).
 * `attempts` must already be filtered to the cluster + level scope.
 */
export function areaMastery(
  cluster: string,
  area: string,
  level: LevelScope,
  byPI: Map<string, Attempt[]>,
): AreaMastery {
  const universe = effectiveUniverse(cluster, area, level, byPI);
  const piCount = universe.length;
  if (piCount === 0) {
    return { cluster, area, mastery: 0, coverage: 0, piCount: 0, seenPICount: 0, provisional: true };
  }
  let masteryNum = 0;
  let coverageNum = 0;
  let seenPICount = 0;
  let totalEffN = 0;
  for (const pi of universe) {
    const stats = piStats(byPI.get(piKey(cluster, area, pi)) ?? []);
    masteryNum += stats.coverage * stats.mastery;
    coverageNum += stats.coverage;
    totalEffN += stats.effectiveN;
    if (stats.attempts > 0) seenPICount++;
  }
  return {
    cluster,
    area,
    mastery: masteryNum / piCount,
    coverage: coverageNum / piCount,
    piCount,
    seenPICount,
    provisional: seenPICount === 0 || totalEffN < PROVISIONAL_EFFN,
  };
}

/**
 * Per-PI mastery for one area's whole universe (inventory ∪ drift), sorted
 * weakest-first then alphabetically — the PI drill panel's data. `byPI` is the
 * pre-grouped, cluster+level-filtered attempt index.
 */
export function areaPIStats(
  cluster: string,
  area: string,
  level: LevelScope,
  byPI: Map<string, Attempt[]>,
): PIMastery[] {
  return effectiveUniverse(cluster, area, level, byPI)
    .map((pi) => ({
      cluster,
      area,
      pi,
      ...piStats(byPI.get(piKey(cluster, area, pi)) ?? []),
    }))
    .sort((a, b) => a.mastery - b.mastery || a.pi.localeCompare(b.pi));
}

/** Areas to render for a cluster at a level scope: inventory areas ∪ any seen
 *  (drift) areas from the attempt index, sorted. */
export function areasForClusterWithDrift(
  cluster: string,
  level: LevelScope,
  byPI: Map<string, Attempt[]>,
): string[] {
  const areas = new Set(areasForCluster(cluster, level));
  const prefix = `${cluster}${KEY_SEP}`;
  for (const k of byPI.keys()) {
    if (!k.startsWith(prefix)) continue;
    const rest = k.slice(prefix.length);
    const area = rest.slice(0, rest.indexOf(KEY_SEP));
    if (area) areas.add(area);
  }
  return [...areas].sort((a, b) => a.localeCompare(b));
}

// --------------------------------------------------------------- readiness

/** Attempts filtered to a cluster + level scope. */
function filterAttempts(attempts: Attempt[], cluster: string | "all", level: LevelScope): Attempt[] {
  return attempts.filter(
    (a) => (cluster === "all" || a.cluster === cluster) && (level === "all" || a.level === level),
  );
}

/** Readiness for one concrete cluster at a level scope. `byPI` is that cluster's
 *  pre-grouped, pre-filtered attempts. */
function clusterReadiness(
  cluster: string,
  level: LevelScope,
  byPI: Map<string, Attempt[]>,
  sampleN: number,
): Readiness {
  const blueprint = clusterBlueprint(cluster, level);
  const areas = areasForClusterWithDrift(cluster, level, byPI);
  let num = 0;
  let den = 0;
  for (const area of areas) {
    const w = blueprint[area] ?? 1; // uncatalogued area ⇒ neutral unit weight
    const am = areaMastery(cluster, area, level, byPI);
    num += w * am.mastery;
    den += w;
  }
  return { cluster, level, readiness: den > 0 ? num / den : 0, sampleN };
}

/**
 * Level-scoped attempts bucketed by cluster, each cluster's already grouped by PI
 * with its raw count. This is exactly the state `readiness` needs, factored out so
 * the trajectory replay can BUILD IT ONCE and extend it (rather than re-filtering
 * and re-grouping the whole log at every point). Insertion order within a PI's
 * list follows the order attempts are added; piStats sorts internally, so it
 * doesn't matter.
 */
type AttemptIndex = Map<string, { byPI: Map<string, Attempt[]>; n: number }>;

/** Add one attempt to the index, creating its cluster bucket on first sight. */
function indexAttempt(index: AttemptIndex, a: Attempt): void {
  let entry = index.get(a.cluster);
  if (!entry) {
    entry = { byPI: new Map(), n: 0 };
    index.set(a.cluster, entry);
  }
  const k = piKey(a.cluster, a.instructionalArea, a.performanceIndicator);
  const list = entry.byPI.get(k);
  if (list) list.push(a);
  else entry.byPI.set(k, [a]);
  entry.n++;
}

/** Readiness read off a prebuilt index (attempts already filtered to `level`). */
function readinessFromIndex(
  cluster: string | "all",
  level: LevelScope,
  index: AttemptIndex,
): Readiness {
  if (cluster !== "all") {
    const entry = index.get(cluster);
    return clusterReadiness(cluster, level, entry?.byPI ?? new Map(), entry?.n ?? 0);
  }
  // Blend per-cluster readiness weighted by each cluster's attempt count.
  let num = 0;
  let den = 0;
  let sampleN = 0;
  for (const c of bankClusters()) {
    const entry = index.get(c);
    if (!entry || entry.n === 0) continue; // no evidence ⇒ excluded from the blend
    const r = clusterReadiness(c, level, entry.byPI, entry.n);
    num += r.readiness * entry.n;
    den += entry.n;
    sampleN += entry.n;
  }
  return { cluster: "all", level, readiness: den > 0 ? num / den : 0, sampleN };
}

/**
 * The headline. Blueprint-weighted blend of area masteries for a cluster × level.
 * With `cluster: "all"`, an attempt-weighted blend of every bank cluster's
 * readiness (used for the trajectory line and any overall figure; the hero tile
 * chooses to show a "select a cluster" hint instead — locked decision).
 */
export function readiness(
  cluster: string | "all",
  level: LevelScope,
  attempts: Attempt[],
): Readiness {
  const index: AttemptIndex = new Map();
  for (const a of filterAttempts(attempts, cluster, level)) indexAttempt(index, a);
  return readinessFromIndex(cluster, level, index);
}

// --------------------------------------------------------------- trajectory

/**
 * Replay readiness at each finished session's end time. Abandoned sessions
 * (endedTs === null) are excluded (no valid x) but their attempts still count.
 * Per-session points, collapsed to per-day (max readiness that day) once the
 * span is dense, so the line stays legible (locked decision).
 *
 * The replay walks the sorted log ONCE, extending a running AttemptIndex up to
 * each session's end instead of re-filtering + re-grouping the whole prefix per
 * point (which made the replay quadratic in log size). The day-bucket collapse
 * still happens afterwards on purpose: it keeps the day's MAX readiness, which
 * isn't knowable without the per-session points.
 */
export function trajectory(
  cluster: string | "all",
  level: LevelScope,
  attempts: Attempt[],
  sessions: Session[],
  dayBucketThreshold = 14,
): TrajectoryPoint[] {
  const ends = sessions
    .filter(
      (s) =>
        s.endedTs !== null &&
        (cluster === "all" || s.cluster === cluster) &&
        (level === "all" || s.level === level),
    )
    .map((s) => s.endedTs as number)
    .sort((a, b) => a - b);
  if (ends.length === 0) return [];

  const scoped = filterAttempts(attempts, cluster, level).sort((a, b) => a.ts - b.ts);
  const index: AttemptIndex = new Map();
  let next = 0; // first attempt not yet folded into `index`
  const points: TrajectoryPoint[] = ends.map((ts) => {
    for (; next < scoped.length && scoped[next].ts <= ts; next++) {
      indexAttempt(index, scoped[next]);
    }
    return { ts, readiness: readinessFromIndex(cluster, level, index).readiness };
  });

  if (points.length <= dayBucketThreshold) return points;

  // Collapse to one point per calendar day (the day's max readiness), keeping the
  // latest ts within each day as the x so the line still reads left-to-right.
  // The day key is LOCAL (`localDateKey`), matching streaks/forecast/plan overrides
  // and the local dates this graph labels its dots with — bucketing by UTC midnight
  // splits one local evening across two dots (and merges two local days into one)
  // for every user west of Greenwich.
  const byDay = new Map<string, TrajectoryPoint>();
  for (const p of points) {
    const day = localDateKey(p.ts);
    const prev = byDay.get(day);
    if (!prev || p.readiness >= prev.readiness) byDay.set(day, { ts: p.ts, readiness: p.readiness });
  }
  return [...byDay.values()].sort((a, b) => a.ts - b.ts);
}

// --------------------------------------------------------------- weak areas

/** The concrete level to launch a Practice-this drill for a PI under a scope:
 *  the filter's level if set, else the first level whose universe carries it. */
export function launchLevelForArea(
  cluster: string,
  area: string,
  pi: string,
  level: LevelScope,
): Level {
  if (level !== "all") return level;
  for (const lv of ["District", "Association", "ICDC"] as Level[]) {
    if (piUniverse(cluster, area, lv).includes(pi)) return lv;
  }
  return "District";
}

/**
 * Rank PIs by actionability for the weak-area board: confident low-mastery PIs
 * first (you've shown you're weak), interleaved with uncovered PIs (never
 * practiced), with provisional (thin-evidence) weaknesses damped so one unlucky
 * attempt doesn't dominate. Spans the filtered cluster(s) × level scope.
 */
export function weakestPIs(
  attempts: Attempt[],
  filter: { cluster: string | "all"; level: LevelScope },
  limit = 12,
): WeakPI[] {
  const { cluster, level } = filter;
  const scoped = filterAttempts(attempts, cluster, level);
  const byPI = groupByPI(scoped);
  const clusters = cluster === "all" ? bankClusters() : [cluster];

  const rows: WeakPI[] = [];
  for (const c of clusters) {
    for (const area of areasForClusterWithDrift(c, level, byPI)) {
      const universe = effectiveUniverse(c, area, level, byPI);
      for (const pi of universe) {
        const stats = piStats(byPI.get(piKey(c, area, pi)) ?? []);
        const seen = stats.attempts > 0;
        const weakness = !seen
          ? UNCOVERED_WEAKNESS
          : (1 - stats.mastery) * (stats.provisional ? PROVISIONAL_DAMPEN : 1);
        rows.push({
          cluster: c,
          area,
          pi,
          ...stats,
          seen,
          level: launchLevelForArea(c, area, pi, level),
          weakness,
        });
      }
    }
  }
  // Weakest first; tie-break by staleness (older last attempt surfaces sooner).
  rows.sort((a, b) => b.weakness - a.weakness || a.lastTs - b.lastTs);
  return rows.slice(0, limit);
}

// ------------------------------------------------------------- accuracy

export interface AccuracySummary {
  answered: number; // graded picks
  correct: number;
  accuracy: number; // correct / answered, 0 when answered === 0
}

/** Overall accuracy over a filtered attempt set. A pickless row is excluded from the
 *  denominator (§9 honesty) rather than counted as a wrong answer — but no writer
 *  produces one, so this reports on every logged attempt in practice (#107). */
export function accuracySummary(attempts: Attempt[]): AccuracySummary {
  let answered = 0;
  let correct = 0;
  for (const a of attempts) {
    if (a.chosen === null) continue;
    answered++;
    if (a.correct) correct++;
  }
  return { answered, correct, accuracy: answered > 0 ? correct / answered : 0 };
}
