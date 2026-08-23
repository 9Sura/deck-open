// Account deletion (sub-plan §10, D12/4e). A POST route holding the service-role
// key: it deletes the AUTHENTICATED CALLER's own auth user, and the
// `on delete cascade` FKs drop every attempts/sessions/profiles row for them.
//
// Security: the uid comes from the verified session (getUser via cookies), NEVER
// from the request body — so a caller can only ever delete their own account.
// The client then clears its local per-user DB + signs out (handled in
// auth-provider.deleteAccount).

import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";

export async function POST() {
  const supabase = await createClient();
  if (!supabase) {
    return NextResponse.json({ error: "Not configured." }, { status: 503 });
  }

  // Verified identity from the cookie session — the only uid we'll act on.
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not signed in." }, { status: 401 });
  }

  const admin = createAdminClient();
  if (!admin) {
    // Service-role key not set (SUPABASE_SERVICE_ROLE_KEY). Deletion can't run.
    return NextResponse.json(
      { error: "Account deletion is unavailable right now." },
      { status: 503 },
    );
  }

  const { error } = await admin.auth.admin.deleteUser(user.id);
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
