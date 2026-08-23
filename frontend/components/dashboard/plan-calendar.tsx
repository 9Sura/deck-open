"use client";

// The 3-day plan calendar (plan 09 §9.3, BD4). A compact Today · Tomorrow · +2
// strip in the header box; tapping a day opens a popup of that day's tasks + their
// status. Today is live (real done/progress + a working Start); future days are
// PREVIEW-ONLY — a "planned" chip, a lock, and NO Start (BD3, also enforced at the
// data layer in study-dashboard). The forecast is labelled "expected · firms up
// each day" (BD5) — directional, not a promise.
//
// Pure presentational: the forecast is computed upstream (forecast.ts) and passed
// in. `now` is already baked into each DayForecast.ts, so weekday formatting uses
// `new Date(ts)` (arg form — allowed under the React Compiler purity rules).

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import type { DayForecast } from "@/lib/progress/forecast";
import type { Pacing, PlanTask } from "@/lib/progress/plan";
import { localDateKey } from "@/lib/progress/plan-config";
import { cn } from "@/lib/utils";

const HINT: Record<PlanTask["difficultyHint"], { label: string; cls: string }> = {
  build: {
    label: "build",
    cls: "border-[var(--diff-easy-line)] bg-[var(--diff-easy-bg)] text-[var(--diff-easy-ink)]",
  },
  mixed: {
    label: "mixed",
    cls: "border-[var(--diff-med-line)] bg-[var(--diff-med-bg)] text-[var(--diff-med-ink)]",
  },
  challenge: {
    label: "challenge",
    cls: "border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] text-[var(--diff-hard-ink)]",
  },
};

const STATUS: Record<Pacing["status"], string> = {
  ahead: "text-[var(--diff-easy-ink)]",
  "on-track": "text-[var(--diff-med-ink)]",
  behind: "text-[var(--diff-hard-ink)]",
  "no-date": "text-muted",
};
const STATUS_LABEL: Record<Pacing["status"], string> = {
  ahead: "ahead of pace",
  "on-track": "on track",
  behind: "behind pace",
  "no-date": "no date set",
};

const dayName = (day: DayForecast) =>
  day.dayOffset === 0
    ? "Today"
    : day.dayOffset === 1
      ? "Tomorrow"
      : new Date(day.ts).toLocaleDateString(undefined, { weekday: "long" });

export function PlanCalendar({
  days,
  onLaunch,
}: {
  days: DayForecast[];
  /** Launch a task from a day. dayOffset > 0 is a no-op at the data layer (BD3). */
  onLaunch: (task: PlanTask, dayOffset: number) => void;
}) {
  const [openOffset, setOpenOffset] = React.useState<number | null>(null);
  const selected = days.find((d) => d.dayOffset === openOffset) ?? null;

  // Launching a today task closes the popup first, so the hosted quiz modal
  // isn't stacked underneath this dialog (future days no-op at the data layer).
  const handleLaunch = React.useCallback(
    (task: PlanTask, dayOffset: number) => {
      setOpenOffset(null);
      onLaunch(task, dayOffset);
    },
    [onLaunch],
  );

  // A month grid centred on today; only the forecast days (today, +1, +2) are
  // active — every other cell is inert (clicking does nothing).
  const today = days[0];
  // Cheap derivations (~42-cell grid); the React Compiler memoizes them.
  // FIRST-wins, not last-wins (issue #122): forecast dates are distinct by
  // construction now that forecast.ts steps by calendar day, but if two ever
  // collide again the LIVE day must win the cell — a projected day there is
  // locked, so today would lose its Start buttons and its "today" pill.
  const byDate = new Map<string, DayForecast>();
  for (const d of days) if (!byDate.has(d.date)) byDate.set(d.date, d);
  // The grid must COVER the whole forecast window, not just today's month
  // (issue #132) — see buildMonthGrid.
  const grid = buildMonthGrid(today.ts, days[days.length - 1].ts);
  const monthLabel = windowMonthLabel(today.ts, days[days.length - 1].ts);

  return (
    <div className="w-full shrink-0 sketch-radius border-2 border-line bg-paper p-2.5 sm:w-52">
      <p className="mb-1 text-center text-[0.7rem] font-bold tracking-tight">{monthLabel}</p>

      {/* weekday header */}
      <div className="grid grid-cols-7 text-center">
        {WEEKDAYS.map((w, i) => (
          <span key={i} className="text-[0.5rem] font-semibold uppercase text-muted">
            {w}
          </span>
        ))}
      </div>

      {/* day cells */}
      <div className="mt-0.5 grid grid-cols-7 gap-0.5">
        {grid.map((cell) => (
          <DayCell
            key={cell.dateKey}
            cell={cell}
            forecast={byDate.get(cell.dateKey)}
            onOpen={setOpenOffset}
          />
        ))}
      </div>

      <Dialog
        open={selected !== null}
        onClose={() => setOpenOffset(null)}
        label={selected ? `Plan for ${dayName(selected)}` : "Plan"}
        className="max-w-lg"
      >
        {selected && (
          <DayPopup
            day={selected}
            onClose={() => setOpenOffset(null)}
            onLaunch={handleLaunch}
          />
        )}
      </Dialog>
    </div>
  );
}

