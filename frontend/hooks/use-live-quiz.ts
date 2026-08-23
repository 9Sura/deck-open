"use client";

// The focus-quiz engine (plan 07-8 §6, revised static-first).
//
// Originally spec'd as a one-ahead network prefetch engine calling a live model.
// That path was dropped (the hosted cascade exhausted; a static site has no place
// to run a model per request — see plan §0 UPDATE). This is the honest static
// version: it composes a difficulty-mixed set from the bank up front (instant, $0,
// deployable anywhere) and steps through it one question at a time. "Freshness"
// comes from the bank being enriched offline (pregen_pool.py → synced JSON), not
// from a per-click model call. Every question is a BankQuestion, so the typing
// animation and cards render identically to how live questions would have.

import * as React from "react";
import {
  composeTest,
  BankUnavailableError,
  type BankQuestion,
  type CandidateSource,
  type ComposedTest,
  type MixPreset,
} from "@/lib/question-bank";
import type { Level } from "@/lib/deca";
import type { Choice } from "@/lib/progress/types";

export type LiveQuizStatus = "idle" | "loading" | "ready" | "error";

/** A fresh, truthy 31-bit seed for the compose shuffle. */
const randomSeed = () => Math.floor(Math.random() * 0x7fffffff) || 1;

/** Monotonic-ish clock for per-question timing; falls back off the wall clock. */
const now = () =>
  typeof performance !== "undefined" ? performance.now() : Date.now();

export interface UseLiveQuizArgs {
  cluster: string;
  level: Level;
  /** Optional in fixed mode (a pre-supplied set has no compose mix). */
  mix?: MixPreset;
  count?: number;
  /** Which slice of the bank to draw from (all / pool-only / sets-only). */
  source?: CandidateSource;
  /** Compose only while the modal is open; reset when it closes. */
  open: boolean;
  /**
   * When provided, skip composing and step through this exact set (the
   * question-bank focus mode). Disables `regenerate` — a fixed set can't re-draw.
   */
  fixedQuestions?: BankQuestion[];
  /**
   * Prior answers to restore (by questionId → chosen), for resuming a saved quiz.
   * Only applied in fixed mode; matched to the set by id, then locked so they
   * aren't re-recorded. Navigation resumes at the first still-unanswered question.
   */
  initialAnswers?: Map<string, Choice | null>;
}

export interface LiveQuiz {
  status: LiveQuizStatus;
  error: string | null;
  questions: BankQuestion[];
  meta: ComposedTest | null;
  index: number;
  total: number;
  current: BankQuestion | undefined;
  isFirst: boolean;
  isLast: boolean;
  /** Indices the user has landed on — drives the navigator's visited marks. */
  visited: Set<number>;
  /**
   * Locked answers by question index — unanswered indices are simply absent, so
   * `answers.has(i)` means "locked". The value stays nullable to mirror the stored
   * Attempt, but nothing locks a question without a pick: the quiz's "Skip question"
   * control just moves on and leaves the index absent (#107).
   */
  answers: Map<number, Choice | null>;
  /**
   * Lock the current question to a choice. Immutable after the first set —
   * re-answering is a no-op. Returns the per-question `elapsedMs` it stamped
   * (view→answer time), or `null` when it was a no-op (already locked), so the
   * caller can persist the attempt in one call.
   */
  answerCurrent: (choice: Choice | null) => number | null;
  /** Count of locked questions. */
  answeredCount: number;
  /** Count of locked questions whose pick matched the answer. */
  correctCount: number;
  next: () => void;
  prev: () => void;
  /** Jump straight to a question (clamped to range). */
  goTo: (index: number) => void;
  /** Recompose a different draw of the same settings. */
  regenerate: () => void;
}

