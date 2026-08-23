// Help — a plain-language, parent-readable FAQ. Static (no data, no client
// state) so it prerenders. Lives in the nav for guests and moves to the footer
// once you're in an account (see components/nav.tsx + footer).

import type { Metadata } from "next";
import Link from "next/link";
import { MarkerText } from "@/components/marker-text";

export const metadata: Metadata = {
  title: "Help",
  description: "How DECK works — guest vs. account, practice, progress, and data.",
};

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-8">
      <h2 className="font-display text-xl font-bold tracking-tight">{title}</h2>
      <div className="mt-2 space-y-2 text-[0.95rem] leading-relaxed text-ink/80">
        {children}
      </div>
    </section>
  );
}

export default function HelpPage() {
  return (
    <div className="mx-auto max-w-2xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Back home
      </Link>

      <div className="mt-4">
        <MarkerText rotate={-3} className="text-base">
          how it works
        </MarkerText>
        <h1 className="mt-1 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
          Help
        </h1>
        <p className="mt-3 text-sm text-muted">
          DECK is a study tool for DECA practice — practice tests, a question bank,
          and vocab drills. It is not affiliated with DECA Inc.; all practice
          material is AI-generated.
        </p>
      </div>

      {/* The guest/account split described here is decided by
          lib/auth/gated-routes.ts (MEMBER_ROUTES / ACCOUNT_ONLY_ROUTES), and it
          is stated in TWO places — here and app/privacy/page.tsx's guest-mode
          section. Issue #144 was the privacy page drifting from this one while
          this one stayed right; move both when a route moves between the lists. */}
      <Section title="What can I do without an account?">
        {/*
          Say what the browse route actually serves (issue #162). This used to
          claim "browse every question", but /question-bank reaches the numbered
          exam sets ONLY: its one loader is loadSet (question-bank.ts), which
          resolves a cluster×level×set through setMeta and fetches that single
          set file. The much larger `-pool` files are reached only through
          loadCandidates / loadPIQuestions — composeTest, the dashboard drills
          and /review — all of which are account-gated. Deliberately no figure
          here: a set count would be a second live number on a static prose page
          and would go stale the way #134's test-length list did.
        */}
        <p>
          As a guest you get the <strong>Question Bank</strong> — browse the
          ready-made <strong>exam sets</strong> and run{" "}
          <strong>focus quizzes</strong> from them, free and with no sign-up.
        </p>
        <p>
          Creating an account unlocks the rest: your own <strong>dashboard</strong>,
          plus the <strong>Practice Tests</strong>, <strong>Vocab</strong>, and{" "}
          <strong>Roleplay</strong> pages. The practice tests and the dashboard
          drills also draw on the <strong>much larger question pool</strong>{" "}
          behind the exam sets, which the bank&rsquo;s browse view
          doesn&rsquo;t show. An
          account also <strong>remembers your practice</strong> — the Progress and
          Review pages fill in — and syncs it across your devices.
        </p>
        <p>
          Guest mode records nothing, so your history starts once you make an
          account. See the{" "}
          <Link href="/privacy" className="underline hover:text-ink">
            privacy page
          </Link>{" "}
          for exactly what is and isn&rsquo;t stored.
        </p>
      </Section>

      <Section title="Question bank & focus mode (no account needed)">
        <p>
          The <strong>Question Bank</strong> lets you browse thousands of
          questions across the ready-made exam sets, each tagged Easy, Medium, or
          Hard. <strong>Focus mode</strong>{" "}
          is a distraction-free quiz over a fixed set, with a side navigator so you
          can jump between questions. This is the free guest experience — no sign-up
          required.
        </p>
      </Section>

      <Section title="Practice tests (account)">
        {/*
          Two things here go stale if you write them as a list rather than a rule
          (issue #134). The test lengths live in COUNTS in app/test-generator/page.tsx
          and have already changed once — this used to say "25- or 50-question" and
          missed the 10 that was added, the same drift #124 fixed on the generator
          page's own mix hint. And the redraw control is called "New set", not
          "Regenerate": it renders only on the end screen once you finish
          (live-quiz-modal.tsx, `status === "ready" && finished`) and is hidden
          entirely for a fixed set, which is every focus quiz off the Question Bank.
        */}
        <p>
          The <strong>Test Generator</strong> builds a difficulty-mixed practice
          test for the cluster and level you pick, drawn from the real question
          bank. Choose how long you want it and a mix preset — Exam-real, Balanced,
          or Challenge. When you finish, the score screen offers{" "}
          <strong>New set</strong> to draw a fresh test with the same settings.
        </p>
        <p>
          Focus quizzes from the Question Bank run a fixed set of questions, so
          they don&rsquo;t redraw — start a new one to get different questions.
        </p>
      </Section>

      <Section title="Vocab (account)">
        <p>
          <strong>Vocab Terms</strong> drills the key terminology for each event —
          50 terms per event, so you can quickly review definitions before a
          competition.
        </p>
      </Section>

      <Section title="Roleplays (account)">
        <p>
          The <strong>Roleplay Challenge</strong>{" "}
          is a day board of role-play case
          studies you can actually run: open one and it walks you through the
          brief, prep time, your presentation, and a debrief, with the judge&rsquo;s
          questions held back until prep is over — the same order a real judged
          roleplay goes in. New scenarios drop at{" "}
          <strong>midnight Eastern time</strong>, so everyone is on the same day
          wherever they are.
        </p>
        <p>
          The archive is <strong>still small</strong> — a handful of scenarios
          across a few days, so most of the 28 events are greyed out for now, and
          more days fill in as they are written. A roleplay run lives in the page
          only: it is not saved, it does not appear on Progress or Review, and
          refreshing loses it.
        </p>
      </Section>

      <Section title="Progress & Review (accounts only)">
        <p>
          <strong>Progress</strong>{" "}
          shows a readiness trajectory and a mastery
          heatmap by performance indicator, so you can see where you&rsquo;re
          strong and what to drill next. <strong>Review</strong> is your error log:
          it collects the questions you missed and clears them once you answer that
          question correctly again.
        </p>
        <p>
          Both pages need a saved history, so they only work when you&rsquo;re
          signed in.
        </p>
      </Section>

      <Section title="Accounts & passwords">
        <p>
          Accounts use a <strong>username and password</strong>{" "}
          — no email. Because
          there&rsquo;s no email on file, there is currently{" "}
          <strong>no password reset</strong>: if you forget your password, the
          account is locked. Please keep your password somewhere safe.
        </p>
        <p>
          DECK is in <strong>beta</strong>, and everyone testing accounts shares one
          database while we iterate — your data is walled off from other testers,
          but treat it as an early test system and don&rsquo;t rely on it being
          permanent yet.
        </p>
      </Section>

      <Section title="Themes & animated effects">
        <p>
          Open <strong>Settings</strong> (the gear) → <strong>Themes</strong> to
          switch between six looks, including three seasonal themes with animated
          overlays. The <strong>Animated effects</strong>{" "}
          toggle at the top turns
          those overlays off (motion also respects your system&rsquo;s
          reduce-motion setting).
        </p>
      </Section>

      <Section title="Managing your data">
        <p>
          In <strong>Settings → Data</strong> you can export everything as a JSON
          file, reset your progress, or delete your account and all of its data.
          Full details are on the{" "}
          <Link href="/privacy" className="underline hover:text-ink">
            privacy page
          </Link>
          .
        </p>
      </Section>

      <Section title="Still stuck?">
        <p>
          This is a student-built practice tool in active development. If something
          is broken or unclear, or you want your data removed and can&rsquo;t do it
          yourself, reach out and we&rsquo;ll help. The{" "}
          <Link href="/changelog" className="underline hover:text-ink">
            changelog
          </Link>{" "}
          tracks what&rsquo;s new.
        </p>
      </Section>
    </div>
  );
}
