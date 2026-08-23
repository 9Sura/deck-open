import Link from "next/link";
import { Sparkle } from "@/components/doodles";
import { FooterAccountLinks } from "@/components/footer-account-links";
import { FooterPracticeLinks } from "@/components/footer-practice-links";

export function Footer() {
  return (
    <footer className="border-t border-dashed border-line">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 py-8 sm:flex-row sm:px-8">
        <div className="flex items-center gap-2 font-display font-extrabold tracking-tight">
          <Sparkle className="h-4 w-4 text-highlight-ink" />
          <span className="sketch-radius border-2 border-ink bg-accent px-1.5 py-0.5 text-[var(--on-accent)]">DECK</span>
        </div>
        <div className="flex items-center gap-6 text-sm text-muted">
          {/* Both are member routes — a guest's click opens sign-up rather than
              landing on the wall (#146). */}
          <FooterPracticeLinks />
          {/* Guest-only in the nav; these render here once signed in. */}
          <FooterAccountLinks />
          {/* The only legal links, and the only place either renders on every
              route — the footer sits outside <MemberGate>, unlike the nav split
              (#209). Neither is in gated-routes.ts and neither should be. */}
          <Link href="/terms" className="hover:text-ink">Terms</Link>
          <Link href="/privacy" className="hover:text-ink">Privacy</Link>
        </div>
        <p className="text-xs text-muted">
          Built for DECA competitors. Not affiliated with DECA Inc.
        </p>
      </div>
    </footer>
  );
}
