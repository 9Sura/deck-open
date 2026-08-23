// Loader for the committed roleplay archive (frontend plan 11 §6, F4/F9).
//
// Unlike the question bank and vocab, `frontend/public/roleplays/` IS the
// archive's canonical home — there is no sync script and nothing chains into
// `prebuild` (F4). And unlike `bank-manifest.json`, NOTHING here is imported at
// build time (F9): `index.json` grows every batch and the month shards grow
// forever, so every file is fetched on demand and the JS bundle never widens.
//
// Client-safe: no React, no build-time JSON import. `fetch` runs in the browser.
//
// Tolerance over strictness (plan 11 §8.1): the contract was authored from 7
// samples of one generator arm, so every reader below normalizes rather than
// asserts. A field the generator drops degrades to an empty list, never to a
// thrown render.

import type { Roleplay, RoleplayDay, RoleplayIndex, RoleplayMeta, RoleplayPI } from "./types";

const ROOT = "/roleplays";

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const MONTH_RE = /^\d{4}-\d{2}$/;
const CODE_RE = /^[A-Za-z]{2,6}$/;

/**
 * The archive couldn't be read: a 404 (the common one — `public/roleplays/` is
 * absent until the first real batch lands), an unreachable network, or a file
 * that isn't JSON. Mirrors `BankUnavailableError`; every caller is expected to
 * degrade to an honest empty state rather than blank the page.
 */
export class ArchiveUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ArchiveUnavailableError";
  }
}

// The archive is static committed JSON, so each file is fetched + parsed AT MOST
// ONCE per tab and memoized — the PROMISE, so concurrent callers (the board and
// the archive browse both want the month shards) share one in-flight request. A
// failed fetch is evicted so a later retry can succeed. Mirrors
// `questionFileCache` in lib/question-bank.ts.
const fileCache = new Map<string, Promise<unknown>>();

async function fetchJson<T>(path: string, what: string): Promise<T> {
  const cached = fileCache.get(path) as Promise<T> | undefined;
  if (cached) return cached;

  const load = (async () => {
    let res: Response;
    try {
      res = await fetch(path);
    } catch {
      throw new ArchiveUnavailableError(`Couldn't reach the archive to load ${what}.`);
    }
    if (!res.ok) {
      throw new ArchiveUnavailableError(`Couldn't load ${what} (HTTP ${res.status}).`);
    }
    try {
      return (await res.json()) as T;
    } catch {
      throw new ArchiveUnavailableError(`${what} is on disk but couldn't be read.`);
    }
  })();

  fileCache.set(path, load);
  load.catch(() => fileCache.delete(path));
  return load as Promise<T>;
}

// ---------------------------------------------------------------------------
// Paths. Every segment is validated before it reaches a URL — `?day=` and
// `?event=` are user-typeable (F7), so an unvalidated date would let a hand-typed
// `../..` walk out of /roleplays/.
// ---------------------------------------------------------------------------

function datePath(date: string): string {
  if (!DATE_RE.test(date)) {
    throw new ArchiveUnavailableError(`"${date}" isn't a date the archive can hold.`);
  }
  return date.replace(/-/g, "/");
}

// ---------------------------------------------------------------------------
// Normalizers — the tolerance layer.
// ---------------------------------------------------------------------------

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

const str = (v: unknown, fallback = ""): string => (typeof v === "string" ? v : fallback);

const strList = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((s): s is string => typeof s === "string") : [];

/**
 * Performance indicators, in BOTH shapes. Backend plan 05 D5 made each one a
 * `{ area, pi, role }` object; the 7 committed day fixtures still carry bare
 * strings until they are regenerated (that plan's §7 step 7). Feeding objects to
 * `strList` would have dropped every PI silently — no error, no console warning —
 * so this reads both and drops neither.
 *
 * A legacy string becomes `{ pi }` with NO area: absent, never guessed. The area
 * a case declared cannot be recovered from the indicator's text (25.8% of DECA's
 * PIs are filed under more than one area), which is the whole reason the backend
 * records it at authoring time.
 */
