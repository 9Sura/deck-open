"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, ChevronLeft, ChevronRight, RotateCcw, Shuffle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Highlight } from "@/components/highlight";
import { MarkerText } from "@/components/marker-text";
import { TapeLabel } from "@/components/tape-label";
import { Segmented } from "@/components/ui/segmented";
import { Select } from "@/components/ui/select";
import { StickyNote, Sparkle } from "@/components/doodles";
import { cn } from "@/lib/utils";
import { CLUSTERS } from "@/lib/data/clusters";
import { FORMAT_LABEL } from "@/lib/deca";
import {
  clusterHasVocab,
  clusterTagSummary,
  eventsForCluster,
  formatTag,
  loadVocabEvent,
  vocabEventMeta,
  type VocabDifficulty,
  type VocabTerm,
} from "@/lib/vocab";

const PATH = "/vocab";
const CARD_TAPE = ["support", "accent", "highlight"] as const;

/**
 * The vocab difficulty badge is deliberately NOT the one in components/question-card.tsx.
 * That badge's local `Difficulty` type is `"easy" | "medium" | "hard"`, and reusing it would
 * make the purged easy tier expressible again — the thing vocab plan 01 §3/§7 require be
 * unrepresentable, and the whole reason `VocabDifficulty` is its own union. What the two
 * badges share is the `--diff-*` token set in globals.css, so both re-skin per theme.
 */
const DIFFICULTY_STYLE: Record<VocabDifficulty, { label: string; cls: string }> = {
  medium: {
    label: "Medium",
    cls: "border-[var(--diff-med-line)] bg-[var(--diff-med-bg)] text-[var(--diff-med-ink)]",
  },
  hard: {
    label: "Hard",
    cls: "border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] text-[var(--diff-hard-ink)]",
  },
};

/** "All areas" and "the cards with no area at all" — see AREA_EVENT below. */
const AREA_ALL = "all";
/**
 * The event-flavor cards. 723 of the 7,000 deck rows carry no tag: `seed-vocab.mjs` sets
 * `tags: t.areas ?? []` for flavor terms, and only 4 of the 28 event catalog files declare
 * `areas`. Those rows are the most event-specific vocabulary in the deck, so the area filter
 * gives them their own bucket rather than making a third of each deck unreachable.
 */
const AREA_EVENT = "event";

type DifficultyFilter = "all" | VocabDifficulty;
type SessionSize = "all" | "20" | "50";

const DIFFICULTY_VALUES: DifficultyFilter[] = ["all", "medium", "hard"];
const SIZE_VALUES: SessionSize[] = ["all", "20", "50"];

export default function VocabPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        Back home
      </Link>

      <div className="mt-4 flex items-start justify-between gap-4">
        <div>
          <MarkerText rotate={-3} className="text-base">
            vocab terms
          </MarkerText>
          <h1 className="mt-1 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
            Study with <span className="text-accent">flashcards</span>
          </h1>
        </div>
        <StickyNote className="hidden h-14 w-14 text-ink/70 sm:block" />
      </div>

      <React.Suspense fallback={<div className="mt-8 h-40" />}>
        <VocabBrowser />
      </React.Suspense>
    </div>
  );
}

