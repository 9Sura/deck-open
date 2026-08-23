// Read-only staleness report for the frontend's data artifacts.
//
// This script WRITES NOTHING. `npm run sync-data` is the only thing that writes.
// That separation is the point (issue #63): it used to run automatically on
// `predev` + `prebuild`, so merely starting the dev server rewrote data at whatever
// half-finished state it happened to be in and left thousands of lines of unintended
// JSON diff in the working tree. Writing is now deliberate; this checks whether it
// is owed.
//
// Two sources, and since #203 they ask DIFFERENT QUESTIONS:
//
//   bank  — public/question-bank/ is the single canonical tree (no backend mirror),
//           so there is no copy to verify. What can go stale are the two artifacts
//           DERIVED from it, which lib/ imports at build time:
//           lib/data/bank-manifest.json and lib/data/pi-inventory.json. Both are
//           recomputed here, in memory, using derive-bank-artifacts.mjs itself.
//
//           This arm is now FATAL, where the tree comparison it replaced was not.
//           The old leniency existed for a staging rule that no longer exists: the
//           backend ran ahead of the frontend while a cluster was open, so bank
//           drift was usually legitimate. With one tree, a stale artifact is never
//           legitimate — it means someone wrote the bank and skipped `derive-bank`,
//           and the app would serve a PI-coverage denominator describing a bank that
//           is no longer there.
//
//   vocab — backend/feat-vocab/data/ -> public/vocab/. Still a real copy, still no
//           staged-release rule, still fatal.
//
// Exit codes: 0 = everything current.  1 = stale bank artifacts, vocab drift, or a
// missing source tree.
//
// Node, no deps. Run via `npm run check-data`.

import { readdir, readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "..");
const repoRoot = path.resolve(frontend, "..");

// One implementation of the derivation, imported rather than reimplemented: a
// "current" verdict from a second copy of the builder would only ever be that
// copy's opinion.
const {
  buildPiInventory,
  serializeInventory,
  clusterDirs,
  BANK_DIR,
  MANIFEST_SRC,
  MANIFEST_LIB_DEST,
  PI_INVENTORY_DEST,
} = await import("./derive-bank-artifacts.mjs");

const SOURCES = [
  {
    name: "vocab",
    src: path.join(repoRoot, "backend", "feat-vocab", "data"),
    dest: path.join(frontend, "public", "vocab"),
    mirrors: [],
    fatal: true,
    note: "no staged-release rule here — run `npm run sync-vocab`",
    countQuestions: false,
  },
];

// relative path -> sha256 of the file's bytes, for every file under `root`.
async function hashTree(root) {
  const out = new Map();
  async function walk(dir) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) await walk(full);
      else if (entry.isFile()) {
        out.set(
          path.relative(root, full),
          createHash("sha256").update(await readFile(full)).digest("hex"),
        );
      }
    }
  }
  await walk(root);
  return out;
}

// Total questions across every cluster file, ignoring manifest.json. CLAUDE.md used
// to track this as a two-sided figure ("backend 11,466 · frontend 10,226") because
// there were two trees to disagree; there is one now, so it is simply the bank size.
async function countQuestions(root) {
  let total = 0;
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const dir = path.join(root, entry.name);
    for (const file of await readdir(dir)) {
      if (!file.endsWith(".json") || file === "manifest.json") continue;
      try {
        const parsed = JSON.parse(await readFile(path.join(dir, file), "utf8"));
        if (Array.isArray(parsed)) total += parsed.length;
      } catch {
        // An unreadable file is the sync's problem to report, not the count's.
      }
    }
  }
  return total;
}

