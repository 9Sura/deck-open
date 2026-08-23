"use client";

import * as React from "react";
import { Snowflake } from "@/components/doodles";
import { usePrefersReducedMotion } from "@/hooks/use-prefers-reduced-motion";
import { useHydrated, hash } from "@/components/particle-field";

/**
 * The First Snow snowfall overlay — a sparse, hand-drawn drift of flakes.
 *
 * Every failure mode from first-snow plan §3 is handled HERE so the shared
 * <ThemeEffects> wrapper (z-40 / pointer-events-none / aria-hidden) stays dumb:
 *   • Hydration (§3.1): client-only mount via useHydrated — the server emits no
 *     snow DOM at all — AND positions are index-derived, never Math.random(), so
 *     there is nothing to mismatch even if it ever rendered on the server.
 *   • Reduced motion (§3.2): read the preference and render null. We must NOT
 *     lean on CSS: the global reduced-motion !important rule in globals.css would
 *     zero the fall duration and pile every flake at the bottom — worse than none.
 *   • Perf (§3.4): ~20 flakes, transform+opacity only (CSS keyframes, compositor),
 *     no rAF loop, no filter/box-shadow on moving nodes, will-change: transform.
 */
const FLAKES = 20;

/** All per-flake variety comes from its index: left, size, opacity, fall
 *  duration, a negative delay (so the sky starts already snowing), and a gentle
 *  horizontal drift fed to the keyframe via a custom property. */
function flakeStyle(i: number): React.CSSProperties {
  const left = hash(i, 1) * 100; // vw spread, %
  const size = 10 + hash(i, 2) * 14; // 10–24px
  const opacity = 0.45 + hash(i, 3) * 0.45; // 0.45–0.90
  const duration = 9 + hash(i, 4) * 9; // 9–18s
  const delay = -hash(i, 5) * 18; // pre-roll so flakes aren't all at the top
  const drift = (hash(i, 6) - 0.5) * 80; // -40–40px lateral sway

  return {
    left: `${left.toFixed(2)}%`,
    width: `${size.toFixed(1)}px`,
    height: `${size.toFixed(1)}px`,
    animationDuration: `${duration.toFixed(2)}s`,
    animationDelay: `${delay.toFixed(2)}s`,
    ["--flake-opacity" as string]: opacity.toFixed(2),
    ["--flake-drift" as string]: `${drift.toFixed(0)}px`,
  };
}

export function Snowfall() {
  const hydrated = useHydrated();
  const reduced = usePrefersReducedMotion();

  // A stopped snowfall is worse than none — render nothing rather than a frozen
  // pile (see §3.2). Server render is also empty (hydrated=false).
  if (!hydrated || reduced) return null;

  return (
    <>
      {Array.from({ length: FLAKES }, (_, i) => (
        <Snowflake key={i} className="snowflake" style={flakeStyle(i)} />
      ))}
    </>
  );
}
