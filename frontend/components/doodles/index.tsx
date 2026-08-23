import * as React from "react";

type DoodleProps = React.SVGProps<SVGSVGElement>;

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2.2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

/** A loose hand-drawn arrow, pointing right. Rotate via className/style. */
export function ArrowScribble(props: DoodleProps) {
  return (
    <svg viewBox="0 0 64 40" width={64} height={40} {...props}>
      <path {...base} d="M4 22c14-2 30-5 52-6" />
      <path {...base} d="M46 6c4 4 8 7 10 10-4 2-8 5-11 9" />
    </svg>
  );
}

/** Four-point sparkle / twinkle. */
export function Sparkle(props: DoodleProps) {
  return (
    <svg viewBox="0 0 32 32" width={32} height={32} {...props}>
      <path
        {...base}
        d="M16 3c1.5 7 4 9.5 11 11-7 1.5-9.5 4-11 11-1.5-7-4-9.5-11-11 7-1.5 9.5-4 11-11Z"
      />
    </svg>
  );
}

/** Wavy underline stroke. Stretch by setting width. */
export function SquiggleUnderline(props: DoodleProps) {
  return (
    <svg viewBox="0 0 120 12" width={120} height={12} preserveAspectRatio="none" {...props}>
      <path {...base} d="M2 7c10-6 20 5 30 0s20-6 30 0 20 5 28 0" />
    </svg>
  );
}

/** Sketchy rising chart with an up-arrow. */
export function RisingChart(props: DoodleProps) {
  return (
    <svg viewBox="0 0 88 64" width={88} height={64} {...props}>
      <path {...base} d="M6 58c8-4 12-16 20-14s10 12 18 4 14-30 24-38" />
      <path {...base} d="M58 10c4-1 8-1 12 0-1 4-1 8 0 12" />
    </svg>
  );
}

/** Lightning bolt (energy / streak). */
export function Lightning(props: DoodleProps) {
  return (
    <svg viewBox="0 0 40 56" width={40} height={56} {...props}>
      <path {...base} d="M24 3 8 32h12l-6 21 22-32H22l6-18Z" />
    </svg>
  );
}

/** Emphasis burst — short rays radiating out, used around CTAs. */
export function StarBurst(props: DoodleProps) {
  return (
    <svg viewBox="0 0 40 40" width={40} height={40} {...props}>
      <path {...base} d="M20 4v9M20 27v9M4 20h9M27 20h9M8 8l6 6M26 26l6 6M32 8l-6 6M14 26l-6 6" />
    </svg>
  );
}

/** Circled scribble underline for a single word. */
export function CircleScribble(props: DoodleProps) {
  return (
    <svg viewBox="0 0 140 60" width={140} height={60} preserveAspectRatio="none" {...props}>
      <path
        {...base}
        d="M70 6C34 4 8 16 8 31s28 24 63 23 61-11 60-24S104 8 74 6"
      />
    </svg>
  );
}

/* ------------------------------------------------------------------ *
 * DECA-flavored set — a curated, single-stroke vocabulary (ideas, deals,
 * competition, judged roleplays) to replace the generic scatter.
 * ------------------------------------------------------------------ */

/** Lightbulb — the idea / strategy mark. */
export function Lightbulb(props: DoodleProps) {
  return (
    <svg viewBox="0 0 40 52" width={40} height={52} {...props}>
      <path {...base} d="M20 4c-8 0-14 6-14 13 0 5 3 8 5 11 1.5 2 2 4 2 6h14c0-2 .5-4 2-6 2-3 5-6 5-11 0-7-6-13-14-13Z" />
      <path {...base} d="M14 40h12M16 46h8" />
    </svg>
  );
}

/** Handshake — the deal / partnership mark. */
export function Handshake(props: DoodleProps) {
  return (
    <svg viewBox="0 0 64 40" width={64} height={40} {...props}>
      <path {...base} d="M4 12h10l8 7c2 2 5 2 7 0l3-3" />
      <path {...base} d="M60 12H48l-9 8" />
      <path {...base} d="M22 19l7 6c2 2 5 2 7 0m-4 5c2 2 4 2 6 0" />
      <path {...base} d="M14 12v14M50 12v14" />
    </svg>
  );
}

/** Price tag — the marketing / pricing mark. */
export function PriceTag(props: DoodleProps) {
  return (
    <svg viewBox="0 0 48 48" width={48} height={48} {...props}>
      <path {...base} d="M6 24 24 6h16c1 0 2 1 2 2v16L24 42Z" />
      <circle {...base} cx={33} cy={15} r={3} />
    </svg>
  );
}

/** Podium / medal — the competition mark. */
export function Podium(props: DoodleProps) {
  return (
    <svg viewBox="0 0 56 44" width={56} height={44} {...props}>
      <path {...base} d="M22 40h12V16H22zM4 40h18V26H4zM34 40h18V22H34z" />
      <path {...base} d="M28 6v6M25 9h6" />
    </svg>
  );
}

/** Little hand-drawn crown — a top-place / royalty mark. Tilt via className. The
 *  three peaks carry jewel dots (filled, so they read against the outline). */
