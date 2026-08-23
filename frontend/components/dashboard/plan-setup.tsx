"use client";

// The plan setup card (plan 09 §3, first-run step ①). Pick target cluster +
// level + (optional) competition date. Used both for first-run onboarding and for
// "Edit plan" from the header. Emits a partial config; the dashboard stamps
// createdTs / diagnosticDone and persists via setPlanConfig (synced, D3).
//
// PURITY: `now` is passed in (client-stamped) — the date <input> min/value derive
// from `new Date(now)` / `new Date(ms)` WITH an argument, which is deterministic
// and lint-safe (only argless new Date()/Date.now() are banned in render).

import * as React from "react";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { Segmented } from "@/components/ui/segmented";
import { Button } from "@/components/ui/button";
import { MarkerText } from "@/components/marker-text";
import { CLUSTERS } from "@/lib/data/clusters";
import { LEVELS, type Level } from "@/lib/deca";
import type { PlanConfig } from "@/lib/progress/plan-config";

/** Local-midnight ms of a yyyy-mm-dd input value (or null when cleared). */
function dateStrToMs(value: string): number | null {
  if (!value) return null;
  const ms = new Date(`${value}T00:00:00`).getTime();
  return Number.isFinite(ms) ? ms : null;
}

/** yyyy-mm-dd for a date <input> from epoch ms (local), or "" when null. */
function msToDateStr(ms: number | null): string {
  if (ms == null) return "";
  const d = new Date(ms);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export interface PlanDraft {
  cluster: string;
  level: Level;
  eventDate: number | null;
}

export function PlanSetup({
  now,
  initial,
  onSubmit,
  onCancel,
}: {
  now: number;
  initial?: PlanConfig | null;
  onSubmit: (draft: PlanDraft) => void;
  onCancel?: () => void;
}) {
  const [cluster, setCluster] = React.useState(
    initial?.cluster ?? CLUSTERS[0].value,
  );
  const [level, setLevel] = React.useState<Level>(initial?.level ?? "District");
  const [dateStr, setDateStr] = React.useState(msToDateStr(initial?.eventDate ?? null));

  const minDate = msToDateStr(now);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ cluster, level, eventDate: dateStrToMs(dateStr) });
  };

  return (
    <Card variant={0} className="mx-auto max-w-xl p-6 sm:p-8">
      <MarkerText rotate={-3} className="text-base">
        {initial ? "edit your plan" : "set your target"}
      </MarkerText>
      <h2 className="mt-1 font-display text-2xl font-extrabold tracking-tight">
        {initial ? "Update your study plan" : "Let's build your study plan"}
      </h2>
      <p className="mt-2 text-sm text-ink/70">
        Pick the exam you&apos;re training for and (optionally) when you compete —
        the plan paces your daily work toward it.
      </p>

      <form onSubmit={submit} className="mt-6 grid gap-6">
        <Field label="cluster">
          <Select
            value={cluster}
            onChange={setCluster}
            aria-label="cluster"
            options={CLUSTERS.map((c) => ({ value: c.value, label: c.label }))}
          />
        </Field>

        <Field label="level">
          <Segmented
            value={level}
            onChange={(v) => setLevel(v as Level)}
            options={LEVELS.map((l) => ({ value: l.value, label: l.label, sub: l.note }))}
          />
        </Field>

        <Field label="competition date" hint="optional">
          <input
            type="date"
            value={dateStr}
            min={minDate}
            onChange={(e) => setDateStr(e.target.value)}
            aria-label="competition date"
            className="hand-border-2 w-full bg-paper px-4 py-2.5 text-[0.95rem] text-ink outline-none transition-colors focus-visible:ring-2 focus-visible:ring-support/50"
          />
        </Field>

        <div className="flex flex-wrap gap-3 pt-1">
          <Button type="submit" variant="primary">
            {initial ? "Save plan" : "Continue"}
          </Button>
          {onCancel && (
            <Button type="button" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          )}
        </div>
      </form>
    </Card>
  );
}
