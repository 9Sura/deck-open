"use client";

// The one-time "your guest progress is now synced" banner (sub-plan §8). Shown
// once on /progress right after a first sign-in that migrated guest attempts,
// then cleared (read-and-clear flag). Silent if the guest had no attempts.

import * as React from "react";
import { takeMigrationNotice } from "@/lib/progress/migrate";

export function MigrationNotice() {
  const [count, setCount] = React.useState<number | null>(null);

  React.useEffect(() => {
    // Read-and-clear on mount (client only). Defer the setState to a microtask
    // so it's never a synchronous set inside the effect body (React Compiler).
    const n = takeMigrationNotice();
    if (n) Promise.resolve().then(() => setCount(n));
  }, []);

  if (!count) return null;

  return (
    <div className="sketch-radius mt-6 flex items-start justify-between gap-4 border-2 border-[var(--diff-easy-line)] bg-[var(--diff-easy-bg)]/40 px-4 py-3">
      <p className="text-sm text-ink/85">
        <span className="mr-1.5">✓</span>
        Your guest progress —{" "}
        <span className="stat font-semibold text-ink">{count}</span> answered
        question{count === 1 ? "" : "s"} — is now saved to your account and synced
        across your devices.
      </p>
      <button
        type="button"
        onClick={() => setCount(null)}
        aria-label="Dismiss"
        className="shrink-0 rounded-lg px-2 py-0.5 text-sm leading-none text-ink/50 transition-colors hover:bg-ink/5 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
      >
        ✕
      </button>
    </div>
  );
}