/* --------------------------------------------------------------- month grid */

const WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"];

interface GridCell {
  ts: number;
  dateKey: string;
  dayNum: number;
  inMonth: boolean;
}

/** The calendar cells for the month containing `todayTs` (whole weeks, trimmed to
 *  the last week with an in-month day), GROWN if necessary so the last cell reaches
 *  `coverThroughTs`. Pure; `new Date(y, m, d)` is arg-form.
 *
 *  The grow step is the fix for issue #132. Trimming to whole weeks means the last
 *  cell can BE the last day of the month, so on the final day or two of some months
 *  (2026-10-31, 2026-02-28, 2028-09-30 — 15 days across 2026–2028) tomorrow's and
 *  the day-after's date have no cell at all, `byDate.get(cell.dateKey)` never
 *  matches them, and a "3-day" calendar renders one openable day. Sizing off the
 *  forecast window rather than off the month makes coverage a consequence instead of
 *  a coincidence, so it can't regress if the window ever grows past 3 days. */
function buildMonthGrid(todayTs: number, coverThroughTs: number): GridCell[] {
  const d = new Date(todayTs);
  const year = d.getFullYear();
  const month = d.getMonth();
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cellAt = (i: number): GridCell => {
    const cellDate = new Date(year, month, 1 - firstWeekday + i);
    const ts = cellDate.getTime();
    return {
      ts,
      dateKey: localDateKey(ts),
      dayNum: cellDate.getDate(),
      inMonth: cellDate.getMonth() === month,
    };
  };
  // Compare DATE KEYS, not timestamps: a cell's ts is local midnight while
  // `coverThroughTs` carries a time of day, and the keys are what byDate looks up.
  // They're YYYY-MM-DD, so string order is date order. Each pass advances the last
  // cell a full week, so this terminates.
  const coverKey = localDateKey(coverThroughTs);
  let total = Math.ceil((firstWeekday + daysInMonth) / 7) * 7;
  while (cellAt(total - 1).dateKey < coverKey) total += 7;
  const cells: GridCell[] = [];
  for (let i = 0; i < total; i++) cells.push(cellAt(i));
  return cells;
}

/** The heading over the grid: the month(s) the FORECAST WINDOW spans — a single
 *  month while today and +2 share one, a range when they don't ("Oct – Nov 2026",
 *  "Dec 2026 – Jan 2027").
 *
 *  Issue #161: this used to format `today.ts` alone, while buildMonthGrid grows past
 *  the end of today's month so every forecast day has a cell (#132) — so on the last
 *  day or two of some months the openable cells sat in the next month under a heading
 *  naming the current one.
 *
 *  The window, NOT the grid's own span: the grid's leading cells are the tail of the
 *  previous month on nearly every month (whole-week padding), so labelling the grid
 *  would read "Sep – Oct 2026" almost always. The window is exactly the set of cells
 *  a user can open, which is what the heading is for, and it stays right if the
 *  window ever grows past 3 days.
 *
 *  `formatRange` collapses shared fields itself (equal month+year renders as the
 *  single-date format), so the three shapes above need no branching here. */
function windowMonthLabel(startTs: number, endTs: number): string {
  return new Intl.DateTimeFormat(undefined, { month: "short", year: "numeric" }).formatRange(
    new Date(startTs),
    new Date(endTs),
  );
}

