-- 0001_init.sql — Phase 4a auth foundation (sub-plan §3).
--
-- Three tables behind the ProgressStore seam: attempts (append-only event log),
-- sessions (one row per run, upsert-latest), profiles (account identity + prefs).
-- PKs are the CLIENT-minted uuids (lib/progress/ids.ts) so every remote write is
-- an idempotent upsert-by-id and the guest->account migration is a set union.
--
-- RLS is the entire per-user security model (D1/D8): one `for all` policy per
-- table, gated on auth.uid(). The leaderboard definer RPC that reads across users
-- lands in 0002 (Phase 4d) — until then the raw tables are fully RLS-sealed.

-- attempts: append-only, one row per answered question. PK = client uuid.
create table public.attempts (
  id                    uuid primary key,                       -- client-minted (ids.ts)
  user_id               uuid not null references auth.users on delete cascade,
  ts                    timestamptz not null,
  question_id           text not null,
  cluster               text not null,
  level                 text not null,
  instructional_area    text not null,
  performance_indicator text not null,
  difficulty            text not null,
  chosen                text,                                   -- null = skip
  correct               boolean not null,
  elapsed_ms            integer not null,
  source                text not null,
  session_id            uuid not null,
  created_at            timestamptz not null default now()
);
create index attempts_user_cluster_level on public.attempts (user_id, cluster, level);
create index attempts_user_pi            on public.attempts (user_id, performance_indicator);
create index attempts_user_ts            on public.attempts (user_id, ts);

-- sessions: one row per run; upsert-latest (start -> endSession patch).
create table public.sessions (
  id          uuid primary key,
  user_id     uuid not null references auth.users on delete cascade,
  ts          timestamptz not null,
  ended_ts    timestamptz,
  cluster     text not null,
  level       text not null,
  source      text not null,
  total       integer not null,
  answered    integer not null,
  correct     integer not null,
  elapsed_ms  integer not null
);
create index sessions_user_ts on public.sessions (user_id, ts);

-- profiles: the account identity + prefs (mirrors profile.ts + username + opt-in).
create table public.profiles (
  user_id            uuid primary key references auth.users on delete cascade,
  username           text not null unique,               -- the login identity (D2); case-insensitive below
  display_name       text not null,
  avatar_emoji       text not null default '📝',
  leaderboard_opt_in boolean not null default false,
  created_at         timestamptz not null default now()
);
create unique index profiles_username_lower on public.profiles (lower(username));  -- case-insensitive uniqueness

alter table public.attempts enable row level security;
alter table public.sessions enable row level security;
alter table public.profiles enable row level security;

-- RLS: a user sees and writes ONLY their own rows (D8). One policy per table,
-- gated on auth.uid() for every verb (for all = select/insert/update/delete).
create policy attempts_owner on public.attempts
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy sessions_owner on public.sessions
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy profiles_owner on public.profiles
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Auto-create a profile row on signup. username + display_name come from the
-- signup metadata (set client-side on signUp); the profiles_username_lower unique
-- index rejects a taken username (surfaced as "username already taken" in the UI).
create function public.handle_new_user() returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (user_id, username, display_name)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'username', 'user_' || left(new.id::text, 8)),
    coalesce(new.raw_user_meta_data->>'display_name', new.raw_user_meta_data->>'username', 'Guest')
  );
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- Username availability pre-check for the sign-up dialog. RLS forbids an
-- anonymous user from reading `profiles` directly, so a definer function exposes
-- ONLY a yes/no (never any row data). The profiles_username_lower unique index
-- remains the race-safe source of truth; this is just a friendly pre-flight.
create function public.username_available(u text) returns boolean
  language sql security definer stable as $$
    select not exists (select 1 from public.profiles where lower(username) = lower(u));
$$;
grant execute on function public.username_available(text) to anon, authenticated;
