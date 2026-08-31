"use client";

// The Roleplay Challenge (frontend plan 11, phase B: the day board + archive).
//
// This replaced a locked draft of a per-click roleplay GENERATOR whose
// `TODO(pass-3): POST /api/generate-roleplay` was never going to exist — a static
// site has nowhere to run a model per request, which is the same reason the
// live-JIT quiz path was dropped. The generator is retired, not deferred (F6).
//
// ROUTE SHAPE (F7): one route, query-param navigation — `?day=`, `?view=archive`,
// `?event=`. No dynamic segments: the archive reaches ~10,200 files a year, so
// `generateStaticParams` over it is a build-time liability that grows forever,
// and the usual counter-argument (SEO) doesn't apply because `/roleplay` is
// member-gated and never indexed. Access is already enforced by `MEMBER_ROUTES`
// in lib/auth/gated-routes.ts — this file adds no second list.
//
// UNLOCKED, EARLY. Plan 11 had the dev-lock coming off in phase E, once a real
// `fill_buffer.py` batch existed; it came off here instead, so what members see
// is the real board over the committed FIXTURE archive — 7 roleplays across 3
// sparse days, most events greyed. Nothing about that is faked, and the board
// was built for exactly this state (§4c). Phase C closed the gap that left: a
// card now opens into the run surface. What is still thin is the archive itself,
// and it stays that way until the K3 fix lets a real batch land.
//
// The run surface is hosted ONCE, here, over the board — the same shape as the
// dashboard hosting a single `LiveQuizModal`. It is keyed by `date:code` so a
// different scenario (or a close) gets fresh run state rather than inheriting a
// half-finished one, which is also how phase C gets away with keeping that state
// in React (see components/roleplay/run-surface.tsx).

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MarkerText } from "@/components/marker-text";
import { Clipboard, Sparkle } from "@/components/doodles";
import { DayBoard } from "@/components/roleplay/day-board";
import { ArchiveBrowse } from "@/components/roleplay/archive-browse";
import { RunSurface } from "@/components/roleplay/run-surface";
import { loadAllDays, loadIndex } from "@/lib/roleplay/archive";
import { dayNumber, resolveDay, stepDay } from "@/lib/roleplay/select";
import type { RoleplayDay } from "@/lib/roleplay/types";
import { easternDateKey, msUntilNextEasternDay } from "@/lib/roleplay/eastern";

const PATH = "/roleplay";

export default function RoleplayPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Back home
      </Link>

      <div className="mt-4 flex items-start justify-between gap-4">
        <div>
          <MarkerText rotate={-3} className="text-base">
            roleplay challenge
          </MarkerText>
          {/* The daily framing is TRUE OF THE MECHANISM and false of the archive
              (#118, the member-side half of #108): the board really does drop on
              Eastern midnight, but the only days on disk are the 7 committed
              fixtures across 3 sparse days, because fill_buffer.py (backend plan
              03 step 6) has never been run. This headline used to read "A new
              case study every day" and sat directly above a board headed with a
              date three days stale showing 1 of 28 events. It names the content
              instead, in the same words as the landing card, so both sides of
              the funnel read as one voice. RESTORE the daily framing HERE AND ON
              THE LANDING CARD in the same change that ships the first generated
              batch. */}
          <h1 className="mt-1 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
            Full <span className="text-accent-ink">case studies</span> across the 28 events
          </h1>
        </div>
        <Clipboard className="hidden h-14 w-11 text-ink/70 sm:block" />
      </div>

      <div className="mt-8">
        {/* The browser reads ?day/&view from the URL, so this needs a Suspense
            boundary (useSearchParams). */}
        <React.Suspense fallback={<Waiting label="opening the archive…" />}>
          <RoleplayChallenge />
        </React.Suspense>
      </div>
    </div>
  );
}

type Status = "loading" | "ready" | "unavailable";

