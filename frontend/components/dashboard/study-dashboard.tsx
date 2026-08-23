"use client";

// The signed-in home (plan 09 §3/§4, D1). Orchestrates the first-run flow (pick
// target → diagnostic → plan), derives the study plan live from the synced log
// each load (nothing derived is stored — plan-08 D8), and hosts ONE LiveQuizModal
// that every launchable task (and the diagnostic) deep-links into.
//
// PURITY (React Compiler is strict): `now` is stamped in an effect via a microtask
// (never Date.now() in render) and fed to the pure buildStudyPlan; Date.now() is
// only used inside event handlers (nonce/seed), which is allowed.
//
// DAY KEY (issue #32): `now` is therefore a SNAPSHOT, so it is the single source of
// the day key — `dayKey` derives from it and both the rendered plan and every
// config.today write go through that one value. Handlers must NOT re-derive the day
// from Date.now(): past local midnight a stale snapshot and a live clock disagreed,
// and the write reseeded a day the screen wasn't rendering, wiping the day's tasks,
// dismissals and session attribution. A rollover timer keeps the snapshot's day
// current instead.

import * as React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { LiveQuizModal } from "@/components/live-quiz-modal";
import { ReadinessTrajectory } from "@/components/progress/readiness-trajectory";
import { MasteryHeatmap } from "@/components/progress/mastery-heatmap";
import { PlanHeader } from "@/components/dashboard/plan-header";
import { PlanSetup, type PlanDraft } from "@/components/dashboard/plan-setup";
import { TodayPlan, type AddOption } from "@/components/dashboard/today-plan";
import { Diagnostic } from "@/components/dashboard/diagnostic";
import { useAuth } from "@/components/auth/auth-provider";
import { useProgress } from "@/components/progress-provider";
import { useProgressData } from "@/hooks/use-progress-data";
import {
  areaMastery,
  areasForClusterWithDrift,
  groupByPI,
  readiness,
  trajectory,
  weakestPIs,
  type WeakPI,
} from "@/lib/progress/mastery";
import { errorLog } from "@/lib/progress/errors";
import { createResolver } from "@/lib/progress/resolver";
import { buildStudyPlan, drillHint, type PlanTask } from "@/lib/progress/plan";
import { forecastPlan } from "@/lib/progress/forecast";
import {
  applyDayEdit,
  localDateKey,
  msUntilNextLocalDay,
  overridesFor,
  type CustomTask,
  type DayPlan,
  type PlanTaskType,
} from "@/lib/progress/plan-config";
import { sampleDiagnostic } from "@/lib/progress/diagnostic";
import {
  noticeForDraw,
  composeTest,
  loadCandidates,
  loadPIQuestions,
  loadQuestionsByIds,
  type BankQuestion,
} from "@/lib/question-bank";
import type { AttemptSource, Choice } from "@/lib/progress/types";
import type { HeatRow } from "@/components/progress/progress-dashboard";
import { CLUSTERS } from "@/lib/data/clusters";
import type { Level } from "@/lib/deca";

const clusterLabel = (value: string) =>
  CLUSTERS.find((c) => c.value === value)?.label ?? value;

/** What the shared quiz host is currently running. */
type QuizReq =
  | {
      mode: "compose";
      cluster: string;
      level: Level;
      mix: "balanced" | "challenge" | "exam-real";
      count: number;
      origin: AttemptSource;
    }
  | {
      mode: "fixed";
      cluster: string;
      level: Level;
      questions: BankQuestion[];
      origin: AttemptSource;
      /** Prior answers to restore when resuming a saved task quiz. */
      initialAnswers?: Map<string, Choice | null>;
      /** Existing session to accumulate into (resume), instead of a new one. */
      resumeSessionId?: string;
      /** That session's already-recorded duration, so the resumed sitting adds to
       *  it rather than overwriting it. */
      resumeElapsedMs?: number;
      /** Why THIS set is what it is — surfaced inside the modal, never as a status
       *  pill (issue #123). Set when a PI drill fell back to the whole instructional
       *  area, so the questions don't arrive under a PI name they don't belong to. */
      notice?: string;
    };