export function Crown(props: DoodleProps) {
  return (
    <svg viewBox="0 0 48 40" width={48} height={40} {...props}>
      <path {...base} d="M6 30 10 13 18 23 24 8 30 23 38 13 42 30Z" />
      <path {...base} d="M8 31c11 3 21 3 32 0" />
      {/* Jewels are always gold, so a black-outlined crown reads as black & gold. */}
      <circle cx={10} cy={12} r={1.7} fill="var(--highlight)" stroke="none" />
      <circle cx={24} cy={7} r={2} fill="var(--highlight)" stroke="none" />
      <circle cx={38} cy={12} r={1.7} fill="var(--highlight)" stroke="none" />
    </svg>
  );
}

/** Graduation cap / mortarboard — the scholar / contributor mark. A flat diamond
 *  board over a peeking cap band, with a button + tassel hanging off the side. */
export function GradCap(props: DoodleProps) {
  return (
    <svg viewBox="0 0 48 40" width={48} height={40} {...props}>
      <path {...base} d="M24 9 4 17 24 25 44 17 24 9Z" />
      <path {...base} d="M14 20v6c0 2 5 4 10 4s10-2 10-4v-6" />
      <path {...base} d="M24 17 40 20v9" />
      <circle cx={24} cy={17} r={1.5} fill="currentColor" stroke="none" />
      <circle cx={40} cy={31} r={1.9} fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Clipboard with a check — the judge / graded-roleplay mark. */
export function Clipboard(props: DoodleProps) {
  return (
    <svg viewBox="0 0 40 52" width={40} height={52} {...props}>
      <path {...base} d="M8 8h6c0-3 2-4 6-4s6 1 6 4h6c2 0 3 1 3 3v34c0 2-1 3-3 3H8c-2 0-3-1-3-3V11c0-2 1-3 3-3Z" />
      <path {...base} d="M14 26l4 4 8-9M14 38h12" />
    </svg>
  );
}

/** Cog / gear — the settings mark. A toothed outer rim + a center hub hole, so it
 *  reads as a gear (not a sun): the eight teeth sit ON the rim, not as rays. */
export function Gear(props: DoodleProps) {
  return (
    <svg viewBox="0 0 40 40" width={40} height={40} {...props}>
      {/* gear body rim + center hub */}
      <circle {...base} cx={20} cy={20} r={11} />
      <circle {...base} cx={20} cy={20} r={4.5} />
      {/* eight teeth poking out from the rim */}
      <path
        {...base}
        d="M31 20h3M20 31v3M9 20H6M20 9V6M27.8 27.8l2.1 2.1M12.2 27.8l-2.1 2.1M12.2 12.2l-2.1-2.1M27.8 12.2l2.1-2.1"
      />
    </svg>
  );
}

/** Six-spoke snowflake — the winter / First Snow mark. Three crossing spokes
 *  plus a small chevron barb at each tip; inherits color via currentColor. */
export function Snowflake(props: DoodleProps) {
  return (
    <svg viewBox="0 0 40 40" width={24} height={24} {...props}>
      {/* three spoke diameters through the center */}
      <path {...base} d="M20 5 20 35M33 12.5 7 27.5M33 27.5 7 12.5" />
      {/* a chevron barb near each of the six tips */}
      <path
        {...base}
        d="M23.4 8.1 20 11 16.6 8.1M32 17 27.8 15.5 28.6 11.1M28.6 28.9 27.8 24.5 32 23M16.6 31.9 20 29 23.4 31.9M8 23 12.2 24.5 11.4 28.9M11.4 11.1 12.2 15.5 8 17"
      />
    </svg>
  );
}

/** Blossom petal — the Spring / First Bloom particle. A filled teardrop with a
 *  soft notch at the tip and a single crease vein; fills via currentColor so the
 *  overlay can tint each petal per-instance. */
export function Petal(props: DoodleProps) {
  return (
    <svg viewBox="0 0 24 24" width={20} height={20} {...props}>
      <path
        fill="currentColor"
        stroke="none"
        d="M12 2c1.6 2.6 5.2 6 5.2 11.4 0 4.6-2.3 8.6-5.2 8.6s-5.2-4-5.2-8.6C6.8 8 10.4 4.6 12 2Z"
      />
      <path
        d="M12 7c-.5 4-.5 8 0 13"
        fill="none"
        stroke="rgba(0,0,0,0.16)"
        strokeWidth={1}
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Dandelion seed — the Summer / Midsummer particle. A pappus (crown of fine
 *  hairs) over a filament and a filled seed; the hairs lead as it drifts UP on
 *  the breeze. Strokes inherit currentColor so the overlay tints each per-seed. */
export function DandelionSeed(props: DoodleProps) {
  return (
    <svg viewBox="0 0 24 24" width={18} height={18} {...props}>
      {/* pappus — fine hairs fanning from the crown */}
      <path
        d="M12 9V1.5M12 9 8.6 1.6M12 9 15.4 1.6M12 9 5.4 3.4M12 9 18.6 3.4M12 9 3 6M12 9 21 6"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.3}
        strokeLinecap="round"
      />
      {/* filament */}
      <path
        d="M12 9V18"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
      />
      {/* seed */}
      <ellipse cx={12} cy={20} rx={1.5} ry={2.5} fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Sticky note with a folded corner — the annotation mark. */
export function StickyNote(props: DoodleProps) {
  return (
    <svg viewBox="0 0 44 44" width={44} height={44} {...props}>
      <path {...base} d="M6 6h32v24L26 40H6z" />
      <path {...base} d="M26 40V30h12M14 16h16M14 23h10" />
    </svg>
  );
}
