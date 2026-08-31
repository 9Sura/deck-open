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

// TWO BROWSE MODES, not one drill-down. A numbered set and a pool are different
// kinds of thing — a set is a 100-question test you sit, a pool is an 800–1,000
// question shelf you filter — so hanging the pool off a cluster's set list made
// it read like "Set 3". `?browse=pool` is the whole separation, and it also
// drops a step: a pool has NO set number, so pool mode goes cluster → level →
// browse while sets mode keeps cluster → set → level → study.
type Mode = "sets" | "pool";

const POOL_TOTAL = CLUSTERS.reduce((n, c) => n + poolClusterCount(c.value), 0);

const MODE_BLURB: Record<Mode, string> = {
  sets: "Each set is a full practice exam, banked whole — pick a cluster, then a set, then a level, and sit it or run it as a focus quiz.",
  pool: `The ${fmt(POOL_TOTAL)} questions that were never placed into a numbered exam. Same authoring, far more of it — filter by area, difficulty, or search, then quiz yourself on a random slice of whatever's left.`,
};

export default function QuestionBankPage() {
  // The heading names the mode and the mode comes from ?browse, so the header
  // sits inside the Suspense boundary too (useSearchParams); the prerendered
  // fallback is the default mode's header.
  return (
    <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Back home
      </Link>

      <React.Suspense
        fallback={
          <>
            <PageHeading mode="sets" />
            <div className="mt-8 h-40" />
          </>
        }
      >
        <QuestionBankBrowser />
      </React.Suspense>
    </div>
  );
}

function PageHeading({ mode }: { mode: Mode }) {
  return (
    <div className="mt-4 flex items-start justify-between gap-4">
      <div>
        <MarkerText rotate={-3} className="text-base">
          question bank
        </MarkerText>
        <h1 className="mt-1 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
          Browse the{" "}
          <span className="text-accent-ink">{mode === "pool" ? "pool" : "exam sets"}</span>
        </h1>
      </div>
      <RisingChart className="hidden h-14 w-20 text-ink/70 sm:block" />
    </div>
  );
}

