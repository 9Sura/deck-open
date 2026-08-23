// The question resolver (plan 08 §7, phase 3 sub-plan §5, D2). The one new infra
// piece: the Attempt log is tag-only by design, but the Error Log and Review Lab must
// show real question text/options/explanation, so we re-hydrate BankQuestion by id.
//
// Groups requested ids by cluster×level, calls loadCandidates(cluster, level, "all")
// ONCE per slice (all sets + pool, de-duped by id), indexes every returned question by
// id, and memoizes the slice so repeated Error Log renders don't re-fetch. Unresolvable
// ids (the bank was re-authored and dropped that item) are simply absent from the map —
// callers treat that as "no longer in the bank" (never throw, never lose the log entry).
//
// Lives outside React (pure fetch logic, like question-bank.ts); the hook owns one
// instance per tab.

import { loadCandidates, type BankQuestion } from "@/lib/question-bank";
import type { Level } from "@/lib/deca";

export interface ResolveRequest {
  questionId: string;
  cluster: string;
  level: Level;
}

export interface QuestionResolver {
  /** Hydrate a batch of ids to bank questions. Returns only the hits (misses omitted). */
  resolve(ids: ResolveRequest[]): Promise<Map<string, BankQuestion>>;
  /** Sync lookup for an already-resolved id (cache hit); undefined if not yet fetched or absent. */
  get(questionId: string): BankQuestion | undefined;
}

const sliceKey = (cluster: string, level: Level) => `${cluster}|${level}`;

export function createResolver(): QuestionResolver {
  // Per-slice fetch promises, memoized so a slice is fetched at most once per tab.
  const slices = new Map<string, Promise<Map<string, BankQuestion>>>();
  // Flattened id → question index across every resolved slice (for the sync `get`).
  const index = new Map<string, BankQuestion>();

  function loadSlice(cluster: string, level: Level): Promise<Map<string, BankQuestion>> {
    const key = sliceKey(cluster, level);
    let p = slices.get(key);
    if (!p) {
      p = loadCandidates(cluster, level, "all")
        .then((questions) => {
          const map = new Map<string, BankQuestion>();
          for (const q of questions) {
            map.set(q.id, q);
            index.set(q.id, q);
          }
          return map;
        })
        .catch(() => {
          // A failed slice fetch resolves to empty (ids drop, counted as unresolved) and
          // is NOT cached, so a later render can retry it.
          slices.delete(key);
          return new Map<string, BankQuestion>();
        });
      slices.set(key, p);
    }
    return p;
  }

  return {
    async resolve(ids) {
      // One fetch per distinct cluster×level, in parallel.
      const needed = new Map<string, { cluster: string; level: Level }>();
      for (const { cluster, level } of ids) {
        needed.set(sliceKey(cluster, level), { cluster, level });
      }
      await Promise.all([...needed.values()].map(({ cluster, level }) => loadSlice(cluster, level)));

      const out = new Map<string, BankQuestion>();
      for (const { questionId } of ids) {
        const q = index.get(questionId);
        if (q) out.set(questionId, q);
      }
      return out;
    },
    get(questionId) {
      return index.get(questionId);
    },
  };
}
