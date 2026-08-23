"use client";

// The guest CTA funnel (plan 09 §2b, D7). A signed-out user can browse the
// Question Bank freely, but every OTHER practice entry point funnels to sign-up
// instead of routing: a gated click opens the create-account dialog. A signed-in
// user (or an unconfigured, account-less build — "use the app as today") passes
// straight through.
//
// Two shapes share one hook: `useRequireAccount()` for wiring a handler onto an
// existing control (e.g. the nav Dashboard button, a marketing CTA <Link>), and
// <GuestGate> for wrapping arbitrary children whose click should be gated.

import * as React from "react";
import { SignInDialog } from "@/components/auth/sign-in-dialog";
import { useAuth } from "@/components/auth/auth-provider";

interface RequireAccount {
  /** True only when a real account is needed AND possible (configured + guest). */
  needsAccount: boolean;
  /**
   * Click guard: when an account is needed, prevents the default (navigation)
   * and opens the sign-up dialog; otherwise a no-op so the control acts normally.
   */
  guard: (e: React.MouseEvent) => void;
  /** Programmatically open the dialog (for non-link buttons). */
  open: () => void;
  /** Mount ONCE per hook use — the create-account dialog it controls. */
  dialog: React.ReactNode;
}

export function useRequireAccount(): RequireAccount {
  const { configured, session } = useAuth();
  const [dialogOpen, setDialogOpen] = React.useState(false);

  // Only funnel when accounts exist and the user is a guest. With no Supabase
  // project, everyone is a guest but there's nothing to sign up for, so the app
  // stays fully usable (the control navigates as it does today).
  const needsAccount = configured && !session;

  const guard = React.useCallback(
    (e: React.MouseEvent) => {
      if (!needsAccount) return;
      e.preventDefault();
      setDialogOpen(true);
    },
    [needsAccount],
  );

  const open = React.useCallback(() => setDialogOpen(true), []);

  const dialog = (
    <SignInDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
  );

  return { needsAccount, guard, open, dialog };
}

/**
 * Wrap a clickable (a button or link) so a guest's click opens sign-up instead.
 * Renders its own dialog — drop it around any single CTA.
 */
export function GuestGate({ children }: { children: React.ReactNode }) {
  const { needsAccount, guard, dialog } = useRequireAccount();
  return (
    <>
      <span
        onClickCapture={needsAccount ? guard : undefined}
        className="contents"
      >
        {children}
      </span>
      {dialog}
    </>
  );
}
