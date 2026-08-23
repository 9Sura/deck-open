"use client";

// The dashboard shell (plan 08 phase 2 §7/§8). Owns the single global filter
// (cluster × level, D4), the memoized mastery roll-ups every module reads, and
// the one <LiveQuizModal/> host that "Practice this" deep-links into (D5).
//
// All derivations are memoized on [attempts/sessions, cluster, level] so the five
// modules don't each re-scan the log per render (§12). The version→re-read wire
// in useProgressData makes a finished drill update the board/heatmap live.

import * as React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { MarkerText } from "@/components/marker-text";
import { LiveQuizModal } from "@/components/live-quiz-modal";
import { StatRow } from "@/components/progress/stat-row";
import { ReadinessTrajectory } from "@/components/progress/readiness-trajectory";
import { MasteryHeatmap } from "@/components/progress/mastery-heatmap";
import { PracticeHistory } from "@/components/progress/practice-history";
import { useProgressData } from "@/hooks/use-progress-data";
import {
  areaMastery,
  areasForClusterWithDrift,
  groupByPI,
  readiness,
  accuracySummary,
  trajectory,
  type AreaMastery,
  type Readiness,
} from "@/lib/progress/mastery";
import {
  noticeForDraw,
  bankClusters,
  loadPIQuestions,
  type BankQuestion,
  type PIDrawKind,
} from "@/lib/question-bank";
import { CLUSTERS } from "@/lib/data/clusters";
import { LEVELS, type Level } from "@/lib/deca";
import { cn } from "@/lib/utils";

type ClusterScope = string | "all";
type LevelScope = Level | "all";

const clusterLabel = (value: string): string =>
  CLUSTERS.find((c) => c.value === value)?.label ?? value;

/** Everything a heatmap row needs: the cluster, its readiness, and its areas. */
export interface HeatRow {
  cluster: string;
  label: string;
  readiness: Readiness;
  areas: AreaMastery[];
}

interface DrillReq {
  cluster: string;
  level: Level;
  pi: string;
  area: string;
}