function RoleplayChallenge() {
  const router = useRouter();
  const params = useSearchParams();

  // --- `now`, stamped in an effect and passed DOWN (plan 11 F1) -------------
  // The day boundary is EASTERN midnight, not the viewer's, so every visitor sees
  // the same drop at the same instant (lib/roleplay/eastern.ts). `now` is still
  // stamped client-side rather than derived during render: this route is
  // statically prerendered, so a build-time clock would freeze the day at build
  // time. Nothing day-dependent renders until `now` exists. The rollover timer and
  // the visibility resync below both measure against EASTERN midnight — a tab left
  // open across it must move to the new drop rather than pin an old one, and a tab
  // in Los Angeles has to do that at 9pm its own time.
  const [now, setNow] = React.useState<number | null>(null);
  React.useEffect(() => {
    Promise.resolve().then(() => setNow(Date.now()));
  }, []);
  React.useEffect(() => {
    if (now == null) return;
    const timer = window.setTimeout(
      () => setNow(Date.now()),
      msUntilNextEasternDay(Date.now()) + 1000,
    );
    const resync = () => {
      setNow((prev) =>
        prev != null && easternDateKey(prev) === easternDateKey(Date.now()) ? prev : Date.now(),
      );
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") resync();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", resync);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", resync);
    };
  }, [now]);

  // --- the archive ---------------------------------------------------------
  const [days, setDays] = React.useState<RoleplayDay[]>([]);
  const [months, setMonths] = React.useState<string[]>([]);
  const [status, setStatus] = React.useState<Status>("loading");

  React.useEffect(() => {
    let cancelled = false;
    Promise.all([loadIndex(), loadAllDays()])
      .then(([index, all]) => {
        if (cancelled) return;
        setMonths(index.months);
        setDays(all);
        setStatus("ready");
      })
      // A missing public/roleplays/ is the PRE-FIRST-BATCH state, not a bug: it
      // must degrade to an honest empty panel, never throw into a blank page.
      .catch(() => {
        if (!cancelled) setStatus("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Opening and closing a run only changes `?event=`, and the board underneath
  // doesn't move — so those navigations pass `scroll: false`. Next scrolls to the
  // top by default, which on close would throw the board back to the header and
  // lose the card the run was opened from (the card `Dialog` is about to restore
  // focus to). Switching day or view still scrolls, because the content there
  // genuinely changes out from under you.
  const go = React.useCallback(
    (
      next: { day?: string | null; view?: string | null; event?: string | null },
      opts?: { scroll?: boolean },
    ) => {
      const qs = new URLSearchParams();
      if (next.day) qs.set("day", next.day);
      if (next.view) qs.set("view", next.view);
      if (next.event) qs.set("event", next.event);
      const s = qs.toString();
      router.push(s ? `${PATH}?${s}` : PATH, { scroll: opts?.scroll ?? true });
    },
    [router],
  );

  if (now == null || status === "loading") {
    return <Waiting label="opening the archive…" />;
  }

  if (status === "unavailable") {
    return (
      <Empty
        title="The challenge hasn't started yet"
        body="There are no roleplays in the archive right now. The first day will show up here as soon as it drops."
      />
    );
  }

  const requested = params.get("day");
  const selection = resolveDay(days, requested, now);

  if (params.get("view") === "archive") {
    return (
      <ArchiveBrowse
        months={months}
        days={days}
        now={now}
        onOpenDay={(date) => go({ day: date })}
        onBack={() => go({})}
      />
    );
  }

  if (!selection.day) {
    return (
      <Empty
        title="Nothing has dropped yet"
        body={
          days.length > 0
            ? "The next day is already written and will unlock on its own date."
            : "The first day will show up here as soon as it drops."
        }
        action={
          months.length > 0 ? (
            <Button variant="outline" size="sm" onClick={() => go({ view: "archive" })}>
              Browse the archive
            </Button>
          ) : null
        }
      />
    );
  }

  const day = selection.day;
  // `?event=` is user-typeable, so it is normalized here and validated inside the
  // run surface against BOTH `EVENTS` and this day's line-up — an unknown code
  // and a code the day doesn't carry each degrade to their own honest panel
  // rather than throwing. It resolves against the day actually on screen, which
  // may be a fallback for an unpublished or unknown `?day=`.
  const event = params.get("event")?.trim().toUpperCase() || null;

  return (
    <>
      <DayBoard
        day={day}
        dayNumber={dayNumber(days, day.date)}
        prev={stepDay(days, day.date, "prev", now)}
        next={stepDay(days, day.date, "next", now)}
        requested={requested}
        fallback={selection.fallback}
        onStep={(date) => go({ day: date })}
        onBrowse={() => go({ view: "archive" })}
        onOpenEvent={(code) => go({ day: day.date, event: code }, { scroll: false })}
      />
      <RunSurface
        // Fresh run state per scenario — and on close, since `event` goes null.
        // Phase C keeps that state in React, so remounting IS the reset.
        key={`${day.date}:${event ?? ""}`}
        open={event != null}
        date={day.date}
        code={event}
        available={day.events}
        onClose={() => go({ day: day.date }, { scroll: false })}
      />
    </>
  );
}

/* --------------------------------------------------------------- pieces */

function Waiting({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-24 text-center">
      <Sparkle className="h-8 w-8 animate-pulse text-accent" />
      <MarkerText rotate={-2}>{label}</MarkerText>
    </div>
  );
}

function Empty({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <Card className="p-8 text-center sm:p-10">
      <MarkerText rotate={-2} className="text-base">
        nothing here yet
      </MarkerText>
      <h2 className="mt-2 font-display text-2xl font-extrabold tracking-tight">{title}</h2>
      <p className="mx-auto mt-3 max-w-md text-sm text-ink/70">{body}</p>
      {action ? <div className="mt-6 flex justify-center">{action}</div> : null}
    </Card>
  );
}