export function useLiveQuiz({
  cluster,
  level,
  mix,
  count = 10,
  source = "all",
  open,
  fixedQuestions,
  initialAnswers,
}: UseLiveQuizArgs): LiveQuiz {
  const [status, setStatus] = React.useState<LiveQuizStatus>("idle");
  const [error, setError] = React.useState<string | null>(null);
  const [questions, setQuestions] = React.useState<BankQuestion[]>([]);
  const [meta, setMeta] = React.useState<ComposedTest | null>(null);
  const [index, setIndex] = React.useState(0);
  const [visited, setVisited] = React.useState<Set<number>>(() => new Set([0]));
  // Locked answers (index → chosen letter); an absent index is unanswered.
  const [answers, setAnswers] = React.useState<Map<number, Choice | null>>(
    () => new Map(),
  );
  // When the current question became visible — the baseline for per-question
  // view→answer timing. Written only from an effect (below), never during
  // render, so it stays lint-clean; read in `answerCurrent` (an event handler).
  const viewStartRef = React.useRef<number>(now());
  // Seed the compose RNG with real entropy per mount — a constant start seed made
  // every first draw byte-for-byte identical across reloads and visitors. Lazy
  // init keeps it stable across re-renders; `|| 1` guards the (astronomically
  // unlikely) 0 draw so the seed is always truthy.
  const [nonce, setNonce] = React.useState(randomSeed);

  // A pre-supplied set (question-bank focus mode) short-circuits composing: we key
  // the reset on the set's content so navigation resets when the set changes.
  const fixed = fixedQuestions ?? null;
  const fixedSig = fixed
    ? `fixed:${fixed.length}:${fixed[0]?.id ?? ""}:${fixed[fixed.length - 1]?.id ?? ""}`
    : "";

  // Reseed on each fresh open (compose mode only): the modal stays mounted across
  // close/open, so without this a reopen of the same settings would reuse the same
  // `nonce` and redraw the identical set. Compute the effective seed for this render
  // and fold it into `loadKey` so the reset below keys off the new draw. `effNonce`
  // is committed to state alongside prevOpen — next render `prevOpen` is true, so
  // the transition fires once (no render loop).
  const [prevOpen, setPrevOpen] = React.useState(open);
  const effNonce = open && !prevOpen && !fixed ? randomSeed() : nonce;
  if (open !== prevOpen) setPrevOpen(open);
  if (effNonce !== nonce) setNonce(effNonce);

  // Reset synchronously *during render* whenever the inputs change — the
  // React-blessed "adjust state on prop change" pattern, which (unlike doing it in
  // an effect) doesn't trigger cascading renders. In compose mode the effect below
  // performs the async load; in fixed mode there's nothing to load, so we seat the
  // questions here and the effect early-returns.
  const loadKey = fixed
    ? `${open}|${fixedSig}`
    : `${open}|${cluster}|${level}|${mix}|${count}|${source}|${effNonce}`;
  const [prevKey, setPrevKey] = React.useState(loadKey);
  if (loadKey !== prevKey) {
    setPrevKey(loadKey);
    if (!open) {
      // Closed: clear everything so a later open starts fresh.
      setIndex(0);
      setVisited(new Set([0]));
      setAnswers(new Map());
      setStatus("idle");
      setError(null);
      setQuestions([]);
      setMeta(null);
    } else if (fixed) {
      // Fixed set: seat it, and RESTORE prior answers (resume) by matching ids.
      // Locked answers aren't re-recorded; resume at the first unanswered question.
      const seeded = new Map<number, Choice | null>();
      if (initialAnswers && initialAnswers.size > 0) {
        fixed.forEach((q, i) => {
          if (initialAnswers.has(q.id)) seeded.set(i, initialAnswers.get(q.id) ?? null);
        });
      }
      let start = 0;
      while (start < fixed.length && seeded.has(start)) start++;
      if (start >= fixed.length) start = 0; // all answered → land on the first
      setAnswers(seeded);
      setIndex(fixed.length > 0 ? start : 0);
      setVisited(new Set<number>([start, ...seeded.keys()]));
      setQuestions(fixed);
      setMeta(null);
      setStatus(fixed.length > 0 ? "ready" : "error");
      setError(fixed.length > 0 ? null : "This set has no questions to show.");
    } else {
      // Compose mode: fresh draw; the effect below loads it.
      setIndex(0);
      setVisited(new Set([0]));
      setAnswers(new Map());
      setStatus("loading");
      setError(null);
    }
  }

  React.useEffect(() => {
    if (!open || fixedQuestions) return;
    let active = true;
    composeTest(cluster, level, count, mix ?? "balanced", nonce, source)
      .then((composed) => {
        if (!active) return;
        setQuestions(composed.questions);
        setMeta(composed);
        if (composed.questions.length > 0) {
          setStatus("ready");
        } else {
          setStatus("error");
          setError("No questions could be composed for this selection.");
        }
      })
      .catch((err) => {
        if (!active) return;
        setQuestions([]);
        setMeta(null);
        setStatus("error");
        setError(
          err instanceof BankUnavailableError
            ? err.message
            : "Couldn't assemble this set. Try again in a moment.",
        );
      });
    return () => {
      active = false;
    };
  }, [open, cluster, level, mix, count, source, nonce, fixedQuestions]);

  // Re-stamp the view clock whenever the visible question changes (navigation,
  // a fresh load, or a reset back to index 0). Ref writes belong in effects, not
  // render — post-commit timing is fine for a view→answer measure.
  React.useEffect(() => {
    viewStartRef.current = now();
  }, [index, questions]);

  const total = questions.length;
  const goTo = React.useCallback(
    (target: number) => {
      const clamped = Math.max(0, Math.min(target, Math.max(0, total - 1)));
      setIndex(clamped);
      setVisited((prev) => {
        if (prev.has(clamped)) return prev;
        const nextSet = new Set(prev);
        nextSet.add(clamped);
        return nextSet;
      });
    },
    [total],
  );
  const next = React.useCallback(() => goTo(index + 1), [goTo, index]);
  const prev = React.useCallback(() => goTo(index - 1), [goTo, index]);

  const answerCurrent = React.useCallback(
    (choice: Choice | null): number | null => {
      if (answers.has(index)) return null; // already locked — a no-op
      const elapsedMs = Math.max(0, Math.round(now() - viewStartRef.current));
      setAnswers((prev) => {
        const nextMap = new Map(prev);
        nextMap.set(index, choice);
        return nextMap;
      });
      return elapsedMs;
    },
    [answers, index],
  );
  // A fixed set can't be re-drawn; regenerate is a no-op in that mode.
  const regenerate = React.useCallback(() => {
    if (fixedQuestions) return;
    setNonce((n) => n + 1);
  }, [fixedQuestions]);

  // Derived score-so-far — a pickless lock (null) could never be correct.
  let correctCount = 0;
  for (const [i, choice] of answers) {
    if (choice !== null && questions[i]?.answer === choice) correctCount++;
  }

  return {
    status,
    error,
    questions,
    meta,
    index,
    total,
    current: questions[index],
    isFirst: index === 0,
    isLast: total > 0 && index === total - 1,
    visited,
    answers,
    answerCurrent,
    answeredCount: answers.size,
    correctCount,
    next,
    prev,
    goTo,
    regenerate,
  };
}
