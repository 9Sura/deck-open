"use client";

import * as React from "react";
import { useTheme } from "@/components/theme-provider";
import { useEffectsEnabled } from "@/hooks/use-effects-enabled";
import { Bracket } from "@/components/accents";
import { THEMES } from "@/lib/themes";
import { cn } from "@/lib/utils";

/**
 * True when `month` (1-indexed) falls inside a theme's [start, end] season
 * window, INCLUSIVE and WRAP-AWARE: a window that crosses the year-end like
 * [12, 2] (Dec–Feb) is true for 12, 1, and 2. See first-snow plan §5.
 */
function inSeason([start, end]: [number, number], month: number): boolean {
  return start <= end
    ? month >= start && month <= end
    : month >= start || month <= end;
}

/** false on the server, true once mounted — so the client-only "in season" badge
 *  (which reads `new Date()`) never diverges from the server's first paint. */
function useHydrated(): boolean {
  return React.useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

/**
 * The Themes tab — a grid of theme cards, one per registry entry. Clicking
 * `setTheme(id)` live-applies through the provider, so the whole app re-skins
 * behind the blurred settings popup instantly (and persists to localStorage).
 * Swatch chips are drawn from the registry hexes, so each card previews ITS OWN
 * palette regardless of the currently-active theme.
 */
export function ThemePicker() {
  const { theme, setTheme } = useTheme();
  const { enabled: effectsOn, setEnabled: setEffectsOn } = useEffectsEnabled();
  const hydrated = useHydrated();
  // Client-side month (1-indexed). Gated behind `hydrated` at the badge, so the
  // server never renders it and there is no SSR/timezone mismatch.
  const month = new Date().getMonth() + 1;

  return (
    <div className="flex flex-col gap-4">
      {/* Animated-effects switch — governs the seasonal overlays (petals, seeds,
          snow). Global preference, so it reads as "off" even under a non-seasonal
          theme where nothing is currently drawn. */}
      <div className="flex items-center justify-between gap-4 rounded-2xl border-2 border-line bg-paper px-4 py-3">
        <span className="flex min-w-0 flex-col">
          <span className="font-display text-sm font-bold tracking-tight">
            Animated effects
          </span>
          <span className="text-xs leading-snug text-muted">
            Seasonal overlays — petals, seeds &amp; snow. (Motion also respects
            your system&rsquo;s reduce-motion setting.)
          </span>
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={effectsOn}
          aria-label="Animated theme effects"
          onClick={() => setEffectsOn(!effectsOn)}
          className={cn(
            "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 border-ink transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
            effectsOn ? "bg-accent" : "bg-paper-2",
          )}
        >
          <span
            className={cn(
              "inline-block h-4 w-4 rounded-full bg-ink transition-transform",
              effectsOn ? "translate-x-5" : "translate-x-0.5",
            )}
          />
        </button>
      </div>

      <div
        role="group"
        aria-label="Theme"
        className="grid grid-cols-1 gap-3 sm:grid-cols-2"
      >
        {THEMES.map((t) => {
        const active = theme === t.id;
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => setTheme(t.id)}
            aria-pressed={active}
            className={cn(
              "flex flex-col gap-2.5 rounded-2xl border-2 p-4 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
              active
                ? "border-ink bg-paper-2 shadow-[var(--btn-shadow)]"
                : "border-line bg-paper hover:-translate-y-0.5 hover:border-ink/40",
            )}
          >
            {/* Swatch preview — 4 chips (paper·ink·accent·highlight) in an
                inked frame so the preview itself looks hand-drawn. The rare
                "in season" flag rides the swatch's top-right corner so it never
                competes with the label + mode badge for row width. */}
            <span
              aria-hidden
              className="relative hand-border flex h-8 overflow-hidden rounded-md"
            >
              {t.swatch.map((hex, i) => (
                <span
                  key={i}
                  style={{ background: hex }}
                  className="h-full flex-1"
                />
              ))}
              {hydrated && t.seasonWindow && inSeason(t.seasonWindow, month) && (
                <span className="marker absolute right-1 top-1 rounded bg-highlight px-1.5 py-0.5 text-[0.6rem] leading-none text-highlight-ink shadow-sm ring-1 ring-ink/10">
                  in season ✨
                </span>
              )}
            </span>

            <span className="flex items-center justify-between gap-2">
              {active ? (
                <Bracket color="ink" className="font-display text-lg font-bold tracking-tight">
                  {t.label}
                </Bracket>
              ) : (
                <span className="font-display text-lg font-bold tracking-tight">
                  {t.label}
                </span>
              )}
              <span
                className={cn(
                  "marker shrink-0 rounded px-1.5 py-0.5 text-[0.65rem] leading-none",
                  t.mode === "dark"
                    ? "bg-support/15 text-support-ink"
                    : "bg-highlight/30 text-highlight-ink",
                )}
              >
                {t.mode}
              </span>
            </span>

            <span className="text-sm leading-snug text-muted">{t.blurb}</span>
          </button>
        );
      })}
      </div>
    </div>
  );
}
