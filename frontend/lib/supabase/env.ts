// Client-safe Supabase env access. Both values are public (RLS is the security
// model, D1/D8) so they inline into the client bundle fine. Until the project is
// provisioned these are undefined — every consumer treats that as "guest only,
// no network", so the whole app still builds and runs with zero Supabase config.

export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

/** True once both public env vars are set — the gate for showing any auth UI. */
export const isSupabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
