/**
 * Theme registry — the single source of truth for the theme switcher.
 *
 * Each entry maps 1:1 to a `[data-theme="…"]` value token block in
 * `app/globals.css` (Classic = the `:root` defaults, applied when no attribute
 * is set). Adding a theme = one entry here + one CSS block there.
 *
 * `swatch` holds four representative hexes (paper, ink, accent, highlight) used
 * ONLY to draw the little preview chips in the picker — they mirror the CSS
 * token values but are not what actually skins the app (the cascade does that).
 * Keep them in sync with §2 of the theming plan when tuning palettes.
 */

export type ThemeId =
  | "notebook"
  | "golden-hour"
  | "terminal"
  | "first-bloom"
  | "midsummer"
  | "first-snow";
export type ThemeMode = "light" | "dark";

/** Ornamental overlay a theme opts into — one per seasonal theme. Each maps to a
 *  component in <ThemeEffects>'s EFFECTS map. */
export type ThemeEffect = "snow" | "petals" | "seeds";

export interface ThemeDef {
  id: ThemeId;
  label: string;
  blurb: string;
  mode: ThemeMode;
  /** Preview chips: [paper, ink, accent, highlight]. */
  swatch: [string, string, string, string];
  /**
   * Optional non-interactive DOM overlay rendered by <ThemeEffects>. Kept
   * separate from the token cascade — a seasonal theme is (base tokens) +
   * (optional effect), and the two never mix. See first-snow plan §1.
   */
  effect?: ThemeEffect;
  /**
   * [startMonth, endMonth], 1-indexed and inclusive; wraps the year-end
   * (e.g. [12, 2] = Dec–Feb). Only surfaces an "in season" badge in the
   * picker — nothing auto-switches. See first-snow plan §5.
   */
  seasonWindow?: [number, number];
}

export const DEFAULT_THEME: ThemeId = "notebook";

export const THEMES: ThemeDef[] = [
  {
    id: "notebook",
    label: "Classic",
    blurb: "The original cream notebook — DECA blue, navy & gold.",
    mode: "light",
    swatch: ["#fbf7ef", "#2a2622", "#0b5fba", "#f5b301"],
  },
  {
    id: "golden-hour",
    label: "Golden Hour",
    blurb: "A warm light refresh — amber signature over sunnier cream.",
    mode: "light",
    swatch: ["#fcf6ea", "#33291f", "#e08a2e", "#f5b301"],
  },
  {
    id: "terminal",
    label: "Terminal",
    blurb: "Charcoal study machine — phosphor green, amber, mono numerals.",
    mode: "dark",
    swatch: ["#16181c", "#e6e6e3", "#4ade80", "#fbbf24"],
  },
  {
    id: "first-bloom",
    label: "First Bloom",
    blurb: "A spring meadow — fresh green, blossom pink, petals on the breeze.",
    mode: "light",
    swatch: ["#f3faef", "#2b3327", "#3f9d5a", "#f6c945"],
    effect: "petals",
    seasonWindow: [3, 5],
  },
  {
    id: "midsummer",
    label: "Midsummer",
    blurb: "A summer sunset — coral & gold over an apricot sky, seeds on the breeze.",
    mode: "light",
    swatch: ["#fde3cf", "#3a2333", "#e85d3c", "#f4a72a"],
    effect: "seeds",
    seasonWindow: [6, 8],
  },
  {
    id: "first-snow",
    label: "First Snow",
    blurb: "A midnight-blue snow day — frost-white ink, drifting flakes.",
    mode: "dark",
    swatch: ["#213456", "#f2f7fc", "#8fd4ff", "#ffd674"],
    effect: "snow",
    seasonWindow: [12, 2],
  },
];

export const THEME_IDS: ThemeId[] = THEMES.map((t) => t.id);

/** Storage key shared by the provider and the FOUC head script. */
export const THEME_STORAGE_KEY = "deca-theme";

export function isThemeId(v: unknown): v is ThemeId {
  return typeof v === "string" && (THEME_IDS as string[]).includes(v);
}
