"use client";

// Bounce anyone whose practice ISN'T BEING LOGGED off the account-only pages
// (plan 09 D10). /progress and /review are member surfaces — with account-only
// logging there is nothing to show without one — so when the session goes away
// (sign-out, or a guest deep-links in) we replace the route with the homepage.
// The dashboard at `/` doesn't need this: HomeGate already swaps to the
// marketing landing when the session drops.
//
// The OTHER member routes (Practice Tests, Vocab, Roleplays) have real content
// to tease, so they're gated in place by <MemberGate> instead of redirected —
// both read the same list in lib/auth/gated-routes.ts.
//
// The test is `hasProgressLogging`, NOT "is there a session on a configured
// project" (issue #47). An unconfigured, account-less build gets the same
// non-logging NullStore a guest does, so these two pages are permanently empty
// there and get the same redirect — previously it skipped the guard entirely on
// `!configured` and left two dead routes reachable. Still waits for `loading` so
// the initial pre-session paint never triggers a spurious redirect (an
// unconfigured build resolves `loading` immediately). Uses router.replace so the
// protected page isn't left in history behind the homepage.

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import {
  ACCOUNT_ONLY_ROUTES,
  hasProgressLogging,
  matchesRoute,
} from "@/lib/auth/gated-routes";

const isProtected = (path: string) => matchesRoute(path, ACCOUNT_ONLY_ROUTES);

export function RouteGuard() {
  const { configured, loading, session } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  React.useEffect(() => {
    if (loading || hasProgressLogging({ configured, session })) return;
    if (isProtected(pathname)) router.replace("/");
  }, [configured, loading, session, pathname, router]);

  return null;
}
