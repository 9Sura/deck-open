// A straight ProgressStore implementation over Supabase (sub-plan §5). Every
// method scopes to the current user_id (RLS enforces it server-side; we set it
// on writes too). camelCase (app) <-> snake_case (Postgres) is mapped at this
// boundary via the row helpers; epoch-ms timestamps <-> timestamptz ISO strings.
//
// In the SyncingStore this is the REMOTE half: reads here are used only for the
// initial pull / refresh (the hot read path is served from IndexedDB), and
// writes are driven by the outbox flusher. Every write is upsert/patch-by-id, so
// replays are idempotent. Methods throw on error so the flusher can back off.

import type { SupabaseClient } from "@supabase/supabase-js";
import type { ProgressStore } from "@/lib/progress/store";
import type {
  Attempt,
  AttemptFilter,
  Choice,
  Session,
  SessionFilter,
} from "@/lib/progress/types";
import type { Level } from "@/lib/deca";
import type { Difficulty } from "@/lib/question-bank";

const ATTEMPTS = "attempts";
const SESSIONS = "sessions";
const CHUNK = 500; // rows per upsert batch (import/migration)
const PAGE = 1000; // rows REQUESTED per read page (the server may return fewer)

// PostgREST caps an un-ranged `select` at 1000 rows, silently truncating larger
// result sets. Page through with `.range()` so a device with >1000 attempts pulls
// its full history. `make` must apply a deterministic order (by the unique id) so
// pages don't skip or repeat rows; a query builder can't be reused after `await`,
// so we rebuild the filtered query each call.
//
// Advance by what the server ACTUALLY returned and stop only on an empty page
// (issue #111). `PAGE` is our request size, not a fact about the server: PostgREST's
// `db-max-rows` is a server setting, and if it is ever tightened below `PAGE` then a
// full first page comes back short — a "short page ⇒ we're done" test would break the
// loop after one round trip and silently truncate the pull. Costs one extra request
// when the total is an exact multiple of the page size, and is correct at every cap.
// (`Content-Range` would avoid that trip, but `make` hands back the parsed body.)
async function fetchAll<T>(
  make: (from: number, to: number) => PromiseLike<{ data: T[] | null; error: unknown }>,
): Promise<T[]> {
  const out: T[] = [];
  for (let from = 0; ; ) {
    const { data, error } = await make(from, from + PAGE - 1);
    if (error) throw error;
    const rows = data ?? [];
    if (rows.length === 0) break;
    out.push(...rows);
    from += rows.length;
  }
  return out;
}

// ---- row mapping -----------------------------------------------------------

interface AttemptRow {
  id: string;
  user_id: string;
  ts: string;
  question_id: string;
  cluster: string;
  level: string;
  instructional_area: string;
  performance_indicator: string;
  difficulty: string;
  chosen: string | null;
  correct: boolean;
  elapsed_ms: number;
  source: string;
  session_id: string;
}

interface SessionRow {
  id: string;
  user_id: string;
  ts: string;
  ended_ts: string | null;
  cluster: string;
  level: string;
  source: string;
  total: number;
  answered: number;
  correct: number;
  elapsed_ms: number;
}

const iso = (ms: number) => new Date(ms).toISOString();

function attemptToRow(a: Attempt, userId: string): AttemptRow {
  return {
    id: a.id,
    user_id: userId,
    ts: iso(a.ts),
    question_id: a.questionId,
    cluster: a.cluster,
    level: a.level,
    instructional_area: a.instructionalArea,
    performance_indicator: a.performanceIndicator,
    difficulty: a.difficulty,
    chosen: a.chosen,
    correct: a.correct,
    elapsed_ms: a.elapsedMs,
    source: a.source,
    session_id: a.sessionId,
  };
}

function rowToAttempt(r: AttemptRow): Attempt {
  return {
    id: r.id,
    ts: Date.parse(r.ts),
    questionId: r.question_id,
    cluster: r.cluster,
    level: r.level as Level,
    instructionalArea: r.instructional_area,
    performanceIndicator: r.performance_indicator,
    difficulty: r.difficulty as Difficulty,
    chosen: r.chosen as Choice | null,
    correct: r.correct,
    elapsedMs: r.elapsed_ms,
    source: r.source as Attempt["source"],
    sessionId: r.session_id,
  };
}

function sessionToRow(s: Session, userId: string): SessionRow {
  return {
    id: s.id,
    user_id: userId,
    ts: iso(s.ts),
    ended_ts: s.endedTs === null ? null : iso(s.endedTs),
    cluster: s.cluster,
    level: s.level,
    source: s.source,
    total: s.total,
    answered: s.answered,
    correct: s.correct,
    elapsed_ms: s.elapsedMs,
  };
}

function rowToSession(r: SessionRow): Session {
  return {
    id: r.id,
    ts: Date.parse(r.ts),
    endedTs: r.ended_ts === null ? null : Date.parse(r.ended_ts),
    cluster: r.cluster,
    level: r.level as Level,
    source: r.source as Session["source"],
    total: r.total,
    answered: r.answered,
    correct: r.correct,
    elapsedMs: r.elapsed_ms,
  };
}

