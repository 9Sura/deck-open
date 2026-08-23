"use client";

// The run surface — what turns a roleplay from a document you read into a
// rehearsal you perform (frontend plan 11 §4b). One hosted overlay, deep-linked
// by `?day=&event=`, exactly like the dashboard hosts one `LiveQuizModal`.
//
// FOUR STATES, and the ORDER OF REVEAL IS THE PRODUCT:
//   Brief    what a competitor gets before the clock starts: event, cluster, PIs,
//            21st Century Skills, the participant instructions. Not the situation.
//   Prep     the situation and the exhibit, against `prepMinutes`. The judge's
//            characterization and questions ARE NOT RENDERED — not hidden with
//            CSS, not in the DOM. Reading them here destroys the exercise, and a
//            display:none question is still readable from the inspector and still
//            read aloud by a screen reader.
//   Present  `presentMinutes`, the judge revealed, questions one at a time.
//   Debrief  self-score + everything unlocked (components/roleplay/debrief.tsx).
//
// TIMINGS COME FROM `lib/data/events.ts`, NEVER FROM THE ROLEPLAY TEXT. The
// generated `participantInstructions` boilerplate is measurably wrong about this:
// it says "10 minutes to present … and no time for judge questions" and is then
// followed by three judge questions. Six of the seven committed fixtures carry
// `meta.defects: ["boilerplate:denies-judge-questions"]` for precisely that. The
// text is still rendered verbatim in the Brief — it is a tracked backend defect,
// and papering over it by rewriting the prose would make it uncountable (plan 11
// §2a note 4, §8.4) — but every number on screen comes from `findEvent(code)`.
// Series/Principles run 10 + 10; Team runs 30 + 15, which is a different screen.
//
// RUN STATE IS REACT-ONLY IN PHASE C. A refresh loses the run. Plan §4b asks for
// persistence, but that is `lib/roleplay/run-store.ts` — phase D — and pulling a
// store, a schema and a migration into C stops C being one shippable unit. The
// state below hoists into that store behind the same props when D lands. What C
// owes the user instead is honesty: closing mid-timer asks first, and the debrief
// says out loud that it isn't kept.
//
// NOTHING ENTERS /progress (F2). No `ProgressStore`, no `mastery.ts`, no
// `Attempt` — running a roleplay must not move the readiness number.
//
// NO STRING CLAIMS VERIFIED DIFFICULTY (F5). There is no referee, and
// `meta.gate.passed` means "nothing countable is wrong", not "this is ICDC-hard".
// The one supportable line is "harder than the district-level material DECA
// publishes."
//
// The clock lives in an effect and never in render. `Dialog` returns null until
// it has hydrated, so no countdown is ever server-rendered — which is the other
// half of the hydration discipline `lib/roleplay/select.ts` keeps by staying pure.

import * as React from "react";
import { Dialog } from "@/components/ui/dialog";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TapeLabel } from "@/components/tape-label";
import { MarkerText } from "@/components/marker-text";
import { Sparkle } from "@/components/doodles";
import { ExhibitBlock, SituationProse } from "@/components/roleplay/exhibit-block";
import { JudgeQuestions } from "@/components/roleplay/judge-questions";
import { Debrief, type PiScore } from "@/components/roleplay/debrief";
import { loadRoleplay } from "@/lib/roleplay/archive";
import { formatDay } from "@/lib/roleplay/select";
import { findEvent } from "@/lib/data/events";
import { FORMAT_LABEL } from "@/lib/deca";
import type { Roleplay } from "@/lib/roleplay/types";
import { cn } from "@/lib/utils";

type Stage = "brief" | "prep" | "present" | "debrief";

const STAGES: { key: Stage; label: string }[] = [
  { key: "brief", label: "Brief" },
  { key: "prep", label: "Prep" },
  { key: "present", label: "Present" },
  { key: "debrief", label: "Debrief" },
];

/** A run is "in flight" — and therefore worth confirming before you lose it — for
 *  exactly the two timed stages. Brief and Debrief close without a prompt. */
const TIMED: Stage[] = ["prep", "present"];

