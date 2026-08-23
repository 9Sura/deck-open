"use client";

import * as React from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

/** Fade + rise into view on scroll. Honors reduced-motion via CSS override. */
export function AnimatedSection({
  children,
  className,
  delay = 0,
  as = "div",
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  as?: "div" | "section" | "li";
}) {
  const MotionTag = motion[as];
  return (
    <MotionTag
      className={cn(className)}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.55, ease: [0.2, 0.8, 0.3, 1], delay }}
    >
      {children}
    </MotionTag>
  );
}
