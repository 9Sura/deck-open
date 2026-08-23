"use client";

// The React seam over the ProgressStore (plan 08 §4, sub-plan §5/§7). Selects the
// active store by auth state and exposes it plus a `version` counter that bumps on
// every write (and on cross-device pulls), so Phase 2/3 selectors re-read with
// zero changes on their side.
//
// - Guest, or an account-less (unconfigured) build
//                       → NullStore: NON-LOGGING (plan 09 D10, account-only
//                          logging). Writes are dropped, reads are empty. Both
//                          may use focus quizzes but nothing is recorded.
// - Signed-in           → SyncingStore(IndexedDbStore("deck-progress-<uid>") +
//                          SupabaseStore + Outbox), which writes through to Postgres
//                          and survives offline. Sign-out DETACHES the user store
//                          (never wipes) and falls back to the guest NullStore.
//
// That first branch is exactly `!hasProgressLogging(auth)` from
// lib/auth/gated-routes.ts, and the nav + <RouteGuard> now ask the same question
// before offering /progress and /review (issue #47). They used to disagree: an
// unconfigured build was "full access" to them and "guest" here, so it advertised
// two analytics pages that this provider could never populate.
//
// The guest→account migration (plan-08 4c) is DROPPED (plan 09 D10): there is no
// guest log to union — logging is account-only from the start.
//
// Lint note (React Compiler is strict): the store swap sets state via a microtask
// (`Promise.resolve().then`), never synchronously in the effect body.

import * as React from "react";
import {
  GUEST_DB_NAME,
  IndexedDbStore,
} from "@/lib/progress/idb-store";
import { NullStore } from "@/lib/progress/null-store";
import { SupabaseStore } from "@/lib/progress/supabase-store";
import { SyncingStore, type SyncErrorInfo } from "@/lib/progress/syncing-store";
import { Outbox } from "@/lib/progress/outbox";
import { createClient } from "@/lib/supabase/client";
import { useAuth } from "@/components/auth/auth-provider";
import type { ProgressStore } from "@/lib/progress/store";
import type { Attempt, Session } from "@/lib/progress/types";
import { readProfile, writeProfile, type Profile } from "@/lib/progress/profile";
import { NoticeLayerProvider } from "@/components/notice-layer";

/** A LOCAL storage failure — this device isn't saving/loading at all (issue #9
 *  follow-up). Distinct from SyncErrorInfo, which means the opposite: saved here,
 *  just not on your account. */
export interface StorageErrorInfo {
  /** "save" = a write was lost; "read" = the log couldn't be loaded. */
  kind: "save" | "read";
  /** The underlying error message — for a console line / support hint. */
  message: string;
}

function errMessage(err: unknown): string {
  return err && typeof err === "object" &&
    typeof (err as { message?: unknown }).message === "string"
    ? (err as { message: string }).message
    : String(err);
}

interface ProgressContextValue {
  store: ProgressStore;
  hydrated: boolean; // false on the server + first client paint
  version: number; // increments after each successful write / pull
  profile: Profile | null;
  setProfile: (p: Profile) => void;
  // Write wrappers that bump `version` so subscribers re-read (Phase 2+).
  recordAttempts: (a: Attempt[]) => Promise<void>;
  startSession: (s: Session) => Promise<void>;
  endSession: (id: string, patch: Partial<Session>) => Promise<void>;
  /** Wipe all attempts + sessions (local + remote when signed in), then bump `version`. */
  resetProgress: () => Promise<void>;
  /** Set when a signed-in write was permanently rejected and dropped from the sync
   *  queue (issue #5). Local practice is unaffected; this only flags that some
   *  progress couldn't reach the server. null = syncing normally. */
  syncError: SyncErrorInfo | null;
  /** Dismiss the current sync-error notice. */
  dismissSyncError: () => void;
  /** Set when this DEVICE's storage failed — a write was dropped or the log
   *  couldn't be read (issue #9 follow-up). Without this the app looks identical
   *  to a healthy one with no practice in it. null = storage healthy. */
  storageError: StorageErrorInfo | null;
  /** Report a storage fault from a direct `store` caller that bypasses the write
   *  wrappers below (the dashboard's read in useProgressData). */
  reportStorageError: (kind: StorageErrorInfo["kind"], err: unknown) => void;
  /** Dismiss the current storage-error notice. */
  dismissStorageError: () => void;
}

