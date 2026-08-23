"""Issues #153 and #185 fixtures: `check_authored.label_divergence()`, all three branches.

THE #153 DEFECT. The instrument scored the fraction of label wording common to all four
options, so a row whose four labels share a LONG phrase and differ only in a SHORT
trailing clause read as convergent -- at exactly the moment that clause is the tell it
exists to catch. §10-14 chunk 9 shipped 12 of 90 rows in that shape while BOTH
instruments built for the class reported better than the committed bank:

    m0073  A $12,750, the correct total redemption cost after the intern's third calculation
           B $11,250, the correct total redemption cost for the deal
           C $127,500, the correct total redemption cost, first attempt
           D $187,500, the correct total redemption cost, second attempt

shared = 0.33, so the row never flagged. A reader following the documented method
("read the RATE against that baseline") concluded the batch was 2.5x cleaner than the
bank, on a batch carrying the class at 10.8%.

THE #185 DEFECT, AND THIS FIXTURE WAS PART OF IT. Three byte-identical labels beside
one divergent option, WHERE THE DIVERGENT ONE IS THE KEY, falls between both branches
-- branch 1 needs `shared` LOW and three identical labels drive it UP; branch 2 needs
the leftovers on three of the four and this shape puts them all on one. §10-16 chunks
9/10/11 shipped four live rows of it past a gate reading ABOVE its own baseline:

    e0032  A 15% of respondents visited exactly twice
           B 25% of respondents visited exactly twice
           C 40% of respondents visited exactly twice
           D 20% of the 150 customers visited exactly twice          <- KEY

The version of this file before #185 asserted, in as many words, that this case was
"branch 1's question". Branch 1 structurally cannot answer it: it requires
`shared < LABEL_SHARED_MAX` and three identical labels guarantee the opposite. That
assertion is now two assertions -- odd option a DISTRACTOR (nothing fires, correctly)
and odd option the KEY (branch 3 fires) -- because a fixture that pins a wrong claim
is worse than no fixture: it is a passing test standing where the hole is.

WHY IT NEEDS A FIXTURE. This repo has now watched two calibrated instruments drift
without anything noticing (issue #88's combination-option regex, issue #76's
GATED_FIELDS map), and the rule is standing: when a gate's behaviour is asserted in a
comment, assert it in a fixture too. The specific hazards here are:

  * WIDENING branch 2 until the bank baseline stops being readable. `LABEL_UNIQUE_MIN`
    of 2 finds one more of the 12 known rows and fires on 48.8% of the bank.
  * NARROWING it back onto `shared`, which is the defect issue #153 is.
  * REACHING BRANCH 3'S CLASS by lowering `LABEL_REMAINDER_SPREAD` to 1. That drops
    the `answer` condition and fires on all 329 of the bank's `spread == 1` rows,
    including the 219 where a DISTRACTOR is the odd one out -- a real but far weaker
    defect, since crossing off the option that reads differently gets a student
    nowhere. Asserted below so re-proposing it is loud.
  * Breaking #75's NEGATIVE arm. §10-10's h1-deleak2 is the only adjudicated
    accepted-fix this instrument has, and a detector with no adjudicated negative is a
    detector nobody can falsify.
  * Splitting the finding onto a second line. `build_repair_prompt.finding_scope`
    adds `options` for every gate line it cannot place (issue #77) -- harmless here,
    since the repair IS an option repair, but it is the reason the line count is
    pinned rather than left to drift.

THREE ADJUDICATED PAIRS. The first two are read off disk rather than pasted.

  §10-14 chunks 9/10 (issue #153). The DEFECT arm is `gate/audit-c910-0{1,2}.json` --
  the blind-audit INPUT, which `build_audit_input.py` wrote from the authored parts
  BEFORE the repair, so it carries the options as shipped. The FIX arm is
  `parts/chunk9-part{1..4}.json`, which `apply_repair` wrote back in place. The 12 row
  ids are the ones two independent blind shards named with quoted phrases, recorded as
  criterion C6 in `chunks910-repair-scope.md`.

  §10-10's H1 (issue #75). `parts/h1-deleak.json` is round 1, which two blind solvers
  still answered by reading; `-deleak2.json` is the accepted fix. This pair is the
  REGRESSION arm: a new branch must not move either number.

  §10-16 chunk 10 (issue #185). The four rows the unscoped blind pass found, plus
  `e0059` -- the one row of that shape branch 1 DID catch, which is the arm that keeps
  the branches from being read as interchangeable. THIS PAIR IS INLINED VERBATIM
  rather than read off disk, and deliberately: §10-16 is an OPEN slice, so
  `output/plan-10/10-16/parts.bak.c91011` (the defect arm) and `parts/` (the fix arm)
  are untracked in the working tree and a fresh clone does not have them. Same
  precedent as `fixtures_agent_cost_kinds.py`, which inlines §10-16's cost rows for
  the same reason. Move it back onto disk once the slice is committed if you like --
  the rows below are byte-identical to the files, `answer` included.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_label_divergence.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, never hardcoded.
"""
import json
import sys
from math import comb
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
MODEL_DIR = GEN.parents[1]                 # backend/test-gen-model
P1014 = MODEL_DIR / "output" / "plan-10" / "10-14"
P1010 = MODEL_DIR / "output" / "plan-10" / "10-10" / "parts"
sys.path.insert(0, str(GEN))
from bank_paths import BANK_DIR  # noqa: E402  the ONE bank path (#203)
from check_authored import (  # noqa: E402
    BANK_LABEL_DIVERGENCE_RATE,
    LABEL_ODD_SPREAD,
    LABEL_REMAINDER_MIN,
    LABEL_REMAINDER_SPREAD,
    LABEL_SHARED_MAX,
    LABEL_UNIQUE_MIN,
    label_divergence,
)
from build_repair_prompt import finding_scope  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def score(q):
    """One row measured the way `check_question` measures it -- options AND answer.

    A row with no `answer` key (the blind audit shards, by construction) is measured
    with the third branch silent, which is what an arm built from blind input can
    honestly say about it.
    """
    return label_divergence(q.get("options") or {}, q.get("answer", ""))


