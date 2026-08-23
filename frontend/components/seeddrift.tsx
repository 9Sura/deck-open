"use client";

import * as React from "react";
import { DandelionSeed } from "@/components/doodles";
import { usePrefersReducedMotion } from "@/hooks/use-prefers-reduced-motion";
import { useHydrated, hash } from "@/components/particle-field";

/**
 * Midsummer's seed drift — dandelion seeds carried UP on a warm sunset breeze.
 * The one overlay that rises: snow and petals fall, so a buoyant
 * upward drift reads unmistakably as a lazy summer evening (and shows on a light
 * sky where a glowing dot never would).
 *
 * Two nested clocks (see <Petals>): the OUTER <span> only rises bottom→top
 * (linear); the INNER tuft sways and gently rocks on its own shorter clock
 * (ease-in-out, ALTERNATE) — so no two seeds trace the same path.
 *
 * Same safety contract as <Snowfall> (first-snow plan §3): client-only mount,
 * render null under reduced motion (a frozen scatter is worse than none),
 * index-derived positions (never Math.random), transform+opacity only.
 */
const SEEDS = 14;

/** Warm sunset palette — sepia · amber · terracotta, cycled by index so each
 *  seed reads against the apricot sky. */
const SEED_COLORS = ["#c9743f", "#b95a3c", "#caa15a", "#d98f4a", "#a86a4a"];

/** OUTER span: horizontal spot + size + the vertical rise clock. */
function riseStyle(i: number): React.CSSProperties {
  const left = hash(i, 1) * 100; // vw spread, %
  const size = 14 + hash(i, 2) * 10; // 14–24px
  const opacity = 0.55 + hash(i, 3) * 0.3; // 0.55–0.85
  const duration = 11 + hash(i, 4) * 9; // 11–20s rise
  const delay = -hash(i, 5) * 20; // pre-roll so the air starts already full

  return {
    left: `${left.toFixed(2)}%`,
    width: `${size.toFixed(1)}px`,
    height: `${size.toFixed(1)}px`,
    animationDuration: `${duration.toFixed(2)}s`,
    animationDelay: `${delay.toFixed(2)}s`,
    ["--seed-opacity" as string]: opacity.toFixed(2),
  };
}

/** INNER tuft: its own sway clock + tint + sway amplitude. */
function swayStyle(i: number): React.CSSProperties {
  const duration = 2.8 + hash(i, 6) * 2.7; // 2.8–5.5s sway (independent of the rise)
  const delay = -hash(i, 7) * 5;
  const sway = 14 + hash(i, 8) * 16; // 14–30px lateral rock

  return {
    color: SEED_COLORS[i % SEED_COLORS.length],
    animationDuration: `${duration.toFixed(2)}s`,
    animationDelay: `${delay.toFixed(2)}s`,
    ["--sway" as string]: `${sway.toFixed(0)}px`,
  };
}

export function SeedDrift() {
  const hydrated = useHydrated();
  const reduced = usePrefersReducedMotion();

  if (!hydrated || reduced) return null;

  return (
    <>
      {Array.from({ length: SEEDS }, (_, i) => (
        <span key={i} className="seed" style={riseStyle(i)}>
          <DandelionSeed className="seed-tuft" style={swayStyle(i)} width="100%" height="100%" />
        </span>
      ))}
    </>
  );
}