/** Map a camelCase session patch to the snake-case columns it touches. */
function sessionPatchToRow(patch: Partial<Session>): Partial<SessionRow> {
  const row: Partial<SessionRow> = {};
  if (patch.ts !== undefined) row.ts = iso(patch.ts);
  if (patch.endedTs !== undefined)
    row.ended_ts = patch.endedTs === null ? null : iso(patch.endedTs);
  if (patch.total !== undefined) row.total = patch.total;
  if (patch.answered !== undefined) row.answered = patch.answered;
  if (patch.correct !== undefined) row.correct = patch.correct;
  if (patch.elapsedMs !== undefined) row.elapsed_ms = patch.elapsedMs;
  if (patch.cluster !== undefined) row.cluster = patch.cluster;
  if (patch.level !== undefined) row.level = patch.level;
  if (patch.source !== undefined) row.source = patch.source;
  return row;
}

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

// ---- store -----------------------------------------------------------------

export class SupabaseStore implements ProgressStore {
  constructor(
    private readonly sb: SupabaseClient,
    private readonly userId: string,
  ) {}

  async recordAttempts(a: Attempt[]): Promise<void> {
    if (a.length === 0) return;
    const rows = a.map((x) => attemptToRow(x, this.userId));
    // Append-only: ignore rows already present (a replay), never rewrite them.
    const { error } = await this.sb
      .from(ATTEMPTS)
      .upsert(rows, { onConflict: "id", ignoreDuplicates: true });
    if (error) throw error;
  }

  async startSession(s: Session): Promise<void> {
    const { error } = await this.sb
      .from(SESSIONS)
      .upsert(sessionToRow(s, this.userId), { onConflict: "id" });
    if (error) throw error;
  }

  async endSession(id: string, patch: Partial<Session>): Promise<void> {
    // Upsert (not .update) so a finished session still lands even when its
    // start row never reached the server — the start op was dropped/dead-lettered
    // by the outbox, or a partial reset landed between start and end. A plain
    // `.update().eq("id", id)` matches ZERO rows *without erroring* in that case,
    // silently losing the end patch so the session stays endedTs=null server-side
    // and on every other device (issue #11). The SyncingStore hands us the FULL
    // finalized session here (not just the delta), so the row satisfies every
    // NOT NULL column on insert; on id-conflict it patches the existing row.
    // Idempotent — safe for the outbox to replay.
    const row: Partial<SessionRow> = {
      ...sessionPatchToRow(patch),
      id,
      user_id: this.userId,
    };
    const { error } = await this.sb
      .from(SESSIONS)
      .upsert(row, { onConflict: "id" });
    if (error) throw error;
  }

  async getAttempts(filter?: AttemptFilter): Promise<Attempt[]> {
    const rows = await fetchAll<AttemptRow>((from, to) => {
      let q = this.sb.from(ATTEMPTS).select("*").eq("user_id", this.userId);
      if (filter?.cluster !== undefined) q = q.eq("cluster", filter.cluster);
      if (filter?.level !== undefined) q = q.eq("level", filter.level);
      if (filter?.performanceIndicator !== undefined)
        q = q.eq("performance_indicator", filter.performanceIndicator);
      if (filter?.source !== undefined) q = q.eq("source", filter.source);
      if (filter?.since !== undefined) q = q.gte("ts", iso(filter.since));
      return q.order("id", { ascending: true }).range(from, to);
    });
    return rows.map(rowToAttempt);
  }

  async getSessions(filter?: SessionFilter): Promise<Session[]> {
    const rows = await fetchAll<SessionRow>((from, to) => {
      let q = this.sb.from(SESSIONS).select("*").eq("user_id", this.userId);
      if (filter?.cluster !== undefined) q = q.eq("cluster", filter.cluster);
      if (filter?.level !== undefined) q = q.eq("level", filter.level);
      if (filter?.since !== undefined) q = q.gte("ts", iso(filter.since));
      return q.order("id", { ascending: true }).range(from, to);
    });
    return rows.map(rowToSession);
  }

  async clear(): Promise<void> {
    // The remote reset (D12): drop this user's rows. RLS also scopes it.
    const a = await this.sb.from(ATTEMPTS).delete().eq("user_id", this.userId);
    if (a.error) throw a.error;
    const s = await this.sb.from(SESSIONS).delete().eq("user_id", this.userId);
    if (s.error) throw s.error;
  }

  async exportAll(): Promise<{ attempts: Attempt[]; sessions: Session[] }> {
    const [attempts, sessions] = await Promise.all([
      this.getAttempts(),
      this.getSessions(),
    ]);
    return { attempts, sessions };
  }

  async importAll(data: {
    attempts: Attempt[];
    sessions: Session[];
  }): Promise<void> {
    // Chunked upsert-by-id — the migration primitive (push local up). Attempts
    // ignore duplicates (append-only); sessions merge (upsert-latest).
    for (const batch of chunk(data.attempts, CHUNK)) {
      const { error } = await this.sb
        .from(ATTEMPTS)
        .upsert(
          batch.map((x) => attemptToRow(x, this.userId)),
          { onConflict: "id", ignoreDuplicates: true },
        );
      if (error) throw error;
    }
    for (const batch of chunk(data.sessions, CHUNK)) {
      const { error } = await this.sb
        .from(SESSIONS)
        .upsert(
          batch.map((x) => sessionToRow(x, this.userId)),
          { onConflict: "id" },
        );
      if (error) throw error;
    }
  }
}
