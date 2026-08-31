"use client";

// Readiness trajectory (plan 08 phase 2 §7.1, D6). Inline SVG area+line of
// readiness over time — a single accent series (so no legend box; the title names
// it), soft filled band to the baseline, dots at each finished session, recessive
// grid/axes in theme tokens. Hover shows a crosshair + tooltip (dataviz: an SVG
// chart ships its hover layer by default). Points are already per-session /
// day-bucketed by the engine. Theme-token only ⇒ legible in light and dark.
//
// The viewBox WIDTH tracks the measured render width (a ResizeObserver) and the
// height is fixed to match the rendered box, so the SVG scales 1:1 — no
// horizontal stretching of the axis numbers or dots (which `preserveAspectRatio:
// none` on a fixed-width viewBox would otherwise cause on a full-width graph).

import * as React from "react";
import { MarkerText } from "@/components/marker-text";
import type { TrajectoryPoint } from "@/lib/progress/mastery";

const W0 = 600; // SSR / first-paint default width (px); replaced by the measured width
const H = 288; // matches the h-72 render height → 1:1 vertical scale
const PAD = { l: 34, r: 10, t: 16, b: 28 };

const fmtDay = (ts: number) => {
  try {
    return new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
};

export function ReadinessTrajectory({
  points,
  cluster,
  clusterName,
}: {
  points: TrajectoryPoint[];
  cluster: string | "all";
  clusterName: string | null;
}) {
  const [hover, setHover] = React.useState<number | null>(null);
  const [w, setW] = React.useState(W0);
  const wrapRef = React.useRef<HTMLDivElement>(null);

  // Track the rendered width so the viewBox maps 1:1 (no distortion).
  React.useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const cw = entries[0]?.contentRect.width;
      if (cw) setW(cw);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const title = clusterName ? `${clusterName} readiness` : "Overall readiness";

  const tsMin = points.length ? points[0].ts : 0;
  const tsMax = points.length ? points[points.length - 1].ts : 0;
  const span = tsMax - tsMin;

  const xOf = React.useCallback(
    (ts: number) =>
      points.length <= 1 || span === 0
        ? PAD.l + (w - PAD.l - PAD.r) / 2
        : PAD.l + ((ts - tsMin) / span) * (w - PAD.l - PAD.r),
    [points.length, span, tsMin, w],
  );
  const yOf = (r: number) => PAD.t + (1 - r) * (H - PAD.t - PAD.b);

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (points.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * w;
    let best = 0;
    let bestD = Infinity;
    for (let i = 0; i < points.length; i++) {
      const d = Math.abs(xOf(points[i].ts) - px);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    }
    setHover(best);
  };

  if (points.length === 0) {
    return (
      <Frame title={title}>
        <div className="flex h-72 flex-col items-center justify-center gap-2 text-center">
          <MarkerText rotate={-2} className="text-sm">
            no trajectory yet
          </MarkerText>
          <p className="max-w-xs text-sm text-muted">
            Finish a couple of sessions
            {cluster === "all" ? "" : " in this cluster"} and your readiness line
            appears here.
          </p>
        </div>
      </Frame>
    );
  }

  const baselineY = yOf(0);
  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xOf(p.ts).toFixed(1)} ${yOf(p.readiness).toFixed(1)}`)
    .join(" ");
  const areaPath =
    `M ${xOf(points[0].ts).toFixed(1)} ${baselineY.toFixed(1)} ` +
    points.map((p) => `L ${xOf(p.ts).toFixed(1)} ${yOf(p.readiness).toFixed(1)}`).join(" ") +
    ` L ${xOf(points[points.length - 1].ts).toFixed(1)} ${baselineY.toFixed(1)} Z`;

  const active = hover != null ? points[hover] : null;

  return (
    <Frame title={title}>
      <div className="relative" ref={wrapRef}>
        <svg
          viewBox={`0 0 ${w} ${H}`}
          preserveAspectRatio="none"
          className="h-72 w-full"
          role="img"
          aria-label={`${title} over time, ${points.length} point${points.length === 1 ? "" : "s"}`}
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        >
          {/* Gridlines + y labels (recessive) */}
          {[0, 0.25, 0.5, 0.75, 1].map((r) => (
            <g key={r}>
              <line
                x1={PAD.l}
                x2={w - PAD.r}
                y1={yOf(r)}
                y2={yOf(r)}
                stroke="var(--line)"
                strokeWidth={1}
                vectorEffect="non-scaling-stroke"
              />
              <text
                x={PAD.l - 6}
                y={yOf(r) + 3}
                textAnchor="end"
                fontSize={10}
                fill="var(--muted)"
              >
                {Math.round(r * 100)}
              </text>
            </g>
          ))}

          {/* Area band + line */}
          <path d={areaPath} fill="var(--accent)" opacity={0.14} />
          <path
            d={linePath}
            fill="none"
            stroke="var(--accent)"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />

          {/* Crosshair */}
          {active && (
            <line
              x1={xOf(active.ts)}
              x2={xOf(active.ts)}
              y1={PAD.t}
              y2={baselineY}
              stroke="var(--accent)"
              strokeWidth={1}
              strokeDasharray="3 3"
              vectorEffect="non-scaling-stroke"
            />
          )}

          {/* Dots */}
          {points.map((p, i) => (
            <circle
              key={p.ts}
              cx={xOf(p.ts)}
              cy={yOf(p.readiness)}
              r={hover === i ? 5 : 3}
              fill="var(--accent)"
              stroke="var(--paper)"
              strokeWidth={1.5}
            />
          ))}

          {/* x-axis end labels */}
          <text x={PAD.l} y={H - 8} textAnchor="start" fontSize={10} fill="var(--muted)">
            {fmtDay(tsMin)}
          </text>
          {span > 0 && (
            <text x={w - PAD.r} y={H - 8} textAnchor="end" fontSize={10} fill="var(--muted)">
              {fmtDay(tsMax)}
            </text>
          )}
        </svg>

        {/* Tooltip */}
        {active && (
          <div
            className="pointer-events-none absolute -top-1 z-10 -translate-x-1/2 rounded-lg border-2 border-ink bg-paper px-2.5 py-1.5 text-center shadow-md"
            style={{ left: `${(xOf(active.ts) / w) * 100}%` }}
          >
            <p className="stat text-sm font-bold text-accent-ink">
              {Math.round(active.readiness * 100)}%
            </p>
            <p className="text-[0.65rem] text-muted">{fmtDay(active.ts)}</p>
          </div>
        )}
      </div>
      {points.length === 1 && (
        <p className="mt-1 text-center text-xs text-muted">
          One session so far — keep practicing to see the trend.
        </p>
      )}
    </Frame>
  );
}

function Frame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border-2 border-line bg-paper p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="font-display text-xl font-bold tracking-tight">{title}</h2>
        <MarkerText rotate={2} className="text-xs">
          over time
        </MarkerText>
      </div>
      {children}
    </section>
  );
}
