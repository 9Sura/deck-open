"use client";

// Browser Supabase client (sub-plan §4). createBrowserClient handles cookie
// storage itself (falls back to document.cookie) and is a singleton by default,
// so calling this repeatedly returns one shared client per tab.
//
// Returns null when the project isn't provisioned yet — callers treat null as
// "guest only", so nothing throws with zero Supabase config.

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { SUPABASE_ANON_KEY, SUPABASE_URL, isSupabaseConfigured } from "./env";

let client: SupabaseClient | null = null;

export function createClient(): SupabaseClient | null {
  if (!isSupabaseConfigured) return null;
  if (client) return client;
  client = createBrowserClient(SUPABASE_URL!, SUPABASE_ANON_KEY!);
  return client;
}
