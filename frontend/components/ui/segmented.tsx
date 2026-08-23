"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface SegmentedOption<T extends string | number> {
  value: T;
  label: string;
  sub?: string;
  disabled?: boolean;
}

/** Pill segmented control — used for level / question-count presets. */
export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  className,
}: {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {options.map((opt) => {
        const active = opt.value === value;
        const disabled = opt.disabled ?? false;
        return (
          <button
            key={String(opt.value)}
            type="button"
            onClick={() => !disabled && onChange(opt.value)}
            disabled={disabled}
            aria-pressed={active}
            className={cn(
              "sketch-radius flex flex-col items-center border-2 px-4 py-2.5 text-center text-ink transition-all active:scale-[0.97]",
              disabled
                ? "cursor-not-allowed border-ink/10 bg-paper-2 text-muted opacity-50 active:scale-100"
                : active
                ? "border-ink bg-highlight/50 shadow-[2px_2px_0_0_var(--ink)]"
                : "border-ink/20 bg-paper hover:-translate-y-0.5 hover:border-ink/40 hover:bg-paper-2"
            )}
          >
            <span className="text-[0.95rem] font-semibold leading-tight">{opt.label}</span>
            {opt.sub && (
              <span className="text-xs text-muted">{opt.sub}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