const piList = (v: unknown): RoleplayPI[] => {
  if (!Array.isArray(v)) return [];
  const out: RoleplayPI[] = [];
  for (const entry of v) {
    if (typeof entry === "string") {
      out.push({ pi: entry });
      continue;
    }
    if (!isRecord(entry) || typeof entry.pi !== "string") continue;
    const area = str(entry.area);
    const role = entry.role === "core" || entry.role === "adjacent" ? entry.role : undefined;
    out.push({ pi: entry.pi, ...(area ? { area } : {}), ...(role ? { role } : {}) });
  }
  return out;
};

const num = (v: unknown, fallback = 0): number =>
  typeof v === "number" && Number.isFinite(v) ? v : fallback;

function normalizeIndex(raw: unknown): RoleplayIndex {
  const r = isRecord(raw) ? raw : {};
  const totals = isRecord(r.totals) ? r.totals : {};
  return {
    version: num(r.version, 1),
    latest: str(r.latest),
    months: strList(r.months).filter((m) => MONTH_RE.test(m)),
    totals: { days: num(totals.days), roleplays: num(totals.roleplays) },
  };
}

function normalizeDay(raw: unknown): RoleplayDay {
  const r = isRecord(raw) ? raw : {};
  return {
    date: str(r.date),
    events: strList(r.events),
    missing: strList(r.missing),
  };
}

function normalizeMeta(raw: unknown): RoleplayMeta {
  const r = isRecord(raw) ? raw : {};
  const claimed = isRecord(r.claimed) ? r.claimed : {};
  const corroborated = isRecord(r.corroborated) ? r.corroborated : {};
  const gate = isRecord(r.gate) ? r.gate : {};
  const generator = isRecord(r.generator) ? r.generator : {};
  const claimedExhibit = str(claimed.exhibit);
  return {
    claimed: {
      stakeholders: strList(claimed.stakeholders),
      constraints: strList(claimed.constraints),
      conflicts: strList(claimed.conflicts),
      ...(claimedExhibit ? { exhibit: claimedExhibit } : {}),
    },
    corroborated: {
      stakeholders: strList(corroborated.stakeholders),
      constraints: strList(corroborated.constraints),
      exhibit: corroborated.exhibit === true,
    },
    // A gate verdict that didn't survive the round trip is recorded as FAILED,
    // never as passed: `passed` is the weaker claim ("nothing countable is
    // wrong"), and defaulting a missing one to true would invent it.
    gate: {
      passed: gate.passed === true,
      failedKnobs: strList(gate.failedKnobs),
      issues: strList(gate.issues),
      // Threaded rather than dropped. `normalizeMeta` rebuilds field by field, so
      // a key it does not name vanishes silently — and these two are the ones
      // that say what `passed` actually covers (backend plan 04 §5). Omitted
      // when empty so a pre-gate-version-4 roleplay does not grow an empty list
      // that reads as "nothing ran" rather than "this predates the record".
      ...(strList(gate.checks).length ? { checks: strList(gate.checks) } : {}),
      ...(strList(gate.unverified).length
        ? { unverified: strList(gate.unverified) }
        : {}),
    },
    situationWords: num(r.situationWords),
    generator: {
      model: str(generator.model, "unknown"),
      passes: generator.passes === 1 ? 1 : 2,
      ...(str(generator.axesHash) ? { axesHash: str(generator.axesHash) } : {}),
    },
    defects: strList(r.defects),
  };
}

function normalizeRoleplay(raw: unknown, date: string, code: string): Roleplay {
  const r = isRecord(raw) ? raw : {};
  const rawFormat = str(r.format);
  const format =
    rawFormat === "series" || rawFormat === "principles" || rawFormat === "team"
      ? rawFormat
      : "series";
  const rawLevel = str(r.level);
  const level =
    rawLevel === "District" || rawLevel === "Association" || rawLevel === "ICDC"
      ? rawLevel
      : "ICDC";

  // Optional by contract and ABSENT, not null/"" — PFL genuinely has no career
  // cluster, and 3 of the 7 committed fixtures have no exhibit. Spread them in
  // only when real so a renderer's `?.` check means what it says.
  const careerCluster = str(r.careerCluster);
  const rawExhibit = isRecord(r.exhibit) ? r.exhibit : null;
  const exhibitRows = rawExhibit ? strList(rawExhibit.rows) : [];
  const exhibit =
    rawExhibit && exhibitRows.length > 0
      ? { title: str(rawExhibit.title), rows: exhibitRows }
      : null;

  return {
    schemaVersion: num(r.schemaVersion, 1),
    id: str(r.id, `${date}-${code}`),
    date: str(r.date, date),
    code: str(r.code, code),
    format,
    level,
    // Read from the file, not hardcoded: two tiers now coexist on disk and a
    // constant here would relabel every retired `icdc-plus` entry as if it had
    // been authored against the live bar. Unknown values fall back to the
    // retired tier, which is the safe direction — it under-claims.
    tier: str(r.tier) === "icdc" ? "icdc" : "icdc-plus",
    ...(careerCluster ? { careerCluster } : {}),
    instructionalArea: str(r.instructionalArea),
    performanceIndicators: piList(r.performanceIndicators),
    twentyFirstCenturySkills: strList(r.twentyFirstCenturySkills),
    participantInstructions: str(r.participantInstructions),
    situation: str(r.situation),
    ...(exhibit ? { exhibit } : {}),
    judgeCharacterization: str(r.judgeCharacterization),
    judgeQuestions: strList(r.judgeQuestions),
    meta: normalizeMeta(r.meta),
  };
}

