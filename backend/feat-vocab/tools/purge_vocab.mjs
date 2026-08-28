// Phase 1 of vocab plan 01: purge and regrade the catalog that already exists.
//
// ingest_vocab.mjs banks NEW authored batches. This is its mirror for terms
// already in the catalog, which is all of Phase 1. What separates the disposals
// is whether the CONCEPT failed or only this COPY of it:
//
//   DELETED AND DENYLISTED — a term the blind judge rates `easy`. The concept
//     itself failed the §3 obviousness bar, so it may never re-enter; that is
//     what catalog/denylist.txt is for.
//   DELETED, NOT DENYLISTED — the concept is sound, this copy is not, so Phase 3
//     must be free to author it properly. Two ways in:
//       - a deterministic rule (definition under 60 characters, a duplicate
//         losing its home);
//       - the judge rates it `reauthor` — a real DECA-testable concept whose
//         definition here is written at a lay level and teaches nothing.
//
// The `reauthor` verdict exists because the judge grades the definition as
// given, and without it a badly-written card would permanently denylist a good
// concept. Economic systems and inflation's impact are both corroborated in the
// exam PI corpus for this area, and both cards were written lay enough to read
// as `easy` — the denylist would have banned two live PIs on prose. (The PI
// lines themselves are deliberately not quoted here: this file ships to the
// public mirror and the corpus does not, so a reader there could not check them
// anyway, and PI phrasing is the taxonomy migration constraint 3 withholds.)
// The inverse case is left deliberately open. A term that is BOTH obvious and
// short — `Competition`, 59 chars, named in §1 as an obviousness failure — exits
// deterministically and is therefore not denylisted, so Phase 3 may re-author
// it. That is a deferred re-entry, not a leak: ingest_vocab.mjs judges every
// authored batch, so an obvious concept is rejected there instead. Judging the
// deterministic failures here to close it early would mean judging terms whose
// text is already being discarded, and would break "a file is judged whole or
// not at all" — the judged set is the survivors, not the whole file.
//
// Duplicate homes, from the §6 Phase 1 rules:
//   area vs. event   the AREA file wins. Event flavor is what the area files do
//                    not cover, so an event re-authoring an area term is the
//                    event's copy to lose. Applied automatically.
//   event vs. event  dropped from BOTH. A term two events want is not event
//                    flavor; it belongs in an area file and Phase 3 authors it
//                    there. Applied automatically.
//   area vs. area    NOT decided here. ~26% of distinct PIs are filed by DECA
//                    under more than one instructional area (see CLAUDE.md), so
//                    this is a real classification call, not a defect. The call
//                    is recorded as data in catalog/duplicate-homes.json, with
//                    the PI line or the reasoning it rests on; a contested slug
//                    missing from that file blocks the run rather than being
//                    guessed at.
//
// Usage:
//   node tools/purge_vocab.mjs --report                     the §8 purge report
//   node tools/purge_vocab.mjs --resolve-duplicates         dry run
//   node tools/purge_vocab.mjs --resolve-duplicates --apply
//   node tools/purge_vocab.mjs --judge-prompt --area economics
//   node tools/purge_vocab.mjs --verdicts <file> --area economics [--apply]
//
// Nothing is written without --apply.

import fs from "node:fs";
import path from "node:path";

import { slugify } from "../lib/slug.mjs";
import {
  catalogFiles,
  readCatalogFile,
  collectSlugHomes,
  loadDenylist,
  denylistPath,
  gateTerms,
  featRoot,
} from "./vocab_gate.mjs";

const repoRoot = path.resolve(featRoot, "..", "..");
const authoredRoot = path.join(featRoot, "authored");
// The two PI libraries are separate by design and must never be re-synced to each
// other (CLAUDE.md), so evidence from each is labelled by which one it came from.
const PI_DIRS = [
  { label: "exam", dir: path.join(repoRoot, "backend", "test-gen-model", "data", "pi") },
  { label: "roleplay", dir: path.join(repoRoot, "backend", "roleplay-gen-model", "data", "pi") },
];

const isArea = (file) => file.includes("/areas/");
const homesPath = path.join(featRoot, "catalog", "duplicate-homes.json");

/** slug -> winning catalog file, for the area-vs-area calls made by hand. */
function loadDuplicateHomes() {
  if (!fs.existsSync(homesPath)) return new Map();
  const parsed = JSON.parse(fs.readFileSync(homesPath, "utf8"));
  return new Map((parsed.homes ?? []).map((h) => [slugify(h.slug), h.home]));
}

