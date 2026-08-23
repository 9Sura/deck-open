// Privacy policy (sub-plan §10, D11 — a launch gate). Plain-language and
// parent-readable because DECA competitors are minors. Documents exactly what's
// stored, why, and how reset / delete / export work. Static — no data, no client
// state — so it prerenders.

import type { Metadata } from "next";
import Link from "next/link";
import { MarkerText } from "@/components/marker-text";

export const metadata: Metadata = {
  title: "Privacy",
  description:
    "What DECK stores, why, and how to reset, delete, or export your data.",
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

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-2xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Back home
      </Link>

      <div className="mt-4">
        <MarkerText rotate={-3} className="text-base">
          the plain-language version
        </MarkerText>
        <h1 className="mt-1 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
          Privacy
        </h1>
        <p className="mt-3 text-sm text-muted">
          DECK is a study tool for DECA practice. It is not affiliated with DECA
          Inc. This page explains what we store and the control you have over it.
        </p>
      </div>

      <div className="mt-6 rounded-2xl border-2 border-line bg-paper-2 px-5 py-4 text-[0.95rem] leading-relaxed text-ink/80">
        <p>
          <strong>Beta note.</strong> DECK is in early testing, and everyone
          trying out accounts right now shares <strong>one</strong> database. Your
          practice data is still walled off so other testers can’t read it (see{" "}
          <em>If you make an account</em> below) — but the people running the beta
          can access what’s stored, to fix bugs and help testing, and data may be
          reset as we iterate. Please don’t put anything personal in your username
          or answers, and don’t treat account data as permanent yet. Guest mode
          records no practice data at all, so it’s unaffected.
        </p>
      </div>

      {/* What guest mode INCLUDES is decided by lib/auth/gated-routes.ts, not
          here — MEMBER_ROUTES (/test-generator, /vocab, /roleplay) is swapped
          for a sign-up panel, and ACCOUNT_ONLY_ROUTES (/progress, /review)
          redirects home. Issue #144 was this paragraph promising guests they
          could "generate tests" while /test-generator sat in MEMBER_ROUTES,
          which is the policy page contradicting the app. If a route moves
          between those lists, this section and /help's "What you get" both have
          to move with it. */}
      <Section title="If you don't make an account (guest mode)">
        <p>
          You can practice freely as a guest — browse the{" "}
          <strong>Question Bank</strong> and run focus quizzes from it, answering
          as many questions as you like. As a guest, none of that is{" "}
          <strong>recorded anywhere</strong>: your answers aren’t saved on your
          device and aren’t uploaded to us, so there’s nothing about your practice
          to store or see. (The one thing that is counted, for guests and members
          alike, is anonymous page visits — see <em>Site analytics</em> below.)
        </p>
        <p>
          The trade-off is that the rest of the app needs an account. Practice
          tests, vocab terms, and roleplays ask you to sign up when you open them,
          and progress tracking needs a saved history to work, so the{" "}
          <strong>Progress</strong> and <strong>Review</strong> pages aren’t part
          of guest mode at all — they’re hidden from the menu, and opening one
          directly sends you back to the homepage. Make an account when you want
          your practice remembered.
        </p>
      </Section>

      <Section title="If you make an account">
        <p>We store, tied to your account:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Your <strong>username</strong> (chosen by you) and a display name.
          </li>
          <li>
            Your <strong>practice log</strong> — each answered question’s topic,
            your choice, whether it was correct, and timing — plus a row per
            practice session.
          </li>
        </ul>
        <p>
          We do <strong>not</strong> collect your email, real name, school, or
          location. Accounts don’t use email yet, which also means there is{" "}
          <strong>no password reset</strong> — if you forget your password, the
          account is locked (your data stays safe on the server, but you can’t get
          back in). Keep your password somewhere safe.
        </p>
        <p>
          Your account data lives in a hosted database (Supabase) — during the
          current beta, a single shared project for everyone testing. Access is
          locked down per account: database security rules mean only you, signed
          in, can read or write your own rows, so other testers can’t see your
          practice history. It’s used only to compute your own progress, mastery,
          and review pages, and to sync them across your devices.
        </p>
      </Section>

      <Section title="Site analytics">
        <p>
          DECK is hosted on Vercel, and we use <strong>Vercel Web Analytics</strong>{" "}
          to see which pages get visited and how many people show up. It runs for
          everyone — guests and signed-in members — and records the page you
          landed on, roughly where in the world the visit came from, and what kind
          of browser or device you used.
        </p>
        <p>
          It uses <strong>no cookies</strong>, doesn’t follow you to other sites,
          and isn’t tied to your account or your practice log — the two never meet.
          We use it to decide what to build next, not to look at any one person.
        </p>
      </Section>

      <Section title="Age">
        <p>
          You must be <strong>13 or older</strong> to create an account (you confirm
          this at sign-up). If you’re under 13, please use guest mode — it needs no
          account and keeps no record of your practice anywhere: not with us, and
          not on your device. (Anonymous page-visit counts still apply, as above.)
        </p>
      </Section>

      <Section title="Leaderboards">
        <p>
          Leaderboards aren’t available yet. If they arrive, they’ll be{" "}
          <strong>off by default</strong> and opt-in only, and would show just
          aggregate standings (like a score and rank) — never your individual
          answers.
        </p>
      </Section>

      <Section title="Your controls">
        <p>In Settings → Data you can, at any time:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Export</strong> all your data as a JSON file.
          </li>
          <li>
            <strong>Reset progress</strong> — erase your practice history (on your
            device, and on your account if you’re signed in).
          </li>
          <li>
            <strong>Delete account</strong> — permanently remove your account and
            all of its data everywhere.
          </li>
        </ul>
        {/* Describe the MECHANISM, not the rendered state: Export and Reset are
            rendered-and-disabled for a guest (settings-data.tsx — `nothingToReset`),
            but the whole Delete account block is behind `signedIn`, so it is absent
            from the DOM rather than switched off (issue #145). Tying the sentence to
            "you need an account to have one" keeps it true if that gating changes. */}
        <p>
          As a guest there is nothing to export or reset, so those two buttons are
          there but switched off. <strong>Delete account</strong> only appears once
          you have an account to delete.
        </p>
      </Section>

      <Section title="Questions">
        <p>
          This is a student-built practice tool. If something here is unclear, or
          you want your data removed and can’t do it yourself, reach out and we’ll
          help.
        </p>
      </Section>
    </div>
  );
}
