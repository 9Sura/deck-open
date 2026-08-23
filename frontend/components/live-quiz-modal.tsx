"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { MarkerText } from "@/components/marker-text";
import { TapeLabel } from "@/components/tape-label";
import { Sparkle } from "@/components/doodles";
import { TypewriterQuestion } from "@/components/typewriter-question";
import { useLiveQuiz } from "@/hooks/use-live-quiz";
import { useProgress } from "@/components/progress-provider";
import { NoticeOutlet } from "@/components/notice-layer";
import { toAttempt, type AttemptSource, type Choice } from "@/lib/progress/types";
import { newSessionId } from "@/lib/progress/ids";
import {
  MIX_PRESETS,
  type BankQuestion,
  type CandidateSource,
  type Difficulty,
  type MixPreset,
} from "@/lib/question-bank";
import type { Level } from "@/lib/deca";
import { cn } from "@/lib/utils";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

// Faint difficulty tint on the navigator cells so the mix is legible at a glance.
// Tokenized so the dots stay legible on dark themes (globals.css --diff-*-dot).
const DIFF_DOT: Record<string, string> = {
  easy: "bg-[var(--diff-easy-dot)]",
  medium: "bg-[var(--diff-med-dot)]",
  hard: "bg-[var(--diff-hard-dot)]",
};

