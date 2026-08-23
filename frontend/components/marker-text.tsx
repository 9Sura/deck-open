import * as React from "react";
import { cn } from "@/lib/utils";

/** Hand-marker annotation text — slightly rotated, uppercase-friendly. */
export function MarkerText({
  children,
  rotate = -4,
  className,
}: {
  children: React.ReactNode;
  rotate?: number;
  className?: string;
}) {
  return (
    <span
      className={cn("marker inline-block text-muted", className)}
      style={{ transform: `rotate(${rotate}deg)` }}
    >
      {children}
    </span>
  );
}
