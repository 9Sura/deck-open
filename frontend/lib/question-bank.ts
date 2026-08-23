// Loader + browse helpers for the committed question bank.
//
// The question bank is a set of pre-authored exams (NOT live generation — that's
// the test generator). Users browse the discrete sets and pick one to study.
//
// The manifest (counts + coverage, no question text) is imported at build time so
// the browse UI knows what exists without a network round-trip. The per-set
// question files are fetched on demand from /question-bank/... — they're copied
// into public/ by scripts/sync-question-bank.mjs.
//
// Client-safe: types + pure helpers, no React. `fetch` runs in the browser.

import type { MockQuestion } from "@/lib/mock";
import { LEVELS, type Level } from "@/lib/deca";
import manifest from "@/lib/data/bank-manifest.json";
import areaParaphrases from "@/lib/data/area-paraphrases.json";

export type Difficulty = "easy" | "medium" | "hard";
export type DifficultyCounts = Record<Difficulty, number>;

// A bank question is a MockQuestion plus the extra fields the backend attaches.
// The `extends` keeps QuestionCard (which takes MockQuestion) untouched.
export interface BankQuestion extends MockQuestion {
  id: string;
  cluster: string;
  level: Level;
  difficulty: Difficulty;
  verified: boolean;
}

// Sets carry a `set` number; pools don't. Both now carry `difficultyCounts`
// (backend plan 07 §4/§6). BankSetMeta keeps `set` optional-free for the browse
// route; BankPoolMeta drops it. BankCollMeta is the shared shape the compose
// path reads (it only needs cluster/level/file/count/difficultyCounts).
export interface BankCollMeta {
  cluster: string;
  level: Level;
  file: string;
  count: number;
  areaCounts: Record<string, number>;
  letterDistribution: Record<string, number>;
  difficultyCounts: DifficultyCounts;
}

export interface BankSetMeta extends BankCollMeta {
  set: number;
}

export type BankPoolMeta = BankCollMeta;

export interface BankManifest {
  version: number;
  sets: Record<string, BankSetMeta>;
  pools: Record<string, BankPoolMeta>;
}

const MANIFEST = manifest as BankManifest;
const ALL_SETS = Object.values(MANIFEST.sets);

/** Total committed bank questions (sets + pools), straight off the manifest. */
export const BANK_QUESTION_COUNT = [...ALL_SETS, ...Object.values(MANIFEST.pools)].reduce(
  (n, c) => n + c.count,
  0,
);

// A conservative, marketing-safe rendering of the size above: rounded DOWN to the
// nearest hundred so the claim stays true as the bank grows (backend plan 10 lands
// a slice at a time). Formatted here rather than with toLocaleString() so server
// and browser renders can't disagree on the separator and break hydration.
export const BANK_SIZE_LABEL = `${String(Math.floor(BANK_QUESTION_COUNT / 100) * 100).replace(
  /\B(?=(\d{3})+(?!\d))/g,
  ",",
)}+`;

export class BankUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BankUnavailableError";
  }
}

/** Clusters that have at least one set built (any set, any level). */
export function bankClusters(): string[] {
  return [...new Set(ALL_SETS.map((s) => s.cluster))];
}

/** Whether a cluster has any built sets — drives "coming soon" tiles. */
export function clusterHasBank(cluster: string): boolean {
  return ALL_SETS.some((s) => s.cluster === cluster);
}

/** Distinct set numbers built for a cluster, ascending (e.g. [1, 2]). */
export function setsForCluster(cluster: string): number[] {
  return [
    ...new Set(ALL_SETS.filter((s) => s.cluster === cluster).map((s) => s.set)),
  ].sort((a, b) => a - b);
}

/** Levels built for a cluster×set, in canonical order (District → ICDC). */
export function levelsForSet(cluster: string, setN: number): Level[] {
  const built = new Set(
    ALL_SETS.filter((s) => s.cluster === cluster && s.set === setN).map((s) => s.level),
  );
  return LEVELS.map((l) => l.value).filter((v) => built.has(v));
}

/** The manifest entry for one exact cluster×level×set, if it exists. */
export function setMeta(cluster: string, level: Level, setN: number): BankSetMeta | undefined {
  return ALL_SETS.find(
    (s) => s.cluster === cluster && s.level === level && s.set === setN,
  );
}

