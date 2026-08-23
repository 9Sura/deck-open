"use client";

import * as React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { Segmented } from "@/components/ui/segmented";
import { Loop } from "@/components/loop";
import { MarkerText } from "@/components/marker-text";
import { LiveQuizModal } from "@/components/live-quiz-modal";
import { Sparkle, RisingChart } from "@/components/doodles";
import { CLUSTERS } from "@/lib/data/clusters";
import { LEVELS, type Level } from "@/lib/deca";
import {
  hardShelfDepth,
  sliceAvailable,
  poolDepth,
  MIX_PRESETS,
  DEEP_HARD_SHELF,
  type CandidateSource,
  type MixPreset,
} from "@/lib/question-bank";

const COUNTS = [
  { value: 10, label: "10", sub: "quick" },
  { value: 25, label: "25", sub: "short" },
  { value: 50, label: "50", sub: "half exam" },
];

// Draw from the whole bank, or only the "pool" questions that were never placed
// into a numbered exam set (the extra ~1,588 additions). Lets a user drill just
// those. "sets" is a valid CandidateSource too but isn't surfaced here.
const SOURCES: { value: CandidateSource; label: string; sub: string }[] = [
  { value: "all", label: "Whole bank", sub: "sets + pool" },
  { value: "pool", label: "Pool only", sub: "not in exam sets" },
];

const MIX_ORDER: MixPreset[] = ["exam-real", "balanced", "challenge"];

// "20 / 60 / 20" from a preset's easy/medium/hard weights.
const mixSub = (m: MixPreset) => {
  const w = MIX_PRESETS[m].weights;
  return `${w.easy} / ${w.medium} / ${w.hard}`;
};

/** Challenge needs a deep hard shelf; a 50q Challenge was never authored. */
const isHardHeavy = (mix: MixPreset, count: number) =>
  mix === "challenge" || (mix === "balanced" && count === 50);

export default function TestGeneratorPage() {
  const [cluster, setCluster] = React.useState(CLUSTERS[0].value);
  const [level, setLevel] = React.useState<Level>("District");
  const [count, setCount] = React.useState<number>(25);
  const [mix, setMix] = React.useState<MixPreset>("exam-real");
  const [source, setSource] = React.useState<CandidateSource>("all");
  const [liveOpen, setLiveOpen] = React.useState(false);

  const activeCluster = CLUSTERS.find((c) => c.value === cluster)!;
  const poolCount = poolDepth(cluster, level);
  // Pool-only needs a non-empty pool for the slice; otherwise the usual check.
  const available = source === "pool" ? poolCount > 0 : sliceAvailable(cluster, level);
  // Measure the shelf the draw will actually use, not the combined one — a
  // Pool-only Challenge must warn on the pool's hard count alone.
  const shelf = hardShelfDepth(cluster, level, source);
  const shallowWarning = isHardHeavy(mix, count) && shelf < DEEP_HARD_SHELF;

  // 50q Challenge is dropped (backend plan 07 §6.1) — nobody authored the
  // ~75 hard/slice it would need. Disable Challenge at 50, and fall back to
  // Balanced if the count changes out from under a Challenge selection.
  const challengeDisabled = count === 50;

  function pickCount(next: number) {
    setCount(next);
    if (next === 50 && mix === "challenge") setMix("balanced");
  }

  const mixOptions = MIX_ORDER.map((m) => ({
    value: m,
    label: MIX_PRESETS[m].label,
    sub: mixSub(m),
    disabled: m === "challenge" && challengeDisabled,
  }));

  return (
    <div className="mx-auto max-w-3xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Back
      </Link>

      <div className="mt-4 flex items-start justify-between gap-4">
        <div>
          <MarkerText rotate={-3} className="text-base">
            practice test generator
          </MarkerText>
          <h1 className="mt-1 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
            Build a <Loop color="accent">practice exam</Loop>
          </h1>
        </div>
        <RisingChart className="hidden h-14 w-20 text-ink/70 sm:block" />
      </div>

      {/* ---- Form ---- */}
      <div className="mt-8 rounded-3xl border-2 border-ink bg-paper p-6 shadow-[var(--frame-shadow)] sm:p-8">
        <div className="grid gap-6">
          <Field label="cluster" hint={activeCluster.examName}>
            <Select
              value={cluster}
              onChange={setCluster}
              aria-label="cluster"
              options={CLUSTERS.map((c) => ({ value: c.value, label: c.label }))}
            />
          </Field>

          <Field label="level">
            <Segmented
              value={level}
              onChange={setLevel}
              options={LEVELS.map((l) => ({ value: l.value, label: l.label, sub: l.note }))}
            />
          </Field>

          <Field
            label="questions"
            hint="a focused, one-at-a-time run — jump to any question from the side"
          >
            <Segmented value={count} onChange={pickCount} options={COUNTS} />
          </Field>

          <Field
            label="draw from"
            hint={
              source === "pool"
                ? `only the ${poolCount} pool question${poolCount === 1 ? "" : "s"} not in an exam set`
                : "the full bank — exam sets plus the extra pool"
            }
          >
            <Segmented value={source} onChange={setSource} options={SOURCES} />
          </Field>

          <Field
            label="difficulty mix"
            hint={
              // State the exclusion, not an allow-list: the gate is `count === 50`,
              // so Challenge is available at 10 AND 25. Naming a count that works
              // goes stale the moment COUNTS changes (it already had — this read
              // "25-only" after 10 was added, issue #124).
              challengeDisabled
                ? "Challenge isn't available at 50 — its hard shelf isn't deep enough"
                : "easy / medium / hard blend"
            }
          >
            <Segmented value={mix} onChange={setMix} options={mixOptions} />
          </Field>

          {shallowWarning && (
            <p className="-mt-2 text-sm text-muted">
              <span className="font-semibold text-ink/70">Heads up:</span>{" "}
              {activeCluster.label} · {level}
              {source === "pool" ? " (pool only)" : ""} has a short hard shelf (
              {shelf} hard questions). This preset composes, but New set
              reshuffles a shallow pool — the draw will lean medium.
            </p>
          )}

          <div className="flex items-center gap-4 pt-2">
            <Button
              size="lg"
              variant="primary"
              onClick={() => setLiveOpen(true)}
              disabled={!available}
            >
              Start focus quiz
            </Button>
            <div className="flex items-center gap-2 text-sm text-muted">
              <Sparkle className="h-4 w-4 text-accent" />
              exam-authentic · every PI tagged
            </div>
          </div>

          {!available && (
            <p className="text-sm text-muted">
              {source === "pool"
                ? `${activeCluster.label} · ${level} has no pool questions outside its exam sets — switch "draw from" to Whole bank, or pick another slice.`
                : `${activeCluster.label} · ${level} isn't in the bank yet — pick another level or cluster.`}
            </p>
          )}
        </div>
      </div>

      <LiveQuizModal
        open={liveOpen}
        onClose={() => setLiveOpen(false)}
        cluster={cluster}
        clusterLabel={activeCluster.label}
        level={level}
        mix={mix}
        count={count}
        source={source}
        origin="test-gen"
      />
    </div>
  );
}
