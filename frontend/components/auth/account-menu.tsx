"use client";

// The Nav account control (sub-plan §4). Guest → a compact "Sign in" pill that
// opens the auth dialog; signed-in → an avatar button that opens a small dropdown
// (username + Sign out), so the bar stays uncluttered. Renders nothing until the
// Supabase project is provisioned, so guest-only builds show exactly today's Nav.
//
// Two variants share the component: `pill` (desktop nav cluster) and `row` (the
// full-width mobile menu row), mirroring SettingsButton.

import * as React from "react";
import { Button } from "@/components/ui/button";
import { SignInDialog } from "@/components/auth/sign-in-dialog";
import { useAuth } from "@/components/auth/auth-provider";
import { cn } from "@/lib/utils";

export function AccountMenu({
  variant = "pill",
  className,
  onAct,
}: {
  variant?: "pill" | "row";
  className?: string;
  /** Called when the dialog opens or the user signs out — e.g. close mobile menu. */
  onAct?: () => void;
}) {
  const { configured, loading, user, username, signOut } = useAuth();
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement>(null);

  // Close the dropdown on outside click / Esc.
  React.useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  // No project yet → no auth UI at all (guest mode is the whole app).
  if (!configured) return null;

  const openDialog = () => {
    onAct?.();
    setDialogOpen(true);
  };

  const doSignOut = async () => {
    onAct?.();
    setMenuOpen(false);
    await signOut();
  };

  const label = username ?? "Account";
  const initial = (username ?? "?").charAt(0).toUpperCase();

  if (variant === "row") {
    return (
      <>
        {user ? (
          <div className={cn("flex flex-col gap-1", className)}>
            <div className="flex items-center gap-2 px-3 py-2 font-medium text-ink/80">
              <Avatar initial={initial} />
              {label}
            </div>
            <button
              type="button"
              onClick={doSignOut}
              className="rounded-lg px-3 py-2.5 text-left font-medium text-ink/70 hover:bg-ink/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper"
            >
              Sign out
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={openDialog}
            disabled={loading}
            className={cn(
              "rounded-lg px-3 py-2.5 text-left font-medium text-ink/80 hover:bg-ink/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
              className,
            )}
          >
            Sign in
          </button>
        )}
        <SignInDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
      </>
    );
  }

  return (
    <>
      {user ? (
        <div ref={menuRef} className={cn("relative", className)}>
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-label="Account menu"
            onClick={() => setMenuOpen((v) => !v)}
            className="sketch-radius flex h-8 w-8 items-center justify-center border-2 border-ink bg-accent text-xs font-bold text-[var(--on-accent)] transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper"
          >
            {initial}
          </button>
          {menuOpen && (
            <div
              role="menu"
              className="sketch-radius absolute right-0 top-full z-50 mt-2 w-44 border-2 border-ink bg-paper p-1.5 shadow-[var(--btn-shadow)]"
            >
              <div className="px-2.5 pt-1 text-xs text-muted">Signed in as</div>
              <div className="truncate px-2.5 pb-2 text-sm font-semibold text-ink">
                {label}
              </div>
              <div className="my-1 border-t border-dashed border-line" />
              <button
                type="button"
                role="menuitem"
                onClick={doSignOut}
                className="w-full rounded-md px-2.5 py-1.5 text-left text-sm text-ink/80 transition-colors hover:bg-ink/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      ) : (
        <Button
          size="sm"
          variant="outline"
          className={className}
          disabled={loading}
          onClick={openDialog}
        >
          Sign in
        </Button>
      )}
      <SignInDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </>
  );
}

function Avatar({ initial }: { initial: string }) {
  return (
    <span className="sketch-radius flex h-7 w-7 shrink-0 items-center justify-center border-2 border-ink bg-accent text-xs font-bold text-[var(--on-accent)]">
      {initial}
    </span>
  );
}
