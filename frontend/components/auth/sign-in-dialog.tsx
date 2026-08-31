"use client";

// Username + password auth dialog (sub-plan §4, D2/D11). One form, a Log in /
// Sign up toggle; sign-up adds the 13+ age gate (D11), the Terms + Privacy
// agreement line (#209), and states plainly that there's no password recovery
// yet (no email on file). Reuses the app's Dialog + Card + hand-bordered input
// treatment.

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Dialog } from "@/components/ui/dialog";
import { Card } from "@/components/ui/card";
import { TapeLabel } from "@/components/tape-label";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth/auth-provider";
import { cn } from "@/lib/utils";

type Mode = "signin" | "signup";

const inputClass =
  "hand-border-2 w-full bg-paper px-4 py-2.5 text-[0.95rem] text-ink outline-none transition-colors placeholder:text-muted focus-visible:ring-2 focus-visible:ring-support/50";

export function SignInDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { signIn, signUp } = useAuth();
  const router = useRouter();
  const [mode, setMode] = React.useState<Mode>("signin");
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [ageOk, setAgeOk] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const reset = React.useCallback(() => {
    setPassword("");
    setError(null);
    setBusy(false);
    setAgeOk(false);
  }, []);

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
    setAgeOk(false);
  };

  const close = () => {
    reset();
    setUsername("");
    setMode("signin");
    onClose();
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (mode === "signup" && !ageOk) {
      setError("Please confirm you're 13 or older.");
      return;
    }
    setBusy(true);
    const { error: err } =
      mode === "signin"
        ? await signIn(username, password)
        : await signUp(username, password);
    if (err) {
      setError(err);
      setBusy(false);
      return;
    }
    close();
    // Land every successful login/signup on the dashboard, not whatever page the
    // funnel was opened from.
    router.push("/");
  };

  return (
    <Dialog open={open} onClose={close} label="Account" className="max-w-md">
      <Card variant={0} className="p-5 sm:p-7">
        <div className="mb-5 flex items-center justify-between gap-4">
          <TapeLabel color="accent" rotate={-3}>
            {mode === "signin" ? "log in" : "sign up"}
          </TapeLabel>
          <button
            type="button"
            onClick={close}
            aria-label="Close (Esc)"
            className="rounded-lg px-2 py-1 text-lg leading-none text-ink/60 transition-colors hover:bg-ink/5 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper"
          >
            ✕
          </button>
        </div>

        <p className="mb-5 text-sm text-ink/70">
          {mode === "signin"
            ? "Log in to sync your practice across devices."
            : "Create an account to save your progress and sync it everywhere — no email needed."}
        </p>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="auth-username" className="marker text-sm text-muted">
              Username
            </label>
            <input
              id="auth-username"
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={inputClass}
              placeholder="e.g. deca_ace"
              required
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="auth-password" className="marker text-sm text-muted">
              Password
            </label>
            <input
              id="auth-password"
              name="password"
              type="password"
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              placeholder={mode === "signup" ? "At least 8 characters" : "Your password"}
              required
            />
          </div>

          {mode === "signup" && (
            <label className="flex cursor-pointer items-start gap-2.5 text-sm text-ink/80">
              <input
                type="checkbox"
                checked={ageOk}
                onChange={(e) => setAgeOk(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--accent)]"
              />
              <span>I&apos;m 13 years or older.</span>
            </label>
          )}

          {/* A stated line, NOT a second checkbox (#209): the 13+ box is the one
              thing sign-up refuses to proceed without, and a second gate would
              add a second failure path in onSubmit for no gain. Links open in a
              new tab so a half-filled form isn't thrown away. */}
          {mode === "signup" && (
            <p className="text-xs leading-relaxed text-muted">
              By creating an account you agree to the{" "}
              <Link
                href="/terms"
                target="_blank"
                className="underline underline-offset-2 hover:text-ink"
              >
                Terms
              </Link>{" "}
              and{" "}
              <Link
                href="/privacy"
                target="_blank"
                className="underline underline-offset-2 hover:text-ink"
              >
                Privacy policy
              </Link>
              .
            </p>
          )}

          {error && (
            <p
              role="alert"
              className="sketch-radius border-2 border-dashed border-[var(--diff-hard-line)] bg-[var(--diff-hard-bg)]/30 px-3 py-2 text-sm text-[var(--diff-hard-ink)]"
            >
              {error}
            </p>
          )}

          <Button type="submit" variant="primary" className="w-full" disabled={busy}>
            {busy
              ? mode === "signin"
                ? "Logging in…"
                : "Creating account…"
              : mode === "signin"
                ? "Log in"
                : "Create account"}
          </Button>
        </form>

        {/* No email on file ⇒ no password reset yet (D2). Say it plainly. */}
        <p className="mt-4 text-xs text-muted">
          {mode === "signup"
            ? "Heads up: accounts have no email yet, so there's no password reset — keep your password somewhere safe."
            : "Forgot your password? Recovery isn't available yet (no email on file). Reach out if you're locked out."}
        </p>

        <div className="mt-4 border-t border-dashed border-line pt-4 text-center text-sm text-ink/70">
          {mode === "signin" ? (
            <>
              New to DECK?{" "}
              <button
                type="button"
                onClick={() => switchMode("signup")}
                className={cn("font-semibold text-accent-ink underline-offset-4 hover:underline")}
              >
                Create an account
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => switchMode("signin")}
                className={cn("font-semibold text-accent-ink underline-offset-4 hover:underline")}
              >
                Log in
              </button>
            </>
          )}
        </div>
      </Card>
    </Dialog>
  );
}
