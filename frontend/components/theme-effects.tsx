"use client";

import * as React from "react";
import { useTheme } from "@/components/theme-provider";
import { useEffectsEnabled } from "@/hooks/use-effects-enabled";
import { Snowfall } from "@/components/snowfall";
import { Petals } from "@/components/petalfall";
import { SeedDrift } from "@/components/seeddrift";
import { THEMES, type ThemeEffect } from "@/lib/themes";

/**
 * The generic effects layer. Mounted ONCE in app/layout.tsx inside
 * <ThemeProvider> (so useTheme resolves), it looks up the active theme's
 * optional `effect` and renders the matching overlay, or nothing.
 *
 * A seasonal theme is (base tokens) + (optional effect); the two never mix.
 * Adding a future season = a new component + one entry in EFFECTS. The shared
 * wrapper solves the cross-cutting concerns once: z-40 sits it in FRONT of page
 * content but BEHIND the nav and modals (both z-50) — so a modal's backdrop-blur
 * samples the snow behind it — and pointer-events-none / aria-hidden keep it out
 * of input and the a11y tree. See first-snow plan §1.2 & §3.3.
 */
const EFFECTS: Record<ThemeEffect, React.ReactNode> = {
  snow: <Snowfall />,
  petals: <Petals />,
  seeds: <SeedDrift />,
};

export function ThemeEffects() {
  const { theme } = useTheme();
  const { enabled } = useEffectsEnabled();
  const effect = THEMES.find((t) => t.id === theme)?.effect;
  if (!effect || !enabled) return null;

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-40 overflow-hidden"
    >
      {EFFECTS[effect]}
    </div>
  );
}
