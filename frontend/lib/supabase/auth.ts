// Username <-> synthetic-email mapping + validation (D2, sub-plan §4).
//
// Supabase Auth is email-keyed, but we present a pure username UX. A username
// maps deterministically to `<normalized>@users.deck.app`, so signUp /
// signInWithPassword use Supabase's native email/password unchanged while the
// real, display-cased username lives on the profiles row (unique, case-insensitive).
//
// The identity key is the LOWERCASED username: "Kelton" and "kelton" resolve to
// the same synthetic email and the same account (profiles_username_lower enforces
// the matching case-insensitive uniqueness). Validation forbids any character
// that normalize() would drop, so what the user types maps 1:1 with no surprises.

/** The domain for synthetic placeholder emails — never receives real mail. */
const SYNTHETIC_EMAIL_DOMAIN = "users.deck.app";

export const USERNAME_MIN = 3;
export const USERNAME_MAX = 20;
/** Letters, digits, underscore only — a safe email local-part and URL-safe. */
const USERNAME_RE = /^[a-zA-Z0-9_]+$/;

/** Lowercase + trim. Input is assumed already validated (no chars to strip). */
export function normalizeUsername(raw: string): string {
  return raw.trim().toLowerCase();
}

/** The deterministic placeholder email Supabase Auth is keyed on. */
export function syntheticEmail(username: string): string {
  return `${normalizeUsername(username)}@${SYNTHETIC_EMAIL_DOMAIN}`;
}

/** null if valid; otherwise a user-facing reason. */
export function validateUsername(raw: string): string | null {
  const u = raw.trim();
  if (u.length < USERNAME_MIN) return `At least ${USERNAME_MIN} characters.`;
  if (u.length > USERNAME_MAX) return `At most ${USERNAME_MAX} characters.`;
  if (!USERNAME_RE.test(u)) return "Letters, numbers, and _ only.";
  return null;
  // Reservation / profanity / impersonation filtering (usernames are public on
  // the leaderboard) is a Phase 4d product decision — not gated here in 4a.
}

export const PASSWORD_MIN = 8;

/** null if valid; otherwise a user-facing reason. */
export function validatePassword(pw: string): string | null {
  if (pw.length < PASSWORD_MIN) return `At least ${PASSWORD_MIN} characters.`;
  return null;
}
