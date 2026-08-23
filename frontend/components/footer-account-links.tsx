"use client";

// Changelog + Help live in the nav for guests; once you're in an account they
// relocate here to the footer, keeping the member nav focused on practice tabs.
//
// Guest-first render (null until the session resolves) mirrors the Nav, so the
// server + first client paint agree and there's no hydration flash. "Full access"
// = signed in, OR an unconfigured account-less build (where there is no guest nav
// to host these, so the footer is the right home).

import Link from "next/link";
import { useAuth } from "@/components/auth/auth-provider";
import { hasFullAccess } from "@/lib/auth/gated-routes";

export function FooterAccountLinks() {
  const auth = useAuth();
  if (!hasFullAccess(auth)) return null;

  return (
    <>
      <Link href="/changelog" className="hover:text-ink">
        Changelog
      </Link>
      <Link href="/help" className="hover:text-ink">
        Help
      </Link>
    </>
  );
}
