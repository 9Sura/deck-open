// Server Supabase client for route handlers / server components (sub-plan §4).
// Reads the session from request cookies via next/headers. In Next 16 `cookies()`
// is async, so this factory is async too.
//
// The `setAll` try/catch is the documented pattern: a Server Component can't
// write cookies, but that's fine — proxy.ts refreshes the session on every
// request, so the write here is a best-effort no-op when it isn't allowed.
//
// Returns null when the project isn't provisioned (guest-only, no network).

import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { SUPABASE_ANON_KEY, SUPABASE_URL, isSupabaseConfigured } from "./env";

export async function createClient(): Promise<SupabaseClient | null> {
  if (!isSupabaseConfigured) return null;
  const cookieStore = await cookies();

  return createServerClient(SUPABASE_URL!, SUPABASE_ANON_KEY!, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Called from a Server Component — proxy.ts owns the session refresh.
        }
      },
    },
  });
}
