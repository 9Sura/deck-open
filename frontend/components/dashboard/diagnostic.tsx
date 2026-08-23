"use client";

// The diagnostic invite card (plan 09 §3, first-run step ②, D4). Presentational:
// it explains the short mixed diagnostic and offers Start / Skip. The actual quiz
// is hosted by <StudyDashboard/>'s shared LiveQuizModal with origin="diagnostic"
// (so attempts are written source:"diagnostic"); this card just kicks it off and
// reflects the compose state. Skippable → the plan falls back to a soft/
// uncovered-heavy plan until enough practice accrues (§7.2).

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MarkerText } from "@/components/marker-text";
import { TapeLabel } from "@/components/tape-label";
import { Sparkle } from "@/components/doodles";
import { DIAGNOSTIC_SIZE } from "@/lib/progress/diagnostic";

export function Diagnostic({
  clusterLabel,
  level,
  state,
  onStart,
  onSkip,
}: {
  clusterLabel: string;
  level: string;
  state: "idle" | "loading" | "empty";
  onStart: () => void;
  onSkip: () => void;
}) {
  return (
    <Card variant={1} className="mx-auto max-w-xl p-6 text-center sm:p-8">
      <div className="mb-3 flex justify-center">
        <TapeLabel color="accent" rotate={-2}>
          step 2 of 2
        </TapeLabel>
      </div>
      <MarkerText rotate={-2} className="text-base">
        quick diagnostic
      </MarkerText>
      <h2 className="mt-1 font-display text-2xl font-extrabold tracking-tight">
        Take a {DIAGNOSTIC_SIZE}-question check-in
      </h2>
      <p className="mx-auto mt-3 max-w-md text-sm text-ink/70">
        A short mixed set across {clusterLabel} · {level} so your plan starts from
        a real baseline instead of a cold zero. You can skip and just start
        practicing — the plan fills in as you go.
      </p>

      {state === "empty" && (
        <p className="mx-auto mt-4 max-w-md text-sm text-[var(--diff-hard-ink)]">
          No bank questions are available for that target yet — skipping for now.
        </p>
      )}

      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Button
          variant="primary"
          onClick={onStart}
          disabled={state === "loading" || state === "empty"}
        >
          {state === "loading" ? (
            <span className="inline-flex items-center gap-2">
              <Sparkle className="h-4 w-4 animate-pulse" /> composing…
            </span>
          ) : (
            "Start diagnostic"
          )}
        </Button>
        <Button variant="ghost" onClick={onSkip}>
          Skip for now
        </Button>
      </div>
    </Card>
  );
}
