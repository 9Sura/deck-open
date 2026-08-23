// The ProgressStore implementation over raw IndexedDB (sub-plan §4/§6). No
// runtime dependency. NOT throwaway — it ships as guest mode and, in Phase 4b,
// becomes the optimistic/offline cache in front of the Supabase store.
//
// Phase 4 additions:
// - Per-user DB namespacing (D7): the constructor takes a DB name, so a guest
//   uses "deck-progress" and a signed-in user "deck-progress-<uid>". Each name
//   opens an isolated database; sign-out detaches (never wipes).
// - An `outbox` object store (DB v2) holding pending remote mutations for the
//   SyncingStore. `openDb`/`tx` are exported so the Outbox shares one schema
//   definition and one connection per DB name.
//
// SSR-safe: every method short-circuits when `indexedDB` is undefined (the
// server, and any non-browser context) — reads return empty, writes no-op.

import type { ProgressStore } from "@/lib/progress/store";
import type {
  Attempt,
  AttemptFilter,
  Session,
  SessionFilter,
} from "@/lib/progress/types";

/** The guest (un-suffixed) database name; signed-in users pass "deck-progress-<uid>". */
export const GUEST_DB_NAME = "deck-progress";
const DB_VERSION = 2; // v2 adds the `outbox` store
const ATTEMPTS = "attempts";
const SESSIONS = "sessions";
export const OUTBOX = "outbox";

const hasIDB = () => typeof indexedDB !== "undefined";

/** Wrap an IDBRequest as a promise. */
export function reqToPromise<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// One open connection per DB name (a guest DB + one per signed-in user). Keyed
// so switching accounts doesn't collide on a single module-global promise.
const dbPromises = new Map<string, Promise<IDBDatabase>>();

/** Drop a memoized connection, but only if it's still the one we cached (issue #9).
 *  The identity check matters: `deleteDatabase` (or a retry that already reopened)
 *  may have replaced the entry, and evicting blindly would throw away a live handle. */
function evict(dbName: string, p: Promise<IDBDatabase>): void {
  if (dbPromises.get(dbName) === p) dbPromises.delete(dbName);
}

/** Open (and, on first run / upgrade, build) a database by name. Memoized per name.
 *
 *  The memo is only ever allowed to hold a connection that's still usable (issue #9):
 *  a FAILED open is evicted so the next call retries instead of replaying the same
 *  rejection for the rest of the session, and a connection the browser later closes
 *  out from under us is evicted too (a resolved-but-dead handle poisons every `tx`
 *  with InvalidStateError just as thoroughly as a rejected promise). */
export function openDb(dbName: string): Promise<IDBDatabase> {
  const existing = dbPromises.get(dbName);
  if (existing) return existing;
  const p = new Promise<IDBDatabase>((resolve, reject) => {
    const req = indexedDB.open(dbName, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      // Guarded creates → correct for a fresh DB and for a v1→v2 upgrade
      // (attempts/sessions already exist; only `outbox` is added).
      if (!db.objectStoreNames.contains(ATTEMPTS)) {
        const attempts = db.createObjectStore(ATTEMPTS, { keyPath: "id" });
        attempts.createIndex("by_cluster_level", ["cluster", "level"], {
          unique: false,
        });
        attempts.createIndex("by_pi", "performanceIndicator", { unique: false });
        attempts.createIndex("by_ts", "ts", { unique: false });
        attempts.createIndex("by_session", "sessionId", { unique: false });
      }
      if (!db.objectStoreNames.contains(SESSIONS)) {
        const sessions = db.createObjectStore(SESSIONS, { keyPath: "id" });
        sessions.createIndex("by_ts", "ts", { unique: false });
      }
      if (!db.objectStoreNames.contains(OUTBOX)) {
        // Ordered FIFO: autoIncrement `seq` is the key, so a cursor/getAll
        // returns pending mutations in enqueue order.
        db.createObjectStore(OUTBOX, { keyPath: "seq", autoIncrement: true });
      }
    };
    req.onsuccess = () => {
      const db = req.result;
      // Another tab wants to upgrade or delete this DB: close ours so it isn't
      // blocked, and evict so our next call reopens. Without this, a second open
      // tab silently blocks `deleteDatabase` (which resolves on `onblocked` and
      // reports success) and the account wipe never happens.
      db.onversionchange = () => {
        db.close();
        evict(dbName, p);
      };
      // The browser force-closed the connection (storage pressure, site data
      // cleared). The handle is dead but the promise stays resolved, so evict.
      db.onclose = () => evict(dbName, p);
      resolve(db);
    };
    req.onerror = () => reject(req.error);
  });
  dbPromises.set(dbName, p);
  // Evict a failed open (transient quota / blocked storage / a synchronous throw
  // from `indexedDB.open` in private mode) so the next caller gets a fresh try.
  // `.catch` also marks `p` handled — callers still see their own rejection.
  p.catch(() => evict(dbName, p));
  return p;
}

/** Delete an entire database by name (account deletion / hard local wipe, D12).
 *  Drops the memoized connection first so the delete isn't blocked by an open
 *  handle, then resolves even if the browser reports `blocked` (best-effort). */
export async function deleteDatabase(dbName: string): Promise<void> {
  if (!hasIDB()) return;
  const open = dbPromises.get(dbName);
  dbPromises.delete(dbName);
  if (open) {
    try {
      (await open).close();
    } catch {
      /* already closing — fall through to the delete */
    }
  }
  await new Promise<void>((resolve) => {
    const req = indexedDB.deleteDatabase(dbName);
    req.onsuccess = () => resolve();
    req.onerror = () => resolve();
    req.onblocked = () => resolve();
  });
}

