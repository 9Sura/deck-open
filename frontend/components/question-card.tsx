"use client";

import * as React from "react";
import { Highlight } from "@/components/highlight";
import { cn } from "@/lib/utils";
import type { MockQuestion } from "@/lib/mock";

const LETTERS = ["A", "B", "C", "D"] as const;

type Difficulty = "easy" | "medium" | "hard";

// Traffic-light tones from the --diff-* tokens so the badge re-skins per theme
// (translucent tints + light ink on dark grounds). See globals.css / plan §3.2.
const DIFFICULTY_STYLE: Record<Difficulty, { label: string; cls: string }> = {
  easy: { label: "Easy", cls: "border-[var(--diff-easy-line)] bg-[var(--diff-easy-bg)] text-[var(--diff-easy-ink)]" },
  medium: { label: "Medium", cls: "border-[var(--diff-med-line)] bg-[var(--diff-med-bg)] text-[var(--diff-med-ink)]" },
  hard: { label: "Hard", cls: "border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] text-[var(--diff-hard-ink)]" },
};

function DifficultyBadge({ difficulty }: { difficulty: Difficulty }) {
  const s = DIFFICULTY_STYLE[difficulty];
  return (
    <span
      className={cn(
        "sketch-radius shrink-0 border-2 px-2 py-0.5 text-xs font-semibold",
        s.cls,
      )}
    >
      {s.label}
    </span>
  );
}

export function QuestionCard({
  q,
  index,
}: {
  q: MockQuestion & { difficulty?: Difficulty };
  index: number;
}) {
  const [revealed, setRevealed] = React.useState(false);

  return (
    // A complete, solid border that grows with the content (incl. the revealed
    // explanation) — replaces the hand-drawn SketchFrame, whose open corner read
    // as a gap and whose stretched SVG didn't wrap tall/expanded cards.
    <div className="rounded-3xl border-2 border-ink bg-paper p-6 shadow-[var(--frame-shadow)] sm:p-7">
      <div className="mb-3 flex items-center gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink font-display text-sm font-bold text-paper">
          {index + 1}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <Highlight color="highlight" animate={false} className="text-sm font-medium">
            {q.instructionalArea}
          </Highlight>
          {q.difficulty && <DifficultyBadge difficulty={q.difficulty} />}
        </div>
      </div>

      <p className="text-lg font-medium leading-relaxed">{q.question}</p>

      <ul className="mt-4 space-y-2">
        {LETTERS.map((letter) => {
          const isAnswer = revealed && letter === q.answer;
          return (
            <li
              key={letter}
              className={cn(
                "sketch-radius flex gap-3 border-2 px-4 py-3 text-[0.95rem] transition-colors",
                isAnswer
                  ? "border-highlight bg-highlight/20"
                  : "border-line bg-paper"
              )}
            >
              <span className="font-bold text-ink/70">{letter}.</span>
              <span>{q.options[letter]}</span>
              {isAnswer && (
                <span className="marker ml-auto text-sm text-highlight-ink">correct</span>
              )}
            </li>
          );
        })}
      </ul>

      <div className="mt-5">
        {!revealed ? (
          <button
            onClick={() => setRevealed(true)}
            className="marker text-sm text-support-ink underline underline-offset-4 hover:opacity-80"
          >
            reveal answer &amp; explanation →
          </button>
        ) : (
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
        )}
      </div>
    </div>
  );
}