export function StudyDashboard() {
  const { username, planConfig, setPlanConfig } = useAuth();
  const { version } = useProgress();
  const { attempts, sessions, hydrated, loading } = useProgressData();

  // --- client-stamped `now`, refreshed on each write so pacing/"done" stay live.
  const [now, setNow] = React.useState<number | null>(null);
  React.useEffect(() => {
    Promise.resolve().then(() => setNow(Date.now()));
  }, [version, hydrated]);

  // THE day key — one source of truth for both the plan on screen and every edit
  // to it (issue #32). Reading it off `now` alone means a tab left open across
  // local midnight can't render one day while writing another; the rollover
  // effect below is what keeps `now` on the current day.
  const dayKey = now != null ? localDateKey(now) : "";

  // Re-stamp `now` when the local day rolls over, so a dashboard left open
  // overnight moves to the new day instead of rendering a stale one. The timer
  // fires unconditionally (a new `now` reschedules this effect for the following
  // midnight); wake/refocus re-checks too, because a suspended tab's timer can
  // fire long after the fact — that path only re-stamps if the day ACTUALLY
  // changed, so ordinary tab switching doesn't churn the plan.
  React.useEffect(() => {
    if (now == null) return;
    const timer = window.setTimeout(
      () => setNow(Date.now()),
      msUntilNextLocalDay(Date.now()) + 1000,
    );
    const resync = () => {
      setNow((prev) =>
        prev != null && localDateKey(prev) === localDateKey(Date.now()) ? prev : Date.now(),
      );
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") resync();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", resync);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", resync);
    };
  }, [now]);

  // The rendered day key mirrored to a ref so the callbacks below (several of them
  // async) mutate the day the plan is CURRENTLY showing rather than re-reading the
  // clock and diverging from it.
  const dayKeyRef = React.useRef(dayKey);
  React.useEffect(() => {
    dayKeyRef.current = dayKey;
  }, [dayKey]);

  // --- editing the plan (from the header) ---------------------------------
  const [editing, setEditing] = React.useState(false);

  // --- shared quiz host + its loading/empty status -------------------------
  const [quiz, setQuiz] = React.useState<QuizReq | null>(null);
  const [drillStatus, setDrillStatus] = React.useState<"idle" | "loading" | "empty">("idle");
  // Set true while a diagnostic is running so its close marks the config done.
  const pendingDiagnostic = React.useRef(false);
  // The plan-task id whose Start launched the currently-open quiz (null for the
  // diagnostic, heatmap "Practice this", and quick actions). Used to attribute the
  // quiz's session to that task so its progress counts only its own attempts.
  const activeTaskIdRef = React.useRef<string | null>(null);
  // Latest config mirrored to a ref (updated in an effect, never during render)
  // so the async quiz/diagnostic handlers read the current value.
  const configRef = React.useRef(planConfig);
  React.useEffect(() => {
    configRef.current = planConfig;
  }, [planConfig]);
  // Latest attempts mirrored to a ref (updated in an effect) so async launch
  // handlers can restore a resumed quiz's prior answers from the current log.
  const attemptsRef = React.useRef(attempts);
  React.useEffect(() => {
    attemptsRef.current = attempts;
  }, [attempts]);
  // Sessions mirrored the same way, so a resumed launch can hand the modal the
  // duration already banked on that session (it writes the session's TOTAL, so a
  // second sitting must add to the first rather than replace it).
  const sessionsRef = React.useRef(sessions);
  React.useEffect(() => {
    sessionsRef.current = sessions;
  }, [sessions]);
  const bankedElapsed = React.useCallback(
    (sessionId: string | undefined) =>
      sessionId === undefined
        ? 0
        : sessionsRef.current.find((s) => s.id === sessionId)?.elapsedMs ?? 0,
    [],
  );
  // The error log mirrored to a ref (for the fix-misses launcher: it needs each
  // miss's cluster/level to hydrate the question and its resolved status).
  const errorsRef = React.useRef<ReturnType<typeof errorLog>>([]);
  // One question resolver per tab (memoized slice cache) for hydrating miss ids.
  const [resolver] = React.useState(() => createResolver());

  // Fold an edit into config.today (a single, self-pruning day override synced on
  // the profiles row); resets the override when the date rolls over. Keyed off the
  // RENDERED day, never the clock, so an edit can't land on a day the plan on
  // screen isn't showing (issue #32).
  const updateToday = React.useCallback(
    (mut: (day: DayPlan) => DayPlan) => {
      const key = dayKeyRef.current;
      if (!key) return; // pre-hydration: nothing is rendered to edit yet
      // Functional update so several edits in the same tick (session attribution,
      // saved-quiz, dismiss/add, the daily freeze) compose on the freshest config
      // instead of clobbering each other — the bug that stopped progress tracking.
      // applyDayEdit returns the config untouched when the mutator changes
      // nothing, letting setPlanConfig skip a redundant write.
      void setPlanConfig((cfg) => applyDayEdit(cfg, key, mut));
    },
    [setPlanConfig],
  );

  // Persist a task's generated question-id set so pressing Start again resumes the
  // same quiz instead of regenerating.
  const recordTaskQuiz = React.useCallback(
    (taskId: string, ids: string[]) =>
      updateToday((d) => ({ ...d, quizzes: { ...(d.quizzes ?? {}), [taskId]: ids } })),
    [updateToday],
  );

  // Today's override read straight from the config ref (for async handlers that
  // need the freshest persisted quiz/session ids).
  const currentDay = React.useCallback((): DayPlan | null => {
    const cfg = configRef.current;
    const key = dayKeyRef.current;
    return key && cfg?.today && cfg.today.date === key ? cfg.today : null;
  }, []);

  const closeQuiz = React.useCallback(() => {
    if (pendingDiagnostic.current) {
      pendingDiagnostic.current = false;
      void setPlanConfig((cfg) =>
        cfg && !cfg.diagnosticDone ? { ...cfg, diagnosticDone: true } : cfg,
      );
    }
    activeTaskIdRef.current = null;
    setQuiz(null);
  }, [setPlanConfig]);

  // --- launch a fixed-set drill (weak-PI / coverage) -----------------------
  const launchDrill = React.useCallback(
    async (cluster: string, level: Level, pi: string, area: string, count: number, origin: AttemptSource) => {
      setDrillStatus("loading");
      try {
        const { questions, kind } = await loadPIQuestions(cluster, level, pi, count, area);
        if (questions.length === 0) {
          setDrillStatus("empty");
          return;
        }
        setDrillStatus("idle");
        setQuiz({
          mode: "fixed",
          cluster,
          level,
          questions,
          origin,
          notice: noticeForDraw(kind),
        });
      } catch {
        setDrillStatus("empty");
      }
    },
    [],
  );

  // --- launch a plan task's quiz (drill or compose), RESUMABLE --------------
  // The question set is persisted per task the first time it's generated, so
  // pressing Start again loads the SAME questions (not a fresh draw); prior answers
  // are restored from the log and the task's session is reused so progress
  // accumulates across sessions.
  const launchTaskQuiz = React.useCallback(
    async (task: PlanTask) => {
      const l = task.launch;
      if (l.kind !== "drill" && l.kind !== "quiz") return;
      const { cluster, level } = l;
      const origin: AttemptSource =
        task.type === "challenge" || task.type === "milestone" ? "test-gen" : "focus";
      activeTaskIdRef.current = task.id;
      setDrillStatus("loading");
      try {
        const day = currentDay();
        const saved = day?.quizzes?.[task.id];
        let questions: BankQuestion[] = [];
        // Set only on a FIRST launch whose draw came, wholly or partly, from outside
        // the named PI. A resumed task rehydrates by id and so has no draw kind to
        // report — the note explains the draw, and by then the set is already fixed
        // (issue #197).
        let notice: string | undefined;
        if (saved && saved.length > 0) {
          questions = await loadQuestionsByIds(cluster, level, saved);
        }
        if (questions.length === 0) {
          // First launch (or the saved set vanished) — generate + persist its ids.
          if (l.kind === "drill") {
            // A "Learn" (coverage) drill draws only from the REMAINING bank — the
            // questions this student hasn't answered yet — so it stays fresh and
            // gives fewer than its target when few are left. Weak drills are
            // unaffected (they may re-serve missed questions). Phase B #2 — the
            // drill's difficulty tilts to the task's adaptive hint.
            const isCoverage = task.type === "coverage";
            const excludeIds = isCoverage
              ? new Set(attemptsRef.current.map((a) => a.questionId))
              : undefined;
            const draw = await loadPIQuestions(
              l.cluster,
              l.level,
              l.pi,
              l.count,
              l.area,
              task.difficultyHint,
              excludeIds,
              isCoverage, // fill a thin PI up to `count` from the rest of the area
            );
            questions = draw.questions;
            notice = noticeForDraw(draw.kind);
          } else {
            questions = (await composeTest(l.cluster, l.level, l.count, l.mix, Date.now())).questions;
          }
          if (questions.length === 0) {
            setDrillStatus("empty");
            return;
          }
          recordTaskQuiz(task.id, questions.map((q) => q.id));
        }
        // Restore prior answers (from the task's session) + resume that session.
        const sessionIds = day?.sessions?.[task.id] ?? [];
        const sessionSet = new Set(sessionIds);
        const qids = new Set(questions.map((q) => q.id));
        const initialAnswers = new Map<string, Choice | null>();
        for (const a of attemptsRef.current) {
          if (sessionSet.has(a.sessionId) && qids.has(a.questionId)) {
            initialAnswers.set(a.questionId, a.chosen);
          }
        }
        setDrillStatus("idle");
        setQuiz({
          mode: "fixed",
          cluster,
          level,
          questions,
          origin,
          initialAnswers,
          resumeSessionId: sessionIds[0],
          resumeElapsedMs: bankedElapsed(sessionIds[0]),
          notice,
        });
      } catch {
        setDrillStatus("empty");
      }
    },
    [currentDay, recordTaskQuiz, bankedElapsed],
  );

  // --- launch a fix-misses task's quiz (same hosted process, error-log-driven) --
  // Presents the batch's currently-UNRESOLVED misses as a hosted quiz (hydrated by
  // id across clusters). Answering one correctly resolves it in the error log, so
  // the task's count reflects the error log; still-wrong misses reappear next
  // launch (retry-until-fixed, like /review). No answer-restore — each visit is a
  // fresh attempt at what's left.
  //
  // And therefore NO SESSION RESUME either (issue #46). Unlike a task quiz — same
  // set, same size, prior answers restored, so the modal's absolute `endSession`
  // write is a true roll-up — every sitting here runs a DIFFERENT, shrinking set
  // with nothing restored. Reusing the first sitting's session row made the modal
  // overwrite its `answered`/`correct` with only the latest sitting's counts while
  // `total` stayed at the original batch size, losing the earlier roll-up and
  // pinning the row "abandoned" (`answered < total`) forever. Each sitting gets its
  // own session instead: honest per-sitting totals, accuracy and duration. Safe
  // because a fix-misses task's progress is computed from the ERROR LOG
  // (`fixMissesFrom` in lib/progress/plan.ts), never from `countInSessions` — the
  // ids `onSessionStart` appends to `today.sessions[taskId]` aren't read for it.
  const launchFixMisses = React.useCallback(
    async (task: PlanTask) => {
      activeTaskIdRef.current = task.id;
      setDrillStatus("loading");
      try {
        const day = currentDay();
        const missIds =
          task.id === "fix-misses"
            ? day?.fixMissesAuto ?? []
            : day?.custom.find((c) => c.id === task.id)?.missIds ?? [];
        const byId = new Map(errorsRef.current.map((e) => [e.questionId, e]));
        const open = missIds.filter((id) => byId.get(id)?.resolved === false);
        if (open.length === 0) {
          setDrillStatus("empty");
          return;
        }
        const reqs = open.map((id) => {
          const e = byId.get(id)!;
          return { questionId: id, cluster: e.cluster, level: e.level };
        });
        const map = await resolver.resolve(reqs);
        const questions = open
          .map((id) => map.get(id))
          .filter((q): q is BankQuestion => q !== undefined);
        if (questions.length === 0) {
          setDrillStatus("empty");
          return;
        }
        const cfg = configRef.current;
        setDrillStatus("idle");
        setQuiz({
          mode: "fixed",
          cluster: cfg?.cluster ?? questions[0].cluster,
          level: cfg?.level ?? questions[0].level,
          questions,
          origin: "review-lab",
        });
      } catch {
        setDrillStatus("empty");
      }
    },
    [currentDay, resolver],
  );

  const launchTask = React.useCallback(
    (task: PlanTask) => {
      if (task.type === "fix-misses") {
        void launchFixMisses(task);
        return;
      }
      void launchTaskQuiz(task);
    },
    [launchFixMisses, launchTaskQuiz],
  );

  // "Practice this" from the heatmap → a fixed drill, same as /progress.
  const practicePI = React.useCallback(
    (req: { cluster: string; level: Level; pi: string; area: string }) => {
      activeTaskIdRef.current = null; // ad-hoc heatmap drill — not a plan task
      void launchDrill(req.cluster, req.level, req.pi, req.area, 10, "focus");
    },
    [launchDrill],
  );

  // --- diagnostic ----------------------------------------------------------
  const startDiagnostic = React.useCallback(async () => {
    const cfg = configRef.current;
    if (!cfg) return;
    activeTaskIdRef.current = null; // the diagnostic isn't a tracked plan task
    setDrillStatus("loading");
    const questions = await sampleDiagnostic(cfg.cluster, cfg.level, Date.now());
    if (questions.length === 0) {
      setDrillStatus("empty");
      return;
    }
    setDrillStatus("idle");
    pendingDiagnostic.current = true;
    setQuiz({ mode: "fixed", cluster: cfg.cluster, level: cfg.level, questions, origin: "diagnostic" });
  }, []);

  const skipDiagnostic = React.useCallback(() => {
    void setPlanConfig((cfg) =>
      cfg && !cfg.diagnosticDone ? { ...cfg, diagnosticDone: true } : cfg,
    );
  }, [setPlanConfig]);

  // --- per-day task edits (dismiss / add / remove) -------------------------
  // Record the session a task's quiz launched (so its progress counts only its own
  // attempts). Fired by the modal's onSessionStart when a session begins.
  const recordTaskSession = React.useCallback(
    (taskId: string, sessionId: string) =>
      updateToday((d) => {
        const cur = d.sessions?.[taskId] ?? [];
        if (cur.includes(sessionId)) return d;
        return { ...d, sessions: { ...(d.sessions ?? {}), [taskId]: [...cur, sessionId] } };
      }),
    [updateToday],
  );

  const handleSessionStart = React.useCallback(
    (sessionId: string) => {
      const tid = activeTaskIdRef.current;
      if (tid) recordTaskSession(tid, sessionId);
    },
    [recordTaskSession],
  );

  const dismissTask = React.useCallback(
    (id: string) =>
      updateToday((d) => {
        const dismissed = d.dismissed.includes(id) ? d.dismissed : [...d.dismissed, id];
        // Dismissing the AUTO fix-misses task must RELEASE its miss snapshot, so
        // those misses free up (become unowned) and a fresh fix-misses task can be
        // added — otherwise "Add → Fix your misses" would wrongly read "already
        // covered" for a task that's no longer shown.
        if (id === "fix-misses") return { ...d, dismissed, fixMissesAuto: [] };
        return { ...d, dismissed };
      }),
    [updateToday],
  );

  const removeCustomTask = React.useCallback(
    (id: string) =>
      updateToday((d) => ({ ...d, custom: d.custom.filter((c) => c.id !== id) })),
    [updateToday],
  );

  // --- create / edit the plan config --------------------------------------
  const savePlan = React.useCallback(
    (draft: PlanDraft) => {
      const cfg = configRef.current;
      // Editing the plan (e.g. just adding a competition date) must NOT clobber
      // today's live state — task→session attribution, custom tasks, saved
      // quizzes, and the frozen recommended set all live on `today`. Carry it
      // through untouched. Only when the TARGET cluster/level actually changes do
      // those tasks no longer match, so we drop `today` to let the plan
      // regenerate fresh for the new target.
      const targetChanged =
        cfg?.cluster !== draft.cluster || cfg?.level !== draft.level;
      // `diagnosticDone` is a stored per-CONFIG flag, but the diagnostic is
      // one-time PER TARGET. On a target switch the stored flag would stay true
      // and desync from the scoped `diagnosticTaken` the header derives — the
      // freeze effect and step-② gate (which read this flag) would then skip the
      // new target's diagnostic and freeze today cold. Re-derive it from the log
      // for the new target so all three agree: true only if the new cluster×level
      // already has a diagnostic attempt (switching back), false for a fresh one.
      const diagnosticDone = targetChanged
        ? attempts.some(
            (a) =>
              a.source === "diagnostic" &&
              a.cluster === draft.cluster &&
              a.level === draft.level,
          )
        : (cfg?.diagnosticDone ?? false);
      void setPlanConfig({
        cluster: draft.cluster,
        level: draft.level,
        eventDate: draft.eventDate,
        createdTs: cfg?.createdTs ?? Date.now(),
        diagnosticDone,
        today: targetChanged ? undefined : cfg?.today,
      });
      setEditing(false);
    },
    [setPlanConfig, attempts],
  );

  // --- derived roll-ups (memoized; pure over the live log) -----------------
  const cluster = planConfig?.cluster ?? "";
  const level = (planConfig?.level ?? "District") as Level;

  const scoped = React.useMemo(
    () => attempts.filter((a) => a.cluster === cluster && a.level === level),
    [attempts, cluster, level],
  );
  // The diagnostic is one-time PER TARGET: taken ⇔ the log has a diagnostic attempt
  // for THIS cluster×level (scoped). Derived (not a stored flag), so skipping keeps
  // it available, finishing hides it for good — and editing the plan to a new cluster
  // re-surfaces a "Take diagnostic" suited to that cluster (no attempts there yet).
  const diagnosticTaken = React.useMemo(
    () => scoped.some((a) => a.source === "diagnostic"),
    [scoped],
  );
  const byPI = React.useMemo(() => groupByPI(scoped), [scoped]);
  const read = React.useMemo(
    () => readiness(cluster, level, attempts),
    [cluster, level, attempts],
  );
  const weakness = React.useMemo(
    () => weakestPIs(attempts, { cluster, level }),
    [attempts, cluster, level],
  );
  // The fix-your-misses task launches /review, whose Error Log defaults to ALL
  // clusters/levels — so misses are counted globally (over the whole log), not
  // scoped to the plan target, to match exactly what the user sees there.
  const errors = React.useMemo(() => errorLog(attempts), [attempts]);
  React.useEffect(() => {
    errorsRef.current = errors;
  }, [errors]);
  const areaRollups = React.useMemo(
    () =>
      areasForClusterWithDrift(cluster, level, byPI).map((a) =>
        areaMastery(cluster, a, level, byPI),
      ),
    [cluster, level, byPI],
  );
  const traj = React.useMemo(
    () => trajectory(cluster, level, attempts, sessions),
    [cluster, level, attempts, sessions],
  );
  const heat = React.useMemo<HeatRow[]>(
    () => [{ cluster, label: clusterLabel(cluster), readiness: read, areas: areaRollups }],
    [cluster, read, areaRollups],
  );

  const overrides = React.useMemo(
    () => overridesFor(planConfig, dayKey),
    [planConfig, dayKey],
  );

  // How many questions each learning (coverage) drill could actually assemble right
  // now — the count of UNANSWERED questions in each uncovered PI's instructional area
  // (a short PI tops up from its area, capped at the target). Feeds buildStudyPlan so
  // a "Learn" card shows its true size BEFORE launch (never 3 when only 2 exist). The
  // bank is fetched once per cluster/level into a ref; the count recomputes cheaply as
  // answers land. setState only inside a microtask / async resolve (strict rule).
  const candidatesRef = React.useRef<{ key: string; qs: BankQuestion[] } | null>(null);
  const [availabilityByPI, setAvailabilityByPI] = React.useState<Record<string, number>>({});
  const [bankTotal, setBankTotal] = React.useState<number | undefined>(undefined);
  React.useEffect(() => {
    if (!planConfig || !cluster) return;
    const key = `${cluster}|${level}`;
    let active = true;
    const compute = (qs: BankQuestion[]) => {
      if (!active) return;
      const answered = new Set(attempts.map((a) => a.questionId));
      // Per-area UNANSWERED counts (learning drills) + per-PI TOTAL counts (weak
      // drills, which may re-serve answered questions) in one pass over the bank.
      const areaOpen = new Map<string, number>();
      const piTotal = new Map<string, number>();
      for (const q of qs) {
        piTotal.set(q.performanceIndicator, (piTotal.get(q.performanceIndicator) ?? 0) + 1);
        if (answered.has(q.id)) continue;
        areaOpen.set(q.instructionalArea, (areaOpen.get(q.instructionalArea) ?? 0) + 1);
      }
      const map: Record<string, number> = {};
      for (const w of weakness) {
        // Seen PI → weak drill (exact-PI pool); unseen → Learn (unanswered area pool).
        map[w.pi] = w.seen ? piTotal.get(w.pi) ?? 0 : areaOpen.get(w.area) ?? 0;
      }
      setAvailabilityByPI(map);
      setBankTotal(qs.length);
    };
    const cached = candidatesRef.current;
    if (cached?.key === key) {
      const qs = cached.qs;
      Promise.resolve().then(() => compute(qs));
    } else {
      loadCandidates(cluster, level, "all")
        .then((qs) => {
          if (!active) return;
          candidatesRef.current = { key, qs };
          compute(qs);
        })
        .catch(() => {
          if (active) setAvailabilityByPI({});
        });
    }
    return () => {
      active = false;
    };
  }, [cluster, level, weakness, attempts, planConfig]);

  const plan = React.useMemo(() => {
    if (!planConfig || now == null) return null;
    return buildStudyPlan({
      attempts: scoped,
      weakness,
      errors,
      readiness: read,
      areaRollups,
      config: planConfig,
      overrides,
      availabilityByPI,
      bankTotal,
      now,
    });
  }, [planConfig, now, scoped, weakness, errors, read, areaRollups, overrides, availabilityByPI, bankTotal]);

  // Freeze the day's recommended set ONCE, the first time a full plan is built for
  // the day (after the diagnostic is done, so it reflects real signal — not the
  // cold warm-up-only bootstrap). From then on buildStudyPlan renders this fixed
  // set (progress recomputed live) instead of re-deriving, so no new recommended
  // tasks appear as the user's stats shift mid-day. setState via microtask (strict
  // React-Compiler rule); the `recommended` guard makes it idempotent.
  //
  // TWO guards keep it from freezing a plan built on no evidence (issue #61). The
  // render gate ~170 lines below is NOT one of them: React runs every effect before
  // an early return matters, so this fires — and writes — while the skeleton shows.
  //  · `hydrated`/`loading` — the attempt log is an async IndexedDB read that returns
  //    [] until it resolves, while planConfig (localStorage-cached) and `now` land in
  //    a microtask. Without this the first build of the day sees an EMPTY log for a
  //    user with a full history, derives the cold bootstrap, and freezes it — one
  //    warm-up card until local midnight, synced to their other devices.
  //  · `plan.cold` — belt and braces, and a fix in its own right: a user who SKIPS
  //    the diagnostic has diagnosticDone true with a genuinely empty log, so the
  //    guard above passes and the cold plan is still the wrong thing to pin. A cold
  //    plan is supposed to re-derive as the first attempts land; it freezes on the
  //    first warm build instead.
  React.useEffect(() => {
    if (!hydrated || loading) return;
    if (!plan || !planConfig || !dayKey) return;
    if (!planConfig.diagnosticDone) return;
    if (plan.cold) return;
    const today = planConfig.today?.date === dayKey ? planConfig.today : undefined;
    if (today?.recommended?.length) return; // already frozen today
    const specs = plan.freeze;
    // An EMPTY set is never worth freezing (issue #66): `[]` is truthy, so storing it
    // would read as "frozen" and strand the day's plan empty until local midnight —
    // and sync that empty day to the user's other devices. Nothing to pin means let
    // it keep re-deriving as their data changes.
    if (specs.length === 0) return;
    Promise.resolve().then(() =>
      updateToday((d) => (d.recommended?.length ? d : { ...d, recommended: specs })),
    );
  }, [hydrated, loading, plan, planConfig, dayKey, updateToday]);

  // The rolling 3-day forecast (plan 09 §9). Day 0 IS `plan` (passed in, never
  // recomputed), so the calendar and Today's-Plan can never disagree; +1/+2 are a
  // pure projection over a synthetic log. A few extra brain runs per relevant
  // change — cheap at Phase-1 sizes, and re-derived every load (nothing stored).
  const forecast = React.useMemo(() => {
    if (!plan || !planConfig || now == null) return [];
    return forecastPlan({
      plan,
      attempts,
      config: planConfig,
      now,
      // The projected days must be capped by the SAME bank supply as day 0 (#160),
      // or the Tomorrow cell sizes a card off the nominal target the bank can't fill.
      availabilityByPI,
      bankTotal,
    });
  }, [plan, planConfig, now, attempts, availabilityByPI, bankTotal]);

  // BD3: future days are read-only — a task's Start no-ops for dayOffset > 0,
  // enforced HERE at the data layer (not just hidden), so no deep-link/keyboard
  // path through the calendar can start a task before its day arrives.
  const launchTaskAt = React.useCallback(
    (task: PlanTask, dayOffset: number) => {
      if (dayOffset > 0) return;
      launchTask(task);
    },
    [launchTask],
  );

  // --- "Add a task" menu (materialize a recommendation TYPE into a real task) --
  // PIs already targeted by a task today, so an added drill picks a fresh one.
  const usedPIs = React.useMemo(
    () =>
      new Set(
        (plan?.tasks ?? [])
          .map((t) => t.target?.pi)
          .filter((pi): pi is string => Boolean(pi)),
      ),
    [plan],
  );
  const presentTypes = React.useMemo(
    () => new Set((plan?.tasks ?? []).map((t) => t.type)),
    [plan],
  );
  // Unresolved misses NOT already owned by a VISIBLE fix-misses task — these are
  // what a NEW fix-misses task would snapshot. Ownership is tied to what's actually
  // shown (plan.tasks), NOT the raw snapshot: a dismissed auto batch leaves a stale
  // `fixMissesAuto`, but since its task isn't shown, its misses free up again so a
  // fresh fix-misses task can be added.
  const unownedMisses = React.useMemo(() => {
    const autoVisible = (plan?.tasks ?? []).some((t) => t.id === "fix-misses");
    const owned = new Set<string>([
      ...(autoVisible ? overrides.fixMissesAuto : []),
      ...overrides.custom
        .filter((c) => c.type === "fix-misses")
        .flatMap((c) => c.missIds ?? []),
    ]);
    return errors
      .filter((e) => !e.resolved && !owned.has(e.questionId))
      .map((e) => e.questionId);
  }, [plan, overrides, errors]);
  const hasAnyUnresolvedMiss = React.useMemo(
    () => errors.some((e) => !e.resolved),
    [errors],
  );

  // NOTE: the fix-misses AUTO batch was removed. Auto-inserting a "Fix your misses"
  // task the moment you got something wrong was the "errors added extra tests"
  // behavior, and its per-answer write to config.today raced the session-attribution
  // write and clobbered it (progress then stopped tracking). Misses are now handled
  // only on demand: "Add a task → Fix your misses", and /review. Nothing writes to
  // config.today as a side effect of answering.

  // Which add-menu options make sense right now (disable duplicates / no-candidate),
  // each with a hover reason explaining why it's unavailable.
  //
  // The no-candidate options ASK THE BUILDER instead of restating its rule — the two
  // used to drift (#110: the menu required mastery < 0.6, but materializeTask falls
  // back to any seen un-targeted PI, so a drill greyed out that would have built fine).
  // materializeTask is pure — `stamp` is a parameter precisely so this speculative
  // call has no side effect — and each arm is a `.find` over ~12 rows, so calling it
  // to answer "would this work?" and throwing the result away is free.
  const canAdd = (type: PlanTaskType) =>
    materializeTask(type, {
      weakness,
      usedPIs,
      cluster,
      level,
      missIds: unownedMisses,
      stamp: 0,
    }) !== null;
  const addOptions: AddOption[] = [
    {
      type: "weak-drill",
      label: "Weak-area drill",
      desc: "Your weakest performance indicator",
      disabled: !canAdd("weak-drill"),
      reason: "Nothing left to drill — today's plan already covers the areas you've practiced.",
    },
    {
      type: "coverage",
      label: "Coverage filler",
      desc: "A performance indicator you've never tried",
      disabled: !canAdd("coverage"),
      reason: "Every performance indicator here is already covered or in today's plan.",
    },
    {
      type: "warmup",
      label: "Warm-up quiz",
      desc: "Quick 10-question mixed set",
      disabled: presentTypes.has("warmup"),
      reason: "A warm-up quiz is already in today's plan.",
    },
    {
      type: "challenge",
      label: "Challenge set",
      desc: "Hard-heavy 10-question mix",
      disabled: presentTypes.has("challenge"),
      reason: "A challenge set is already in today's plan.",
    },
    {
      type: "milestone",
      label: "Milestone test",
      desc: "Full 50-question exam-real test",
      disabled: presentTypes.has("milestone"),
      reason: "A milestone test is already in today's plan.",
    },
    {
      type: "fix-misses",
      label: "Fix your misses",
      desc: "Re-answer questions you got wrong",
      disabled: !canAdd("fix-misses"),
      reason: hasAnyUnresolvedMiss
        ? "Your open misses are already covered by a fix-misses task."
        : "No misses to fix — you're all caught up.",
    },
  ];

  const addTaskOfType = React.useCallback(
    (type: PlanTaskType) => {
      const cfg = configRef.current;
      if (!cfg) return;
      const task = materializeTask(type, {
        weakness,
        usedPIs,
        cluster: cfg.cluster,
        level: cfg.level,
        missIds: unownedMisses,
        stamp: Date.now(),
      });
      if (task) updateToday((d) => ({ ...d, custom: [...d.custom, task] }));
    },
    [weakness, usedPIs, unownedMisses, updateToday],
  );

  // The shared quiz modal host — mounted unconditionally, `open` toggled (mounting
  // already-open renders blank). Compose vs fixed picked from `quiz`.
  const quizHost = (
    <>
      {drillStatus === "loading" && <StatusPill>composing your set…</StatusPill>}
      {drillStatus === "empty" && (
        <StatusPill onDismiss={() => setDrillStatus("idle")}>
          No bank questions available for that one yet.
        </StatusPill>
      )}
      <LiveQuizModal
        open={quiz !== null}
        onClose={closeQuiz}
        cluster={quiz?.cluster ?? "all"}
        clusterLabel={quiz ? clusterLabel(quiz.cluster) : ""}
        level={quiz?.level ?? "District"}
        mix={quiz?.mode === "compose" ? quiz.mix : undefined}
        count={quiz?.mode === "compose" ? quiz.count : undefined}
        fixedQuestions={quiz?.mode === "fixed" ? quiz.questions : undefined}
        notice={quiz?.mode === "fixed" ? quiz.notice : undefined}
        origin={quiz?.origin ?? "focus"}
        animate={false}
        onSessionStart={handleSessionStart}
        initialAnswers={quiz?.mode === "fixed" ? quiz.initialAnswers : undefined}
        resumeSessionId={quiz?.mode === "fixed" ? quiz.resumeSessionId : undefined}
        resumeElapsedMs={quiz?.mode === "fixed" ? quiz.resumeElapsedMs : undefined}
      />
    </>
  );

  // --- render gates --------------------------------------------------------
  if (!hydrated || loading || now == null) {
    return <DashboardSkeleton />;
  }

  const wrap = (inner: React.ReactNode) => (
    <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
      {inner}
      {quizHost}
    </div>
  );

  // Step ① — no plan yet (or editing): the setup card.
  if (!planConfig || editing) {
    return wrap(
      <PlanSetup
        now={now}
        initial={planConfig}
        onSubmit={savePlan}
        onCancel={editing ? () => setEditing(false) : undefined}
      />,
    );
  }

  // Step ② — plan set, diagnostic not yet taken/skipped.
  if (!planConfig.diagnosticDone) {
    return wrap(
      <div className="flex flex-col items-center gap-6">
        <Diagnostic
          clusterLabel={clusterLabel(planConfig.cluster)}
          level={planConfig.level}
          state={drillStatus}
          onStart={() => void startDiagnostic()}
          onSkip={skipDiagnostic}
        />
      </div>,
    );
  }

  // Step ③ — the full plan dashboard.
  return wrap(
    <div className="flex flex-col gap-8">
      <PlanHeader
        username={username}
        config={planConfig}
        pacing={plan?.pacing ?? { daysLeft: null, expectedReadiness: 0, actualReadiness: 0, status: "no-date" }}
        forecast={forecast}
        onLaunchTask={launchTaskAt}
        onEditPlan={() => setEditing(true)}
        onTakeDiagnostic={() => void startDiagnostic()}
        diagnosticTaken={diagnosticTaken}
      />

      <div className="grid gap-8 lg:grid-cols-2">
        <TodayPlan
          tasks={plan?.tasks ?? []}
          onLaunch={launchTask}
          onDismiss={dismissTask}
          onRemoveCustom={removeCustomTask}
          onAddTaskType={addTaskOfType}
          addOptions={addOptions}
        />

        <div className="flex flex-col gap-6">
          <ReadinessTrajectory
            points={traj}
            cluster={cluster}
            clusterName={clusterLabel(cluster)}
          />
        </div>
      </div>

      <MasteryHeatmap
        rows={heat}
        level={level}
        byPI={byPI}
        singleCluster
        onPractice={practicePI}
      />

      {/* Quick actions — escape hatches into any surface. */}
      <section>
        <h2 className="font-display text-xl font-bold tracking-tight">Quick actions</h2>
        <div className="mt-3 flex flex-wrap gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              activeTaskIdRef.current = null; // ad-hoc quick action, not a plan task
              setQuiz({ mode: "compose", cluster, level, mix: "balanced", count: 10, origin: "focus" });
            }}
          >
            Focus quiz
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/test-generator">Generate test</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/review">Review errors</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href="/progress">Full progress →</Link>
          </Button>
        </div>
      </section>
    </div>,
  );
}

