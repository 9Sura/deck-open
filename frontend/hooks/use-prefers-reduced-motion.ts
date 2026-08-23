import * as React from "react";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/**
 * Track the OS "reduce motion" setting via useSyncExternalStore so there is no
 * setState-in-effect (React 19 lint) and no SSR hydration mismatch — the server
 * snapshot is always false, the client subscribes to the media query.
 *
 * Shared by the typewriter animation and the theme snowfall overlay: both must
 * fully stop (not just slow) under reduced motion, and both need the same
 * mismatch-free read. See first-snow plan §3.2.
 */
export function usePrefersReducedMotion(): boolean {
  return React.useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia(REDUCED_MOTION_QUERY);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => window.matchMedia(REDUCED_MOTION_QUERY).matches,
    () => false,
  );
}
