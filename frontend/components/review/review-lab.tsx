"use client";

// The Review Lab shell. Owns the single global filter (cluster × level, matching the
// dashboard's D4 shape), the review-data hook, the resolved bank questions for the Error
// Log cards, and the one <LiveQuizModal/> host that a per-card "Review now" opens into
// with `origin: "review-lab"`.
//
// Reviewing a card writes review-lab attempts → `version` bumps → useReviewData re-reads →
// the Error Log updates, and the same attempts flow into /progress mastery + history.

import * as React from "react";
import Link from "next/link";
import { LiveQuizModal } from "@/components/live-quiz-modal";
import { ErrorLog } from "@/components/review/error-log";
import { useReviewData, type ReviewFilter, type ReviewSet } from "@/hooks/use-review-data";
import { useProgress } from "@/components/progress-provider";
import type { ErrorItem } from "@/lib/progress/errors";
import { bankClusters, type BankQuestion } from "@/lib/question-bank";
import { CLUSTERS } from "@/lib/data/clusters";
import { LEVELS, type Level } from "@/lib/deca";
import { cn } from "@/lib/utils";

const clusterLabel = (v: string): string => CLUSTERS.find((c) => c.value === v)?.label ?? v;

/** Stable empty set for the always-mounted (closed) modal — avoids a new [] each render. */
const EMPTY_SET: BankQuestion[] = [];

export function ReviewLab() {
  const { hydrated } = useProgress();

  const [cluster, setCluster] = React.useState<ReviewFilter["cluster"]>("all");
  const [level, setLevel] = React.useState<ReviewFilter["level"]>("all");
  const filter = React.useMemo<ReviewFilter>(() => ({ cluster, level }), [cluster, level]);

  const { errorItems, errorsByPI, errorsByPattern, resolver, reviewNow, loading } =
    useReviewData(filter);

  // Re-hydrate every error item to its real bank question (async, lint-safe .then).
  const [resolved, setResolved] = React.useState<Map<string, BankQuestion>>(() => new Map());
  React.useEffect(() => {
    if (!hydrated) return;
    let active = true;
    resolver
      .resolve(
        errorItems.map((i) => ({ questionId: i.questionId, cluster: i.cluster, level: i.level })),
      )
      .then((m) => {
        if (active) setResolved(m);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [errorItems, resolver, hydrated]);

  // --- Review-now modal host -------------------------------------------------
  const [queue, setQueue] = React.useState<ReviewSet | null>(null);
  const [modalOpen, setModalOpen] = React.useState(false);
  // `note` is ONLY for messages that fire with the modal CLOSED. Anything that
  // explains the set being answered goes to the modal's `notice` instead — a
  // page-level pill is `z-40` under the modal's `z-50` portal, outside its focus
  // trap and outside its `aria-modal` subtree, so it was painted under the
  // backdrop blur and then surfaced after the quiz was exited (issue #123).
  const [note, setNote] = React.useState<string | null>(null);

  const reviewCard = React.useCallback(
    async (item: ErrorItem) => {
      setNote(null);
      try {
        const set = await reviewNow(item);
        if (set.questions.length === 0) {
          setNote("This question is no longer in the bank — nothing to review.");
          return;
        }
        setQueue(set);
        setModalOpen(true);
      } catch {
        setNote("Couldn't open that review.");
      }
    },
    [reviewNow],
  );

  const closeModal = React.useCallback(() => {
    setModalOpen(false);
    setQueue(null);
  }, []);

  // Session header: a concrete cluster/level when filtered, else derived from the item
  // being reviewed. Attempts self-tag from each question, so the session-row cluster/level
  // is cosmetic only.
  const sessionCluster =
    cluster !== "all" ? cluster : queue?.questions[0]?.cluster ?? "all";
  const sessionLevel: Level =
    level !== "all" ? level : (queue?.questions[0]?.level ?? "District");
  const headerLabel = cluster !== "all" ? clusterLabel(cluster) : "Review session";

  // --- Render ----------------------------------------------------------------
  if (!hydrated || loading) {
    return <ReviewSkeleton />;
  }

  return (
    <div className="mt-8">
      {/* Filter bar (single global filter, mirrors the dashboard) */}
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <Segmented
          label="Cluster"
          value={cluster}
          onChange={setCluster}
          options={[
            { value: "all", label: "All clusters" },
            ...CLUSTERS.filter((c) => bankClusters().includes(c.value)).map((c) => ({
              value: c.value,
              label: c.label,
            })),
          ]}
        />
        <Segmented
          label="Level"
          value={level}
          onChange={(v) => setLevel(v as ReviewFilter["level"])}
          options={[
            { value: "all", label: "All levels" },
            ...LEVELS.map((l) => ({ value: l.value, label: l.label })),
          ]}
        />
        <Link
          href="/progress"
          className="text-sm text-muted underline-offset-4 hover:text-ink hover:underline sm:ml-auto"
        >
          View mastery on /progress →
        </Link>
      </div>

      <div className="mt-6">
        <ErrorLog
          errorItems={errorItems}
          errorsByPI={errorsByPI}
          errorsByPattern={errorsByPattern}
          resolved={resolved}
          onReviewNow={reviewCard}
        />
      </div>

      {note && <StatusPill onDismiss={() => setNote(null)}>{note}</StatusPill>}

      {/* Mounted unconditionally, `open` toggled — the false→true transition is what
          seats the fixed set in useLiveQuiz (mounting already-open renders blank). */}
      <LiveQuizModal
        open={modalOpen}
        onClose={closeModal}
        cluster={sessionCluster}
        clusterLabel={headerLabel}
        level={sessionLevel}
        fixedQuestions={queue?.questions ?? EMPTY_SET}
        notice={
          queue && queue.unresolved > 0
            ? "The original question left the bank — reviewing fresh same-PI questions."
            : undefined
        }
        animate={false}
        origin="review-lab"
      />
    </div>
  );
}

/* ------------------------------------------------------------ filter control */

function Segmented<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="marker text-xs uppercase tracking-wide text-muted">{label}</span>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            aria-pressed={value === o.value}
            className={cn(
              "sketch-radius border-2 px-3 py-1 text-sm font-medium transition-colors",
              value === o.value
                ? "border-ink bg-accent text-[var(--on-accent)]"
                : "border-line bg-paper text-ink/60 hover:bg-paper-2",
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- status pill */

function StatusPill({
  children,
  onDismiss,
}: {
  children: React.ReactNode;
  onDismiss?: () => void;
}) {
  return (
    <div className="fixed inset-x-0 bottom-6 z-40 flex justify-center px-4">
      <div className="sketch-radius flex items-center gap-3 border-2 border-ink bg-paper px-4 py-2 text-sm shadow-lg">
        <span className="text-ink/80">{children}</span>
        {onDismiss && (
          <button onClick={onDismiss} className="text-muted hover:text-ink" aria-label="Dismiss">
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ skeleton */

function ReviewSkeleton() {
  return (
    <div className="mt-10 animate-pulse" aria-hidden>
      <div className="h-64 rounded-2xl border-2 border-line bg-paper-2" />
    </div>
  );
}
