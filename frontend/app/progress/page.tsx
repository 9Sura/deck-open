"use client";

// The /progress dashboard route (plan 08 phase 2 §6). A thin client wrapper in
// the notebook aesthetic — header chrome + the data-driven <ProgressDashboard/>.
// Client-rendered with data read on mount (no server fetch); the dashboard is
// hydration-guarded so the server + first paint render the empty state and
// nothing touches IndexedDB on the server.

import Link from "next/link";
import { MarkerText } from "@/components/marker-text";
import { RisingChart } from "@/components/doodles";
import { ProgressDashboard } from "@/components/progress/progress-dashboard";
import { MigrationNotice } from "@/components/progress/migration-notice";

export default function ProgressPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Back home
      </Link>

      <div className="mt-4 flex items-start justify-between gap-4">
        <div>
          <MarkerText rotate={-3} className="text-base">
            your progress
          </MarkerText>
          <h1 className="mt-1 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
            Track your <span className="text-accent-ink">mastery</span>
          </h1>
        </div>
        <RisingChart className="hidden h-14 w-20 text-ink/70 sm:block" />
      </div>

      <MigrationNotice />

      <ProgressDashboard />
    </div>
  );
}
