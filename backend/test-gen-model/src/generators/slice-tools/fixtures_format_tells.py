#!/usr/bin/env python3
"""Pin the format tells that sit under DECIMAL-ODD (issue #174). No model, no network.

WHY A FIXTURE: the repo rule is that a gate's behaviour asserted only in a comment
drifts (issue #88 -- the rule-5 combination guard was wrong in BOTH directions
while a comment claimed otherwise). check_batch_invariants' docstring now carries
three measured verdicts, two of them POSITIVE and one NEGATIVE, and the negative
one is the fragile one: "lone non-round cents is at chance, do not gate it" is
exactly the kind of decision a later reader re-litigates because the class LOOKS
like the two beside it. It is asserted here so re-adding it fails a test.

The two defect rows are §10-14 H1's, reproduced from the issue verbatim -- both
had already passed every deterministic gate when a blind solver named them.

    python slice-tools/fixtures_format_tells.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_batch_invariants as cbi  # noqa: E402

FAILS = []


def row(cid, options, answer="A", question="A retailer reviews its pricing."):
    return {"cand_id": cid, "question": question, "options": options, "answer": answer,
            "difficulty": "hard", "performanceIndicator": "Some PI",
            "instructionalArea": "Selling", "explanation": "Because.", "_file": "fixture.json"}


def advisories(rows):
    blocking, advisory = cbi.check(rows, {}, 0.82, "fixture")
    if blocking:
        FAILS.append(f"unexpected BLOCKING findings on a fixture row: {blocking!r}")
    return advisory


def expect(label, rows, substr):
    adv = advisories(rows)
    if not any(substr in a for a in adv):
        FAILS.append(f"{label}: expected an advisory containing {substr!r}; got {adv!r}")


def forbid(label, rows, substr):
    adv = advisories(rows)
    bad = [a for a in adv if substr in a]
    if bad:
        FAILS.append(f"{label}: advisory should NOT contain {substr!r}; got {bad!r}")


# --- 1. THE ARTICLE TELL: §10-14 h0014, solved cold by a blind solver ---------
# "An" agrees with the vowel sound of *eighty*. The article alone names the key,
# with no arithmetic done at all.
H0014 = row("h0014", {
    "A": "An $80 keystone selling price for the seasonal line",
    "B": "A $70 keystone selling price for the seasonal line",
    "C": "A $75 keystone selling price for the seasonal line",
    "D": "A $60 keystone selling price for the seasonal line"}, answer="A")
# The row appears in the roll-up by cand_id -- NOT merely in a count. A gate that
# reports a number and no rows sends the next repair round hunting (#127).
expect("h0014 named in the roll-up", [H0014], "rows: h0014")
# ...and it is ITEMISED as LIVE: all four carry an article and only the key's
# differs. That escalation is the whole difference between the construction rule
# and the defect, so it is asserted separately -- and it must carry the options,
# since the roll-up deliberately does not.
expect("h0014 is itemised LIVE", [H0014], "ARTICLE-NUMERAL LIVE  h0014")
expect("the LIVE row carries its options", [H0014], "An $80 keystone selling price")

# THE PRESCRIBED REWRITE MUST BE CLEAN. If it were not, the rule in
# authoring-concept.txt 13c would be telling an author to swap one flag for
# another, and the check would be un-satisfiable rather than constructive.
forbid("the rewrite is clean", [row("h0014fix", {
    "A": "A keystone selling price of $80 for the seasonal line",
    "B": "A keystone selling price of $70 for the seasonal line",
    "C": "A keystone selling price of $75 for the seasonal line",
    "D": "A keystone selling price of $60 for the seasonal line"}, answer="A")],
    "ARTICLE-NUMERAL")

# THE FORM IS FLAGGED EVEN WHEN IT IS NOT YET LIVE -- one option carrying it, the
# other three not. This is the construction half of the rule and it is deliberate:
# a number changed in a later repair round re-creates the leak in a row nobody
# re-reads. It must NOT carry the LIVE escalation.
NOT_LIVE = [row("h0100", {
    "A": "A 12% markup on the wholesale cost",
    "B": "Twelve percent added to the wholesale cost",
    "C": "Markup of twelve percent over wholesale",
    "D": "Wholesale cost plus one-eighth"}, answer="A")]
expect("bare form still named", NOT_LIVE, "rows: h0100")
forbid("bare form is not itemised LIVE", NOT_LIVE, "ARTICLE-NUMERAL LIVE")

# AND THE ODD ARTICLE ON A DISTRACTOR IS NOT LIVE EITHER. The tell is that the
# article names THE KEY; an odd article on a wrong option costs the student
# nothing. Same escalation boundary, from the other side.
forbid("odd article on a distractor is not LIVE", [row("h0101", {
    "A": "A $70 keystone selling price for the seasonal line",
    "B": "An $80 keystone selling price for the seasonal line",
    "C": "A $75 keystone selling price for the seasonal line",
    "D": "A $60 keystone selling price for the seasonal line"}, answer="A")],
    "ARTICLE-NUMERAL LIVE")

# THE ROLL-UP IS WHAT KEEPS THE REPORT READABLE, and that is measured, not tidy:
# §10-14's H1 carries the form on 19 of 21 rows because it is an AUTHOR HABIT, and
# itemising all 19 with their options buries the one LIVE row under 76 option
# lines. Twelve carrier rows must produce ONE roll-up plus one itemised LIVE row.
MANY = [row(f"h02{i:02d}", {
    "A": f"A ${100 + i} net price for the order this season",
    "B": f"A ${200 + i} net price for the order this season",
    "C": f"A ${300 + i} net price for the order this season",
    "D": f"A ${400 + i} net price for the order this season"}, answer="A")
    for i in range(12)] + [H0014]
adv = advisories(MANY)
rollups = [a for a in adv if a.startswith("ARTICLE-NUMERAL  ")]
lives = [a for a in adv if a.startswith("ARTICLE-NUMERAL LIVE  ")]
if len(rollups) != 1:
    FAILS.append(f"13 carrier rows must produce exactly ONE roll-up line; got {len(rollups)}")
if len(lives) != 1:
    FAILS.append(f"13 carrier rows with one live tell must itemise exactly ONE; got {len(lives)}")
if rollups and "13 row(s)" not in rollups[0]:
    FAILS.append(f"the roll-up must carry the carrier COUNT; got {rollups[0]!r}")
if rollups and "100.0%" not in rollups[0]:
    FAILS.append("the roll-up must carry the batch RATE over four-quantity rows; got "
                 f"{rollups[0]!r}")
if rollups and "bank baseline 12.2%" not in rollups[0]:
    FAILS.append("the roll-up must print the bank baseline beside the batch rate, or the rate "
                 f"is unreadable; got {rollups[0]!r}")


# --- 2. THE PRECISION TELL: §10-14 h0005, named by two blind solvers ----------
# All four carry a decimal, so DECIMAL-ODD's 1-of-4 / 3-of-4 split never fires --
# yet 8.0 is visibly the clean one.
H0005 = row("h0005", {
    "A": "About 8.0 inventory turns for the quarter",
    "B": "About 9.88 inventory turns for the quarter",
    "C": "About 8.78 inventory turns for the quarter",
    "D": "About 9.13 inventory turns for the quarter"}, answer="A")
expect("h0005 fires", [H0005], "DECIMAL-PRECISION  h0005")
# DECIMAL-ODD MUST STAY SILENT ON IT. If it fired, the new check would be a
# duplicate report rather than the gap-filler it is documented as.
forbid("h0005 is not a DECIMAL-ODD row", [H0005], "DECIMAL-ODD")

# THE TRAILING ZERO IS THE POINT. Counting raw characters scores 8.0 at one place
# and hides it among the two-place options -- rstrip("0") is what makes it zero.
if cbi.decimal_places("About 8.0 turns") != 0:
    FAILS.append("decimal_places('8.0') must strip the trailing zero and read 0 places")
if cbi.decimal_places("About 9.88 turns") != 2:
    FAILS.append("decimal_places('9.88') must read 2 places")
if cbi.decimal_places("About 8 turns") is not None:
    FAILS.append("decimal_places on a row with no decimal must read None, not 0 -- an "
                 "integer option is DECIMAL-ODD's business, not this check's")

# FOUR EQUALLY PRECISE OPTIONS ARE CLEAN. There is no odd one out, so nothing to
# read off, whatever the values are.
forbid("uniform precision is clean", [row("h0102", {
    "A": "About 8.02 inventory turns for the quarter",
    "B": "About 9.88 inventory turns for the quarter",
    "C": "About 8.78 inventory turns for the quarter",
    "D": "About 9.13 inventory turns for the quarter"}, answer="A")], "DECIMAL-PRECISION")

# THE CLEANEST OPTION ON A DISTRACTOR IS NOT A TELL, on DECIMAL-ODD's own
# precedent -- that check reports only when the minority IS the key.
forbid("cleanest distractor is not reported", [row("h0103", {
    "A": "About 9.88 inventory turns for the quarter",
    "B": "About 8.0 inventory turns for the quarter",
    "C": "About 8.78 inventory turns for the quarter",
    "D": "About 9.13 inventory turns for the quarter"}, answer="A")], "DECIMAL-PRECISION")

# DECIMAL-ODD IS UNCHANGED. The new check must not have moved the old one's
# 1-of-4 behaviour, which is what §10-12 calibrated it on.
expect("DECIMAL-ODD still fires on a 1-of-4 split", [row("h0104", {
    "A": "$62.50 per unit shipped",
    "B": "$40 per unit shipped",
    "C": "$50 per unit shipped",
    "D": "$60 per unit shipped"}, answer="A")], "DECIMAL-ODD  h0104")


# --- 3. THE NEGATIVE ASSERTION: lone non-round cents is NOT gated -------------
# Issue #174's third tell. Measured at 29.41% over 34 bank rows (p=0.34) -- at
# chance -- and the only fix is renumbering the stem, which risks a real
# arithmetic error to chase a non-signal. THIS ROW MUST STAY UNFLAGGED. It is
# §10-14 h0007 verbatim.
H0007 = row("h0007", {
    "A": "$547.20 in total landed cost for the order",
    "B": "$608.00 in total landed cost for the order",
    "C": "$576.00 in total landed cost for the order",
    "D": "$520.00 in total landed cost for the order"}, answer="A")
for marker in ("CENTS", "NON-ROUND"):
    forbid(f"cents tell is declined ({marker})", [H0007], marker)
# It is not caught incidentally either: every option carries two decimal places,
# so the precision check reads no odd one out, and all four carry a decimal so
# DECIMAL-ODD is silent. If a future edit makes either fire on this row, the
# declined class has been gated by accident.
for marker in ("DECIMAL-PRECISION", "DECIMAL-ODD"):
    forbid(f"cents row stays clean under {marker}", [H0007], marker)


# --- 4. THE NEGATIVE ASSERTION: no broad article check -----------------------
# Issue #174's headline (34% key rate, 1,229 rows) reproduces, but splitting it
# shows the signal is 164 of 472 rows where the article precedes a WORD -- one
# option worded differently from the other three, with the key being that option.
# That is label_divergence's defect, already instrumented. A broad article check
# here would re-report it under a name that misattributes the mechanism.
forbid("no broad article check", [row("h0105", {
    "A": "An allowance granted to the retailer at the end of the season",
    "B": "A discount granted to the retailer at the end of the season",
    "C": "A rebate granted to the retailer at the end of the season",
    "D": "A markdown granted to the retailer at the end of the season"}, answer="A")],
    "ARTICLE")


# --- 5. THE RATE IS NOT THE JUSTIFICATION, and the message must say so --------
# The article check is defended as a CONSTRUCTION rule: its own bank tell rate is
# 3 of 13 (23.1%), BELOW the 25% chance floor. The precision check is defended by
# a number that is suggestive and not significant. Both messages have to carry
# their honest status or a reader takes the row list as a work order -- the same
# calibration failure label_divergence documents at 19.6%.
adv = advisories([H0005])
if not any("p=0.07" in a and "suggestive not significant" in a for a in adv):
    FAILS.append("DECIMAL-PRECISION must print its baseline AND its honest significance; "
                 f"got {adv!r}")
adv = advisories([H0014])
if not any("a CONSTRUCTION rule, not a rate" in a and "rewrite as" in a for a in adv):
    FAILS.append("ARTICLE-NUMERAL must name itself a construction rule AND print the rewrite, "
                 f"since its own tell rate is below chance; got {adv!r}")


if FAILS:
    print(f"\n  {len(FAILS)} FIXTURE FAILURE(S)\n")
    for f in FAILS:
        print(f"    - {f}")
    raise SystemExit(1)
print("\n  format-tell fixtures: all assertions hold "
      "(article construction rule, decimal precision, cents DECLINED, no broad article check)\n")
