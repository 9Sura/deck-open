"use client";

// Practice history (plan 08 phase 2 §7.4). Session rows newest-first: when, where
// (origin · cluster · level), score, difficulty mix, duration, and an "abandoned"
// tag when a session was left unfinished. No row action in Phase 2 (re-opening a
// session is Phase 3+).

import * as React from "react";
import { MarkerText } from "@/components/marker-text";
import { CLUSTERS } from "@/lib/data/clusters";
import type { Attempt, AttemptSource, Session } from "@/lib/progress/types";
import type { Difficulty } from "@/lib/question-bank";
import { cn } from "@/lib/utils";

const clusterLabel = (v: string) => CLUSTERS.find((c) => c.value === v)?.label ?? v;

const ORIGIN_LABEL: Record<AttemptSource, string> = {
  focus: "Focus",
  "test-gen": "Test-gen",
  "review-lab": "Review",
  diagnostic: "Diagnostic",
  browse: "Browse",
};

const DIFF_DOT: Record<Difficulty, string> = {
  easy: "bg-[var(--diff-easy-dot)]",
  medium: "bg-[var(--diff-med-dot)]",
  hard: "bg-[var(--diff-hard-dot)]",
};

function fmtDate(ts: number): string {
  try {
    return new Date(ts).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function fmtDuration(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return rem === 0 ? `${m}m` : `${m}m ${rem}s`;
}

export function PracticeHistory({
  sessions,
  attempts,
}: {
  sessions: Session[];
  attempts: Attempt[];
}) {
  const bySession = React.useMemo(() => {
    const map = new Map<string, Attempt[]>();
    for (const a of attempts) {
      const list = map.get(a.sessionId);
      if (list) list.push(a);
      else map.set(a.sessionId, [a]);
    }
    return map;
  }, [attempts]);

  return (
    <section className="rounded-2xl border-2 border-line bg-paper p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-display text-xl font-bold tracking-tight">Practice history</h2>
        <MarkerText rotate={-2} className="text-xs">
          {sessions.length} session{sessions.length === 1 ? "" : "s"}
        </MarkerText>
      </div>

      {sessions.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted">
          No sessions in this filter yet.
        </p>
      ) : (
        <ul className="divide-y divide-line">
          {sessions.map((s) => {
            const abandoned = s.endedTs === null || s.answered < s.total;
            const accPct =
              s.answered > 0 ? Math.round((s.correct / s.answered) * 100) : null;
            const mix = diffMix(bySession.get(s.id) ?? []);
            return (
              <li
                key={s.id}
                className="flex flex-wrap items-center gap-x-4 gap-y-1.5 py-3 text-sm"
              >
                <span className="stat w-32 shrink-0 text-muted">{fmtDate(s.ts)}</span>
                <span className="flex items-center gap-1.5">
                  <span className="sketch-radius border border-line bg-paper-2 px-1.5 py-0.5 text-[0.7rem] text-muted">
                    {ORIGIN_LABEL[s.source]}
                  </span>
                  <span className="text-ink/80">
                    {clusterLabel(s.cluster)} · {s.level}
                  </span>
                </span>

                <span className="ml-auto flex items-center gap-3">
                  {mix.total > 0 && (
                    <span className="hidden items-center gap-1.5 sm:flex" aria-hidden>
                      {(["easy", "medium", "hard"] as Difficulty[])
                        .filter((d) => mix[d] > 0)
                        .map((d) => (
                          <span key={d} className="flex items-center gap-1 text-[0.7rem] text-muted">
                            <span className={cn("h-2 w-2 rounded-full", DIFF_DOT[d])} />
                            {mix[d]}
                          </span>
                        ))}
                    </span>
                  )}
                  {accPct !== null ? (
                    <span className="stat font-semibold text-ink">
                      {s.correct}/{s.answered}
                      <span className="ml-1 text-muted">({accPct}%)</span>
                    </span>
                  ) : (
                    <span className="text-muted">no picks</span>
                  )}
                  <span className="stat w-14 text-right text-muted">
                    {fmtDuration(s.elapsedMs)}
                  </span>
                  {abandoned && (
                    <span className="sketch-radius border border-[var(--diff-med-line)] bg-[var(--diff-med-bg)] px-1.5 py-0.5 text-[0.7rem] text-[var(--diff-med-ink)]">
                      abandoned
                    </span>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function diffMix(attempts: Attempt[]): Record<Difficulty, number> & { total: number } {
  const mix = { easy: 0, medium: 0, hard: 0, total: 0 };
  for (const a of attempts) {
    mix[a.difficulty]++;
    mix.total++;
  }
  return mix;
}