const ProgressContext = React.createContext<ProgressContextValue | null>(null);

/** false on the server, true once mounted — the SSR-safe hydration guard. */
function useHydrated(): boolean {
  return React.useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

export function ProgressProvider({ children }: { children: React.ReactNode }) {
  const { session } = useAuth();
  const uid = session?.user?.id ?? null;

  // Guest store is the SSR-safe default: a NON-LOGGING NullStore (D10). The effect
  // below swaps to a SyncingStore when signed in, and back on sign-out.
  const [store, setStore] = React.useState<ProgressStore>(() => new NullStore());

  const hydrated = useHydrated();
  const [version, setVersion] = React.useState(0);
  const bumpVersion = React.useCallback(() => setVersion((v) => v + 1), []);

  // Sync-error surface (issue #5): the SyncingStore calls this when it dead-letters
  // a permanently-failing op, so the UI can flag "some progress couldn't sync"
  // instead of the queue silently stalling. null = healthy.
  const [syncError, setSyncError] = React.useState<SyncErrorInfo | null>(null);
  const handleSyncError = React.useCallback(
    (info: SyncErrorInfo) => setSyncError(info),
    [],
  );
  const dismissSyncError = React.useCallback(() => setSyncError(null), []);

  // Storage-error surface (issue #9 follow-up). Every local read/write funnels
  // through here, so one notice covers the quiz writes, the dashboard read, and
  // the SyncingStore's outbox. A "save" fault outranks a "read" fault: not
  // recording an answer is worse than failing to display one.
  const [storageError, setStorageError] = React.useState<StorageErrorInfo | null>(
    null,
  );
  const reportStorageError = React.useCallback(
    (kind: StorageErrorInfo["kind"], err: unknown) => {
      const message = errMessage(err);
      setStorageError((prev) =>
        prev?.kind === "save" && kind === "read" ? prev : { kind, message },
      );
    },
    [],
  );
  const dismissStorageError = React.useCallback(() => setStorageError(null), []);
  // The SyncingStore's outbox lives in the same IndexedDB as the local cache, so
  // a failure there is a "we aren't saving" fault, not a "we aren't syncing" one.
  const handleStorageError = React.useCallback(
    (err: unknown) => reportStorageError("save", err),
    [reportStorageError],
  );

  // The uid the current store was built for (null = guest). Starts at null to
  // match the useState default, so the first mount doesn't rebuild the guest store.
  const builtForRef = React.useRef<string | null>(null);
  // The live SyncingStore, so teardown is driven by us rather than by the effect's
  // cleanup — see the ownership note on the effect below (issue #111).
  const syncingRef = React.useRef<SyncingStore | null>(null);

  // Retire the live syncing store, if there is one. Sign-out, account switch and
  // unmount are the only three ways a store is legitimately torn down.
  const retireSyncing = React.useCallback(() => {
    syncingRef.current?.dispose();
    syncingRef.current = null;
  }, []);

  // Store lifecycle. Builds AT MOST ONE SyncingStore per account (issue #111):
  // the deps below are all `useCallback`s over stable deps today, so this runs
  // once per sign-in — but if any of them ever became unstable, the pre-#111
  // shape (construct unconditionally, dispose in the effect's cleanup) would
  // dispose the live store and build another over the same IndexedDB on EVERY
  // render. `dispose()` detaches listeners and clears the retry timer but cannot
  // cancel an in-flight `flush()`, so the retired instance's `drain()` would keep
  // running while the new one started its own, and the two would race on
  // `remove`/`bumpTries`/`markDead` for the same outbox `seq`.
  //
  // The guard alone isn't enough, which is why the store is owned by a ref: React
  // runs the previous cleanup BEFORE the re-run, so a cleanup that disposed
  // unconditionally would retire the live store and then the guard would return
  // early and never replace it. Teardown is therefore explicit here (sign-out /
  // account switch) and in the unmount-only effect below.
  React.useEffect(() => {
    const sb = createClient(); // browser client (null when unconfigured)

    if (!uid || !sb) {
      // No logging possible (guest, or an account-less build — the same branch
      // the gates read as `!hasProgressLogging`). Only rebuild when coming FROM
      // a signed-in store.
      if (builtForRef.current !== null) {
        builtForRef.current = null;
        retireSyncing();
        const guest = new NullStore();
        Promise.resolve().then(() => {
          setStore(guest);
          setSyncError(null); // a guest has no sync queue — clear any stale notice
          setStorageError(null); // …and a NullStore never touches storage
          bumpVersion();
        });
      }
      return;
    }

    if (builtForRef.current === uid) return; // already built for this account

    retireSyncing(); // account switch: retire the previous account's store first

    // Ask the browser to keep the offline cache from being evicted mid-season
    // (4e). Best-effort — a prompt on some browsers, silent on others.
    void navigator.storage?.persist?.();

    // Signed-in: build the offline-first syncing store on a per-user cache.
    const dbName = `${GUEST_DB_NAME}-${uid}`;
    const syncing = new SyncingStore(
      new IndexedDbStore(dbName),
      new SupabaseStore(sb, uid),
      new Outbox(dbName),
      bumpVersion,
      handleSyncError,
      handleStorageError,
    );
    builtForRef.current = uid;
    syncingRef.current = syncing;
    Promise.resolve().then(() => {
      setStore(syncing);
      bumpVersion();
    });

    // No guest→account migration (D10) — logging is account-only, so there's no
    // guest log to union. Just start the syncing store's freshness triggers
    // (initial pull + outbox drain + cross-device refresh).
    syncing.start();
  }, [uid, bumpVersion, handleSyncError, handleStorageError, retireSyncing]);

  // Unmount teardown, on its own empty-dep effect so it fires when the provider
  // really goes away and never on a same-account re-run. Resetting `builtForRef`
  // keeps StrictMode's mount→cleanup→mount honest: the second mount rebuilds.
  React.useEffect(
    () => () => {
      builtForRef.current = null;
      retireSyncing();
    },
    [retireSyncing],
  );

  // Read the stored profile lazily on the client (null on the server, where
  // there is no localStorage). No effect + setState, so no cascading render.
  const [profile, setProfileState] = React.useState<Profile | null>(() =>
    typeof window === "undefined" ? null : readProfile(),
  );

  const setProfile = React.useCallback((p: Profile) => {
    writeProfile(p);
    setProfileState(p);
  }, []);

  // The three quiz writes SWALLOW their error on purpose — a storage fault must
  // never block answering a question — but they no longer swallow the KNOWLEDGE
  // of it: each reports, which raises the notice below. `version` only bumps on a
  // real write, so a failed save can't masquerade as a successful one.
  const recordAttempts = React.useCallback(
    async (a: Attempt[]) => {
      try {
        await store.recordAttempts(a);
      } catch (err) {
        reportStorageError("save", err);
        return;
      }
      setVersion((v) => v + 1);
    },
    [store, reportStorageError],
  );
  const startSession = React.useCallback(
    async (s: Session) => {
      try {
        await store.startSession(s);
      } catch (err) {
        reportStorageError("save", err);
        return;
      }
      setVersion((v) => v + 1);
    },
    [store, reportStorageError],
  );
  const endSession = React.useCallback(
    async (id: string, patch: Partial<Session>) => {
      try {
        await store.endSession(id, patch);
      } catch (err) {
        reportStorageError("save", err);
        return;
      }
      setVersion((v) => v + 1);
    },
    [store, reportStorageError],
  );
  // Reset is the exception: it RETHROWS. It's an explicit, confirmed, irreversible
  // action, so the caller has to be able to say "that didn't work" instead of
  // reporting success over a wipe that never happened. Still bump `version` on the
  // way out — a partial reset means the on-screen counts are now stale either way.
  const resetProgress = React.useCallback(async () => {
    try {
      await store.clear();
    } catch (err) {
      setVersion((v) => v + 1);
      throw err;
    }
    setVersion((v) => v + 1);
  }, [store]);

  const value = React.useMemo<ProgressContextValue>(
    () => ({
      store,
      hydrated,
      version,
      profile,
      setProfile,
      recordAttempts,
      startSession,
      endSession,
      resetProgress,
      syncError,
      dismissSyncError,
      storageError,
      reportStorageError,
      dismissStorageError,
    }),
    [
      store,
      hydrated,
      version,
      profile,
      setProfile,
      recordAttempts,
      startSession,
      endSession,
      resetProgress,
      storageError,
      reportStorageError,
      dismissStorageError,
      syncError,
      dismissSyncError,
    ],
  );

  // One notice region, storage first: "this device isn't saving" is strictly worse
  // news than "this device is saving but not syncing", and stacking both would just
  // bury the important one.
  //
  // It is PUBLISHED to the notice layer rather than rendered here (issue #196).
  // Both faults are raised by writes, and writes happen inside a quiz, so this
  // notice used to paint under the `z-50` portalled overlay that was on screen
  // whenever it fired. NoticeLayerProvider renders it at body level exactly as
  // before when nothing is open, and hands it to an open overlay's <NoticeOutlet />
  // — inside its `aria-modal` subtree and its Tab trap — when one is.
  const notice = storageError ? (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 bottom-4 z-50 mx-auto flex max-w-md items-start gap-3 rounded-lg border border-line bg-paper px-4 py-3 text-sm text-ink shadow-md"
    >
      <span className="flex-1">
        {storageError.kind === "save" ? (
          <>
            Your browser isn&rsquo;t letting DECK save on this device right now,
            so this practice may not be recorded. This usually means private
            browsing or a full disk &mdash; you can keep practising, but check
            your Progress page afterwards.
          </>
        ) : (
          <>
            We couldn&rsquo;t load your saved practice from this device, so your
            Progress and Review pages may look empty. Nothing has been deleted
            &mdash; try reloading the page.
          </>
        )}
      </span>
      <button
        type="button"
        onClick={dismissStorageError}
        className="shrink-0 font-medium text-muted hover:text-ink"
      >
        Dismiss
      </button>
    </div>
  ) : syncError ? (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 bottom-4 z-50 mx-auto flex max-w-md items-start gap-3 rounded-lg border border-line bg-paper px-4 py-3 text-sm text-ink shadow-md"
    >
      <span className="flex-1">
        {syncError.op === "reset" ? (
          <>
            Your progress was cleared on this device, but couldn&rsquo;t be
            cleared on your account &mdash; it may come back the next time
            this device syncs. Try resetting again.
          </>
        ) : (
          <>
            Some progress couldn&rsquo;t sync to your account, so it may not
            appear on your other devices. It&rsquo;s still saved on this
            device.
          </>
        )}
      </span>
      <button
        type="button"
        onClick={dismissSyncError}
        className="shrink-0 font-medium text-muted hover:text-ink"
      >
        Dismiss
      </button>
    </div>
  ) : null;

  return (
    <ProgressContext.Provider value={value}>
      <NoticeLayerProvider node={notice}>{children}</NoticeLayerProvider>
    </ProgressContext.Provider>
  );
}

export function useProgress(): ProgressContextValue {
  const ctx = React.useContext(ProgressContext);
  if (!ctx) {
    throw new Error("useProgress must be used within a ProgressProvider");
  }
  return ctx;
}
