"use client";

// Loads the WHOLE Attempt/Session log once for the dashboard and re-reads it
// whenever `version` bumps (plan 08 phase 2 §4, D3). Only /progress needs the
// full log in memory, so this lives in a page-scoped hook rather than the global
// provider (which is mounted on every route and must stay lean).
//
// The version→re-read wire is what makes "Practice this" feel live: finishing a
// drill launched from the dashboard writes → version bumps → this re-reads →
// mastery recomputes → the heatmap/board update with no manual refresh.
//
// Lint note (React Compiler is strict here, Phase 1): state is set in the awaited
// `.then`, never synchronously in the effect body — mirrors use-live-quiz's
// compose effect and question-bank's loadSet.

import * as React from "react";
import { useProgress } from "@/components/progress-provider";
import type { Attempt, Session } from "@/lib/progress/types";

export interface ProgressData {
  attempts: Attempt[];
  sessions: Session[];
  /** true until the first read resolves — lets the dashboard show a skeleton. */
  loading: boolean;
  /** false on the server + first client paint (SSR-safe empty state gate). */
  hydrated: boolean;
}

export function useProgressData(): ProgressData {
  const { store, version, hydrated, reportStorageError } = useProgress();

  // Literal initializers run once (state persists across renders) — stable refs
  // without a module-level const.
  const [attempts, setAttempts] = React.useState<Attempt[]>([]);
  const [sessions, setSessions] = React.useState<Session[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!hydrated) return;
    let active = true; // guard against out-of-order resolves
    Promise.all([store.getAttempts(), store.getSessions()])
      .then(([a, s]) => {
        if (!active) return;
        setAttempts(a);
        setSessions(s);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        // A read failure still falls through to the empty state — no page here
        // has a sensible error layout, and half a dashboard is worse than none.
        // But it reports, so the provider's notice can say "we couldn't load your
        // practice" instead of leaving the empty state to imply "you have none".
        reportStorageError("read", err);
        setLoading(false);
      });
    return () => {
      active = false;
    };
    // Re-read on every write (version) and once hydrated.
  }, [store, version, hydrated, reportStorageError]);

  return { attempts, sessions, loading, hydrated };
}
