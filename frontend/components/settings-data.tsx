"use client";

// The "Data" settings panel (plan 08 §4; sub-plan §10, D12). Three controls over
// the local (and, when signed in, synced) progress log:
//   - Export my data (JSON) — portability, a good-faith minor-data practice (4e).
//   - Reset progress — two-step; for a signed-in user it now wipes local + remote.
//   - Delete account — signed-in only; typed-confirm; server cascade + local wipe.

import * as React from "react";
import { Button } from "@/components/ui/button";
import { useProgress } from "@/components/progress-provider";
import { useProgressData } from "@/hooks/use-progress-data";
import { useAuth } from "@/components/auth/auth-provider";
import { hasProgressLogging } from "@/lib/auth/gated-routes";
import { cn } from "@/lib/utils";

type Phase = "idle" | "confirming" | "resetting" | "done" | "failed";
type DeletePhase = "idle" | "confirming" | "deleting";

export function SettingsData() {
  const { resetProgress, store, hydrated } = useProgress();
  const { attempts, sessions, loading } = useProgressData();
  const auth = useAuth();
  const { user, username, deleteAccount, setPlanConfig } = auth;
  const [phase, setPhase] = React.useState<Phase>("idle");

  const total = attempts.length;
  const sessionCount = sessions.length;
  const nothingToReset = hydrated && !loading && total === 0;
  const signedIn = Boolean(user);
  // Logging is account-only (D10), so without one there is no store to describe
  // — a guest and an account-less build both hold a NullStore. Saying "stored on
  // this device" there is simply untrue, and it's the copy someone reads when
  // they're trying to work out why Progress is empty (issue #47).
  const logging = hasProgressLogging(auth);

  // ---- export --------------------------------------------------------------
  const [exporting, setExporting] = React.useState(false);
  const [exportFailed, setExportFailed] = React.useState(false);
  const doExport = React.useCallback(async () => {
    setExporting(true);
    setExportFailed(false);
    try {
      const data = await store.exportAll();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      // Both halves of this are load-bearing off Chromium, and neither failure
      // is catchable: a download that never starts raises nothing, so the catch
      // below can't see it and the button just flips back with no file (#250).
      //   - A synthetic click on a DETACHED anchor is ignored by some engines,
      //     so the anchor goes into the document before the click and out after.
      //   - Revoking the object URL in the same task can cancel a fetch the
      //     browser hasn't started yet, so the revoke is deferred a task. It
      //     still runs — the blob isn't leaked, just released a tick later.
      const a = document.createElement("a");
      a.href = url;
      a.download = "deck-progress-export.json";
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch {
      // Say so rather than re-enabling a button that looks like it did nothing.
      setExportFailed(true);
    }
    setExporting(false);
  }, [store]);

  // ---- reset ---------------------------------------------------------------
  // Reset is irreversible and explicitly confirmed, so it must never report
  // success it didn't achieve: a failed wipe leaves the user believing their data
  // is gone when it's still here (and, signed in, still on the server).
  //
  // It also clears TODAY'S PLAN, which the progress store can't reach (issue
  // #214). The day plan lives on `profiles.plan_config`, written through the auth
  // provider rather than the store, so a wipe of attempts + sessions used to leave
  // `config.today` behind holding the ids of the rows it just deleted, the saved
  // question set for each task, and the day's frozen recommended list — the
  // dashboard kept rendering the pre-reset cards, and Start re-served the identical
  // questions. Only `today` goes: the target cluster/level, competition date and
  // `diagnosticDone` are plan SETUP, not progress, and dropping them would push a
  // reset straight back into first-run onboarding. Today's user-added tasks do go
  // with it — they're part of the day being cleared.
  //
  // Sequenced after the wipe so a failed reset leaves the plan alone, and awaited
  // rather than fired off: it resolves once the row write has been attempted, and
  // it can't reject (a failed write keeps the dirty marker and retries), while the
  // on-screen plan is already cleared optimistically either way.
  const doReset = React.useCallback(async () => {
    setPhase("resetting");
    try {
      await resetProgress();
    } catch {
      setPhase("failed");
      return;
    }
    await setPlanConfig((prev) => (prev?.today ? { ...prev, today: undefined } : prev));
    setPhase("done");
  }, [resetProgress, setPlanConfig]);

  React.useEffect(() => {
    if (phase !== "done") return;
    const t = setTimeout(() => setPhase("idle"), 2500);
    return () => clearTimeout(t);
  }, [phase]);

  // ---- delete account ------------------------------------------------------
  const [deletePhase, setDeletePhase] = React.useState<DeletePhase>("idle");
  const [confirmName, setConfirmName] = React.useState("");
  const [deleteError, setDeleteError] = React.useState<string | null>(null);
  const canDelete = confirmName.trim() === (username ?? "").trim() && !!username;

  const doDelete = React.useCallback(async () => {
    setDeletePhase("deleting");
    setDeleteError(null);
    const { error } = await deleteAccount();
    if (error) {
      setDeleteError(error);
      setDeletePhase("confirming");
      return;
    }
    // Success → auth state flips to guest; this section unmounts on its own.
  }, [deleteAccount]);

  return (
    <div className="space-y-5">
      <div>
        <h3 className="font-display text-lg font-bold tracking-tight">Your practice data</h3>
        <p className="mt-1 text-sm text-ink/70">
          {logging ? (
            <>
              Every graded question and session you complete is stored on this device to power your{" "}
              <span className="font-medium">Progress</span> and{" "}
              <span className="font-medium">Review</span>{" "}
              pages. Because you&rsquo;re signed in,
              it&rsquo;s also synced to your account across devices.
            </>
          ) : auth.configured ? (
            <>
              Your practice isn&rsquo;t being recorded while you&rsquo;re signed out — the{" "}
              <span className="font-medium">Progress</span> and{" "}
              <span className="font-medium">Review</span> pages come with a free account. Nothing
              is stored on this device and nothing is uploaded.
            </>
          ) : (
            <>
              This copy of DECK has no accounts set up, so your practice isn&rsquo;t being recorded:
              nothing is stored on this device and nothing is uploaded. Everything else works
              normally.
            </>
          )}
        </p>
      </div>

      <div className="sketch-radius border-2 border-line bg-paper-2/50 px-4 py-3 text-sm">
        {!hydrated || loading ? (
          <span className="text-muted">Loading your data…</span>
        ) : !logging ? (
          <span className="text-muted">Nothing is being recorded.</span>
        ) : total === 0 ? (
          <span className="text-muted">No progress stored yet.</span>
        ) : (
          <span className="text-ink/80">
            <span className="stat font-semibold text-ink">{total}</span> answered question
            {total === 1 ? "" : "s"} across{" "}
            <span className="stat font-semibold text-ink">{sessionCount}</span> session
            {sessionCount === 1 ? "" : "s"}.
          </span>
        )}
      </div>

      {/* Export — portability. */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">Export my data</p>
          <p className="mt-0.5 text-xs text-muted">
            Download all your attempts and sessions as a JSON file.
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Button
            size="sm"
            variant="outline"
            disabled={nothingToReset || exporting}
            onClick={doExport}
          >
            {exporting ? "Exporting…" : "Export (JSON)"}
          </Button>
          {exportFailed && (
            <p role="alert" className="text-xs text-[var(--diff-hard-ink)]">
              Couldn’t read your data — try again.
            </p>
          )}
        </div>
      </div>

      {/* Reset — two-step confirm, irreversible. */}
      <div className="sketch-radius border-2 border-dashed border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)]/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink">Reset progress</p>
            <p className="mt-0.5 text-xs text-muted">
              {/* Same rule as the header copy: without logging there is no local
                  store either, so don't claim there's something here to erase. */}
              {logging
                ? "Permanently deletes all answered questions and sessions on this device and on your account, and clears today’s plan. Your target event and date are kept. This can’t be undone."
                : "Nothing is being recorded, so there’s nothing to reset."}
            </p>
          </div>

          {phase === "done" ? (
            <span className="stat shrink-0 text-sm font-semibold text-[var(--diff-easy-ink)]">
              ✓ Progress cleared
            </span>
          ) : phase === "failed" ? (
            <div className="flex shrink-0 flex-col items-end gap-1">
              <Button
                size="sm"
                variant="outline"
                className="border-[var(--diff-hard-line)] text-[var(--diff-hard-ink)] hover:bg-[var(--diff-hard-bg)]"
                onClick={() => setPhase("confirming")}
              >
                Try again
              </Button>
              <p role="alert" className="text-xs text-[var(--diff-hard-ink)]">
                Couldn’t clear your progress — nothing was deleted.
              </p>
            </div>
          ) : phase === "confirming" ? (
            <div className="flex shrink-0 items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                className={cn(
                  "border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] text-[var(--diff-hard-ink)]",
                  "hover:bg-[var(--diff-hard-bg)]",
                )}
                onClick={doReset}
              >
                Confirm reset
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setPhase("idle")}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button
              size="sm"
              variant="outline"
              className="shrink-0 border-[var(--diff-hard-line)] text-[var(--diff-hard-ink)] hover:bg-[var(--diff-hard-bg)]"
              disabled={nothingToReset || phase === "resetting"}
              onClick={() => setPhase("confirming")}
            >
              {phase === "resetting" ? "Resetting…" : "Reset progress"}
            </Button>
          )}
        </div>
      </div>

      {/* Delete account — signed-in only, typed-confirm, irreversible. */}
      {signedIn && (
        <div className="sketch-radius border-2 border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)]/20 p-4">
          <p className="text-sm font-semibold text-[var(--diff-hard-ink)]">Delete account</p>
          <p className="mt-0.5 text-xs text-muted">
            Permanently erases your account and all of its data everywhere. Your login stops working.
            This can’t be undone.
          </p>

          {deletePhase === "idle" ? (
            <Button
              size="sm"
              variant="outline"
              className="mt-3 border-[var(--diff-hard-line)] text-[var(--diff-hard-ink)] hover:bg-[var(--diff-hard-bg)]"
              onClick={() => {
                setDeletePhase("confirming");
                setConfirmName("");
                setDeleteError(null);
              }}
            >
              Delete account
            </Button>
          ) : (
            <div className="mt-3 space-y-2.5">
              <label htmlFor="delete-confirm" className="block text-xs text-ink/70">
                Type your username{" "}
                <span className="font-semibold text-ink">{username}</span> to confirm:
              </label>
              <input
                id="delete-confirm"
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
                autoCapitalize="none"
                spellCheck={false}
                disabled={deletePhase === "deleting"}
                className="hand-border-2 w-full bg-paper px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-[var(--diff-hard-line)]"
                placeholder={username ?? ""}
              />
              {deleteError && (
                <p role="alert" className="text-xs text-[var(--diff-hard-ink)]">
                  {deleteError}
                </p>
              )}
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)] text-[var(--diff-hard-ink)] hover:bg-[var(--diff-hard-bg)]"
                  disabled={!canDelete || deletePhase === "deleting"}
                  onClick={doDelete}
                >
                  {deletePhase === "deleting" ? "Deleting…" : "Permanently delete"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={deletePhase === "deleting"}
                  onClick={() => setDeletePhase("idle")}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