function VocabBrowser() {
  const router = useRouter();
  const params = useSearchParams();

  const rawCluster = params.get("cluster");
  const cluster = rawCluster && clusterHasVocab(rawCluster) ? rawCluster : null;

  const rawEvent = params.get("event");
  const event = cluster && rawEvent && vocabEventMeta(cluster, rawEvent) ? rawEvent : null;

  const clusterMeta = CLUSTERS.find((c) => c.value === cluster);
  const eventMeta = cluster && event ? vocabEventMeta(cluster, event) : null;

  const rawDifficulty = params.get("difficulty") as DifficultyFilter | null;
  const difficulty: DifficultyFilter =
    rawDifficulty && DIFFICULTY_VALUES.includes(rawDifficulty) ? rawDifficulty : "all";

  const area = params.get("area") ?? AREA_ALL;

  const rawSize = params.get("size") as SessionSize | null;
  const size: SessionSize = rawSize && SIZE_VALUES.includes(rawSize) ? rawSize : "all";

  // Cluster/event navigation pushes (the back button should walk the browse tree) and drops
  // the deck filters, which are meaningless against a different event's areas.
  const go = React.useCallback(
    (next: { cluster?: string | null; event?: string | null }) => {
      const qs = new URLSearchParams();
      if (next.cluster) qs.set("cluster", next.cluster);
      if (next.event) qs.set("event", next.event);
      const s = qs.toString();
      router.push(s ? `${PATH}?${s}` : PATH);
    },
    [router],
  );

  // Filter changes replace instead, so toggling a filter a dozen times doesn't bury the event
  // grid a dozen entries deep in history. The URL still carries them, so "RMS, hard only,
  // 20 cards" is a shareable link like ?cluster= and ?event= already are.
  const setFilters = React.useCallback(
    (patch: Record<string, string | null>) => {
      const qs = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(patch)) {
        if (value === null) qs.delete(key);
        else qs.set(key, value);
      }
      router.replace(`${PATH}?${qs.toString()}`, { scroll: false });
    },
    [params, router],
  );

  return (
    <>
      <div className="mt-6 flex flex-wrap items-center gap-2 text-sm text-muted">
        <Crumb active={cluster === null} onClick={() => go({})}>
          All clusters
        </Crumb>
        {cluster && clusterMeta && (
          <>
            <span aria-hidden>/</span>
            <Crumb active={event === null} onClick={() => go({ cluster })}>
              {clusterMeta.label}
            </Crumb>
          </>
        )}
        {eventMeta && (
          <>
            <span aria-hidden>/</span>
            <Crumb active>{eventMeta.code}</Crumb>
          </>
        )}
      </div>

      <div className="mt-8">
        {cluster === null && (
          <div className="grid gap-6 sm:grid-cols-2">
            {CLUSTERS.map((c, i) => {
              const built = clusterHasVocab(c.value);
              return (
                <TileButton
                  key={c.value}
                  variant={i}
                  fullWidth
                  disabled={!built}
                  onClick={() => go({ cluster: c.value })}
                  tape={built ? `${eventsForCluster(c.value).length} events` : "coming soon"}
                  tapeColor={built ? CARD_TAPE[i % CARD_TAPE.length] : "support"}
                  eyebrow="cluster"
                  title={c.label}
                  sub={c.examName}
                  body={built ? clusterTagSummary(c.value) : "Vocab sets coming soon."}
                />
              );
            })}
          </div>
        )}

        {cluster !== null && event === null && clusterMeta && (
          <div className="grid gap-6 sm:grid-cols-2">
            {eventsForCluster(cluster).map((ev, i) => (
              <TileButton
                key={ev.code}
                variant={i}
                fullWidth
                onClick={() => go({ cluster, event: ev.code })}
                // Every deck holds 250 terms since Phase 5, so "250 terms" on all 28 tiles
                // said nothing. The hard/medium split is the one number that still varies.
                tape={`${ev.difficultyCounts.hard} hard / ${ev.difficultyCounts.medium} med`}
                tapeColor={CARD_TAPE[i % CARD_TAPE.length]}
                eyebrow={clusterMeta.label}
                title={ev.code}
                sub={ev.name}
                body={eventSummary(ev)}
              />
            ))}
          </div>
        )}

        {cluster !== null && event !== null && clusterMeta && eventMeta && (
          <div className="mx-auto max-w-3xl">
            <FlashcardStudy
              key={`${cluster}-${event}`}
              cluster={cluster}
              eventCode={event}
              clusterLabel={clusterMeta.label}
              difficulty={difficulty}
              area={area}
              size={size}
              onFilters={setFilters}
              onBack={() => go({ cluster })}
            />
          </div>
        )}
      </div>
    </>
  );
}

function eventSummary(event: NonNullable<ReturnType<typeof vocabEventMeta>>) {
  const label = event.format ? FORMAT_LABEL[event.format] : "DECA event";
  const tags = event.tags.slice(0, 3).map(formatTag);
  const size = `${event.termCount} terms`;
  if (tags.length === 0) return `${label}. ${size}.`;
  return `${label}. ${size}, focused on ${tags.join(", ")}.`;
}

/**
 * Fisher-Yates driven by a mulberry32 PRNG rather than `Math.random()` directly, so the draw
 * is a pure function of (pool, seed). The session can then be a `useMemo` that only re-rolls
 * when the seed or the filtered pool actually changes — a bare `Math.random()` shuffle would
 * hand the student a different 20 cards on any incidental re-render.
 */
