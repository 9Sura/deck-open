"use client";

import * as React from "react";
import { Dialog } from "@/components/ui/dialog";
import { Card } from "@/components/ui/card";
import { TapeLabel } from "@/components/tape-label";
import { ThemePicker } from "@/components/theme-picker";
import { SettingsData } from "@/components/settings-data";
import { cn } from "@/lib/utils";

// Data-driven so future utility tabs (Motion, Display, …) are a one-line add.
const TABS: { id: string; label: string; render: () => React.ReactNode }[] = [
  { id: "themes", label: "Themes", render: () => <ThemePicker /> },
  { id: "data", label: "Data", render: () => <SettingsData /> },
  // { id: "motion", label: "Motion", render: () => <MotionSettings /> },
  // { id: "display", label: "Display", render: () => <DisplaySettings /> },
];

export function SettingsDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [active, setActive] = React.useState(TABS[0].id);
  const activeTab = TABS.find((t) => t.id === active) ?? TABS[0];
  const tabRefs = React.useRef<Record<string, HTMLButtonElement | null>>({});

  // Arrow-key roving focus across the tablist (WAI-ARIA tabs pattern).
  const onTabKeyDown = (e: React.KeyboardEvent) => {
    const i = TABS.findIndex((t) => t.id === active);
    let next = i;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (i + 1) % TABS.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp")
      next = (i - 1 + TABS.length) % TABS.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = TABS.length - 1;
    else return;
    e.preventDefault();
    const id = TABS[next].id;
    setActive(id);
    tabRefs.current[id]?.focus();
  };

  return (
    <Dialog open={open} onClose={onClose} label="Settings">
      <Card variant={0} className="p-5 sm:p-7">
        <div className="mb-5 flex items-center justify-between gap-4">
          <TapeLabel color="support" rotate={-3}>
            settings
          </TapeLabel>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close settings (Esc)"
            className="rounded-lg px-2 py-1 text-lg leading-none text-ink/60 transition-colors hover:bg-ink/5 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper"
          >
            ✕
          </button>
        </div>

        <div className="flex flex-col gap-5 sm:flex-row sm:gap-6">
          <div
            role="tablist"
            aria-label="Settings sections"
            aria-orientation="vertical"
            onKeyDown={onTabKeyDown}
            className="flex gap-2 sm:w-36 sm:shrink-0 sm:flex-col"
          >
            {TABS.map((t) => {
              const selected = t.id === active;
              return (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  id={`settings-tab-${t.id}`}
                  aria-selected={selected}
                  aria-controls={`settings-panel-${t.id}`}
                  tabIndex={selected ? 0 : -1}
                  ref={(el) => {
                    tabRefs.current[t.id] = el;
                  }}
                  onClick={() => setActive(t.id)}
                  className={cn(
                    "marker sketch-radius border-2 px-3 py-1.5 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
                    selected
                      ? "border-ink bg-accent text-[var(--on-accent)]"
                      : "border-line bg-paper text-ink/60 hover:bg-paper-2 hover:text-ink",
                  )}
                >
                  {t.label}
                </button>
              );
            })}
          </div>

          <div
            role="tabpanel"
            id={`settings-panel-${activeTab.id}`}
            aria-labelledby={`settings-tab-${activeTab.id}`}
            tabIndex={0}
            // Locked to a bounded block that scrolls — keeps the settings popup a
            // stable size as the theme list grows, but tall enough to show most
            // of the list at once (capped to the viewport on short screens). p-1
            // gives card hover-lift + focus rings room so the scrollport doesn't
            // clip them.
            className="min-w-0 flex-1 max-h-[min(72vh,36rem)] overflow-y-auto p-1 outline-none"
          >
            {activeTab.render()}
          </div>
        </div>
      </Card>
    </Dialog>
  );
}