def flagged(rows):
    """(flagged, in-scope, odd-key) over {cand_id: question dict}."""
    scored = [d for d in (score(q) for q in rows.values()) if d]
    return (sum(1 for d in scored if d["flagged"]), len(scored),
            sum(1 for d in scored if d["odd_key"]))


def short(cid):
    return cid.split("-")[-1]


print("Issues #153 / #185 -- label divergence, the remainder and odd-one-out branches\n")

# ---------------------------------------------------------------------------
# 1. The §10-14 pair -- the 12 rows two blind shards named, before and after repair.
# ---------------------------------------------------------------------------
C6_ROWS = ["m0032", "m0034", "m0038", "m0041", "m0043", "e0044",
           "m0045", "m0069", "m0073", "m0075", "e0080", "m0081"]

audit = []
for name in ("audit-c910-01.json", "audit-c910-02.json"):
    audit += json.loads((P1014 / "gate" / name).read_text(encoding="utf-8"))
# `chunk` is part of a row's identity, not a label: cand_ids COLLIDE across chunks
# (§10-11 measured 179 distinct ids over 650 rows), and these 12 are chunk 9's.
defect = {short(r["cand_id"]): r for r in audit
          if r["chunk"] == "chunk9" and short(r["cand_id"]) in C6_ROWS}
fixed = {}
for i in (1, 2, 3, 4):
    for q in json.loads((P1014 / "parts" / f"chunk9-part{i}.json").read_text(encoding="utf-8")):
        if short(q["cand_id"]) in C6_ROWS:
            fixed[short(q["cand_id"])] = q

check("both arms of the §10-14 pair are on disk and complete",
      len(defect) == 12 and len(fixed) == 12,
      f"defect {len(defect)} rows, fix {len(fixed)} rows (expected 12 and 12)")

d_flag, d_scope, d_odd = flagged(defect)
f_flag, f_scope, f_odd = flagged(fixed)
check(f"the defect arm flags 8 of 12 (was 3 before this branch existed)",
      d_flag == 8 and d_scope == 12, f"{d_flag} of {d_scope} in scope")
check("the repaired arm flags 0 of 12",
      f_flag == 0 and f_scope == 12, f"{f_flag} of {f_scope} in scope")
