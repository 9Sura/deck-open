// The guest (non-logging) ProgressStore (plan 09 D10 — account-only logging).
//
// This REVERSES plan-08's guest-local-first design. A signed-out user may still
// USE focus quizzes and the rest of Question Bank, but nothing they do is
// recorded — logging (and therefore the study plan, /progress, /review) is an
// account-only feature. So the guest store drops every write and reads empty,
// behind the SAME ProgressStore seam a signed-in SyncingStore satisfies. The old
// guest→account migration is gone (plan 09 D10): there is no guest log to union.
//
// SSR-safe by construction — no IndexedDB, no network, no state.

import type { ProgressStore } from "@/lib/progress/store";
import type { Attempt, Session } from "@/lib/progress/types";

export class NullStore implements ProgressStore {
  async recordAttempts(attempts: Attempt[]): Promise<void> {
    void attempts;
  }
  async startSession(s: Session): Promise<void> {
    void s;
  }
  async endSession(id: string, patch: Partial<Session>): Promise<void> {
    void id;
    void patch;
  }
  async getAttempts(): Promise<Attempt[]> {
    return [];
  }
  async getSessions(): Promise<Session[]> {
    return [];
  }
  async clear(): Promise<void> {}
  async exportAll(): Promise<{ attempts: Attempt[]; sessions: Session[] }> {
    return { attempts: [], sessions: [] };
  }
  async importAll(data: { attempts: Attempt[]; sessions: Session[] }): Promise<void> {
    void data;
  }
}
