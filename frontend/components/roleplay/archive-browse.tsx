"use client";

// Archive browse (frontend plan 11 §4d) — every day that has dropped, by month,
// filterable by format and by event.
//
// Only PUBLISHED days are listed. Future-dated days are physically on disk (the
// buffer runs 7–14 days ahead) and stepping to one is already refused by
// `stepDay`; listing one here would put a door on the same wall. A month whose
// days are all still in the future is still SHOWN — it exists, it just has
// nothing to open yet — because the alternative is a month that silently
// vanishes and reappears.

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Segmented } from "@/components/ui/segmented";
import { MarkerText } from "@/components/marker-text";
import { EVENTS, EVENTS_BY_FORMAT } from "@/lib/data/events";
import { FORMAT_LABEL, type EventFormat } from "@/lib/deca";
import { formatDay, formatMonth, monthOf, publishedDays } from "@/lib/roleplay/select";
import type { RoleplayDay } from "@/lib/roleplay/types";

const ORDER: EventFormat[] = ["series", "principles", "team"];
type FormatFilter = EventFormat | "all";

export function ArchiveBrowse({
  months,
  days,
  now,
  onOpenDay,
  onBack,
}: {
  /** `index.months`, as listed. */
  months: string[];
  /** Every day on disk (the page filters nothing — this component does). */
  days: RoleplayDay[];
  now: number;
  onOpenDay: (date: string) => void;
  onBack: () => void;
}) {
  const [format, setFormat] = React.useState<FormatFilter>("all");
  const [code, setCode] = React.useState("all");

  // Narrowing the format resets an event that no longer belongs to it, so the
  // two filters can't contradict each other into an always-empty list.
  const setFormatFilter = (next: FormatFilter) => {
    setFormat(next);
    if (next !== "all" && code !== "all" && !EVENTS_BY_FORMAT[next].some((e) => e.code === code)) {
      setCode("all");
    }
  };

  const inFilter = React.useCallback(
    (eventCode: string) => {
      if (code !== "all") return eventCode === code;
      if (format === "all") return true;
      return EVENTS_BY_FORMAT[format].some((e) => e.code === eventCode);
    },
    [code, format],
  );

  const published = publishedDays(days, now);
  const unfiltered = code === "all" && format === "all";

  // Months from the INDEX, not from the day list: a month the index knows about
  // but that has published nothing yet still gets a row.
  const byMonth = months
    .slice()
    .sort((a, b) => b.localeCompare(a))
    .map((month) => {
      const inMonth = published
        .filter((d) => monthOf(d.date) === month)
        .sort((a, b) => b.date.localeCompare(a.date));
      return {
        month,
        days: inMonth
          .map((d) => ({ day: d, matches: d.events.filter(inFilter).length }))
          .filter((row) => row.matches > 0 || unfiltered),
        published: inMonth.length,
      };
    });

  const eventOptions = [
    { value: "all", label: "Every event" },
    ...(format === "all" ? EVENTS : EVENTS_BY_FORMAT[format]).map((e) => ({
      value: e.code,
      label: `${e.code} — ${e.name}`,
    })),
  ];

  const totalListed = byMonth.reduce((n, m) => n + m.days.length, 0);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <MarkerText rotate={-3} className="text-base">
            the archive
          </MarkerText>
          <h2 className="mt-1 font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
            Every day so far
          </h2>
        </div>
        <Button variant="outline" size="sm" onClick={onBack}>
          ← Back to the latest day
        </Button>
      </div>

      {/* ---- Filters ---- */}
      <div className="mt-6 grid gap-4 sm:grid-cols-[auto_minmax(0,20rem)] sm:items-end">
        <div>
          <p className="marker mb-2 text-sm text-muted">format</p>
          <Segmented
            value={format}
            onChange={setFormatFilter}
            options={[
              { value: "all" as FormatFilter, label: "All" },
              ...ORDER.map((f) => ({ value: f as FormatFilter, label: FORMAT_LABEL[f] })),
            ]}
          />
        </div>
        <div>
          <p className="marker mb-2 text-sm text-muted">event</p>
          <Select value={code} onChange={setCode} aria-label="event" options={eventOptions} />
        </div>
      </div>

      {published.length === 0 ? (
        <p className="mt-8 rounded-2xl border-2 border-line bg-paper-2 p-5 text-sm text-muted">
          Nothing has dropped yet. The first day will appear here as soon as it does.
        </p>
      ) : totalListed === 0 ? (
        <p className="mt-8 rounded-2xl border-2 border-line bg-paper-2 p-5 text-sm text-muted">
          No day in the archive carries that event yet.
        </p>
      ) : null}

      {/* ---- Months, newest first ---- */}
      <div className="mt-8 space-y-8">
        {byMonth.map(({ month, days: rows, published: count }) => (
          <section key={month}>
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-dashed border-line pb-2">
              <h3 className="font-display text-xl font-bold tracking-tight">
                {formatMonth(month)}
              </h3>
              {/* The heading counts what is RENDERED under it. `count` is the
                  month's whole published supply, and the rows are filtered, so
                  quoting `count` alone let a month read "2 days" over nothing
                  at all (#159). Under a filter both numbers are shown, because
                  the supply is still the honest answer to "what dropped". */}
              <p className="marker text-sm text-muted">
                {count === 0
                  ? "nothing published yet"
                  : unfiltered
                    ? `${count} day${count === 1 ? "" : "s"}`
                    : rows.length === 0
                      ? `${count} day${count === 1 ? "" : "s"} · none match`
                      : `${rows.length} of ${count} day${count === 1 ? "" : "s"}`}
              </p>
            </div>

            {/* A month with supply but no matching rows would otherwise be a
                heading over whitespace — the top-of-page notice only fires when
                NOTHING matches in ANY month. */}
            {count > 0 && rows.length === 0 ? (
              <p className="mt-3 px-3 py-2.5 text-sm text-muted">
                Nothing this month matches the current filter.
              </p>
            ) : null}

            {rows.length > 0 ? (
              <ul className="mt-3 space-y-2">
                {rows.map(({ day, matches }) => (
                  <li key={day.date}>
                    <button
                      type="button"
                      onClick={() => onOpenDay(day.date)}
                      className="flex w-full flex-wrap items-baseline justify-between gap-2 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-paper-2"
                    >
                      <span className="font-medium">{formatDay(day.date)}</span>
                      <span className="text-sm text-muted">
                        {code === "all" && format === "all"
                          ? `${day.events.length} of ${EVENTS.length} events`
                          : `${matches} matching event${matches === 1 ? "" : "s"}`}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        ))}
      </div>
    </div>
  );
}
