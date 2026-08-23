import type { Metadata } from "next";
import { Fraunces, Geist, Geist_Mono, Shantell_Sans } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthProvider } from "@/components/auth/auth-provider";
import { RouteGuard } from "@/components/auth/route-guard";
import { MemberGate } from "@/components/auth/member-gate";
import { WelcomeOverlay } from "@/components/auth/welcome-overlay";
import { ProgressProvider } from "@/components/progress-provider";
import { ThemeEffects } from "@/components/theme-effects";
import { THEME_STORAGE_KEY } from "@/lib/themes";
import { Analytics } from "@vercel/analytics/next";

// Display: Fraunces soft-serif — warm, characterful headlines.
// Variable font → no `weight`; pull the SOFT + optical-size axes for the
// friendly, refined feel we're after.
const display = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
  axes: ["SOFT", "opsz"],
});

const sans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

// Mono: Geist Mono — same family voice as the body sans. Loaded up front so
// the Terminal theme can point numerals (`.stat`) at it with no dynamic load.
const mono = Geist_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

// Handwriting: Shantell Sans — a refined variable hand face (default BNCE=0,
// so it reads calm/inked, not bouncy-marker). Replaces Permanent Marker.
const marker = Shantell_Sans({
  variable: "--font-marker",
  subsets: ["latin"],
});

// `title.template` suffixes every child segment's title with "— DECK", so a
// route only names itself ("Question Bank" -> "Question Bank — DECK"). `default`
// is required alongside a template and is what `/` itself renders. Routes whose
// page.tsx is `"use client"` can't export metadata at all — they carry a tiny
// server `layout.tsx` instead (issue #50).
export const metadata: Metadata = {
  title: {
    default: "DECK",
    template: "%s — DECK",
  },
  // Matches the hero, and for the same reason (#108): "unlimited" described the
  // dropped live-JIT path, not the bank the tests are actually composed from.
  // This string is the search-result and link-preview copy, so it is the same
  // claim reaching a guest one step earlier than the landing page does.
  description:
    "Exam-authentic DECA practice tests and roleplay case studies, built to order. Pick your cluster or event, set the level, and practice.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${sans.variable} ${mono.variable} ${marker.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        {/* No-flash theme: runs synchronously during HTML parse, before first
            paint, so a stored non-default theme is applied without a snap.
            Dependency-free and self-contained (see theming plan §1.3). */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t)document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`,
          }}
        />
      </head>
      <body className="min-h-full flex flex-col bg-paper text-ink">
        <ThemeProvider>
          <ThemeEffects />
          {/* AuthProvider sits above ProgressProvider so Phase 4b can select the
              store by auth state; in 4a it only powers the Nav account menu.
              ProgressProvider wraps Nav too so the settings dialog's "reset progress"
              shares the same store instance as the pages — a reset bumps `version` and
              refreshes an open /progress or /review live. */}
          <AuthProvider>
            <RouteGuard />
            <ProgressProvider>
              <Nav />
              {/* MemberGate wraps only the page body, so the nav/footer stay put
                  while a guest on a member route gets the sign-up panel in place
                  of the page (#33). */}
              <main className="flex-1">
                <MemberGate>{children}</MemberGate>
              </main>
              <Footer />
            </ProgressProvider>
            <WelcomeOverlay />
          </AuthProvider>
        </ThemeProvider>
        {/* Vercel Web Analytics — renders no DOM of its own and only loads its
            script on Vercel deployments (it no-ops in local dev), so it sits
            outside the providers rather than inside the app tree. Page-view
            counts only; see /privacy. */}
        <Analytics />
      </body>
    </html>
  );
}
