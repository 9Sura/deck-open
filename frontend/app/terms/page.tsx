// Terms of service (issue #209). Written to the same standard as
// app/privacy/page.tsx: plain-language and parent-readable, because DECA
// competitors are minors. Static — no data, no client state — so it prerenders.
//
// DELIBERATELY THIN ON DATA. Anything about what is stored, where it lives, or
// how to export/reset/delete it stays on the privacy page and is LINKED from
// here, never restated. Issue #144 was two prose pages drifting apart on a fact
// that was duplicated between them; a third document makes that easier, not
// harder. The rule for this file: if a sentence would answer "what do you keep
// about me?", it belongs on /privacy.
//
// Not legal advice, and it doesn't claim to be — this is a student-built free
// tool describing its own rules in the language its users read.

import type { Metadata } from "next";
import Link from "next/link";
import { MarkerText } from "@/components/marker-text";

export const metadata: Metadata = {
  title: "Terms",
  description:
    "The plain-language rules for using DECK — who it's for, what an account is, and why the practice material can be wrong.",
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

export default function TermsPage() {
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
          Terms
        </h1>
        <p className="mt-3 text-sm text-muted">
          DECK is a free study tool for DECA practice, built by students. It is
          not affiliated with DECA Inc. This page is the deal: what you can
          expect from DECK, and what we expect from you. Using the site means you
          agree to it.
        </p>
      </div>

      <div className="mt-6 rounded-2xl border-2 border-line bg-paper-2 px-5 py-4 text-[0.95rem] leading-relaxed text-ink/80">
        <p>
          <strong>The short version.</strong> Everything here is practice
          material written by AI, so <strong>some of it will be wrong</strong> —
          study with it, don’t cite it. DECK is in beta and free: it can change,
          break, or go away, and account data may be reset while we’re testing.
          You need to be <strong>13 or older</strong> for an account. Be decent,
          don’t try to break the site, and don’t treat this as official DECA
          preparation, because it isn’t.
        </p>
      </div>

      <Section title="Who can use DECK">
        <p>
          Anyone can use <strong>guest mode</strong> — the question bank and its
          focus quizzes — with no account and no age check.
        </p>
        {/* 13+ is enforced at sign-up by the checkbox in
            components/auth/sign-in-dialog.tsx and stated on /privacy under
            "Age". Three sites, one fact — move all three together. */}
        <p>
          To <strong>create an account</strong> you must be{" "}
          <strong>13 or older</strong>, which you confirm when you sign up. If
          you’re under 13, guest mode is for you: it needs no account and keeps
          no record of your practice anywhere. If we learn an account belongs to
          someone under 13, we’ll remove it.
        </p>
        <p>
          If you’re under 18, we’d rather your parent or guardian knew you were
          using DECK. The{" "}
          <Link href="/privacy" className="underline hover:text-ink">
            privacy page
          </Link>{" "}
          is written for them to read.
        </p>
      </Section>

      <Section title="Your account">
        <p>
          An account is a <strong>username and a password</strong> — no email, no
          real name, nothing else. It’s yours to keep your practice history
          under, and you’re responsible for what happens on it, so don’t share
          your password or let someone else use your account.
        </p>
        {/* The no-recovery fact is ALSO in sign-in-dialog.tsx's sign-up footnote
            (where a user is making the decision) and on /privacy. Deliberate
            duplication at the point of decision — keep the three in step. */}
        <p>
          Because there’s no email on file, there is{" "}
          <strong>no password reset</strong>. If you forget your password, the
          account is locked and we can’t let you back in. Keep it somewhere safe.
        </p>
        <p>
          You can close your account whenever you like, from{" "}
          <strong>Settings → Data → Delete account</strong>. We can close or
          suspend one too — if it’s being used to break the rules below, if it
          belongs to someone under 13, or if we have to shut something down for
          everyone. Where it’s reasonable to warn you first, we will.
        </p>
      </Section>

      <Section title="The practice material is AI-generated">
        <p>
          Every practice question, roleplay scenario, and vocab term on DECK was{" "}
          <strong>written by an AI model</strong>, not by DECA and not by a
          teacher. It’s built to look and feel like the real thing, and it’s
          checked by automated tools — but that isn’t the same as being correct.
        </p>
        <p>
          So, plainly: <strong>some of it is wrong.</strong> Answers can be
          mislabelled, explanations can contain mistakes, and a question can be
          worded so that more than one answer looks right. Use DECK to drill and
          to find your weak spots — not as a source of fact, and not as something
          to quote in a competition or an assignment. When it matters, check
          against DECA’s own published materials or ask your advisor.
        </p>
        <p>
          DECK is <strong>not affiliated with, endorsed by, or connected to DECA
          Inc.</strong> Nothing here is official DECA preparation, and no score or
          streak on this site predicts how you’ll do at a real event. Where DECA’s
          names for events, clusters, and performance indicators appear, they’re
          used to describe what you’re practising — they belong to DECA Inc.
        </p>
      </Section>

      <Section title="Using DECK fairly">
        <p>Don’t:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Try to break, overload, or get around the site’s security, or reach
            other people’s accounts or data.
          </li>
          <li>
            Scrape or bulk-download the question bank, or hammer the site with
            automated requests.
          </li>
          <li>
            Put anything personal, offensive, or that isn’t yours into a username
            or display name.
          </li>
          <li>
            Republish DECK’s practice material as your own, or sell it.
          </li>
          <li>Use DECK to cheat on something you’re actually being graded on.</li>
        </ul>
        <p>
          Practising as much as you want, on as many devices as you want, is the
          point — none of the above is about how hard you study.
        </p>
      </Section>

      <Section title="It’s a beta, and it’s free">
        <p>
          DECK is provided <strong>as-is</strong>. It’s a student project given
          away for nothing, so we can’t promise it will be available, that it will
          work correctly, or that it will still exist next term. Pages can change,
          features can be removed, and the whole thing can go offline without
          notice.
        </p>
        <p>
          While we’re in beta, <strong>account data may be reset</strong> as we
          change how things are stored.{" "}
          <Link href="/privacy" className="underline hover:text-ink">
            Export your data
          </Link>{" "}
          if you want to keep it. Don’t treat DECK as the only copy of anything
          you care about.
        </p>
        <p>
          To the extent the law allows it, we’re not responsible for what happens
          if DECK is wrong, unavailable, or loses your practice history — up to
          and including a competition that doesn’t go the way you hoped. That’s
          the trade for a free tool, and it’s why the accuracy section above is
          worded as bluntly as it is.
        </p>
      </Section>

      <Section title="Your data">
        <p>
          What DECK stores, where it lives, who can see it, and how to export,
          reset, or delete it are all on the{" "}
          <Link href="/privacy" className="underline hover:text-ink">
            privacy page
          </Link>{" "}
          — deliberately in one place rather than half-repeated here. The short
          version: guest mode records nothing at all, an account stores your
          username and your practice log, and you can wipe either from Settings →
          Data at any time.
        </p>
      </Section>

      <Section title="Changes to these terms">
        <p>
          We’ll update this page as DECK changes, and the update is announced in
          the{" "}
          <Link href="/changelog" className="underline hover:text-ink">
            changelog
          </Link>{" "}
          like everything else. Carrying on using DECK after a change means the
          new version applies. If a change is one you’re not happy with, you can
          delete your account from Settings → Data.
        </p>
      </Section>

      <Section title="Questions">
        <p>
          This is a student-built practice tool, and this page is written in plain
          English rather than legal language — it isn’t legal advice. If something
          here is unclear, or you think DECK has got something wrong, reach out and
          we’ll sort it out.
        </p>
      </Section>
    </div>
  );
}
