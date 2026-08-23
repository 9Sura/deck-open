"use client";

import * as React from "react";
import { AnimatePresence, motion } from "motion/react";
import { cn } from "@/lib/utils";

// A custom dropdown — NOT a native <select>. Native option lists are drawn by
// the OS and can't be styled, so this renders its own popover to match the
// hand-drawn notebook look (like Segmented is a custom control, not native
// radios). Data-driven API mirrors Segmented: `value` + `onChange(value)` +
// `options`, which may be a flat list or grouped.

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectGroup {
  label: string;
  options: SelectOption[];
}

type Items = SelectOption[] | SelectGroup[];

const isGrouped = (items: Items): items is SelectGroup[] =>
  items.length > 0 && "options" in items[0];

/** Flatten to the selectable options, preserving order, for keyboard nav. */
function flatten(items: Items): SelectOption[] {
  return isGrouped(items) ? items.flatMap((g) => g.options) : items;
}

export function Select({
  value,
  onChange,
  options,
  placeholder = "Select…",
  disabled = false,
  className,
  "aria-label": ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  options: Items;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
}) {
  const flat = React.useMemo(() => flatten(options), [options]);
  const selected = flat.find((o) => o.value === value);

  const [open, setOpen] = React.useState(false);
  const [active, setActive] = React.useState(-1); // highlighted index into `flat`

  const rootRef = React.useRef<HTMLDivElement>(null);
  const buttonRef = React.useRef<HTMLButtonElement>(null);
  const listRef = React.useRef<HTMLUListElement>(null);
  const optionRefs = React.useRef<(HTMLLIElement | null)[]>([]);
  const listboxId = React.useId();

  // Typeahead buffer.
  const typed = React.useRef("");
  const typedTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const nextEnabled = React.useCallback(
    (from: number, dir: 1 | -1) => {
      const n = flat.length;
      for (let step = 1; step <= n; step++) {
        const i = (from + dir * step + n * step) % n;
        if (!flat[i]?.disabled) return i;
      }
      return from;
    },
    [flat],
  );

  const openMenu = React.useCallback(
    (highlight: "selected" | "first" | "last") => {
      const selIdx = flat.findIndex((o) => o.value === value);
      let start =
        highlight === "last"
          ? nextEnabled(0, -1)
          : highlight === "selected" && selIdx >= 0
          ? selIdx
          : nextEnabled(-1, 1);
      if (flat[start]?.disabled) start = nextEnabled(start, 1);
      setActive(start);
      setOpen(true);
    },
    [flat, value, nextEnabled],
  );

  const close = React.useCallback((refocus = true) => {
    setOpen(false);
    setActive(-1);
    if (refocus) buttonRef.current?.focus();
  }, []);

  const commit = React.useCallback(
    (idx: number) => {
      const opt = flat[idx];
      if (!opt || opt.disabled) return;
      onChange(opt.value);
      close();
    },
    [flat, onChange, close],
  );

  // Close on outside click.
  React.useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) close(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open, close]);

  // Keep the highlighted option in view.
  React.useEffect(() => {
    if (open && active >= 0) {
      optionRefs.current[active]?.scrollIntoView({ block: "nearest" });
    }
  }, [open, active]);

  // Focus the list when it opens so keyboard events land here.
  React.useEffect(() => {
    if (open) listRef.current?.focus();
  }, [open]);

  const typeahead = React.useCallback(
    (ch: string) => {
      typed.current += ch.toLowerCase();
      if (typedTimer.current) clearTimeout(typedTimer.current);
      typedTimer.current = setTimeout(() => (typed.current = ""), 600);
      const match = flat.findIndex(
        (o) => !o.disabled && o.label.toLowerCase().startsWith(typed.current),
      );
      if (match >= 0) setActive(match);
    },
    [flat],
  );

  function onButtonKeyDown(e: React.KeyboardEvent) {
    if (disabled) return;
    if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openMenu("selected");
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      openMenu("last");
    }
  }

  function onListKeyDown(e: React.KeyboardEvent) {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActive((i) => nextEnabled(i < 0 ? -1 : i, 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((i) => nextEnabled(i < 0 ? 0 : i, -1));
        break;
      case "Home":
        e.preventDefault();
        setActive(nextEnabled(-1, 1));
        break;
      case "End":
        e.preventDefault();
        setActive(nextEnabled(0, -1));
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        if (active >= 0) commit(active);
        break;
      case "Escape":
        e.preventDefault();
        close();
        break;
      case "Tab":
        close(false);
        break;
      default:
        if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
          typeahead(e.key);
        }
    }
  }

  // Render options with group headers, tracking the running flat index so
  // refs / active state line up with keyboard nav.
  let flatIdx = -1;
  const renderOption = (opt: SelectOption) => {
    flatIdx += 1;
    const idx = flatIdx;
    const isSelected = opt.value === value;
    const isActive = idx === active;
    return (
      <li
        key={opt.value}
        ref={(el) => {
          optionRefs.current[idx] = el;
        }}
        id={`${listboxId}-opt-${idx}`}
        role="option"
        aria-selected={isSelected}
        aria-disabled={opt.disabled || undefined}
        onMouseEnter={() => !opt.disabled && setActive(idx)}
        onClick={() => commit(idx)}
        className={cn(
          "flex cursor-pointer items-center gap-2 px-3 py-2 text-[0.95rem] transition-colors",
          opt.disabled && "cursor-not-allowed text-muted opacity-50",
          !opt.disabled && isActive && "bg-highlight/40",
          isSelected && "font-semibold text-ink",
        )}
      >
        <span
          aria-hidden
          className={cn(
            "w-4 shrink-0 text-highlight-ink",
            isSelected ? "opacity-100" : "opacity-0",
          )}
        >
          ✓
        </span>
        <span className="flex-1">{opt.label}</span>
      </li>
    );
  };

  return (
    <div ref={rootRef} className="relative min-w-0">
      <button
        ref={buttonRef}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-label={ariaLabel}
        disabled={disabled}
        onClick={() => (open ? close(false) : openMenu("selected"))}
        onKeyDown={onButtonKeyDown}
        className={cn(
          "hand-border flex h-12 w-full min-w-0 items-center bg-paper px-4 pr-10 text-left text-[0.95rem] font-medium text-ink outline-none transition-colors focus-visible:ring-2 focus-visible:ring-support/50",
          disabled && "cursor-not-allowed opacity-50",
          className,
        )}
      >
        <span className={cn("min-w-0 truncate", !selected && "text-muted")}>
          {selected ? selected.label : placeholder}
        </span>
        <motion.svg
          aria-hidden
          viewBox="0 0 24 24"
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.18 }}
          className="pointer-events-none absolute right-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-ink/50"
          fill="none"
          stroke="currentColor"
          strokeWidth={2.2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="m6 9 6 6 6-6" />
        </motion.svg>
      </button>

      <AnimatePresence>
        {open && (
          <motion.ul
            ref={listRef}
            id={listboxId}
            role="listbox"
            tabIndex={-1}
            aria-activedescendant={
              active >= 0 ? `${listboxId}-opt-${active}` : undefined
            }
            onKeyDown={onListKeyDown}
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute left-0 right-0 top-full z-50 mt-2 max-h-72 origin-top overflow-auto border-2 border-ink bg-paper py-1.5 shadow-[3px_3px_0_0_var(--ink)] outline-none sketch-radius"
          >
            {isGrouped(options)
              ? options.map((group) => (
                  <li key={group.label} role="presentation">
                    <div className="marker px-3 pb-1 pt-2 text-xs uppercase tracking-wide text-muted">
                      {group.label}
                    </div>
                    <ul role="presentation">
                      {group.options.map(renderOption)}
                    </ul>
                  </li>
                ))
              : options.map(renderOption)}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