# #185 did not move this pair, and could not have moved the defect arm even if the
# rows carried the shape: `build_audit_input.py` writes the blind profile, which has
# no `answer`, so branch 3 is structurally silent on it. Said out loud rather than
# implied, since "0" here means two different things on the two arms.
check("the odd-one-out branch (#185) fires on NEITHER arm of the §10-14 pair",
      d_odd == 0 and f_odd == 0,
      f"defect {d_odd} (blind input carries no `answer` — the branch cannot fire), "
      f"fix {f_odd} (measured WITH the answer)")

# The named row from the issue, asserted on its own so a threshold move that loses
# exactly this shape cannot hide inside an aggregate.
m0073 = score(defect["m0073"])
check("m0073 -- the row in the issue -- is flagged BY THE REMAINDER BRANCH",
      m0073["flagged"] and m0073["remainder"],
      f"shared {m0073['shared']:.2f} worst {m0073['worst']} spread {m0073['spread']}")
check("...and its shared fraction is ABOVE the branch-1 threshold, which is the defect",
      m0073["shared"] > LABEL_SHARED_MAX,
      f"shared {m0073['shared']:.2f} vs LABEL_SHARED_MAX {LABEL_SHARED_MAX}")

# ---------------------------------------------------------------------------
# 2. The §10-10 pair -- the REGRESSION arm. Neither number may move.
# ---------------------------------------------------------------------------
print()
r1 = {short(q["cand_id"]): q
      for q in json.loads((P1010 / "h1-deleak.json").read_text(encoding="utf-8"))}
r2 = {short(q["cand_id"]): q
      for q in json.loads((P1010 / "h1-deleak2.json").read_text(encoding="utf-8"))}
r1_flag, r1_scope, r1_odd = flagged(r1)
r2_flag, r2_scope, r2_odd = flagged(r2)
check("§10-10 round 1 (the #75 defect arm) still flags 7 of 8 in-scope rows",
      (r1_flag, r1_scope) == (7, 8), f"{r1_flag} of {r1_scope}")
check("§10-10 round 2 (the accepted fix) still flags 0 — the negative arm",
      (r2_flag, r2_scope) == (0, 8), f"{r2_flag} of {r2_scope}")
# Both arms carry a real `answer`, so this is the arm where the odd-one-out branch
# COULD have fired and did not: the adjudicated accepted fix stays at zero under all
# three branches, which is what "a union never withdraws and never invents" means here.
check("...and the odd-one-out branch (#185) leaves both §10-10 arms untouched",
      r1_odd == 0 and r2_odd == 0,
      f"round 1 {r1_odd}, round 2 {r2_odd} — measured WITH the answer on both")
# This is the measurement that chose LABEL_REMAINDER_MIN. Dropping `shared` outright
# (i.e. flagging on worst >= 3 alone) finds one more §10-14 row and breaks this arm.
loose = sum(1 for q in r2.values()
            if (d := score(q)) and d["worst"] >= LABEL_UNIQUE_MIN)
check("...and the rejected 'drop the shared conjunct' rule would break it",
      loose == 1,
      "worst>=3 alone flags h0008's accepted fix; this is why the branch needs "
      f"LABEL_REMAINDER_MIN={LABEL_REMAINDER_MIN}, not {LABEL_UNIQUE_MIN}")

