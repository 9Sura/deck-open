// The one definition of a vocab slug.
//
// Catalog files do NOT store a slug — it is derived from the term. The
// assembler (seed-vocab.mjs) and the Phase 0 tools (vocab_gate.mjs and friends)
// both need it, and the gate's "no slug appears in two catalog files" rule is
// only meaningful if every caller derives it the same way. Import this; never
// re-spell the regex.

export function slugify(term) {
  return String(term).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}
