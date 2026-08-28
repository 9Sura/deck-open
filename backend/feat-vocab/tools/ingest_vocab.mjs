// Gate an authored vocab batch and merge the survivors into the catalog.
//
// Two calls, in order (vocab plan 01 §3, §4):
//
//   --judge-prompt   run the deterministic gate over authored/<key>/batch-NN.json,
//                    write the rejects out with their reasons, and emit
//                    authored/<key>/judge-NN.md — the survivors' term and definition
//                    with the AUTHORED DIFFICULTY WITHHELD, so a second subagent
//                    rates them blind.
//   --verdicts FILE  apply that subagent's ratings and merge. A judged-"easy" term is
//                    DISCARDED and re-authored, never repaired in — the same discipline
//                    icdc_gate.py enforces on the roleplay bank. An author/judge
//                    disagreement between medium and hard downgrades to the lower.
//
// The merged file must then pass the full gate, mix rule included, or nothing is
// written. Neither call touches a model; the subagent does the two authoring steps.
//
// Usage:
//   node tools/ingest_vocab.mjs --area economics --batch 3 --judge-prompt
//   node tools/ingest_vocab.mjs --area economics --batch 3 --verdicts authored/economics/judged-03.json
//   node tools/ingest_vocab.mjs --area economics --batch 3 --verdicts ... --dry-run

import fs from "node:fs";
import path from "node:path";

import { slugify } from "../lib/slug.mjs";
import {
  catalogFiles,
  readCatalogFile,
  collectSlugHomes,
  loadDenylist,
  gateTerms,
  featRoot,
} from "./vocab_gate.mjs";

const repoRoot = path.resolve(featRoot, "..", "..");
const authoredRoot = path.join(featRoot, "authored");

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`);
}

// Re-running a batch (new verdicts, a corrected prompt) must not double-log its
// rejects, so an entry is keyed by batch + term + stage rather than blindly pushed.
function appendRejects(dir, entries) {
  if (!entries.length) return;
  const file = path.join(dir, "rejected.json");
  const existing = fs.existsSync(file) ? readJson(file) : [];
  const key = (e) => `${e.batch}\u0000${e.term}\u0000${e.stage}`;
  const seen = new Set(existing.map(key));
  const fresh = entries.filter((e) => !seen.has(key(e)));
  if (!fresh.length) return;
  writeJson(file, [...existing, ...fresh]);
  console.log(`[ingest-vocab] ${fresh.length} reject(s) appended to ${path.relative(repoRoot, file)}`);
}

function parseArgs(argv) {
  const opts = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--area") opts.area = argv[++i];
    else if (arg === "--event") opts.event = argv[++i];
    else if (arg === "--batch") opts.batch = Number(argv[++i]);
    else if (arg === "--judge-prompt") opts.judgePrompt = true;
    else if (arg === "--verdicts") opts.verdicts = argv[++i];
    else if (arg === "--dry-run") opts.dryRun = true;
    else {
      console.error(`[ingest-vocab] unknown argument: ${arg}`);
      process.exit(2);
    }
  }
  if (Boolean(opts.area) === Boolean(opts.event)) {
    console.error("[ingest-vocab] pass exactly one of --area <name> or --event <CODE>.");
    process.exit(2);
  }
  if (!Number.isFinite(opts.batch)) {
    console.error("[ingest-vocab] --batch <n> is required.");
    process.exit(2);
  }
  if (Boolean(opts.judgePrompt) === Boolean(opts.verdicts)) {
    console.error("[ingest-vocab] pass exactly one of --judge-prompt or --verdicts <file>.");
    process.exit(2);
  }
  return opts;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const key = opts.area ?? opts.event;
  const kind = opts.area ? "areas" : "events";
  const fileLabel = `catalog/${kind}/${key}.json`;
  const nn = String(opts.batch).padStart(2, "0");
  const dir = path.join(authoredRoot, key);
  const batchFile = path.join(dir, `batch-${nn}.json`);

  if (!fs.existsSync(batchFile)) {
    console.error(`[ingest-vocab] no authored batch at ${path.relative(repoRoot, batchFile)}`);
    process.exit(2);
  }

  const docs = catalogFiles().map(readCatalogFile);
  const target = docs.find((d) => d.file === fileLabel);
  if (!target) {
    console.error(`[ingest-vocab] no catalog file at ${fileLabel} — create it before ingesting.`);
    process.exit(2);
  }

  const denylist = loadDenylist();
  const slugHomes = collectSlugHomes(docs);
  const incoming = readJson(batchFile);
  if (!Array.isArray(incoming)) {
    console.error(`[ingest-vocab] ${path.relative(repoRoot, batchFile)} must be a JSON array of terms.`);
    process.exit(2);
  }

  // The batch is gated as if it were already in its destination file, so a slug
  // the file already owns still trips the duplicate rule. The mix rule is a
  // property of the whole file, so it is checked after the merge, not here.
  const withSources = incoming.map((t) => ({
    ...t,
    sourceRefs: t?.sourceRefs?.length ? t.sourceRefs : (target.sourceRefs ?? []),
  }));
  const bankedSlugs = new Set(target.terms.map((t) => slugify(t.term)));
  const batchHomes = new Map(slugHomes);
  for (const t of withSources) {
    const slug = slugify(t?.term ?? "");
    if (slug && !batchHomes.has(slug)) batchHomes.set(slug, []);
  }

  const gated = gateTerms(withSources, { fileLabel, denylist, slugHomes: batchHomes, skipMix: true });
  const alreadyBanked = gated.passed.filter((t) => bankedSlugs.has(slugify(t.term)));
  const fresh = gated.passed.filter((t) => !bankedSlugs.has(slugify(t.term)));

  console.log(
    `[ingest-vocab] ${incoming.length} authored, ${gated.failures.length} failed the gate, ${alreadyBanked.length} already banked, ${fresh.length} awaiting judgment.`,
  );

  appendRejects(
    dir,
    [
      ...gated.failures.map((f) => ({ batch: opts.batch, term: f.term, stage: "gate", reasons: f.reasons })),
      ...alreadyBanked.map((t) => ({ batch: opts.batch, term: t.term, stage: "gate", reasons: ["duplicate: already banked in this file"] })),
    ],
  );

  if (opts.judgePrompt) {
    if (!fresh.length) {
      console.error("[ingest-vocab] nothing survived the gate — re-author the batch, do not repair it.");
      process.exitCode = 1;
      return;
    }
    const listing = fresh
      .map((t, i) => `${i + 1}. **${t.term}** — ${t.definition}`)
      .join("\n");
    const body = `# Vocab judging — ${key}, batch ${nn}

