-- 0003_plan_config.sql — Study Plan Dashboard (plan 09 §4.1, D3).
--
-- Adds the ONE new persisted study-plan state: a per-account plan config
-- (target cluster/level + competition date + flags), stored as jsonb on the
-- existing `profiles` row so the target follows the user across devices. Shape
-- mirrors lib/progress/plan-config.ts `PlanConfig`; the client validates/coerces
-- on read, so the column is intentionally schemaless (null = "no plan yet").
--
-- Re-runnable (drop/if-exists style, like 0001's guarded creates): safe to apply
-- to a DB that already has the column. RLS is unchanged — `profiles` is already
-- owner-scoped (profiles_owner in 0001), so plan_config inherits that policy and
-- never needs its own.

alter table public.profiles
  add column if not exists plan_config jsonb;
