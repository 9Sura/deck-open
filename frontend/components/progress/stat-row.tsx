"use client";

// Headline tiles (plan 08 phase 2 §7.0). Readiness is the hero number; under a
// cluster:"all" filter it shows a "select a cluster" hint instead of a blended
// figure (locked decision — per-cluster readings live in the heatmap). Accuracy
// footnotes its own correct/answered so the percentage is never a bare number
// (§9 honesty); it carries no skip count, because nothing logs a skip (#107).

import * as React from "react";
import { TapeLabel } from "@/components/tape-label";
import type { AccuracySummary, Readiness } from "@/lib/progress/mastery";
import { cn } from "@/lib/utils";

const pct = (v: number) => `${Math.round(v * 100)}%`;

export function StatRow({
  headline,
  clusterLabel,
  attemptsCount,
  accuracy,
  areasCovered,
}: {
  headline: Readiness | null; // null ⇒ cluster:"all"
  clusterLabel: string | null;
  attemptsCount: number;
  accuracy: AccuracySummary;
  areasCovered: { covered: number; total: number };
}) {
  const readinessHasData = headline != null && headline.sampleN > 0;
  const coverageFrac =
    areasCovered.total > 0 ? areasCovered.covered / areasCovered.total : 0;

  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Hero: readiness */}
      <Tile
        hero
        eyebrow="readiness"
        tape={clusterLabel ?? "all clusters"}
        footnote={
          headline == null
            ? "pick a cluster for a single readiness"
            : readinessHasData
            ? `across ${headline.sampleN} attempt${headline.sampleN === 1 ? "" : "s"}`
            : "no attempts in scope yet"
        }
      >
        {headline == null ? (
          <span className="text-2xl font-bold text-ink/40">— select —</span>
        ) : readinessHasData ? (
          <span className="stat text-4xl font-extrabold text-accent-ink">
            {pct(headline.readiness)}
          </span>
        ) : (
          <span className="text-2xl font-bold text-ink/40">no data</span>
        )}
      </Tile>

      <Tile eyebrow="attempts logged" footnote="graded questions answered">
        <span className="stat text-4xl font-extrabold text-ink">{attemptsCount}</span>
      </Tile>

      <Tile
        eyebrow="overall accuracy"
        footnote={
          accuracy.answered > 0
            ? `${accuracy.correct}/${accuracy.answered} correct`
            : "answer some questions to see this"
        }
      >
        {accuracy.answered > 0 ? (
          <span className="stat text-4xl font-extrabold text-ink">
            {pct(accuracy.accuracy)}
          </span>
        ) : (
          <span className="text-2xl font-bold text-ink/40">no data</span>
        )}
      </Tile>

      <Tile
        eyebrow="areas covered"
        footnote={`${areasCovered.total} area${
          areasCovered.total === 1 ? "" : "s"
        } in scope`}
      >
        <span className="stat text-4xl font-extrabold text-ink">
          {pct(coverageFrac)}
        </span>
      </Tile>
    </div>
  );
}

function Tile({
  eyebrow,
  tape,
  footnote,
  hero,
  children,
}: {
  eyebrow: string;
  tape?: string;
  footnote: string;
  hero?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex flex-col rounded-2xl border-2 p-5",
        hero ? "border-ink bg-paper-2" : "border-line bg-paper",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="marker text-xs uppercase tracking-wide text-muted">{eyebrow}</p>
        {tape && (
          <TapeLabel color="support" rotate={3} className="shrink-0">
            {tape}
          </TapeLabel>
        )}
      </div>
      <div className="mt-3">{children}</div>
      <p className="mt-2 text-xs text-muted">{footnote}</p>
    </div>
  );
}
