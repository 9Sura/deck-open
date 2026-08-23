"use client";

import * as React from "react";

/**
 * Shared primitives for every seasonal particle overlay (snow, petals, seeds).
 * Each overlay is a sibling component under <ThemeEffects>, and they
 * all need the same two SSR-safe building blocks — factored here so the safety
 * contract from first-snow plan §3 is written once, not copy-pasted per season.
 */

/**
 * false on the server, true once mounted — the client-only mount guard (same
 * pattern as ui/dialog.tsx & live-quiz-modal.tsx). Every overlay renders null
 * until hydrated so the server emits no particle DOM to mismatch.
 */
export function useHydrated(): boolean {
  return React.useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

/**
 * Deterministic hash in [0, 1) from a particle index + attribute salt — the
 * classic fract(sin·k) trick. Stable across renders and SSR-safe (never
 * Math.random()), so each particle's placement is fixed by its index alone and
 * there is nothing to diverge even if it ever rendered on the server.
 */
export function hash(i: number, salt: number): number {
  const x = Math.sin((i + 1) * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
}