type LoadStatus = "loading" | "ready" | "unavailable";

export function RunSurface({
  open,
  date,
  code,
  /** The codes this day actually carries (`day.events`). */
  available,
  onClose,
}: {
  open: boolean;
  date: string;
  /** The raw `?event=` value, upper-cased by the caller. Null when closed. */
  code: string | null;
  available: string[];
  onClose: () => void;
}) {
  const event = code ? findEvent(code) : undefined;
  const onThisDay = code != null && available.includes(code);
  const loadable = open && code != null && event != null && onThisDay;

  // --- the roleplay ---------------------------------------------------------
  // Starts at "loading" and is only ever moved off it by the fetch settling —
  // there is no synchronous reset in the effect, because the page remounts this
  // component per `date:code` (see its `key`), so a new scenario always starts
  // from this initial state rather than inheriting the last one's.
  const [roleplay, setRoleplay] = React.useState<Roleplay | null>(null);
  const [status, setStatus] = React.useState<LoadStatus>("loading");

  React.useEffect(() => {
    if (!loadable || code == null) return;
    let cancelled = false;
    loadRoleplay(date, code)
      .then((rp) => {
        if (cancelled) return;
        setRoleplay(rp);
        setStatus("ready");
      })
      // A file the day manifest promised but `public/` doesn't have is a real
      // possibility (a half-copied batch), and it degrades to a panel — never to
      // a thrown render behind a modal backdrop the user then can't dismiss.
      .catch(() => {
        if (cancelled) return;
        setRoleplay(null);
        setStatus("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [loadable, date, code]);

  // --- run state (ephemeral — see the header) -------------------------------
  const [stage, setStage] = React.useState<Stage>("brief");
  const [revealed, setRevealed] = React.useState(0);
  const [scores, setScores] = React.useState<Map<number, PiScore>>(new Map());
  const [confirming, setConfirming] = React.useState(false);

  const restart = React.useCallback(() => {
    setStage("brief");
    setRevealed(0);
    setScores(new Map());
  }, []);

  // Esc, the backdrop, and Exit all land here. Mid-run they raise the confirm
  // instead of closing; a SECOND Esc (or backdrop click) while the confirm is up
  // goes through, so the keyboard escape hatch is two presses, not zero.
  const requestClose = React.useCallback(() => {
    if (confirming) {
      onClose();
      return;
    }
    if (TIMED.includes(stage)) {
      setConfirming(true);
      return;
    }
    onClose();
  }, [confirming, stage, onClose]);

  const label = event ? `${event.code} — ${event.name}` : "Roleplay";

  return (
    <Dialog open={open} onClose={requestClose} label={label} className="max-w-3xl">
      <Card className="p-5 sm:p-8">
        {/* ---- Header ---- */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <TapeLabel color="accent" rotate={-2}>
                {code ?? "roleplay"}
              </TapeLabel>
              <span className="marker text-sm text-muted">{formatDay(date)}</span>
            </div>
            <h2 className="mt-2 font-display text-2xl font-extrabold leading-tight tracking-tight">
              {event ? event.name : "This scenario"}
            </h2>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={requestClose}
            aria-label="Close this roleplay"
          >
            Exit ✕
          </Button>
        </div>

        {/* ---- Confirm, inline. NOT a nested dialog — a second focus trap over
                the first is how a modal becomes impossible to leave. ---- */}
        {confirming ? (
          <ConfirmEnd onKeepGoing={() => setConfirming(false)} onEnd={onClose} />
        ) : null}

        {/* ---- Body ---- */}
        {code == null ? null : !event ? (
          <Degraded
            title="That isn't one of the 28 events"
            body={`The archive is organised by event code, and "${code}" isn't one of them. Pick an event from the day's line-up instead.`}
            onClose={onClose}
          />
        ) : !onThisDay ? (
          <Degraded
            title={`${event.code} isn't part of this day`}
            body={`${event.name} didn't clear the quality checks for ${formatDay(date, true)}, so there's no scenario to run. Every event that did make it is still on the board — and ${event.code} may well be there on another day.`}
            onClose={onClose}
          />
        ) : status === "loading" ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <Sparkle className="h-8 w-8 animate-pulse text-accent" />
            <MarkerText rotate={-2}>opening the scenario…</MarkerText>
          </div>
        ) : status === "unavailable" || !roleplay ? (
          <Degraded
            title="This one wouldn't open"
            body={`${event.code} is listed for ${formatDay(date, true)}, but its file couldn't be read just now. Try again, or step to another event.`}
            onClose={onClose}
          />
        ) : (
          <Run
            roleplay={roleplay}
            prepMinutes={event.prepMinutes}
            presentMinutes={event.presentMinutes}
            formatLabel={FORMAT_LABEL[event.format]}
            roles={event.roles}
            stage={stage}
            onStage={setStage}
            revealed={revealed}
            onReveal={() => setRevealed((n) => n + 1)}
            scores={scores}
            onScore={(i, s) => setScores((prev) => new Map(prev).set(i, s))}
            onRestart={restart}
          />
        )}
      </Card>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ the run */

function Run({
  roleplay,
  prepMinutes,
  presentMinutes,
  formatLabel,
  roles,
  stage,
  onStage,
  revealed,
  onReveal,
  scores,
  onScore,
  onRestart,
}: {
  roleplay: Roleplay;
  prepMinutes: number;
  presentMinutes: number;
  formatLabel: string;
  roles: number;
  stage: Stage;
  onStage: (s: Stage) => void;
  revealed: number;
  onReveal: () => void;
  scores: Map<number, PiScore>;
  onScore: (index: number, score: PiScore) => void;
  onRestart: () => void;
}) {
  const allAsked = revealed >= roleplay.judgeQuestions.length;

  return (
    <div className="mt-5">
      <StageRail stage={stage} />

      {stage === "brief" ? (
        <Brief
          roleplay={roleplay}
          prepMinutes={prepMinutes}
          presentMinutes={presentMinutes}
          formatLabel={formatLabel}
          roles={roles}
          onStart={() => onStage("prep")}
        />
      ) : null}

      {/* Mounted only while `stage === "prep"`. The judge block is not rendered
          anywhere in this branch — that absence IS the feature. */}
      {stage === "prep" ? (
        <Prep
          roleplay={roleplay}
          minutes={prepMinutes}
          onPresent={() => onStage("present")}
        />
      ) : null}

      {stage === "present" ? (
        <Present
          roleplay={roleplay}
          minutes={presentMinutes}
          revealed={revealed}
          onReveal={onReveal}
          allAsked={allAsked}
          onDebrief={() => onStage("debrief")}
        />
      ) : null}

      {stage === "debrief" ? (
        <Debrief
          roleplay={roleplay}
          scores={scores}
          onScore={onScore}
          onRestart={onRestart}
          className="mt-6"
        />
      ) : null}
    </div>
  );
}

function StageRail({ stage }: { stage: Stage }) {
  const at = STAGES.findIndex((s) => s.key === stage);
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      {STAGES.map((s, i) => (
        <li key={s.key} className="flex items-center gap-2">
          {i > 0 ? <span aria-hidden className="text-ink/25">→</span> : null}
          <span
            aria-current={i === at ? "step" : undefined}
            className={cn(
              i === at
                ? "marker font-semibold text-ink"
                : i < at
                ? "text-ink/50"
                : "text-ink/30",
            )}
          >
            {s.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

/* --------------------------------------------------------------- 1. Brief */

function Brief({
  roleplay,
  prepMinutes,
  presentMinutes,
  formatLabel,
  roles,
  onStart,
}: {
  roleplay: Roleplay;
  prepMinutes: number;
  presentMinutes: number;
  formatLabel: string;
  roles: number;
  onStart: () => void;
}) {
  return (
    <div className="mt-6 flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-ink/70">
        <span>{formatLabel}</span>
        {/* PFL is the one event DECA publishes no career cluster for — render
            nothing rather than "General" (plan 11 §2a note 3). */}
        {roleplay.careerCluster ? (
          <>
            <span aria-hidden className="text-ink/25">·</span>
            <span>{roleplay.careerCluster}</span>
          </>
        ) : null}
        {roleplay.instructionalArea ? (
          <>
            <span aria-hidden className="text-ink/25">·</span>
            <span>{roleplay.instructionalArea}</span>
          </>
        ) : null}
        <span aria-hidden className="text-ink/25">·</span>
        <span>{roles === 1 ? "1 participant" : `${roles} participants`}</span>
      </div>

      {/* Every number here is from events.ts. Never from the prose below. */}
      <div className="sketch-radius flex flex-wrap gap-x-8 gap-y-3 border-2 border-ink bg-paper-2 p-4">
        <TimeFact label="to prepare" minutes={prepMinutes} />
        <TimeFact label="to present" minutes={presentMinutes} />
      </div>

      <ListBlock
        title="Performance indicators"
        note="What the judge is scoring you against."
        items={roleplay.performanceIndicators.map((p) => p.pi)}
        ordered
      />
      <ListBlock
        title="21st Century Skills"
        items={roleplay.twentyFirstCenturySkills}
      />

      {roleplay.participantInstructions ? (
        <div>
          <h3 className="font-display text-lg font-bold tracking-tight">
            Participant instructions
          </h3>
          <p className="mt-2 text-[0.95rem] leading-relaxed text-ink/80">
            {roleplay.participantInstructions}
          </p>
          {/* The boilerplate above is unreliable about timing and about whether
              there are judge questions. It is rendered verbatim on purpose (see
              the file header); this line is how we stay honest without editing
              it — and it is true of every scenario, so it reads nothing out of
              `meta`, which never reaches a display surface (F10). */}
          <p className="mt-3 border-l-2 border-line pl-3 text-sm text-muted">
            Go by the times above — they come from DECA&rsquo;s published event
            guidelines. This run finishes with the judge&rsquo;s questions.
          </p>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 border-t border-dashed border-line pt-5">
        <Button variant="primary" onClick={onStart}>
          Start prep — {prepMinutes} min →
        </Button>
        <p className="text-sm text-muted">
          The situation opens when you do. The judge stays hidden until you present.
        </p>
      </div>
    </div>
  );
}

function TimeFact({ label, minutes }: { label: string; minutes: number }) {
  return (
    <div>
      <p className="stat text-2xl font-bold leading-none">{minutes} min</p>
      <p className="marker mt-1 text-sm text-muted">{label}</p>
    </div>
  );
}

/* ---------------------------------------------------------------- 2. Prep */

function Prep({
  roleplay,
  minutes,
  onPresent,
}: {
  roleplay: Roleplay;
  minutes: number;
  onPresent: () => void;
}) {
  return (
    <div className="mt-6 flex flex-col gap-6">
      <Countdown minutes={minutes} label="prep" />

      {/* The PIs stay on screen through prep — a competitor has them on the
          sheet in front of them, and prepping without them is the wrong task. */}
      <ListBlock
        title="Performance indicators"
        items={roleplay.performanceIndicators.map((p) => p.pi)}
        ordered
        compact
      />

      <div>
        <h3 className="font-display text-lg font-bold tracking-tight">
          Event situation
        </h3>
        <SituationProse situation={roleplay.situation} className="mt-3" />
      </div>

      {roleplay.exhibit ? <ExhibitBlock exhibit={roleplay.exhibit} /> : null}

      <div className="flex flex-wrap items-center gap-3 border-t border-dashed border-line pt-5">
        <Button variant="primary" onClick={onPresent}>
          I&rsquo;m ready — start presenting →
        </Button>
        <p className="text-sm text-muted">
          You don&rsquo;t have to run the clock down. Nobody is proctoring this.
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- 3. Present */

function Present({
  roleplay,
  minutes,
  revealed,
  onReveal,
  allAsked,
  onDebrief,
}: {
  roleplay: Roleplay;
  minutes: number;
  revealed: number;
  onReveal: () => void;
  allAsked: boolean;
  onDebrief: () => void;
}) {
  return (
    <div className="mt-6 flex flex-col gap-6">
      <Countdown minutes={minutes} label="presenting" />

      {roleplay.judgeCharacterization ? (
        <div>
          <TapeLabel color="support" rotate={-2}>
            who you&rsquo;re talking to
          </TapeLabel>
          <p className="mt-2.5 text-[0.95rem] leading-relaxed text-ink/85">
            {roleplay.judgeCharacterization}
          </p>
        </div>
      ) : null}

      {/* The exhibit stays up — the numbers are what you're arguing from. The
          situation collapses, so the questions have the screen. */}
      {roleplay.exhibit ? <ExhibitBlock exhibit={roleplay.exhibit} /> : null}

      <details className="sketch-radius border-2 border-ink/20 bg-paper-2 px-4 py-3">
        <summary className="marker cursor-pointer text-sm text-muted">
          Re-read the situation
        </summary>
        <SituationProse situation={roleplay.situation} className="mt-3" />
      </details>

      <div className="border-t border-dashed border-line pt-5">
        <h3 className="font-display text-lg font-bold tracking-tight">
          The judge&rsquo;s questions
        </h3>
        <p className="mt-1.5 text-sm text-ink/70">
          One at a time, the way they&rsquo;d actually land. Answer out loud before
          you reveal the next one.
        </p>
        <JudgeQuestions
          questions={roleplay.judgeQuestions}
          revealed={revealed}
          onReveal={onReveal}
          className="mt-4"
        />
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-dashed border-line pt-5">
        <Button variant={allAsked ? "primary" : "outline"} onClick={onDebrief}>
          Finish — score yourself →
        </Button>
        {!allAsked ? (
          <p className="text-sm text-muted">
            You can stop here, but there are still questions you haven&rsquo;t seen.
          </p>
        ) : null}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ parts */

function ListBlock({
  title,
  note,
  items,
  ordered = false,
  compact = false,
}: {
  title: string;
  note?: string;
  items: string[];
  ordered?: boolean;
  compact?: boolean;
}) {
  if (items.length === 0) return null;

  // PI and 21st-Century-Skill counts run 3–7 and 3–4 across the fixtures and come
  // from the JSON, never from `events.ts`'s nominal `piCount` — the generator is
  // what decided how many this scenario actually carries.
  const listClass = cn(
    "mt-2.5 flex flex-col gap-1.5 pl-5 text-[0.95rem] text-ink/85",
    ordered ? "list-decimal" : "list-disc",
  );
  const rows = items.map((item, i) => <li key={i}>{item}</li>);

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3
          className={cn(
            "font-display font-bold tracking-tight",
            compact ? "text-base" : "text-lg",
          )}
        >
          {title}
        </h3>
        <span className="marker text-sm text-muted">{items.length}</span>
      </div>
      {note ? <p className="mt-1 text-sm text-ink/70">{note}</p> : null}
      {ordered ? <ol className={listClass}>{rows}</ol> : <ul className={listClass}>{rows}</ul>}
    </div>
  );
}

function ConfirmEnd({
  onKeepGoing,
  onEnd,
}: {
  onKeepGoing: () => void;
  onEnd: () => void;
}) {
  const keepRef = React.useRef<HTMLButtonElement>(null);
  // Land focus on the safe option, so Enter on a confirm you didn't mean to open
  // keeps the run rather than ending it.
  React.useEffect(() => {
    keepRef.current?.focus();
  }, []);

  return (
    // `role="alert"`, not `alertdialog`: this is an inline panel inside a dialog
    // that already owns the focus trap. A second modal role over the first is how
    // an overlay becomes one you can't get out of.
    <div role="alert" className="sketch-radius mt-4 border-2 border-ink bg-highlight/30 p-4">
      <p className="text-[0.95rem] font-semibold">End this run?</p>
      <p className="mt-1 text-sm text-ink/75">
        Your timer and any self-scores go with it — nothing from a roleplay is
        saved yet.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button ref={keepRef} variant="primary" size="sm" onClick={onKeepGoing}>
          Keep going
        </Button>
        <Button variant="outline" size="sm" onClick={onEnd}>
          End run
        </Button>
      </div>
    </div>
  );
}

function Degraded({
  title,
  body,
  onClose,
}: {
  title: string;
  body: string;
  onClose: () => void;
}) {
  return (
    <div className="mt-6 border-t border-dashed border-line pt-6">
      <h3 className="font-display text-xl font-bold tracking-tight">{title}</h3>
      <p className="mt-2 text-[0.95rem] text-ink/75">{body}</p>
      <Button variant="outline" size="sm" className="mt-5" onClick={onClose}>
        ← Back to the day
      </Button>
    </div>
  );
}

/* --------------------------------------------------------------- the clock */

/**
 * A display-only countdown. Skippable, pausable, and it does not gate anything:
 * a student practising at their desk is not being proctored (plan 11 §4b).
 *
 * The clock is read inside an effect and never during render, and this only ever
 * mounts inside `Dialog`, which returns null until hydrated — so no countdown is
 * server-rendered and there is no hydration mismatch to reintroduce.
 *
 * Remaining time is recomputed from a wall-clock delta rather than decremented
 * per tick, so a backgrounded tab (where timers are throttled) resumes at the
 * right number instead of drifting minutes behind.
 *
 * No CSS transition on the bar: it is information, updated four times a second,
 * and animating it would be motion this app lets you switch off.
 */
function Countdown({ minutes, label }: { minutes: number; label: string }) {
  const totalMs = minutes * 60_000;
  const [remaining, setRemaining] = React.useState(totalMs);
  const [running, setRunning] = React.useState(true);
  // Reset has to re-run the interval effect even when `running` was already true
  // — otherwise the next tick recomputes from the OLD base and stamps the reset
  // straight back off. A counter in the deps is what makes "reset while running"
  // actually restart the clock.
  const [runId, setRunId] = React.useState(0);
  const remainingRef = React.useRef(totalMs);

  React.useEffect(() => {
    if (!running) return;
    const base = remainingRef.current;
    const startedAt = Date.now();
    const id = window.setInterval(() => {
      const next = Math.max(0, base - (Date.now() - startedAt));
      remainingRef.current = next;
      setRemaining(next);
      if (next === 0) setRunning(false);
    }, 250);
    return () => window.clearInterval(id);
  }, [running, runId]);

  const reset = () => {
    remainingRef.current = totalMs;
    setRemaining(totalMs);
    setRunning(true);
    setRunId((n) => n + 1);
  };

  const expired = remaining === 0;
  const mins = Math.floor(remaining / 60_000);
  const secs = Math.floor((remaining % 60_000) / 1000);
  const pct = totalMs === 0 ? 0 : (remaining / totalMs) * 100;

  return (
    <div className="sketch-radius border-2 border-ink bg-paper-2 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          {/* aria-live is off on purpose: a value that changes 4×/second would
              make a screen reader unusable. The state is announced by the
              buttons and by the "time's up" line instead. */}
          <p
            role="timer"
            aria-live="off"
            className={cn(
              "stat text-3xl font-bold leading-none tabular-nums",
              expired && "text-[var(--result-wrong-ink)]",
            )}
          >
            {mins}:{String(secs).padStart(2, "0")}
          </p>
          <p className="marker text-sm text-muted">
            {expired ? "time’s up" : `${label} · ${minutes} min`}
          </p>
        </div>
        <div className="flex gap-2">
          {!expired ? (
            <Button variant="ghost" size="sm" onClick={() => setRunning((r) => !r)}>
              {running ? "Pause" : "Resume"}
            </Button>
          ) : null}
          <Button variant="ghost" size="sm" onClick={reset}>
            Reset
          </Button>
        </div>
      </div>

      <div
        aria-hidden
        className="mt-3 h-2 w-full overflow-hidden rounded-full border border-ink/20 bg-paper"
      >
        <div
          className={cn("h-full", expired ? "bg-[var(--result-wrong-line)]" : "bg-accent")}
          style={{ width: `${pct}%` }}
        />
      </div>

      {expired ? (
        <p className="mt-2.5 text-sm text-muted">
          That&rsquo;s the real limit — but the clock doesn&rsquo;t stop you. Carry
          on, or move to the next step whenever you like.
        </p>
      ) : null}
    </div>
  );
}