function shuffled<T>(items: T[], seed: number): T[] {
  const out = items.slice();
  let s = seed >>> 0;
  for (let i = out.length - 1; i > 0; i--) {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    const r = ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    const j = Math.floor(r * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function matchesArea(term: VocabTerm, area: string): boolean {
  if (area === AREA_ALL) return true;
  if (area === AREA_EVENT) return term.tags.length === 0;
  return term.tags.includes(area);
}

function matchesDifficulty(term: VocabTerm, difficulty: DifficultyFilter): boolean {
  return difficulty === "all" || term.difficulty === difficulty;
}

function FlashcardStudy({
  cluster,
  eventCode,
  clusterLabel,
  difficulty,
  area: requestedArea,
  size,
  onFilters,
  onBack,
}: {
  cluster: string;
  eventCode: string;
  clusterLabel: string;
  difficulty: DifficultyFilter;
  area: string;
  size: SessionSize;
  onFilters: (patch: Record<string, string | null>) => void;
  onBack: () => void;
}) {
  const [terms, setTerms] = React.useState<VocabTerm[]>([]);
  const [eventName, setEventName] = React.useState(eventCode);
  const [state, setState] = React.useState<"loading" | "ready" | "error">("loading");
  const [errorMsg, setErrorMsg] = React.useState("");
  const [index, setIndex] = React.useState(0);
  const [revealed, setRevealed] = React.useState(false);
  const [learned, setLearned] = React.useState<Set<string>>(() => new Set());
  const [seed, setSeed] = React.useState(() => Math.floor(Math.random() * 0xffffffff));

  React.useEffect(() => {
    let cancelled = false;

    loadVocabEvent(cluster, eventCode)
      .then(({ vocab }) => {
        if (cancelled) return;
        setTerms(vocab.terms);
        setEventName(vocab.event.name);
        setState("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setErrorMsg(err instanceof Error ? err.message : "Couldn't load those terms.");
        setState("error");
      });

    return () => {
      cancelled = true;
    };
  }, [cluster, eventCode]);

  // Which areas this deck actually contains. Note this is a near-partition, not an overlap
  // set: the gate keeps a slug in one catalog file, so 6,255 of 7,000 rows carry exactly one
  // tag and only 22 carry two. The bucket totals therefore sum a hair above the deck size.
  const areas = React.useMemo(() => {
    const counts = new Map<string, number>();
    let untagged = 0;
    for (const term of terms) {
      if (term.tags.length === 0) untagged += 1;
      for (const tag of term.tags) counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
    return { counts, untagged };
  }, [terms]);

  // A shared link can name an area this deck doesn't carry; fall back rather than showing an
  // empty deck for a filter the student can't see is set.
  const area =
    requestedArea === AREA_ALL ||
    (requestedArea === AREA_EVENT && areas.untagged > 0) ||
    areas.counts.has(requestedArea)
      ? requestedArea
      : AREA_ALL;

  // Each control counts against the OTHER control's current selection, so the numbers read as
  // "what I'd get if I clicked this" instead of as a static census.
  const byArea = React.useMemo(
    () => terms.filter((term) => matchesArea(term, area)),
    [terms, area],
  );
  const byDifficulty = React.useMemo(
    () => terms.filter((term) => matchesDifficulty(term, difficulty)),
    [terms, difficulty],
  );

  const difficultyCounts = React.useMemo(() => {
    let medium = 0;
    let hard = 0;
    for (const term of byArea) {
      if (term.difficulty === "hard") hard += 1;
      else medium += 1;
    }
    return { all: byArea.length, medium, hard };
  }, [byArea]);

  const areaOptions = React.useMemo(() => {
    const counts = new Map<string, number>();
    let untagged = 0;
    for (const term of byDifficulty) {
      if (term.tags.length === 0) untagged += 1;
      for (const tag of term.tags) counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
    const options = [...areas.counts.keys()]
      .sort((a, b) => formatTag(a).localeCompare(formatTag(b)))
      .map((tag) => ({
        value: tag,
        label: `${formatTag(tag)} (${counts.get(tag) ?? 0})`,
        disabled: (counts.get(tag) ?? 0) === 0,
      }));
    if (areas.untagged > 0) {
      options.push({
        value: AREA_EVENT,
        label: `Event-specific (${untagged})`,
        disabled: untagged === 0,
      });
    }
    return [
      { value: AREA_ALL, label: `All areas (${byDifficulty.length})`, disabled: false },
      ...options,
    ];
  }, [areas, byDifficulty]);

  const pool = React.useMemo(
    () =>
      terms.filter((term) => matchesDifficulty(term, difficulty) && matchesArea(term, area)),
    [terms, difficulty, area],
  );

  // "All" keeps the assembler's deliberate ordering; a sized session is a shuffled draw over
  // the whole filtered pool, sliced — so it can never repeat a card.
  const session = React.useMemo(
    () => (size === "all" ? pool : shuffled(pool, seed).slice(0, Number(size))),
    [pool, size, seed],
  );

  // Any change to the session — a filter, a size, a new draw — starts it over, otherwise a
  // stale index points past the end of a smaller set. Adjusted during render rather than in an
  // effect (react.dev "you might not need an effect"): the memo only yields a new array when
  // the pool, the size or the seed actually changed.
  const [sessionAtIndex, setSessionAtIndex] = React.useState(session);
  if (sessionAtIndex !== session) {
    setSessionAtIndex(session);
    setIndex(0);
    setRevealed(false);
  }

  const active = session[index];
  const progress = session.length > 0 ? ((index + 1) / session.length) * 100 : 0;
  const learnedHere = session.reduce(
    (total, term) => total + (learned.has(term.slug) ? 1 : 0),
    0,
  );

  const move = (direction: -1 | 1) => {
    setIndex((current) => {
      const next = current + direction;
      if (next < 0 || next >= session.length) return current;
      return next;
    });
    setRevealed(false);
  };

  const toggleLearned = () => {
    if (!active) return;
    setLearned((current) => {
      const next = new Set(current);
      if (next.has(active.slug)) next.delete(active.slug);
      else next.add(active.slug);
      return next;
    });
  };

  if (state === "loading") {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <Sparkle className="h-8 w-8 animate-pulse text-accent" />
        <MarkerText rotate={-2}>opening the deck...</MarkerText>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="rounded-2xl border-2 border-line bg-paper-2 p-6 text-center">
        <MarkerText rotate={-2}>couldn&apos;t open that deck</MarkerText>
        <p className="mt-2 text-sm text-muted">{errorMsg}</p>
        <div className="mt-4">
          <Button variant="outline" onClick={onBack}>
            Pick another event
          </Button>
        </div>
      </div>
    );
  }

  if (terms.length === 0) {
    return (
      <div className="rounded-2xl border-2 border-line bg-paper-2 p-6 text-center">
        <MarkerText rotate={-2}>empty deck</MarkerText>
        <p className="mt-2 text-sm text-muted">No vocab terms were found for this event.</p>
      </div>
    );
  }

  const header = (
    <>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl font-bold tracking-tight">
            {clusterLabel} / {eventCode}
          </h2>
          <p className="mt-1 text-sm text-muted">{eventName}</p>
        </div>
        <TapeLabel color="support" rotate={-3}>
          {learnedHere}/{session.length} learned
        </TapeLabel>
      </div>

      <div className="mb-5 rounded-2xl border-2 border-line bg-paper-2 p-4 sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1">
            <p className="marker mb-2 text-sm text-muted">difficulty</p>
            <Segmented<DifficultyFilter>
              options={[
                { value: "all", label: "All", sub: `${difficultyCounts.all} cards` },
                { value: "medium", label: "Medium", sub: `${difficultyCounts.medium} cards` },
                { value: "hard", label: "Hard", sub: `${difficultyCounts.hard} cards` },
              ]}
              value={difficulty}
              onChange={(value) =>
                onFilters({ difficulty: value === "all" ? null : value })
              }
            />
          </div>
          <div className="min-w-0 sm:w-64">
            <p className="marker mb-2 text-sm text-muted">area</p>
            <Select
              aria-label="Filter by instructional area"
              value={area}
              onChange={(value) => onFilters({ area: value === AREA_ALL ? null : value })}
              options={areaOptions}
            />
          </div>
        </div>

        <div className="mt-4 border-t border-dashed border-line pt-4">
          <p className="marker mb-2 text-sm text-muted">session</p>
          <div className="flex flex-wrap items-center gap-3">
            <Segmented<SessionSize>
              options={[
                { value: "all", label: "All", sub: `${pool.length} cards` },
                { value: "20", label: "20", sub: "random draw" },
                { value: "50", label: "50", sub: "random draw" },
              ]}
              value={size}
              onChange={(value) => onFilters({ size: value === "all" ? null : value })}
            />
            {size !== "all" && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSeed(Math.floor(Math.random() * 0xffffffff))}
              >
                <Shuffle className="h-4 w-4" />
                New draw
              </Button>
            )}
          </div>
        </div>
      </div>
    </>
  );

  if (!active) {
    return (
      <div>
        {header}
        <div className="rounded-2xl border-2 border-line bg-paper-2 p-6 text-center">
          <MarkerText rotate={-2}>nothing matches those filters</MarkerText>
          <p className="mt-2 text-sm text-muted">
            This deck has no {difficulty === "all" ? "" : `${difficulty} `}cards in that area.
          </p>
          <div className="mt-4">
            <Button
              variant="outline"
              onClick={() => onFilters({ difficulty: null, area: null })}
            >
              Clear the filters
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const isLearned = learned.has(active.slug);

  return (
    <div>
      {header}

      <div className="mb-4 h-3 overflow-hidden rounded-full border-2 border-ink bg-paper">
        <div className="h-full bg-highlight transition-all" style={{ width: `${progress}%` }} />
      </div>

      <button
        type="button"
        onClick={() => setRevealed((value) => !value)}
        aria-pressed={revealed}
        className="block w-full text-left transition-transform hover:-translate-y-0.5"
      >
        {/* `variant` follows the position in the session, not in the full 250-card deck, so
            the frame rhythm stays stable as you page through whatever you filtered to. */}
        <Card variant={index} className="min-h-[21rem] p-6 sm:p-8">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink font-display text-sm font-bold text-paper">
              {index + 1}
            </span>
            <div className="flex flex-wrap items-center gap-2">
              {active.tags.length > 0 ? (
                active.tags.map((tag) => (
                  <Highlight
                    key={tag}
                    color="highlight"
                    animate={false}
                    className="text-sm font-medium"
                  >
                    {formatTag(tag)}
                  </Highlight>
                ))
              ) : (
                <Highlight color="highlight" animate={false} className="text-sm font-medium">
                  Event-specific
                </Highlight>
              )}
              <DifficultyBadge difficulty={active.difficulty} />
            </div>
          </div>

          {!revealed ? (
            <div className="flex min-h-56 flex-col justify-center">
              <p className="marker text-sm text-muted">term</p>
              <p className="mt-3 font-display text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
                {active.term}
              </p>
              <p className="mt-8 text-sm text-muted">Click the card to reveal the definition.</p>
            </div>
          ) : (
            <div className="flex min-h-56 flex-col justify-center">
              <p className="marker text-sm text-muted">definition</p>
              <p className="mt-3 text-xl font-semibold leading-relaxed">{active.definition}</p>
              <div className="mt-6 rounded-2xl bg-paper-2 p-4">
                <p className="text-[0.8rem] font-semibold uppercase text-muted">Why it matters</p>
                <p className="mt-1 leading-relaxed text-ink/80">{active.whyItMatters}</p>
              </div>
            </div>
          )}
        </Card>
      </button>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => move(-1)} disabled={index === 0}>
            <ChevronLeft className="h-4 w-4" />
            Prev
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => move(1)}
            disabled={index >= session.length - 1}
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setRevealed((value) => !value)}>
            <RotateCcw className="h-4 w-4" />
            Flip
          </Button>
          <Button
            variant={isLearned ? "accent" : "primary"}
            size="sm"
            onClick={toggleLearned}
            className={cn(isLearned && "bg-support")}
          >
            <CheckCircle2 className="h-4 w-4" />
            {isLearned ? "Learned" : "Mark learned"}
          </Button>
        </div>
      </div>

      <div className="mt-8 flex flex-wrap gap-3">
        <Button variant="outline" onClick={onBack}>
          Pick another event
        </Button>
        <Button asChild variant="ghost">
          <Link href="/question-bank">Open question bank</Link>
        </Button>
      </div>
    </div>
  );
}

function DifficultyBadge({ difficulty }: { difficulty: VocabDifficulty }) {
  const style = DIFFICULTY_STYLE[difficulty];
  return (
    <span
      className={cn(
        "sketch-radius shrink-0 border-2 px-2 py-0.5 text-xs font-semibold",
        style.cls,
      )}
    >
      {style.label}
    </span>
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
            <span className="marker text-muted">covers / </span>
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
