// Guest → account migration (sub-plan §8, D6). The one algorithm that must be
// exactly right. On the first sign-in on a device with un-migrated guest data:
// push the guest log up, pull the union back down, carry a custom display name,
// and set a marker so it never re-runs.
//
// Idempotency is the whole game: every write is upsert-by-client-uuid and every
// id is a stable client uuid (ids.ts). Running this twice — or on two devices —
// converges to the SET UNION of all attempts; a shared question answered on two
// devices is two distinct attempts (distinct ids), which is correct. Nothing is
// ever incremented, so there is nothing to double. Guest data is only ever
// COPIED, never destroyed (a second account on the same browser migrates its own
// guest slice).

import type { SupabaseClient } from "@supabase/supabase-js";
import { GUEST_DB_NAME, IndexedDbStore } from "@/lib/progress/idb-store";
import { SupabaseStore } from "@/lib/progress/supabase-store";
import { readProfile } from "@/lib/progress/profile";

const migratedKey = (uid: string) => `deck-migrated:${uid}`;
const NOTICE_KEY = "deck-migration-notice";

export interface MigrationResult {
  /** True if the migration actually ran this call (vs. already-done / skipped). */
  ran: boolean;
  /** Guest attempts pushed up — drives the one-time "your progress is synced" toast. */
  guestAttempts: number;
}

/** True once this uid has migrated on this device (marker present, or no storage). */
export function hasMigrated(uid: string): boolean {
  if (typeof localStorage === "undefined") return true;
  try {
    return localStorage.getItem(migratedKey(uid)) !== null;
  } catch {
    return true; // storage blocked — don't loop trying to migrate
  }
}

function markMigrated(uid: string): void {
  try {
    localStorage.setItem(migratedKey(uid), new Date().toISOString());
  } catch {
    /* storage blocked — worst case it re-runs next sign-in; still idempotent */
  }
}

/**
 * Union the guest log into the signed-in account, both directions, by id.
 * Safe to call on every sign-in — the marker short-circuits after the first
 * success, and every write is idempotent even without it. Throws on network
 * failure (marker stays unset → retried next sign-in); the caller catches.
 */
export async function migrateGuestToAccount(
  sb: SupabaseClient,
  uid: string,
): Promise<MigrationResult> {
  if (hasMigrated(uid)) return { ran: false, guestAttempts: 0 };

  const guestLocal = new IndexedDbStore(GUEST_DB_NAME);
  const userLocal = new IndexedDbStore(`${GUEST_DB_NAME}-${uid}`);
  const remote = new SupabaseStore(sb, uid);

  // 1. Read the guest log from the un-suffixed DB.
  const guest = await guestLocal.exportAll();

  // 2. Push guest rows up (upsert-by-id; never re-mint).
  if (guest.attempts.length > 0 || guest.sessions.length > 0) {
    await remote.importAll(guest);
  }

  // 3. Pull the union (guest + any prior remote) down into the per-user cache.
  const server = await remote.exportAll();
  await userLocal.importAll(server);

  // 4. Carry a custom guest display name onto the account (skip the "Guest" default).
  const profile = readProfile();
  if (profile && profile.displayName && profile.displayName !== "Guest") {
    await sb
      .from("profiles")
      .update({ display_name: profile.displayName })
      .eq("user_id", uid);
  }

  // 5. Guard against re-runs. Guest DB is left intact (copied, never destroyed).
  markMigrated(uid);
  return { ran: true, guestAttempts: guest.attempts.length };
}

// ---- one-time /progress notice --------------------------------------------

/** Flag the "your guest progress is now synced" toast (only when there was any). */
export function setMigrationNotice(guestAttempts: number): void {
  if (guestAttempts <= 0 || typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(NOTICE_KEY, String(guestAttempts));
  } catch {
    /* storage blocked — the toast just won't show */
  }
}

/** Read-and-clear the notice count (shown once, then gone). null if none. */
export function takeMigrationNotice(): number | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const raw = localStorage.getItem(NOTICE_KEY);
    if (!raw) return null;
    localStorage.removeItem(NOTICE_KEY);
    const n = parseInt(raw, 10);
    return Number.isFinite(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
}