export function ProgressDashboard() {
  const { attempts, sessions, loading, hydrated } = useProgressData();

  const [cluster, setCluster] = React.useState<ClusterScope>("all");
  const [level, setLevel] = React.useState<LevelScope>("all");

  // --- Practice-this modal host (D5) ---------------------------------------
  const [drill, setDrill] = React.useState<DrillReq | null>(null);
  const [drillState, setDrillState] = React.useState<
    "idle" | "loading" | "ready" | "empty"
  >("idle");
  const [drillQs, setDrillQs] = React.useState<BankQuestion[]>([]);
  const [drillKind, setDrillKind] = React.useState<PIDrawKind>("pi");

  const practicePI = React.useCallback(async (req: DrillReq) => {
    setDrill(req);
    setDrillState("loading");
    setDrillQs([]);
    try {
      const { questions, kind } = await loadPIQuestions(
        req.cluster,
        req.level,
        req.pi,
        10,
        req.area,
      );
      if (questions.length === 0) {
        setDrillKind("none");
        setDrillState("empty");
        return;
      }
      setDrillQs(questions);
      setDrillKind(kind);
      setDrillState("ready");
    } catch {
      setDrillKind("none");
      setDrillState("empty");
    }
  }, []);

  const closeDrill = React.useCallback(() => {
    setDrill(null);
    setDrillState("idle");
    setDrillQs([]);
  }, []);

  // --- Memoized roll-ups (one scan, shared by every module) ----------------
  const filtered = React.useMemo(
    () =>
      attempts.filter(
        (a) =>
          (cluster === "all" || a.cluster === cluster) &&
          (level === "all" || a.level === level),
      ),
    [attempts, cluster, level],
  );

  const byPI = React.useMemo(() => groupByPI(filtered), [filtered]);

  const clustersInScope = React.useMemo(
    () => (cluster === "all" ? bankClusters() : [cluster]),
    [cluster],
  );

  const heat = React.useMemo<HeatRow[]>(
    () =>
      clustersInScope.map((c) => ({
        cluster: c,
        label: clusterLabel(c),
        readiness: readiness(c, level, filtered),
        areas: areasForClusterWithDrift(c, level, byPI).map((area) =>
          areaMastery(c, area, level, byPI),
        ),
      })),
    [clustersInScope, level, filtered, byPI],
  );

  const headline = React.useMemo<Readiness | null>(
    () => (cluster === "all" ? null : readiness(cluster, level, filtered)),
    [cluster, level, filtered],
  );

  const acc = React.useMemo(() => accuracySummary(filtered), [filtered]);

  const traj = React.useMemo(
    () => trajectory(cluster, level, attempts, sessions),
    [cluster, level, attempts, sessions],
  );

  const filteredSessions = React.useMemo(
    () =>
      sessions
        .filter(
          (s) =>
            (cluster === "all" || s.cluster === cluster) &&
            (level === "all" || s.level === level),
        )
        .sort((a, b) => (b.endedTs ?? b.ts) - (a.endedTs ?? a.ts)),
    [sessions, cluster, level],
  );

  // Areas-covered headline: Σ areaCoverage / areaCount across the scope.
  const areasCovered = React.useMemo(() => {
    const all = heat.flatMap((h) => h.areas);
    if (all.length === 0) return { covered: 0, total: 0 };
    const sum = all.reduce((s, a) => s + a.coverage, 0);
    return { covered: sum, total: all.length };
  }, [heat]);

  // --- Render gates --------------------------------------------------------
  if (!hydrated || loading) {
    return <DashboardSkeleton />;
  }

  if (attempts.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="mt-8">
      {/* Filter bar (single global filter — D4) */}
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
          onChange={(v) => setLevel(v as LevelScope)}
          options={[
            { value: "all", label: "All levels" },
            ...LEVELS.map((l) => ({ value: l.value, label: l.label })),
          ]}
        />
      </div>

      <StatRow
        headline={headline}
        clusterLabel={cluster === "all" ? null : clusterLabel(cluster)}
        attemptsCount={filtered.length}
        accuracy={acc}
        areasCovered={areasCovered}
      />

      <div className="mt-8">
        <ReadinessTrajectory
          points={traj}
          cluster={cluster}
          clusterName={cluster === "all" ? null : clusterLabel(cluster)}
        />
      </div>

      <div className="mt-6">
        <MasteryHeatmap
          rows={heat}
          level={level}
          byPI={byPI}
          singleCluster={cluster !== "all"}
          onPractice={practicePI}
        />
      </div>

      <div className="mt-6">
        <PracticeHistory sessions={filteredSessions} attempts={filtered} />
      </div>

      {/* Practice-this status pill + modal host. These two pills only ever render
          with the modal CLOSED, which is the reason they work — anything that has
          to be read WHILE the quiz is open goes to the modal's `notice` prop, not
          here (issue #123: a z-40 pill paints under the z-50 portal, sits outside
          its focus trap, and is hidden from screen readers by `aria-modal`). */}
      {drillState === "loading" && (
        <StatusPill>composing your drill…</StatusPill>
      )}
      {drillState === "empty" && (
        <StatusPill onDismiss={closeDrill}>
          No bank questions available for that one yet.
        </StatusPill>
      )}
      {/* Mounted unconditionally, `open` toggled — the false→true transition is what
          seats the fixed set in useLiveQuiz (mounting already-open renders blank). */}
      <LiveQuizModal
        open={drill !== null && drillState === "ready"}
        onClose={closeDrill}
        cluster={drill?.cluster ?? "all"}
        clusterLabel={drill ? clusterLabel(drill.cluster) : ""}
        level={drill?.level ?? "District"}
        fixedQuestions={drillQs}
        notice={noticeForDraw(drillKind)}
        animate={false}
        origin="focus"
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
          <button
            onClick={onDismiss}
            className="text-muted hover:text-ink"
            aria-label="Dismiss"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------- empty / skeleton */

function EmptyState() {
  return (
    <div className="mt-10 rounded-2xl border-2 border-dashed border-line bg-paper-2 p-10 text-center">
      <MarkerText rotate={-2} className="text-base">
        nothing tracked yet
      </MarkerText>
      <h2 className="mt-3 font-display text-2xl font-bold tracking-tight">
        Answer a few questions and your mastery shows up here
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-ink/70">
        Every graded question you answer — in a focus quiz or a generated test —
        feeds an honest mastery estimate per cluster, area, and performance
        indicator. Start a quiz to seed your dashboard.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Button asChild variant="primary">
          <Link href="/test-generator">Generate a practice test →</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/question-bank">Browse the question bank →</Link>
        </Button>
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="mt-10 animate-pulse space-y-6" aria-hidden>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 rounded-2xl border-2 border-line bg-paper-2" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="h-64 rounded-2xl border-2 border-line bg-paper-2" />
        <div className="h-64 rounded-2xl border-2 border-line bg-paper-2" />
      </div>
      <div className="h-48 rounded-2xl border-2 border-line bg-paper-2" />
    </div>
  );
}
