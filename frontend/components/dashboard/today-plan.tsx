"use client";

// Today's Plan (plan 09 §3 + follow-up) — the ordered PlanTask[] from
// buildStudyPlan as task cards. Each card's Start launches an existing surface
// (drill / quiz / review); a card ticks "done" only when its progress reaches its
// target (derived in plan.ts, never stored). A per-card dropdown reveals a status
// bar so an unfinished task still shows how far along it is.
//
// The user can edit the day:
//  - Remove a task — recommended tasks dismiss, added tasks delete — behind a
//    two-step confirm so a stray click can't wipe a task.
//  - "Add a task" picks a recommendation TYPE (weak drill, coverage, warm-up,
//    challenge, milestone, fix misses) from a menu; the dashboard materializes a
//    real task of that type (it generates the right questions and tracks progress
//    like any recommended task). Both edits persist synced (config.today) and feed
//    back into the recommender (dismissed drop out, added trim the count + dedupe).

import * as React from "react";
import { Button } from "@/components/ui/button";
import { MarkerText } from "@/components/marker-text";
import type { PlanTask } from "@/lib/progress/plan";
import type { PlanTaskType } from "@/lib/progress/plan-config";
import { cn } from "@/lib/utils";

/** One option in the "Add a task" menu. */
export interface AddOption {
  type: PlanTaskType;
  label: string;
  desc: string;
  disabled: boolean;
  /** Why it's disabled — shown as a hover tooltip on a disabled option. */
  reason?: string;
}

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

const progressVerb = (type: PlanTask["type"]) =>
  type === "fix-misses" ? "fixed" : "done";

/* --------------------------------------------------- add-menu option row */

// A single add-menu option. A disabled option is aria-disabled (not natively
// `disabled`, which would swallow hover) and shows its reason as a tooltip that
// follows the cursor while the pointer is inside the row.
function AddOptionRow({
  opt,
  onPick,
}: {
  opt: AddOption;
  onPick: (type: PlanTaskType) => void;
}) {
  const [pos, setPos] = React.useState<{ x: number; y: number } | null>(null);
  const showTip = opt.disabled && !!opt.reason;

  return (
    <div className="relative">
      <button
        type="button"
        aria-disabled={opt.disabled}
        onClick={() => {
          if (!opt.disabled) onPick(opt.type);
        }}
        onMouseMove={(e) => {
          if (!showTip) return;
          const r = e.currentTarget.getBoundingClientRect();
          setPos({ x: e.clientX - r.left, y: e.clientY - r.top });
        }}
        onMouseLeave={() => setPos(null)}
        className={cn(
          "flex w-full items-center justify-between gap-3 rounded-xl border-2 px-3 py-2 text-left transition-colors",
          opt.disabled
            ? "cursor-not-allowed border-dashed border-line opacity-50"
            : "border-line hover:border-ink hover:bg-paper-2",
        )}
      >
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold">{opt.label}</span>
          <span className="block truncate text-xs text-muted">{opt.desc}</span>
        </span>
        {!opt.disabled && <span className="shrink-0 text-lg leading-none text-accent-ink">+</span>}
      </button>
      {showTip && pos && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-30 w-max max-w-[15rem] sketch-radius border-2 border-ink bg-paper px-2.5 py-1.5 text-xs text-ink shadow-[var(--btn-shadow)]"
          style={{ left: pos.x + 14, top: pos.y + 16 }}
        >
          {opt.reason}
        </div>
      )}
    </div>
  );
}