/** One month-grid day. Inert unless it's a forecast day (today / +1 / +2). */
function DayCell({
  cell,
  forecast,
  onOpen,
}: {
  cell: GridCell;
  forecast: DayForecast | undefined;
  onOpen: (dayOffset: number) => void;
}) {
  const hasTasks = (forecast?.tasks.length ?? 0) > 0;

  // Inert cell — a plain number, not focusable, click does nothing.
  if (!forecast) {
    return (
      <div
        className={cn(
          "flex h-6 items-center justify-center text-[0.65rem]",
          cell.inMonth ? "text-ink/60" : "text-muted/30",
        )}
      >
        {cell.dayNum}
      </div>
    );
  }

  const isToday = forecast.dayOffset === 0;
  const label =
    forecast.dayOffset === 0 ? "Today" : forecast.dayOffset === 1 ? "tomorrow" : "the day after";

  return (
    <button
      type="button"
      onClick={() => onOpen(forecast.dayOffset)}
      aria-label={`Plan for ${label} — ${forecast.tasks.length} task${forecast.tasks.length === 1 ? "" : "s"}`}
      className="relative flex h-6 items-center justify-center rounded-md transition-colors hover:bg-ink/5"
    >
      <span
        className={cn(
          "flex h-5 w-5 items-center justify-center rounded-full text-[0.65rem]",
          isToday
            ? "bg-accent font-bold text-[var(--on-accent)]"
            : "border-2 border-ink font-semibold text-ink",
        )}
      >
        {cell.dayNum}
      </span>
      {hasTasks && (
        <span
          aria-hidden
          className={cn(
            "absolute bottom-0 h-1 w-1 rounded-full",
            isToday ? "bg-accent" : "bg-ink/60",
          )}
        />
      )}
    </button>
  );
}

/* ------------------------------------------------------------- the day popup */

function DayPopup({
  day,
  onClose,
  onLaunch,
}: {
  day: DayForecast;
  onClose: () => void;
  onLaunch: (task: PlanTask, dayOffset: number) => void;
}) {
  const locked = day.dayOffset > 0;
  const p = day.pacing;

  return (
    <div className="sketch-radius border-2 border-ink bg-paper shadow-[var(--btn-shadow)]">
      {/* header */}
      <div className="flex items-start justify-between gap-4 border-b-2 border-dashed border-line p-5">
        <div>
          <h2 className="font-display text-xl font-bold tracking-tight">{dayName(day)}</h2>
          <p className="text-sm text-muted">
            {new Date(day.ts).toLocaleDateString(undefined, {
              weekday: "long",
              month: "long",
              day: "numeric",
            })}
            {locked && " · preview"}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="rounded-lg p-1.5 text-muted transition-colors hover:bg-ink/5 hover:text-ink"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" aria-hidden>
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>

      {/* task list */}
      <div className="max-h-[50vh] overflow-y-auto p-5">
        {day.tasks.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">Nothing planned for this day.</p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {day.tasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                locked={locked}
                unlockDay={dayName(day)}
                onLaunch={() => onLaunch(task, day.dayOffset)}
              />
            ))}
          </ul>
        )}
      </div>

      {/* pacing footer */}
      <div className="flex items-center justify-between gap-3 border-t-2 border-dashed border-line px-5 py-3.5">
        <span className="text-xs text-muted">
          {locked ? "Projected readiness" : "Readiness"}
        </span>
        <span className="flex items-baseline gap-2">
          <span className="stat font-display text-lg font-extrabold tracking-tight">
            {Math.round(p.actualReadiness * 100)}%
          </span>
          <span className={cn("text-xs font-semibold", STATUS[p.status])}>
            {STATUS_LABEL[p.status]}
          </span>
        </span>
      </div>
    </div>
  );
}

function TaskRow({
  task,
  locked,
  unlockDay,
  onLaunch,
}: {
  task: PlanTask;
  locked: boolean;
  unlockDay: string;
  onLaunch: () => void;
}) {
  const { current, total } = task.progress;
  return (
    <li
      className={cn(
        "flex items-center gap-3 rounded-xl border-2 p-3",
        task.done ? "border-dashed border-line bg-paper-2/60" : "border-line bg-paper",
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className={cn("truncate text-sm font-semibold", task.done && "text-ink/60 line-through")}>
            {task.title}
          </p>
          <span
            className={cn(
              "sketch-radius border-2 px-1.5 py-0.5 text-[0.6rem] font-semibold",
              HINT[task.difficultyHint].cls,
            )}
          >
            {HINT[task.difficultyHint].label}
          </span>
          <span className="text-[0.65rem] text-muted">×{task.size}</span>
        </div>
        <p className="truncate text-xs text-muted">{task.subtitle}</p>
      </div>

      {locked ? (
        <div className="flex shrink-0 flex-col items-end gap-0.5">
          <span className="sketch-radius border-2 border-line px-1.5 py-0.5 text-[0.6rem] font-semibold text-muted">
            planned
          </span>
          <span className="text-[0.6rem] text-muted">unlocks {unlockDay}</span>
        </div>
      ) : task.done ? (
        <span className="shrink-0 text-sm font-semibold text-[var(--diff-easy-ink)]">✓ done</span>
      ) : (
        <div className="flex shrink-0 items-center gap-2">
          {current > 0 && (
            <span className="text-[0.7rem] text-muted">
              {current}/{total}
            </span>
          )}
          <Button variant="primary" size="sm" onClick={onLaunch}>
            Start
          </Button>
        </div>
      )}
    </li>
  );
}