function QuestionBankBrowser() {
  const router = useRouter();
  const params = useSearchParams();

  const mode: Mode = params.get("browse") === "pool" ? "pool" : "sets";

  // Derive the drill-down from the URL, validating each step against the bank so
  // stale/hand-typed params fall back to the nearest valid step. "Valid" is
  // mode-specific: pool mode needs a pool file for the cluster, not a set.
  const rawCluster = params.get("cluster");
  const clusterOk = mode === "pool" ? clusterHasPool : clusterHasBank;
  const cluster = rawCluster && clusterOk(rawCluster) ? rawCluster : null;

  // Only sets mode has a set step; ?set is ignored outright in pool mode.
  const rawSet = mode === "sets" && cluster ? params.get("set") : null;
  const setN =
    cluster && rawSet != null && setsForCluster(cluster).includes(Number(rawSet))
      ? Number(rawSet)
      : null;

  const levelsHere =
    cluster == null
      ? []
      : mode === "pool"
        ? poolLevels(cluster)
        : setN == null
          ? []
          : levelsForSet(cluster, setN);

  const rawLevel = params.get("level") as Level | null;
  const level = rawLevel && levelsHere.includes(rawLevel) ? rawLevel : null;

  // Both modes need a cluster and a level; sets mode needs a set on top of that.
  const atLevelStep = cluster !== null && level === null && (mode === "pool" || setN !== null);
  const atStudyStep = cluster !== null && level !== null && (mode === "pool" || setN !== null);

  const clusterMeta = CLUSTERS.find((c) => c.value === cluster);

  const go = React.useCallback(
    (next: {
      mode?: Mode;
      cluster?: string | null;
      set?: number | null;
      level?: Level | null;
    }) => {
      // Mode is sticky unless a caller changes it, so every crumb and tile stays
      // on the shelf the student is browsing.
      const m = next.mode ?? mode;
      const qs = new URLSearchParams();
      if (m === "pool") qs.set("browse", "pool");
      if (next.cluster) qs.set("cluster", next.cluster);
      if (m === "sets" && next.set != null) qs.set("set", String(next.set));
      if (next.level) qs.set("level", next.level);
      const s = qs.toString();
      router.push(s ? `${PATH}?${s}` : PATH);
    },
    [router, mode],
  );

  return (
    <>
      <PageHeading mode={mode} />

      {/* ---- Which shelf ---- */}
      <div className="mt-7">
        <Segmented<Mode>
          value={mode}
          onChange={(m) => go({ mode: m })}
          options={[
            { value: "sets", label: "Exam sets", sub: "full practice tests" },
            { value: "pool", label: "The pool", sub: `${fmt(POOL_TOTAL)} questions` },
          ]}
        />
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink/70">
          {MODE_BLURB[mode]}
        </p>
      </div>

      {/* ---- Breadcrumb ---- */}
      <div className="mt-6 flex flex-wrap items-center gap-2 text-sm text-muted">
        <Crumb active={cluster === null} onClick={() => go({})}>
          All clusters
        </Crumb>
        {cluster && clusterMeta && (
          <>
            <span aria-hidden>›</span>
            <Crumb
              active={mode === "pool" ? level === null : setN === null}
              onClick={() => go({ cluster })}
            >
              {clusterMeta.label}
            </Crumb>
          </>
        )}
        {mode === "sets" && setN !== null && (
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
              const built = mode === "pool" ? clusterHasPool(c.value) : clusterHasBank(c.value);
              return (
                <TileButton
                  key={c.value}
                  variant={i}
                  fullWidth
                  disabled={!built}
                  onClick={() => go({ cluster: c.value })}
                  tape={
                    !built
                      ? "coming soon"
                      : mode === "pool"
                        ? `${fmt(poolClusterCount(c.value))} Q`
                        : `${setsForCluster(c.value).length} sets`
                  }
                  tapeColor={built ? CARD_TAPE[i % CARD_TAPE.length] : "support"}
                  eyebrow="cluster"
                  title={c.label}
                  sub={
                    built && mode === "pool"
                      ? `${c.examName} · ${poolLevels(c.value).length} levels`
                      : c.examName
                  }
                  body={
                    built
                      ? mode === "pool"
                        ? poolCoverage(c.value)
                        : clusterCoverage(c.value)
                      : mode === "pool"
                        ? "No pool for this cluster yet."
                        : "In development — question sets coming soon."
                  }
                />
              );
            })}
          </div>
        )}

        {/* -------- Step 2 (sets mode only): pick a set -------- */}
        {mode === "sets" && cluster !== null && setN === null && clusterMeta && (
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

        {/* -------- Step 3: pick a level (each set level is an actual test) -------- */}
        {atLevelStep && cluster !== null && (
          <div className="grid gap-6 sm:grid-cols-2">
            {levelsHere.map((lv, i) => {
              const meta =
                mode === "pool" ? poolMeta(cluster, lv) : setMeta(cluster, lv, setN as number);
              return (
                <TileButton
                  key={lv}
                  variant={i}
                  fullWidth
                  onClick={() => go({ cluster, set: setN, level: lv })}
                  tape={meta ? `${fmt(meta.count)} Q` : ""}
                  tapeColor={CARD_TAPE[i % CARD_TAPE.length]}
                  eyebrow={mode === "pool" ? "the pool" : `Set ${setN}`}
                  title={lv}
                  sub={LEVEL_NOTE[lv]}
                  body={meta ? coverageSummary(meta.areaCounts) : undefined}
                />
              );
            })}
          </div>
        )}

        {/* -------- Step 4: study -------- */}
        {atStudyStep && cluster !== null && level !== null && clusterMeta && (
          <div className={cn(mode === "sets" && "mx-auto max-w-3xl")}>
            {mode === "pool" ? (
              <PoolView
                key={`${cluster}-pool-${level}`}
                cluster={cluster}
                clusterLabel={clusterMeta.label}
                level={level}
                onBack={() => go({ cluster })}
              />
            ) : (
              <StudyView
                key={`${cluster}-${setN}-${level}`}
                cluster={cluster}
                clusterLabel={clusterMeta.label}
                level={level}
                setN={setN as number}
                onBack={() => go({ cluster, set: setN })}
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

/**
 * One question against one filter state. `filtered` runs all three axes; the
 * counts shown under a control run every axis EXCEPT its own, so each option
 * previews the result set that picking it actually produces (issue #230).
 */
function poolMatches(
  item: BankQuestion,
  area: string,
  difficulty: Difficulty | typeof ANY,
  needle: string,
): boolean {
  if (area !== ANY && item.instructionalArea !== area) return false;
  if (difficulty !== ANY && item.difficulty !== difficulty) return false;
  if (!needle) return true;
  return (
    item.question.toLowerCase().includes(needle) ||
    item.performanceIndicator.toLowerCase().includes(needle) ||
    Object.values(item.options).some((o) => o.toLowerCase().includes(needle))
  );
}

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

  const needle = query.trim().toLowerCase();

  // Order the areas ONCE, by their whole-pool size, so the list never
  // reshuffles under the cursor as the live counts below move.
  const areaOrder = React.useMemo(() => {
    const total = new Map<string, number>();
    for (const item of questions) {
      total.set(item.instructionalArea, (total.get(item.instructionalArea) ?? 0) + 1);
    }
    return [...total.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([name]) => name);
  }, [questions]);

  // Counted over the loaded pool, not the manifest: the numbers a control
  // advertises have to be the numbers that control yields, which a static
  // whole-pool figure stops being the moment another filter is set.
  const areaOptions = React.useMemo(() => {
    const counts = new Map<string, number>();
    let total = 0;
    for (const item of questions) {
      if (!poolMatches(item, ANY, difficulty, needle)) continue;
      total += 1;
      counts.set(item.instructionalArea, (counts.get(item.instructionalArea) ?? 0) + 1);
    }
    return [
      { value: ANY, label: `All areas (${fmt(total)})` },
      // Every area stays listed even at zero — dropping the selected one out of
      // the list leaves the trigger rendering its placeholder instead.
      ...areaOrder.map((name) => ({
        value: name,
        label: `${name} (${fmt(counts.get(name) ?? 0)})`,
      })),
    ];
  }, [questions, areaOrder, difficulty, needle]);

  const difficultyCounts = React.useMemo(() => {
    const counts: Record<string, number> = { [ANY]: 0, easy: 0, medium: 0, hard: 0 };
    for (const item of questions) {
      if (!poolMatches(item, area, ANY, needle)) continue;
      counts[ANY] += 1;
      counts[item.difficulty] = (counts[item.difficulty] ?? 0) + 1;
    }
    return counts;
  }, [questions, area, needle]);

  const filtered = React.useMemo(
    () => questions.filter((item) => poolMatches(item, area, difficulty, needle)),
    [questions, area, difficulty, needle],
  );

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
            the pool
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
        {/* SWC drops the leading space of a multi-line JSX text node, so the
            space after {level} has to be explicit or the level runs straight
            into "questions" (#229). */}
        These are the {clusterLabel} · {level}{" "}
        questions that were never placed into a numbered exam set — the same
        authoring, just more of it than one 100-question test can hold. Filter
        down to what you&apos;re studying, or quiz yourself on a random{" "}
        {POOL_FOCUS_SIZE} of whatever the filter leaves.
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
                { value: ANY as string, label: "Any", sub: fmt(difficultyCounts[ANY]) },
                ...DIFFICULTIES.map((d) => ({
                  value: d as string,
                  label: d[0].toUpperCase() + d.slice(1),
                  sub: fmt(difficultyCounts[d] ?? 0),
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