# ---------------------------------------------------------------------------
# 3. The §10-16 pair (issue #185) -- four rows the blind pass found and nothing
#    deterministic could reach, plus the one row of that shape branch 1 DID catch.
#
# Inlined rather than read off disk: §10-16 is an open slice and neither
# `parts.bak.c91011` (defect) nor `parts` (fix) is committed. Byte-identical to the
# files, `answer` included. See the docstring.
# ---------------------------------------------------------------------------
print()
P1016_DEFECT = {
    "e0032": {"answer": "D", "options": {
        "A": "15% of respondents visited exactly twice",
        "B": "25% of respondents visited exactly twice",
        "C": "40% of respondents visited exactly twice",
        "D": "20% of the 150 customers visited exactly twice"}},
    "e0053": {"answer": "B", "options": {
        "A": "$3,250, the price after the discount series",
        "B": "$3,420, the net price after the full discount series",
        "C": "$4,000, the price after the discount series",
        "D": "$3,600, the price after the discount series"}},
    "m0054": {"answer": "B", "options": {
        "A": "$6,000, the resulting net invoice price",
        "B": "$6,885, the net invoice price for Meridian Distributors after discounts",
        "C": "$9,000, the resulting net invoice price",
        "D": "$7,650, the resulting net invoice price"}},
    "e0068": {"answer": "C", "options": {
        "A": "$72.80 selling price for the item",
        "B": "$43.08 selling price for the item",
        "C": "$80.00 selling price for the retailer's item",
        "D": "$86.00 selling price for the item"}},
}
P1016_FIXED = {
    "e0032": {"answer": "D", "options": {
        "A": "15% of respondents visited exactly twice",
        "B": "25% of respondents visited exactly twice",
        "C": "40% of respondents visited exactly twice",
        "D": "20% of respondents visited exactly twice"}},
    "e0053": {"answer": "B", "options": {
        "A": "$3,250, the price after the discount series",
        "B": "$3,420, the price after the discount series",
        "C": "$4,000, the price after the discount series",
        "D": "$3,600, the price after the discount series"}},
    "m0054": {"answer": "B", "options": {
        "A": "$6,000, the resulting net invoice price",
        "B": "$6,885, the resulting net invoice price",
        "C": "$9,000, the resulting net invoice price",
        "D": "$7,650, the resulting net invoice price"}},
    "e0068": {"answer": "C", "options": {
        "A": "$72.80 selling price for the item",
        "B": "$43.08 selling price for the item",
        "C": "$80.00 selling price for the item",
        "D": "$86.00 selling price for the item"}},
}
# The control the four rows need. `e0059` is the SAME batch, the SAME shape as far as a
# reader is concerned -- and branch 1 caught it, because its odd option diverges far
# enough to drop `shared` to 0.125. Keeping it here is what stops branch 3 being read
# as "the branch for §10-16 rows": the branches are not interchangeable and the row
# that separates them belongs in the fixture.
P1016_BRANCH1 = {"answer": "D", "options": {
    "A": "28.6% markup on the item's cost",
    "B": "Cost equal to 71.4% of the retail price",
    "C": "140.0% markup on the item's cost",
    "D": "40.0% markup based on the item's original cost"}}

o_flag, o_scope, o_odd = flagged(P1016_DEFECT)
check("the §10-16 defect arm flags 4 of 4 — all by the odd-one-out branch",
      (o_flag, o_scope, o_odd) == (4, 4, 4),
      f"{o_flag} flagged of {o_scope} in scope, {o_odd} by branch 3 "
      "(0 of 4 before it existed)")
p_flag, p_scope, p_odd = flagged(P1016_FIXED)
check("the §10-16 repaired arm flags 0 of 4 — the adjudicated negative",
      (p_flag, p_scope, p_odd) == (0, 4, 0),
      f"{p_flag} flagged of {p_scope} in scope")
# Per row, so a threshold move that keeps the aggregate by trading one row for another
# cannot pass. e0032 and e0068 are the reason there is no word floor beside `spread`.
for cid in ("e0032", "e0053", "m0054", "e0068"):
    d = score(P1016_DEFECT[cid])
    check(f"{cid}: shared {d['shared']:.3f} is ABOVE branch 1's threshold, "
          f"spread {d['spread']} is BELOW branch 2's — which is the hole",
          d["odd_key"] and d["shared"] > LABEL_SHARED_MAX
          and d["spread"] < LABEL_REMAINDER_SPREAD,
          f"worst {d['worst']} word(s) on option {d['odd']}, the key")
d = score(P1016_BRANCH1)
check("§10-16's e0059 is caught by BRANCH 1, not branch 3 — the branches differ",
      d["flagged"] and not d["odd_key"] and d["shared"] < LABEL_SHARED_MAX,
      f"shared {d['shared']:.3f} worst {d['worst']} spread {d['spread']}; its odd "
      "option diverges far enough to drop the shared fraction on its own")

