"use client";

// Session context (sub-plan §4). Owns the browser Supabase client, the current
// session/user, and the username+password auth actions. Sits ABOVE
// ProgressProvider in the tree so Phase 4b can select the store by auth state;
// in 4a it only powers the Nav account menu — nothing syncs yet.
//
// Degrades cleanly when the project isn't provisioned (`configured: false`):
// loading resolves immediately, there's no session, and the auth actions return
// a friendly error. Guest mode is unaffected with zero Supabase config.

import * as React from "react";
import type { Session, User } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/env";
import { GUEST_DB_NAME, deleteDatabase } from "@/lib/progress/idb-store";
import {
  syntheticEmail,
  validatePassword,
  validateUsername,
} from "@/lib/supabase/auth";
import {
  coercePlanConfig,
  readPlanConfigCache,
  readPlanConfigDirty,
  writePlanConfigCache,
  writePlanConfigDirty,
  type PlanConfig,
} from "@/lib/progress/plan-config";
import {
  backoffMs,
  classifyError,
  failureMessage,
} from "@/lib/progress/sync-failure";

export interface AuthContextValue {
  /** True once the Supabase project env is set — gates all auth UI. */
  configured: boolean;
  /** False until the initial session load resolves. */
  loading: boolean;
  session: Session | null;
  user: User | null;
  /** Display username from the account (signup metadata), or null when guest. */
  username: string | null;
  signUp: (username: string, password: string) => Promise<{ error: string | null }>;
  signIn: (username: string, password: string) => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
  /** Permanently delete the account (server cascade) + wipe local + sign out (D12). */
  deleteAccount: () => Promise<{ error: string | null }>;
  /** Username to greet with the sign-in welcome animation; null when idle. */
  welcome: string | null;
  /** Called by the welcome overlay when its animation finishes. */
  clearWelcome: () => void;
  /** True after this session was signed out because the account logged in elsewhere
   *  ("newest login wins"). Drives the one-time "signed out elsewhere" notice. */
  bootedElsewhere: boolean;
  /** Dismiss the "signed out elsewhere" notice. */
  clearBooted: () => void;
  /** The account's study-plan config (profiles.plan_config), or null when guest / unset. */
  planConfig: PlanConfig | null;
  /**
   * Persist the study-plan config to the profiles row (+ local cache). No-op when
   * guest. Accepts either a value or a functional updater `(prev) => next`; the
   * updater form composes on the FRESHEST config (a synchronous mirror), so several
   * writers firing in the same tick (session attribution, saved-quiz, dismiss/add,
   * the daily freeze) no longer clobber each other's edits.
   */
  setPlanConfig: (
    config: PlanConfig | ((prev: PlanConfig | null) => PlanConfig | null),
  ) => Promise<void>;
  /** Set when a study-plan edit couldn't be saved to the account and retrying has
   *  stopped (issue #181). The edit is still applied on this device and is re-sent
   *  on the next load/reconnect — this only says it isn't on the account yet. */
  planSyncError: { message: string } | null;
  /** Dismiss the "plan didn't save to your account" notice. */
  dismissPlanSyncError: () => void;
}

const GUEST: AuthContextValue = {
  configured: false,
  loading: false,
  session: null,
  user: null,
  username: null,
  signUp: async () => ({ error: "Accounts aren't available yet." }),
  signIn: async () => ({ error: "Accounts aren't available yet." }),
  signOut: async () => {},
  deleteAccount: async () => ({ error: "Accounts aren't available yet." }),
  welcome: null,
  clearWelcome: () => {},
  bootedElsewhere: false,
  clearBooted: () => {},
  planConfig: null,
  setPlanConfig: async () => {},
  planSyncError: null,
  dismissPlanSyncError: () => {},
};

const AuthContext = React.createContext<AuthContextValue>(GUEST);

// Retry cap for the plan_config write timer (issue #181). Same shape and reason as
// the outbox's MAX_TRIES — the backoff caps out at tries >= 5, so 8 spans a
// plausible blip — but reaching it does NOT drop the edit: the dirty marker stays
// set, so the next load, reconnect or tab focus tries again. Only the timer stops.
const PLAN_MAX_TRIES = 8;

