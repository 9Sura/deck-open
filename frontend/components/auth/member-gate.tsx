"use client";

// Route-side half of the guest funnel (issue #33). The click-side guard
// (`useRequireAccount` on the nav button + the marketing CTAs) only covers
// clicks made INSIDE the app, so a bookmark, a shared link, browser history or a
// search result handed a signed-out visitor the full member feature. This wraps
// `main` and renders a sign-up panel IN PLACE of the page for every route in
// MEMBER_ROUTES — the deep link still lands somewhere meaningful, and signing up
// is one click away.
//
// In place rather than a redirect on purpose: bouncing a shared /vocab link to
// the homepage looks broken and says nothing about why. The empty analytics
// pages (/progress, /review) keep the redirect — see route-guard.tsx.
//
// SSR/flash: the server has no session and the first client paint starts with
// none either, so both render the skeleton while a configured project's session
// is in flight, then swap once it resolves — no hydration mismatch and no
// member content painted for a guest. Non-gated routes never wait on auth.
// Zero-Supabase builds (`configured: false`) pass everything straight through.

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { MarkerText } from "@/components/marker-text";
import { TapeLabel } from "@/components/tape-label";
import { LockGlyph } from "@/components/dev-lock";
import { useAuth } from "@/components/auth/auth-provider";
import { useRequireAccount } from "@/components/auth/guest-gate";
import { MEMBER_ROUTES, hasFullAccess, matchesRoute } from "@/lib/auth/gated-routes";

interface Pitch {
  eyebrow: string;
  title: string;
  blurb: string;
}

const PITCH: Record<string, Pitch> = {
  "/test-generator": {
    eyebrow: "practice tests",
    title: "Practice tests come with an account",
    blurb:
      "Build a difficulty-mixed test for any cluster and level, then study it question by question. An account is what lets us keep score — every answer feeds your progress and your error log.",
  },
  "/vocab": {
    eyebrow: "vocab terms",
    title: "Vocab terms come with an account",
    blurb:
      "Event-specific DECA terms with definitions and why-it-matters notes. An account remembers which ones you've got down, so you're not restarting the deck every session.",
  },
  // Live since phase C — the pitch must not still describe the retired,
  // unfinished feature (#51). What it can honestly promise is the run: a day
  // board over a real (small) archive, stepping brief → prep → present →
  // debrief. The archive's thinness is named rather than hidden, and no string
  // here claims verified difficulty (plan 11 F5).
  "/roleplay": {
    eyebrow: "roleplays",
    title: "Roleplays come with an account",
    blurb:
      "Role-play case studies you run start to finish — brief, prep, presentation, then a debrief against the performance indicators, with the judge's questions held back until prep is over. The day rolls over at midnight Eastern for everyone, and the archive is young — a handful of scenarios so far, with more days filling in.",
  },
};

const FALLBACK: Pitch = {
  eyebrow: "members only",
  title: "This one comes with an account",
  blurb:
    "Create a free account to unlock it — your progress saves and syncs across your devices.",
};

export function MemberGate({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const { loading } = auth;
  const pathname = usePathname();

  const gated = !hasFullAccess(auth) && matchesRoute(pathname, MEMBER_ROUTES);

  // Only hold the page back while a gated route's session is still resolving —
  // an open route must never wait on auth.
  if (gated && loading) return <GateSkeleton />;
  if (!gated) return <>{children}</>;

  const prefix = MEMBER_ROUTES.find((p) => matchesRoute(pathname, [p]));
  return <SignUpPanel pitch={(prefix && PITCH[prefix]) || FALLBACK} />;
}

function SignUpPanel({ pitch }: { pitch: Pitch }) {
  const { open, dialog } = useRequireAccount();

  return (
    <div className="mx-auto max-w-2xl px-5 py-16 sm:px-8">
      <Card variant={1} className="p-7 text-center sm:p-10">
        <div className="mb-4 flex justify-center">
          <LockGlyph className="h-11 w-11 text-ink/75" />
        </div>
        <div className="mb-3 flex justify-center">
          <TapeLabel color="accent" rotate={-2}>
            free account
          </TapeLabel>
        </div>
        <MarkerText rotate={-2} className="text-base">
          {pitch.eyebrow}
        </MarkerText>
        <h1 className="mt-2 font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
          {pitch.title}
        </h1>
        <p className="mx-auto mt-4 max-w-md text-[0.95rem] leading-relaxed text-ink/70">
          {pitch.blurb}
        </p>

        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Button variant="primary" size="md" onClick={open}>
            Create a free account
          </Button>
          <Button asChild variant="outline" size="md">
            <Link href="/question-bank">Browse the question bank</Link>
          </Button>
        </div>

        <p className="mt-5 text-xs text-muted">
          No email needed — just a username and a password. Free while in beta.
        </p>
      </Card>
      {dialog}
    </div>
  );
}

function GateSkeleton() {
  return (
    <div className="mx-auto max-w-2xl px-5 py-16 sm:px-8" aria-hidden>
      <div className="h-80 animate-pulse rounded-2xl border-2 border-line bg-paper-2" />
    </div>
  );
}
