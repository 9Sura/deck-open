"use client";

// The marketing landing (plan 09 §4.4) — the GUEST home, extracted verbatim from
// the old app/page.tsx. Now a client component so a guest's practice CTAs funnel
// to sign-up (D7): one capturing click handler intercepts clicks on the gated
// practice routes and opens the create-account dialog instead of navigating. The
// Question Bank CTA is the one open surface, so it still routes; #anchors and the
// hero all pass through. With no Supabase project (needsAccount=false) every CTA
// navigates as it does today — the app stays fully usable account-free.

import * as React from "react";
import type { ComponentProps } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Loop } from "@/components/loop";
import { Highlight } from "@/components/highlight";
import { Underline } from "@/components/accents";
import { MarkerText } from "@/components/marker-text";
import { AnimatedSection } from "@/components/animated-section";
import { ToolCard } from "@/components/tool-card";
import { ToolCarousel } from "@/components/tool-carousel";
import { useRequireAccount } from "@/components/auth/guest-gate";
import { MEMBER_ROUTES } from "@/lib/auth/gated-routes";
import { BANK_SIZE_LABEL } from "@/lib/question-bank";
import { PI_COVERAGE_LABEL } from "@/lib/progress/inventory";
import {
  ArrowScribble,
  RisingChart,
  Sparkle,
  StarBurst,
  Lightbulb,
  Clipboard,
  StickyNote,
} from "@/components/doodles";

const TOOLS: ComponentProps<typeof ToolCard>[] = [
  {
    href: "/test-generator",
    eyebrow: "MULTIPLE CHOICE",
    title: "Practice Test Generator",
    // No "unlimited", no "fresh every time" (#108). The live-JIT path was
    // dropped, so composeTest draws from the committed bank — a cluster×level's
    // distinct draws are finite. The composition genuinely IS on demand and the
    // mix genuinely does vary, so that half of the claim stays. The tape states
    // the bank size off BANK_SIZE_LABEL (floored, so it can't go stale).
    blurb:
      "Cluster exams built to order from the question bank — every question tagged with its instructional area, a best answer, and an explanation.",
    cta: "Generate a test",
    tape: BANK_SIZE_LABEL,
    tapeColor: "support",
    variant: 0,
    doodle: <RisingChart className="h-14 w-auto" />,
  },
  {
    href: "/question-bank",
    eyebrow: "CURATED SETS",
    title: "Question Bank",
    blurb:
      "Pre-built, ready-to-study exam sets — pick a cluster, then a set, then your level and start practicing right away.",
    cta: "Browse the bank",
    tape: "READY-MADE",
    tapeColor: "highlight",
    variant: 2,
    doodle: <StickyNote className="h-14 w-auto" />,
  },
  {
    href: "/vocab",
    eyebrow: "FLASHCARDS",
    title: "Vocab Terms",
    blurb:
      "Event-specific DECA terms with definitions, why-it-matters notes, and quick progress tracking.",
    cta: "Study vocab",
    tape: "FLASHCARDS",
    tapeColor: "support",
    variant: 1,
    doodle: <Lightbulb className="h-14 w-auto" />,
  },
  {
    // Was a locked "Roleplay Generator" card. That feature is gone — a static
    // site has nowhere to run a model per request — and /roleplay is now the
    // daily challenge, so the card names what it actually links to.
    href: "/roleplay",
    eyebrow: "CASE STUDY",
    title: "Roleplay Challenge",
    // The daily framing is TRUE OF THE MECHANISM and false of the archive
    // (#108): the board really does drop on Eastern midnight, but the only days
    // on disk are the 7 committed fixtures across 3 sparse days, because
    // fill_buffer.py (backend plan 03 step 6) has never been run. So the card
    // names what a guest actually finds. RESTORE "NEW DAILY" and the "each day"
    // blurb in the same change that ships the first generated batch — TOGETHER
    // WITH the H1 in app/roleplay/page.tsx, which carried the same claim until
    // #118 and is deferred on the same batch.
    blurb:
      "Full role-play case studies across the 28 events — with performance indicators, participant instructions, and the judge characterization.",
    cta: "Open the roleplay board",
    tape: "TIMED",
    tapeColor: "accent",
    variant: 1,
    doodle: <Clipboard className="h-14 w-auto" />,
  },
];

// Practice routes gated behind sign-up for guests. Question Bank (the free
// teaser), the home anchor, and the Developers page stay open. Shared with the
// route-side gate so the two halves of the funnel can't drift (#33).
const GATED_PREFIXES = MEMBER_ROUTES;

