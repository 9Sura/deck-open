"use client";

// The sign-in welcome animation. On a fresh sign-in / sign-up the whole viewport
// becomes a blank "Welcome, <username>" page (same display font, centered); the
// greeting fades, a deck of DECK-branded cards forms at center and spins for a
// beat, deals out to COVER the screen, then the cards scatter off one at a time
// to REVEAL the live site behind them — the deck sweeping away to unveil the app.
//
// Choreography is stage-driven (welcome → deck → cover → reveal) via motion
// variants: deck/spin is synchronized; cover + reveal are staggered per piece so
// cards deal and clear one at a time.
//
// Triggered by auth-provider.welcome (only on an explicit sign-in/up). Fully
// honors reduced motion: greeting fade only, no cards.

import * as React from "react";
import { AnimatePresence, motion, type Variants } from "motion/react";
import { useAuth } from "@/components/auth/auth-provider";
import { usePrefersReducedMotion } from "@/hooks/use-prefers-reduced-motion";
import {
  Sparkle,
  StarBurst,
  Lightbulb,
  RisingChart,
  SquiggleUnderline,
  Lightning,
} from "@/components/doodles";

// 6×2 grid → tall, portrait cards that still tile the whole viewport.
const COLS = 6;
const ROWS = 2;
const PIECE_COUNT = COLS * ROWS;
const CELL_W = 100 / COLS; // vw
const CELL_H = 100 / ROWS; // vh
const COVER_STAGGER = 0.06; // s between each card dealing into place
const REVEAL_STAGGER = 0.05; // s between each card flying off

type Stage = "welcome" | "deck" | "cover" | "reveal";

// Per-piece geometry — pure functions of the index so variant functions can
// derive everything from `custom={i}`.
const colOf = (i: number) => i % COLS;
const rowOf = (i: number) => Math.floor(i / COLS);
const startX = (i: number) => 50 - (colOf(i) + 0.5) * CELL_W; // vw: slot → centre
const startY = (i: number) => 50 - (rowOf(i) + 0.5) * CELL_H; // vh
const tiltOf = (i: number) => ((i * 53) % 13) - 6; // -6..6°, deterministic
// Reveal: fling each card outward, away from centre (edge cards travel furthest).
const flingX = (i: number) => ((colOf(i) + 0.5) * CELL_W - 50) * 2.8; // vw
const flingY = (i: number) => ((rowOf(i) + 0.5) * CELL_H - 50) * 2.8; // vh

const pieceVariants: Variants = {
  hidden: (i: number) => ({
    x: `${startX(i)}vw`,
    y: `${startY(i)}vh`,
    rotate: tiltOf(i),
    scale: 0.32,
    opacity: 0,
    boxShadow: "0 0vh 0vh rgba(0,0,0,0)",
  }),
  // Form the stack at centre and whip the deck TWO snappy turns in place, with a
  // lift shadow that grows so the deck feels like it rises as it spins.
  deck: (i: number) => ({
    x: `${startX(i)}vw`,
    y: `${startY(i)}vh`,
    rotate: tiltOf(i) + 720,
    scale: 0.5,
    opacity: 1,
    boxShadow: "0 1.6vh 3.6vh rgba(0,0,0,0.32)",
    transition: {
      opacity: { duration: 0.25 },
      scale: { duration: 0.35 },
      boxShadow: { duration: 0.9 },
      // Snappy whip with a slight overshoot settle (easeOutBack-ish).
      rotate: { duration: 0.9, ease: [0.3, 1.5, 0.5, 1] },
    },
  }),
  // Deal out to assemble the logo page — staggered so pieces land one at a time.
  // rotate MUST be 0 here so the slices line up flush into one continuous logo;
  // shadow drops to flat so the assembled page reads clean (no per-cell shadows).
  cover: (i: number) => ({
    x: "0vw",
    y: "0vh",
    rotate: 0,
    scale: 1,
    opacity: 1,
    boxShadow: "0 0vh 0vh rgba(0,0,0,0)",
    transition: { delay: i * COVER_STAGGER, duration: 0.45, ease: [0.22, 0.7, 0.3, 1] },
  }),
  // Float off — the reveal. Each piece lifts, drifts gently up-and-out with a
  // soft rotation, scales up a touch (rising toward you), and fades. Staggered
  // one at a time, slow soft easing, so the deck buoyantly clears the app.
  reveal: (i: number) => ({
    x: `${flingX(i) * 0.28}vw`,
    y: `${-48 + flingY(i) * 0.15}vh`,
    rotate: tiltOf(i) + (i % 2 === 0 ? 1 : -1) * 12,
    scale: 1.06,
    opacity: 0,
    boxShadow: "0 1.6vh 3.4vh rgba(0,0,0,0.22)",
    transition: { delay: i * REVEAL_STAGGER, duration: 1.25, ease: [0.33, 0, 0.3, 1] },
  }),
};

