"use client";

// Shared, theme-token-only viz primitives for the dashboard (plan 08 phase 2 §7,
// D6). Mastery is a magnitude 0→1, so it rides a SEQUENTIAL single-hue ramp
// (pale paper → accent) built with color-mix so it re-skins per theme in light
// AND dark. "Provisional" (thin-evidence) state is encoded REDUNDANTLY — a
// diagonal hatch + a glyph + muted fill — never color alone, so "not enough data"
// can't masquerade as low or high mastery.

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Sequential ramp position for a mastery value ∈ [0,1]: pale recessed paper at 0,
 * saturated accent near 1. Capped below full accent so any overlaid ink text
 * stays legible on every theme; magnitude is also carried by the numeral, so the
 * color is reinforcement, not the sole channel.
 */
export function masteryTint(mastery: number): string {
  const pct = Math.max(0, Math.min(1, mastery)) * 64; // 0–64% accent
  return `color-mix(in oklab, var(--accent) ${pct}%, var(--paper))`;
}

/** A 45° hatch over recessed paper — the provisional/low-confidence texture.
 *  Kept gentle (thin stripe, wide gap, blended toward the base) so it reads as
 *  texture rather than noise behind overlaid numerals. */
export const HATCH_BG =
  "repeating-linear-gradient(45deg, var(--paper-2) 0 5px, color-mix(in oklab, var(--line) 55%, var(--paper-2)) 5px 6.5px)";

/**
 * A horizontal mastery meter. Provisional bars are hatched + carry a "~" so a
 * thin estimate never reads as settled; uncovered (no attempts) shows a dashed
 * "not started" track instead of a fill.
 */
export function MasteryBar({
  mastery,
  provisional,
  seen,
  className,
}: {
  mastery: number;
  provisional: boolean;
  seen: boolean;
  className?: string;
}) {
  if (!seen) {
    return (
      <div
        className={cn(
          "flex h-3 items-center rounded-full border border-dashed border-line",
          className,
        )}
      >
        <span className="w-full text-center text-[0.6rem] leading-none text-muted">
          not started
        </span>
      </div>
    );
  }
  const width = `${Math.round(Math.max(0, Math.min(1, mastery)) * 100)}%`;
  return (
    <div
      className={cn("h-3 overflow-hidden rounded-full bg-paper-2", className)}
      role="meter"
      aria-valuenow={Math.round(mastery * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full rounded-full transition-[width]"
        style={
          provisional
            ? { width, background: HATCH_BG }
            : { width, background: masteryTint(Math.max(0.15, mastery)) }
        }
      />
    </div>
  );
}

/** A small pill that reads mastery as a percent, with a ~ prefix when provisional. */
export function MasteryReading({
  mastery,
  provisional,
  seen,
}: {
  mastery: number;
  provisional: boolean;
  seen: boolean;
}) {
  if (!seen) return <span className="stat text-sm text-muted">—</span>;
  return (
    <span className="stat text-sm font-semibold text-ink">
      {provisional ? "~" : ""}
      {Math.round(mastery * 100)}%
    </span>
  );
}
