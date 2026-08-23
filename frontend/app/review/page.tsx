"use client";

// The /review route (plan 08 phase 3 sub-plan §7, D6). A thin client wrapper in the
// notebook aesthetic — header chrome + the data-driven <ReviewLab/>. Client-rendered
// with data read on mount (no server fetch); the lab is hydration-guarded so the server
// + first paint render the empty state and nothing touches IndexedDB on the server.

import Link from "next/link";
import { MarkerText } from "@/components/marker-text";
import { ArrowScribble } from "@/components/doodles";
import { ReviewLab } from "@/components/review/review-lab";

export default function ReviewPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8">
      <Link href="/progress" className="text-sm text-muted hover:text-ink">
        ← Back to progress
      </Link>

      <div className="mt-4 flex items-start justify-between gap-4">
        <div>
          <MarkerText rotate={-3} className="text-base">
            close the loop
          </MarkerText>
          <h1 className="mt-1 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
            Review your <span className="text-accent">misses</span>
          </h1>
        </div>
        <ArrowScribble className="hidden h-14 w-20 text-ink/70 sm:block" />
      </div>

      <ReviewLab />
    </div>
  );
}
