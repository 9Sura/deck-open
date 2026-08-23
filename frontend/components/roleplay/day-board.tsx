// The day board — one day's drop, all 28 events (frontend plan 11 §4a).
//
// Presentational: the page owns `now`, the day list, and the URL. This component
// is handed an already-resolved day and the already-computed neighbours, so it
// contains no clock and no fetch.

import { Button } from "@/components/ui/button";
import { MarkerText } from "@/components/marker-text";
import { TapeLabel } from "@/components/tape-label";
import { EventCard } from "@/components/roleplay/event-card";
import { EVENTS_BY_FORMAT } from "@/lib/data/events";
import { FORMAT_LABEL, type EventFormat } from "@/lib/deca";
import { CHALLENGE_TIMEZONE_LABEL } from "@/lib/roleplay/eastern";
import { formatDay, type DayFallback } from "@/lib/roleplay/select";
import type { RoleplayDay } from "@/lib/roleplay/types";

const ORDER: EventFormat[] = ["series", "principles", "team"];
const TOTAL_EVENTS = ORDER.reduce((n, f) => n + EVENTS_BY_FORMAT[f].length, 0);

export function DayBoard({
  day,
  dayNumber,
  prev,
  next,
  requested,
  fallback,
  onStep,
  onBrowse,
  onOpenEvent,
}: {
  day: RoleplayDay;
  /** 1-based position among all days on disk, or null if it isn't on disk. */
  dayNumber: number | null;
  /** The previous/next AVAILABLE day, or null at either end of the archive. */
  prev: RoleplayDay | null;
  next: RoleplayDay | null;
  /** What `?day=` asked for, so a fallback can name it. */
  requested: string | null;
  fallback: DayFallback;
  onStep: (date: string) => void;
  onBrowse: () => void;
  /** Opens the run surface over this board (`?event=`). Available cards only. */
  onOpenEvent: (code: string) => void;
}) {
  const present = new Set(day.events);
  const availableCount = ORDER.reduce(
    (n, fmt) => n + EVENTS_BY_FORMAT[fmt].filter((e) => present.has(e.code)).length,
    0,
  );

  return (
    <div>
      {/* ---- Day header + stepper ---- */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <MarkerText rotate={-3} className="text-base">
            {dayNumber != null ? `day ${dayNumber} of the challenge` : "the daily drop"}
          </MarkerText>
          <h2 className="mt-1 font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
            {formatDay(day.date, true)}
          </h2>
          {/* The drop is one global day on Eastern (lib/roleplay/eastern.ts), so a
              competitor on the west coast gets the new set at 9pm their time and a
              date here that their own phone won't agree with for another three
              hours. Saying which clock this runs on is the difference between that
              reading as a schedule and reading as a bug. */}
          <p className="mt-1 text-sm text-muted">
            New scenarios drop at midnight {CHALLENGE_TIMEZONE_LABEL}.
          </p>
        </div>

        {/* The PARENT wraps, but that only ever separates the heading block from
            this one — it cannot break the stepper itself, and the stepper is what
            overflows: three labelled buttons measure ~433px against a 390px phone
            (issue #206). So this row wraps too, and `justify-end` keeps a wrapped
            line hanging off the right edge where the parent's `justify-between`
            had already put it. No-op above `sm`, where all three fit on one line. */}
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!prev}
            onClick={() => prev && onStep(prev.date)}
          >
            ← Previous day
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!next}
            onClick={() => next && onStep(next.date)}
          >
            Next day →
          </Button>
          <Button variant="ghost" size="sm" onClick={onBrowse}>
            Browse the archive
          </Button>
        </div>
      </div>

      {/* ---- What the URL asked for vs. what is on screen ---- */}
      {fallback !== "none" && requested ? (
        <p className="mt-4 border-l-2 border-line pl-3 text-sm text-muted">
          {fallback === "not-published"
            ? `${formatDay(requested, true)} hasn't dropped yet — showing the latest day instead.`
            : `The archive has nothing for ${requested} — showing the latest day instead.`}
        </p>
      ) : null}

      {/* ---- Honest framing. "Harder than the district-level material DECA
              publishes" is the ONLY supportable difficulty claim (plan 11 F5):
              there is no referee, and K4/K5/subtle-K8 ship unverified. ---- */}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <TapeLabel color="highlight" rotate={-2}>
          {availableCount} of {TOTAL_EVENTS} events
        </TapeLabel>
        <p className="text-sm text-ink/70">
          Fresh scenarios, written to be harder than the district-level material DECA
          publishes.
        </p>
      </div>

      {availableCount === 0 ? (
        <p className="mt-6 rounded-2xl border-2 border-line bg-paper-2 p-5 text-sm text-muted">
          Nothing cleared the quality checks for this day. Step back to an earlier day —
          every event that did make it is still in the archive.
        </p>
      ) : null}

      {/* ---- The 28, grouped by format ---- */}
      {ORDER.map((fmt) => {
        const events = EVENTS_BY_FORMAT[fmt];
        const got = events.filter((e) => present.has(e.code)).length;
        return (
          <section key={fmt} className="mt-10">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="font-display text-xl font-bold tracking-tight">
                {FORMAT_LABEL[fmt]}
              </h3>
              <p className="marker text-sm text-muted">
                {got} of {events.length} available
              </p>
            </div>
            <div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {events.map((event, i) => {
                const available = present.has(event.code);
                return (
                  <EventCard
                    key={event.code}
                    event={event}
                    available={available}
                    // Only an available card gets a launcher — a greyed card has
                    // no file behind it, so making it clickable would open a
                    // panel whose whole content is "there's nothing here."
                    onOpen={available ? () => onOpenEvent(event.code) : undefined}
                    variant={i}
                  />
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