function writeDoc(entry, terms) {
  const doc = JSON.parse(fs.readFileSync(entry.path, "utf8"));
  doc.terms = terms;
  fs.writeFileSync(entry.path, `${JSON.stringify(doc, null, 2)}\n`);
}

function appendDenylist(slugs, note) {
  if (!slugs.length) return;
  const existing = loadDenylist();
  const fresh = [...new Set(slugs)].filter((s) => !existing.has(s)).sort();
  if (!fresh.length) return;
  const stamp = `\n# ${note}\n${fresh.join("\n")}\n`;
  fs.appendFileSync(denylistPath, stamp);
  console.log(`[purge-vocab] ${fresh.length} slug(s) added to ${path.relative(repoRoot, denylistPath)}`);
}

/** Which PI corpus files mention this term — evidence for an area-vs-area call. */
function piEvidence(term) {
  const needle = String(term).toLowerCase();
  const hits = [];
  for (const { label, dir } of PI_DIRS) {
    if (!fs.existsSync(dir)) continue;
    for (const file of fs.readdirSync(dir)) {
      if (!file.endsWith(".txt")) continue;
      const text = fs.readFileSync(path.join(dir, file), "utf8").toLowerCase();
      if (text.includes(needle)) hits.push(`${label}:${file.replace(/\.txt$/, "")}`);
    }
  }
  return hits;
}

/** slug -> { areas: [file], events: [file] } for every slug in more than one file. */
function duplicateHomes(docs) {
  const homes = collectSlugHomes(docs);
  const out = new Map();
  for (const [slug, files] of homes) {
    const uniq = [...new Set(files)];
    if (uniq.length < 2) continue;
    out.set(slug, {
      areas: uniq.filter(isArea),
      events: uniq.filter((f) => !isArea(f)),
    });
  }
  return out;
}

/**
 * One winner per contested slug. `decided` carries the hand-made area-vs-area
 * calls; a slug it does not cover, and that needs it, lands in `unresolved` and
 * stops the run.
 */
function classifyDuplicates(dupes, decided = new Map()) {
  const areaWins = []; // [slug, keepFile, dropFiles]  — automatic, area beats event
  const byDecision = []; // [slug, keepFile, dropFiles] — from duplicate-homes.json
  const bothDrop = []; // [slug, dropFiles]             — no area home at all
  const unresolved = []; // [slug, allFiles]
  const misfiled = []; // [slug, homeClaimed]           — decision names a file without the term

  for (const [slug, { areas, events }] of dupes) {
    const all = [...areas, ...events];
    if (areas.length >= 2) {
      const home = decided.get(slug);
      if (!home) unresolved.push([slug, all]);
      else if (!areas.includes(home)) misfiled.push([slug, home]);
      else byDecision.push([slug, home, all.filter((f) => f !== home)]);
    } else if (areas.length === 1 && events.length) {
      areaWins.push([slug, areas[0], events]);
    } else {
      bothDrop.push([slug, events]);
    }
  }
  return { areaWins, byDecision, bothDrop, unresolved, misfiled };
}

/**
 * Terms in one file that fail a deterministic rule for a reason OTHER than the
 * missing difficulty — the ones Phase 1 deletes without denylisting.
 */
function deterministicFailures(doc, denylist, slugHomes) {
  const withSources = doc.terms.map((t) => ({
    ...t,
    // Phase 1 grades what is on disk; difficulty is what it is about to assign,
    // so it is stubbed here to keep the rule out of this particular question.
    difficulty: t.difficulty ?? "medium",
    sourceRefs: t.sourceRefs?.length ? t.sourceRefs : (doc.sourceRefs ?? []),
  }));
  const { failures } = gateTerms(withSources, {
    fileLabel: doc.file,
    denylist,
    slugHomes,
    skipMix: true,
  });
  return failures;
}

function parseArgs(argv) {
  const opts = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--report") opts.report = true;
    else if (arg === "--resolve-duplicates") opts.resolveDuplicates = true;
    else if (arg === "--judge-prompt") opts.judgePrompt = true;
    else if (arg === "--verdicts") opts.verdicts = argv[++i];
    else if (arg === "--area") opts.area = argv[++i];
    else if (arg === "--event") opts.event = argv[++i];
    else if (arg === "--apply") opts.apply = true;
    else {
      console.error(`[purge-vocab] unknown argument: ${arg}`);
      process.exit(2);
    }
  }
  const modes = [opts.report, opts.resolveDuplicates, opts.judgePrompt, Boolean(opts.verdicts)].filter(Boolean);
  if (modes.length > 1) {
    console.error("[purge-vocab] pass one mode: --report, --resolve-duplicates, --judge-prompt or --verdicts.");
    process.exit(2);
  }
  if (!modes.length) opts.report = true;
  return opts;
}

