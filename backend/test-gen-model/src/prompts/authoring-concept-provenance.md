# Provenance for `authoring-concept.txt`

**This file is never sent to an authoring agent.** It holds the measurement history that used to
live inside the brief itself — which slice found each defect, what it cost, and which earlier
wordings were tried and withdrawn.

## Why it was split out

`authoring-concept.txt` grew from 15,313 chars (`de69d95`, 2026-07-27) to 44,112 chars (`aff4162`,
2026-08-07) — 2.9× in eleven days — because every slice finding was appended as narrative next to
the rule it produced. Over the same period the median authoring-agent `prompt_chars` went 41k
(§10-5 … §10-9) to 82k (§10-14).

That matters because §10-14 is the first slice in plan 10 to score `T_REINGEST` on
`agent_cost.py`: the prompt is re-sent every turn, so brief size is multiplied by turn count, not
paid once. `agent_cost.py predict` on chunk 2's real shape (95 items, 4 groups, 67,670 chars) reads
T_REINGEST 194.6k; the same shape at 40,000 chars reads 153.1k.

**Do not read this as "the brief was the problem."** §10-5's billing split (parent plan §4.5)
weights cache READS at ~2% of the bill and cache WRITES at ~47%, because every turn re-caches the
grown prefix. A smaller brief shrinks what each turn re-caches; it does not change how many turns
there are. **Turns remain the larger lever** — which is what the tool budget in the prompt and the
turn-overrun line in `agent_cost.py report` are for.

**This supersedes the "there is nothing worth taking out" note that used to sit in
`build_prompt.py`** (lever 3, 2026-07-29). That measurement was taken on §10-4 chunk 1, whose brief
was 17,167 chars of a 38,221-char prompt. It was correct then and is not correct at 44k. The
composition it reported is preserved below.

The cut moved narrative, not rules. Every rule, every worked example, every banned-word list and
every mechanical test stayed in the brief: 44,112 → 30,454 chars, **31%**.

## What each rule cost to learn

