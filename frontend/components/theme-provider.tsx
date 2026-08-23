"use client";

import * as React from "react";
import {
  DEFAULT_THEME,
  THEME_STORAGE_KEY,
  isThemeId,
  type ThemeId,
} from "@/lib/themes";

interface ThemeContextValue {
  theme: ThemeId;
  setTheme: (id: ThemeId) => void;
}

const ThemeContext = React.createContext<ThemeContextValue | null>(null);

/**
 * The `<html data-theme>` attribute IS the store — the FOUC head script sets it
 * before first paint, `setTheme` writes it, and we subscribe React to it via
 * `useSyncExternalStore`. This avoids a setState-in-effect (repo lint) and any
 * flash-then-snap: the client's first snapshot already reflects what the head
 * script applied.
 */
const listeners = new Set<() => void>();

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

function getSnapshot(): ThemeId {
  const attr = document.documentElement.getAttribute("data-theme");
  return isThemeId(attr) ? attr : DEFAULT_THEME;
}

// The server has no DOM/localStorage — render the default and let the head
// script + first client snapshot correct it before paint.
function getServerSnapshot(): ThemeId {
  return DEFAULT_THEME;
}

function applyTheme(id: ThemeId): void {
  document.documentElement.setAttribute("data-theme", id);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, id);
  } catch {
    /* localStorage blocked — selection just won't persist this session */
  }
  listeners.forEach((fn) => fn());
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = React.useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot,
  );

  const value = React.useMemo<ThemeContextValue>(
    () => ({ theme, setTheme: applyTheme }),
    [theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = React.useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