// Plain-language paraphrases of the DECA instructional areas, so card
// descriptions don't reproduce the official section names verbatim.
const AREA_PARAPHRASE: Record<string, string> = areaParaphrases;

const paraphraseArea = (area: string) => AREA_PARAPHRASE[area] ?? area.toLowerCase();

/**
 * A plain-language paraphrase of the instructional-area sections a test covers,
 * ordered by how many questions each area carries (heaviest first). Area names
 * are reworded (not reproduced verbatim). E.g.
 * "Heaviest on self-awareness and teamwork, communicating on the job & reading
 *  the numbers, plus economic principles, running daily operations and 7 more areas."
 */
export function coverageSummary(areaCounts: Record<string, number>): string {
  const areas = Object.entries(areaCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([area]) => paraphraseArea(area));
  if (areas.length === 0) return "";

  // "A, B & C" — Oxford-free ampersand join for the leading areas.
  const ampJoin = (arr: string[]) =>
    arr.length <= 1 ? arr.join("") : `${arr.slice(0, -1).join(", ")} & ${arr[arr.length - 1]}`;

  const top = areas.slice(0, 3);
  const next = areas.slice(3, 5);
  const rest = areas.length - top.length - next.length;

  const extras = [...next];
  if (rest > 0) extras.push(`${rest} more area${rest === 1 ? "" : "s"}`);

  let sentence = `Heaviest on ${ampJoin(top)}`;
  if (extras.length > 0) {
    const tail =
      extras.length === 1
        ? extras[0]
        : `${extras.slice(0, -1).join(", ")} and ${extras[extras.length - 1]}`;
    sentence += `, plus ${tail}`;
  }
  return `${sentence}.`;
}

/** Sum several per-area count maps into one coverage map. */
function sumAreaCounts(maps: Record<string, number>[]): Record<string, number> {
  const total: Record<string, number> = {};
  for (const m of maps) {
    for (const [area, n] of Object.entries(m)) {
      total[area] = (total[area] ?? 0) + n;
    }
  }
  return total;
}

/** Sum per-area question counts across several collections into one coverage map. */
function aggregateAreaCounts(sets: BankCollMeta[]): Record<string, number> {
  return sumAreaCounts(sets.map((s) => s.areaCounts));
}

/** Paraphrase of the sections covered across every set in a cluster. */
export function clusterCoverage(cluster: string): string {
  return coverageSummary(aggregateAreaCounts(ALL_SETS.filter((s) => s.cluster === cluster)));
}

/** Paraphrase of the sections covered across the levels of one set. */
export function setCoverage(cluster: string, setN: number): string {
  return coverageSummary(
    aggregateAreaCounts(ALL_SETS.filter((s) => s.cluster === cluster && s.set === setN)),
  );
}

export interface LoadedSet {
  meta: BankSetMeta;
  questions: BankQuestion[];
}

/**
 * Load one exact set's questions by cluster×level×set. Fetches
 * /question-bank/<cluster>/<file>.json. Throws BankUnavailableError if that
 * combination isn't in the bank.
 */
export async function loadSet(
  cluster: string,
  level: Level,
  setN: number,
): Promise<LoadedSet> {
  const meta = setMeta(cluster, level, setN);
  if (!meta) {
    throw new BankUnavailableError(
      `No ${cluster} · ${level} · set ${setN} exists in the bank.`,
    );
  }
  // Shares the per-file memo with the compose/drill paths (fetchQuestions), so a set
  // browsed once doesn't re-download when a drill or test later draws from it.
  const questions = await fetchQuestions(meta.file, cluster);
  return { meta, questions };
}

// ---------------------------------------------------------------------------
// Difficulty-mixed compose path (the Test Generator).
//
// Unlike the browse route above, the Test Generator never serves a set whole.
// It draws from the cluster×level *candidate pool* = both sets + the pool file
// (~300–324 questions), composing by (instructionalArea, difficulty) slot so a
// preset like "Challenge" actually delivers hard questions. Which set an item
// came from is not an axis a student can perceive (backend plan 07 §0.1).
// ---------------------------------------------------------------------------

const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard"];
const DIFFICULTY_VOCAB = new Set<string>(DIFFICULTIES);

