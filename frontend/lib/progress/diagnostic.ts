// First-run diagnostic sampler (plan 09 §4.3, D4). Samples a short, difficulty-
// mixed set spread across the target cluster×level's instructional areas, so the
// plan seeds a real baseline readiness (pacing starts honest) instead of a cold
// zero. Attempts are written with source:"diagnostic" by the hosting quiz modal.
//
// This reuses the bank's compose spine rather than a new sampler: composeTest
// already allocates by the exam blueprint (broad area spread) and balances the
// difficulty marginal, which is exactly a diagnostic's job. Client-only path
// (fetches the candidate files); safe to call from an event handler.

import { composeTest, type BankQuestion } from "@/lib/question-bank";
import type { Level } from "@/lib/deca";

/** Default diagnostic length — a ~15–20-question mixed set (plan §3, D4). */
export const DIAGNOSTIC_SIZE = 18;

/**
 * Build the diagnostic question set for a target cluster×level. `nonce` reseeds
 * the draw (pass a fresh random int from the caller — outside render). Returns an
 * empty array when the slice has no bank files (the UI then offers to skip).
 */
export async function sampleDiagnostic(
  cluster: string,
  level: Level,
  nonce: number,
  count: number = DIAGNOSTIC_SIZE,
): Promise<BankQuestion[]> {
  try {
    const composed = await composeTest(cluster, level, count, "balanced", nonce);
    return composed.questions;
  } catch {
    // BankUnavailableError (or a fetch failure) — no diagnostic for this slice.
    return [];
  }
}
