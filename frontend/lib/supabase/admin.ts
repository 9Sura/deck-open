// Service-role Supabase client — SERVER ONLY (sub-plan §10, D12). Used solely for
// privileged admin actions the anon key can't do (account deletion via
// auth.admin.deleteUser). The service-role key bypasses RLS, so this module must
// NEVER be imported from client code — it's imported only by the delete route
// handler. `SUPABASE_SERVICE_ROLE_KEY` is a non-NEXT_PUBLIC env var, so it is
// never inlined into the client bundle.

import { createClient } from "@supabase/supabase-js";
import type { SupabaseClient } from "@supabase/supabase-js";
import { SUPABASE_URL } from "@/lib/supabase/env";

/** Null when the URL or the server-only service-role key isn't configured. */
export function createAdminClient(): SupabaseClient | null {
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!SUPABASE_URL || !serviceKey) return null;
  return createClient(SUPABASE_URL, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
