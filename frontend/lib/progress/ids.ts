// Id minting for the progress records (sub-plan §11.2). No dependency:
// crypto.randomUUID() where available, with a Math.random fallback for older
// Safari that never exposed it in non-secure contexts. Ids are only ever the
// dedupe key (put-by-id) so a v4-shaped fallback is sufficient.

/** A best-effort UUID v4 string. */
export function uuid(): string {
  const c =
    typeof globalThis !== "undefined"
      ? (globalThis.crypto as Crypto | undefined)
      : undefined;
  if (c?.randomUUID) return c.randomUUID();

  // Fallback: RFC-4122-shaped v4 from Math.random. Not cryptographically
  // strong, but ids here only need to be collision-free per user, not secret.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0;
    const v = ch === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** A fresh session id. Thin alias so call sites read intently. */
export function newSessionId(): string {
  return uuid();
}
