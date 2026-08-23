// Typed access to the build-time PI inventory (plan 08 phase 2 §5, D2).
//
// The inventory is the coverage *denominator*: the universe of performance
// indicators the bank covers per cluster × level × instructional area. It's a
// frontend-only artifact emitted by scripts/sync-question-bank.mjs (the backend
// manifest carries area counts but not PI lists), imported here at build time.
//
// Granularity is cluster × level × area (locked decision). A `level` of "all"
// unions the PI universes across every level for that cluster, so the dashboard
// filter can show a combined-levels coverage without losing per-level accuracy.
//
// Client-safe: pure data + helpers, no React.

import type { Level } from "@/lib/deca";
import inventoryJson from "@/lib/data/pi-inventory.json";

interface AreaMap {
  [area: string]: string[];
}
interface LevelEntry {
  areas: AreaMap;
}
interface ClusterEntry {
  levels: { [level: string]: LevelEntry };
}
export interface PiInventory {
  version: number;
  clusters: { [cluster: string]: ClusterEntry };
}

const INVENTORY = inventoryJson as PiInventory;

/** Canonical level scope for a lookup — a concrete level or every level unioned. */
export type LevelScope = Level | "all";

/** Distinct performance indicators the bank covers, across every cluster × level × area. */
export const PI_UNIVERSE_SIZE = (() => {
  const pis = new Set<string>();
  for (const cluster of Object.values(INVENTORY.clusters))
    for (const level of Object.values(cluster.levels))
      for (const list of Object.values(level.areas)) for (const pi of list) pis.add(pi);
  return pis.size;
})();

// A conservative rendering of the size above for marketing copy — rounded DOWN to
// the nearest fifty so the claim stays true as the inventory grows. Same rule as
// BANK_SIZE_LABEL in lib/question-bank.ts: state a floor, never an exact figure.
export const PI_COVERAGE_LABEL = `${Math.floor(PI_UNIVERSE_SIZE / 50) * 50}+`;

/** All levels the inventory carries for a cluster (empty if the cluster is absent). */
function levelsForCluster(cluster: string): string[] {
  const entry = INVENTORY.clusters[cluster];
  return entry ? Object.keys(entry.levels) : [];
}

// The two lookups below are pure over INVENTORY — a build-time import that never
// changes — so their answers are memoized per (cluster, [area,] level) key. The
// mastery engine calls piUniverse once per AREA per readiness() call, and
// `trajectory` replays readiness once per finished session, so an uncached
// lookup re-allocates and re-sorts the same handful of universes thousands of
// times over a long log. The key joins on NUL for the same reason mastery.ts's
// piKey does: areas contain spaces, cluster/level names don't contain NUL.
// The cached arrays are shared AND frozen — every caller only reads them (or
// copies into a Set), and freezing turns a future accidental mutation into a
// throw rather than a silently poisoned cache.
const KEY_SEP = "\u0000";
const areaCache = new Map<string, readonly string[]>();
const universeCache = new Map<string, readonly string[]>();

function memo(
  cache: Map<string, readonly string[]>,
  key: string,
  compute: () => string[],
): readonly string[] {
  const hit = cache.get(key);
  if (hit) return hit;
  const value = Object.freeze(compute());
  cache.set(key, value);
  return value;
}

/**
 * The distinct instructional areas covered for a cluster at the given level
 * scope, sorted. With `"all"`, the union across levels (the inventory is already
 * sorted, so a fresh sort keeps output stable). Empty when nothing matches.
 */
export function areasForCluster(
  cluster: string,
  level: LevelScope = "all",
): readonly string[] {
  return memo(areaCache, `${cluster}${KEY_SEP}${level}`, () => {
    const entry = INVENTORY.clusters[cluster];
    if (!entry) return [];
    const levels = level === "all" ? levelsForCluster(cluster) : [level];
    const areas = new Set<string>();
    for (const lv of levels) {
      const le = entry.levels[lv];
      if (!le) continue;
      for (const area of Object.keys(le.areas)) areas.add(area);
    }
    return [...areas].sort((a, b) => a.localeCompare(b));
  });
}

/**
 * The PI universe for a cluster × area at the given level scope, sorted +
 * de-duplicated. With `"all"`, the union of the PIs across every level (a PI can
 * appear at more than one level). Empty when the triple isn't in the inventory —
 * callers treat that as "no coverage denominator here" rather than an error.
 */
export function piUniverse(
  cluster: string,
  area: string,
  level: LevelScope = "all",
): readonly string[] {
  return memo(universeCache, `${cluster}${KEY_SEP}${area}${KEY_SEP}${level}`, () => {
    const entry = INVENTORY.clusters[cluster];
    if (!entry) return [];
    const levels = level === "all" ? levelsForCluster(cluster) : [level];
    const pis = new Set<string>();
    for (const lv of levels) {
      const le = entry.levels[lv];
      const list = le?.areas[area];
      if (!list) continue;
      for (const pi of list) pis.add(pi);
    }
    return [...pis].sort((a, b) => a.localeCompare(b));
  });
}

/** Total distinct PIs in the universe for a cluster × area × level scope. */
export function piUniverseSize(
  cluster: string,
  area: string,
  level: LevelScope = "all",
): number {
  return piUniverse(cluster, area, level).length;
}

/** Whether the inventory knows this exact PI in a cluster × area × level scope. */
export function inventoryHasPI(
  cluster: string,
  area: string,
  pi: string,
  level: LevelScope = "all",
): boolean {
  return piUniverse(cluster, area, level).includes(pi);
}