/**
 * Coerce a raw bank tag to the three-tier vocabulary the compose path indexes on.
 *
 * `byDifficulty[q.difficulty]` (and `drawByHint`'s buckets) index a fixed
 * three-key record, so an out-of-vocabulary tier — `"Easy"`, `"expert"`, a
 * number — reaches `undefined.push()` and takes the whole compose down. Today
 * only `verify_bank.py` keeps the bank to the three tiers, which is a contract
 * held outside the file that depends on it; this is that contract restated where
 * the JSON actually becomes a `BankQuestion`. Case is folded (a plausible drift),
 * anything else falls back to "medium" like a missing tag always has.
 */
function normalizeDifficulty(raw: unknown): Difficulty {
  if (typeof raw !== "string") return "medium";
  const tier = raw.trim().toLowerCase();
  return DIFFICULTY_VOCAB.has(tier) ? (tier as Difficulty) : "medium";
}

/** Preset difficulty mixes (easy / medium / hard weights). */
export const MIX_PRESETS = {
  "exam-real": { label: "Exam-real", weights: { easy: 20, medium: 60, hard: 20 } },
  balanced: { label: "Balanced", weights: { easy: 25, medium: 50, hard: 25 } },
  challenge: { label: "Challenge", weights: { easy: 10, medium: 40, hard: 50 } },
} as const satisfies Record<
  string,
  { label: string; weights: DifficultyCounts }
>;

export type MixPreset = keyof typeof MIX_PRESETS;

/**
 * The manifest hard-shelf target from backend plan 07 §6 (12 hard × 3×
 * Regenerate headroom). A slice at or above this Regenerates a hard-heavy
 * preset with real depth; below it, Regenerate reshuffles a shallow pool.
 */
export const DEEP_HARD_SHELF = 36;