function usernameOf(user: User | null): string | null {
  const meta = user?.user_metadata as { username?: string } | undefined;
  return meta?.username ?? null;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Stable per-tab client (null when unconfigured). Lazy init — no work on SSR.
  const [supabase] = React.useState(() => createClient());
  const [session, setSession] = React.useState<Session | null>(null);
  const [loading, setLoading] = React.useState(isSupabaseConfigured);
  const [welcome, setWelcome] = React.useState<string | null>(null);
  const clearWelcome = React.useCallback(() => setWelcome(null), []);
  const [planConfig, setPlanConfigState] = React.useState<PlanConfig | null>(null);
  // Synchronous mirror of the latest config so a functional setPlanConfig update
  // composes on the freshest value even when several writes fire before React
  // commits (the effect-updated `configRef` in the dashboard lagged a render,
  // which let concurrent writers clobber one another — dropping task/session
  // attribution so progress stopped tracking). Updated in lockstep with state.
  const configMirrorRef = React.useRef<PlanConfig | null>(null);
  const applyConfig = React.useCallback((cfg: PlanConfig | null) => {
    configMirrorRef.current = cfg;
    setPlanConfigState(cfg);
  }, []);
  // Serialize row writes so out-of-order network completions can't land an older
  // snapshot last; each queued write already carries the fully-merged config.
  const writeChainRef = React.useRef<Promise<unknown>>(Promise.resolve());

  // ---- durable plan_config writes (issue #181) -----------------------------
  // `profiles.plan_config` is the one synced write in the app that doesn't ride the
  // durable Outbox, and it doesn't need to: the config is a single last-write-wins
  // blob, so replaying superseded snapshots (what a queue does, correctly, for the
  // append-only attempt log) would be wrong — the only thing worth re-sending is
  // the newest cached value. What it DOES need is a record that the cache is ahead
  // of the row plus a retry, because the write was previously fire-and-forget: a
  // failure was invisible, and the next load's profiles read then overwrote the
  // unlanded edit with the stale row, silently dropping a task's session
  // attribution, its saved quiz set, or the day's frozen recommended list.
  //
  // The retry cap lives at module scope (PLAN_MAX_TRIES).
  const planWriteSeqRef = React.useRef(0);
  const planTriesRef = React.useRef(0);
  const planRetryRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const [planSyncError, setPlanSyncError] = React.useState<{
    message: string;
  } | null>(null);
  const dismissPlanSyncError = React.useCallback(() => setPlanSyncError(null), []);

  /** One attempt at the row write. Returns null on success, or the failure.
   *
   *  postgrest-js only REJECTS when `.throwOnError()` is set. Without it every
   *  failure — a 5xx, an RLS rejection, even a dead connection (PostgrestBuilder
   *  catches the fetch error itself) — RESOLVES with `{ error }`, so the result has
   *  to be inspected. The `.catch(() => {})` this replaced caught nothing, because
   *  nothing was ever thrown. */
  const pushPlanConfig = React.useCallback(
    async (id: string, cfg: PlanConfig): Promise<unknown | null> => {
      if (!supabase) return { message: "Accounts aren't available yet." };
      try {
        const { error } = await supabase
          .from("profiles")
          .update({ plan_config: cfg })
          .eq("user_id", id);
        return error ?? null;
      } catch (err) {
        // Defensive: a client-level throw (bad session refresh, etc.).
        return err ?? { message: "Unknown error" };
      }
    },
    [supabase],
  );

  // Indirection so the retry timer (and the listeners below) always re-enter the
  // CURRENT flush without making the callback depend on itself.
  const flushRef = React.useRef<(id: string) => Promise<void>>(async () => {});

  /** Send the newest config for `id` if the marker says the row is behind, then
   *  clear the marker / back off / give up. NEVER REJECTS — every caller invokes
   *  it as `void`, and an escaping rejection would skip the retry entirely. */
  const flushPlanConfig = React.useCallback(
    async (id: string): Promise<void> => {
      if (!readPlanConfigDirty(id)) return;
      // The mirror is the freshest value; the cache covers a fresh load that hasn't
      // applied anything yet (e.g. re-pushing an edit made before a reload).
      const cfg = configMirrorRef.current ?? readPlanConfigCache(id);
      if (!cfg) {
        // Marker with nothing to send (cache cleared out from under us) — the row
        // is authoritative again, so stop claiming otherwise.
        writePlanConfigDirty(id, false);
        return;
      }
      const seq = planWriteSeqRef.current;
      const failure = await pushPlanConfig(id, cfg);
      if (!failure) {
        // Only the NEWEST write may clear the marker. A later edit queued behind
        // this one is still unlanded, and clearing here would let the load effect
        // overwrite it with the row this push just wrote.
        if (seq === planWriteSeqRef.current) {
          writePlanConfigDirty(id, false);
          planTriesRef.current = 0;
          setPlanSyncError(null);
        }
        return;
      }
      const kind = classifyError(failure);
      const tries = (planTriesRef.current += 1);
      if (kind === "permanent" || tries >= PLAN_MAX_TRIES) {
        setPlanSyncError({ message: failureMessage(failure) });
        return; // marker STAYS set — a reload / reconnect / focus re-sends it
      }
      if (planRetryRef.current || typeof window === "undefined") return;
      planRetryRef.current = setTimeout(() => {
        planRetryRef.current = null;
        void flushRef.current(id);
      }, backoffMs(tries));
    },
    [pushPlanConfig],
  );

  React.useEffect(() => {
    flushRef.current = flushPlanConfig;
  }, [flushPlanConfig]);

  // ---- single active session ("newest login wins") ------------------------
  // Each browser that LOGS IN mints a random token, stamps it on profiles.active_session,
  // and remembers it. Every signed-in client watches that column (initial read +
  // realtime) and signs itself out the instant it sees a token that isn't its own —
  // so a fresh login elsewhere boots the older session (and one-at-a-time use also
  // sidesteps the cross-device plan_config clobber).
  const sessionTokenRef = React.useRef<string | null>(null);
  // Set true at the start of signIn/signUp so the profiles-load effect knows THIS
  // load is a fresh login and should CLAIM the session rather than validate it.
  const loginInProgressRef = React.useRef(false);
  const [bootedElsewhere, setBootedElsewhere] = React.useState(false);
  const sessionKey = (id: string) => `deck-session:${id}`;
  const enforceBoot = React.useCallback(async () => {
    sessionTokenRef.current = null;
    setBootedElsewhere(true);
    await supabase?.auth.signOut();
  }, [supabase]);

  React.useEffect(() => {
    if (!supabase) return;
    // Initial load, then subscribe to every future auth transition. Both set
    // state from async callbacks (never synchronously in render), so the strict
    // React-Compiler rules are satisfied.
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
      setLoading(false);
    });
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  // Load the study-plan config (plan 09 §4.1, D3) from the profiles row whenever
  // the account changes. Seed from the per-uid localStorage cache first so the
  // dashboard doesn't flash "no plan" while the row is in flight. All setState is
  // async (.then / microtask), never synchronous in the effect body (strict rule).
  const uid = session?.user?.id ?? null;
  React.useEffect(() => {
    if (!supabase || !uid) {
      sessionTokenRef.current = null;
      Promise.resolve().then(() => {
        applyConfig(null);
        // No account on screen ⇒ nothing for a plan-sync notice to refer to. The
        // marker itself is deliberately NOT cleared: it belongs to that uid and
        // must survive until the edit lands or the account is deleted.
        setPlanSyncError(null);
      });
      return;
    }
    const cached = readPlanConfigCache(uid);
    if (cached) Promise.resolve().then(() => applyConfig(cached));

    let active = true;
    void (async () => {
      // Read plan_config + the active-session token together. If active_session
      // doesn't exist yet (migration 0004 not applied), fall back to plan_config
      // only and leave session enforcement inert — never break the plan load.
      type ProfileRow = { plan_config?: unknown; active_session?: string | null };
      const primary = await supabase
        .from("profiles")
        .select("plan_config, active_session")
        .eq("user_id", uid)
        .maybeSingle();
      let data: unknown = primary.data;
      if (primary.error) {
        const fallback = await supabase
          .from("profiles")
          .select("plan_config")
          .eq("user_id", uid)
          .maybeSingle();
        data = fallback.data;
      }
      const row = (data ?? null) as ProfileRow | null;
      if (!active) return;

      // The row is authoritative UNLESS this device holds an edit that is not known
      // to have reached it (issue #181) — in that case the row is the stale side,
      // and applying it here is exactly how a failed write used to be reverted
      // without anyone noticing. Keep the cached edit and re-send it instead.
      const unsynced =
        readPlanConfigDirty(uid) &&
        (configMirrorRef.current != null || readPlanConfigCache(uid) != null);
      if (unsynced) {
        // What's applied is already the newest (the cache seed above, or a newer
        // edit made while the row was in flight) — re-send it, don't re-apply the
        // snapshot read at effect start, which an edit may already have superseded.
        void flushRef.current(uid);
      } else {
        const cfg = coercePlanConfig(row?.plan_config);
        applyConfig(cfg);
        writePlanConfigCache(uid, cfg);
        // A marker with no cache behind it describes nothing — drop it so it can't
        // strand a later load on a value that no longer exists.
        if (readPlanConfigDirty(uid)) writePlanConfigDirty(uid, false);
      }

      // ---- single-session enforcement ----
      const dbToken = row?.active_session ?? null;
      if (loginInProgressRef.current) {
        // Fresh login from THIS browser — claim the account for this session.
        loginInProgressRef.current = false;
        const token =
          typeof crypto !== "undefined" && crypto.randomUUID
            ? crypto.randomUUID()
            : `${uid}-${Date.now()}-${Math.round(Math.random() * 1e9)}`;
        sessionTokenRef.current = token;
        try {
          localStorage.setItem(sessionKey(uid), token);
        } catch {
          /* storage blocked — enforcement degrades to best-effort */
        }
        try {
          await supabase
            .from("profiles")
            .update({ active_session: token })
            .eq("user_id", uid);
        } catch {
          /* column missing (migration not applied) — enforcement stays inert */
        }
      } else {
        // Restored session (reload / returning device) — validate our claim.
        let token: string | null = null;
        try {
          token = localStorage.getItem(sessionKey(uid));
        } catch {
          token = null;
        }
        sessionTokenRef.current = token;
        if (dbToken && token !== dbToken) {
          // A newer login on another device owns the account now — step aside.
          void enforceBoot();
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [supabase, uid, applyConfig, enforceBoot]);

  // Watch the account's active-session token in realtime, so a login elsewhere
  // boots THIS session promptly (not only on the next reload). Delivery is
  // owner-scoped by RLS; if the realtime publication isn't set up, this simply
  // never fires and the initial-read check above remains the backstop.
  React.useEffect(() => {
    if (!supabase || !uid) return;
    const channel = supabase
      .channel(`profiles-session:${uid}`)
      .on(
        "postgres_changes",
        { event: "UPDATE", schema: "public", table: "profiles", filter: `user_id=eq.${uid}` },
        (payload) => {
          const next =
            (payload.new as { active_session?: string | null } | null)?.active_session ?? null;
          const mine = sessionTokenRef.current;
          if (next && mine && next !== mine) void enforceBoot();
        },
      )
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [supabase, uid, enforceBoot]);

  const setPlanConfig = React.useCallback<AuthContextValue["setPlanConfig"]>(
    async (config) => {
      if (!supabase || !uid) return;
      // Resolve against the synchronous mirror so updater-form writes compose on
      // the freshest config rather than a stale render's value.
      const prev = configMirrorRef.current;
      const next =
        typeof config === "function"
          ? (config as (p: PlanConfig | null) => PlanConfig | null)(prev)
          : config;
      if (next == null) return; // nothing to persist (guarded updater bailed)
      if (next === prev) return; // updater made no change — skip a redundant write
      // Optimistic: update UI + cache immediately, then persist to the row on a
      // serialized chain so writes land in the order they were issued.
      applyConfig(next);
      writePlanConfigCache(uid, next);
      // Mark BEFORE the write goes out: if the tab dies mid-flight, the next load
      // has to assume the edit didn't land rather than assume it did.
      writePlanConfigDirty(uid, true);
      planWriteSeqRef.current += 1;
      planTriesRef.current = 0; // a fresh edit restarts the backoff
      const run = writeChainRef.current.then(() => flushPlanConfig(uid));
      writeChainRef.current = run.catch(() => {});
      await run;
    },
    [supabase, uid, applyConfig, flushPlanConfig],
  );

  // Re-send an unsynced edit when the device comes back (reconnect / tab focus),
  // mirroring the outbox flusher's triggers — the backoff timer alone would keep
  // retrying on a schedule that has nothing to do with when the network returns,
  // and stops entirely once PLAN_MAX_TRIES is reached.
  React.useEffect(() => {
    if (!supabase || !uid || typeof window === "undefined") return;
    const onOnline = () => void flushRef.current(uid);
    const onVisible = () => {
      if (document.visibilityState === "visible") void flushRef.current(uid);
    };
    window.addEventListener("online", onOnline);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("online", onOnline);
      document.removeEventListener("visibilitychange", onVisible);
      if (planRetryRef.current) {
        clearTimeout(planRetryRef.current);
        planRetryRef.current = null;
      }
    };
  }, [supabase, uid]);

  const signUp = React.useCallback<AuthContextValue["signUp"]>(
    async (rawUsername, password) => {
      if (!supabase) return { error: "Accounts aren't available yet." };
      const uErr = validateUsername(rawUsername);
      if (uErr) return { error: uErr };
      const pErr = validatePassword(password);
      if (pErr) return { error: pErr };
      const username = rawUsername.trim();

      // Friendly pre-check (the unique index is the race-safe guarantee).
      const { data: available } = await supabase.rpc("username_available", {
        u: username,
      });
      if (available === false) return { error: "That username is taken." };

      // Flag the imminent auth transition as a fresh login so the profiles-load
      // effect CLAIMS this session (rather than validating an existing token).
      setBootedElsewhere(false);
      loginInProgressRef.current = true;
      const { error } = await supabase.auth.signUp({
        email: syntheticEmail(username),
        password,
        options: { data: { username, display_name: username } },
      });
      if (error) {
        loginInProgressRef.current = false;
        // A racing duplicate trips the trigger's unique insert → a generic DB
        // error; the most likely cause at this point is a taken username.
        const msg = /database|already|registered|exists/i.test(error.message)
          ? "That username is taken."
          : error.message;
        return { error: msg };
      }
      setWelcome(username);
      return { error: null };
    },
    [supabase],
  );

  const signIn = React.useCallback<AuthContextValue["signIn"]>(
    async (rawUsername, password) => {
      if (!supabase) return { error: "Accounts aren't available yet." };
      const username = rawUsername.trim();
      if (!username || !password)
        return { error: "Enter your username and password." };
      // Fresh login → claim the account for this session (see the load effect).
      setBootedElsewhere(false);
      loginInProgressRef.current = true;
      const { error } = await supabase.auth.signInWithPassword({
        email: syntheticEmail(username),
        password,
      });
      if (error) {
        loginInProgressRef.current = false;
        const msg = /invalid login credentials/i.test(error.message)
          ? "Wrong username or password."
          : error.message;
        return { error: msg };
      }
      setWelcome(username);
      return { error: null };
    },
    [supabase],
  );

  const signOut = React.useCallback(async () => {
    await supabase?.auth.signOut();
  }, [supabase]);

  const deleteAccount = React.useCallback<
    AuthContextValue["deleteAccount"]
  >(async () => {
    if (!supabase) return { error: "Accounts aren't available yet." };
    const uid = session?.user?.id ?? null;

    // Server route (service-role) deletes the auth user; the FK cascade drops
    // every attempts/sessions/profiles row.
    const res = await fetch("/account/delete", { method: "POST" });
    if (!res.ok) {
      let msg = "Couldn't delete your account. Please try again.";
      try {
        const body = (await res.json()) as { error?: string };
        if (body?.error) msg = body.error;
      } catch {
        /* non-JSON error body — keep the generic message */
      }
      return { error: msg };
    }

    // Wipe the local per-user cache + migration marker, then sign out to guest.
    if (uid) {
      await deleteDatabase(`${GUEST_DB_NAME}-${uid}`);
      // The plan cache and its unsynced-edit marker go with it: the row is gone, so
      // a surviving marker would have this device trying to re-push a deleted
      // account's config forever (issue #181).
      writePlanConfigCache(uid, null);
      writePlanConfigDirty(uid, false);
      try {
        localStorage.removeItem(`deck-migrated:${uid}`);
      } catch {
        /* storage blocked — nothing to clean */
      }
    }
    await supabase.auth.signOut();
    return { error: null };
  }, [supabase, session]);

  const clearBooted = React.useCallback(() => setBootedElsewhere(false), []);

  const value = React.useMemo<AuthContextValue>(
    () => ({
      configured: isSupabaseConfigured,
      loading,
      session,
      user: session?.user ?? null,
      username: usernameOf(session?.user ?? null),
      signUp,
      signIn,
      signOut,
      deleteAccount,
      welcome,
      clearWelcome,
      bootedElsewhere,
      clearBooted,
      planConfig,
      setPlanConfig,
      planSyncError,
      dismissPlanSyncError,
    }),
    [
      loading,
      session,
      signUp,
      signIn,
      signOut,
      deleteAccount,
      welcome,
      clearWelcome,
      bootedElsewhere,
      clearBooted,
      planConfig,
      setPlanConfig,
      planSyncError,
      dismissPlanSyncError,
    ],
  );

  return (
    <AuthContext.Provider value={value}>
      {bootedElsewhere ? (
        <BootedNotice onDismiss={clearBooted} />
      ) : (
        planSyncError && <PlanSyncNotice onDismiss={dismissPlanSyncError} />
      )}
      {children}
    </AuthContext.Provider>
  );
}

/** A one-time notice shown after this session was booted by a newer login. */
function BootedNotice({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="fixed inset-x-0 top-0 z-[60] flex justify-center px-4 py-3">
      <div className="flex max-w-xl items-center gap-3 rounded-xl border-2 border-ink bg-paper px-4 py-2.5 text-sm shadow-[var(--btn-shadow)]">
        <span className="text-ink/80">
          You were signed out because your account was opened on another device.
        </span>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded-md px-2 py-0.5 text-muted hover:bg-ink/5 hover:text-ink"
          aria-label="Dismiss"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

/** Shown when a study-plan edit couldn't be saved to the account and retrying has
 *  stopped (issue #181). Deliberately says the work is safe here and will re-send:
 *  the edit IS applied locally and the marker survives a reload, so the honest line
 *  is "not on your account yet", not "lost". Same voice as ProgressProvider's sync
 *  notice, which says the same thing about the attempt log. */
function PlanSyncNotice({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="fixed inset-x-0 top-0 z-[60] flex justify-center px-4 py-3">
      <div
        role="status"
        aria-live="polite"
        className="flex max-w-xl items-center gap-3 rounded-xl border-2 border-ink bg-paper px-4 py-2.5 text-sm shadow-[var(--btn-shadow)]"
      >
        <span className="text-ink/80">
          Your study plan couldn&rsquo;t save to your account, so it may not match
          on your other devices. It&rsquo;s still saved on this device and
          we&rsquo;ll try again.
        </span>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded-md px-2 py-0.5 text-muted hover:bg-ink/5 hover:text-ink"
          aria-label="Dismiss"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

export function useAuth(): AuthContextValue {
  return React.useContext(AuthContext);
}
