import type { EventFormat, Level } from "@/lib/deca";

/**
 * The Roleplay Challenge data contract (frontend plan 11 §2b).
 *
 * The archive is PERMANENT — a field added after the buffer fills means
 * regenerating every day already on disk. This file and its producer,
 * `backend/roleplay-gen-model/src/generators/parse_roleplay.py`, are one
 * contract in two languages and must be changed together.
 *
 * Everything here is derived from real generated output
 * (`backend/roleplay-gen-model/output/bake-off/icdc/no-example/*.txt`), not
 * designed in the abstract.
 */

/** Bumped only on a breaking shape change; the parser stamps it per file. */
export const ROLEPLAY_SCHEMA_VERSION = 1;

/**
 * What difficulty was ASKED FOR, never what was proven (plan 11 F5).
 *
 * There is no referee (backend D4) and `icdcVerified` was deliberately removed
 * from the schema because nothing backs it. Never render "verified", "guaranteed
 * ICDC", or "competition-accurate difficulty".
 *
 * TWO VALUES, AND THEY MEAN DIFFERENT THINGS — do not collapse them:
 *
 *   "icdc"       the live tier. DECA's own published format, at DECA's own
 *                scale: no data exhibit, 2-3 judge questions, roles rather than
 *                a named cast, and a situation length band derived from the
 *                event's own corpus mean. Difficulty is in the judgment the case
 *                demands. Backend gate version 5.
 *   "icdc-plus"  RETIRED. Every roleplay banked before gate version 5. Its
 *                authoring spec REQUIRED a numeric exhibit, >= 3 named
 *                stakeholders with incompatible interests, >= 3 colliding
 *                constraints, and >= 3 judge questions in evaluator voice --
 *                a shape that appears in 0 of the 396 real DECA roleplays the
 *                backend corpus holds. Kept only so already-banked entries stay
 *                readable; never author a new one.
 *
 * The supportable user-facing claim for BOTH is "harder than the district-level
 * material DECA publishes" -- and for "icdc" the honest gloss is "the shape DECA
 * publishes, turned on a harder question."
 */
export type RoleplayTier = "icdc-plus" | "icdc";

export interface RoleplayExhibit {
  /** Heading with its `EXHIBIT n:` prefix stripped. */
  title: string;
  /**
   * One line per row, close to as-authored: list markers stripped, markdown
   * table rules dropped, nothing parsed into cells. A row may be a markdown
   * table row (`| Position | 25 | 30 |`) or a plain labelled figure
   * (`Current assets: $250,000`) — both occur in real output, so a renderer
   * that wants cells splits on `|` itself and falls back to plain text.
   */
  rows: string[];
}

/**
 * One performance indicator, with the instructional area it was DRAWN from
 * (backend plan 05 D5). `area`/`role` are optional for one reason and it is not
 * laziness: the 7 committed day fixtures predate the schema and carry bare
 * strings, and they are regenerated rather than hand-migrated, because 25.8% of
 * DECA's PIs are filed under more than one area and the mapping cannot be
 * recovered from the string afterwards. An absent `area` therefore means
 * UNRECORDED — never guess one to fill it in.
 */
export interface RoleplayPI {
  /** The indicator, verbatim as the case lists it. */
  pi: string;
  /** The area it was drawn from. Absent on pre-plan-05 entries. */
  area?: string;
  /** "core" = from the declared instructional area; "adjacent" = supporting. */
  role?: "core" | "adjacent";
}

export interface Roleplay {
  schemaVersion: number;
  /** `${date}-${code}` — the stable join key for run state. Never renumbered. */
  id: string;
  /** Publish day, `YYYY-MM-DD`. May be in the FUTURE — see `RoleplayIndex.latest`. */
  date: string;
  /** Joins to `EVENTS` in lib/data/events.ts. */
  code: string;
  format: EventFormat;
  /** Always "ICDC". The `Level` union is NOT widened for this tier (F3/D6). */
  level: Level;
  tier: RoleplayTier;
  /** Absent for PFL, the one event DECA publishes no career cluster for. Never "General". */
  careerCluster?: string;
  /**
   * The instructional area the generator DECLARED for this case, and drew the core
   * indicators from — not a label computed from what it happened to sample
   * (backend plan 05 §4.2). Every `role: "core"` entry below carries it.
   */
  instructionalArea: string;
  /** Verbatim from the PI library — the generator's highest-value fidelity check. */
  performanceIndicators: RoleplayPI[];
  twentyFirstCenturySkills: string[];
  /**
   * Boilerplate, and UNRELIABLE about timing: it says "no time for judge
   * questions" and then three judge questions follow. Take prep/present minutes
   * from `events.ts`, never from this prose (`meta.defects` flags each instance).
   */
  participantInstructions: string;
  /** Prose only, paragraphs separated by a blank line. The exhibit is NOT embedded. */
  situation: string;
  /**
   * Optional, and on the live tier it is ALWAYS ABSENT: F3 bans a data block
   * outright, because 0 of the 396 real DECA roleplays carry one. Present only
   * on `tier: "icdc-plus"` entries, whose retired spec required it. Render the
   * absence plainly rather than faking a block; never add UI that assumes one.
   */
  exhibit?: RoleplayExhibit;
  judgeCharacterization: string;
  /**
   * 2 or 3 on the live tier (F6) — DECA's own range, measured at 2 in 302 of 396
   * corpus roleplays and 3 in 89. Retired `icdc-plus` entries have a floor of 3.
   * They have no heading in the source text — bare numbered lines.
   */
  judgeQuestions: string[];
  /** Never rendered as roleplay text (F10). */
  meta: RoleplayMeta;
}

