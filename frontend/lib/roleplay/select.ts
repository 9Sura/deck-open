// Which day of the archive is on screen (frontend plan 11 §4a, F1 ← backend D8).
//
// STRICTLY PURE. There is no `Date.now()` and no argless `new Date()` in this
// file, and there must never be one. Pinning the boundary to Eastern removed the
// TIMEZONE half of the hydration hazard, but not the CLOCK half: the buffer is
// filled 7–14 days ahead, so future-dated days are physically present in
// `public/roleplays/`, and `/roleplay` is statically prerendered — a day derived
// at build time is a day frozen at build time. So every function here still takes
// `now` (epoch ms) from a caller that stamped it in a mount effect, and the page
// still renders a skeleton until it has one. Same discipline as
// `lib/progress/plan.ts`.
//
// `index.latest` is the newest date ON DISK and is routinely in the future. It is
// never the day to show.
//
// THE DAY BOUNDARY IS EASTERN MIDNIGHT, NOT THE VIEWER'S — one global day, so
// "today's roleplays" is the same set of files for everyone (see eastern.ts for
// why, and for why the study plan's day key stays viewer-local). Every comparison
// here goes through `todayKey`. Do not "simplify" that to
// `new Date(ms).toISOString().slice(0, 10)`: that is UTC, and 9pm on Jul 31 in
// New York is already Aug 1 in UTC, so it would unlock the next day's drop three
// hours early and do it every evening. `formatDay` builds its weekday with
// `new Date(y, m - 1, d)` rather than `new Date("2026-07-28")` for the same class
// of reason.

import { easternDateKey } from "./eastern";
import type { RoleplayDay } from "./types";

/**
 * The challenge's `YYYY-MM-DD` "today" for an epoch ms — the cutoff every
 * selector compares against. Eastern, therefore identical for every viewer at the
 * same instant.
 */
export function todayKey(now: number): string {
  return easternDateKey(now);
}

/** `"2026-07-28"` → `"2026-07"`, the month shard it lives in. */
export function monthOf(date: string): string {
  return date.slice(0, 7);
}

/**
 * Has this day dropped yet? Eastern, so the answer is the same for every viewer.
 * ISO date strings compare lexicographically, so this is a plain string compare —
 * no Date parsing, and no off-by-one.
 */
export function isPublished(date: string, now: number): boolean {
  return date <= todayKey(now);
}

/** The days that have dropped, ascending. Future-dated days on disk are dropped. */
export function publishedDays(days: RoleplayDay[], now: number): RoleplayDay[] {
  const cutoff = todayKey(now);
  return days.filter((d) => d.date <= cutoff);
}

/**
 * The day to show by default: `max(date) where date <= todayEastern`.
 *
 * NOT `index.latest`, and NOT today's calendar date — the archive is sparse
 * (a missed batch leaves a gap), so the newest published day may be several days
 * old. `null` when nothing has dropped yet.
 */
export function latestAvailableDay(days: RoleplayDay[], now: number): RoleplayDay | null {
  const published = publishedDays(days, now);
  return published.length > 0 ? published[published.length - 1] : null;
}

/**
 * "Day N of the challenge" — the day's 1-based position among ALL days on disk,
 * ascending. A position, not a calendar count: day 3 is the third drop, whether
 * or not the second one was the day before. `null` when the date isn't on disk.
 */
export function dayNumber(days: RoleplayDay[], date: string): number | null {
  const sorted = [...days].sort((a, b) => a.date.localeCompare(b.date));
  const i = sorted.findIndex((d) => d.date === date);
  return i === -1 ? null : i + 1;
}

/**
 * The previous/next AVAILABLE day — never a calendar step. `null` at either end,
 * which is what disables the stepper.
 *
 * "next" cannot leave the published set, so a future-dated day sitting in
 * `public/` is unreachable until the Eastern date catches up.
 */
export function stepDay(
  days: RoleplayDay[],
  from: string,
  direction: "prev" | "next",
  now: number,
): RoleplayDay | null {
  const published = publishedDays(days, now);
  if (direction === "prev") {
    const earlier = published.filter((d) => d.date < from);
    return earlier.length > 0 ? earlier[earlier.length - 1] : null;
  }
  return published.find((d) => d.date > from) ?? null;
}

/** Why the day on screen isn't the one the URL asked for. */
export type DayFallback =
  | "none"
  /** `?day=` names a day that exists on disk but hasn't dropped yet. */
  | "not-published"
  /** `?day=` names a day the archive has never held. */
  | "not-found";

export interface DaySelection {
  day: RoleplayDay | null;
  fallback: DayFallback;
}

/**
 * Resolve `?day=` against the archive. An unpublished or unknown date falls back
 * to the latest available day and SAYS which happened, so the board can tell the
 * user rather than silently showing them something else.
 */
export function resolveDay(
  days: RoleplayDay[],
  requested: string | null,
  now: number,
): DaySelection {
  if (!requested) return { day: latestAvailableDay(days, now), fallback: "none" };
  const match = days.find((d) => d.date === requested);
  if (!match) return { day: latestAvailableDay(days, now), fallback: "not-found" };
  if (!isPublished(match.date, now)) {
    return { day: latestAvailableDay(days, now), fallback: "not-published" };
  }
  return { day: match, fallback: "none" };
}

// ---------------------------------------------------------------------------
// Display. Still pure, still clock-free: these take a date STRING and read only
// the parts of it, so a server render and a browser render agree.
// ---------------------------------------------------------------------------

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const WEEKDAY_NAMES = [
  "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
];

/** `"2026-07-28"` → `"July 2026"`. */
export function formatMonth(month: string): string {
  const [y, m] = month.slice(0, 7).split("-");
  const name = MONTH_NAMES[Number(m) - 1];
  return name ? `${name} ${y}` : month;
}

/**
 * `"2026-07-28"` → `"Tuesday, July 28"` (with the year when `withYear`).
 *
 * The weekday is computed with the LOCAL-time `Date(y, m, d)` constructor, which
 * is deterministic given the string — unlike `new Date("2026-07-28")`, which
 * parses as UTC midnight and lands on the 27th for anyone west of Greenwich.
 */
export function formatDay(date: string, withYear = false): string {
  const [y, m, d] = date.split("-").map(Number);
  if (!y || !m || !d) return date;
  const weekday = WEEKDAY_NAMES[new Date(y, m - 1, d).getDay()];
  const tail = withYear ? `, ${y}` : "";
  return `${weekday}, ${MONTH_NAMES[m - 1]} ${d}${tail}`;
}
