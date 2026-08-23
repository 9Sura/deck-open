"use client";

import * as React from "react";

/**
 * "Animated theme effects" preference — the on/off switch for the seasonal
 * overlays (petals / seeds / snow) that <ThemeEffects> renders.
 *
 * Backed by a single localStorage key and a module-level listener set, read via
 * useSyncExternalStore. Same shape as the theme provider (external store, no
 * setState-in-effect), but there's no DOM attribute to mirror — the overlay is
 * decorative and mounts client-side only, so a plain module store is enough and
 * needs no Context. Effects default ON; only an explicit "0" turns them off.
 *
 * Motion is still gated independently by prefers-reduced-motion in each particle
 * component, so this toggle is an *additional* opt-out, not the only one.
 */

export const EFFECTS_STORAGE_KEY = "deca-effects";

const listeners = new Set<() => void>();

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

function getSnapshot(): boolean {
  try {
    return localStorage.getItem(EFFECTS_STORAGE_KEY) !== "0";
  } catch {
    return true;
  }
}

// The server has no localStorage — default to enabled, matching the stored
// default, so the first client snapshot only ever *removes* the overlay.
function getServerSnapshot(): boolean {
  return true;
}

function setEffectsEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(EFFECTS_STORAGE_KEY, enabled ? "1" : "0");
  } catch {
    /* localStorage blocked — preference just won't persist this session */
  }
  listeners.forEach((fn) => fn());
}

export function useEffectsEnabled(): {
  enabled: boolean;
  setEnabled: (enabled: boolean) => void;
} {
  const enabled = React.useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot,
  );
  return { enabled, setEnabled: setEffectsEnabled };
}