# ---------------------------------------------------------------------------
# 4. Every branch is a UNION -- none can withdraw a row an earlier one finds.
#
# Stated as a property over synthetic rows rather than trusted from the source, since
# the whole value of "no earlier reading is invalidated" rests on it.
# ---------------------------------------------------------------------------
print()
BRANCH_1_ONLY = {  # labels barely overlap, and only ONE option carries leftovers
    "A": "$40,000, the gross margin",
    "B": "$62,500, the contribution per unit before shipping deductions",
    "C": "$12,000, the gross margin",
    "D": "$9,750, the gross margin",
}
d = label_divergence(BRANCH_1_ONLY)
check("a branch-1 row is still flagged, and NOT reported as a remainder row",
      d["flagged"] and not d["remainder"],
      f"shared {d['shared']:.2f} worst {d['worst']} spread {d['spread']}")
# ...and branch 1 still OWNS it when its odd option happens to be the key. The two
# branches genuinely overlap on that row (spread is 1 and the odd option is B), and
# the precedence is the same one `remainder` already takes: whichever branch's finding
# text a reader gets, they get exactly one, and it is branch 1's.
d = label_divergence(BRANCH_1_ONLY, "B")
check("...and branch 1 keeps the row when its odd option IS the key",
      d["flagged"] and not d["odd_key"] and not d["remainder"],
      f"spread {d['spread']} odd {d['odd']} — branch 3 would claim it; branch 1's "
      "reading wins, exactly as branch 2 defers")

PARALLEL = {  # the compliant shape: identical labels, only the number differs
    "A": "$12,750, the total redemption cost for this campaign",
    "B": "$11,250, the total redemption cost for this campaign",
    "C": "$127,500, the total redemption cost for this campaign",
    "D": "$187,500, the total redemption cost for this campaign",
}
d = label_divergence(PARALLEL, "A")
check("four identical labels are clean under all three branches",
      not d["flagged"] and d["worst"] == 0 and d["odd"] is None, f"worst {d['worst']}")

ONE_ODD = {  # one option diverges; the other three are word-identical
    "A": "$12,750, the total redemption cost for this campaign",
    "B": "$11,250, the total redemption cost for this campaign",
    "C": "$127,500, the total redemption cost for this campaign",
    "D": "$187,500, the redemption cost the coordinator first wrote down",
}
# THIS PAIR IS ISSUE #185. The version of this file before it made ONE assertion here
# -- that one odd option does not trip branch 2 -- and explained it away as "branch 1's
# question". It is not: branch 1 needs `shared` LOW and three identical labels drive it
# UP, so nothing answered it at all and §10-16 shipped four rows through the gap. The
# two assertions below are the same row asked twice, and the ANSWER is what separates
# them.
d = label_divergence(ONE_ODD, "A")
check("ONE odd option, and it is a DISTRACTOR: nothing fires, correctly",
      not d["flagged"] and not d["remainder"] and not d["odd_key"],
      f"spread {d['spread']} < LABEL_REMAINDER_SPREAD {LABEL_REMAINDER_SPREAD} so "
      f"branch 2 stays out, and shared {d['shared']:.2f} >= LABEL_SHARED_MAX "
      f"{LABEL_SHARED_MAX} so branch 1 does too — crossing off the option that reads "
      "differently gets a student nowhere here")
d = label_divergence(ONE_ODD, "D")
check("...the SAME row with that odd option as the KEY trips branch 3 (#185)",
      d["flagged"] and d["odd_key"] and not d["remainder"],
      f"spread {d['spread']} == LABEL_ODD_SPREAD {LABEL_ODD_SPREAD} and odd "
      f"{d['odd']} is the key — cover the stem and the row still solves")
check("...and the branch is silent with no answer, so an options-only caller is "
      "unchanged",
      not label_divergence(ONE_ODD)["odd_key"],
      "`answer` is optional; every arm that predates #185 reads what it read before")

# ---------------------------------------------------------------------------
# 5. The finding is ONE line and it routes to the OPTIONS scope, on all three branches.
#
# The remainder and odd-one-out lines are worded differently (neither may quote
# `shared` as "only N% is common" -- that is the number that HID the defect in both
# cases), so each is a separate string and has to be checked separately. The
# odd-one-out line is the one at risk: it says "cover the stem", and a stem word in a
# finding is how a row gets scoped to `question` by accident.
# ---------------------------------------------------------------------------
print()
BRANCH_2_LINE = (
    "options do not describe the same quantity in the same words — they share a "
    "label (33% of the wording is common to all four) and are then told apart by "
    "what trails it: option A (4: after, calculation, intern, third). Delete the "
    "trailing clauses; make every label identical and let only the number differ")
