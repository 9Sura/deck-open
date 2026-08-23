"use client";

// The Review Lab's data hook. Wraps useProgressData() (which loads the whole log once
// + re-reads on `version`), owns the single QuestionResolver instance for the tab, and
// derives — purely, memoized — the Error Log (missed questions grouped by PI / pattern),
// plus a per-card "Review now" mini-session builder.
//
// Recomputed on load + on every write (`version` → the underlying read re-runs →
// attempts change → these memos recompute), never persisted. The spaced-review
// scheduler was removed; reviewing is now per-card only.

import * as React from "react";
import { useProgressData } from "@/hooks/use-progress-data";
import { errorLog, type ErrorItem, type MistakePattern } from "@/lib/progress/errors";
import { createResolver, type QuestionResolver } from "@/lib/progress/resolver";
import { loadPIQuestions, type BankQuestion } from "@/lib/question-bank";
import type { Level } from "@/lib/deca";

export interface ReviewFilter {
  cluster: string | "all";
  level: Level | "all";
}

/** A per-card review mini-session: the missed question + a few fresh same-PI items. */
export interface ReviewSet {
  questions: BankQuestion[];
  unresolved: number; // 1 when the missed question is no longer in the bank
}

export interface ReviewData {
  errorItems: ErrorItem[]; // filtered, newest-miss first
  errorsByPI: Map<string, ErrorItem[]>;
  errorsByPattern: Map<MistakePattern, ErrorItem[]>;
  resolver: QuestionResolver;
  /** Mini-session for one Error Log card: that question + a few fresh same-PI. */
  reviewNow: (item: ErrorItem) => Promise<ReviewSet>;
  loading: boolean;
  hydrated: boolean;
}

/** Fresh same-PI items to pad a single-card "Review now" so it isn't a one-question quiz. */
const REVIEW_NOW_FRESH = 4;

export function useReviewData(filter: ReviewFilter): ReviewData {
  const { attempts, loading, hydrated } = useProgressData();

  // One resolver per tab (literal initializer runs once — stable ref, no module const).
  const [resolver] = React.useState<QuestionResolver>(() => createResolver());

  const scoped = React.useMemo(
    () =>
      attempts.filter(
        (a) =>
          (filter.cluster === "all" || a.cluster === filter.cluster) &&
          (filter.level === "all" || a.level === filter.level),
      ),
    [attempts, filter.cluster, filter.level],
  );

  // Only OPEN misses: a question answered correctly since its last miss (`resolved`) is a
  // completed review and drops off the log. Finishing a review bumps `version` → re-read →
  // the just-corrected item is now resolved → it disappears here.
  const errorItems = React.useMemo(
    () => errorLog(scoped).filter((i) => !i.resolved),
    [scoped],
  );
  const byPI = React.useMemo(() => {
    const m = new Map<string, ErrorItem[]>();
    for (const it of errorItems) {
      const k = `${it.cluster} ${it.instructionalArea} ${it.performanceIndicator}`;
      const list = m.get(k);
      if (list) list.push(it);
      else m.set(k, [it]);
    }
    return m;
  }, [errorItems]);
  const byPattern = React.useMemo(() => {
    const m = new Map<MistakePattern, ErrorItem[]>();
    for (const it of errorItems) {
      const list = m.get(it.latestPattern);
      if (list) list.push(it);
      else m.set(it.latestPattern, [it]);
    }
    return m;
  }, [errorItems]);

  const reviewNow = React.useCallback(
    async (item: ErrorItem): Promise<ReviewSet> => {
      const resolved = await resolver.resolve([
        { questionId: item.questionId, cluster: item.cluster, level: item.level },
      ]);
      const base = resolved.get(item.questionId);

      const questions: BankQuestion[] = [];
      const queuedIds = new Set<string>();
      if (base) {
        questions.push(base);
        queuedIds.add(base.id);
      }

      // A few fresh same-PI items so a single-card review is a real mini-session.
      try {
        const { questions: fresh } = await loadPIQuestions(
          item.cluster,
          item.level as Level,
          item.performanceIndicator,
          REVIEW_NOW_FRESH + 1,
          item.instructionalArea,
        );
        for (const q of fresh) {
          if (questions.length >= REVIEW_NOW_FRESH + 1) break;
          if (queuedIds.has(q.id)) continue;
          queuedIds.add(q.id);
          questions.push(q);
        }
      } catch {
        // No fresh items available — the single question (if resolved) still reviews.
      }

      return { questions, unresolved: base ? 0 : 1 };
    },
    [resolver],
  );

  return {
    errorItems,
    errorsByPI: byPI,
    errorsByPattern: byPattern,
    resolver,
    reviewNow,
    loading,
    hydrated,
  };
}
