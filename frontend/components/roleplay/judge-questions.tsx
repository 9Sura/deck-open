// The judge's questions, revealed ONE AT A TIME (frontend plan 11 §4b).
//
// This is the mechanism the whole run surface exists for. A roleplay you can read
// end-to-end in one scroll is a document; a roleplay whose questions arrive after
// you have committed to an answer is a rehearsal. So this component is
// CONTROLLED — it renders `questions.slice(0, revealed)` and nothing more, and
// the run surface keeps `revealed` at 0 for the whole of Prep.
//
// Hiding with CSS would not do: an unrevealed question must not be in the DOM at
// all, or a curious competitor reads it out of the inspector (and a screen reader
// reads it out loud) before they have answered the previous one.
//
// The count is NEVER hardcoded. Every committed fixture happens to carry exactly
// three (K6's floor is 3), but the floor is a floor — a later batch may carry
// more, and "1 of 3" baked into a string would quietly start lying.

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function JudgeQuestions({
  questions,
  revealed,
  onReveal,
  className,
}: {
  questions: string[];
  /** How many are on screen. The rest are not rendered — see the header note. */
  revealed: number;
  /** Omitted in the debrief, where everything is already unlocked. */
  onReveal?: () => void;
  className?: string;
}) {
  const total = questions.length;
  const shown = Math.max(0, Math.min(revealed, total));
  const more = shown < total;

  if (total === 0) {
    return (
      <p className={cn("text-sm text-muted", className)}>
        This scenario didn&rsquo;t come with judge questions.
      </p>
    );
  }

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      {/* Politely announced so a screen-reader user hears each question as it
          arrives, rather than having to go hunting for what changed. */}
      <ol className="flex flex-col gap-3" aria-live="polite">
        {questions.slice(0, shown).map((q, i) => (
          <li
            key={i}
            className="sketch-radius border-2 border-ink bg-paper-2 p-4 text-[0.95rem] leading-relaxed"
          >
            <span className="marker mr-2 text-sm text-muted">
              Question {i + 1} of {total}
            </span>
            <span className="mt-1 block text-ink/90">{q}</span>
          </li>
        ))}
      </ol>

      {more && onReveal ? (
        <div>
          <Button variant="outline" size="sm" onClick={onReveal}>
            {shown === 0
              ? total === 1
                ? "The judge asks their question →"
                : "The judge asks their first question →"
              : `Next question (${shown + 1} of ${total}) →`}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