// ---- seeded RNG so Regenerate (via nonce) yields a genuinely different draw --

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function seededShuffle<T>(arr: T[], rng: () => number): T[] {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/**
 * Largest-remainder allocation of `total` across weighted keys. Guarantees the
 * parts sum to exactly `total`. Keys with weight 0 get 0.
 */
function largestRemainder(
  total: number,
  weights: Readonly<Record<string, number>>,
): Record<string, number> {
  const keys = Object.keys(weights);
  const sum = keys.reduce((s, k) => s + weights[k], 0);
  if (sum <= 0 || total <= 0) return Object.fromEntries(keys.map((k) => [k, 0]));

  const exact = keys.map((k) => ({ k, v: (total * weights[k]) / sum }));
  const alloc: Record<string, number> = {};
  let assigned = 0;
  for (const { k, v } of exact) {
    alloc[k] = Math.floor(v);
    assigned += alloc[k];
  }
  const remainder = total - assigned;
  const byFrac = [...exact].sort((a, b) => (b.v % 1) - (a.v % 1));
  for (let i = 0; i < remainder; i++) alloc[byFrac[i % byFrac.length].k]++;
  return alloc;
}

/**
 * Aggregated set (blueprint) area weights for ONE cluster×level.
 *
 * The numbered sets define the blueprint — they're the exam-shaped artifact, so a
 * slice that has them ignores its pool here (unchanged behaviour: all 15 current
 * cluster×levels carry both files). A slice with a `-pool` file but NO sets would
 * otherwise return `{}`, which walks straight through allocateAreas → zero slots →
 * an EMPTY composed test, while `sliceAvailable` (which does count pools) still
 * advertises the slice as composable. Falling back to the pool's own area counts
 * keeps those two in agreement.
 *
 * The fallback is per LEVEL, and every blueprint reader goes through this — the
 * cluster-wide scope below sums it level by level rather than filtering sets once
 * across the cluster, so a cluster that has sets at one level and only a pool at
 * another still weights the pool-only level instead of silently dropping it.
 */
function levelAreaCounts(cluster: string, level: Level): Record<string, number> {
  const sets = ALL_SETS.filter((s) => s.cluster === cluster && s.level === level);
  if (sets.length > 0) return aggregateAreaCounts(sets);
  const pool = MANIFEST.pools?.[poolKey(cluster, level)];
  return pool ? aggregateAreaCounts([pool]) : {};
}

// The manifest is a build-time import, so a cluster×scope blueprint is fixed for
// the life of the tab. Memoized (and frozen — every caller only reads it) because
// the mastery engine asks for one per readiness() call, and `trajectory` replays
// readiness once per finished session.
const blueprintCache = new Map<string, Readonly<Record<string, number>>>();

/**
 * Public blueprint area weights for a cluster at a level scope — the exam's own
 * per-area question counts, used by the mastery engine to weight readiness by how
 * heavily the real exam tests each area. `"all"` aggregates across every level.
 */
export function clusterBlueprint(
  cluster: string,
  level: Level | "all" = "all",
): Readonly<Record<string, number>> {
  const key = `${cluster}|${level}`;
  const hit = blueprintCache.get(key);
  if (hit) return hit;
  const levels = level === "all" ? LEVELS.map((l) => l.value) : [level];
  const blueprint = Object.freeze(
    sumAreaCounts(levels.map((l) => levelAreaCounts(cluster, l))),
  );
  blueprintCache.set(key, blueprint);
  return blueprint;
}

/** Distinct instructional areas the bank sets cover for a cluster (blueprint keys). */
export function clusterAreas(cluster: string): string[] {
  return Object.keys(clusterBlueprint(cluster, "all")).sort((a, b) => a.localeCompare(b));
}

/**
 * Area allocation for `count` questions, weighted by the exam blueprint.
 * Mirrors the backend's exam-vs-quiz logic: floor-1 per area when there are at
 * least as many questions as areas, otherwise the `count` heaviest areas.
 */
function allocateAreas(
  count: number,
  blueprint: Readonly<Record<string, number>>,
): Record<string, number> {
  const areas = Object.keys(blueprint);
  if (areas.length === 0) return {};
  if (count >= areas.length) {
    const base = Object.fromEntries(areas.map((a) => [a, 1]));
    const extra = largestRemainder(count - areas.length, blueprint);
    for (const a of areas) base[a] += extra[a] ?? 0;
    return base;
  }
  const top = [...areas].sort((a, b) => blueprint[b] - blueprint[a]).slice(0, count);
  return Object.fromEntries(top.map((a) => [a, 1]));
}

export interface Slot {
  area: string;
  difficulty: Difficulty;
}

/**
 * The spine of the compose path: turn (cluster, level, count, mix) into `count`
 * {area, difficulty} slots whose area marginal matches the exam blueprint and
 * whose difficulty marginal matches the preset. The joint assignment is random
 * (shuffle-and-zip), reproducible from `nonce`.
 */
export function planQuestions(
  cluster: string,
  level: Level,
  count: number,
  mix: MixPreset,
  nonce: number,
): Slot[] {
  const rng = mulberry32(nonce);
  const diffAlloc = largestRemainder(count, MIX_PRESETS[mix].weights);
  const areaAlloc = allocateAreas(count, clusterBlueprint(cluster, level));

  const areaLabels: string[] = [];
  for (const [area, n] of Object.entries(areaAlloc)) {
    for (let i = 0; i < n; i++) areaLabels.push(area);
  }
  const diffLabels: Difficulty[] = [];
  for (const d of DIFFICULTIES) {
    for (let i = 0; i < (diffAlloc[d] ?? 0); i++) diffLabels.push(d);
  }

  const shuffledAreas = seededShuffle(areaLabels, rng);
  const shuffledDiffs = seededShuffle(diffLabels, rng);
  return shuffledAreas.map((area, i) => ({
    area,
    difficulty: shuffledDiffs[i] ?? "medium",
  }));
}

// When a slot's exact (area, difficulty) bucket is empty, borrow from the
// nearest difficulty first — hard prefers medium over easy, and vice versa.
const NEAREST_DIFFICULTY: Record<Difficulty, Difficulty[]> = {
  easy: ["easy", "medium", "hard"],
  medium: ["medium", "easy", "hard"],
  hard: ["hard", "medium", "easy"],
};

const setKey = (cluster: string, level: Level, setN: number) =>
  `${cluster}-${level.toLowerCase()}-${setN}`;
const poolKey = (cluster: string, level: Level) =>
  `${cluster}-${level.toLowerCase()}-pool`;

// The bank is static committed JSON, so each file is fetched + parsed AT MOST ONCE
// per tab and memoized (the promise, so concurrent callers share one in-flight
// request). This is what keeps "composing your set…" from re-downloading and
// re-parsing the whole cluster bank on every launch, availability check, or compose.
// A failed fetch is evicted so a later retry can succeed.
const questionFileCache = new Map<string, Promise<BankQuestion[]>>();

async function fetchQuestions(file: string, cluster: string): Promise<BankQuestion[]> {
  const key = `${cluster}/${file}`;
  const cached = questionFileCache.get(key);
  if (cached) return cached;
  const load = (async () => {
    const res = await fetch(`/question-bank/${cluster}/${file}`);
    if (!res.ok) throw new Error(`Failed to load ${file} (HTTP ${res.status}).`);
    const raw = (await res.json()) as BankQuestion[];
    // Migration safety: a missing OR out-of-vocabulary difficulty tag reads as
    // "medium". This is the one seam where bank JSON becomes a BankQuestion, so
    // every downstream `byDifficulty[q.difficulty]` is safe by construction.
    return raw.map((q) => ({ ...q, difficulty: normalizeDifficulty(q.difficulty) }));
  })();
  questionFileCache.set(key, load);
  load.catch(() => questionFileCache.delete(key));
  return load;
}

/**
 * Which slice of the bank to draw from:
 *  - `all`  — the numbered exam sets + the pool file (the default; ~4,588 total)
 *  - `pool` — ONLY the `-pool` file: the extra questions that were never placed
 *             into an exam set (~1,588). Lets a user drill just those additions.
 *  - `sets` — ONLY the numbered exam sets (~3,000; what /question-bank browses).
 */
export type CandidateSource = "all" | "pool" | "sets";

/**
 * The candidate pool for a cluster×level. By default both sets + the pool file,
 * concatted and de-duped by `id` — this, never a single set, is what the Test
 * Generator samples from. `source` narrows it to just the sets or just the pool.
 * Throws BankUnavailableError if the requested source has no files.
 */
export async function loadCandidates(
  cluster: string,
  level: Level,
  source: CandidateSource = "all",
): Promise<BankQuestion[]> {
  const files: string[] = [];
  if (source !== "pool") {
    for (const setN of setsForCluster(cluster)) {
      if (setMeta(cluster, level, setN)) files.push(setKey(cluster, level, setN) + ".json");
    }
  }
  if (source !== "sets") {
    const pool = MANIFEST.pools?.[poolKey(cluster, level)];
    if (pool) files.push(pool.file);
  }

  if (files.length === 0) {
    const which = source === "pool" ? "pool " : source === "sets" ? "exam-set " : "";
    throw new BankUnavailableError(
      `No ${cluster} · ${level} ${which}questions exist in the bank.`,
    );
  }

  const batches = await Promise.all(files.map((f) => fetchQuestions(f, cluster)));
  const byId = new Map<string, BankQuestion>();
  for (const q of batches.flat()) if (!byId.has(q.id)) byId.set(q.id, q);
  return [...byId.values()];
}

/** Question count in the `-pool` file for a cluster×level (0 if none). */
export function poolDepth(cluster: string, level: Level): number {
  return MANIFEST.pools?.[poolKey(cluster, level)]?.count ?? 0;
}

/**
 * Hard-shelf depth for a cluster×level, from the manifest — counting only the
 * halves `source` will actually draw from. A Pool-only draw never sees the exam
 * sets' hard questions, so summing both would overstate the shelf the user is
 * about to Regenerate against (entrepreneurship·ICDC reads 45 combined but 21
 * pool-only, straddling DEEP_HARD_SHELF). `source` must match what is passed to
 * `loadCandidates` / `composeTest`.
 */
export function hardShelfDepth(
  cluster: string,
  level: Level,
  source: CandidateSource = "all",
): number {
  const fromSets =
    source === "pool"
      ? 0
      : ALL_SETS.filter((s) => s.cluster === cluster && s.level === level).reduce(
          (n, s) => n + (s.difficultyCounts?.hard ?? 0),
          0,
        );
  const p = MANIFEST.pools?.[poolKey(cluster, level)];
  const fromPool = source === "sets" ? 0 : (p?.difficultyCounts?.hard ?? 0);
  return fromSets + fromPool;
}

/** Whether a cluster×level can be composed (has at least one candidate file). */
export function sliceAvailable(cluster: string, level: Level): boolean {
  const hasSet = setsForCluster(cluster).some((n) => setMeta(cluster, level, n));
  return hasSet || Boolean(MANIFEST.pools?.[poolKey(cluster, level)]);
}

export interface ComposedTest {
  questions: BankQuestion[];
  mix: MixPreset;
  /** Difficulty split the preset asked for. */
  requested: DifficultyCounts;
  /** Difficulty split actually delivered (after borrowing). */
  delivered: DifficultyCounts;
  /** Slots filled from a non-target difficulty because the bucket ran dry. */
  borrowed: number;
  /**
   * Slots that couldn't be filled at all — `count` minus what was delivered.
   * Every difficulty (and so every borrow target) was exhausted, or the slice
   * has no blueprint to allocate against. Non-zero means the caller asked for
   * `count` questions and is holding fewer: a short test must not be presented
   * as a full one.
   */
  short: number;
  /** True when the slice's hard shelf is below the Regenerate-headroom target. */
  shallowHardShelf: boolean;
}

const emptyCounts = (): DifficultyCounts => ({ easy: 0, medium: 0, hard: 0 });

/**
 * Compose a difficulty-mixed practice test from the combined candidate pool.
 *
 * Difficulty is the primary, student-perceptible axis; instructional area is a
 * soft preference. So we fill **difficulty-first**: each difficulty bucket draws
 * its planned count, preferring areas still under the blueprint target, then
 * borrowing from the nearest difficulty only if that bucket runs dry. This makes
 * a preset like "Challenge" deliver its full hard count whenever the slice's hard
 * shelf is deep enough — and where it isn't (short clusters), the shortfall shows
 * up honestly as a shallow Regenerate (the same hard items reshuffled) plus a
 * `shallowHardShelf` flag, never as a mostly-medium draw dressed up as Challenge.
 *
 * When even the borrow targets run dry the slot is left unfilled rather than
 * duplicated, so the result can be shorter than `count` — reported as `short`,
 * never silently.
 *
 * `nonce` reseeds the shuffle so Regenerate yields a different draw.
 */
export async function composeTest(
  cluster: string,
  level: Level,
  count: number,
  mix: MixPreset,
  nonce: number,
  source: CandidateSource = "all",
): Promise<ComposedTest> {
  const candidates = await loadCandidates(cluster, level, source);
  const rng = mulberry32(nonce ^ 0x9e3779b9);
  const pool = seededShuffle(candidates, rng);

  // Marginals from the plan: how many of each difficulty, and the soft
  // per-area target. (planQuestions is the documented spine; we consume its
  // marginals rather than its joint slot assignment, which would pin scarce
  // hard items to areas that have none.)
  const slots = planQuestions(cluster, level, count, mix, nonce);
  const requested = emptyCounts();
  const areaTarget: Record<string, number> = {};
  for (const s of slots) {
    requested[s.difficulty]++;
    areaTarget[s.area] = (areaTarget[s.area] ?? 0) + 1;
  }

  const byDifficulty: Record<Difficulty, BankQuestion[]> = {
    easy: [],
    medium: [],
    hard: [],
  };
  for (const q of pool) byDifficulty[q.difficulty].push(q);

  const used = new Set<string>();
  const areaGot: Record<string, number> = {};

  // Draw an unused question from a list, preferring one whose area is still
  // under its blueprint target; otherwise the first unused (area saturated).
  const drawFrom = (list: BankQuestion[]): BankQuestion | undefined => {
    let fallback: BankQuestion | undefined;
    for (const q of list) {
      if (used.has(q.id)) continue;
      if (!fallback) fallback = q;
      if ((areaGot[q.instructionalArea] ?? 0) < (areaTarget[q.instructionalArea] ?? 0)) {
        return q;
      }
    }
    return fallback;
  };
  const take = (q: BankQuestion) => {
    used.add(q.id);
    areaGot[q.instructionalArea] = (areaGot[q.instructionalArea] ?? 0) + 1;
  };

  const questions: BankQuestion[] = [];
  let borrowed = 0;

  // Fill scarcest difficulty first so a short hard bucket claims its questions
  // before medium/easy borrowing could touch them.
  const fillOrder: Difficulty[] = ["hard", "medium", "easy"];
  for (const d of fillOrder) {
    for (let i = 0; i < (requested[d] ?? 0); i++) {
      let q = drawFrom(byDifficulty[d]);
      let didBorrow = false;
      if (!q) {
        for (const nd of NEAREST_DIFFICULTY[d]) {
          if (nd === d) continue;
          q = drawFrom(byDifficulty[nd]);
          if (q) {
            didBorrow = true;
            break;
          }
        }
      }
      if (q) {
        take(q);
        questions.push(q);
        if (didBorrow) borrowed++;
      }
    }
  }

  const delivered = emptyCounts();
  for (const q of questions) delivered[q.difficulty]++;

  return {
    questions: seededShuffle(questions, rng),
    mix,
    requested,
    delivered,
    borrowed,
    short: Math.max(0, count - questions.length),
    shallowHardShelf: hardShelfDepth(cluster, level, source) < DEEP_HARD_SHELF,
  };
}

// ---------------------------------------------------------------------------
// PI-filtered drill draw — the "Practice this" deep-link from the dashboard
// (plan 08 phase 2 §8). Pull the cluster×level candidates, narrow to one PI,
// shuffle, and slice N. Falls back to the whole area when the exact PI has no
// fetchable items (the inventory lists it but this level's files don't carry it),
// so an uncovered PI is still practiceable, and — under `fill` — tops a THIN PI up
// from the same area. Both cases are reported through `kind`, because a set that is
// partly off-PI has to say so exactly as a wholly off-PI one does (issue #208).
// ---------------------------------------------------------------------------

/** How the drill set was resolved, so the UI can surface a "closest available" note.
 *  `"pi+area"` is the PARTIAL case: the exact PI supplied some of the set and the rest
 *  was topped up from the wider instructional area (the `fill` branch). */
export type PIDrawKind = "pi" | "pi+area" | "area" | "none";

/** The one statement of the area-fallback rule, shared by every host that launches a
 *  PI drill (/progress and the dashboard). A `kind === "area"` draw means the exact PI
 *  had nothing fetchable and the set came from the whole instructional area instead —
 *  say so, or the questions arrive under a PI name they don't belong to (issue #197). */
export const AREA_FALLBACK_NOTICE = "Closest available — practicing the whole area.";

/** The same rule for a PARTIAL top-up (issue #208): the PI was thinner than the target,
 *  so some of the set comes from elsewhere in the area. Distinct wording because the set
 *  IS mostly on-PI — the note discloses the remainder, it doesn't retitle the drill. */
export const PARTIAL_AREA_FILL_NOTICE =
  "Topped up from the wider area — some questions are from other indicators.";

/** The one place a draw kind becomes a sentence. Both hosts call this instead of
 *  comparing `kind` themselves: an equality test (`kind === "area"`) still COMPILES
 *  when a member is added to `PIDrawKind`, so a host that keeps its own predicate goes
 *  silently stale on the next case rather than failing the build (issues #33, #197). */
export function noticeForDraw(kind: PIDrawKind): string | undefined {
  if (kind === "area") return AREA_FALLBACK_NOTICE;
  if (kind === "pi+area") return PARTIAL_AREA_FILL_NOTICE;
  return undefined;
}

export interface PIDraw {
  questions: BankQuestion[];
  kind: PIDrawKind;
}

/** Fisher–Yates over Math.random — a fresh draw per launch (browser-only path). */
function shuffle<T>(arr: T[]): T[] {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/**
 * Load up to `count` questions for one performance indicator at a cluster×level.
 * Prefers exact-PI matches; if none exist, falls back to the PI's `area` (when
 * given) so uncovered PIs are still drillable. Returns `{ questions, kind }`
 * where `kind` records what actually matched. May throw BankUnavailableError if
 * the cluster×level has no candidate files at all.
 */
/**
 * Load an exact, ordered set of questions by id from a cluster×level's candidates
 * (the study-plan "resume the same quiz" path). Ids that no longer exist in the
 * bank are dropped; order follows `ids`. Empty result ⇒ caller regenerates.
 */
export async function loadQuestionsByIds(
  cluster: string,
  level: Level,
  ids: string[],
): Promise<BankQuestion[]> {
  if (ids.length === 0) return [];
  const candidates = await loadCandidates(cluster, level, "all");
  const byId = new Map(candidates.map((q) => [q.id, q]));
  return ids
    .map((id) => byId.get(id))
    .filter((q): q is BankQuestion => q !== undefined);
}

/** A drill's difficulty tilt (Phase B #2) — how a hint biases the per-PI draw.
 *  A short bucket is topped up from the rest of the pool, so a thin PI still fills. */
type DrillHint = "build" | "mixed" | "challenge";
const HINT_DRAW: Record<DrillHint, Record<Difficulty, number>> = {
  build: { easy: 0.45, medium: 0.45, hard: 0.1 },
  mixed: { easy: 0.3, medium: 0.45, hard: 0.25 },
  challenge: { easy: 0.1, medium: 0.4, hard: 0.5 },
};

/** Largest-remainder integer split of `n` across a difficulty weighting. */
function allocateDifficulty(n: number, mix: Record<Difficulty, number>): Record<Difficulty, number> {
  const diffs: Difficulty[] = ["easy", "medium", "hard"];
  const raw = diffs.map((d) => n * mix[d]);
  const counts = raw.map((v) => Math.floor(v));
  let used = counts.reduce((s, v) => s + v, 0);
  const order = diffs.map((_, i) => ({ i, rem: raw[i] - counts[i] })).sort((a, b) => b.rem - a.rem);
  let k = 0;
  while (used < n) {
    counts[order[k % diffs.length].i]++;
    used++;
    k++;
  }
  return { easy: counts[0], medium: counts[1], hard: counts[2] };
}

/** Draw `count` questions from a pool with a difficulty tilt, topping up any short
 *  bucket from the remaining pool so the set always fills to what's available. */
function drawByHint(pool: BankQuestion[], count: number, hint: DrillHint): BankQuestion[] {
  const buckets: Record<Difficulty, BankQuestion[]> = { easy: [], medium: [], hard: [] };
  for (const q of shuffle(pool)) buckets[q.difficulty].push(q);
  const want = allocateDifficulty(count, HINT_DRAW[hint]);
  const picked: BankQuestion[] = [];
  for (const d of ["easy", "medium", "hard"] as Difficulty[]) {
    picked.push(...buckets[d].splice(0, Math.min(want[d], buckets[d].length)));
  }
  if (picked.length < count) {
    const leftover = shuffle([...buckets.easy, ...buckets.medium, ...buckets.hard]);
    picked.push(...leftover.slice(0, count - picked.length));
  }
  return shuffle(picked).slice(0, count);
}

export async function loadPIQuestions(
  cluster: string,
  level: Level,
  pi: string,
  count = 10,
  area?: string,
  /** Optional difficulty tilt for the draw (Phase B adaptive drills). */
  hint?: DrillHint,
  /** Question ids to exclude from the draw — the "remaining bank" for a learning
   *  drill, so it serves only questions the student hasn't answered yet (fewer than
   *  `count` if that's all that's left). */
  excludeIds?: Set<string>,
  /** When the exact-PI pool is thinner than `count`, top the draw up from the rest
   *  of the same instructional area (still excluding answered questions), so a
   *  learning drill hits its target of `count` whenever the area can supply it and
   *  only comes up short when the whole remaining bank is exhausted. */
  fill = false,
): Promise<PIDraw> {
  const candidates = await loadCandidates(cluster, level, "all");
  const available =
    excludeIds && excludeIds.size > 0
      ? candidates.filter((q) => !excludeIds.has(q.id))
      : candidates;
  const draw = (pool: BankQuestion[], n = count) =>
    hint ? drawByHint(pool, n, hint) : shuffle(pool).slice(0, n);

  const exact = available.filter((q) => q.performanceIndicator === pi);
  if (exact.length > 0) {
    let questions = draw(exact);
    let topped = false;
    // Top up a short PI draw from the broader area (related, still-unseen material).
    if (fill && questions.length < count && area) {
      const have = new Set(questions.map((q) => q.id));
      const areaExtra = available.filter(
        (q) => q.instructionalArea === area && q.performanceIndicator !== pi && !have.has(q.id),
      );
      if (areaExtra.length > 0) {
        const extra = draw(areaExtra, count - questions.length);
        // Only a draw that actually YIELDED off-PI questions is partial — an empty
        // top-up leaves a set that is wholly on-PI and has nothing to disclose.
        topped = extra.length > 0;
        questions = [...questions, ...extra];
      }
    }
    return { questions, kind: topped ? "pi+area" : "pi" };
  }

  if (area) {
    const inArea = available.filter((q) => q.instructionalArea === area);
    if (inArea.length > 0) {
      return { questions: draw(inArea), kind: "area" };
    }
  }

  return { questions: [], kind: "none" };
}
