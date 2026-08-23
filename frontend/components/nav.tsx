"use client";

// Auth-aware navigation (plan 09 §2b, D7/D8). Two shells switched by auth state:
//
// - GUEST (configured + signed out): a minimal, sign-up-funneling bar — Question
//   Bank (the free teaser), a locked Developers page, and Changelog + Help, plus a
//   "Dashboard" primary button that opens the create-account dialog (a guest has
//   no dashboard).
// - MEMBER / full access (signed in, OR an unconfigured account-less build where
//   everyone uses the app as today): the full tab set returns, Developers is
//   hidden, Changelog + Help relocate to the footer, and "Start practicing"
//   returns.
//
// SSR/flash: the server has no session and the first client paint starts with
// none too, so both render the guest shell and swap on hydration (gated on the
// session resolving) — no mismatch.
//
// Zero-Supabase builds are full-access for PRACTICE but keep the two analytics
// tabs hidden (issue #47): with no accounts there's no logging (D10), so
// /progress and /review can never fill — advertising them ships two dead tabs
// whose emptiness reads as "progress tracking is broken". Both questions are
// answered by lib/auth/gated-routes.ts so this bar and the route-side guard
// can't drift.

import * as React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { SettingsButton } from "@/components/settings-button";
import { AccountMenu } from "@/components/auth/account-menu";
import { useAuth } from "@/components/auth/auth-provider";
import { useRequireAccount } from "@/components/auth/guest-gate";
import {
  ACCOUNT_ONLY_ROUTES,
  hasFullAccess,
  hasProgressLogging,
  matchesRoute,
} from "@/lib/auth/gated-routes";
import { cn } from "@/lib/utils";

const MEMBER_LINKS = [
  { href: "/test-generator", label: "Practice Tests" },
  { href: "/question-bank", label: "Question Bank" },
  { href: "/vocab", label: "Vocab Terms" },
  { href: "/roleplay", label: "Roleplays" },
  { href: "/progress", label: "Progress" },
  { href: "/review", label: "Review" },
];

// Changelog + Help ride the guest bar; once you're in an account they move down
// to the footer (see components/footer.tsx) so the member nav stays focused.
const GUEST_LINKS = [
  { href: "/question-bank", label: "Question Bank" },
  { href: "/developers", label: "Developers" },
  { href: "/changelog", label: "Changelog" },
  { href: "/help", label: "Help" },
];

export function Nav() {
  const auth = useAuth();
  const [open, setOpen] = React.useState(false);
  // The Dashboard button funnels a guest to sign-up (reuses the create-account dialog).
  const { open: openSignUp, dialog } = useRequireAccount();

  // Full access = signed in, or no accounts at all (use the app as today).
  const fullAccess = hasFullAccess(auth);
  // …but the analytics tabs need LOGGING, which an account-less build never has.
  const logging = hasProgressLogging(auth);
  const links = React.useMemo(() => {
    if (!fullAccess) return GUEST_LINKS;
    return logging
      ? MEMBER_LINKS
      : MEMBER_LINKS.filter((l) => !matchesRoute(l.href, ACCOUNT_ONLY_ROUTES));
  }, [fullAccess, logging]);

  const primary = fullAccess ? (
    <Button asChild size="sm" variant="primary">
      <Link href="/test-generator">Start practicing</Link>
    </Button>
  ) : (
    <Button size="sm" variant="primary" onClick={openSignUp}>
      Dashboard
    </Button>
  );

  return (
    <header className="sticky top-0 z-50 border-b border-dashed border-line bg-paper/85 backdrop-blur">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
        {/* Logo + links as one LEFT-anchored group, so the tab slots sit at a
            fixed offset from the logo regardless of how many links there are —
            a guest's Question Bank / Developers fill the same first two slots a
            member's Practice Tests / Question Bank would occupy. */}
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-1.5 font-display text-xl font-extrabold tracking-tight">
            <span className="sketch-radius border-2 border-ink bg-accent px-2 py-0.5 text-[var(--on-accent)]">DECK</span>
          </Link>

          <div className="hidden items-center gap-5 lg:flex">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className="text-[0.95rem] font-medium text-ink/70 transition-colors hover:text-ink"
              >
                {l.label}
              </Link>
            ))}
          </div>
        </div>

        <div className="hidden items-center gap-2 lg:flex">
          {primary}
          {/* Settings + account pushed to the far corner, set apart from the CTA. */}
          <div className="ml-6 flex items-center gap-2">
            <SettingsButton />
            <AccountMenu />
          </div>
        </div>

        <button
          aria-label="Toggle menu"
          className="lg:hidden rounded-lg p-2 hover:bg-ink/5"
          onClick={() => setOpen((v) => !v)}
        >
          <div className="space-y-1.5">
            <span className={cn("block h-0.5 w-6 bg-ink transition-transform", open && "translate-y-2 rotate-45")} />
            <span className={cn("block h-0.5 w-6 bg-ink transition-opacity", open && "opacity-0")} />
            <span className={cn("block h-0.5 w-6 bg-ink transition-transform", open && "-translate-y-2 -rotate-45")} />
          </div>
        </button>
      </nav>

      {open && (
        <div className="border-t border-dashed border-line px-5 pb-5 pt-2 lg:hidden">
          <div className="flex flex-col gap-1">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2.5 font-medium text-ink/80 hover:bg-ink/5"
              >
                {l.label}
              </Link>
            ))}
            <SettingsButton
              variant="row"
              onOpen={() => setOpen(false)}
              className="mt-1"
            />
            <AccountMenu variant="row" onAct={() => setOpen(false)} className="mt-1" />
            {fullAccess ? (
              <Button asChild size="sm" variant="primary" className="mt-2 w-full">
                <Link href="/test-generator" onClick={() => setOpen(false)}>
                  Start practicing
                </Link>
              </Button>
            ) : (
              <Button
                size="sm"
                variant="primary"
                className="mt-2 w-full"
                onClick={() => {
                  setOpen(false);
                  openSignUp();
                }}
              >
                Dashboard
              </Button>
            )}
          </div>
        </div>
      )}
      {dialog}
    </header>
  );
}
