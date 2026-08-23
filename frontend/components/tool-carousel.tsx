"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ComponentProps } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ToolCard } from "@/components/tool-card";
import { cn } from "@/lib/utils";

type Tool = ComponentProps<typeof ToolCard>;

type Selected = {
  index: number;
  tool: Tool;
  dx: number; // card-center minus root-center, at press time
  dy: number;
  w: number; // card width at press time
};

const CENTER_W = 380; // px — resting width of the centered card

/**
 * Tool cards on a slow, continuously revolving belt (.animate-revolve in
 * globals.css). PRESS a card to pull it to the center: it flies from its live
 * belt position to the middle, the revolving belt behind blurs + dims to focus
 * attention, and an ✕ (or a backdrop click / Escape) sends it back. The belt
 * keeps revolving behind the blur; the pressed card's slot goes blank and
 * travels on. Keyboard: belt cards are buttons (Enter opens); focus pauses the
 * belt so a focused card doesn't slide.
 */
export function ToolCarousel({ tools }: { tools: Tool[] }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<Selected | null>(null);
  const doubled = [...tools, ...tools];

  const open = useCallback((index: number, tool: Tool, el: HTMLElement) => {
    const root = rootRef.current;
    if (!root) return;
    const c = el.getBoundingClientRect();
    const r = root.getBoundingClientRect();
    setSelected({
      index,
      tool,
      dx: c.left + c.width / 2 - (r.left + r.width / 2),
      dy: c.top + c.height / 2 - (r.top + r.height / 2),
      w: c.width,
    });
  }, []);

  const close = useCallback(() => setSelected(null), []);

  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [selected, close]);

  return (
    <div ref={rootRef} className="relative -mx-5 py-10 sm:-mx-8">
      {/* Revolving belt (masked + clipped). The vertical `py-4 -my-4` is load
          bearing: `.revolve-viewport` is `overflow: hidden`, and without it the
          viewport is exactly as tall as a card — so a card's hover `scale-[1.02]`
          (and its lift shadow) grew straight into the clip and its top and bottom
          borders vanished. The padding gives the growth somewhere to go; the equal
          negative margin cancels it, so the belt's layout is unchanged. */}
      <div className="revolve-viewport revolve-mask group -my-4 px-5 py-4 sm:px-8">
        <ul className="flex w-max animate-revolve group-focus-within:[animation-play-state:paused]">
          {doubled.map((tool, i) => {
            const clone = i >= tools.length;
            const held = selected?.index === i;
            return (
              <li
                key={i}
                aria-hidden={clone || undefined}
                className="mr-6 flex w-[19rem] shrink-0 sm:w-[21rem]"
              >
                <button
                  type="button"
                  tabIndex={clone ? -1 : 0}
                  aria-label={`Open ${typeof tool.title === "string" ? tool.title : "tool"}`}
                  onClick={(e) => open(i, tool, e.currentTarget)}
                  className={cn(
                    "block h-full w-full cursor-pointer rounded-[inherit] text-left transition-transform duration-200",
                    held ? "invisible" : "hover:scale-[1.02]",
                  )}
                >
                  {/* preview only: no inner interactivity — the button opens it */}
                  <ToolCard {...tool} focusable={false} className="pointer-events-none h-full w-full" />
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {/* focus view: pressed card flown to center, belt blurred behind */}
      <AnimatePresence>
        {selected && [
          <motion.div
            key="backdrop"
            className="revolve-backdrop absolute inset-0 z-40 cursor-pointer"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22 }}
            onClick={close}
          />,
          <motion.div
            key="focus"
            className="pointer-events-none absolute inset-0 z-50 flex items-center justify-center"
            initial={{ x: selected.dx, y: selected.dy, scale: selected.w / CENTER_W, opacity: 0.5 }}
            animate={{ x: 0, y: 0, scale: 1, opacity: 1 }}
            exit={{ scale: 0.94, opacity: 0 }}
            transition={{ type: "spring", stiffness: 280, damping: 28 }}
          >
            <div
              className="pointer-events-auto relative"
              style={{ width: CENTER_W, maxWidth: "88vw" }}
            >
              <ToolCard {...selected.tool} className="w-full shadow-2xl" />
              <button
                type="button"
                onClick={close}
                aria-label="Close"
                className="hand-border absolute -right-3 -top-3 grid h-9 w-9 place-items-center rounded-full bg-paper text-ink shadow-md transition-colors hover:bg-paper-2"
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2.4}
                  strokeLinecap="round"
                >
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </div>
          </motion.div>,
        ]}
      </AnimatePresence>
    </div>
  );
}
