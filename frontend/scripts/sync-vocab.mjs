// Sync the backend vocab database into the frontend.
//
// Copies backend/feat-vocab/data/
//   -> frontend/public/vocab/              (served verbatim at /vocab/...)
// and builds frontend/lib/data/vocab-manifest.json so the UI can import counts
// and event metadata at build time without loading every flashcard file.
//
// Node, no deps. Run via `npm run sync-vocab` (or `npm run sync-data`). No longer
// wired into `predev`/`prebuild` — see the header of sync-question-bank.mjs and
// issue #63. `npm run check-data` reports, read-only, whether a sync is owed.

import { cp, mkdir, copyFile, readdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, "..");
const repoRoot = path.resolve(frontend, "..");

const SRC = path.join(repoRoot, "backend", "feat-vocab", "data");
const PUBLIC_DEST = path.join(frontend, "public", "vocab");
const MANIFEST_LIB_DEST = path.join(frontend, "lib", "data", "vocab-manifest.json");

async function readJson(file) {
  return JSON.parse(await readFile(file, "utf8"));
}

async function main() {
  if (!existsSync(SRC)) {
    console.error(`[sync-vocab] backend vocab data not found at:\n  ${SRC}`);
    process.exit(1);
  }

  await mkdir(PUBLIC_DEST, { recursive: true });
  await cp(SRC, PUBLIC_DEST, { recursive: true });

  const clusterDirs = (await readdir(SRC, { withFileTypes: true }))
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .sort();

  const clusters = {};
  let eventCount = 0;
  let termCount = 0;

  for (const cluster of clusterDirs) {
    const manifestPath = path.join(SRC, cluster, "manifest.json");
    if (!existsSync(manifestPath)) continue;

    const clusterManifest = await readJson(manifestPath);
    const events = {};

    for (const event of clusterManifest.events ?? []) {
      const vocabPath = path.join(SRC, cluster, event.file);
      const vocab = existsSync(vocabPath) ? await readJson(vocabPath) : null;
      const tags = vocab
        ? [...new Set((vocab.terms ?? []).flatMap((term) => term.tags ?? []))].sort()
        : [];

      events[event.code] = {
        code: event.code,
        name: event.name,
        file: event.file,
        termCount: event.termCount,
        format: vocab?.event?.format ?? null,
        tags,
      };
      eventCount += 1;
      termCount += event.termCount ?? 0;
    }

    clusters[cluster] = {
      cluster,
      label: clusterManifest.label,
      examName: clusterManifest.examName,
      eventCount: Object.keys(events).length,
      termCount: Object.values(events).reduce((sum, event) => sum + event.termCount, 0),
      events,
    };

    await copyFile(manifestPath, path.join(PUBLIC_DEST, cluster, "manifest.json"));
  }

  await mkdir(path.dirname(MANIFEST_LIB_DEST), { recursive: true });
  await writeFile(
    MANIFEST_LIB_DEST,
    `${JSON.stringify({ version: 1, clusters }, null, 2)}\n`,
    "utf8",
  );

  console.log(
    `[sync-vocab] synced ${termCount} term(s) across ${eventCount} event(s) and ${Object.keys(clusters).length} cluster(s)`,
  );
  console.log(`[sync-vocab]   -> ${path.relative(frontend, PUBLIC_DEST)}/`);
  console.log(`[sync-vocab]   -> ${path.relative(frontend, MANIFEST_LIB_DEST)}`);
}

main().catch((err) => {
  console.error("[sync-vocab] failed:", err);
  process.exit(1);
});
