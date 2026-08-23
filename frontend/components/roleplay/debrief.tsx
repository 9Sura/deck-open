// The debrief — a per-PI self-score, and the full text unlocked for re-reading
// (frontend plan 11 §4b/§5a).
//
// EPHEMERAL, DELIBERATELY. Phase C keeps the whole run in React state: nothing
// here is written anywhere, and closing the overlay loses it. `lib/roleplay/
// run-store.ts` is phase D and slots in behind these same props (`scores` +
// `onScore` hoisted into a store) without touching this file. The panel says so
// out loud rather than letting a competitor assume their scores were kept.
//
// The four levels are DECA's own judging scale, which is why self-scoring against
// them costs no new data model (§5a): a competitor who has scored themselves
// "Below Expectations" on a PI has produced the same artefact a judge would.
//
// NOTHING HERE ENTERS /progress (F2 ← backend D7). A roleplay is not an
// `Attempt`; this file imports no `ProgressStore` and no `mastery.ts`, and a
// self-score must never move the readiness number.
//
// And `meta` is not an answer key (F10). There is no model output on this screen
// telling the competitor what the "right" answer was, because nothing in the file
// establishes one — `meta.claimed` is the generator's own self-report and
// `corroborated` only checks that the people it named appear in the prose.

import { Button } from "@/components/ui/button";
import { TapeLabel } from "@/components/tape-label";
import { ExhibitBlock, SituationProse } from "@/components/roleplay/exhibit-block";
import { JudgeQuestions } from "@/components/roleplay/judge-questions";
import { cn } from "@/lib/utils";
import type { Roleplay } from "@/lib/roleplay/types";

/** DECA's four-level judging scale, weakest first. */
export type PiScore = 1 | 2 | 3 | 4;

const SCALE: { value: PiScore; label: string; cls: string }[] = [
  { value: 1, label: "Little / no value", cls: "border-[var(--result-wrong-line)] bg-[var(--result-wrong-bg)] text-[var(--result-wrong-ink)]" },
  { value: 2, label: "Below expectations", cls: "border-[var(--result-skip-line)] bg-[var(--result-skip-bg)] text-[var(--result-skip-ink)]" },
  { value: 3, label: "Meets expectations", cls: "border-[var(--diff-med-line)] bg-[var(--diff-med-bg)] text-[var(--diff-med-ink)]" },
  { value: 4, label: "Exceeds expectations", cls: "border-[var(--result-correct-line)] bg-[var(--result-correct-bg)] text-[var(--result-correct-ink)]" },
];

export function Debrief({
  roleplay,
  scores,
  onScore,
  onRestart,
  className,
}: {
  roleplay: Roleplay;
  /** PI index → self-score. Sparse: an unrated PI is simply absent. */
  scores: Map<number, PiScore>;
  onScore: (index: number, score: PiScore) => void;
  onRestart: () => void;
  className?: string;
}) {
  // `.pi` is the indicator text; each entry also carries the instructional area it
  // was drawn from (backend plan 05 D5), which nothing renders yet. Note the scores
  // below are keyed by INDEX, and the generator now orders PIs core-first, so an
  // index means something different than it did — harmless while run state is
  // ephemeral, but plan 11 phase D persists these, and that tap should key on the
  // indicator, not on its position.
  const pis = roleplay.performanceIndicators.map((entry) => entry.pi);
  const rated = pis.filter((_, i) => scores.has(i)).length;

  return (
    <div className={cn("flex flex-col gap-8", className)}>
      {/* ---- Self-score ---- */}
      <section>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="font-display text-xl font-bold tracking-tight">
            How did you do on each indicator?
          </h3>
          <p className="marker text-sm text-muted">
            {rated} of {pis.length} scored
          </p>
        </div>
        <p className="mt-1.5 text-sm text-ink/70">
          These are the four levels a DECA judge scores you against. Be honest with
          yourself — this is for you, and nobody sees it.
        </p>

        <div className="mt-5 flex flex-col gap-5">
          {pis.map((pi, i) => {
            const current = scores.get(i);
            return (
              <div key={i} className="border-b border-dashed border-line pb-5 last:border-0 last:pb-0">
                <p className="text-[0.95rem] font-semibold leading-snug">{pi}</p>
                <div
                  className="mt-2.5 flex flex-wrap gap-2"
                  role="group"
                  aria-label={`Self-score: ${pi}`}
                >
                  {SCALE.map((step) => {
                    const active = current === step.value;
                    return (
                      <button
                        key={step.value}
                        type="button"
                        onClick={() => onScore(i, step.value)}
                        aria-pressed={active}
                        className={cn(
                          "sketch-radius border-2 px-3 py-1.5 text-sm font-semibold transition-all active:scale-[0.97]",
                          active
                            ? cn(step.cls, "shadow-[2px_2px_0_0_var(--ink)]")
                            : "border-ink/20 bg-paper text-ink/70 hover:-translate-y-0.5 hover:border-ink/40 hover:bg-paper-2",
                        )}
                      >
                        {step.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Say plainly that this is thrown away. Phase D is what makes it stick;
            until then, implying otherwise would be the lie. */}
        <p className="mt-5 border-l-2 border-line pl-3 text-sm text-muted">
          Your scores stay on this screen — they clear when you close the run, and
          nothing from a roleplay is recorded against your progress.
        </p>
      </section>

      {/* ---- Everything unlocked ---- */}
      <section>
        <h3 className="font-display text-xl font-bold tracking-tight">
          The whole scenario
        </h3>
        <p className="mt-1.5 text-sm text-ink/70">
          Re-read it now that you know what you were being asked.
        </p>

        {roleplay.exhibit ? <ExhibitBlock exhibit={roleplay.exhibit} className="mt-4" /> : null}
        <SituationProse situation={roleplay.situation} className="mt-4" />

        {roleplay.judgeCharacterization ? (
          <div className="mt-6">
            <TapeLabel color="support" rotate={-2}>
              the judge
            </TapeLabel>
            <p className="mt-2.5 text-[0.95rem] leading-relaxed text-ink/85">
              {roleplay.judgeCharacterization}
            </p>
          </div>
        ) : null}

        <div className="mt-6">
          <TapeLabel color="accent" rotate={2}>
            what they asked
          </TapeLabel>
          <JudgeQuestions
            questions={roleplay.judgeQuestions}
            revealed={roleplay.judgeQuestions.length}
            className="mt-3"
          />
        </div>
      </section>

      <div>
        <Button variant="outline" onClick={onRestart}>
          ↻ Run it again
        </Button>
      </div>
    </div>
  );
}
