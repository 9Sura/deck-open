// One event's tile on the day board (frontend plan 11 §4a/§4c).
//
// Every card's numbers — PI count, prep/present minutes, participant count —
// come from `EVENTS` in lib/data/events.ts and NEVER from the roleplay text: the
// generated PARTICIPANT INSTRUCTIONS boilerplate is measurably unreliable about
// timing (it says "no time for judge questions" and then asks three), which is a
// backend defect the frontend must not paper over (plan 11 §2a note 4).
//
// The unavailable state is a FIRST-CLASS state, not an edge case. Until the K3
// prompt fix lands, most events fail the gate on most days, so a board where 25
// of 28 cards are greyed is the normal render. Showing them greyed is the honest
// version of that; silently rendering only the three that exist is not.
//
// An AVAILABLE card is the run surface's launcher (phase C). The whole card is
// the control — `role="button"` with a keyboard handler rather than a button
// buried in the footer — so there is exactly one focus stop per card, and so
// `Dialog`'s restore-focus-on-close lands back on the card the run was opened
// from instead of somewhere near it.

import type { KeyboardEvent } from "react";
import { Card } from "@/components/ui/card";
import { TapeLabel } from "@/components/tape-label";
import { cn } from "@/lib/utils";
import type { DecaEvent } from "@/lib/deca";

export function EventCard({
  event,
  available,
  onOpen,
  variant = 0,
}: {
  event: DecaEvent;
  available: boolean;
  /** Omitted on unavailable cards — there is nothing behind them to open. */
  onOpen?: () => void;
  variant?: number;
}) {
  const interactive = available && onOpen != null;

  return (
    <Card
      variant={variant}
      className={cn(
        "flex h-full flex-col p-5",
        !available && "opacity-55 grayscale",
        interactive &&
          "cursor-pointer transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-support/50 focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
      )}
      {...(interactive
        ? {
            role: "button",
            tabIndex: 0,
            // The name is set explicitly so a screen reader announces the action
            // rather than reciting the whole card body as the button's label.
            "aria-label": `Open ${event.name} (${event.code})`,
            onClick: onOpen,
            onKeyDown: (e: KeyboardEvent<HTMLDivElement>) => {
              // The ARIA button contract: Enter and Space both activate.
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onOpen();
              }
            },
          }
        : {})}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="marker text-sm text-muted">{event.code}</p>
        {available ? (
          <TapeLabel color="accent" rotate={3} className="shrink-0">
            {event.prepMinutes} + {event.presentMinutes} min
          </TapeLabel>
        ) : null}
      </div>

      <h4 className="mt-1 font-display text-lg font-bold leading-tight tracking-tight">
        {event.name}
      </h4>
      {/* PFL is the one event DECA publishes no career cluster for — render
          nothing rather than an invented one, exactly as the run surface does
          (plan 11 §2a note 3). */}
      {event.careerCluster ? (
        <p className="mt-1.5 text-sm text-ink/60">{event.careerCluster}</p>
      ) : null}

      <div className="mt-auto border-t border-dashed border-line pt-3">
        {available ? (
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-sm text-ink/70">
              {event.piCount} performance indicators ·{" "}
              {event.roles === 1 ? "1 participant" : "2 participants"}
            </p>
            {interactive ? (
              <span aria-hidden className="marker text-sm font-semibold text-accent">
                Run it →
              </span>
            ) : null}
          </div>
        ) : (
          <p className="marker text-sm text-muted">not available for this day</p>
        )}
      </div>
    </Card>
  );
}
