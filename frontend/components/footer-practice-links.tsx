"use client";

// The footer's two practice links (Practice Tests / Roleplays), funnelled to
// sign-up for a guest exactly like every other CTA into those routes (#146).
//
// The footer sits OUTSIDE <MemberGate> in app/layout.tsx, so it renders on every
// page a guest can see — including the ones where the nav has deliberately
// dropped these same two tabs from GUEST_LINKS. Rendering them unguarded meant
// one piece of chrome advertised what the other suppressed, and a guest's click
// landed on the full-page sign-up wall instead of the create-account dialog
// every other gated click opens.
//
// The links stay VISIBLE for guests rather than hiding (the direction the nav
// takes): the footer is a sitemap, not a "what can I open right now" bar, so
// naming what an account unlocks is on-message — and hiding them would collapse
// a guest's footer row to a single Privacy link, since Changelog + Help ride the
// guest NAV and only relocate here once signed in (see footer-account-links).
//
// A click guard also means server and client render identical markup, so unlike
// FooterAccountLinks there's no guest-first-then-swap on hydration.
//
// Which hrefs to gate comes from MEMBER_ROUTES — the same list the route-side
// gate and the marketing-home funnel read, so this can't drift from them (#33).

import Link from "next/link";
import { useRequireAccount } from "@/components/auth/guest-gate";
import { MEMBER_ROUTES, matchesRoute } from "@/lib/auth/gated-routes";

const PRACTICE_LINKS = [
  { href: "/test-generator", label: "Practice Tests" },
  { href: "/roleplay", label: "Roleplays" },
];

export function FooterPracticeLinks() {
  const { needsAccount, guard, dialog } = useRequireAccount();

  return (
    <>
      {PRACTICE_LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          onClick={
            needsAccount && matchesRoute(l.href, MEMBER_ROUTES) ? guard : undefined
          }
          className="hover:text-ink"
        >
          {l.label}
        </Link>
      ))}
      {dialog}
    </>
  );
}