async function compare(source) {
  if (!existsSync(source.src)) {
    console.error(`[check-data] ${source.name}: backend source not found at:\n  ${source.src}`);
    return { drifted: true, broken: true };
  }
  // Being BEHIND the backend is what the standing rule allows; being absent is
  // not — the frontend serves these files, so a missing tree is always fatal.
  if (!existsSync(source.dest)) {
    console.error(`[check-data] ${source.name}: never synced — ${path.relative(frontend, source.dest)}/ does not exist`);
    return { drifted: true, broken: true };
  }

  const [srcFiles, destFiles] = await Promise.all([hashTree(source.src), hashTree(source.dest)]);

  const changed = [];
  const missing = []; // in the backend, not yet in the frontend
  const extra = []; // in the frontend, no longer in the backend
  for (const [rel, hash] of srcFiles) {
    if (!destFiles.has(rel)) missing.push(rel);
    else if (destFiles.get(rel) !== hash) changed.push(rel);
  }
  for (const rel of destFiles.keys()) if (!srcFiles.has(rel)) extra.push(rel);

  for (const mirror of source.mirrors) {
    const rel = path.relative(frontend, mirror.to);
    if (!existsSync(mirror.to)) missing.push(rel);
    else {
      const [a, b] = await Promise.all([readFile(mirror.from), readFile(mirror.to)]);
      if (!a.equals(b)) changed.push(rel);
    }
  }

  const drifted = changed.length > 0 || missing.length > 0 || extra.length > 0;

  if (source.countQuestions) {
    const [backend, frontendCount] = await Promise.all([
      countQuestions(source.src),
      countQuestions(source.dest),
    ]);
    console.log(
      `[check-data] ${source.name}: backend ${backend} question(s) · frontend ${frontendCount}` +
        (backend === frontendCount ? "" : ` (gap ${backend - frontendCount})`),
    );
  }

  if (!drifted) {
    console.log(`[check-data] ${source.name}: in sync (${srcFiles.size} file(s))`);
    return { drifted: false, broken: false };
  }

  console.log(
    `[check-data] ${source.name}: OUT OF SYNC — ${changed.length} changed, ${missing.length} missing in frontend, ${extra.length} extra`,
  );
  for (const rel of [...changed].sort()) console.log(`[check-data]   ~ ${rel}`);
  for (const rel of [...missing].sort()) console.log(`[check-data]   + ${rel} (only in backend)`);
  // `cp -r` never prunes, so an extra file survives a sync — it has to go by hand.
  for (const rel of [...extra].sort()) console.log(`[check-data]   - ${rel} (only in frontend; sync will NOT remove it)`);
  console.log(`[check-data]   ${source.note}`);
  return { drifted: true, broken: false };
}

// Recompute what `npm run derive-bank` would write and diff it against the committed
// artifacts. Nothing is written.
async function checkBankArtifacts() {
  if (!existsSync(BANK_DIR)) {
    console.error(`[check-data] bank: question bank not found at:\n  ${BANK_DIR}`);
    return { drifted: true, broken: true };
  }

  const stale = [];

  const onDiskManifest = existsSync(MANIFEST_LIB_DEST) ? await readFile(MANIFEST_LIB_DEST) : null;
  const bankManifest = await readFile(MANIFEST_SRC);
  if (onDiskManifest === null || !onDiskManifest.equals(bankManifest)) {
    stale.push(path.relative(frontend, MANIFEST_LIB_DEST));
  }

  const { inventory, piTotal, areaTotal, fileCount } = await buildPiInventory(await clusterDirs());
  const expected = serializeInventory(inventory);
  const actual = existsSync(PI_INVENTORY_DEST) ? await readFile(PI_INVENTORY_DEST, "utf8") : null;
  if (actual !== expected) stale.push(path.relative(frontend, PI_INVENTORY_DEST));

  console.log(
    `[check-data] bank: ${await countQuestions(BANK_DIR)} question(s) in ${fileCount} file(s) · ` +
      `${piTotal} PI slot(s) across ${areaTotal} group(s)`,
  );

  if (stale.length === 0) {
    console.log("[check-data] bank: derived artifacts current");
    return { drifted: false, broken: false };
  }
  console.log(`[check-data] bank: STALE — ${stale.length} derived artifact(s) behind the bank`);
  for (const rel of stale.sort()) console.log(`[check-data]   ~ ${rel}`);
  console.log("[check-data]   run `npm run derive-bank` and commit the result");
  return { drifted: true, broken: false };
}

async function main() {
  let fail = false;
  let anyDrift = false;

  const bank = await checkBankArtifacts();
  if (bank.drifted) {
    anyDrift = true;
    fail = true; // no staged-release rule survives #203 — see the header
  }

  for (const source of SOURCES) {
    const result = await compare(source);
    if (result.drifted) {
      anyDrift = true;
      if (source.fatal || result.broken) fail = true;
    }
  }

  if (fail) {
    console.error("[check-data] FAIL — run `npm run sync-data` and commit the result.");
    process.exit(1);
  }
  if (anyDrift) {
    console.log("[check-data] OK — drift reported above is non-fatal.");
  } else {
    console.log("[check-data] OK — everything is current.");
  }
}

main().catch((err) => {
  console.error("[check-data] failed:", err);
  process.exit(1);
});
