"use client";

// The Error Log. A grouped, browsable list of every missed question — toggle between
// grouping by performance indicator and by mistake pattern. Each card is re-hydrated from
// the bank (or degrades to tags-only). Cards are mistake-driven history; "Review now"
// turns any one into a mini review session.

import * as React from "react";
import { MarkerText } from "@/components/marker-text";
import { ErrorCard, PATTERN_META } from "@/components/review/error-card";
import { CLUSTERS } from "@/lib/data/clusters";
import type { BankQuestion } from "@/lib/question-bank";
import type { ErrorItem, MistakePattern } from "@/lib/progress/errors";
import { cn } from "@/lib/utils";

const clusterLabel = (v: string) => CLUSTERS.find((c) => c.value === v)?.label ?? v;

type GroupMode = "pi" | "pattern";

// Pattern sections render in a stable, meaningful order (actionable first).
// No "skipped" section: moving past a question is navigation, not an attempt, so
// nothing in the app logs one and the section could only ever render empty (#107).
const PATTERN_ORDER: MistakePattern[] = [
  "slow-and-wrong-on-hard",
  "careless-on-easy",
  "missed",
];

export function ErrorLog({
  errorItems,
  errorsByPI,
  errorsByPattern,
  resolved,
  onReviewNow,
}: {
  errorItems: ErrorItem[];
  errorsByPI: Map<string, ErrorItem[]>;
  errorsByPattern: Map<MistakePattern, ErrorItem[]>;
  resolved: Map<string, BankQuestion>;
  onReviewNow: (item: ErrorItem) => void;
}) {
  const [mode, setMode] = React.useState<GroupMode>("pi");

  // By-PI sections, ordered by most recent miss in the group.
  const piSections = React.useMemo(() => {
    return [...errorsByPI.values()]
      .map((items) => ({
        key: `${items[0].cluster} ${items[0].instructionalArea} ${items[0].performanceIndicator}`,
        title: items[0].performanceIndicator,
        sub: `${clusterLabel(items[0].cluster)} · ${items[0].instructionalArea}`,
        items,
        lastTs: Math.max(...items.map((i) => i.lastMissTs)),
      }))
      .sort((a, b) => b.lastTs - a.lastTs);
  }, [errorsByPI]);

  return (
    <section className="rounded-2xl border-2 border-line bg-paper p-5">
      <div className="mb-1 flex items-center justify-between gap-3">
        <h2 className="font-display text-xl font-bold tracking-tight">Error log</h2>
        <MarkerText rotate={-2} className="text-xs">
          {errorItems.length} miss{errorItems.length === 1 ? "" : "es"}
        </MarkerText>
      </div>
      <p className="mb-4 text-xs text-muted">
        Every question you got wrong — tap “Review now” on any to try it again.
      </p>

      {errorItems.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted">
          No misses in this filter — miss a few and they collect here.
        </p>
      ) : (
        <>
          <div className="mb-4 flex items-center gap-2">
            <span className="marker text-xs uppercase tracking-wide text-muted">Group by</span>
            <div className="flex gap-1.5">
              {(
                [
                  ["pi", "Performance indicator"],
                  ["pattern", "Mistake pattern"],
                ] as [GroupMode, string][]
              ).map(([m, label]) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  aria-pressed={mode === m}
                  className={cn(
                    "sketch-radius border-2 px-3 py-1 text-sm font-medium transition-colors",
                    mode === m
                      ? "border-ink bg-accent text-[var(--on-accent)]"
                      : "border-line bg-paper text-ink/60 hover:bg-paper-2",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Scroll the cards inside the box instead of growing the whole page. */}
          <div className="max-h-[65vh] space-y-6 overflow-y-auto pr-1">
            {mode === "pi"
              ? piSections.map((s) => (
                  <Group key={s.key} title={s.title} sub={s.sub} count={s.items.length}>
                    {s.items.map((item) => (
                      <ErrorCard
                        key={item.questionId}
                        item={item}
                        question={resolved.get(item.questionId)}
                        onReviewNow={onReviewNow}
                      />
                    ))}
                  </Group>
                ))
              : PATTERN_ORDER.filter((p) => errorsByPattern.has(p)).map((p) => {
                  const items = errorsByPattern.get(p)!;
                  return (
                    <Group key={p} title={PATTERN_META[p].label} sub={PATTERN_META[p].blurb} count={items.length}>
                      {items.map((item) => (
                        <ErrorCard
                          key={item.questionId}
                          item={item}
                          question={resolved.get(item.questionId)}
                          onReviewNow={onReviewNow}
                        />
                      ))}
                    </Group>
                  );
                })}
          </div>
        </>
      )}
    </section>
  );
}

function Group({
  title,
  sub,
  count,
  children,
}: {
  title: string;
  sub: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-ink" title={title}>
            {title}
          </h3>
          <p className="truncate text-[0.7rem] text-muted">{sub}</p>
        </div>
        <span className="stat shrink-0 text-xs text-muted">{count}</span>
      </div>
      <ul className="space-y-2.5">{children}</ul>
    </div>
  );
}
