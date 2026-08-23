"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { NoticeOutlet } from "@/components/notice-layer";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

/** false on the server, true once mounted — the portal-safe hydration guard. */
function useHydrated(): boolean {
  return React.useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

/**
 * Reusable modal — the app's blurred-backdrop + focus-trap treatment, extracted
 * from the LiveQuizModal a11y pattern (scroll lock, portal, Esc, click-outside,
 * restore-focus-on-close, hydration guard). Renders the backdrop and a
 * focusable panel wrapper; callers supply the panel's inner content.
 */
export function Dialog({
  open,
  onClose,
  label,
  children,
  className,
}: {
  open: boolean;
  onClose: () => void;
  /** Accessible name for the dialog (aria-label). */
  label: string;
  children: React.ReactNode;
  /** Extra classes for the panel wrapper (e.g. max-width override). */
  className?: string;
}) {
  const hydrated = useHydrated();
  const panelRef = React.useRef<HTMLDivElement>(null);
  const restoreFocusRef = React.useRef<HTMLElement | null>(null);

  // Focus the panel + lock scroll when it OPENS; restore focus on close. Depends
  // on `open` only — so a parent re-render (e.g. typing in an input, which passes
  // a fresh onClose reference) never re-runs this and never steals focus back.
  React.useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => panelRef.current?.focus());
    return () => {
      document.body.style.overflow = prevOverflow;
      cancelAnimationFrame(raf);
      restoreFocusRef.current?.focus?.();
    };
  }, [open]);

  // Esc-to-close + Tab focus-trap. Separate effect: it needs the current
  // `onClose`, and re-binding the listener on that change is harmless (no refocus).
  React.useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const nodes = panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!hydrated || !open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 px-4 py-8 backdrop-blur-md sm:py-12"
      role="dialog"
      aria-modal="true"
      aria-label={label}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        className={cn("w-full max-w-2xl outline-none", className)}
      >
        {children}
        {/* App-wide storage/sync notices, hosted INSIDE the panel so they paint
            above this portal, sit in the `aria-modal` subtree and are reachable
            by the Tab trap above (issue #196). Last in the panel, so Dismiss is
            the last stop in the cycle. */}
        <NoticeOutlet />
      </div>
    </div>,
    document.body,
  );
}