function resolveTarget(docs, opts) {
  if (Boolean(opts.area) === Boolean(opts.event)) {
    console.error("[purge-vocab] this mode needs exactly one of --area <name> or --event <CODE>.");
    process.exit(2);
  }
  const kind = opts.area ? "areas" : "events";
  const name = opts.area ?? opts.event;
  const doc = docs.find((d) => d.kind === kind && d.name === name);
  if (!doc) {
    console.error(`[purge-vocab] no ${kind} catalog file named ${name}`);
    process.exit(2);
  }
  return doc;
}

function report(docs, denylist, slugHomes) {
  const dupes = duplicateHomes(docs);
  const { areaWins, byDecision, bothDrop, unresolved } = classifyDuplicates(dupes, loadDuplicateHomes());

  let terms = 0;
  let gateFailing = 0;
  let owed = 0;
  const perFile = [];
  for (const doc of docs) {
    terms += doc.terms.length;
    const failures = deterministicFailures(doc, denylist, slugHomes);
    gateFailing += failures.length;
    // Judgment is owed on a term only if it is BOTH ungraded and not already
    // headed for deletion on a deterministic rule. Counting graded terms here is
    // what kept this line from converging as files were graded.
    const failing = new Set(failures.map((f) => f.slug));
    owed += doc.terms.filter((t) => !t.difficulty && !failing.has(slugify(t.term))).length;
    perFile.push({ file: doc.file, terms: doc.terms.length, failing: failures.length, failures });
  }

  console.log(`[purge-vocab] PHASE 1 PURGE REPORT — ${docs.length} file(s), ${terms} term(s)\n`);
  console.log("Deterministic failures (deleted, NOT denylisted — the concept survives for Phase 3):");
  for (const f of perFile.filter((f) => f.failing)) {
    console.log(`  ${f.file}  ${f.failing}/${f.terms}`);
    for (const fail of f.failures) console.log(`      ${fail.term}: ${fail.reasons.join("; ")}`);
  }
  console.log(`\n  ${gateFailing} term instance(s) across ${perFile.filter((f) => f.failing).length} file(s).\n`);

  console.log(`Duplicate slugs: ${dupes.size} slug(s) in more than one file.`);
  console.log(`  area beats event, event copy dropped : ${areaWins.length}`);
  console.log(`  both event copies dropped           : ${bothDrop.length}`);
  console.log(`  area vs. area, decided in duplicate-homes.json : ${byDecision.length}`);
  for (const [slug, home] of byDecision) console.log(`      ${slug} -> ${path.basename(home)}`);
  console.log(`  area vs. area, NEEDS A DECISION     : ${unresolved.length}`);
  for (const [slug, files] of unresolved) {
    const evidence = piEvidence(slug.replace(/-/g, " "));
    console.log(`      ${slug}`);
    console.log(`        homes: ${files.map((f) => path.basename(f)).join(" | ")}`);
    console.log(`        PI corpus mentions: ${evidence.length ? evidence.join(", ") : "(none — no corpus evidence either way)"}`);
  }

  console.log(
    `\n[purge-vocab] Judgment is still owed on ${owed} term(s); ${terms - gateFailing - owed} already graded. §8 stops the campaign if the total purge exceeds 60%.`,
  );
}

