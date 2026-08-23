"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Highlight } from "@/components/highlight";
import { MarkerText } from "@/components/marker-text";
import { TapeLabel } from "@/components/tape-label";
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
  type VocabTerm,
} from "@/lib/vocab";

const PATH = "/vocab";
const CARD_TAPE = ["support", "accent", "highlight"] as const;

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
                tape={`${ev.termCount} terms`}
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
  if (tags.length === 0) return label;
  return `${label}. Focus: ${tags.join(", ")}.`;
}

function FlashcardStudy({
  cluster,
  eventCode,
  clusterLabel,
  onBack,
}: {
  cluster: string;
  eventCode: string;
  clusterLabel: string;
  onBack: () => void;
}) {
  const [terms, setTerms] = React.useState<VocabTerm[]>([]);
  const [eventName, setEventName] = React.useState(eventCode);
  const [state, setState] = React.useState<"loading" | "ready" | "error">("loading");
  const [errorMsg, setErrorMsg] = React.useState("");
  const [index, setIndex] = React.useState(0);
  const [revealed, setRevealed] = React.useState(false);
  const [learned, setLearned] = React.useState<Set<string>>(() => new Set());

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

  const active = terms[index];
  const progress = terms.length > 0 ? ((index + 1) / terms.length) * 100 : 0;

  const move = (direction: -1 | 1) => {
    setIndex((current) => {
      const next = current + direction;
      if (next < 0 || next >= terms.length) return current;
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

  if (!active) {
    return (
      <div className="rounded-2xl border-2 border-line bg-paper-2 p-6 text-center">
        <MarkerText rotate={-2}>empty deck</MarkerText>
        <p className="mt-2 text-sm text-muted">No vocab terms were found for this event.</p>
      </div>
    );
  }

  const isLearned = learned.has(active.slug);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl font-bold tracking-tight">
            {clusterLabel} / {eventCode}
          </h2>
          <p className="mt-1 text-sm text-muted">{eventName}</p>
        </div>
        <TapeLabel color="support" rotate={-3}>
          {learned.size}/{terms.length} learned
        </TapeLabel>
      </div>

      <div className="mb-4 h-3 overflow-hidden rounded-full border-2 border-ink bg-paper">
        <div className="h-full bg-highlight transition-all" style={{ width: `${progress}%` }} />
      </div>

      <button
        type="button"
        onClick={() => setRevealed((value) => !value)}
        aria-pressed={revealed}
        className="block w-full text-left transition-transform hover:-translate-y-0.5"
      >
        <Card variant={index} className="min-h-[21rem] p-6 sm:p-8">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink font-display text-sm font-bold text-paper">
              {index + 1}
            </span>
            <div className="flex flex-wrap items-center gap-2">
              {active.tags.slice(0, 3).map((tag) => (
                <Highlight key={tag} color="highlight" animate={false} className="text-sm font-medium">
                  {formatTag(tag)}
                </Highlight>
              ))}
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
            disabled={index === terms.length - 1}
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