Rate each term below \`easy\`, \`medium\` or \`hard\` **on your own reading**. You are not
being shown what the author rated them, and you should not try to infer it.

- **hard** — requires a formula, a legal doctrine, a quantitative distinction, or a
  discrimination from a near-neighbour term. The card makes the student compute a
  number or draw a line the term's own name does not draw — \`Five nines availability\`
  is \`hard\` (99.999% is 5.26 minutes a year), \`6-by-6 rule\` is not (the name is the
  rule). A bare number is not enough; the number has to decide something.
- **medium** — a PI-level concept a prepared DECA competitor must define *precisely*;
  the phrase may look familiar but the tested definition is technical. **Naming a
  framework and expanding its acronym is \`medium\`** — BANT, SPIN, AIDA, the Big Five,
  MBTI, DISC, Tuckman, Kohlberg and every named encryption term rate here, because the
  card's whole content is what the letters stand for.
- **easy** — a bright 16-year-old with no DECA training would define it correctly on
  the first try.

Judge the term as a study card: does the *definition given* teach something a
competitor would otherwise get wrong?

## Terms (${fresh.length})

${listing}

## Output

Write \`backend/feat-vocab/authored/${key}/judged-${nn}.json\` — a JSON array, nothing
else:

\`\`\`json
[{ "term": "Contribution margin", "difficulty": "hard" }]
\`\`\`

Then run:

\`\`\`bash
node backend/feat-vocab/tools/ingest_vocab.mjs --${opts.area ? "area" : "event"} ${key} --batch ${opts.batch} --verdicts backend/feat-vocab/authored/${key}/judged-${nn}.json
\`\`\`

A term you rate \`easy\` is discarded and re-authored — it is never edited into the
catalog — so rate it honestly rather than charitably.
`;
    const out = path.join(dir, `judge-${nn}.md`);
    fs.writeFileSync(out, body);
    console.log(`[ingest-vocab] wrote ${path.relative(repoRoot, out)} — ${fresh.length} term(s) to judge.`);
    return;
  }

  // --verdicts: apply the blind ratings, then merge.
  const verdictFile = path.resolve(opts.verdicts);
  if (!fs.existsSync(verdictFile)) {
    console.error(`[ingest-vocab] no verdicts at ${opts.verdicts}`);
    process.exit(2);
  }
  const verdicts = new Map(
    readJson(verdictFile).map((v) => [slugify(v.term), String(v.difficulty ?? "").toLowerCase()]),
  );

  const merged = [];
  const judged = [];
  for (const term of fresh) {
    const slug = slugify(term.term);
    const verdict = verdicts.get(slug);
    if (!verdict) {
      judged.push({ batch: opts.batch, term: term.term, stage: "judge", reasons: ["judge: no verdict for this term"] });
      continue;
    }
    if (verdict === "easy") {
      judged.push({ batch: opts.batch, term: term.term, stage: "judge", reasons: [`judge: rated easy (author said ${term.difficulty})`] });
      continue;
    }
    // Disagreement between medium and hard downgrades to the lower.
    const difficulty = term.difficulty === "hard" && verdict === "hard" ? "hard" : "medium";
    merged.push({ ...term, difficulty });
  }
  appendRejects(dir, judged);

  const nextTerms = [...target.terms, ...merged];
  const check = gateTerms(
    nextTerms.map((t) => ({ ...t, sourceRefs: t?.sourceRefs?.length ? t.sourceRefs : (target.sourceRefs ?? []) })),
    { fileLabel, denylist, slugHomes, skipMix: false },
  );

  console.log(
    `[ingest-vocab] ${merged.length} term(s) survived judging (${judged.length} discarded); file would hold ${nextTerms.length}.`,
  );

  if (!check.ok) {
    for (const line of check.fileFailures) console.error(`[ingest-vocab] ${line}`);
    for (const f of check.failures) console.error(`[ingest-vocab] ${f.term}: ${f.reasons.join("; ")}`);
    console.error("[ingest-vocab] merged file fails the gate — nothing written. Re-author the batch.");
    process.exitCode = 1;
    return;
  }

  if (opts.dryRun) {
    console.log("[ingest-vocab] --dry-run — nothing written.");
    return;
  }

  const doc = readJson(target.path);
  doc.terms = nextTerms;
  writeJson(target.path, doc);
  console.log(`[ingest-vocab] ${fileLabel} now holds ${nextTerms.length} term(s).`);
}

main();
