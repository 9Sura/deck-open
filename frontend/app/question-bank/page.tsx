"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { Select } from "@/components/ui/select";
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
  clusterHasPool,
  setsForCluster,
  levelsForSet,
  setMeta,
  coverageSummary,
  clusterCoverage,
  setCoverage,
  loadSet,
  loadPool,
  poolClusterCount,
  poolCoverage,
  poolLevels,
  poolMeta,
  type BankQuestion,
  type Difficulty,
} from "@/lib/question-bank";

const PATH = "/question-bank";

const LEVEL_NOTE: Record<Level, string> = Object.fromEntries(
  LEVELS.map((l) => [l.value, l.note]),
) as Record<Level, string>;

const CARD_TAPE = ["support", "accent", "highlight"] as const;

// Thousands separators are formatted here rather than with toLocaleString() so a
// server render and a browser render can't disagree and break hydration — the
// same reason BANK_SIZE_LABEL does it by hand (lib/question-bank.ts).
const fmt = (n: number) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");

// The second shelf is addressed with `?set=pool` rather than a set number — a
// pool is a cluster×level collection with no set of its own. Keeping it in the
// same param means one breadcrumb, one back-stack, and one `go()`.
const POOL = "pool" as const;
type SetSel = number | typeof POOL;

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

  const rawSet = cluster ? params.get("set") : null;
  const setSel: SetSel | null = !cluster
    ? null
    : rawSet === POOL && clusterHasPool(cluster)
      ? POOL
      : setsForCluster(cluster).includes(Number(rawSet))
        ? Number(rawSet)
        : null;
  const isPool = setSel === POOL;

  const rawLevel = params.get("level") as Level | null;
  const levelsHere =
    cluster == null || setSel == null
      ? []
      : isPool
        ? poolLevels(cluster)
        : levelsForSet(cluster, setSel as number);
  const level = rawLevel && levelsHere.includes(rawLevel) ? rawLevel : null;

  const clusterMeta = CLUSTERS.find((c) => c.value === cluster);

  const go = React.useCallback(
    (next: { cluster?: string | null; set?: SetSel | null; level?: Level | null }) => {
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
            <Crumb active={setSel === null} onClick={() => go({ cluster })}>
              {clusterMeta.label}
            </Crumb>
          </>
        )}
        {setSel != null && (
          <>
            <span aria-hidden>›</span>
            <Crumb active={level === null} onClick={() => go({ cluster, set: setSel })}>
              {isPool ? "Extra pool" : `Set ${setSel}`}
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
                  // The pool shelf lives one step in, so the cluster tile has to
                  // say it exists — otherwise the landing step still reads as
                  // "this cluster is two exam sets" and the other ~2,700
                  // questions behind it are never discovered.
                  tape={
                    built
                      ? clusterHasPool(c.value)
                        ? `${setsForCluster(c.value).length} sets + pool`
                        : `${setsForCluster(c.value).length} sets`
                      : "coming soon"
                  }
                  tapeColor={built ? CARD_TAPE[i % CARD_TAPE.length] : "support"}
                  eyebrow="cluster"
                  title={c.label}
                  sub={
                    built && clusterHasPool(c.value)
                      ? `${c.examName} · ${fmt(poolClusterCount(c.value))} extra pool questions`
                      : c.examName
                  }
                  body={built ? clusterCoverage(c.value) : "In development — question sets coming soon."}
                />
              );
            })}
          </div>
        )}

        {/* -------- Step 2: pick a set, or the extra pool -------- */}
        {cluster !== null && setSel === null && clusterMeta && (
          <>
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

            {/* The pool is not another exam — it's everything that didn't fit in
                one, so it gets its own labelled shelf rather than a tile that
                reads like "Set 3". */}
            {clusterHasPool(cluster) && (
              <div className="mt-10">
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <MarkerText rotate={-2} className="text-base">
                    beyond the exam sets
                  </MarkerText>
                  <span className="text-sm text-muted">
                    {fmt(poolClusterCount(cluster))} more questions
                  </span>
                </div>
                <div className="mt-4">
                  <TileButton
                    variant={setsForCluster(cluster).length}
                    fullWidth
                    onClick={() => go({ cluster, set: POOL })}
                    tape={`${poolLevels(cluster).length} levels`}
                    tapeColor="highlight"
                    eyebrow={clusterMeta.label}
                    title="Extra pool"
                    sub="Every question that was never placed into a numbered set"
                    body={poolCoverage(cluster)}
                  />
                </div>
              </div>
            )}
          </>
        )}

        {/* -------- Step 3: pick a level (each set level is an actual test) -------- */}
        {cluster !== null && setSel !== null && level === null && (
          <div className="grid gap-6 sm:grid-cols-2">
            {levelsHere.map((lv, i) => {
              const meta = isPool ? poolMeta(cluster, lv) : setMeta(cluster, lv, setSel as number);
              return (
                <TileButton
                  key={lv}
                  variant={i}
                  fullWidth
                  onClick={() => go({ cluster, set: setSel, level: lv })}
                  tape={meta ? `${fmt(meta.count)} Q` : ""}
                  tapeColor={CARD_TAPE[i % CARD_TAPE.length]}
                  eyebrow={isPool ? "Extra pool" : `Set ${setSel}`}
                  title={lv}
                  sub={LEVEL_NOTE[lv]}
                  body={meta ? coverageSummary(meta.areaCounts) : undefined}
                />
              );
            })}
          </div>
        )}

        {/* -------- Step 4: study -------- */}
        {cluster !== null && setSel !== null && level !== null && clusterMeta && (
          <div className={cn(!isPool && "mx-auto max-w-3xl")}>
            {isPool ? (
              <PoolView
                key={`${cluster}-pool-${level}`}
                cluster={cluster}
                clusterLabel={clusterMeta.label}
                level={level}
                onBack={() => go({ cluster, set: POOL })}
              />
            ) : (
              <StudyView
                key={`${cluster}-${setSel}-${level}`}
                cluster={cluster}
                clusterLabel={clusterMeta.label}
                level={level}
                setN={setSel as number}
                onBack={() => go({ cluster, set: setSel })}
              />
            )}
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

  if (state === "loading") return <LoadingBlock label="opening the set…" />;

  if (state === "error") {
    return <ErrorBlock title="couldn't open that set" message={errorMsg} onBack={onBack} />;
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

/* -------------------------------------------------------------- pool view */

// A pool file is 800–1,000 questions, an order of magnitude past a 100-question
// set, so it is browsed rather than read start-to-finish: filter down, then page.
// Rendering all of them as QuestionCards at once is what makes the tab hang.
const POOL_PAGE_SIZE = 20;

/** A focus quiz over a pool is a SAMPLE of the filter, not the filter itself. */
const POOL_FOCUS_SIZE = 20;

const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard"];
const ANY = "any";

function PoolView({
  cluster,
  clusterLabel,
  level,
  onBack,
}: {
  cluster: string;
  clusterLabel: string;
  level: Level;
  onBack: () => void;
}) {
  const [questions, setQuestions] = React.useState<BankQuestion[]>([]);
  const [state, setState] = React.useState<"loading" | "ready" | "error">("loading");
  const [errorMsg, setErrorMsg] = React.useState("");

  const [area, setArea] = React.useState<string>(ANY);
  const [difficulty, setDifficulty] = React.useState<Difficulty | typeof ANY>(ANY);
  const [query, setQuery] = React.useState("");
  const [page, setPage] = React.useState(0);

  // The focus quiz steps a frozen sample. Drawn once per launch and held in
  // state, so re-renders (paging behind the modal) can't reshuffle mid-quiz.
  const [focusSet, setFocusSet] = React.useState<BankQuestion[] | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    loadPool(cluster, level)
      .then(({ questions: qs }) => {
        if (cancelled) return;
        setQuestions(qs);
        setState("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setErrorMsg(err instanceof Error ? err.message : "Couldn't load that pool.");
        setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [cluster, level]);

  const meta = poolMeta(cluster, level);

  const areaOptions = React.useMemo(() => {
    const counts = meta?.areaCounts ?? {};
    return [
      { value: ANY, label: "All areas" },
      ...Object.entries(counts)
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .map(([name, n]) => ({ value: name, label: `${name} (${n})` })),
    ];
  }, [meta]);

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return questions.filter((item) => {
      if (area !== ANY && item.instructionalArea !== area) return false;
      if (difficulty !== ANY && item.difficulty !== difficulty) return false;
      if (!q) return true;
      return (
        item.question.toLowerCase().includes(q) ||
        item.performanceIndicator.toLowerCase().includes(q) ||
        Object.values(item.options).some((o) => o.toLowerCase().includes(q))
      );
    });
  }, [questions, area, difficulty, query]);

  // Filters shrink the list under the cursor, so clamp rather than reset — a
  // page index left past the end renders an empty list with a live "Next".
  const pageCount = Math.max(1, Math.ceil(filtered.length / POOL_PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const start = safePage * POOL_PAGE_SIZE;
  const visible = filtered.slice(start, start + POOL_PAGE_SIZE);

  const startFocus = () => {
    const pick = filtered.slice();
    for (let i = pick.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [pick[i], pick[j]] = [pick[j], pick[i]];
    }
    setFocusSet(pick.slice(0, POOL_FOCUS_SIZE));
  };

  if (state === "loading") return <LoadingBlock label="opening the pool…" />;

  if (state === "error") {
    return <ErrorBlock title="couldn't open that pool" message={errorMsg} onBack={onBack} />;
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <MarkerText rotate={-2} className="text-sm">
            extra pool
          </MarkerText>
          <h2 className="font-display text-2xl font-bold tracking-tight">
            {clusterLabel} · {level}
          </h2>
        </div>
        <TapeLabel color="highlight" rotate={-3}>
          {fmt(questions.length)} questions
        </TapeLabel>
      </div>

      <p className="mb-6 max-w-2xl text-sm leading-relaxed text-ink/70">
        These are the {clusterLabel} · {level} questions that were never placed into a
        numbered exam set — the same authoring, just more of it than one 100-question
        test can hold. Filter down to what you&apos;re studying, or quiz yourself on a
        random {POOL_FOCUS_SIZE} of whatever the filter leaves.
      </p>

      <div className="rounded-3xl border-2 border-line bg-paper-2 p-5 sm:p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="instructional area">
            <Select
              value={area}
              onChange={(v) => {
                setArea(v);
                setPage(0);
              }}
              options={areaOptions}
              aria-label="Filter by instructional area"
            />
          </Field>
          <Field label="search">
            <input
              type="search"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(0);
              }}
              placeholder="Question text, PI, or an answer choice…"
              className="hand-border h-12 w-full min-w-0 bg-paper px-4 text-[0.95rem] text-ink outline-none transition-colors placeholder:text-muted focus-visible:ring-2 focus-visible:ring-support/50"
            />
          </Field>
        </div>

        <div className="mt-4">
          <Field label="difficulty">
            <Segmented<string>
              value={difficulty}
              onChange={(v) => {
                setDifficulty(v as Difficulty | typeof ANY);
                setPage(0);
              }}
              options={[
                { value: ANY as string, label: "Any", sub: fmt(questions.length) },
                ...DIFFICULTIES.map((d) => ({
                  value: d as string,
                  label: d[0].toUpperCase() + d.slice(1),
                  sub: String(meta?.difficultyCounts?.[d] ?? 0),
                })),
              ]}
            />
          </Field>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          {fmt(filtered.length)} match
          {filtered.length === 1 ? "" : "es"}
          {filtered.length > 0 && (
            <>
              {" · showing "}
              {fmt(start + 1)}–{fmt(Math.min(start + POOL_PAGE_SIZE, filtered.length))}
            </>
          )}
        </p>
        <Button
          variant="primary"
          size="sm"
          disabled={filtered.length === 0}
          onClick={startFocus}
        >
          Quiz me on {Math.min(POOL_FOCUS_SIZE, filtered.length)} of these →
        </Button>
      </div>

      {filtered.length === 0 ? (
        <div className="mt-6 rounded-2xl border-2 border-dashed border-line p-8 text-center">
          <MarkerText rotate={-2}>nothing matches that</MarkerText>
          <p className="mt-2 text-sm text-muted">
            Widen the area, difficulty, or search and the pool comes back.
          </p>
        </div>
      ) : (
        <div className="mt-6 space-y-5">
          {visible.map((q, i) => (
            <QuestionCard key={q.id} q={q} index={start + i} />
          ))}
        </div>
      )}

      {pageCount > 1 && (
        <div className="mt-8 flex items-center justify-center gap-4">
          <Button
            variant="outline"
            size="sm"
            disabled={safePage === 0}
            onClick={() => setPage(safePage - 1)}
          >
            ← Previous
          </Button>
          <span className="text-sm text-muted">
            Page {fmt(safePage + 1)} of {fmt(pageCount)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={safePage >= pageCount - 1}
            onClick={() => setPage(safePage + 1)}
          >
            Next →
          </Button>
        </div>
      )}

      <div className="mt-8 flex flex-wrap gap-3">
        <Button variant="outline" onClick={onBack}>
          ← Pick another level
        </Button>
        <Button asChild variant="ghost">
          <Link href="/test-generator">Generate a fresh test instead →</Link>
        </Button>
      </div>

      <LiveQuizModal
        open={focusSet !== null}
        onClose={() => setFocusSet(null)}
        cluster={cluster}
        clusterLabel={clusterLabel}
        level={level}
        fixedQuestions={focusSet ?? []}
        animate={false}
        origin="focus"
      />
    </div>
  );
}

/* --------------------------------------------------------------- pieces */

function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <Sparkle className="h-8 w-8 animate-pulse text-accent" />
      <MarkerText rotate={-2}>{label}</MarkerText>
    </div>
  );
}

function ErrorBlock({
  title,
  message,
  onBack,
}: {
  title: string;
  message: string;
  onBack: () => void;
}) {
  return (
    <div className="rounded-2xl border-2 border-line bg-paper-2 p-6 text-center">
      <MarkerText rotate={-2}>{title}</MarkerText>
      <p className="mt-2 text-sm text-muted">{message}</p>
      <div className="mt-4">
        <Button variant="outline" onClick={onBack}>
          ← Pick another level
        </Button>
      </div>
    </div>
  );
}

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
