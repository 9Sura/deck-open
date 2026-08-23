"use client";

import * as React from "react";
import { motion, useInView } from "motion/react";
import { cn } from "@/lib/utils";

type AccentColor = "accent" | "support" | "ink";

const COLOR: Record<AccentColor, string> = {
  accent: "var(--accent)",
  support: "var(--support)",
  ink: "var(--ink)",
};

/**
 * Secondary accent: a rough hand-drawn underline swept under a word. Calmer
 * companion to <Loop>; draws in on scroll.
 */
export function Underline({
  children,
  color = "support",
  className,
  animate = true,
}: {
  children: React.ReactNode;
  color?: AccentColor;
  className?: string;
  animate?: boolean;
}) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  const drawn = animate ? inView : true;

  return (
    <span ref={ref} className={cn("relative inline-block whitespace-pre", className)}>
      <span className="relative">{children}</span>
      <svg
        aria-hidden
        className="pointer-events-none absolute -bottom-1 left-0 h-2 w-full"
        viewBox="0 0 100 8"
        preserveAspectRatio="none"
        fill="none"
      >
        <motion.path
          d="M1 5.5C22 2.2 44 2 66 4.2c11 1.1 22 1.6 33 .4"
          stroke={COLOR[color]}
          strokeWidth={2.2}
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          initial={animate ? { pathLength: 0 } : false}
          animate={{ pathLength: drawn ? 1 : 0 }}
          transition={{ duration: 0.5, ease: [0.2, 0.8, 0.3, 1] }}
        />
      </svg>
    </span>
  );
}

/**
 * Secondary accent: hand-drawn corner brackets framing a term — like marking a
 * graded answer. Static (no draw-in); pairs well with the hand font.
 */
export function Bracket({
  children,
  color = "ink",
  className,
}: {
  children: React.ReactNode;
  color?: AccentColor;
  className?: string;
}) {
  const stroke = COLOR[color];
  return (
    <span className={cn("relative inline-block px-2.5", className)}>
      <svg
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-0 h-full w-2"
        viewBox="0 0 8 40"
        preserveAspectRatio="none"
        fill="none"
      >
        <path
          d="M7 2C3.5 2 2 4 2 8v24c0 4 1.5 6 5 6"
          stroke={stroke}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <span className="relative">{children}</span>
      <svg
        aria-hidden
        className="pointer-events-none absolute inset-y-0 right-0 h-full w-2"
        viewBox="0 0 8 40"
        preserveAspectRatio="none"
        fill="none"
      >
        <path
          d="M1 2c3.5 0 5 2 5 6v24c0 4-1.5 6-5 6"
          stroke={stroke}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </span>
  );
}