/** Run `fn` inside a transaction on one store and resolve when it completes. */
export async function tx<T>(
  dbName: string,
  store: string,
  mode: IDBTransactionMode,
  fn: (s: IDBObjectStore) => Promise<T> | T,
): Promise<T> {
  const db = await openDb(dbName);
  return new Promise<T>((resolve, reject) => {
    const transaction = db.transaction(store, mode);
    const os = transaction.objectStore(store);
    let result: T;
    Promise.resolve(fn(os)).then((r) => {
      result = r;
    }, reject);
    transaction.oncomplete = () => resolve(result);
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error);
  });
}

/** Collect every row of a store via cursor (used for filtered/scan reads). */
function scan<T>(os: IDBObjectStore, predicate?: (row: T) => boolean): Promise<T[]> {
  return new Promise((resolve, reject) => {
    const out: T[] = [];
    const req = os.openCursor();
    req.onsuccess = () => {
      const cursor = req.result;
      if (!cursor) {
        resolve(out);
        return;
      }
      const row = cursor.value as T;
      if (!predicate || predicate(row)) out.push(row);
      cursor.continue();
    };
    req.onerror = () => reject(req.error);
  });
}

export class IndexedDbStore implements ProgressStore {
  constructor(private readonly dbName: string = GUEST_DB_NAME) {}

  async recordAttempts(attempts: Attempt[]): Promise<void> {
    if (!hasIDB() || attempts.length === 0) return;
    await tx(this.dbName, ATTEMPTS, "readwrite", (os) => {
      // put (not add) → idempotent by id; replaying an attempt is a no-op.
      for (const a of attempts) os.put(a);
    });
  }

  async startSession(s: Session): Promise<void> {
    if (!hasIDB()) return;
    await tx(this.dbName, SESSIONS, "readwrite", (os) => {
      os.put(s); // upsert — calling again with the same id is harmless
    });
  }

  async endSession(id: string, patch: Partial<Session>): Promise<void> {
    if (!hasIDB()) return;
    await tx(this.dbName, SESSIONS, "readwrite", async (os) => {
      const existing = (await reqToPromise(os.get(id))) as Session | undefined;
      if (!existing) return; // never started (or already gone) — nothing to patch
      os.put({ ...existing, ...patch, id });
    });
  }

  async getAttempts(filter?: AttemptFilter): Promise<Attempt[]> {
    if (!hasIDB()) return [];
    const rows = await tx(this.dbName, ATTEMPTS, "readonly", (os) => {
      // Use the single most selective index when exactly one field is set;
      // otherwise a full cursor scan + in-memory predicate. At Phase 1 sizes
      // (thousands of rows) a scan is microseconds — correctness over cleverness.
      const only =
        filter &&
        Object.keys(filter).filter(
          (k) => filter[k as keyof AttemptFilter] !== undefined,
        );
      if (only && only.length === 1) {
        if (filter?.performanceIndicator !== undefined) {
          return reqToPromise(
            os
              .index("by_pi")
              .getAll(IDBKeyRange.only(filter.performanceIndicator)),
          ) as Promise<Attempt[]>;
        }
        if (filter?.since !== undefined) {
          return reqToPromise(
            os.index("by_ts").getAll(IDBKeyRange.lowerBound(filter.since)),
          ) as Promise<Attempt[]>;
        }
      }
      return scan<Attempt>(os, filter ? attemptPredicate(filter) : undefined);
    });
    return rows;
  }

  async getSessions(filter?: SessionFilter): Promise<Session[]> {
    if (!hasIDB()) return [];
    return tx(this.dbName, SESSIONS, "readonly", (os) =>
      scan<Session>(os, filter ? sessionPredicate(filter) : undefined),
    );
  }

  async clear(): Promise<void> {
    if (!hasIDB()) return;
    // One clear() per store; both resolve when their transaction completes.
    await tx(this.dbName, ATTEMPTS, "readwrite", (os) => os.clear());
    await tx(this.dbName, SESSIONS, "readwrite", (os) => os.clear());
  }

  async exportAll(): Promise<{ attempts: Attempt[]; sessions: Session[] }> {
    if (!hasIDB()) return { attempts: [], sessions: [] };
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
    if (!hasIDB()) return;
    // Single tx per store, put-by-id: existing ids overwrite with identical
    // data (safe), new ids insert. Idempotent — the Phase 4 migration primitive.
    await tx(this.dbName, ATTEMPTS, "readwrite", (os) => {
      for (const a of data.attempts) os.put(a);
    });
    await tx(this.dbName, SESSIONS, "readwrite", (os) => {
      for (const s of data.sessions) os.put(s);
    });
  }
}

// ---- in-memory predicates for combined-filter scans ------------------------

function attemptPredicate(f: AttemptFilter): (a: Attempt) => boolean {
  return (a) =>
    (f.cluster === undefined || a.cluster === f.cluster) &&
    (f.level === undefined || a.level === f.level) &&
    (f.performanceIndicator === undefined ||
      a.performanceIndicator === f.performanceIndicator) &&
    (f.since === undefined || a.ts >= f.since) &&
    (f.source === undefined || a.source === f.source);
}

function sessionPredicate(f: SessionFilter): (s: Session) => boolean {
  return (s) =>
    (f.cluster === undefined || s.cluster === f.cluster) &&
    (f.level === undefined || s.level === f.level) &&
    (f.since === undefined || s.ts >= f.since);
}