export function WelcomeOverlay() {
  const { welcome, clearWelcome } = useAuth();
  if (!welcome) return null;
  return <WelcomeSequence key={welcome} name={welcome} onDone={clearWelcome} />;
}

function WelcomeSequence({
  name,
  onDone,
}: {
  name: string;
  onDone: () => void;
}) {
  const reduced = usePrefersReducedMotion();
  const [stage, setStage] = React.useState<Stage>("welcome");

  React.useEffect(() => {
    if (reduced) {
      const done = setTimeout(onDone, 1900);
      return () => clearTimeout(done);
    }
    const t = [
      // Deck follows once the third dot has faded in (~1.85s).
      setTimeout(() => setStage("deck"), 1900),
      setTimeout(() => setStage("cover"), 2900),
      setTimeout(() => setStage("reveal"), 4800),
      setTimeout(onDone, 6700),
    ];
    return () => t.forEach(clearTimeout);
  }, [reduced, onDone]);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center overflow-hidden"
      aria-live="polite"
    >
      {/* Solid paper backdrop — hides the site behind the deck; fades out during
          the reveal so the scattering cards uncover the live app. */}
      <motion.div
        className="absolute inset-0 bg-paper"
        initial={{ opacity: 1 }}
        animate={{ opacity: stage === "reveal" ? 0 : 1 }}
        transition={{ duration: 0.9, delay: stage === "reveal" ? 0.15 : 0 }}
      />

      {/* Greeting — same display font, centered. */}
      <AnimatePresence>
        {stage === "welcome" && (
          <motion.h1
            key="greeting"
            className="relative px-6 text-center font-display text-5xl font-extrabold tracking-tight text-ink sm:text-6xl"
            initial={{ opacity: 0, y: 14, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 1.05 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          >
            Welcome, <span className="text-accent">{name}</span>
            {/* three dots that fade in one at a time; deck follows once all show */}
            <span aria-hidden className="text-accent">
              {[0, 1, 2].map((d) => (
                <motion.span
                  key={d}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.75 + d * 0.4, duration: 0.3 }}
                >
                  .
                </motion.span>
              ))}
            </span>
          </motion.h1>
        )}
      </AnimatePresence>

      {/* The deck: forms + spins, covers the screen, then scatters to reveal. */}
      {stage !== "welcome" && !reduced && (
        <motion.div
          className="pointer-events-none absolute inset-0"
          initial="hidden"
          animate={stage}
        >
          {Array.from({ length: PIECE_COUNT }).map((_, i) => {
            const col = colOf(i);
            const row = rowOf(i);
            return (
              <motion.div
                key={i}
                custom={i}
                variants={pieceVariants}
                className="absolute overflow-hidden"
                style={{
                  left: `${col * CELL_W}vw`,
                  top: `${row * CELL_H}vh`,
                  width: `${CELL_W}vw`,
                  height: `${CELL_H}vh`,
                }}
              >
                {/* This piece's slice of the shared full-screen logo page — the
                    mock fills the viewport but is shifted by the cell origin so
                    every piece's slice aligns into one continuous page. */}
                <div
                  className="absolute"
                  style={{
                    left: `${-col * CELL_W}vw`,
                    top: `${-row * CELL_H}vh`,
                    width: "100vw",
                    height: "100vh",
                  }}
                >
                  <LogoPage />
                </div>
                {/* playing-card rank + suit in the corners of the piece */}
                <CornerIndex i={i} />
                {/* border overlaid ON TOP of the slice so it's always visible —
                    adjacent pieces meet into a clear grid over the logo. */}
                <div className="pointer-events-none absolute inset-0 border-2 border-ink/70" />
              </motion.div>
            );
          })}
        </motion.div>
      )}
    </div>
  );
}

