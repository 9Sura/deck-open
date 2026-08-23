// Session refresh on every request (D2, sub-plan §4). In Next 16 the `middleware`
// convention was renamed to `proxy` (node_modules/next/dist/docs/.../proxy.md) —
// same behavior, `proxy` function name, Node.js runtime by default.
//
// This is the @supabase/ssr `updateSession` pattern: read cookies from the
// request, let the Supabase client refresh the token, and write the refreshed
// cookies back onto the response so the session never expires mid-practice.
// getUser() is what actually triggers the refresh — call it before returning.
//
// No-ops entirely when the project isn't provisioned, so guest mode has zero
// proxy cost and nothing throws with no Supabase config.

import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import {
  SUPABASE_ANON_KEY,
  SUPABASE_URL,
  isSupabaseConfigured,
} from "@/lib/supabase/env";

export async function proxy(request: NextRequest) {
  if (!isSupabaseConfigured) return NextResponse.next();

  // Mutable so setAll can rebuild it with refreshed request cookies attached.
  let response = NextResponse.next({ request });

  const supabase = createServerClient(SUPABASE_URL!, SUPABASE_ANON_KEY!, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headers) {
        // Reflect onto the request so downstream reads see the new values...
        for (const { name, value } of cookiesToSet) {
          request.cookies.set(name, value);
        }
        // ...then onto a fresh response with the cookies + no-cache headers.
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
        for (const [key, value] of Object.entries(headers ?? {})) {
          response.headers.set(key, value);
        }
      },
    },
  });

  // Triggers the token refresh (writes cookies via setAll above). Must run
  // before the response is returned or the refreshed session is lost.
  await supabase.auth.getUser();

  return response;
}

export const config = {
  // Run on every route except static assets and image files — auth cookies must
  // travel with page/data requests but not with CSS/JS/images.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