**Rule 2 — stem pull / the artifact case.** PIs naming a thing ("Explain database access tools",
"Demonstrate word processing") ran **9.0% stem pull against a 1.7% baseline**; PIs naming a force
or a relationship ran 1.9%. §10-6 authored Financial Analysis with the rule already in force and
ran **10.0%** — worse than the rate that produced it — because the offending PIs did not look like
tools ("Describe income statements", "Prepare income tax forms", "Explain estate planning",
"Describe sources of income", "Describe functions of money", "Control debt", "Explain legal
considerations for finance"). That is where the "artifact is wider than software" widening came
from. It then leaked again in §10-10 on named METRICS — three of six chunks ran 5.3%, 6.5% and
9.1% — which is where the metric/ratio/formula clause and the acronym clause came from.

**Rule 10 — LETTER= vs LONGEST=.** A 50-question probe with no letter rule put the key at A for
**50 of 50** items. The wrong-key class is §10-14 chunk 3: 5 items keyed on a distractor, the batch
passed **90/90** first time with `LONGEST=` at 100.0% and 0 decisive margins — the cleanest batch
of the slice by every deterministic measure. See `output/plan-10/10-14/chunks234-findings.md`.

**Rule 12 — the band, and half-the-key.** §10-10: of the ten items that hard-failed the 2.2×
ratio, most had all four options inside the band; one ran a 46-char key against distractors of 15,
20 and 20. Eight of those ten sat on "Calculate …" PIs. On plan-10 chunk 4 one author put 59% of
its options outside the band and 32 of its 42 keys over the ceiling, worst by 47 chars; the batch
was thrown away and re-authored, while its sibling on the same brief came in at 7%.

**Rule 12 — `LONGEST=` as an assignment.** The previous wording ("at least one distractor must be
at least as long as the key") cannot be obeyed without measuring all four options, while the same
rule forbade measuring. One author honoured it on **0 of 46** rows; its sibling — same brief, same
model, same day — honoured it on 56 of 60. Repairing the first cost **239k tokens**. Plan-10
chunk 2 came back with the key longest on 71% of items (repair: 100.7k); chunk 3, authored against
the assignment form, came back at 27.7% with no repair pass. Across §10-10's six chunks every batch
at 100% `LONGEST=` broke `key_may_be_longest` zero times, the batch at 88% broke it 4 times, and
the batch at 87% broke it 8. Ties were a third of all `LONGEST=` misses in §10-10 — five rows
across two chunks where the author aimed at the assignment and landed level.

**Rule 12 — the second pass that was paid for and discarded.** On plan-10 chunk 1 an author ran a
self-driven second pass that moved its key-longest rate 57% → 37.7%, still missed the bar, and the
external repair had to run anyway.

**Rule 13 — option tells.** §10-10's H1 shipped every option as `<value>, from <the method that
produced it>`; two raters and two blind solvers flagged it independently and both solvers answered
4 of 4 by reading alone. The first repair round removed the recipe form and a fresh blind solver
still picked 3 of 3 text-only — the mechanism had changed, not gone. **Two rounds, 174.5k tokens.**
§10-11's probe then reproduced it on 2 of 2 computational rows, authored against the brief that
already carried the rule.

An earlier version of rule 12 told authors to write the three distractors as "the plausible wrong
formula, the right formula on the wrong base, the commonly confused metric". **That wording is
withdrawn** — it solved the length floor by inviting method text straight into the options, which
is the defect rule 13 exists to stop.

**Rule 13 — the shipped-bank census (issue #73).** 119 committed computational rows flagged, **112
of them easy or medium**; the hard tier, the one tier that had the rule, was nearly clean.
Twenty-four were answerable by elimination with the stem covered.

**Rule 13a/13b.** §10-12: "current assets of $54,000 and current liabilities of $27,000" shipped
with B "$27,000 in working capital" and C "About $27,000 in working capital", C keyed. It passed
`check_authored` and passed `--list-option-divergence` at 0.0% *because* the labels had been made
identical. Two §10-12 rows on "Read and reconcile bank statements" shipped with no book-side
adjustment.

**Rule 14 — meta-exclusion (issue #131).** A §10-13 repair round was told to fix 8 ambiguous rows
"by adding the fact that rules the competitor out" and produced a meta-exclusion on **5 of the 5
rows where a stem edit was in scope**. All five passed the entire gate suite — `check_authored`
exit 0, stem pull 0.0%, batch invariants 0 blocking, key figures 0 mismatch — because every
instrument reads the OPTIONS or stem-to-KEY overlap and these clauses point at a DISTRACTOR. A
blind solver answered all five correctly with no business knowledge. `--list-stem-meta` is
calibrated at **5 of 5 defect rows flagged, 0 of 5 accepted fixes**, against a 0.61% bank baseline.

**HOW TO WORK — the single-pass rule.** On plan-10 chunk 1 both concept authors wrote their batch
essentially twice (one left a full draft file behind, one left a hand-rolled `lencheck.py`) and
spent 26–33 tool calls each on work the gate does for free, while the referees — doing genuinely
careful judgment work — spent 3. Roughly half of that stage's budget bought nothing.

**HOW TO WORK — the tool budget (§10-14).** chunk3-author: 90 items, **161 tool calls**, 233.0k =
2.59k/item. chunk4-author: 77 items, **4 tool calls**, 147.8k = 1.92k/item — 35% cheaper per item.
chunk2-author-r2: 95 items, 138 tool calls, 256.5k. Those two 100-plus-call agents are why §10-14
scores `T_REINGEST` where six consecutive prior slices scored `T_FLAT`. The tool's reading: **cut
turns, not agents.**

**The nine assertions.** §10-9 chunk 8 self-certified clean against the then-five per-row
assertions and shipped two verbatim-identical stems on the same PI — which is why (f) exists and
why it is stated as the one non-per-row assertion. (d) was one sentence until two authors in a row
read only its first half and reported fixing stem pull "by rewording keys/stems". (i) was added
after §10-14 and is deliberately the one assertion `check_authored` does not back.

## The prompt-composition measurement the cut supersedes

§10-4 chunk 1, 38,221 chars: **45% brief · 42% payload · 13% preamble**, and only 348 of the
brief's 17,167 chars were worked examples (2%). At that size, deleting the entire brief would have
saved ~21k of the agent's 187.8k (11%) and trimming its examples ~0.5k — hence "there is no
lean-brief mode because there is nothing worth taking out."

What changed is the size, not the reasoning: at 44,112 chars on an 82k prompt the brief is over
half the re-sent prefix, and the prefix is re-sent once per turn.
