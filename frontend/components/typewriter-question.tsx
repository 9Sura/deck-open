"use client";

import * as React from "react";
import { useInView } from "motion/react";
import { Highlight } from "@/components/highlight";
import { usePrefersReducedMotion } from "@/hooks/use-prefers-reduced-motion";
import { cn } from "@/lib/utils";
import type { MockQuestion } from "@/lib/mock";
import type { Choice } from "@/lib/progress/types";

const LETTERS = ["A", "B", "C", "D"] as const;

type Difficulty = "easy" | "medium" | "hard";

// Mirrors the tags on <QuestionCard> so a typed question reads identically to a
// bank one (the whole point of the BankQuestion seam — plan 07-8 §6c). Tokenized
// for dark themes alongside QuestionCard — see globals.css --diff-*.
const DIFFICULTY_STYLE: Record<Difficulty, { label: string; cls: string }> = {
  easy: { label: "Easy", cls: "border-[var(--diff-easy-line)] bg-[var(--diff-easy-bg)] text-[var(--diff-easy-ink)]" },
  medium: { label: "Medium", cls: "border-[var(--diff-med-line)] bg-[var(--diff-med-bg)] text-[var(--diff-med-ink)]" },
  hard: { label: "Hard", cls: "border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] text-[var(--diff-hard-ink)]" },
};

/**
 * Advance a single character cursor from 0 to `total` at ~`cps` chars/sec, driven
 * by requestAnimationFrame so it stays smooth and pauses with the tab. The cursor
 * is a GLOBAL index across the whole question, so the stem types first, then each
 * option, with no per-segment timer juggling. Initial state already reflects the
 * reduced-motion (`enabled=false`) case, so a card that mounts under reduced
 * motion never schedules a frame at all.
 *
 * `enabled` can also flip AFTER mount — it is `animate && !reduced`, and
 * `usePrefersReducedMotion` subscribes to the live media query — so losing it
 * mid-reveal must COMPLETE the reveal, not freeze it (#158). Freezing left
 * `done` false forever, which in graded mode disables all four option buttons
 * and makes the question unanswerable.
 */
