"use client";

import * as React from "react";
import { Petal } from "@/components/doodles";
import { usePrefersReducedMotion } from "@/hooks/use-prefers-reduced-motion";
import { useHydrated, hash } from "@/components/particle-field";

/**
 * First Bloom's petal drift — blossom petals that flutter DOWN while swaying and
 * rocking, a distinctly springtime motion (vs. snow's near-straight fall).
 *
 * The realistic flutter comes from nesting two transforms on independent clocks:
 * the OUTER <span> only falls top→bottom (linear), while the INNER blade sways
 * side-to-side and rotates (ease-in-out, ALTERNATE, ~⅓ the fall period). Because
 * the two periods rarely divide evenly, no two petals trace the same path.
 *
 * Same safety contract as <Snowfall> (first-snow plan §3): client-only mount,
 * render null under reduced motion (a frozen petal pile is worse than none),
 * index-derived positions (never Math.random), transform+opacity only.
 */
const PETALS = 16;

/** Blossom palette — soft pinks + cream, cycled by index for organic variety. */
const PETAL_COLORS = ["#f6c4d6", "#f2a9c4", "#fbdbe6", "#f7d0b8", "#efb3cd"];

/** OUTER span: horizontal spot + size + the vertical fall clock. */
function fallStyle(i: number): React.CSSProperties {
  const left = hash(i, 1) * 100; // vw spread, %
  const size = 12 + hash(i, 2) * 12; // 12–24px
  const opacity = 0.5 + hash(i, 3) * 0.4; // 0.50–0.90
  const duration = 10 + hash(i, 4) * 8; // 10–18s fall
  const delay = -hash(i, 5) * 18; // pre-roll so the air starts already full

  return {
    left: `${left.toFixed(2)}%`,
    width: `${size.toFixed(1)}px`,
    height: `${size.toFixed(1)}px`,
    animationDuration: `${duration.toFixed(2)}s`,
    animationDelay: `${delay.toFixed(2)}s`,
    ["--petal-opacity" as string]: opacity.toFixed(2),
  };
}

/** INNER blade: its own sway clock + tint + sway amplitude. */
function swayStyle(i: number): React.CSSProperties {
  const duration = 2.5 + hash(i, 6) * 2.5; // 2.5–5s sway (independent of the fall)
  const delay = -hash(i, 7) * 5;
  const sway = 12 + hash(i, 8) * 16; // 12–28px lateral rock

  return {
    color: PETAL_COLORS[i % PETAL_COLORS.length],
    animationDuration: `${duration.toFixed(2)}s`,
    animationDelay: `${delay.toFixed(2)}s`,
    ["--sway" as string]: `${sway.toFixed(0)}px`,
  };
}

export function Petals() {
  const hydrated = useHydrated();
  const reduced = usePrefersReducedMotion();

  // A stopped drift is worse than none — render nothing rather than a frozen
  // pile (see §3.2). Server render is also empty (hydrated=false).
  if (!hydrated || reduced) return null;

  return (
    <>
      {Array.from({ length: PETALS }, (_, i) => (
        <span key={i} className="petal" style={fallStyle(i)}>
          <Petal className="petal-blade" style={swayStyle(i)} width="100%" height="100%" />
        </span>
      ))}
    </>
  );
}
