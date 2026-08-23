// The scenario's body: the exhibit as a DATA BLOCK, and the situation as prose
// (frontend plan 11 §4b). Both live here on purpose — the whole point of the
// exhibit is that it is *not* another paragraph, and that contrast is easier to
// keep honest when the two renderers sit side by side.
//
// LEGACY SURFACE. This renders the data block that the RETIRED `icdc-plus` tier
// required; the live `icdc` tier BANS one (F3), because 0 of the 396 real DECA
// roleplays in the backend corpus carry an exhibit. It stays because the banked
// `icdc-plus` entries still have theirs and must keep rendering. Do not add UI
// that assumes an exhibit is present, and do not reintroduce one to the generator.
//
// The retired K3 knob existed because the generator kept burying
// decision-relevant numbers inside the situation. Treating the exhibit as a
// first-class object — framed, tabular where it can be — is what makes that knob
// matter to a competitor rather than to a scorer.
//
// TWO SHAPES, both measured across the committed fixtures, not assumed:
//   markdown table   `| Position | Current Staffing | Project Demand |`   (HRM)
//   labelled figure  `Current marketing budget: $500,000 (allocated ...)`  (PBM,
//                    MTDM, ACT, SEM)
// Only ONE of the five fixtures that carry an exhibit uses a table, so a renderer
// that assumes cells is wrong for four of them. Split on "|" only when the row
// actually has one. `types.ts` is explicit that rows are stored close to
// as-authored and are never parsed into cells upstream.
//
// And two of the seven fixtures (PFL, BLTDM) have NO exhibit at all — until the
// K3 prompt fix lands that is the normal case, not an edge case. `archive.ts`
// drops an exhibit with zero rows rather than handing over an empty one, and this
// component returns null on anything empty, so an absent exhibit renders as
// nothing. Never an empty box.

import { cn } from "@/lib/utils";
import type { RoleplayExhibit } from "@/lib/roleplay/types";

/** A `|---|:--:|` rule row — markdown scaffolding, never data. */
const RULE_CELL = /^:?-{2,}:?$/;

/** Longest a leading `Label:` may be before we stop treating it as a label. */
const MAX_LABEL_CHARS = 64;

interface ParsedTable {
  header: string[];
  body: string[][];
}

/** Split a markdown table row into trimmed cells, dropping the edge pipes. */
function cells(row: string): string[] {
  const parts = row.split("|").map((c) => c.trim());
  if (parts.length > 0 && parts[0] === "") parts.shift();
  if (parts.length > 0 && parts[parts.length - 1] === "") parts.pop();
  return parts;
}

/**
 * A table only when EVERY row is a pipe row — a mixed block (one stray pipe in a
 * sentence) stays plain text, because half a table is worse than none.
 * `types.ts` says the parser already drops rules, but tolerance over strictness
 * (plan 11 §8.1): drop any that survived rather than rendering `---` as a figure.
 */
function parseTable(rows: string[]): ParsedTable | null {
  if (rows.length < 2 || !rows.every((r) => r.includes("|"))) return null;
  const grid = rows
    .map(cells)
    .filter((r) => r.length > 0 && !r.every((c) => RULE_CELL.test(c)));
  if (grid.length < 2) return null;
  const [header, ...body] = grid;
  return { header, body };
}

/**
 * `"Current marketing budget: $500,000 (…)"` → label + value, so the figures line
 * up in a column instead of running together as sentences. Returns null when the
 * colon is missing, leads the row, has nothing after it, or sits so far in that
 * it is punctuation inside a sentence rather than a label.
 *
 * The colon must be followed by WHITESPACE (issue #111). `MAX_LABEL_CHARS` only
 * catches a colon that lands late; a colon inside the value itself lands early,
 * so `"9:00 AM cut-off for same-day dispatch"` used to render as label `9` beside
 * value `00 AM cut-off…`, and `"3:1 debt-to-equity after the raise"` as label `3`.
 * A clock time and a ratio never have a space after the colon; a label always
 * does. Declining to split is the safe outcome — the row still renders in full,
 * just as plain text. Latent on the committed fixtures (no time or ratio row
 * among them), but a real generated batch takes this from 5 exhibits to 28/day.
 */
const FIGURE_ROW = new RegExp(`^([^:]{1,${MAX_LABEL_CHARS}}):\\s+(\\S.*)$`);

function splitFigure(row: string): { label: string; value: string } | null {
  const m = FIGURE_ROW.exec(row);
  if (!m) return null;
  return { label: m[1].trim(), value: m[2].trim() };
}

export function ExhibitBlock({
  exhibit,
  className,
}: {
  exhibit: RoleplayExhibit;
  className?: string;
}) {
  const rows = exhibit.rows.map((r) => r.trim()).filter(Boolean);
  if (rows.length === 0) return null;

  const table = parseTable(rows);

  return (
    <figure
      className={cn(
        "sketch-radius border-2 border-ink bg-paper-2 p-4 sm:p-5",
        className,
      )}
    >
      <figcaption className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="marker text-sm text-muted">exhibit</span>
        {exhibit.title ? (
          <span className="font-display text-base font-bold tracking-tight">
            {exhibit.title}
          </span>
        ) : null}
      </figcaption>

      {table ? (
        // The table can be wider than a phone; it scrolls inside the frame rather
        // than pushing the dialog sideways.
        <div className="-mx-1 overflow-x-auto px-1">
          <table className="w-full min-w-[22rem] border-collapse text-sm">
            <thead>
              <tr>
                {table.header.map((c, i) => (
                  <th
                    key={i}
                    scope="col"
                    className={cn(
                      "border-b-2 border-ink px-2 py-1.5 font-semibold",
                      i === 0 ? "text-left" : "text-right",
                    )}
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.body.map((row, r) => (
                <tr key={r} className="border-b border-dashed border-line last:border-0">
                  {row.map((c, i) => (
                    <td
                      key={i}
                      className={cn(
                        "px-2 py-1.5",
                        i === 0
                          ? "text-left text-ink/80"
                          : "stat text-right font-semibold",
                      )}
                    >
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <ul className="flex flex-col gap-2 text-sm">
          {rows.map((row, i) => {
            const figure = splitFigure(row);
            return (
              <li
                key={i}
                className="border-b border-dashed border-line pb-2 last:border-0 last:pb-0"
              >
                {figure ? (
                  <>
                    <span className="text-ink/70">{figure.label}</span>{" "}
                    <span className="stat font-semibold">{figure.value}</span>
                  </>
                ) : (
                  <span className="text-ink/80">{row}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </figure>
  );
}

/**
 * The situation, as paragraphs.
 *
 * `situation` is 8–12 paragraphs separated by a blank line (`\n\n`) — never one
 * blob — so it is split rather than dumped into a single `<p>`. Blank fragments
 * are dropped so a trailing newline can't emit an empty paragraph.
 */
export function SituationProse({
  situation,
  className,
}: {
  situation: string;
  className?: string;
}) {
  const paragraphs = situation
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);

  if (paragraphs.length === 0) return null;

  return (
    <div className={cn("flex flex-col gap-3 text-[0.95rem] leading-relaxed text-ink/85", className)}>
      {paragraphs.map((p, i) => (
        <p key={i}>{p}</p>
      ))}
    </div>
  );
}
