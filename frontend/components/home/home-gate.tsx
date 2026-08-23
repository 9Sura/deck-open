"use client";

// The home swap (plan 09 §4.4, D1). `/` renders the study dashboard when signed
// in, and the marketing landing when a guest. A member never sees the marketing
// page via `/`.
//
// SSR/flash: the server has no session, so it renders the loading skeleton when a
// project is configured (loading starts true) and the marketing home otherwise.
// The first client paint matches (loading still true / still guest), then swaps
// once the session resolves — no hydration mismatch. Zero-Supabase builds have no
// accounts and no logging (D10), so they always show the marketing home.

import { useAuth } from "@/components/auth/auth-provider";
import { MarketingHome } from "@/components/home/marketing-home";
import { StudyDashboard } from "@/components/dashboard/study-dashboard";

export function HomeGate() {
  const { configured, loading, session } = useAuth();

  // Only gate on loading when accounts exist — otherwise it's guest forever.
  if (configured && loading) return <HomeSkeleton />;
  return session ? <StudyDashboard /> : <MarketingHome />;
}

function HomeSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8" aria-hidden>
      <div className="animate-pulse space-y-8">
        <div className="h-28 rounded-2xl border-2 border-line bg-paper-2" />
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="h-72 rounded-2xl border-2 border-line bg-paper-2" />
          <div className="h-72 rounded-2xl border-2 border-line bg-paper-2" />
        </div>
      </div>
    </div>
  );
}
