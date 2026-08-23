import * as React from "react";
import { cn } from "@/lib/utils";

type TagColor = "accent" | "support" | "highlight";

// Tinted fill + inked border; text stays ink for legibility on cream.
const TINT: Record<TagColor, string> = {
  accent: "bg-accent/15",
  support: "bg-support/15",
  highlight: "bg-highlight/40",
};

/**
 * A hand-drawn tag / ink-stamp — our own badge motif, replacing Aniko's rotated
 * tape stickers. An inked (hand-border) chip on a tinted wash, set in the hand
 * font. Kept the `TapeLabel` name so call sites read the same; the look is new.
 */
export function TapeLabel({
  children,
  color = "support",
  rotate = -2,
  className,
}: {
  children: React.ReactNode;
  color?: TagColor;
  rotate?: number;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "marker hand-border inline-block px-3 py-1 text-sm leading-none text-ink",
        TINT[color],
        className
      )}
      style={{ transform: rotate ? `rotate(${rotate}deg)` : undefined }}
    >
      {children}
    </span>
  );
}