export function MarketingHome() {
  const { needsAccount, guard, dialog } = useRequireAccount();

  // One capturing handler: a guest clicking a gated practice link opens sign-up
  // instead of navigating. Cheaper + less invasive than threading a guard through
  // ToolCard / ToolCarousel, and it covers the hero, cards, and steps uniformly.
  const onClickCapture = React.useCallback(
    (e: React.MouseEvent) => {
      if (!needsAccount) return;
      const anchor = (e.target as HTMLElement).closest("a");
      const href = anchor?.getAttribute("href");
      if (href && GATED_PREFIXES.some((p) => href.startsWith(p))) guard(e);
    },
    [needsAccount, guard],
  );

  return (
    <div className="dot-grid bg-paper" onClickCapture={onClickCapture}>
      {/* ------------------------------------------------------------- HERO */}
      <section className="relative mx-auto max-w-6xl overflow-hidden px-5 pb-16 pt-14 sm:px-8 sm:pt-20">
        {/* margin doodles — fewer, more meaningful marks */}
        <RisingChart className="pointer-events-none absolute left-2 top-8 hidden h-16 w-24 text-ink/70 sm:block" />
        {/* Both margin doodles state something the repo can actually back up —
            no invented outcome stats (#35). Floors, so they can't go stale. Both
            are lg-only: below that the hero text fills the margin they sit in. */}
        <MarkerText rotate={-8} className="absolute left-4 top-40 hidden text-sm lg:block">
          {PI_COVERAGE_LABEL} PIs covered
        </MarkerText>
        <Sparkle className="absolute right-8 top-10 hidden h-8 w-8 text-accent sm:block" />
        {/* Deliberately NOT an event count — "28 events" is restated in the
            sub-CTA line below, and two different figures in one viewport read as
            a typo (#35). Bank size comes off the manifest so it can't go stale. */}
        <MarkerText rotate={7} className="absolute right-4 top-28 hidden lg:block">
          {BANK_SIZE_LABEL} questions
        </MarkerText>
        <Lightbulb className="pointer-events-none absolute right-16 top-44 hidden h-12 w-9 text-ink/60 lg:block" />

        <div className="relative mx-auto max-w-3xl text-center">
          <h1 className="font-display text-5xl font-extrabold leading-[1.08] tracking-tight sm:text-7xl">
            Ace your{" "}
            <Loop color="accent">DECA</Loop>{" "}
            <br className="hidden sm:block" />
            exams &amp;{" "}
            <Loop color="highlight">roleplays</Loop>
          </h1>

          {/* "Unlimited" went with the live-JIT path (#108) — tests are composed
              from the committed bank. The figure deliberately stays in the margin
              doodle above rather than being restated here: two renderings of the
              same number in one viewport read as a typo (#35). */}
          <p className="mx-auto mt-7 max-w-xl text-lg leading-8 text-ink/70">
            Exam-authentic practice tests and roleplay case studies, built to
            order. Pick your cluster or event, set the level, and{" "}
            <Underline color="accent" className="font-semibold text-ink">
              start practicing
            </Underline>
            .
          </p>

          <div className="relative mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <StarBurst className="pointer-events-none absolute -left-2 top-1/2 hidden h-8 w-8 -translate-y-1/2 text-ink/60 sm:block" />
            <Button asChild size="lg" variant="primary">
              <Link href="/test-generator">Generate a practice test</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/roleplay">Try a roleplay</Link>
            </Button>
            <StarBurst className="pointer-events-none absolute -right-2 top-1/2 hidden h-8 w-8 -translate-y-1/2 text-ink/60 sm:block" />
          </div>

          <p className="mt-5 text-sm text-muted">
            5 clusters · 28 events · District → ICDC
          </p>
        </div>
      </section>

      {/* ------------------------------------------------------------- TOOLS */}
      <section className="mx-auto max-w-6xl px-5 pb-20 sm:px-8">
        <AnimatedSection className="mb-8 text-center">
          <h2 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
            Four ways to <Highlight color="highlight">practice</Highlight>
          </h2>
        </AnimatedSection>

        {/* Slow revolving belt; hovering a card pulls it to the front and holds
            it still while the rest keep revolving behind. See ToolCarousel. */}
        <ToolCarousel tools={TOOLS} />
      </section>

      {/* --------------------------------------------------------- HOW IT WORKS */}
      <section id="how" className="dot-grid border-t border-dashed border-line bg-paper-2">
        <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
          <AnimatedSection className="mb-12 text-center">
            <MarkerText rotate={-3} className="text-base">
              how it works
            </MarkerText>
            <h2 className="mt-1 font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
              Practice in <Underline color="support">3 steps</Underline>
            </h2>
          </AnimatedSection>

          <div className="grid items-start gap-8 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <AnimatedSection key={s.n} delay={i * 0.1} className="relative">
                {i < STEPS.length - 1 && (
                  <ArrowScribble className="absolute -right-6 top-6 hidden h-10 w-16 text-ink/40 md:block" />
                )}
                <p className="marker text-sm text-muted">STEP {s.n}</p>
                <h3 className="mt-1 font-display text-2xl font-bold tracking-tight">
                  {s.title}
                </h3>
                <p className="mt-2 text-ink/70">{s.body}</p>
              </AnimatedSection>
            ))}
          </div>

          <AnimatedSection className="mt-14 flex flex-col items-center gap-3">
            <Button asChild size="lg" variant="accent">
              <Link href="/test-generator">Start practicing</Link>
            </Button>
            <div className="flex items-center gap-2 text-sm text-muted">
              <Sparkle className="h-4 w-4 text-accent" />
              Free while in beta
            </div>
          </AnimatedSection>
        </div>
      </section>
      {dialog}
    </div>
  );
}

const STEPS = [
  {
    n: 1,
    title: "Pick your event",
    body: "Choose a cluster for a practice test, or one of the 28 events for a roleplay.",
  },
  {
    n: 2,
    title: "Set the level",
    body: "District, Association, or ICDC — plus how many questions you want.",
  },
  {
    n: 3,
    title: "Generate & practice",
    // "a fresh mix", not "fresh material" (#108) — the difficulty mix really is
    // reshuffled on every draw; the questions behind it come from a fixed bank.
    body: "Get a fresh mix of exam-authentic questions every time. Reveal answers when ready.",
  },
];