/* ---------------------------------------------------- add-task materializer */

// Turn a chosen recommendation TYPE into a concrete, fully-specified task (with a
// generated-question launch) using the live weakness ranking + the plan target.
// Mirrors buildStudyPlan's own per-type construction, so an added task behaves
// exactly like a recommended one of that type. Returns null when there's no
// sensible target (e.g. no fresh weak PI) — which is ALSO how the add menu decides
// what to grey out (#110), so this is the single statement of every no-candidate
// rule. Keep it pure: `stamp` (the id's uniqueness) is a parameter rather than a
// Date.now() call so the menu can invoke it speculatively during render.
function materializeTask(
  type: PlanTaskType,
  ctx: {
    weakness: WeakPI[];
    usedPIs: Set<string>;
    cluster: string;
    level: Level;
    missIds: string[];
    stamp: number;
  },
): CustomTask | null {
  const { weakness, usedPIs, cluster, level, missIds, stamp } = ctx;

  if (type === "weak-drill") {
    const w =
      weakness.find((x) => x.seen && x.mastery < 0.6 && !usedPIs.has(x.pi)) ??
      weakness.find((x) => x.seen && !usedPIs.has(x.pi));
    if (!w) return null;
    return {
      id: `add-weak-${stamp}`,
      type,
      title: `Drill: ${w.pi}`,
      subtitle: `${w.area} · weak spot`,
      size: 8,
      difficultyHint: drillHint(w.mastery),
      target: { cluster: w.cluster, level: w.level, pi: w.pi, area: w.area },
      launch: { kind: "drill", cluster: w.cluster, level: w.level, pi: w.pi, area: w.area, count: 8 },
    };
  }

  if (type === "coverage") {
    const w = weakness.find((x) => !x.seen && !usedPIs.has(x.pi));
    if (!w) return null;
    return {
      id: `add-cover-${stamp}`,
      type,
      title: `Learn: ${w.pi}`,
      subtitle: `${w.area} · never practiced`,
      size: 3,
      difficultyHint: "mixed",
      target: { cluster: w.cluster, level: w.level, pi: w.pi, area: w.area },
      launch: { kind: "drill", cluster: w.cluster, level: w.level, pi: w.pi, area: w.area, count: 3 },
    };
  }

  if (type === "warmup") {
    return {
      id: `add-warmup-${stamp}`,
      type,
      title: "Warm-up quiz",
      subtitle: "A quick 10-question mixed set",
      size: 10,
      difficultyHint: "mixed",
      target: { cluster, level },
      launch: { kind: "quiz", cluster, level, mix: "balanced", count: 10 },
    };
  }

  if (type === "challenge") {
    return {
      id: `add-challenge-${stamp}`,
      type,
      title: "Challenge set",
      subtitle: "Hard-heavy mix to push your ceiling",
      size: 10,
      difficultyHint: "challenge",
      target: { cluster, level },
      launch: { kind: "quiz", cluster, level, mix: "challenge", count: 10 },
    };
  }

  if (type === "milestone") {
    return {
      id: `add-milestone-${stamp}`,
      type,
      title: "Milestone test",
      subtitle: "Exam-real 50-question check-in",
      size: 50,
      difficultyHint: "mixed",
      target: { cluster, level },
      launch: { kind: "quiz", cluster, level, mix: "exam-real", count: 50 },
    };
  }

  if (type === "fix-misses") {
    if (missIds.length === 0) return null;
    return {
      id: `add-fix-misses-${stamp}`,
      type,
      title: `Fix ${missIds.length} miss${missIds.length === 1 ? "" : "es"}`,
      subtitle: "Re-answer the questions you got wrong",
      size: missIds.length,
      difficultyHint: "mixed",
      launch: { kind: "review" },
      missIds,
    };
  }

  return null;
}

/* ------------------------------------------------------------- status pill */

function StatusPill({
  children,
  onDismiss,
}: {
  children: React.ReactNode;
  onDismiss?: () => void;
}) {
  return (
    <div className="fixed inset-x-0 bottom-6 z-40 flex justify-center px-4">
      <div className="sketch-radius flex items-center gap-3 border-2 border-ink bg-paper px-4 py-2 text-sm shadow-lg">
        <span className="text-ink/80">{children}</span>
        {onDismiss && (
          <button onClick={onDismiss} className="text-muted hover:text-ink" aria-label="Dismiss">
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- skeleton */

function DashboardSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
      <div className="animate-pulse space-y-8" aria-hidden>
        <div className="h-32 rounded-2xl border-2 border-line bg-paper-2" />
        <div className="grid gap-8 lg:grid-cols-2">
          <div className="h-72 rounded-2xl border-2 border-line bg-paper-2" />
          <div className="h-72 rounded-2xl border-2 border-line bg-paper-2" />
        </div>
        <div className="h-48 rounded-2xl border-2 border-line bg-paper-2" />
      </div>
    </div>
  );
}
