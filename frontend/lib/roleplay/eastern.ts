// The Roleplay Challenge runs on ONE GLOBAL DAY, and that day is Eastern.
//
// This is deliberately UNLIKE every other date in the app. The study plan's day
// key (`localDateKey` in lib/progress/plan-config.ts) is the VIEWER's local day,
// and must stay that way — it keys `config.today`, so a user's own plan has to
// roll over on their own midnight (issue #32). Do not unify the two.
//
// The challenge is the opposite kind of thing: a shared daily drop. "Today's
// roleplays" has to mean the same set of files for everyone, or the cohort splits
// across two different days — a viewer-local boundary would hand Tokyo tomorrow's
// drop thirteen hours before New York got it, and two competitors practising
// together would be looking at different scenarios. DECA is a US organisation and
// runs its own deadlines on Eastern, so Eastern is the boundary.
//
// PURE: every function takes `now` (epoch ms). No `Date.now()`, no argless
// `new Date()` — same rule as select.ts, for the same reason.

/** The one timezone the challenge's day boundary is measured in. */
export const CHALLENGE_TIMEZONE = "America/New_York";

/** Human label for the boundary, for the one place the UI names it. */
export const CHALLENGE_TIMEZONE_LABEL = "Eastern time";

// Built once: constructing an Intl.DateTimeFormat is the expensive part, and
// formatting with it afterwards is cheap. Only the date parts are requested —
// nothing here needs the wall-clock time, and asking for `hour` drags in the
// hour12/hourCycle "24:00" ambiguity for no benefit.
//
// This resolves DST from the ICU tz database rather than from hardcoded
// second-Sunday-in-March arithmetic, so it stays correct if the US ever changes
// its DST rules (a live legislative proposal, not a hypothetical).
const DATE_PARTS = new Intl.DateTimeFormat("en-US", {
  timeZone: CHALLENGE_TIMEZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/**
 * The `YYYY-MM-DD` Eastern date for an epoch ms — the challenge's "today",
 * identical for every viewer on earth at the same instant.
 */
export function easternDateKey(ms: number): string {
  const parts = DATE_PARTS.formatToParts(new Date(ms));
  let year = "";
  let month = "";
  let day = "";
  for (const p of parts) {
    if (p.type === "year") year = p.value;
    else if (p.type === "month") month = p.value;
    else if (p.type === "day") day = p.value;
  }
  return `${year}-${month}-${day}`;
}

/**
 * Milliseconds from `ms` until the next Eastern midnight — how long an open tab
 * has before the drop rolls over. Always > 0.
 *
 * Found by binary search rather than by "24h minus the time so far", because an
 * Eastern day is 23, 24 or 25 hours long depending on DST and the arithmetic
 * version is silently an hour wrong twice a year. `easternDateKey` is
 * non-decreasing in time, so `key === today` is true over a prefix of the search
 * window and false after it — a monotone predicate, which is exactly what binary
 * search needs. It converges on the FIRST instant of the next day even when the
 * window happens to span more than one boundary.
 *
 * ~27 iterations, once per tab per day. The cost is nothing; the correctness is
 * the point.
 */
export function msUntilNextEasternDay(ms: number): number {
  const today = easternDateKey(ms);
  let lo = ms; // known to still be `today`
  // A day is at most 25h, so this is guaranteed to be past the boundary.
  let hi = ms + 25 * 60 * 60 * 1000 + 60_000;
  while (hi - lo > 1) {
    const mid = lo + Math.floor((hi - lo) / 2);
    if (easternDateKey(mid) === today) lo = mid;
    else hi = mid;
  }
  return hi - ms;
}
