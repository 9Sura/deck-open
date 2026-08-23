// Shared failure classification for the two things in the app that push writes to
// Supabase and have to decide whether retrying can ever help: the attempt-log
// outbox flusher (`syncing-store.ts`) and the study-plan config writer
// (`components/auth/auth-provider.tsx`, issue #181).
//
// It lives here rather than inside the flusher because a second copy would drift:
// the classifier encodes which PostgREST/browser error shapes are worth retrying,
// and that answer is a property of the backend, not of the caller.
//
// One caveat the callers must handle themselves: postgrest-js only REJECTS when
// `.throwOnError()` is set. Without it, every failure — a 5xx, an RLS rejection,
// even a dead connection — RESOLVES with `{ error }`. So a caller may hand this
// function either a thrown error or a resolved `PostgrestError`; both shapes carry
// `message`/`code`, and both are classified the same way.

export type FailureKind = "permanent" | "transient" | "unknown";

/** Backoff ceiling. Reached at tries >= 5 on the curve below. */
export const MAX_BACKOFF_MS = 30_000;

/** Exponential backoff for the Nth consecutive failure (1-based), capped. */
export function backoffMs(tries: number): number {
  return Math.min(MAX_BACKOFF_MS, 1000 * 2 ** Math.min(tries, 5));
}

/** Classify a remote failure so the caller knows whether retrying can ever help.
 *  Conservative on both ends: only clear network problems are "transient" (retry
 *  forever), only clear client/data rejections are "permanent" (give up fast);
 *  anything else is "unknown" and rides the caller's try-count backstop. */
export function classifyError(err: unknown): FailureKind {
  if (!err || typeof err !== "object") return "unknown";
  const e = err as { code?: unknown; message?: unknown; status?: unknown };
  const code = typeof e.code === "string" ? e.code : "";
  const message = typeof e.message === "string" ? e.message : "";
  const status = typeof e.status === "number" ? e.status : undefined;

  // Browser/fetch network failures (offline, DNS, connection reset, timeout): the
  // whole connection is unreachable, not this one write — retry indefinitely.
  if (
    err instanceof TypeError ||
    /failed to fetch|networkerror|network request failed|timeout|econn|etimedout|enotfound|fetch failed/i.test(
      message,
    )
  ) {
    return "transient";
  }

  if (typeof status === "number") {
    if (status >= 500) return "transient"; // server hiccup — retry
    if (status >= 400) return "permanent"; // bad request / rejected — won't self-heal
  }

  // Postgres SQLSTATE classes surfaced by PostgREST: 22xxx data exception,
  // 23xxx integrity-constraint violation, 42xxx syntax/access rule — all permanent.
  if (/^(22|23|42)/.test(code)) return "permanent";

  return "unknown";
}

/** The human-readable message off a thrown error or a resolved PostgrestError. */
export function failureMessage(err: unknown): string {
  if (
    err &&
    typeof err === "object" &&
    typeof (err as { message?: unknown }).message === "string"
  ) {
    return (err as { message: string }).message;
  }
  return String(err);
}
