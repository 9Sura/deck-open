"use client";

// Mastery heatmap + PI drill (plan 08 phase 2 §7.2, D6). Per cluster, a wrapping
// grid of instructional-area cells on a SEQUENTIAL single-hue ramp (magnitude);
// provisional cells are hatched and uncovered cells are dashed — "not enough
// data" never masquerades as low or high mastery (redundant encoding: numeral +
// color + texture). Click a cell → a drill panel listing that area's PIs, each
// with a Practice-this deep-link.

import * as React from "react";
import { Button } from "@/components/ui/button";
import { MarkerText } from "@/components/marker-text";
import {
  HATCH_BG,
  MasteryBar,
  MasteryReading,
  masteryTint,
} from "@/components/progress/chart-bits";
import {
  areaPIStats,
  launchLevelForArea,
  type AreaMastery,
  type PIMastery,
} from "@/lib/progress/mastery";
import type { HeatRow } from "@/components/progress/progress-dashboard";
import type { Attempt } from "@/lib/progress/types";
import type { Level } from "@/lib/deca";
import { cn } from "@/lib/utils";

interface Selected {
  cluster: string;
  area: string;
}

export function MasteryHeatmap({
  rows,
  level,
  byPI,
  singleCluster,
  onPractice,
}: {
  rows: HeatRow[];
  level: Level | "all";
  byPI: Map<string, Attempt[]>;
  singleCluster: boolean;
  onPractice: (req: { cluster: string; level: Level; pi: string; area: string }) => void;
}) {
  const [selected, setSelected] = React.useState<Selected | null>(null);

  const toggle = (cluster: string, area: string) =>
    setSelected((s) =>
      s && s.cluster === cluster && s.area === area ? null : { cluster, area },
    );

  const pis = React.useMemo<PIMastery[]>(
    () =>
      selected ? areaPIStats(selected.cluster, selected.area, level, byPI) : [],
    [selected, level, byPI],
  );

  return (
    <section className="rounded-2xl border-2 border-line bg-paper p-5">
      <div className="mb-1 flex items-center justify-between gap-3">
        <h2 className="font-display text-xl font-bold tracking-tight">Mastery by area</h2>
        <MarkerText rotate={-2} className="text-xs">
          click an area to drill in
        </MarkerText>
      </div>
      <RampLegend />

      <div className="mt-4 space-y-6">
        {rows.map((row) => (
          <div key={row.cluster}>
            {!singleCluster && (
              <div className="mb-2 flex items-center gap-2">
                <h3 className="text-sm font-semibold text-ink">{row.label}</h3>
                <span className="stat text-xs text-muted">
                  {row.readiness.sampleN > 0
                    ? `${Math.round(row.readiness.readiness * 100)}% ready`
                    : "no data"}
                </span>
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5">
              {row.areas.map((am) => (
                <AreaCell
                  key={am.area}
                  am={am}
                  active={selected?.cluster === row.cluster && selected?.area === am.area}
                  onClick={() => toggle(row.cluster, am.area)}
                />
              ))}
            </div>

            {/* Inline drill panel, anchored under the owning cluster band. */}
            {selected && selected.cluster === row.cluster && (
              <DrillPanel
                cluster={selected.cluster}
                area={selected.area}
                level={level}
                pis={pis}
                onClose={() => setSelected(null)}
                onPractice={onPractice}
              />
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ cell */

function cellKind(am: AreaMastery): "empty" | "provisional" | "covered" {
  if (am.seenPICount === 0) return "empty";
  if (am.provisional) return "provisional";
  return "covered";
}

function AreaCell({
  am,
  active,
  onClick,
}: {
  am: AreaMastery;
  active: boolean;
  onClick: () => void;
}) {
  const kind = cellKind(am);
  const pct = Math.round(am.mastery * 100);
  const style: React.CSSProperties =
    kind === "covered"
      ? { background: masteryTint(am.mastery) }
      : kind === "provisional"
      ? { background: HATCH_BG }
      : {};

  const label =
    kind === "empty"
      ? `${am.area}: not started, 0 of ${am.piCount} PIs`
      : `${am.area}: ${kind === "provisional" ? "provisional " : ""}${pct}% mastery, ${am.seenPICount} of ${am.piCount} PIs practiced`;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      title={label}
      style={style}
      className={cn(
        "flex min-h-[4.5rem] flex-col justify-between rounded-xl border-2 p-2.5 text-left transition-transform hover:-translate-y-0.5",
        active ? "border-ink ring-2 ring-accent" : "border-line",
        kind === "empty" && "border-dashed",
      )}
    >
      <span
        className={cn(
          "line-clamp-2 text-[0.72rem] font-medium leading-tight text-ink/85",
          kind === "provisional" && "text-ink",
        )}
      >
        {am.area}
      </span>
      <span className="flex items-baseline justify-between gap-1">
        {kind === "empty" ? (
          <span className="stat text-lg font-bold text-ink">—</span>
        ) : (
          // Provisional numerals sit on a solid chip with a spaced, muted ~ so
          // the estimate stays legible over the hatch and the tilde reads as a
          // qualifier rather than crowding the digits.
          <span
            className={cn(
              "stat inline-flex items-baseline gap-0.5 text-lg font-bold leading-none text-ink",
              kind === "provisional" && "rounded-md bg-paper/85 px-1.5 py-0.5",
            )}
          >
            {kind === "provisional" && (
              <span className="text-xs font-semibold text-muted" aria-hidden>
                ~
              </span>
            )}
            {pct}%
          </span>
        )}
        <span className="text-[0.6rem] text-muted">
          {am.seenPICount}/{am.piCount}
        </span>
      </span>
    </button>
  );
}

/* ------------------------------------------------------------ drill panel */

function DrillPanel({
  cluster,
  area,
  level,
  pis,
  onClose,
  onPractice,
}: {
  cluster: string;
  area: string;
  level: Level | "all";
  pis: PIMastery[];
  onClose: () => void;
  onPractice: (req: { cluster: string; level: Level; pi: string; area: string }) => void;
}) {
  return (
    <div className="mt-3 rounded-xl border-2 border-ink bg-paper-2/60 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h4 className="font-display text-base font-bold tracking-tight">
          {area} — {pis.length} indicator{pis.length === 1 ? "" : "s"}
        </h4>
        <button
          onClick={onClose}
          className="text-sm text-muted hover:text-ink"
          aria-label="Close drill"
        >
          Close ✕
        </button>
      </div>
      <ul className="space-y-2">
        {pis.map((pi) => {
          const seen = pi.attempts > 0;
          return (
            <li
              key={pi.pi}
              className="flex flex-col gap-2 rounded-lg border border-line bg-paper p-2.5 sm:flex-row sm:items-center sm:gap-3"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-ink" title={pi.pi}>
                  {pi.pi}
                </p>
                <p className="text-[0.7rem] text-muted">
                  {seen
                    ? `${pi.attempts} attempt${pi.attempts === 1 ? "" : "s"}${
                        pi.provisional ? " · provisional" : ""
                      }`
                    : "not started"}
                </p>
              </div>
              <div className="flex items-center gap-2 sm:w-52">
                <MasteryBar
                  mastery={pi.mastery}
                  provisional={pi.provisional}
                  seen={seen}
                  className="flex-1"
                />
                <MasteryReading
                  mastery={pi.mastery}
                  provisional={pi.provisional}
                  seen={seen}
                />
                <Button
                  size="sm"
                  variant="ghost"
                  className="shrink-0"
                  onClick={() =>
                    onPractice({
                      cluster,
                      level: launchLevelForArea(cluster, area, pi.pi, level),
                      pi: pi.pi,
                      area,
                    })
                  }
                >
                  Practice →
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* --------------------------------------------------------------- legend */

function RampLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[0.7rem] text-muted">
      <span className="flex items-center gap-1.5">
        <span className="marker">mastery</span>
        <span
          className="h-3 w-24 rounded-full border border-line"
          style={{
            background: `linear-gradient(to right, ${masteryTint(0)}, ${masteryTint(1)})`,
          }}
          aria-hidden
        />
        <span>low → high</span>
      </span>
      <span className="flex items-center gap-1.5">
        <span
          className="h-3 w-6 rounded-sm border border-line"
          style={{ background: HATCH_BG }}
          aria-hidden
        />
        provisional (~)
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-3 w-6 rounded-sm border border-dashed border-line" aria-hidden />
        not started (—)
      </span>
    </div>
  );
}
