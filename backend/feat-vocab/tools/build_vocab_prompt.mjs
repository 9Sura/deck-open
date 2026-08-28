// Write a self-contained vocab authoring prompt for one area or one event.
//
// This is the `fill_bank.py --author sonnet` pattern from the roleplay side
// (vocab plan 01 §4): Node writes the prompt, a subagent authors the batch
// beside it, ingest_vocab.mjs gates and banks it. Nothing here calls a model,
// so a re-run is deterministic and free.
//
// Usage:
//   node tools/build_vocab_prompt.mjs --area economics
//   node tools/build_vocab_prompt.mjs --area economics --batch 3 --count 20
//   node tools/build_vocab_prompt.mjs --event ACT
//
// Writes authored/<area|EVENT>/prompt-NN.md. The batch number auto-increments
// past whatever is already in that directory unless --batch says otherwise.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { slugify } from "../lib/slug.mjs";
import { catalogFiles, readCatalogFile, loadDenylist, denylistPath, featRoot } from "./vocab_gate.mjs";

const repoRoot = path.resolve(featRoot, "..", "..");
const authoredRoot = path.join(featRoot, "authored");
const DEFAULT_COUNT = 20;

const PI_LIBRARIES = [
  { label: "Exam PI corpus", dir: path.join(repoRoot, "backend", "test-gen-model", "data", "pi") },
  { label: "Roleplay PI corpus", dir: path.join(repoRoot, "backend", "roleplay-gen-model", "data", "pi") },
];

function readLines(file) {
  if (!fs.existsSync(file)) return [];
  return fs.readFileSync(file, "utf8").split("\n").map((l) => l.trim()).filter(Boolean);
}

/** Core and adjacent PI statements, kept apart — they are two tiers by design. */
function piContext(area) {
  const blocks = [];
  for (const { label, dir } of PI_LIBRARIES) {
    const core = readLines(path.join(dir, `${area}.txt`));
    const adjacent = readLines(path.join(dir, "adjacent", `${area}.txt`));
    if (core.length) blocks.push(`**${label} — ${area} (corroborated):**\n${core.map((l) => `- ${l}`).join("\n")}`);
    if (adjacent.length) {
      blocks.push(
        `**${label} — ${area} (adjacent, support only — do not treat these as the area's own PIs):**\n${adjacent
          .map((l) => `- ${l}`)
          .join("\n")}`,
      );
    }
  }
  return blocks.length ? blocks.join("\n\n") : "_No PI statements on file for this area — author from DECA domain knowledge and cite `deca-domain:" + area + "`._";
}

/** An event's instructional areas, read off its committed deck rather than re-spelled. */
function eventContext(code) {
  const dataRoot = path.join(featRoot, "data");
  for (const cluster of fs.readdirSync(dataRoot)) {
    const file = path.join(dataRoot, cluster, code, "vocab.json");
    if (fs.existsSync(file)) {
      const deck = JSON.parse(fs.readFileSync(file, "utf8"));
      return { cluster, name: deck.event?.name ?? code, areas: deck.instructionalAreas ?? [] };
    }
  }
  console.error(`[build-vocab-prompt] no committed deck for event ${code} — cannot resolve its areas.`);
  process.exit(2);
}

function nextBatch(dir) {
  if (!fs.existsSync(dir)) return 1;
  const used = fs
    .readdirSync(dir)
    .map((f) => /^(?:prompt|batch)-(\d+)\./.exec(f)?.[1])
    .filter(Boolean)
    .map(Number);
  return used.length ? Math.max(...used) + 1 : 1;
}

const RUBRIC = `## The difficulty bar

Every term is \`medium\` or \`hard\`. There is no \`easy\` tier — an easy term is not
hidden, it is rejected.

- **hard** — requires a formula, a legal doctrine, a quantitative distinction, or a
  discrimination from a near-neighbour term. *Contribution margin, price elasticity of
  demand, LIFO reserve, Robinson-Patman Act, keystone markup, yield management,
  accrual vs. cash basis, promissory estoppel.*
- **medium** — a PI-level concept a prepared competitor must define **precisely**. The
  phrase may look familiar; the tested definition is technical. *Channel of
  distribution, service recovery, break-even point, cooperative advertising, product
  mix breadth, cost-plus pricing.*
- **rejected** — a non-DECA high-school student would define it correctly on the first
  try. *Money, competition, profit, information, teamwork, customer.*

**The obviousness test:** could a bright 16-year-old with no DECA training write a
definition a judge would accept? If yes, cut it. If the term is common but its *tested*
definition is technical and they would get it wrong, it is \`medium\`, and the definition
must be written to show exactly the part they would miss.

**Naming a framework and expanding its acronym is \`medium\`, not \`hard\`.** This is the
single most common way a batch fails the mix rule, and it was measured across 21 area
files in Phase 3, not guessed. The blind judge downgraded BANT, SPIN, AIDA, the Big
Five, MBTI, DISC, Tuckman's stages, Kohlberg's stages and every named encryption term.
A \`hard\` card makes the student **compute a number or draw a line the term's own name
does not draw**:

- \`Five nines availability\` survives — 99.999% is 5.26 minutes of downtime a year, a
  figure the name does not give you — where \`asymmetric encryption\` dies, because the
  name already states the distinction.
- \`10-20-30 rule\` survives — it decides slide count, minutes and font size — where
  \`6-by-6 rule\` dies, because the name is the rule.

So a bare number is not enough either: **the number has to decide something.** If the
card's whole content is "X stands for A, B, C and D", it is \`medium\`. Rate it that way
and spend the slot on a term carrying an arithmetic, a threshold or a statutory line.

**At least half of what you author must be \`hard\`.** A batch that is mostly \`medium\`
fails the gate as a file.`;

