"use client";

// The dashboard header (plan 09 §3): greeting + target (cluster/level), a
// readiness ring from readiness(), and the date pacing read (days-left +
// on-track/behind). A streak/level slot is intentionally LEFT for Phase C (D5) —
// room in the layout, nothing shipped. Pacing is labelled guidance, not a
// guarantee (§7.6). Pure presentational; all numbers are passed in.

import { Button } from "@/components/ui/button";
import { PlanCalendar } from "@/components/dashboard/plan-calendar";
import { CLUSTERS } from "@/lib/data/clusters";
import { LEVELS } from "@/lib/deca";
import type { PlanConfig } from "@/lib/progress/plan-config";
import type { Pacing, PlanTask } from "@/lib/progress/plan";
import type { DayForecast } from "@/lib/progress/forecast";
import { cn } from "@/lib/utils";

const clusterLabel = (value: string) =>
  CLUSTERS.find((c) => c.value === value)?.label ?? value;
const levelLabel = (value: string) =>
  LEVELS.find((l) => l.value === value)?.label ?? value;

const STATUS: Record<Pacing["status"], { label: string; cls: string }> = {
  ahead: {
    label: "Ahead of pace",
    cls: "border-[var(--diff-easy-line)] bg-[var(--diff-easy-bg)] text-[var(--diff-easy-ink)]",
  },
  "on-track": {
    label: "On track",
    cls: "border-[var(--diff-med-line)] bg-[var(--diff-med-bg)] text-[var(--diff-med-ink)]",
  },
  behind: {
    label: "Behind pace",
    cls: "border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] text-[var(--diff-hard-ink)]",
  },
  "no-date": {
    label: "No date set",
    cls: "border-line bg-paper-2 text-muted",
  },
};

export function PlanHeader({
  username,
  config,
  pacing,
  forecast,
  onLaunchTask,
  onEditPlan,
  onTakeDiagnostic,
  diagnosticTaken,
}: {
  username: string | null;
  config: PlanConfig;
  pacing: Pacing;
  /** The rolling 3-day forecast (plan 09 §9); [] hides the mini calendar. */
  forecast: DayForecast[];
  /** Launch a task from the calendar; dayOffset > 0 is a no-op at the data layer. */
  onLaunchTask: (task: PlanTask, dayOffset: number) => void;
  onEditPlan: () => void;
  /** Launch the (one-and-only) diagnostic; only shown when not yet taken. */
  onTakeDiagnostic: () => void;
  /** True once the diagnostic has been taken — the diagnostic is a one-time thing,
   *  so the button disappears for good (no retake). */
  diagnosticTaken: boolean;
}) {
  const pct = Math.round(pacing.actualReadiness * 100);
  const status = STATUS[pacing.status];

  return (
    <div className="flex flex-col gap-6 rounded-2xl border-2 border-dashed border-line bg-paper-2 p-6 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:p-8">
      {/* Left: greeting + target + controls */}
      <div className="min-w-0">
        <p className="marker text-sm text-muted">your study plan</p>
        <h1 className="mt-1 font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
          Hi{username ? `, ${username}` : ""}
        </h1>
        <p className="mt-2 text-ink/70">
          Targeting{" "}
          <span className="font-semibold text-ink">{clusterLabel(config.cluster)}</span>{" "}
          · {levelLabel(config.level)}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={onEditPlan}>
            Edit plan
          </Button>
          {!diagnosticTaken && (
            <Button variant="ghost" size="sm" onClick={onTakeDiagnostic}>
              Take diagnostic
            </Button>
          )}
        </div>
      </div>

      {/* Middle: readiness ring + pacing */}
      <div className="flex items-center gap-5">
        <ReadinessRing pct={pct} />
        <div className="flex flex-col items-start gap-2">
          {pacing.daysLeft != null ? (
            <div className="flex items-baseline gap-1.5">
              <span className="stat font-display text-3xl font-extrabold tracking-tight">
                {pacing.daysLeft}
              </span>
              <span className="text-sm text-muted">
                day{pacing.daysLeft === 1 ? "" : "s"} left
              </span>
            </div>
          ) : (
            <span className="text-sm text-muted">🎯 add a competition date</span>
          )}
          <span
            className={cn(
              "sketch-radius border-2 px-2.5 py-0.5 text-xs font-semibold",
              status.cls,
            )}
          >
            {status.label}
          </span>
          <span className="text-[0.7rem] text-muted">readiness is guidance, not a score</span>
        </div>
      </div>

      {/* Right: the compact 3-day plan calendar doodle (plan 09 §9). */}
      {forecast.length > 0 && (
        <PlanCalendar days={forecast} onLaunch={onLaunchTask} />
      )}
    </div>
  );
}

/** A small readiness donut — arc length ∝ readiness %. Redundant numeral inside. */
function ReadinessRing({ pct }: { pct: number }) {
  const r = 34;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - Math.max(0, Math.min(100, pct)) / 100);
  return (
    <div className="relative h-24 w-24 shrink-0">
      <svg viewBox="0 0 80 80" className="h-24 w-24 -rotate-90">
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          className="stroke-line"
          strokeWidth={7}
        />
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          className="stroke-accent"
          strokeWidth={7}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="stat font-display text-2xl font-extrabold leading-none">
          {pct}%
        </span>
        <span className="text-[0.6rem] uppercase tracking-wide text-muted">ready</span>
      </div>
    </div>
  );
}
