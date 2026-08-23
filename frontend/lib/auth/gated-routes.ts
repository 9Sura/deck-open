// The single source of truth for which routes an account unlocks (plan 09 §2b,
// D7). Kept out of the components so the click-side funnel (marketing CTAs), the
// route-side gate, and the redirect guard can't drift apart — issue #33 was
// exactly that drift: the CTAs funnelled to sign-up while the routes themselves
// were wide open to anyone with the URL.
//
// Two tiers, because a guest needs a different answer on each:
//
// - MEMBER_ROUTES  — real member features. A guest who deep-links in gets the
//   sign-up panel IN PLACE of the page (<MemberGate>), so the link still means
//   something and the funnel is one click away.
// - ACCOUNT_ONLY_ROUTES — member surfaces that would be *empty* for a guest
//   anyway (logging is account-only, D10). Nothing to tease, so <RouteGuard>
//   just replaces the route with home.
//
// The two tiers ask DIFFERENT questions about an unconfigured, account-less
// build, and conflating them was issue #47:
//
// - MEMBER_ROUTES ask "could an account exist?" — no accounts means nothing to
//   funnel to, so the practice features are open to everyone (`hasFullAccess`).
//   They work standalone: they compose from the committed bank and static JSON.
// - ACCOUNT_ONLY_ROUTES ask "is anything being LOGGED?" — and logging is
//   account-only (D10), so an unconfigured build gets the non-logging NullStore
//   exactly like a guest does (`hasProgressLogging`). /progress and /review are
//   permanently empty there, so they must not be advertised or reachable, or the
//   build ships two dead pages and no explanation.
//
// Every seam that has to answer either question reads these predicates rather
// than re-deriving `!configured || !!session` locally — nav.tsx, route-guard.tsx,
// member-gate.tsx, footer-account-links.tsx and progress-provider.tsx drifting
// apart on that expression is what #33 and #47 both were.

/** Practice features an account unlocks — gated in place, sign-up shown. */
export const MEMBER_ROUTES = ["/test-generator", "/vocab", "/roleplay"];

/** Analytics surfaces that are empty without an account — redirected home. */
export const ACCOUNT_ONLY_ROUTES = ["/progress", "/review"];

/** The auth facts both predicates need — a structural subset of `useAuth()`. */
export interface AccessState {
  /** True once a Supabase project is configured, i.e. accounts are possible. */
  configured: boolean;
  /** The current session, or null when signed out. */
  session: unknown;
}

/**
 * Can this visitor use the member practice features? Signed in, OR an
 * account-less build where there is no account to gate behind.
 */
export function hasFullAccess({ configured, session }: AccessState): boolean {
  return !configured || !!session;
}

/**
 * Is this visitor's practice actually being recorded? Logging is account-only
 * (D10), so this needs a real session AND a project to hold it — an unconfigured
 * build has no store to write to and reads back empty forever. This is the
 * question the analytics surfaces (/progress, /review) must ask; asking
 * `hasFullAccess` instead advertises pages that can never fill.
 */
export function hasProgressLogging({ configured, session }: AccessState): boolean {
  return configured && !!session;
}

/** Prefix match on a path segment boundary (`/vocab` matches `/vocab/x`, not `/vocabulary`). */
export function matchesRoute(path: string, prefixes: readonly string[]): boolean {
  return prefixes.some((p) => path === p || path.startsWith(`${p}/`));
}
