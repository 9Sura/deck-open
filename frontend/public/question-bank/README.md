# Question Bank

Pre-generated, versioned DECA practice questions — the durable output of the
[test generator](../../../backend/test-gen-model/src/generators/generate_test.py), produced **once** and
committed so the frontend can serve practice with **zero live model compute**.

This folder is the canonical store — the ONE copy. The generators read and write it
directly and Next.js serves it verbatim at `/question-bank/...`; there is deliberately
no backend mirror (issue #203), and `backend/.../src/generators/bank_paths.py` is the
single definition of where it lives. See
../../../backend/test-gen-model/plans/02-question-bank-generation-plan.md
for how it is generated, verified, and consumed.

## Layout

```
question-bank/
  manifest.json              # index: version, `sets` + `pools` sections, per-file
                             #   counts, area / letter / difficulty tallies, PI coverage
  pbm/
    pbm-district-1.json          # set 1 — 100 questions
    pbm-district-2.json          # set 2 — independent, same cluster×level
    pbm-district-pool.json       # the pool — original items drawn alongside the sets
    pbm-association-1.json  …     # (the same 1 / 2 / pool trio at each level)
    pbm-icdc-1.json         …
  marketing/  finance/  hospitality/  entrepreneurship/   … (same shape)
```

5 clusters × 3 levels (`District`, `Association`, `ICDC`), and for each cluster×level
two independent **sets** (`-1`, `-2`) of 100 plus one **pool** (`-pool`) that later
slices grew well past 100. **For the live totals read `manifest.json`** — it is
rewritten on every bank write, so a count transcribed here would be wrong by the next
slice, as the "4,500" that stood here for eight plans was. Clusters mirror
../../../backend/test-gen-model/data/clusters.json.

The frontend never serves a set whole: per cluster×level it pools all 300
candidates (both sets **and** the pool) and draws by `(instructional area,
difficulty)` slot. Author a new set with
`build_question_bank.py <cluster> <level> --set N …` and a pool with `… --pool …`.
Question ids embed the set number or `pool` (`mkt-district-2-0007`,
`mkt-district-pool-0007`) so they stay unique across the whole bank.

## File shape

Each set file is an array of question objects matching the frontend
`MockQuestion` contract in
[frontend/lib/mock.ts](../../lib/mock.ts), plus bank metadata:

```jsonc
{
  "id": "mkt-icdc-1-0007",        // <prefix>-<level>-<set#>-<seq>, unique across the bank
  "cluster": "marketing",
  "level": "ICDC",
  "instructionalArea": "Marketing-Information Management",
  "performanceIndicator": "Discuss marketing research issues",
  "question": "…scenario stem…",
  "options": { "A": "…", "B": "…", "C": "…", "D": "…" },
  "answer": "C",
  "explanation": "…answer + why each distractor is wrong…",
  "difficulty": "medium",        // easy | medium | hard — content-derived, one rubric
  "verified": true               // passed the accuracy gate (see the plan)
}
```

Every question carries a `difficulty` tag (`easy` / `medium` / `hard`), assigned
from the question's content by an independent tagger on a single rubric — not to hit
a target distribution. `manifest.json` carries the live per-tier tallies.

> Generated content, AI-authored. Not affiliated with DECA Inc.
