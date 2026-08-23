// Metadata-only layout. This route's page.tsx is `"use client"` and a client
// component can't export `metadata`, so the title lives here; the root layout's
// title.template appends "— DECK" (issue #50).

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Question Bank",
};

export default function QuestionBankLayout({ children }: { children: React.ReactNode }) {
  return children;
}
