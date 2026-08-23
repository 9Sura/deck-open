// Loader + browse helpers for the committed DECA vocab flashcard database.
//
// The manifest is imported at build time for cluster/event browsing. Individual
// event vocab files are fetched on demand from /vocab/... after sync-vocab copies
// backend/feat-vocab/data into public/.

import type { EventFormat } from "@/lib/deca";
import manifest from "@/lib/data/vocab-manifest.json";

export interface VocabTerm {
  term: string;
  slug: string;
  definition: string;
  whyItMatters: string;
  tags: string[];
  sourceRefs?: string[];
}

export interface VocabEventMeta {
  code: string;
  name: string;
  file: string;
  termCount: number;
  format: EventFormat | null;
  tags: string[];
}

export interface VocabClusterMeta {
  cluster: string;
  label: string;
  examName: string;
  eventCount: number;
  termCount: number;
  events: Record<string, VocabEventMeta>;
}

export interface VocabManifest {
  version: number;
  clusters: Record<string, VocabClusterMeta>;
}

export interface VocabEventFile {
  version: number;
  cluster: string;
  event: {
    code: string;
    name: string;
    format: EventFormat;
  };
  instructionalAreas: string[];
  sourceNotes: string[];
  terms: VocabTerm[];
}

const MANIFEST = manifest as VocabManifest;

export class VocabUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "VocabUnavailableError";
  }
}

export function vocabClusters(): string[] {
  return Object.keys(MANIFEST.clusters);
}

export function clusterHasVocab(cluster: string): boolean {
  return Boolean(MANIFEST.clusters[cluster]?.eventCount);
}

export function vocabClusterMeta(cluster: string): VocabClusterMeta | undefined {
  return MANIFEST.clusters[cluster];
}

export function eventsForCluster(cluster: string): VocabEventMeta[] {
  return Object.values(MANIFEST.clusters[cluster]?.events ?? {}).sort((a, b) =>
    a.code.localeCompare(b.code),
  );
}

export function vocabEventMeta(cluster: string, eventCode: string): VocabEventMeta | undefined {
  return MANIFEST.clusters[cluster]?.events[eventCode];
}

export function clusterTagSummary(cluster: string): string {
  const tags = [
    ...new Set(eventsForCluster(cluster).flatMap((event) => event.tags)),
  ].map(formatTag);

  if (tags.length === 0) return "Flashcards for event-ready DECA vocabulary.";
  const top = tags.slice(0, 4);
  const rest = tags.length - top.length;
  return rest > 0
    ? `Terms for ${top.join(", ")} and ${rest} more area${rest === 1 ? "" : "s"}.`
    : `Terms for ${top.join(", ")}.`;
}

export function formatTag(tag: string): string {
  return tag
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export async function loadVocabEvent(
  cluster: string,
  eventCode: string,
): Promise<{ meta: VocabEventMeta; vocab: VocabEventFile }> {
  const meta = vocabEventMeta(cluster, eventCode);
  if (!meta) {
    throw new VocabUnavailableError(`No vocab set exists for ${cluster} / ${eventCode}.`);
  }

  const res = await fetch(`/vocab/${cluster}/${meta.file}`);
  if (!res.ok) {
    throw new Error(`Failed to load ${meta.file} (HTTP ${res.status}).`);
  }

  return { meta, vocab: (await res.json()) as VocabEventFile };
}
