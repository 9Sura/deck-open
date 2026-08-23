"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MarkerText } from "@/components/marker-text";
import { TapeLabel } from "@/components/tape-label";
import { QuestionCard } from "@/components/question-card";
import { LiveQuizModal } from "@/components/live-quiz-modal";
import { Sparkle, RisingChart } from "@/components/doodles";
import { cn } from "@/lib/utils";
import { CLUSTERS } from "@/lib/data/clusters";
import { LEVELS, type Level } from "@/lib/deca";
import {
  clusterHasBank,
  setsForCluster,
  levelsForSet,
  setMeta,
  coverageSummary,
  clusterCoverage,
  setCoverage,
  loadSet,
  type BankQuestion,
} from "@/lib/question-bank";

const PATH = "/question-bank";

const LEVEL_NOTE: Record<Level, string> = Object.fromEntries(
  LEVELS.map((l) => [l.value, l.note]),
) as Record<Level, string>;

const CARD_TAPE = ["support", "accent", "highlight"] as const;

export default function QuestionBankPage() {
  // Header is static; the browser reads ?cluster/&set/&level from the URL, so it
  // needs a Suspense boundary (useSearchParams).
  return (
    <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Back home
      </Link>

      <div className="mt-4 flex items-start justify-between gap-4">
        <div>
          <MarkerText rotate={-3} className="text-base">
            question bank
          </MarkerText>
          <h1 className="mt-1 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
            Browse the <span className="text-accent">exam sets</span>
          </h1>
        </div>
        <RisingChart className="hidden h-14 w-20 text-ink/70 sm:block" />
      </div>

      <React.Suspense fallback={<div className="mt-8 h-40" />}>
        <QuestionBankBrowser />
      </React.Suspense>
    </div>
  );
}

function QuestionBankBrowser() {
  const router = useRouter();
  const params = useSearchParams();

  // Derive the drill-down from the URL, validating each level against the bank so
  // stale/hand-typed params fall back to the nearest valid step.
  const rawCluster = params.get("cluster");
  const cluster = rawCluster && clusterHasBank(rawCluster) ? rawCluster : null;

  const rawSet = cluster ? Number(params.get("set")) : NaN;
  const setN =
    cluster && setsForCluster(cluster).includes(rawSet) ? rawSet : null;

  const rawLevel = params.get("level") as Level | null;
  const level =
    cluster && setN != null && rawLevel && levelsForSet(cluster, setN).includes(rawLevel)
      ? rawLevel
      : null;

  const clusterMeta = CLUSTERS.find((c) => c.value === cluster);

  const go = React.useCallback(
    (next: { cluster?: string | null; set?: number | null; level?: Level | null }) => {
      const qs = new URLSearchParams();
      if (next.cluster) qs.set("cluster", next.cluster);
      if (next.set != null) qs.set("set", String(next.set));
      if (next.level) qs.set("level", next.level);
      const s = qs.toString();
      router.push(s ? `${PATH}?${s}` : PATH);
    },
    [router],
  );

  return (
    <>
      {/* ---- Breadcrumb ---- */}
      <div className="mt-6 flex flex-wrap items-center gap-2 text-sm text-muted">
        <Crumb active={cluster === null} onClick={() => go({})}>
          All clusters
        </Crumb>
        {cluster && clusterMeta && (
          <>
            <span aria-hidden>›</span>
            <Crumb active={setN === null} onClick={() => go({ cluster })}>
              {clusterMeta.label}
            </Crumb>
          </>
        )}
        {setN != null && (
          <>
            <span aria-hidden>›</span>
            <Crumb active={level === null} onClick={() => go({ cluster, set: setN })}>
              Set {setN}
            </Crumb>
          </>
        )}
        {level && (
          <>
            <span aria-hidden>›</span>
            <Crumb active>{level}</Crumb>
          </>
        )}
      </div>

      <div className="mt-8">
        {/* -------- Step 1: pick a cluster -------- */}
        {cluster === null && (
          <div className="grid gap-6 sm:grid-cols-2">
            {CLUSTERS.map((c, i) => {
              const built = clusterHasBank(c.value);
              return (
                <TileButton
                  key={c.value}
                  variant={i}
                  fullWidth
                  disabled={!built}
                  onClick={() => go({ cluster: c.value })}
                  tape={built ? `${setsForCluster(c.value).length} sets` : "coming soon"}
                  tapeColor={built ? CARD_TAPE[i % CARD_TAPE.length] : "support"}
                  eyebrow="cluster"
                  title={c.label}
                  sub={c.examName}
                  body={built ? clusterCoverage(c.value) : "In development — question sets coming soon."}
                />
              );
            })}
          </div>
        )}

        {/* -------- Step 2: pick a set -------- */}
        {cluster !== null && setN === null && clusterMeta && (
          <div className="grid gap-6 sm:grid-cols-2">
            {setsForCluster(cluster).map((n, i) => (
              <TileButton
                key={n}
                variant={i}
                fullWidth
                onClick={() => go({ cluster, set: n })}
                tape={`${levelsForSet(cluster, n).length} levels`}
                tapeColor={CARD_TAPE[i % CARD_TAPE.length]}
                eyebrow={clusterMeta.label}
                title={`Set ${n}`}
                sub="District · Association · ICDC"
                body={setCoverage(cluster, n)}
              />
            ))}
          </div>
        )}

        {/* -------- Step 3: pick a level (each is an actual test) -------- */}
        {cluster !== null && setN !== null && level === null && (
          <div className="grid gap-6 sm:grid-cols-2">
            {levelsForSet(cluster, setN).map((lv, i) => {
              const meta = setMeta(cluster, lv, setN);
              return (
                <TileButton
                  key={lv}
                  variant={i}
                  fullWidth
                  onClick={() => go({ cluster, set: setN, level: lv })}
                  tape={meta ? `${meta.count} Q` : ""}
                  tapeColor={CARD_TAPE[i % CARD_TAPE.length]}
                  eyebrow={`Set ${setN}`}
                  title={lv}
                  sub={LEVEL_NOTE[lv]}
                  body={meta ? coverageSummary(meta.areaCounts) : undefined}
                />
              );
            })}
          </div>
        )}

        {/* -------- Step 4: study the set (kept narrow for readability) -------- */}
        {cluster !== null && setN !== null && level !== null && clusterMeta && (
          <div className="mx-auto max-w-3xl">
            <StudyView
              key={`${cluster}-${setN}-${level}`}
              cluster={cluster}
              clusterLabel={clusterMeta.label}
              level={level}
              setN={setN}
              onBack={() => go({ cluster, set: setN })}
            />
          </div>
        )}
      </div>
    </>
  );
}

