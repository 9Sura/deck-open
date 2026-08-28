// Deterministic vocab gate — layer 1 of the three-layer difficulty bar in
// vocab plan 01 §3. No model call, no network, no repair: a term either passes
// every rule or it is rejected with a reason.
//
// Rules (each maps to a bullet in plan 01 §3):
//   difficulty     `difficulty` is exactly "medium" or "hard". "easy" is not a
//                  filterable tier, it is a validation error.
//   denylist       the slug is not in catalog/denylist.txt (seeded from the
//                  Phase 1 purge, so easy vocabulary cannot re-enter later).
//   definition     `definition` is >= 60 characters.
//   restates       the definition does not open by restating the term.
//   why            `whyItMatters` is non-empty.
//   sources        `sourceRefs` is non-empty (term-level, or inherited from the
//                  file-level `sourceRefs`).
//   duplicate      the slug appears in exactly one catalog file, and once in it.
//   mix            >= 50% of a file's terms are "hard".
//
// Slugs are DERIVED, not stored — see lib/slug.mjs. That is the only reason the
// cross-file duplicate rule is well-defined.
//
// Usage:
//   node tools/vocab_gate.mjs                      gate every catalog file
//   node tools/vocab_gate.mjs --area economics     gate one area file
//   node tools/vocab_gate.mjs --event ACT          gate one event flavor file
//   node tools/vocab_gate.mjs --file <path>        gate an arbitrary catalog file
//   node tools/vocab_gate.mjs --skip-mix           skip the >=50% hard rule
//   node tools/vocab_gate.mjs --json               machine-readable report
//
// Exit code is 1 if anything failed, 0 otherwise.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { slugify } from "../lib/slug.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
export const featRoot = path.resolve(here, "..");
export const catalogRoot = path.join(featRoot, "catalog");
export const denylistPath = path.join(catalogRoot, "denylist.txt");

export const DIFFICULTIES = ["medium", "hard"];
export const MIN_DEFINITION_CHARS = 60;
export const MIN_HARD_SHARE = 0.5;

const LEADING_STOPWORDS = new Set(["a", "an", "the"]);

