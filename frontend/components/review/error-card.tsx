"use client";

// One Error Log entry (plan 08 phase 3 sub-plan §7). Shows a missed question re-hydrated
// from the bank: the prompt, your wrong pick vs the answer, the explanation, its mistake
// pattern + spaced-review status, and a "Review now" that opens a mini-session on it.
//
// When the bank no longer carries the question (re-authored), the card degrades to a
// tag-only view with a muted note — never blank, never dropped (§10 honesty).

import * as React from "react";
import { Button } from "@/components/ui/button";
import { CLUSTERS } from "@/lib/data/clusters";
import type { BankQuestion } from "@/lib/question-bank";
import type { Difficulty } from "@/lib/question-bank";
import type { ErrorItem, MistakePattern } from "@/lib/progress/errors";
import { cn } from "@/lib/utils";

const clusterLabel = (v: string) => CLUSTERS.find((c) => c.value === v)?.label ?? v;

export const PATTERN_META: Record<
  MistakePattern,
  { label: string; blurb: string; cls: string }
> = {
  "careless-on-easy": {
    label: "Careless (easy)",
    blurb: "Wrong on an easy item, faster than your usual pace — slow down here.",
    cls: "border-[var(--diff-med-line)] bg-[var(--diff-med-bg)] text-[var(--diff-med-ink)]",
  },
  "slow-and-wrong-on-hard": {
    label: "Slow & wrong (hard)",
    blurb: "Wrong on a hard item after a long think — a genuine knowledge gap.",
    cls: "border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] text-[var(--diff-hard-ink)]",
  },
  missed: {
    label: "Missed",
    blurb: "A wrong answer — review the reasoning.",
    cls: "border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] text-[var(--diff-hard-ink)]",
  },
};

const DIFF_DOT: Record<Difficulty, string> = {
  easy: "bg-[var(--diff-easy-dot)]",
  medium: "bg-[var(--diff-med-dot)]",
  hard: "bg-[var(--diff-hard-dot)]",
};

function fmtDate(ts: number): string {
  try {
    return new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export function ErrorCard({
  item,
  question,
  onReviewNow,
}: {
  item: ErrorItem;
  question: BankQuestion | undefined;
  onReviewNow: (item: ErrorItem) => void;
}) {
  const pattern = PATTERN_META[item.latestPattern];

  return (
    <li className="rounded-xl border border-line bg-paper-2/40 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink" title={item.performanceIndicator}>
            {item.performanceIndicator}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[0.7rem] text-muted">
            <Chip>{clusterLabel(item.cluster)}</Chip>
            <Chip>{item.instructionalArea}</Chip>
            <Chip>
              <span
                className={cn("mr-1 inline-block h-1.5 w-1.5 rounded-full", DIFF_DOT[item.difficulty])}
              />
              {item.level}
            </Chip>
            <Chip className={pattern.cls}>{pattern.label}</Chip>
          </div>
        </div>
        <Button size="sm" variant="outline" className="shrink-0" onClick={() => onReviewNow(item)}>
          Review now →
        </Button>
      </div>

      {question ? (
        <div className="mt-3">
          <p className="text-sm text-ink/90">{question.question}</p>
          {/* Only the wrong option the person picked — the correct answer + explanation
              stay hidden so "Review now" is a genuine re-test, not a spoiler. The null
              guard is a type formality, not a state the app produces: every logged miss
              carries a pick, because moving past a question records nothing (#107). */}
          {item.lastChosen !== null && (
            <div className="mt-2 sketch-radius flex items-start gap-2 border border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] px-2.5 py-1.5 text-sm text-[var(--diff-hard-ink)]">
              <span className="stat font-semibold">{item.lastChosen}</span>
              <span className="min-w-0 flex-1">{question.options[item.lastChosen]}</span>
              <span aria-label="your incorrect pick">✕</span>
            </div>
          )}
          <p className="mt-2 text-[0.7rem] text-muted">
            Answer hidden — tap “Review now” to try it again.
          </p>
        </div>
      ) : (
        <p className="mt-3 rounded-lg border border-dashed border-line bg-paper px-3 py-2 text-xs text-muted">
          This question is no longer in the bank — showing your attempt tags only.
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2 text-[0.7rem] text-muted">
        <span>missed {item.misses}×</span>
        <span>last {fmtDate(item.lastMissTs)}</span>
      </div>
    </li>
  );
}

function Chip({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "sketch-radius border px-1.5 py-0.5",
        className ?? "border-line bg-paper text-muted",
      )}
    >
      {children}
    </span>
  );
}