/** false on the server, true once mounted — the portal-safe hydration guard. */
function useHydrated(): boolean {
  return React.useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

export function LiveQuizModal({
  open,
  onClose,
  cluster,
  clusterLabel,
  level,
  mix,
  count = 10,
  source = "all",
  origin,
  animate = true,
  fixedQuestions,
  notice,
  onSessionStart,
  initialAnswers,
  resumeSessionId,
  resumeElapsedMs = 0,
}: {
  open: boolean;
  onClose: () => void;
  cluster: string;
  clusterLabel: string;
  level: Level;
  /** Optional in fixed mode — a pre-supplied set has no compose mix. */
  mix?: MixPreset;
  count?: number;
  /** Which slice of the bank to draw from (all / pool / sets). */
  source?: CandidateSource;
  /**
   * Where captured attempts are recorded — a DIFFERENT axis from `source`
   * (which bank slice). `"test-gen"` for the generator, `"focus"` for the
   * question-bank focus quiz.
   */
  origin: AttemptSource;
  /** Typewriter reveal; the question bank passes false for an instant render. */
  animate?: boolean;
  /** Step through this exact set instead of composing a fresh draw. */
  fixedQuestions?: BankQuestion[];
  /**
   * One line explaining THIS set, shown under the header while the quiz is open
   * (e.g. "the question you missed left the bank — here are same-PI ones").
   *
   * It lives INSIDE the dialog on purpose. A host that renders the same sentence
   * as its own page-level pill loses it three times over (issue #123): the
   * portalled overlay is `z-50` and later in the DOM so a `z-40` pill paints
   * under the backdrop blur; the focus trap below makes anything outside the
   * panel un-Tab-able, so a dismiss control can't be reached; and `aria-modal`
   * tells a screen reader to ignore the whole page outside this subtree. Raising
   * the z-index alone fixes only the first of those.
   */
  notice?: React.ReactNode;
  /** Fired once, when this run lazily starts its session — lets a host attribute
   *  the session (and thus its attempts) to whatever launched the quiz. */
  onSessionStart?: (sessionId: string) => void;
  /** Prior answers to restore (by questionId), for resuming a saved quiz. */
  initialAnswers?: Map<string, Choice | null>;
  /** Reuse this existing session id instead of minting a new one, so a resumed
   *  quiz's attempts accumulate in the same session (no double session).
   *
   *  ONLY valid when this sitting re-runs the SAME set and restores its prior
   *  answers via `initialAnswers` — the roll-up writes `answered`/`correct`
   *  ABSOLUTELY from this sitting's counts, and no one re-patches the row's
   *  `total`. Resume a shrinking or unrestored set and you overwrite the earlier
   *  sitting's roll-up and strand `total` (issue #46 — why the dashboard's
   *  fix-misses launcher mints a fresh session per sitting instead). */
  resumeSessionId?: string;
  /** Time already banked in `resumeSessionId` (its recorded `elapsedMs`). The
   *  roll-up below writes a session's TOTAL duration, so a second sitting must
   *  ADD to this rather than replace it. Ignored without `resumeSessionId`. */
  resumeElapsedMs?: number;
}) {
  const quiz = useLiveQuiz({
    cluster,
    level,
    mix,
    count,
    source,
    open,
    fixedQuestions,
    initialAnswers,
  });
  const hydrated = useHydrated();
  const isFixed = fixedQuestions != null;

  const { startSession, recordAttempts, endSession } = useProgress();

  const [finished, setFinished] = React.useState(false);
  const [navSide, setNavSide] = React.useState<"left" | "right">("right");
  const panelRef = React.useRef<HTMLDivElement>(null);
  const restoreFocusRef = React.useRef<HTMLElement | null>(null);

  // In-flight session state. Lazily started on the first answered question and
  // rolled up on finish and released on close — kept in refs so it never
  // triggers a re-render.
  const sessionIdRef = React.useRef<string | null>(null);
  const sessionStartRef = React.useRef(0);
  // Duration already recorded on the session being resumed. `sessionStartRef` is
  // re-stamped at resume, so without this base the second sitting's elapsed time
  // would OVERWRITE the first's instead of adding to it. 0 for a fresh session.
  const priorElapsedRef = React.useRef(0);
  // Latest score-so-far, mirrored to refs so `writeRollUp` reads current counts
  // regardless of the render it was created in. Written from an effect (not
  // render) so it runs before the roll-up effects on the same commit.
  //
  // MIRROR ONLY WHILE OPEN (#41). Closing runs `useLiveQuiz`'s render-phase
  // reset, which empties both the answer map and the question list — so both
  // counts already read 0 on the closing commit, before any effect flushes.
  // This effect is declared ahead of the close effect below, so without the
  // guard it would overwrite a real score with that 0 and the roll-up would
  // persist `answered: 0, correct: 0` for every early-closed session. Skipping
  // the write leaves the refs on the last live counts, which is what the
  // roll-up wants; a reopen re-mirrors on its first commit (0 for a fresh draw,
  // the restored count when resuming), so nothing stale carries over.
  const answeredCountRef = React.useRef(0);
  const correctCountRef = React.useRef(0);
  React.useEffect(() => {
    if (!open) return;
    answeredCountRef.current = quiz.answeredCount;
    correctCountRef.current = quiz.correctCount;
  });

  // Latest "advance one question" action, mirrored to a ref so the Enter key
  // handler (registered once, in the keydown effect below) always calls the
  // current one without re-subscribing every render. Written from an effect, not
  // render — ref writes belong in effects here (same pattern as the counts above).
  const advanceRef = React.useRef<() => void>(() => {});
  React.useEffect(() => {
    advanceRef.current = () => {
      // Only advance an in-progress question; the end screen / loading / error
      // states own their own Enter (their buttons handle it natively).
      if (quiz.status !== "ready" || finished || !quiz.current) return;
      if (quiz.isLast) setFinished(true);
      else quiz.next();
    };
  });

  // `answeredCount` at the last roll-up write, so a repeat write with nothing
  // new to say is skipped. -1 = never written for the current session.
  //
  // Answered is a sufficient dirty key: a locked answer can't be changed
  // (`answerCurrent` returns null on an already-locked question), so `correct`
  // never moves without it. `elapsedMs` does keep moving, and deliberately
  // isn't tracked — the clock has always stopped at the first finish, and
  // sitting on the end screen isn't quizzing.
  const rolledUpAtRef = React.useRef(-1);

  // Patch the open session with an end time + rolled-up totals. Best-effort:
  // capture must never surface an error to the quiz.
  //
  // This does NOT release the session id (see `endRun`). Finishing writes the
  // roll-up so a completed-but-never-closed run is still recorded, but the run
  // is not over: "Review answers" puts you back in the SAME set, and answering
  // a still-blank question there is one more answer in this session, not a new
  // one. Releasing the id here used to mint a second `Session` on that next
  // answer — finalized with the run's ABSOLUTE counts, so the row claimed every
  // locked answer in the run while holding the attempts of only the last
  // sitting (issue #195). `endSession` is an idempotent patch/upsert at every
  // layer (idb-store / supabase-store / syncing-store, which re-reads and
  // re-enqueues the full row), so re-writing the same session is safe.
  const writeRollUp = React.useCallback(() => {
    const id = sessionIdRef.current;
    if (id === null) return;
    if (rolledUpAtRef.current === answeredCountRef.current) return; // nothing new
    rolledUpAtRef.current = answeredCountRef.current;
    void endSession(id, {
      endedTs: Date.now(),
      answered: answeredCountRef.current,
      correct: correctCountRef.current,
      elapsedMs: priorElapsedRef.current + (Date.now() - sessionStartRef.current),
    }).catch(() => {});
  }, [endSession]);

  // The run is over: write the roll-up and release the id, so the next answer
  // starts a genuinely NEW session. Only two things end a run — closing the
  // modal, and "New set" (a fresh draw with its own `total`).
  const endRun = React.useCallback(() => {
    writeRollUp();
    sessionIdRef.current = null;
    rolledUpAtRef.current = -1;
  }, [writeRollUp]);

  // Reset the end-screen whenever the modal (re)opens — render-time adjust, not
  // an effect, so there's no cascading render.
  const [prevOpen, setPrevOpen] = React.useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) setFinished(false);
  }

  // Roll up on finish (so a completed-but-still-open session is fully recorded)
  // WITHOUT ending the run — reviewing and answering a skipped question stays in
  // the same session. End the run on close (abandon = closed with answered <
  // total); on (re)open, clear the in-flight id so the next answer starts a
  // fresh session. Both guard on the session ref, so a finish → close pair
  // writes once (the close is a no-op unless something was answered after the
  // finish, which is exactly the case this split exists for).
  React.useEffect(() => {
    if (finished) writeRollUp();
  }, [finished, writeRollUp]);
  React.useEffect(() => {
    if (open) {
      sessionIdRef.current = null;
      rolledUpAtRef.current = -1;
    } else {
      endRun();
    }
  }, [open, endRun]);

  // Lock a choice for the current question, then persist it: start the
  // session lazily on the first answer, then append one Attempt. Fire-and-forget
  // — a storage failure is swallowed so it can never block answering.
  const handleChoose = React.useCallback(
    (choice: Parameters<typeof quiz.answerCurrent>[0]) => {
      const current = quiz.current;
      if (!current) return;
      const elapsedMs = quiz.answerCurrent(choice);
      if (elapsedMs === null) return; // already locked — no double-record

      if (sessionIdRef.current === null) {
        if (resumeSessionId) {
          // Resume the task's existing session — attempts accumulate in it; no new
          // session row, and no onSessionStart (it's already attributed).
          sessionIdRef.current = resumeSessionId;
          sessionStartRef.current = Date.now();
          priorElapsedRef.current = resumeElapsedMs;
        } else {
          const id = newSessionId();
          sessionIdRef.current = id;
          sessionStartRef.current = Date.now();
          priorElapsedRef.current = 0;
          onSessionStart?.(id);
          void startSession({
            id,
            ts: sessionStartRef.current,
            endedTs: null,
            cluster,
            level,
            source: origin,
            total: quiz.total,
            answered: 0,
            correct: 0,
            elapsedMs: 0,
          }).catch(() => {});
        }
      }

      const attempt = toAttempt(current, choice, elapsedMs, {
        sessionId: sessionIdRef.current,
        source: origin,
      });
      void recordAttempts([attempt]).catch(() => {});
    },
    [
      quiz,
      cluster,
      level,
      origin,
      startSession,
      recordAttempts,
      onSessionStart,
      resumeSessionId,
      resumeElapsedMs,
    ],
  );

  // Lock body scroll + trap focus while open; restore focus to the opener on close.
  React.useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => panelRef.current?.focus());

    const onKeyDown = (e: KeyboardEvent) => {
      // Enter advances to the next question (or finishes on the last one) —
      // "efficient key usage" so you don't reach for the mouse between questions.
      // But interactive controls keep their native Enter: focus on an answer
      // choice selects it, on Prev/Exit/nav clicks it. Only the panel/body (no
      // focused control) advances — which is exactly where focus lands after you
      // pick an answer (the chosen button unmounts into a static row).
      if (e.key === "Enter" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const active = document.activeElement as HTMLElement | null;
        if (active && active.matches(FOCUSABLE)) return; // let the control handle it
        e.preventDefault();
        advanceRef.current();
        return;
      }

      // Esc intentionally does NOT close — focus mode only exits via the Exit
      // button, so a stray keypress can't drop you out of a quiz mid-question.
      if (e.key !== "Tab" || !panelRef.current) return;
      const nodes = panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
      cancelAnimationFrame(raf);
      restoreFocusRef.current?.focus?.();
    };
    // onClose kept in deps for a stable contract even though the effect no longer
    // calls it (Esc close removed) — keeps the dep-array length constant.
  }, [open, onClose]);

  if (!hydrated || !open) return null;

  const {
    status,
    error,
    current,
    index,
    total,
    isFirst,
    isLast,
    visited,
    questions,
    answers,
    answeredCount,
    correctCount,
  } = quiz;
  const mixLabel = mix ? MIX_PRESETS[mix].label : null;

  // Split the navigator into blocks of 50 so a full 100-question set sits as two
  // side-by-side columns (1–50 | 51–100) on desktop instead of one tall strip.
  // ≤50 questions stay a single block, unchanged.
  const NAV_BLOCK = 50;
  const navBlocks: { q: (typeof questions)[number]; i: number }[][] = [];
  for (let start = 0; start < questions.length; start += NAV_BLOCK) {
    navBlocks.push(
      questions.slice(start, start + NAV_BLOCK).map((q, j) => ({ q, i: start + j })),
    );
  }

  const advance = () => {
    if (isLast) setFinished(true);
    else quiz.next();
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 px-4 py-8 backdrop-blur-md sm:py-12"
      role="dialog"
      aria-modal="true"
      aria-label={`${clusterLabel} focus quiz`}
    >
      <div ref={panelRef} tabIndex={-1} className="w-full max-w-4xl outline-none">
        {/* ---- Header: progress + exit ---- */}
        <div className="mb-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <TapeLabel color="support" rotate={-3}>
              {clusterLabel} · {level}
            </TapeLabel>
            {!finished && total > 0 && (
              <span className="stat text-sm font-semibold text-paper/90">
                Question {index + 1} of {total}
              </span>
            )}
          </div>
          {/* No "(Esc)" in the label: the keydown handler deliberately lets Escape
              fall through (see the Tab-trap effect above), so advertising it as a
              shortcut states one the modal does not have — and the accessible name
              is the only place a screen-reader user would hear it. */}
          <Button variant="outline" size="sm" onClick={onClose} aria-label="Exit quiz">
            Exit ✕
          </Button>
        </div>

        {/* ---- Set notice: why THIS set is what it is (issue #123) ---- */}
        {notice && (
          <div
            role="status"
            className="sketch-radius mx-auto mb-4 flex max-w-2xl items-start gap-2 border-2 border-ink bg-paper px-4 py-2 text-sm text-ink/80"
          >
            <span aria-hidden className="text-accent">
              ※
            </span>
            <span>{notice}</span>
          </div>
        )}

        {/* ---- Body ---- */}
        {status === "loading" && (
          <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 rounded-2xl bg-paper py-16 text-center">
            <Sparkle className="h-8 w-8 animate-pulse text-accent" />
            <MarkerText rotate={-2}>composing your set…</MarkerText>
          </div>
        )}

        {status === "error" && (
          <div className="mx-auto max-w-2xl rounded-2xl bg-paper p-8 text-center">
            <p className="text-ink/80">{error}</p>
            <div className="mt-5 flex justify-center gap-3">
              {!isFixed && (
                <Button variant="outline" onClick={quiz.regenerate}>
                  Try again
                </Button>
              )}
              <Button variant="ghost" onClick={onClose}>
                Exit
              </Button>
            </div>
          </div>
        )}

        {status === "ready" && !finished && current && (
          <div className="flex flex-col gap-4 md:flex-row md:items-start">
            {/* Question column */}
            <div className="order-1 min-w-0 flex-1 md:order-2">
              <TypewriterQuestion
                key={current.id}
                q={current}
                index={index}
                animate={animate}
                chosen={answers.get(index) ?? null}
                answered={answers.has(index)}
                onChoose={handleChoose}
                onSkip={advance}
              />
              <div className="mt-5 flex items-center justify-between gap-3">
                <Button
                  variant="ghost"
                  onClick={quiz.prev}
                  disabled={isFirst}
                  className="text-paper hover:bg-paper/10"
                >
                  ← Prev
                </Button>
                {mixLabel ? (
                  <div className="hidden items-center gap-2 text-sm text-paper/80 sm:flex">
                    <Sparkle className="h-4 w-4 text-accent" />
                    {mixLabel} mix
                  </div>
                ) : (
                  <span className="hidden sm:block" />
                )}
                <Button
                  variant="primary"
                  onClick={advance}
                  aria-keyshortcuts="Enter"
                  title={isLast ? "Finish (Enter)" : "Next question (Enter)"}
                >
                  {isLast ? "Finish" : "Next →"}
                </Button>
              </div>
            </div>

            {/* Navigator rail — side is user-togglable (left / right on desktop) */}
            <aside
              className={cn(
                "order-2 rounded-2xl bg-paper p-3 md:shrink-0",
                // One block keeps the slim rail; two-plus blocks widen to sit beside.
                navBlocks.length > 1 ? "md:w-auto" : "md:w-48",
                navSide === "left" ? "md:order-1" : "md:order-3",
              )}
            >
              <div className="mb-2 flex items-center justify-between gap-2 px-1">
                <p className="text-[0.7rem] font-semibold uppercase tracking-wide text-muted">
                  Jump to
                </p>
                <div className="flex gap-1" role="group" aria-label="Panel side">
                  {(["left", "right"] as const).map((side) => (
                    <button
                      key={side}
                      onClick={() => setNavSide(side)}
                      aria-pressed={navSide === side}
                      aria-label={`Move panel to the ${side}`}
                      className={cn(
                        "sketch-radius flex h-6 w-6 items-center justify-center border-2 text-xs leading-none transition-colors",
                        navSide === side
                          ? "border-ink bg-accent text-[var(--on-accent)]"
                          : "border-line bg-paper text-ink/50 hover:bg-paper-2",
                      )}
                    >
                      {side === "left" ? "◧" : "◨"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex flex-col gap-2 md:flex-row md:gap-3">
                {navBlocks.map((block, bi) => (
                  <div
                    key={bi}
                    className="grid grid-cols-8 gap-1.5 sm:grid-cols-10 md:grid-cols-5"
                  >
                    {block.map(({ q, i }) => {
                      const isCurrent = i === index;
                      const seen = visited.has(i);
                      // Answered-state tint so the rail doubles as a score map:
                      // green = correct pick, red = wrong pick. Current always wins
                      // so you can see where you are. These use the --result-* tokens,
                      // NOT the --diff-* ones, so every theme tunes the pair against
                      // its own ground (issue #20). There is no skipped state: moving
                      // past a question leaves it unanswered, so it reads as "seen".
                      const picked = answers.has(i) ? answers.get(i)! : undefined;
                      const isCorrect = picked != null && q.answer === picked;
                      const isWrong = picked != null && q.answer !== picked;
                      const stateCls = isCurrent
                        ? "border-ink bg-accent text-[var(--on-accent)]"
                        : isCorrect
                        ? "border-[var(--result-correct-line)] bg-[var(--result-correct-bg)] text-[var(--result-correct-ink)] hover:opacity-90"
                        : isWrong
                        ? "border-[var(--result-wrong-line)] bg-[var(--result-wrong-bg)] text-[var(--result-wrong-ink)] hover:opacity-90"
                        : seen
                        ? "border-line bg-paper-2 text-ink/70 hover:bg-paper-2/70"
                        : "border-line bg-paper text-ink/45 hover:bg-paper-2";
                      return (
                        <button
                          key={q.id}
                          onClick={() => quiz.goTo(i)}
                          aria-label={`Go to question ${i + 1} (${q.difficulty})${
                            isCorrect
                              ? ", answered correctly"
                              : isWrong
                              ? ", answered incorrectly"
                              : ""
                          }`}
                          aria-current={isCurrent ? "true" : undefined}
                          className={cn(
                            "stat sketch-radius relative flex h-8 items-center justify-center border-2 text-sm font-semibold transition-colors md:w-8",
                            stateCls,
                          )}
                        >
                          {i + 1}
                          <span
                            aria-hidden
                            className={cn(
                              "absolute bottom-0.5 right-0.5 h-1.5 w-1.5 rounded-full",
                              DIFF_DOT[q.difficulty] ?? "bg-line",
                            )}
                          />
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 px-1 text-[0.7rem] text-muted">
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--diff-easy-dot)]" /> easy
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--diff-med-dot)]" /> med
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--diff-hard-dot)]" /> hard
                </span>
              </div>
              {answeredCount > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 border-t border-line px-1 pt-1.5 text-[0.7rem] text-muted">
                  <span className="flex items-center gap-1">
                    <span className="h-2.5 w-2.5 rounded-sm border border-[var(--result-correct-line)] bg-[var(--result-correct-bg)]" />{" "}
                    correct
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2.5 w-2.5 rounded-sm border border-[var(--result-wrong-line)] bg-[var(--result-wrong-bg)]" />{" "}
                    wrong
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="h-2.5 w-2.5 rounded-sm border border-line bg-paper-2" />{" "}
                    seen
                  </span>
                </div>
              )}
            </aside>
          </div>
        )}

        {status === "ready" && finished && (
          <div className="mx-auto max-w-2xl rounded-2xl bg-paper p-8 text-center">
            <TapeLabel color="highlight" rotate={-2}>
              set complete
            </TapeLabel>
            {answeredCount > 0 ? (
              <>
                <h3 className="mt-4 font-display text-4xl font-extrabold tracking-tight">
                  <span className="text-highlight-ink">{correctCount}</span>
                  <span className="text-ink/40"> / {answeredCount}</span>
                </h3>
                <p className="stat mt-1 text-lg font-semibold text-ink/70">
                  {Math.round((correctCount / answeredCount) * 100)}% correct
                </p>
              </>
            ) : (
              <h3 className="mt-4 font-display text-2xl font-bold tracking-tight">
                No questions answered.
              </h3>
            )}
            <p className="mt-2 text-ink/70">
              answered {answeredCount} of {total}
              {" · "}
              {mixLabel ? `${mixLabel} mix · ` : ""}
              {clusterLabel} · {level}
            </p>
            <ScoreMix questions={questions} answers={answers} />
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              {!isFixed && (
                <Button
                  variant="primary"
                  onClick={() => {
                    // A fresh draw is a new sitting with its own `total`, so the
                    // finished set's session has to be closed out first — leave
                    // it open and the new set's attempts would roll up into it
                    // under the old total (issue #195).
                    endRun();
                    quiz.regenerate();
                    setFinished(false);
                  }}
                >
                  New set
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() => {
                  quiz.goTo(0);
                  setFinished(false);
                }}
              >
                Review answers
              </Button>
              <Button variant="ghost" onClick={onClose}>
                Exit
              </Button>
            </div>
          </div>
        )}
        {/* App-wide storage/sync notices (issue #196). Both are raised by WRITES,
            and a write only happens inside a quiz, so this is the surface they
            actually fire on — hosted inside the panel so they paint above the
            backdrop, sit in the `aria-modal` subtree and their Dismiss button is
            reachable by the Tab trap. Distinct from the `notice` prop above,
            which explains the SET this quiz is serving (issue #123). */}
        <NoticeOutlet />
      </div>
    </div>,
    document.body,
  );
}

// Per-difficulty score chips on the end screen — correct / answered within each
// difficulty present in the set. Tokenized so it re-skins per theme.
const SCORE_MIX_STYLE: Record<Difficulty, { label: string; cls: string }> = {
  easy: { label: "Easy", cls: "border-[var(--diff-easy-line)] bg-[var(--diff-easy-bg)] text-[var(--diff-easy-ink)]" },
  medium: { label: "Medium", cls: "border-[var(--diff-med-line)] bg-[var(--diff-med-bg)] text-[var(--diff-med-ink)]" },
  hard: { label: "Hard", cls: "border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] text-[var(--diff-hard-ink)]" },
};

function ScoreMix({
  questions,
  answers,
}: {
  questions: BankQuestion[];
  answers: Map<number, Choice | null>;
}) {
  const order: Difficulty[] = ["easy", "medium", "hard"];
  const stat: Record<Difficulty, { answered: number; correct: number; total: number }> = {
    easy: { answered: 0, correct: 0, total: 0 },
    medium: { answered: 0, correct: 0, total: 0 },
    hard: { answered: 0, correct: 0, total: 0 },
  };
  questions.forEach((q, i) => {
    const s = stat[q.difficulty];
    s.total++;
    if (answers.has(i)) {
      s.answered++;
      const pick = answers.get(i);
      if (pick != null && pick === q.answer) s.correct++;
    }
  });

  const present = order.filter((d) => stat[d].total > 0);
  if (present.length === 0) return null;

  return (
    <div className="mt-4 flex flex-wrap justify-center gap-2">
      {present.map((d) => (
        <span
          key={d}
          className={cn(
            "stat sketch-radius border-2 px-3 py-1 text-xs font-semibold",
            SCORE_MIX_STYLE[d].cls,
          )}
        >
          {SCORE_MIX_STYLE[d].label} {stat[d].correct}/{stat[d].answered}
        </span>
      ))}
    </div>
  );
}