BRANCH_1_LINE = (
    "options do not describe the same quantity in the same words (only 12% of the "
    "label wording is common to all four; option C (5: amount, itself, markup, "
    "relative)) — an option a student can tell apart by reading; make every label "
    "identical and let only the number differ")
BRANCH_3_LINE = (
    "options do not describe the same quantity in the same words — three of the four "
    "labels carry no wording of their own and THE ODD ONE IS THE KEY: option D (1: "
    "customers). Cover the stem and the row still solves — pick the option that reads "
    "differently. Make every label identical and let only the number differ")
for label, line in (("branch 1", BRANCH_1_LINE), ("branch 2", BRANCH_2_LINE),
                    ("branch 3", BRANCH_3_LINE)):
    check(f"the {label} finding routes to the OPTIONS scope",
          finding_scope([line]) == ("options",),
          f"finding_scope -> {finding_scope([line])}")

# ---------------------------------------------------------------------------
# 6. The committed-bank baseline the gate prints.
#
# NOT a gate: a quarter of the bank's label rows legitimately trip this, because
# "$43,000 in cost of goods sold / $45,000 in COGS" really does break the rule. What
# is pinned is that the PRINTED baseline still describes the bank -- and it has now
# gone stale TWICE. #153 found 23.9% stale by 4.5pp as the bank grew 700 -> 893 label
# rows and added this check; #185 then found 19.6% stale by 2.8pp at 1,060 rows, with
# this check FAILING and nobody having run it. A rate quoted in a gate line and
# measured nowhere is how that happens; a rate measured only by a fixture nobody runs
# is how it happens twice.
# ---------------------------------------------------------------------------
print()
rows = []
keys = []   # the keyed letter beside each row, for the branch-3 census in section 7
for path in sorted(BANK_DIR.glob("*/*.json")):
    if path.name == "manifest.json":
        continue
    for q in json.loads(path.read_text(encoding="utf-8")):
        d = score(q)
        if d:
            rows.append(d)
            keys.append(str(q.get("answer", "")).strip().upper())
rate = 100.0 * sum(1 for d in rows if d["flagged"]) / len(rows) if rows else 0.0
check(f"the printed baseline {BANK_LABEL_DIVERGENCE_RATE:.1f}% still describes the "
      f"bank (measured {rate:.1f}% of {len(rows)} label rows)",
      bool(rows) and abs(rate - BANK_LABEL_DIVERGENCE_RATE) <= 2.0,
      "update BANK_LABEL_DIVERGENCE_RATE if this drifted legitimately")
# The widening that was measured and rejected, asserted so re-proposing it is loud.
# This is the ONLY setting that reaches the 1-2 word trailing clause -- a leftover
# threshold of 2 with no other condition -- and it takes half the bank with it.
loose_rate = 100.0 * sum(1 for d in rows if d["worst"] >= 2) / len(rows)
loose_hits = sum(1 for q in defect.values()
                 if (d := score(q)) and d["worst"] >= 2)
# Anchored to the PRINTED BASELINE rather than to an absolute percentage, because both
# numbers move with the corpus and only their ratio carries the claim. The absolute bar
# was 40.0, written when the loose rate measured 44.1%; §10-17's repair took the loose
# rate to 38.7% and the baseline to 20.2%, so the absolute bar failed while the claim it
# stands for -- "this setting flags most of the bank" -- got STRONGER (1.9x the real
# rate, up from 1.7x). A drifting absolute is exactly what #188 says not to write down.
check("a leftover threshold of 2 is unreadable, as measured",
      loose_rate > 1.5 * BANK_LABEL_DIVERGENCE_RATE and loose_hits == 11,
      f"it would flag {loose_rate:.1f}% of the bank's label rows — "
      f"{loose_rate / BANK_LABEL_DIVERGENCE_RATE:.1f}x the printed "
      f"{BANK_LABEL_DIVERGENCE_RATE:.1f}% baseline — to reach "
      f"{loose_hits} of §10-14's 12 known rows instead of 8")