function judgePrompt(doc, denylist, slugHomes) {
  const failing = new Set(deterministicFailures(doc, denylist, slugHomes).map((f) => f.slug));
  const candidates = doc.terms.filter((t) => !failing.has(slugify(t.term)));
  if (!candidates.length) {
    console.error(`[purge-vocab] every term in ${doc.file} already fails a deterministic rule — nothing to judge.`);
    process.exitCode = 1;
    return;
  }
  const listing = candidates.map((t, i) => `${i + 1}. **${t.term}** — ${t.definition}`).join("\n");
  const body = `# Vocab purge — regrade \`${doc.file}\`

These terms are already in the catalog and carry no difficulty. Nothing here has been
graded before, so there is no prior rating to agree or disagree with.

Ask **two separate questions** about each term, in this order. They decide different
things and conflating them is the mistake this format exists to prevent.

**Question 1 — is the CONCEPT worth testing?**
Would a bright 16-year-old with no DECA training already know this well enough to
answer a judge correctly? Ask it about the idea itself, not about the wording below.

- **No, the concept is obvious** → verdict \`easy\`. The term is deleted **and
  permanently denylisted**; no one may ever author it again. Reserve this for ideas
  that are genuinely common knowledge — \`Profit\`, \`Customer\`, \`Teamwork\`.

**Question 2 — does THIS definition teach the concept?**
Only for concepts that survived question 1. Read the definition as a study card:
does it give the precise, technical content a competitor would otherwise get wrong?

- **No — the concept is real but this card is written at a lay level and teaches
  nothing** → verdict \`reauthor\`. The term is deleted but **not** denylisted, and a
  later phase writes a proper card for it. Use this whenever the idea is DECA-testable
  and the sentence in front of you simply fails to do it justice. It is not a
  half-measure and it is not a downgrade — it is the correct verdict for a good
  concept with a bad card.
- **Yes** → grade it:
  - **hard** — requires a formula, a legal doctrine, a quantitative distinction, or a
    discrimination from a near-neighbour term. Calibrate against these: *contribution
    margin, price elasticity of demand, LIFO reserve, Robinson-Patman Act, keystone
    markup, yield management, accrual vs. cash basis, promissory estoppel.* A term
    that merely states a principle precisely is \`medium\`, not \`hard\`.
  - **medium** — a PI-level concept a prepared DECA competitor must define
    *precisely*; the phrase may look familiar but the tested definition is technical.

Be strict. This pass exists to shrink the catalog. But strictness belongs in question
1, on the concept — do not use \`easy\` to express that a definition is weakly written,
because that bans the idea forever. \`reauthor\` is what says "weak card".

## Terms (${candidates.length})

${listing}

## Output

Write \`backend/feat-vocab/authored/purge/${doc.kind}-${doc.name}.json\` — a JSON array,
nothing else:

\`\`\`json
[{ "term": "Contribution margin", "difficulty": "hard" }]
\`\`\`

One entry per term listed above, all ${candidates.length} of them — a file is judged whole or not
at all. \`difficulty\` is exactly one of \`easy\`, \`reauthor\`, \`medium\`, \`hard\`.

Then run:

\`\`\`bash
node backend/feat-vocab/tools/purge_vocab.mjs --verdicts backend/feat-vocab/authored/purge/${doc.kind}-${doc.name}.json --${doc.kind === "areas" ? "area" : "event"} ${doc.name}
\`\`\`
`;
  const dir = path.join(authoredRoot, "purge");
  fs.mkdirSync(dir, { recursive: true });
  const out = path.join(dir, `${doc.kind}-${doc.name}.md`);
  fs.writeFileSync(out, body);
  console.log(`[purge-vocab] wrote ${path.relative(repoRoot, out)} — ${candidates.length} term(s) to judge.`);
}

function applyVerdicts(doc, opts, denylist, slugHomes) {
  const file = path.resolve(opts.verdicts);
  if (!fs.existsSync(file)) {
    console.error(`[purge-vocab] no verdicts at ${opts.verdicts}`);
    process.exit(2);
  }
  const verdicts = new Map(
    JSON.parse(fs.readFileSync(file, "utf8")).map((v) => [slugify(v.term), String(v.difficulty ?? "").toLowerCase()]),
  );
  const failing = new Set(deterministicFailures(doc, denylist, slugHomes).map((f) => f.slug));

  const kept = [];
  const purged = []; // judged easy — deleted AND denylisted, the concept failed
  const dropped = []; // deterministic rule — deleted, concept survives
  const reauthored = []; // judged reauthor — deleted, concept survives
  const unjudged = [];
  for (const term of doc.terms) {
    const slug = slugify(term.term);
    if (failing.has(slug)) {
      dropped.push(term.term);
      continue;
    }
    const verdict = verdicts.get(slug);
    if (!verdict) {
      unjudged.push(term.term);
      continue;
    }
    if (verdict === "easy") {
      purged.push(slug);
      continue;
    }
    // A real concept whose card teaches nothing. Deleted like `easy`, but the
    // slug never reaches the denylist — Phase 3 authors it properly.
    if (verdict === "reauthor") {
      reauthored.push(term.term);
      continue;
    }
    if (verdict !== "medium" && verdict !== "hard") {
      console.error(`[purge-vocab] ${term.term}: verdict "${verdict}" is not easy/reauthor/medium/hard.`);
      process.exitCode = 1;
      return;
    }
    kept.push({ ...term, difficulty: verdict });
  }

  if (unjudged.length) {
    console.error(`[purge-vocab] ${unjudged.length} term(s) have no verdict — judge the whole file or nothing:`);
    for (const t of unjudged) console.error(`    ${t}`);
    process.exitCode = 1;
    return;
  }

  const hard = kept.filter((t) => t.difficulty === "hard").length;
  const share = kept.length ? Math.round((hard / kept.length) * 100) : 0;
  const surviving = dropped.length + reauthored.length;
  console.log(
    `[purge-vocab] ${doc.file}: ${doc.terms.length} in, ${kept.length} kept (${hard} hard, ${share}%), ${purged.length} purged as easy, ${surviving} deleted with the concept intact (${dropped.length} deterministic, ${reauthored.length} judged reauthor).`,
  );
  if (reauthored.length) {
    console.log(`[purge-vocab]   re-author (NOT denylisted): ${reauthored.join(", ")}`);
  }
  if (kept.length && share < 50) {
    console.log("[purge-vocab]   below the >=50% hard mix — Phase 3 authoring for this area must close the gap.");
  }

  if (!opts.apply) {
    console.log("[purge-vocab] dry run — pass --apply to write.");
    return;
  }
  writeDoc(doc, kept);
  appendDenylist(purged, `purged from ${doc.file} — judged easy (plan 01 Phase 1)`);
  console.log(`[purge-vocab] wrote ${doc.file} — ${kept.length} term(s).`);
}

