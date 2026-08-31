// The Developers page (plan 09 §2b, D9) — a team / contributor "about" page.
// Live and unlocked (the old "in development" DevLock overlay was removed). Static
// (no data, no client state) so it prerenders. Shown in the guest nav.

import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Loop } from "@/components/loop";
import { MarkerText } from "@/components/marker-text";
import { TapeLabel } from "@/components/tape-label";
import { Sparkle } from "@/components/doodles";

export const metadata: Metadata = {
  title: "Developers",
  description: "The people behind DECK — a practice tool built by DECA alumni.",
};

interface Person {
  name: string;
  /** Tape label above the name — "Co-Founder", "Alpha Tester", … */
  tag: string;
  /** Secondary role pinned to the row's top-right corner (optional). */
  role?: string;
  bio: string;
  /** VP title (e.g. "Roleplay") → shows the animated "VP of … · GNS DECA" badge. */
  vp?: string;
  /** Omitted when the person hasn't shared a contact email. */
  email?: string;
  /** Optional personal site / portfolio link. */
  link?: { label: string; href: string };
  /** Photo path under /public; falls back to initials when absent. */
  photo?: string;
  /** CSS object-position for the photo crop (default is centered). */
  photoPos?: string;
  initials: string;
  /** DECA accolades, grouped by event. */
  accolades: { event: string; items: string[] }[];
}

const TEAM: Person[] = [
  {
    name: "Kelton Yu",
    tag: "Co-Founder",
    role: "Chief Developer",
    bio: "Senior at Great Neck South High School, Class of 2027. Passionate full-stack developer building a DECA practice tool for students.",
    email: "keltonyu2@gmail.com",
    photo: "/team/kelton-yu.jpg",
    initials: "KY",
    accolades: [
      {
        event: "BLTDM · 2025",
        items: [
          "ICDC Qualifier",
          "State Qualifier",
          "Top 6 in NYS",
          "Top 10 Overall in NYS",
          "Top 10 Test in NYS",
          "Top 10 Roleplay in NYS",
          "Top 1 Regionals",
        ],
      },
      {
        event: "HRM · 2026",
        items: ["State Qualifier", "Top 10 Test in NYS", "Top 2 Regionals"],
      },
    ],
  },
  {
    name: "Jinyuan Chen",
    tag: "Co-Founder",
    bio: "Senior at Great Neck South High School, Class of 2027.",
    vp: "Roleplay",
    email: "jinyuanchen2009@gmail.com",
    photo: "/team/jinyuan-chen.png",
    initials: "JC",
    accolades: [
      {
        event: "BLTDM · 2025",
        items: ["ICDC Qualifier", "Top 6 in NYS", "Top 10 Overall in NYS", "Top 10 Roleplay in NYS", "Top 1 Regionals"],
      },
    ],
  },
  {
    name: "Emily Zhang",
    tag: "Alpha Tester",
    bio: "Junior at Great Neck South High School, Class of 2028.",
    vp: "Prepared Events",
    photo: "/team/emily-zhang.jpg",
    photoPos: "55% 30%",
    initials: "EZ",
    accolades: [
      {
        event: "BOR · 2026",
        items: ["ICDC Qualifier", "Top 2 States"],
      },
      {
        event: "BLTDM · 2025",
        items: [
          "State Qualifier",
          "Top 10 Overall in NYS",
          "Top 10 Roleplay in NYS",
          "Top 2 Regionals",
        ],
      },
    ],
  },
  {
    name: "Ethan Lam",
    tag: "Alpha Tester",
    bio: "Senior at Great Neck South High School, Class of 2027.",
    vp: "Online Competitions",
    photo: "/team/ethan-lam.png",
    initials: "EL",
    accolades: [],
  },
  {
    name: "Tarandeep Dhir",
    tag: "Alpha Tester",
    bio: "Freshman at CCNY, Class of 2030.",
    link: {
      label: "Creative showcase",
      href: "https://dhirtarandeep.wixsite.com/creative-showcase",
    },
    initials: "TD",
    accolades: [],
  },
];