export interface RoleplayMeta {
  /**
   * The model's own self-report. NOT TRUSTWORTHY ALONE — a model certifying its
   * own work is worthless as a verdict. It is kept because Python can
   * CONTRADICT parts of it (see `corroborated`), and because it is the natural
   * answer key for scenario-specific feedback later.
   */
  claimed: {
    stakeholders: string[];
    constraints: string[];
    conflicts: string[];
    /** An exhibit heading it says it wrote. Present + `corroborated.exhibit: false` = fabricated. */
    exhibit?: string;
  };
  /**
   * The subset of `claimed` that Python found in the prose. Empty means nothing
   * checked out.
   *
   * Partial by design: a stakeholder is corroborated on its NAME only, so this
   * never establishes that the stakeholders' interests genuinely conflict (K1),
   * only that the people named are actually on the page.
   */
  corroborated: {
    stakeholders: string[];
    constraints: string[];
    exhibit: boolean;
  };
  /**
   * The deterministic gate at generation time. Knobs K4 (decidable), K5 (no
   * dominant option) and subtle K8 (telegraphing) are NEVER here — they ship
   * unverified by design, so `passed: true` means "nothing countable is wrong",
   * not "this is ICDC-hard".
   */
  gate: {
    passed: boolean;
    /** e.g. ["K3"] — the exhibit knob, the one that fails most. */
    failedKnobs: string[];
    issues: string[];
    /**
     * The criteria that ACTUALLY RAN, e.g. `["structure", "verbatim_pis",
     * "skills_verbatim", …]` (backend plan 04 §5, gate version 4). The two
     * generating paths run different sets — the bank adds prompt-leak,
     * participant-voice and the shelf-wide rules the day path has no use for —
     * so this is per-roleplay data, never a constant. Optional: every roleplay
     * banked under gate version 3 or earlier carries no such list.
     */
    checks?: string[];
    /**
     * The criteria NOBODY ran, carried on the artifact rather than only in a
     * plan: K1/K2 are a self-report cross-check that does not gate, K4/K5 and
     * subtle K8 ship unverified, and difficulty is NOT refereed. This is why
     * `passed: true` is not a quality verdict — 720 banked files read exactly
     * that with nothing beside it, and an outside audit read it as one.
     */
    unverified?: string[];
  };
  /** The word count the K7 BAND verdict was reached on (1.4x–1.8x the event's own corpus mean). */
  situationWords: number;
  /**
   * Two-pass is required on the Ollama day path: single-pass is immovable at
   * ~290 words there, the District median. `axesHash` pins the seed-axes DATA
   * this draw resolved against (sha256 over both axes files) — the axis
   * membership check reads a mutable file, so without it its verdict is not
   * reproducible after a data edit. Optional for the same reason as `checks`.
   */
  generator: { model: string; passes: 1 | 2; axesHash?: string };
  /**
   * Generator content defects found at parse time, e.g.
   * `boilerplate:denies-judge-questions`, `prompt-leak:QUALITY BAR`. Recorded so
   * they stay countable when someone fixes the prompt — the frontend must never
   * paper over one by rewriting the text.
   */
  defects: string[];
}

export interface RoleplayDay {
  date: string;
  /** Codes present, in `EVENTS` order. */
  events: string[];
  /**
   * Codes this day does not carry. Rendered as greyed "not available for this
   * day" cards — a visibly missing event is honest; silently rendering 24 cards
   * and letting a competitor wonder where their event went is not.
   */
  missing: string[];
}

export interface RoleplayIndex {
  version: number;
  /**
   * The newest date ON DISK, which is routinely in the FUTURE — the buffer is
   * filled 7–14 days ahead. Never show this as "today". The selector picks
   * `max(date) where date <= todayLocal`, with `now` passed in from a mount
   * effect (F1): no `Date.now()` and no argless `new Date()` in `lib/roleplay/*`.
   */
  latest: string;
  /** `["2026-07", "2026-08"]` — one fetchable shard per month. */
  months: string[];
  totals: { days: number; roleplays: number };
}