function resolveDuplicates(docs, opts) {
  const { areaWins, byDecision, bothDrop, unresolved, misfiled } = classifyDuplicates(
    duplicateHomes(docs),
    loadDuplicateHomes(),
  );

  if (misfiled.length) {
    console.error(`[purge-vocab] ${misfiled.length} entry in duplicate-homes.json names a file that does not`);
    console.error("[purge-vocab] hold that term. Fix the entry — a wrong home would delete every copy.");
    for (const [slug, home] of misfiled) console.error(`    ${slug} -> ${home}`);
    process.exitCode = 1;
    return;
  }

  if (unresolved.length) {
    console.error(`[purge-vocab] ${unresolved.length} slug(s) live in two AREA files with no entry in`);
    console.error(`[purge-vocab] ${path.relative(repoRoot, homesPath)}. These are a classification call, not a`);
    console.error("[purge-vocab] defect — record a home and the evidence for it, then re-run.");
    for (const [slug, files] of unresolved) {
      console.error(`    ${slug}: ${files.map((f) => path.basename(f)).join(" | ")}`);
    }
    process.exitCode = 1;
    return;
  }

  const drops = new Map(); // file -> Set(slug)
  const note = (file, slug) => {
    if (!drops.has(file)) drops.set(file, new Set());
    drops.get(file).add(slug);
  };
  for (const [slug, , dropFiles] of [...areaWins, ...byDecision]) for (const f of dropFiles) note(f, slug);
  for (const [slug, dropFiles] of bothDrop) for (const f of dropFiles) note(f, slug);

  console.log(
    `[purge-vocab] ${areaWins.length} area-beats-event, ${byDecision.length} decided by hand, ${bothDrop.length} dropped-from-both — ${[...drops.values()].reduce((n, s) => n + s.size, 0)} term instance(s) across ${drops.size} file(s).`,
  );
  for (const [file, slugs] of [...drops].sort()) {
    console.log(`  ${file}: ${[...slugs].sort().join(", ")}`);
  }

  if (!opts.apply) {
    console.log("[purge-vocab] dry run — pass --apply to write. Nothing is denylisted: these concepts survive for Phase 3.");
    return;
  }
  for (const [file, slugs] of drops) {
    const doc = docs.find((d) => d.file === file);
    writeDoc(doc, doc.terms.filter((t) => !slugs.has(slugify(t.term))));
  }
  console.log(`[purge-vocab] rewrote ${drops.size} file(s).`);
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const docs = catalogFiles().map(readCatalogFile);
  const denylist = loadDenylist();
  const slugHomes = collectSlugHomes(docs);

  if (opts.report) return report(docs, denylist, slugHomes);
  if (opts.resolveDuplicates) return resolveDuplicates(docs, opts);
  if (opts.judgePrompt) return judgePrompt(resolveTarget(docs, opts), denylist, slugHomes);
  return applyVerdicts(resolveTarget(docs, opts), opts, denylist, slugHomes);
}

main();