/* ------------------------------------------------------------- study view */

function StudyView({
  cluster,
  clusterLabel,
  level,
  setN,
  onBack,
}: {
  cluster: string;
  clusterLabel: string;
  level: Level;
  setN: number;
  onBack: () => void;
}) {
  const [questions, setQuestions] = React.useState<BankQuestion[]>([]);
  const [state, setState] = React.useState<"loading" | "ready" | "error">("loading");
  const [errorMsg, setErrorMsg] = React.useState("");
  const [focusOpen, setFocusOpen] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    loadSet(cluster, level, setN)
      .then(({ questions: qs }) => {
        if (cancelled) return;
        setQuestions(qs);
        setState("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setErrorMsg(err instanceof Error ? err.message : "Couldn't load that set.");
        setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [cluster, level, setN]);

  if (state === "loading") {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <Sparkle className="h-8 w-8 animate-pulse text-accent" />
        <MarkerText rotate={-2}>opening the set…</MarkerText>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="rounded-2xl border-2 border-line bg-paper-2 p-6 text-center">
        <MarkerText rotate={-2}>couldn&apos;t open that set</MarkerText>
        <p className="mt-2 text-sm text-muted">{errorMsg}</p>
        <div className="mt-4">
          <Button variant="outline" onClick={onBack}>
            ← Pick another level
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-2xl font-bold tracking-tight">
          {clusterLabel} · Set {setN} · {level}
        </h2>
        <div className="flex items-center gap-3">
          <Button variant="primary" size="sm" onClick={() => setFocusOpen(true)}>
            Start focus quiz →
          </Button>
          <TapeLabel color="support" rotate={-3}>
            {questions.length}-question set
          </TapeLabel>
        </div>
      </div>

      <div className="space-y-5">
        {questions.map((q, i) => (
          <QuestionCard key={q.id} q={q} index={i} />
        ))}
      </div>

      <div className="mt-8 flex flex-wrap gap-3">
        <Button variant="outline" onClick={onBack}>
          ← Pick another level
        </Button>
        <Button asChild variant="ghost">
          <Link href="/test-generator">Generate a fresh test instead →</Link>
        </Button>
      </div>

      {/* Focus mode — the exact set, one at a time, no typing animation. */}
      <LiveQuizModal
        open={focusOpen}
        onClose={() => setFocusOpen(false)}
        cluster={cluster}
        clusterLabel={clusterLabel}
        level={level}
        fixedQuestions={questions}
        animate={false}
        origin="focus"
      />
    </div>
  );
}

/* --------------------------------------------------------------- pieces */

function TileButton({
  variant,
  disabled,
  fullWidth,
  onClick,
  tape,
  tapeColor,
  eyebrow,
  title,
  sub,
  body,
}: {
  variant: number;
  disabled?: boolean;
  fullWidth?: boolean;
  onClick: () => void;
  tape: string;
  tapeColor: "accent" | "support" | "highlight";
  eyebrow: string;
  title: string;
  sub: string;
  body?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "text-left transition-transform enabled:hover:-translate-y-1 disabled:cursor-not-allowed disabled:opacity-45",
        fullWidth && "w-full",
      )}
    >
      <Card variant={variant} className="flex h-full flex-col p-6 sm:p-7">
        {/* Tape sits in normal flow (top row) so it never overlaps the title. */}
        <div className="mb-2 flex items-start justify-between gap-3">
          <p className="marker text-sm text-muted">{eyebrow}</p>
          {tape && (
            <TapeLabel color={tapeColor} rotate={4} className="shrink-0">
              {tape}
            </TapeLabel>
          )}
        </div>
        <h3 className="font-display text-2xl font-extrabold tracking-tight">{title}</h3>
        <p className="mt-2 text-sm text-ink/70">{sub}</p>
        {body && (
          <p className="mt-3 border-t border-dashed border-line pt-3 text-sm leading-relaxed text-ink/60">
            <span className="marker text-muted">covers · </span>
            {body}
          </p>
        )}
      </Card>
    </button>
  );
}

function Crumb({
  active,
  onClick,
  children,
}: {
  active?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  if (active || !onClick) {
    return <span className="font-semibold text-ink">{children}</span>;
  }
  return (
    <button type="button" onClick={onClick} className="hover:text-ink hover:underline">
      {children}
    </button>
  );
}
