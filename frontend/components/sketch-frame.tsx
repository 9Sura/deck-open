import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * The framed-surface primitive used across cards, panels, and dialogs. Formerly a
 * hand-inked SVG outline (a jittered rounded-rect stretched behind the box); that
 * read as a wobbly, open-cornered "gap" border and — because it was stretched with
 * `preserveAspectRatio="none"` — its corners distorted and it failed to wrap tall
 * or expanded content. It's now a **clean, solid popout**: one closed CSS border
 * that always encapsulates the content, with a soft lift shadow.
 *
 * The API is unchanged so every call site keeps working: `variant` is accepted but
 * no longer alters the look (it only varied the old hand-drawn outline), `filled`
 * toggles the paper fill, and `softShadow` toggles the lift.
 */
export function SketchFrame({
  children,
  className,
  variant,
  filled = true,
  softShadow = true,
  ...props
}: {
  children?: React.ReactNode;
  className?: string;
  /** Legacy hand-outline selector — retained for API compatibility, now unused. */
  variant?: number;
  /** Fill the frame with paper (opaque surface) vs. transparent. */
  filled?: boolean;
  /** Subtle drop shadow for lift. */
  softShadow?: boolean;
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-frame-variant={variant}
      className={cn(
        "rounded-3xl border-2 border-ink",
        filled ? "bg-paper" : "bg-transparent",
        softShadow && "shadow-[var(--frame-shadow)]",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
