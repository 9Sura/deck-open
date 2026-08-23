"use client";

import * as React from "react";
import { Gear } from "@/components/doodles";
import { SettingsDialog } from "@/components/settings-dialog";
import { cn } from "@/lib/utils";

/**
 * Gear trigger + the settings dialog it owns. Two looks share one component:
 * `icon` (desktop nav cluster) and `row` (a labeled full-width row inside the
 * mobile menu). Each instance owns its own open state; only the visible one is
 * ever clicked, so the two never conflict.
 */
export function SettingsButton({
  variant = "icon",
  className,
  onOpen,
}: {
  variant?: "icon" | "row";
  className?: string;
  /** Called when the dialog opens — e.g. to close the mobile menu. */
  onOpen?: () => void;
}) {
  const [open, setOpen] = React.useState(false);

  const openDialog = () => {
    onOpen?.();
    setOpen(true);
  };

  return (
    <>
      {variant === "row" ? (
        <button
          type="button"
          onClick={openDialog}
          className={cn(
            "flex items-center gap-2 rounded-lg px-3 py-2.5 text-left font-medium text-ink/80 hover:bg-ink/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
            className,
          )}
        >
          <Gear className="h-5 w-5" />
          Settings
        </button>
      ) : (
        <button
          type="button"
          aria-label="Settings"
          onClick={openDialog}
          className={cn(
            "rounded-lg p-2 text-ink/70 transition-colors hover:bg-ink/5 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
            className,
          )}
        >
          <Gear className="h-5 w-5" />
        </button>
      )}
      <SettingsDialog open={open} onClose={() => setOpen(false)} />
    </>
  );
}