export function TodayPlan({
  tasks,
  onLaunch,
  onDismiss,
  onRemoveCustom,
  onAddTaskType,
  addOptions,
}: {
  tasks: PlanTask[];
  onLaunch: (task: PlanTask) => void;
  /** Remove a recommended task for today (won't be re-recommended). */
  onDismiss: (id: string) => void;
  /** Delete a user-added task. */
  onRemoveCustom: (id: string) => void;
  /** Add a task of the chosen recommendation type. */
  onAddTaskType: (type: PlanTaskType) => void;
  addOptions: AddOption[];
}) {
  const remaining = tasks.filter((t) => !t.done).length;
  const [expanded, setExpanded] = React.useState<Set<string>>(() => new Set());
  const [confirming, setConfirming] = React.useState<string | null>(null);
  const [adding, setAdding] = React.useState(false);

  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <section>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-xl font-bold tracking-tight">Today&apos;s plan</h2>
        <span className="text-sm text-muted">
          {remaining === 0 ? "all done 🎉" : `${remaining} left`}
        </span>
      </div>

      {tasks.length === 0 ? (
        <div className="mt-4 rounded-2xl border-2 border-dashed border-line bg-paper-2 p-6 text-center">
          <MarkerText rotate={-2} className="text-sm">
            nothing queued
          </MarkerText>
          <p className="mt-2 text-sm text-ink/70">
            Practice a little, or add your own task below.
          </p>
        </div>
      ) : (
        <ul className="mt-4 flex flex-col gap-3">
          {tasks.map((task) => {
            const isAdded = task.added === true;
            const isOpen = expanded.has(task.id);
            const isConfirming = confirming === task.id;
            const { current, total } = task.progress;
            const pct = total > 0 ? Math.round((current / total) * 100) : 0;
            const hasBar = total > 1;
            return (
              <li
                key={task.id}
                className={cn(
                  "rounded-2xl border-2 transition-colors",
                  task.done
                    ? "border-dashed border-line bg-paper-2/60"
                    : isAdded
                      ? "border-ink bg-paper-2/40"
                      : "border-ink bg-paper",
                )}
              >
                <div className="flex items-center gap-3 p-4">
                  <span
                    aria-hidden
                    className={cn(
                      "sketch-radius flex h-8 w-8 shrink-0 items-center justify-center border-2 text-sm font-bold",
                      task.done
                        ? "border-[var(--diff-easy-line)] bg-[var(--diff-easy-bg)] text-[var(--diff-easy-ink)]"
                        : "border-ink bg-accent text-[var(--on-accent)]",
                    )}
                  >
                    {task.done ? "✓" : ""}
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p
                        className={cn(
                          "truncate font-semibold",
                          task.done && "text-ink/60 line-through",
                        )}
                      >
                        {task.title}
                      </p>
                      <span
                        className={cn(
                          "sketch-radius border-2 px-1.5 py-0.5 text-[0.65rem] font-semibold",
                          HINT[task.difficultyHint].cls,
                        )}
                      >
                        {HINT[task.difficultyHint].label}
                      </span>
                      {isAdded && (
                        <span className="sketch-radius border-2 border-line px-1.5 py-0.5 text-[0.65rem] font-semibold text-muted">
                          yours
                        </span>
                      )}
                      <span className="text-[0.7rem] text-muted">
                        {current}/{total}
                      </span>
                    </div>
                    <p className="truncate text-sm text-muted">{task.subtitle}</p>
                  </div>

                  {isConfirming ? (
                    // ---- two-step remove confirm ----
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="hidden text-xs text-muted sm:inline">
                        {isAdded ? "Delete?" : "Remove?"}
                      </span>
                      <Button
                        variant="primary"
                        size="sm"
                        className="!bg-[var(--diff-hard-bg)] !text-[var(--diff-hard-ink)]"
                        onClick={() => {
                          if (isAdded) onRemoveCustom(task.id);
                          else onDismiss(task.id);
                          setConfirming(null);
                        }}
                      >
                        {isAdded ? "Delete" : "Remove"}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <>
                      {hasBar && (
                        <button
                          type="button"
                          onClick={() => toggle(task.id)}
                          aria-expanded={isOpen}
                          aria-label={isOpen ? "Hide progress" : "Show progress"}
                          className="shrink-0 rounded-lg p-1.5 text-muted transition-colors hover:bg-ink/5 hover:text-ink"
                        >
                          <svg
                            viewBox="0 0 24 24"
                            className={cn("h-4 w-4 transition-transform", isOpen && "rotate-180")}
                            fill="none"
                            stroke="currentColor"
                            strokeWidth={2.5}
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden
                          >
                            <path d="M6 9l6 6 6-6" />
                          </svg>
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setConfirming(task.id)}
                        aria-label={isAdded ? "Delete task" : "Remove from today"}
                        title={isAdded ? "Delete task" : "Remove from today"}
                        className="shrink-0 rounded-lg p-1.5 text-muted transition-colors hover:bg-[var(--diff-hard-bg)] hover:text-[var(--diff-hard-ink)]"
                      >
                        <svg
                          viewBox="0 0 24 24"
                          className="h-4 w-4"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={2.5}
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          aria-hidden
                        >
                          <path d="M6 6l12 12M18 6L6 18" />
                        </svg>
                      </button>
                      {!task.done && (
                        <Button
                          variant="primary"
                          size="sm"
                          className="shrink-0"
                          onClick={() => onLaunch(task)}
                        >
                          Start
                        </Button>
                      )}
                    </>
                  )}
                </div>

                {hasBar && isOpen && (
                  <div className="border-t border-dashed border-line px-4 pb-4 pt-3">
                    <div className="mb-1.5 flex items-center justify-between text-xs text-muted">
                      <span>
                        {current} of {total} {progressVerb(task.type)}
                      </span>
                      <span className="stat font-semibold">{pct}%</span>
                    </div>
                    <div
                      className="h-2.5 w-full overflow-hidden rounded-full border border-line bg-paper-2"
                      role="progressbar"
                      aria-valuenow={current}
                      aria-valuemin={0}
                      aria-valuemax={total}
                    >
                      <div
                        className={cn(
                          "h-full rounded-full transition-[width] duration-300",
                          task.done ? "bg-[var(--diff-easy-line)]" : "bg-accent",
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {/* Add-a-task — a menu of recommendation types */}
      {adding ? (
        <div className="mt-3 rounded-2xl border-2 border-ink bg-paper p-3">
          <div className="mb-2 flex items-center justify-between px-1">
            <p className="marker text-xs text-muted">add a task</p>
            <button
              type="button"
              onClick={() => setAdding(false)}
              className="rounded-md px-2 py-0.5 text-xs text-muted hover:bg-ink/5 hover:text-ink"
            >
              Cancel
            </button>
          </div>
          <div className="flex flex-col gap-1.5">
            {addOptions.map((opt) => (
              <AddOptionRow
                key={opt.type}
                opt={opt}
                onPick={(type) => {
                  onAddTaskType(type);
                  setAdding(false);
                }}
              />
            ))}
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-line py-3 text-sm font-medium text-muted transition-colors hover:border-ink hover:text-ink"
        >
          <span className="text-base leading-none">+</span> Add a task
        </button>
      )}
    </section>
  );
}