const SHAPE = `## Output shape

Write ONE JSON file, an array of term objects, nothing else — no prose, no code fence:

\`\`\`json
[
  {
    "term": "Contribution margin",
    "definition": "Sales revenue minus variable costs — the amount each unit contributes toward fixed costs and profit.",
    "whyItMatters": "Break-even and pricing-floor questions on the finance exam are solved with contribution margin, not gross profit.",
    "difficulty": "hard",
    "sourceRefs": ["backend/test-gen-model/data/pi/financial_analysis.txt"],
    "confusableWith": ["gross-margin"]
  }
]
\`\`\`

Field rules, each enforced by \`tools/vocab_gate.mjs\` — a violation is discarded, never
repaired in:

- \`term\` — the vocabulary item. Do not store a slug; it is derived from this.
- \`definition\` — **at least 60 characters**, and it must NOT open by restating the term
  ("Contribution margin is the..." is rejected). Define the tested distinction.
- \`whyItMatters\` — non-empty, and it must name a **concrete exam or roleplay
  situation**. A term whose importance you cannot situate is a term to drop.
- \`difficulty\` — \`"medium"\` or \`"hard"\`. Any other value fails.
- \`sourceRefs\` — non-empty. A PI-derived term cites the PI file it came from. A term
  authored from DECA domain knowledge cites \`deca-domain:<area>\`.
- \`confusableWith\` — optional, slugs of near-neighbour terms students mix up
  (\`markup-on-cost\` vs \`markup-on-retail\`, \`fifo\` vs \`lifo\`). Cheap to write and where
  much of the study value lives.`;

function parseArgs(argv) {
  const opts = { count: DEFAULT_COUNT };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--area") opts.area = argv[++i];
    else if (arg === "--event") opts.event = argv[++i];
    else if (arg === "--batch") opts.batch = Number(argv[++i]);
    else if (arg === "--count") opts.count = Number(argv[++i]);
    else {
      console.error(`[build-vocab-prompt] unknown argument: ${arg}`);
      process.exit(2);
    }
  }
  if (Boolean(opts.area) === Boolean(opts.event)) {
    console.error("[build-vocab-prompt] pass exactly one of --area <name> or --event <CODE>.");
    process.exit(2);
  }
  return opts;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const docs = catalogFiles().map(readCatalogFile);
  const target = opts.area
    ? docs.find((d) => d.kind === "areas" && d.name === opts.area)
    : docs.find((d) => d.kind === "events" && d.name === opts.event);

  const key = opts.area ?? opts.event;
  const kind = opts.area ? "areas" : "events";
  const fileLabel = `catalog/${kind}/${key}.json`;

  const banked = (target?.terms ?? []).map((t) => `- ${t.term} (${t.difficulty ?? "ungraded"})`);
  const registry = docs
    .filter((d) => d.file !== fileLabel)
    .flatMap((d) => d.terms.map((t) => slugify(t.term)))
    .filter(Boolean)
    .sort();
  const denylist = [...loadDenylist()].sort();

  const dir = path.join(authoredRoot, key);
  const batch = Number.isFinite(opts.batch) ? opts.batch : nextBatch(dir);
  const nn = String(batch).padStart(2, "0");

  const scope = opts.area
    ? `## Scope — instructional area \`${opts.area}\`

Author vocabulary a competitor is tested on **within this instructional area**. It is
the area, not any one event, that owns these terms — several events share it.

${piContext(opts.area)}`
    : (() => {
        const meta = eventContext(opts.event);
        return `## Scope — event flavor for \`${opts.event}\` (${meta.name}, ${meta.cluster} cluster)

Author vocabulary **specific to this event** — the terms that make its deck read
differently from its cluster siblings. Its instructional areas are already covered by
the area files, so do NOT re-author general area vocabulary here; author what this
event's roleplays and cases turn on.

Instructional areas this event declares: ${meta.areas.join(", ") || "(none on file)"}.

Cite \`deca-domain:${opts.event}\` in \`sourceRefs\` for event-flavor terms.`;
      })();

  const body = `# Vocab authoring — ${key}, batch ${nn}

Author **${opts.count} new terms** for \`${fileLabel}\`.

${scope}

${RUBRIC}

## Already banked in this file — do not re-author (${banked.length})

${banked.length ? banked.join("\n") : "_(empty — this file is being authored from zero)_"}

## Slugs owned by other catalog files — every term has exactly one home (${registry.length})

A slug that appears in two catalog files fails the gate. If one of these is the right
term for this area, it stays where it is; author something else.

${registry.length ? registry.map((s) => `- ${s}`).join("\n") : "_(none)_"}

## Denylist — purged, may never re-enter (${denylist.length})

${denylist.length ? denylist.map((s) => `- ${s}`).join("\n") : `_(empty — see ${path.relative(repoRoot, denylistPath)})_`}

${SHAPE}

## Where to write it

\`backend/feat-vocab/authored/${key}/batch-${nn}.json\`

Then run:

\`\`\`bash
node backend/feat-vocab/tools/ingest_vocab.mjs --${opts.area ? "area" : "event"} ${key} --batch ${batch} --judge-prompt
\`\`\`
`;

  fs.mkdirSync(dir, { recursive: true });
  const out = path.join(dir, `prompt-${nn}.md`);
  fs.writeFileSync(out, body);
  console.log(`[build-vocab-prompt] wrote ${path.relative(repoRoot, out)}`);
  console.log(`[build-vocab-prompt]   ${opts.count} term(s) requested, ${banked.length} already banked, ${registry.length} slug(s) spoken for, ${denylist.length} denied.`);
}

main();
