-- 0004_active_session.sql — single active session per account ("newest login wins").
--
-- Each browser that LOGS IN mints a random session token and stamps it here; every
-- signed-in client watches this column (initial read + realtime) and signs itself
-- out the moment it sees a token that isn't its own — so a fresh login elsewhere
-- boots the older session. This also closes the cross-device `plan_config` clobber
-- (two people editing one account's plan at once) by making one-at-a-time the norm.
--
-- Re-runnable (if-exists guards), like the other migrations. RLS is unchanged —
-- `profiles` is already owner-scoped (profiles_owner in 0001), so a user can only
-- read/write their own token, and realtime only ever delivers their own row.
-- null = "no active session claimed yet" (legacy rows / never logged in since this
-- shipped) — clients treat null as "don't boot".

alter table public.profiles
  add column if not exists active_session text;

-- Let clients receive realtime UPDATEs on their own profiles row (RLS still gates
-- delivery to the owner). Guarded so re-applying doesn't error if already added.
do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'profiles'
  ) then
    alter publication supabase_realtime add table public.profiles;
  end if;
end $$;