function useTypewriterCursor(
  total: number,
  enabled: boolean,
  cps: number,
  active: boolean,
): { cursor: number; done: boolean; skip: () => void } {
  const [cursor, setCursor] = React.useState(enabled ? 0 : total);
  // Once skipped, the rAF loop must STOP — otherwise the next frame recomputes a
  // time-based cursor and clobbers the jump-to-end, so typing appears to resume.
  // Seeded from `!enabled`, but the effect re-syncs it below: seeding alone only
  // ever described the setting AT MOUNT.
  const skippedRef = React.useRef(!enabled);

  React.useEffect(() => {
    if (!active) return;
    // Losing `enabled` is the same outcome as pressing "skip typing" — reveal the
    // rest at once. Setting the ref (rather than only jumping the cursor) is what
    // makes it stick: an in-flight rAF frame would otherwise recompute a
    // time-based cursor on its next tick and re-freeze the reveal part-way.
    if (!enabled) skippedRef.current = true;
    if (skippedRef.current) {
      setCursor(total);
      return;
    }
    let raf = 0;
    let start: number | null = null;
    const tick = (t: number) => {
      if (skippedRef.current) {
        setCursor(total);
        return; // do not reschedule — the skip has completed the reveal
      }
      if (start === null) start = t;
      const n = Math.min(total, Math.floor(((t - start) / 1000) * cps));
      setCursor(n);
      if (n < total) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [total, enabled, cps, active]);

  const skip = React.useCallback(() => {
    skippedRef.current = true;
    setCursor(total);
  }, [total]);

  return { cursor, done: cursor >= total, skip };
}

/** A blinking block caret shown at the current typing position. */
function Caret() {
  return (
    <span className="ml-0.5 inline-block h-[1.1em] w-[0.5ch] translate-y-[0.15em] animate-pulse bg-ink/70 align-middle" />
  );
}

export function TypewriterQuestion({
  q,
  index,
  animate = true,
  startOnView = false,
  chosen,
  answered = false,
  onChoose,
  onSkip,
}: {
  q: MockQuestion & { difficulty?: Difficulty };
  index: number;
  /** Parent can force instant (e.g. a global "skip typing" preference). */
  animate?: boolean;
  /** Start typing only once the card scrolls into view (for long lists). The
   *  modal leaves this false so question 1 types immediately on open. */
  startOnView?: boolean;
  // ---- graded mode (opt-in) ----
  // When `onChoose` is supplied the option list is interactive and the question
  // is graded: picking locks the choice, marks correct/incorrect inline, and
  // reveals the explanation. `!answered` is not-yet-answered. Omit `onChoose` for
  // the reveal-only fallback (the browse/reference path), which is unchanged.
  // `chosen` stays nullable to mirror the stored Attempt, but nothing locks a
  // question without a pick — see `onSkip` below (#107).
  chosen?: Choice | null;
  answered?: boolean;
  onChoose?: (c: Choice | null) => void;
  /**
   * "Skip question" action for graded mode. Skipping is NAVIGATION, not an answer
   * (#107): the control moves on to the next question — it does not lock the
   * question, reveal the answer, or record anything. Omit it and the control is
   * not rendered at all, since there is no second meaning for it to fall back to.
   */
  onSkip?: () => void;
}) {
  const reduced = usePrefersReducedMotion();
  const enabled = animate && !reduced;
  const graded = typeof onChoose === "function";

  // For list usage, hold the animation until the card is on screen so a 25/50
  // set writes itself as you scroll rather than all at once. The modal (single
  // card) passes startOnView=false, so it types right away.
  const rootRef = React.useRef<HTMLDivElement>(null);
  const inView = useInView(rootRef, { once: true, amount: 0.3 });
  const active = startOnView ? inView : true;

  // Flat segments in typing order: stem, then A/B/C/D. Offsets let each element
  // slice its own visible substring from the one global cursor.
  const segments = React.useMemo(() => {
    const parts: { key: string; text: string }[] = [
      { key: "stem", text: q.question },
      ...LETTERS.map((l) => ({ key: l, text: q.options[l] ?? "" })),
    ];
    let acc = 0;
    return parts.map((p) => {
      const start = acc;
      acc += p.text.length;
      return { ...p, start, end: acc };
    });
  }, [q]);
  const total = segments.length ? segments[segments.length - 1].end : 0;

  const { cursor, done, skip } = useTypewriterCursor(total, enabled, 62, active);
  // Reveal-only mode keeps its own local reveal toggle; graded mode reveals
  // implicitly once `answered`.
  const [revealed, setRevealed] = React.useState(false);
  const showExplanation = graded ? answered : revealed;

  const visible = (start: number, text: string) =>
    text.slice(0, Math.max(0, Math.min(text.length, cursor - start)));
  const isTyping = (start: number, end: number) => cursor > start && cursor < end;

  const stem = segments[0];

  return (
    <div ref={rootRef}>
    {/* Complete solid border that grows with the revealed explanation (was a
        hand-drawn SketchFrame whose open corner read as a gap + didn't wrap). */}
    <div
      className="rounded-3xl border-2 border-ink bg-paper p-6 shadow-[var(--frame-shadow)] sm:p-7"
      onClick={!done ? skip : undefined}
      role={!done ? "button" : undefined}
      aria-label={!done ? "Skip typing animation" : undefined}
    >
      <div className="mb-3 flex items-center gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink font-display text-sm font-bold text-paper">
          {index + 1}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <Highlight color="highlight" animate={false} className="text-sm font-medium">
            {q.instructionalArea}
          </Highlight>
          {q.difficulty && (
            <span
              className={cn(
                "sketch-radius shrink-0 border-2 px-2 py-0.5 text-xs font-semibold",
                DIFFICULTY_STYLE[q.difficulty].cls,
              )}
            >
              {DIFFICULTY_STYLE[q.difficulty].label}
            </span>
          )}
        </div>
      </div>

      <p className="min-h-[1.75rem] text-lg font-medium leading-relaxed">
        {visible(stem.start, stem.text)}
        {isTyping(stem.start, stem.end) && <Caret />}
      </p>

      <ul className="mt-4 space-y-2">
        {segments.slice(1).map((seg) => {
          const started = cursor > seg.start;
          const letter = seg.key as Choice;
          // Which tone to paint. Graded (once answered): the real answer is
          // always "correct" and a wrong pick is flagged.
          // Reveal-only: highlight the answer once revealed.
          const isTheAnswer = seg.key === q.answer;
          const isWrongPick =
            graded && answered && chosen === letter && !isTheAnswer;
          const paintCorrect = showExplanation && isTheAnswer;

          const body = (
            <>
              <span className="font-bold text-ink/70">{seg.key}.</span>
              <span>
                {visible(seg.start, seg.text)}
                {isTyping(seg.start, seg.end) && <Caret />}
              </span>
              {paintCorrect && (
                <span className="marker ml-auto text-sm text-highlight-ink">correct</span>
              )}
              {isWrongPick && (
                <span className="marker ml-auto text-sm text-[var(--diff-hard-ink)]">
                  your pick
                </span>
              )}
            </>
          );

          const toneCls = paintCorrect
            ? "border-highlight bg-highlight/20"
            : isWrongPick
            ? "border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] text-[var(--diff-hard-ink)]"
            : "border-line bg-paper";

          // Graded, unanswered, and done typing → interactive button.
          if (graded && !answered) {
            const selectable = done;
            return (
              <li key={seg.key} className={cn(started ? "opacity-100" : "opacity-0")}>
                <button
                  type="button"
                  disabled={!selectable}
                  onClick={() => onChoose?.(letter)}
                  className={cn(
                    "sketch-radius flex w-full gap-3 border-2 px-4 py-3 text-left text-[0.95rem] transition-colors",
                    "border-line bg-paper",
                    selectable
                      ? "cursor-pointer hover:border-ink hover:bg-paper-2"
                      : "cursor-default",
                  )}
                >
                  {body}
                </button>
              </li>
            );
          }

          // Answered (graded) or reveal-only: static, tone-skinned row.
          return (
            <li
              key={seg.key}
              aria-current={paintCorrect ? "true" : undefined}
              className={cn(
                "sketch-radius flex gap-3 border-2 px-4 py-3 text-[0.95rem] transition-colors",
                toneCls,
                started ? "opacity-100" : "opacity-0",
              )}
            >
              {body}
            </li>
          );
        })}
      </ul>

      <div className="mt-5 min-h-[1.5rem]">
        {!done ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              skip();
            }}
            className="marker text-sm text-muted underline underline-offset-4 hover:opacity-80"
          >
            skip typing →
          </button>
        ) : graded ? (
          !answered ? (
            onSkip && (
              <button
                onClick={onSkip}
                className="marker text-sm text-muted underline underline-offset-4 hover:opacity-80"
              >
                Skip question →
              </button>
            )
          ) : (
            <Explanation q={q} />
          )
        ) : !revealed ? (
          <button
            onClick={() => setRevealed(true)}
            className="marker text-sm text-support-ink underline underline-offset-4 hover:opacity-80"
          >
            reveal answer &amp; explanation →
          </button>
        ) : (
          <Explanation q={q} />
        )}
      </div>
    </div>
    </div>
  );
}

/** The reveal block — explanation + PI, shared by graded and reveal-only modes. */
function Explanation({ q }: { q: MockQuestion }) {
  return (
    <div className="rounded-2xl bg-paper-2 p-4">
      <p className="text-[0.8rem] font-semibold uppercase tracking-wide text-muted">
        Explanation
      </p>
      <p className="mt-1 leading-relaxed text-ink/80">{q.explanation}</p>
      <p className="mt-3 text-sm text-muted">
        <span className="font-semibold text-ink/70">PI:</span>{" "}
        {q.performanceIndicator}
      </p>
    </div>
  );
}
