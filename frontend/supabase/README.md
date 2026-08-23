# Supabase — DECK accounts (Phase 4a)

This directory holds the Postgres schema + local-stack config for the accounts
feature. **4a builds the auth foundation only** — signing in works; nothing syncs
to Postgres yet (that's 4b). The app runs in guest-only mode with **zero**
Supabase config, so none of this blocks the existing build.

## What's here
- `migrations/0001_init.sql` — `attempts` / `sessions` / `profiles` tables, indexes,
  RLS (one owner-only policy per table), the new-user profile trigger, and a
  `username_available()` pre-check RPC.
- `config.toml` — local Docker stack config. **Email confirmations are OFF** — this
  is required for the synthetic-email username auth (a `<username>@users.deck.app`
  address can't receive a confirmation link). Mirror this in the hosted dashboard.

## Provisioning (do this once)

### Option A — hosted project (recommended for deploy)
1. Create a project at https://supabase.com/dashboard.
2. **Authentication → Providers → Email:** turn **OFF** "Confirm email". Leave the
   Email provider enabled (username+password rides on it via a synthetic address).
3. **SQL Editor:** paste and run `migrations/0001_init.sql`.
4. **Settings → API:** copy the values into `frontend/.env.local` (see
   `.env.local.example`) and into the Vercel project env:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - (`SUPABASE_SERVICE_ROLE_KEY` — not needed until 4e; server-only, never client.)
5. Restart `npm run dev`. A "Sign in" pill appears in the nav.

### Option B — local stack (Docker)
```bash
cd frontend
npx supabase start          # boots Postgres + Auth + Studio in Docker
npx supabase db reset       # applies migrations/*.sql
```
`supabase start` prints the local URL + anon key — put them in `.env.local`.

## Verify RLS (the security model)
In Studio's SQL editor (or psql), signed in as user A, confirm you can only read
your own rows:
```sql
select count(*) from public.attempts;              -- only A's rows
select count(*) from public.attempts where user_id <> auth.uid();  -- must be 0
```
RLS is the entire per-user boundary (D1/D8) — this is the headline test.

## Notes
- **No password recovery yet** — accounts have no email on file (D2). A forgotten
  password locks the account, though the data survives server-side. The email/2FA
  step (later) re-enables recovery with no data migration.
- Leaderboard objects (a `security definer` RPC) land in `0002_leaderboard.sql`
  during Phase 4d — the raw tables stay RLS-sealed until then.