// ---------------------------------------------------------------------------
// Loaders
// ---------------------------------------------------------------------------

/** The archive index. Throws `ArchiveUnavailableError` before the first batch. */
export async function loadIndex(): Promise<RoleplayIndex> {
  return normalizeIndex(await fetchJson<unknown>(`${ROOT}/index.json`, "the archive index"));
}

/** One month's days, e.g. `"2026-07"`. Ascending by date. */
export async function loadMonth(month: string): Promise<RoleplayDay[]> {
  if (!MONTH_RE.test(month)) {
    throw new ArchiveUnavailableError(`"${month}" isn't a month the archive can hold.`);
  }
  const raw = await fetchJson<unknown>(`${ROOT}/months/${month}.json`, `the ${month} archive`);
  const days = (Array.isArray(raw) ? raw : []).map(normalizeDay).filter((d) => DATE_RE.test(d.date));
  return days.sort((a, b) => a.date.localeCompare(b.date));
}

/**
 * Every day on disk, ascending — the month shards concatenated.
 *
 * The day board needs the whole list, not just one day: prev/next must step over
 * AVAILABLE days rather than calendar days (the archive is sparse whenever a
 * batch is missed), and "Day N of the challenge" is a position in this list. A
 * month whose shard is listed but missing is SKIPPED rather than fatal.
 *
 * Cost note: this is one fetch per month in the archive, so it grows ~12/year.
 * The shards are small and highly compressible, and each is memoized per tab, so
 * this is fine for the launch years — it is the client half of the archive-scaling
 * question plan 11 §8.5 already owns (the answer there is a route handler or
 * object storage around year 2–3, not a different shape here).
 */
export async function loadAllDays(): Promise<RoleplayDay[]> {
  const index = await loadIndex();
  const shards = await Promise.all(index.months.map((m) => loadMonth(m).catch(() => [])));
  const byDate = new Map<string, RoleplayDay>();
  for (const day of shards.flat()) if (!byDate.has(day.date)) byDate.set(day.date, day);
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
}

/**
 * One day's manifest straight from `<date>/day.json` — the deep-link path that
 * doesn't need the month shards. The board reads `loadAllDays()` instead, because
 * it needs the neighbours anyway.
 */
export async function loadDay(date: string): Promise<RoleplayDay> {
  const raw = await fetchJson<unknown>(
    `${ROOT}/${datePath(date)}/day.json`,
    `the day list for ${date}`,
  );
  const day = normalizeDay(raw);
  return { ...day, date: DATE_RE.test(day.date) ? day.date : date };
}

/**
 * One roleplay. `code` joins to `EVENTS` in lib/data/events.ts; the file is
 * lower-cased on disk (`2026/07/28/hrm.json`).
 */
export async function loadRoleplay(date: string, code: string): Promise<Roleplay> {
  if (!CODE_RE.test(code)) {
    throw new ArchiveUnavailableError(`"${code}" isn't an event code.`);
  }
  const upper = code.toUpperCase();
  const raw = await fetchJson<unknown>(
    `${ROOT}/${datePath(date)}/${code.toLowerCase()}.json`,
    `${upper} for ${date}`,
  );
  return normalizeRoleplay(raw, date, upper);
}