function Accolade({ children }: { children: React.ReactNode }) {
  return (
    <span className="marker rounded bg-highlight/30 px-2 py-1 text-xs leading-none text-highlight-ink ring-1 ring-ink/10">
      {children}
    </span>
  );
}

/** The premium "Chief Developer" badge — a black pill with gold text, a gold
 *  glow, and a bright sheen sweep (CSS in globals.css; sweep stops under
 *  prefers-reduced-motion). Flashier than the VP badge. */
function ChiefBadge({ label }: { label: string }) {
  return (
    <span className="chief-badge mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold">
      <Sparkle className="h-3.5 w-3.5" />
      {label}
    </span>
  );
}

/** The animated "VP of …" badge — a gold tag with a shine sweep (CSS in
 *  globals.css; the sweep stops under prefers-reduced-motion). */
function VpBadge({ title }: { title: string }) {
  return (
    <span className="roleplay-badge mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold">
      <Sparkle className="h-3.5 w-3.5" />
      VP of {title} · GNS DECA
    </span>
  );
}

function Avatar({ person }: { person: Person }) {
  return (
    <div className="h-32 w-32 shrink-0">
      <div className="flex h-full w-full items-center justify-center overflow-hidden rounded-full border-2 border-ink/15 bg-paper-2">
        {person.photo ? (
          // Source cropped to the round frame.
          <Image
            src={person.photo}
            alt={person.name}
            width={256}
            height={256}
            className="h-full w-full object-cover"
            style={person.photoPos ? { objectPosition: person.photoPos } : undefined}
            priority
          />
        ) : (
          <span className="font-display text-3xl font-extrabold tracking-tight text-ink/45">
            {person.initials}
          </span>
        )}
      </div>
    </div>
  );
}

/** One person as a bordered card, nested inside a section box. */
function PersonCard({ person }: { person: Person }) {
  return (
    <Card className="p-6 sm:p-7">
      <div className="flex flex-col gap-6 sm:flex-row">
        <Avatar person={person} />

        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <TapeLabel color="support" rotate={-2}>
              {person.tag}
            </TapeLabel>
          </div>
          <h2 className="mt-3 font-display text-2xl font-bold tracking-tight">
            {person.name}
          </h2>
          <p className="mt-1 text-sm text-ink/70">{person.bio}</p>
          {person.role && (
            <div>
              <ChiefBadge label={person.role} />
            </div>
          )}
          {person.vp && (
            <div>
              <VpBadge title={person.vp} />
            </div>
          )}
          {person.email && (
            <p className="mt-3 text-sm text-muted">
              Reach out at{" "}
              <a
                href={`mailto:${person.email}`}
                className="font-medium text-ink underline decoration-dotted underline-offset-2 hover:text-accent-ink"
              >
                {person.email}
              </a>
            </p>
          )}
          {person.link && (
            <p className="mt-3 text-sm text-muted">
              See their{" "}
              <a
                href={person.link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-ink underline decoration-dotted underline-offset-2 hover:text-accent-ink"
              >
                {person.link.label}
              </a>
            </p>
          )}

          {/* DECA accolades, grouped by event. */}
          <div className="mt-5 space-y-3">
            {person.accolades.map((group) => (
              <div key={group.event}>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink/60">
                  {group.event}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {group.items.map((item) => (
                    <Accolade key={item}>{item}</Accolade>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}

export default function DevelopersPage() {
  return (
    <div className="mx-auto max-w-3xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← Back home
      </Link>

      <div className="mt-4">
        <MarkerText rotate={-3} className="text-base">
          the people behind deck
        </MarkerText>
        <h1 className="mt-1 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
          Meet the <Loop color="accent">team</Loop>
        </h1>
        <p className="mt-4 max-w-xl text-ink/70">
          DECK is built by a small crew of DECA alumni and volunteers — students
          who wanted exam-authentic practice that actually tracks how you&rsquo;re
          doing. It&rsquo;s an active, student-run project, not affiliated with DECA
          Inc.
        </p>

        <div className="mt-8 space-y-5">
          {TEAM.map((person) => (
            <PersonCard key={person.name} person={person} />
          ))}
        </div>
      </div>
    </div>
  );
}
