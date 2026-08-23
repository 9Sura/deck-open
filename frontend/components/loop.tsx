"use client";

import * as React from "react";
import { motion, useInView } from "motion/react";
import { cn } from "@/lib/utils";

type LoopColor = "accent" | "support" | "highlight" | "ink";

const COLOR: Record<LoopColor, string> = {
  accent: "var(--accent)",
  support: "var(--support)",
  highlight: "var(--highlight)",
  ink: "var(--ink)",
};

/**
 * The signature accent: a rough ink ellipse looped around a keyword — like
 * circling the correct answer on an exam. Replaces Aniko's highlighter swipe as
 * the hero move. The loop overshoots its start (a hand-drawn "go around once"),
 * stretches to the word box, and draws itself in via `pathLength` the first time
 * it scrolls into view. `vectorEffect` keeps the ink weight even at any width.
 */
export function Loop({
  children,
  color = "accent",
  className,
  rotate = -1.5,
  animate = true,
}: {
  children: React.ReactNode;
  color?: LoopColor;
  className?: string;
  rotate?: number;
  animate?: boolean;
}) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  const drawn = animate ? inView : true;

  return (
    <span
      ref={ref}
      className={cn("relative inline-block whitespace-pre", className)}
      style={{ transform: rotate ? `rotate(${rotate}deg)` : undefined }}
    >
      <svg
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-1/2 -z-10 h-[150%] w-[118%] -translate-x-1/2 -translate-y-1/2"
        viewBox="0 0 100 48"
        preserveAspectRatio="none"
        fill="none"
      >
        <motion.path
          d="M74 42C93 38 96 13 66 7 39 1.6 8 6 5 22c-2.4 13 24 22 57 21 21-.7 33-7 31-17"
          stroke={COLOR[color]}
          strokeWidth={2.4}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
          initial={animate ? { pathLength: 0 } : false}
          animate={{ pathLength: drawn ? 1 : 0 }}
          transition={{ duration: 0.7, ease: [0.3, 0.1, 0.2, 1] }}
        />
      </svg>
      <span className="relative">{children}</span>
    </span>
  );
}
