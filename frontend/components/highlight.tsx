"use client";

import * as React from "react";
import { motion, useInView } from "motion/react";
import { cn } from "@/lib/utils";

type HighlightColor = "highlight" | "support" | "accent";

const COLOR: Record<HighlightColor, string> = {
  highlight: "var(--highlight)",
  support: "var(--support)",
  accent: "var(--accent)",
};

/**
 * Restyled highlighter — demoted to a *secondary* accent behind <Loop>. The
 * swab now carries a soft crayon/grain edge (feTurbulence-masked) instead of a
 * flat multiply blob, so it reads hand-laid rather than printed. Draws in
 * left-to-right on first scroll into view.
 */
export function Highlight({
  children,
  color = "highlight",
  className,
  rotate = 0,
  animate = true,
}: {
  children: React.ReactNode;
  color?: HighlightColor;
  className?: string;
  rotate?: number;
  animate?: boolean;
}) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  // SSR-stable unique id — a module counter would desync between server and
  // client render order and cause a hydration mismatch on the filter id.
  const maskId = `grain-${React.useId().replace(/:/g, "")}`;

  return (
    <span
      ref={ref}
      className={cn("relative inline-block whitespace-pre", className)}
      style={{ transform: rotate ? `rotate(${rotate}deg)` : undefined }}
    >
      <motion.svg
        aria-hidden
        className="absolute -inset-x-1 inset-y-0 -z-10 h-full w-[calc(100%+0.5rem)]"
        // Blend is theme-driven: multiply on light grounds, screen on dark —
        // else the swab drives toward black and the highlighter vanishes. Motion
        // types mixBlendMode to the literal union, so cast the CSS var through.
        style={{
          mixBlendMode: "var(--highlight-blend, multiply)" as "multiply",
          originX: 0,
        }}
        viewBox="0 0 100 24"
        preserveAspectRatio="none"
        initial={animate ? { scaleX: 0 } : false}
        animate={animate ? (inView ? { scaleX: 1 } : { scaleX: 0 }) : { scaleX: 1 }}
        transition={{ duration: 0.5, ease: [0.2, 0.8, 0.3, 1] }}
      >
        <defs>
          {/* grainy edge: turbulence displaces the swab outline for a crayon feel */}
          <filter id={maskId} x="-10%" y="-20%" width="120%" height="140%">
            <feTurbulence type="fractalNoise" baseFrequency="0.9 0.4" numOctaves="2" result="n" />
            <feDisplacementMap in="SourceGraphic" in2="n" scale="3.2" />
          </filter>
        </defs>
        {/* slightly irregular blob, roughened by the filter */}
        <path
          d="M2.4 6.3C20 3.1 55 2.2 97.5 4.1c1.8.4 2.1 3.4 1.2 6.9-.7 3-.2 6.4-1.6 8.2-2.3 1.4-31 2.1-63 1.3-18-.5-31-.8-32.2-2.1-1.3-2-1.1-6.2-.6-9.4.3-2.2.6-4.5 1.1-2.7Z"
          fill={COLOR[color]}
          filter={`url(#${maskId})`}
        />
      </motion.svg>
      <span className="relative">{children}</span>
    </span>
  );
}