# ---------------------------------------------------------------------------
# 7. Branch 3's own corpus measurement, and the widening it rejects (#185).
#
# The branch costs the printed rate ~10pp, so the evidence for it belongs here rather
# than only in a comment: the class is a REAL corpus-wide tell, and the cheaper way to
# reach it -- LABEL_REMAINDER_SPREAD of 1, i.e. drop the `answer` condition -- is not.
# ---------------------------------------------------------------------------
print()
# Counted RAW -- `d["odd"] == key`, before branch 1's precedence takes any row away --
# because the question here is whether the CLASS is real, not which branch reports it.
spread1 = [(d, k) for d, k in zip(rows, keys) if d["spread"] == LABEL_ODD_SPREAD]
odd_key = [(d, k) for d, k in spread1 if d["odd"] == k]
odd_rate = 100.0 * len(odd_key) / len(spread1) if spread1 else 0.0
# THE p-VALUE IS COMPUTED, NOT TRANSCRIBED (#188), and finding out why is the point.
# It was written into this message as the literal "p = 3.75e-04" when the branch landed
# at n=329 / k=110, and it has been WRONG on a PASSING assertion ever since the bank
# moved: n=353 gives 5.2e-03, and §10-17's repair takes it to n=362 / k=108 and
# p=2.1e-02. The class is still real and still above chance, but the evidence is a
# hundred times weaker than the number this fixture kept printing -- and #185 already
# recorded that a fixture pinning a wrong claim is a passing test standing exactly where
# the hole is. The bar is therefore the CLAIM (above chance, significant at 0.05) rather
# than the rate the branch happened to be calibrated at.
#
# §10-17 is also WHY it moved, which is worth knowing before the next reword: levelling
# four labels moves rows INTO `spread == 1`, and levelling them correctly puts the
# residual divergence on a DISTRACTOR — so a repair that does exactly what the rule asks
# dilutes the very statistic the branch is measured on.
p_odd = sum(comb(len(spread1), i) * 0.25 ** i * 0.75 ** (len(spread1) - i)
            for i in range(len(odd_key), len(spread1) + 1)) if spread1 else 1.0
check("the odd option is the KEY above the 25% chance floor — the branch is "
      "measured, not chosen",
      len(spread1) > 300 and odd_rate > 25.0 and p_odd < 0.05,
      f"{len(odd_key)} of {len(spread1)} `spread == 1` rows ({odd_rate:.1f}%) against "
      f"25.0% chance; one-sided binomial n={len(spread1)} p=0.25 gives p = {p_odd:.2e}")
wide_rate = 100.0 * len(spread1) / len(rows)
check("dropping the `answer` condition is the widening that was rejected",
      wide_rate > 25.0 and len(spread1) - len(odd_key) > 150,
      f"LABEL_REMAINDER_SPREAD=1 would flag every `spread == 1` row — {wide_rate:.1f}% "
      f"of the bank's label rows — including the {len(spread1) - len(odd_key)} where a "
      "DISTRACTOR is the odd one out, which a student cannot act on")

# ---------------------------------------------------------------------------
# What this fixture does NOT check -- state it, don't imply coverage.
#
#  * That a flagged row IS defective. It is not; the rate is the finding and the rows
#    are candidates for a reader. Same terms as every other soft here.
#  * That the instrument catches the class. It catches the class down to a clause of
#    3-4 content words. §10-14's `e0080` ("...the promotional budget on the draft")
#    carries ONE leftover token and is out of reach at any readable threshold -- 3 of
#    the 12 known rows are, and chunk 10 still reads below baseline. The gate prints
#    that limit on every run; this fixture pins the printed baseline, not the recall.
#  * That the arms are independent evidence. Each defect arm is the batch its own
#    branch was built from -- 8 of 12 on §10-14, 4 of 4 on §10-16 -- so neither is
#    evidence of recall on a shape nobody has written yet. The §10-10 pair is the arm
#    that constrains, because no branch has been allowed to move it.
#  * THAT THE INSTRUMENT NOW COVERS THE CLASS. It has been holed twice, both times by
#    a shape sitting between two branches that were each internally consistent, and
#    both times the rows were found by an unscoped BLIND PASS and by nothing
#    deterministic. §10-16's four rows shipped past a gate reading ABOVE its baseline:
#    a rate above baseline is no more a coverage statement than 0.0% is.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