export function loadDenylist() {
  if (!fs.existsSync(denylistPath)) return new Set();
  return new Set(
    fs
      .readFileSync(denylistPath, "utf8")
      .split("\n")
      .map((line) => line.replace(/#.*$/, "").trim())
      .filter(Boolean)
      .map(slugify),
  );
}

/** Every catalog file on disk, as { file, kind, name, path }. */
export function catalogFiles() {
  const out = [];
  for (const kind of ["areas", "events"]) {
    const dir = path.join(catalogRoot, kind);
    if (!fs.existsSync(dir)) continue;
    for (const file of fs.readdirSync(dir).sort()) {
      if (!file.endsWith(".json")) continue;
      out.push({
        kind,
        name: file.replace(/\.json$/, ""),
        file: `catalog/${kind}/${file}`,
        path: path.join(dir, file),
      });
    }
  }
  return out;
}

export function readCatalogFile(entry) {
  const parsed = JSON.parse(fs.readFileSync(entry.path, "utf8"));
  return { ...entry, ...parsed, terms: parsed.terms ?? [] };
}

/**
 * slug -> [file, ...] across the WHOLE catalog. The duplicate rule needs every
 * file, not just the one being gated, so this is computed once and passed in.
 */
export function collectSlugHomes(files = catalogFiles().map(readCatalogFile)) {
  const homes = new Map();
  for (const doc of files) {
    for (const term of doc.terms) {
      const slug = slugify(term.term ?? "");
      if (!slug) continue;
      if (!homes.has(slug)) homes.set(slug, []);
      homes.get(slug).push(doc.file);
    }
  }
  return homes;
}

/** True when the definition opens by restating the term ("Profit is the ..."). */
export function definitionRestatesTerm(term, definition) {
  const termWords = String(term).toLowerCase().match(/[a-z0-9]+/g) ?? [];
  const defWords = String(definition).toLowerCase().match(/[a-z0-9]+/g) ?? [];
  if (!termWords.length || !defWords.length) return false;
  let i = 0;
  while (i < defWords.length && LEADING_STOPWORDS.has(defWords[i])) i += 1;
  return termWords.every((word, k) => defWords[i + k] === word);
}

/**
 * Gate one file's worth of terms. `slugHomes` and `denylist` come from the
 * whole catalog so cross-file rules work; `fileLabel` is what a home is
 * compared against, so an ingest can gate a batch as if it were already in the
 * file it is destined for.
 */
export function gateTerms(terms, { fileLabel, denylist, slugHomes, skipMix = false } = {}) {
  const failures = [];
  const passed = [];
  const seenInFile = new Set();

  for (const [index, term] of terms.entries()) {
    const label = term?.term ?? `#${index}`;
    const slug = slugify(term?.term ?? "");
    const reasons = [];

    if (!slug) reasons.push("term: empty or unslugifiable");

    if (!DIFFICULTIES.includes(term?.difficulty)) {
      reasons.push(`difficulty: ${JSON.stringify(term?.difficulty)} is not "medium" or "hard"`);
    }

    if (slug && denylist?.has(slug)) reasons.push("denylist: slug was purged and may not re-enter");

    const definition = String(term?.definition ?? "");
    if (definition.trim().length < MIN_DEFINITION_CHARS) {
      reasons.push(`definition: ${definition.trim().length} chars, minimum is ${MIN_DEFINITION_CHARS}`);
    }
    if (definition && definitionRestatesTerm(term?.term, definition)) {
      reasons.push("restates: definition opens by repeating the term");
    }

    if (!String(term?.whyItMatters ?? "").trim()) reasons.push("why: whyItMatters is empty");

    const sourceRefs = term?.sourceRefs ?? [];
    if (!Array.isArray(sourceRefs) || sourceRefs.length === 0) {
      reasons.push("sources: sourceRefs is empty");
    }

    if (slug) {
      if (seenInFile.has(slug)) {
        reasons.push("duplicate: slug appears twice in this file");
      } else {
        seenInFile.add(slug);
      }
      const homes = (slugHomes?.get(slug) ?? []).filter((home) => home !== fileLabel);
      if (homes.length) {
        reasons.push(`duplicate: slug also lives in ${[...new Set(homes)].join(", ")}`);
      }
    }

    if (reasons.length) failures.push({ term: label, slug, reasons });
    else passed.push(term);
  }

  const fileFailures = [];
  if (!skipMix && terms.length) {
    const hard = terms.filter((t) => t?.difficulty === "hard").length;
    const share = hard / terms.length;
    if (share < MIN_HARD_SHARE) {
      fileFailures.push(
        `mix: ${hard}/${terms.length} hard (${Math.round(share * 100)}%), minimum is ${Math.round(MIN_HARD_SHARE * 100)}%`,
      );
    }
  }

  return { passed, failures, fileFailures, ok: failures.length === 0 && fileFailures.length === 0 };
}

function parseArgs(argv) {
  const opts = { json: false, skipMix: false, targets: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--json") opts.json = true;
    else if (arg === "--skip-mix") opts.skipMix = true;
    else if (arg === "--area") opts.targets.push({ kind: "areas", name: argv[++i] });
    else if (arg === "--event") opts.targets.push({ kind: "events", name: argv[++i] });
    else if (arg === "--file") opts.targets.push({ file: argv[++i] });
    else {
      console.error(`[vocab-gate] unknown argument: ${arg}`);
      process.exit(2);
    }
  }
  return opts;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const all = catalogFiles();
  const slugHomes = collectSlugHomes(all.map(readCatalogFile));
  const denylist = loadDenylist();

  let selected = all;
  if (opts.targets.length) {
    selected = opts.targets.map((target) => {
      if (target.file) {
        const abs = path.resolve(target.file);
        const match = all.find((entry) => entry.path === abs);
        if (match) return match;
        return { kind: "file", name: path.basename(abs, ".json"), file: target.file, path: abs };
      }
      const match = all.find((entry) => entry.kind === target.kind && entry.name === target.name);
      if (!match) {
        console.error(`[vocab-gate] no ${target.kind} catalog file named ${target.name}`);
        process.exit(2);
      }
      return match;
    });
  }

  const report = [];
  for (const entry of selected) {
    const doc = readCatalogFile(entry);
    const withSources = doc.terms.map((term) => ({
      ...term,
      sourceRefs: term.sourceRefs?.length ? term.sourceRefs : (doc.sourceRefs ?? []),
    }));
    const result = gateTerms(withSources, {
      fileLabel: doc.file,
      denylist,
      slugHomes,
      skipMix: opts.skipMix,
    });
    report.push({ file: doc.file, terms: doc.terms.length, ...result, passed: result.passed.length });
  }

  const failed = report.filter((r) => !r.ok);

  if (opts.json) {
    console.log(JSON.stringify({ files: report, ok: failed.length === 0 }, null, 2));
  } else {
    for (const r of report) {
      const head = `${r.ok ? "PASS" : "FAIL"}  ${r.file}  ${r.passed}/${r.terms} term(s)`;
      console.log(head);
      for (const line of r.fileFailures) console.log(`        ${line}`);
      for (const f of r.failures) {
        console.log(`      - ${f.term}`);
        for (const reason of f.reasons) console.log(`          ${reason}`);
      }
    }
    const terms = report.reduce((n, r) => n + r.terms, 0);
    const bad = report.reduce((n, r) => n + r.failures.length, 0);
    console.log(
      `[vocab-gate] ${report.length} file(s), ${terms} term(s), ${bad} rejected, ${failed.length} file(s) failing.`,
    );
  }

  // process.exit() would truncate the report above when stdout is a pipe — the
  // --json report is comfortably past the 64 KB the runtime flushes eagerly.
  process.exitCode = failed.length ? 1 : 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