// Playing-card faces, one per piece (deterministic from the index).
const RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"];
const SUITS = ["♠", "♥", "♦", "♣"];
const RED_SUITS = new Set(["♥", "♦"]);

/** The rank + suit indices in opposite corners of a piece, like a real card. */
function CornerIndex({ i }: { i: number }) {
  const rank = RANKS[i % RANKS.length];
  const suit = SUITS[i % SUITS.length];
  const color = RED_SUITS.has(suit) ? "#c0392b" : "var(--ink)";
  return (
    <>
      <div
        className="pointer-events-none absolute left-[7%] top-[5%] flex flex-col items-center leading-none"
        style={{ color }}
      >
        <span className="font-display text-[1.7vw] font-bold">{rank}</span>
        <span className="text-[1.5vw]">{suit}</span>
      </div>
      <div
        className="pointer-events-none absolute bottom-[5%] right-[7%] flex rotate-180 flex-col items-center leading-none"
        style={{ color }}
      >
        <span className="font-display text-[1.7vw] font-bold">{rank}</span>
        <span className="text-[1.5vw]">{suit}</span>
      </div>
    </>
  );
}

/** The shared full-viewport "page" the puzzle assembles into: the DECK logo,
 *  centered, on paper — the same wordmark badge as the nav, scaled up. Rendered
 *  once per piece and clipped to that piece's cell so the slices reconstruct it.
 *  Theme tokens throughout, so it re-tints with the active theme. */
function LogoPage() {
  return (
    <div className="relative flex h-screen w-screen items-center justify-center bg-paper">
      {/* doodles scattered around the logo (theme-tinted) */}
      <Sparkle className="absolute left-[15vw] top-[19vh] h-[5vw] w-[5vw] -rotate-12 text-support" />
      <StarBurst className="absolute right-[17vw] top-[15vh] h-[6.5vw] w-[6.5vw] rotate-6 text-accent" />
      <Lightbulb className="absolute left-[19vw] bottom-[17vh] h-[6.5vw] w-[6.5vw] -rotate-6 text-support" />
      <RisingChart className="absolute right-[15vw] bottom-[19vh] h-[7vw] w-[9vw] text-accent" />
      <Lightning className="absolute left-[30vw] top-[30vh] h-[4.5vw] w-[4.5vw] -rotate-6 text-support" />
      <Sparkle className="absolute right-[31vw] top-[33vh] h-[3.5vw] w-[3.5vw] rotate-6 text-ink/45" />
      <Sparkle className="absolute left-[33vw] bottom-[30vh] h-[3vw] w-[3vw] text-accent" />
      <SquiggleUnderline className="absolute left-1/2 top-[62vh] h-[3vh] w-[26vw] -translate-x-1/2 text-support" />

      {/* the logo, centered */}
      <span className="sketch-radius relative border-[0.4vw] border-ink bg-accent px-[4vw] py-[2.4vh] font-display text-[11vw] font-extrabold leading-none tracking-tight text-[var(--on-accent)]">
        DECK
      </span>
    </div>
  );
}
