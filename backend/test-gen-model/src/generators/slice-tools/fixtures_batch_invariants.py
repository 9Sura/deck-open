#!/usr/bin/env python3
"""Pin check_batch_invariants.py's behaviour. No model, no network.

WHY: §10-12's lesson was that a gate's behaviour asserted only in a comment drifts
(issue #88 -- the rule-5 combination guard was wrong in BOTH directions while a
comment claimed otherwise). So every claim the module docstring makes is asserted
here, including the two NEGATIVE ones: that the cross-row check fires on real
contamination, and that no superset check exists to fire on rule-13 rows.

    python slice-tools/fixtures_batch_invariants.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_batch_invariants as cbi  # noqa: E402

FAILS = []


def row(cid, question, options, answer="A", difficulty="easy", pi="Some PI",
        area="Selling", explanation="Because."):
    return {"cand_id": cid, "question": question, "options": options, "answer": answer,
            "difficulty": difficulty, "performanceIndicator": pi, "instructionalArea": area,
            "explanation": explanation, "_file": "fixture.json"}


def run(label, rows, payload=None, expect_blocking=None, expect_advisory_substr=None,
        forbid_advisory_substr=None):
    blocking, advisory = cbi.check(rows, payload or {}, 0.82, "fixture")
    if expect_blocking is not None:
        hits = [b for b in blocking if expect_blocking in b]
        if not hits:
            FAILS.append(f"{label}: expected a BLOCKING finding containing {expect_blocking!r}; "
                         f"got {blocking!r}")
    if expect_blocking is None and blocking:
        FAILS.append(f"{label}: expected NO blocking findings, got {blocking!r}")
    if expect_advisory_substr:
        if not any(expect_advisory_substr in a for a in advisory):
            FAILS.append(f"{label}: expected an ADVISORY containing "
                         f"{expect_advisory_substr!r}; got {advisory!r}")
    if forbid_advisory_substr:
        bad = [a for a in advisory if forbid_advisory_substr in a]
        if bad:
            FAILS.append(f"{label}: advisory should NOT contain "
                         f"{forbid_advisory_substr!r}; got {bad!r}")
    return blocking, advisory


# --- 1. THE m0048 CASE: the same option text in two different rows ------------
# This is the defect the file exists for. Two rows, each individually well-formed;
# the contamination is only visible BETWEEN them.
CONTAM = "The manager should let the insurance carrier make this decision"
run("cross-row contamination",
    [row("cand-m0048", "A company has $50,000 in surplus cash to deploy.",
         {"A": "The higher return reflects that greater risk of loss",
          "B": CONTAM,
          "C": "Both options carry exactly the same real risk",
          "D": "Guaranteed returns are always the better choice here"}),
     row("cand-m0057", "A chemical distributor discovers a slow leak from a storage tank.",
         {"A": "The company should weigh residents' risk beyond the legal minimum",
          "B": CONTAM,
          "C": "The company should halt shipments immediately to repair it",
          "D": "Legality alone settles the question for the plant manager"})],
    expect_blocking="CROSS-ROW duplicate option")

# A short shared option is NOT contamination -- two items may both offer
# "Brainstorming". Below the 18-char floor, so it must stay silent.
run("short shared option is not contamination",
    [row("cand-a", "Which technique generates ideas?",
         {"A": "Brainstorming", "B": "Auditing", "C": "Invoicing", "D": "Shipping"}),
     row("cand-b", "Which technique opens a session?",
         {"A": "Brainstorming", "B": "Filing", "C": "Costing", "D": "Packing"})])

# --- 2. NO SUPERSET CHECK on rule-13 rows -------------------------------------
# Digit-suffix collision: '20% markup based on cost' inside '120% markup based on
# cost'. Naive containment called this a superset. It is not.
run("rule-13 row with digit-suffix collision is silent",
    [row("cand-e0031", "A boutique buys a scarf for $30 and sells it for $36.",
         {"A": "16.67% markup based on cost", "B": "20% markup based on cost",
          "C": "120% markup based on cost", "D": "6% markup based on cost"}, answer="B")],
    forbid_advisory_substr="SUPERSET")

# Trailing-qualifier containment -- the 30%-of-batch false positive. Also silent.
run("trailing qualifier is not a superset",
    [row("cand-e0025", "What is the cost per acquisition?",
         {"A": "$60 per new member acquired this campaign month",
          "B": "$2,400 per new member acquired", "C": "$80 per new member acquired",
          "D": "$30 per new member acquired"})],
    forbid_advisory_substr="SUPERSET")

# --- 3. Within-row duplicate options (rule 13a) is BLOCKING -------------------
run("duplicate options within a row",
    [row("cand-dup", "Stem.", {"A": "The same text here", "B": "The same text here",
                               "C": "Another option entirely", "D": "A fourth option"})],
    expect_blocking="are the same text")

# --- 4. Answer letter vs the payload's assignment -----------------------------
run("answer letter off its assignment",
    [row("cand-x", "Stem.", {"A": "One", "B": "Two", "C": "Three", "D": "Four"}, answer="A")],
    payload={"cand-x": {"cand_id": "cand-x", "answer_letter": "C"}},
    expect_blocking="the payload assigned C")

run("answer letter matching its assignment is silent",
    [row("cand-x", "Stem.", {"A": "One", "B": "Two", "C": "Three", "D": "Four"}, answer="C")],
    payload={"cand-x": {"cand_id": "cand-x", "answer_letter": "C"}})

# --- 5. Decimal odd-one-out, both directions ----------------------------------
run("key is the only option WITH a decimal",
    [row("cand-h0007", "Set the price.",
         {"A": "$40 per pair", "B": "$50 per pair", "C": "$62.50 per pair", "D": "$60 per pair"},
         answer="C")],
    expect_advisory_substr="DECIMAL-ODD")

run("key is the only option WITHOUT a decimal",
    [row("cand-h0005", "Find the markup.",
         {"A": "A 27.5% markup", "B": "A 50% markup", "C": "A 8.4% markup", "D": "A 33.3% markup"},
         answer="B")],
    expect_advisory_substr="DECIMAL-ODD")

# A DISTRACTOR being the decimal outlier is not a free pick toward the key.
run("decimal outlier on a distractor is silent",
    [row("cand-ok", "Find the markup.",
         {"A": "A 27.5% markup", "B": "A 50% markup", "C": "A 80% markup", "D": "A 33% markup"},
         answer="B")],
    forbid_advisory_substr="DECIMAL-ODD")

# --- 6. Rule 13b needs judgement, so it is ADVISORY, never blocking -----------
run("13b fires when the key's figure is printed in the stem",
    [row("cand-h0006", "Elm Row prices the pan at $50 on the retail floor.",
         {"A": "A 100% margin", "B": "A 50% margin", "C": "A 56% margin", "D": "A 44% margin"},
         answer="B")],
    expect_advisory_substr="13b")

# --- 7. Near-duplicate stems (the sixth author assertion) ---------------------
run("near-duplicate stems across the batch",
    [row("cand-1", "A landscaping company earns most of its revenue from a single large client.",
         {"A": "One", "B": "Two", "C": "Three", "D": "Four"}),
     row("cand-2", "A landscaping company earns most of its revenue from one large client.",
         {"A": "Five", "B": "Six", "C": "Seven", "D": "Eight"})],
    expect_advisory_substr="NEAR-DUP STEM")

# --- 8. THE COLLISION GUARD --------------------------------------------------
# cand_ids restart per payload, so the same id names different questions in
# different chunks. Checking multi-chunk parts against ONE payload compared every
# row to the wrong spec and produced 25 false "letter mismatches" on §10-12's
# shipped batch. The guard must REFUSE, not report.
def _collision_guard():
    dup_a = row("cand-e0019", "A toy company had $40,000 in sales.",
                {"A": "One", "B": "Two", "C": "Three", "D": "Four"}, answer="D")
    dup_a["_file"] = "chunk10-part3.json"
    dup_b = row("cand-e0019", "A competitor spreads false statements about a retailer.",
                {"A": "Five", "B": "Six", "C": "Seven", "D": "Eight"}, answer="C")
    dup_b["_file"] = "chunk9-part1.json"
    payload = {"cand-e0019": {"cand_id": "cand-e0019", "answer_letter": "D"}}
    try:
        cbi.check([dup_a, dup_b], payload, 0.82, "fixture")
    except SystemExit as exc:
        if "REFUSING the answer-letter check" not in str(exc):
            FAILS.append(f"collision guard: refused with the wrong message: {exc}")
        return
    FAILS.append("collision guard: a colliding cand_id with a payload MUST refuse, but it did not")


def _no_collision_no_refusal():
    # Same id twice in the SAME file is not a cross-chunk collision; and without a
    # payload there is nothing to mis-scope, so the batch must still run.
    a = row("cand-x", "Stem one.", {"A": "One", "B": "Two", "C": "Three", "D": "Four"})
    b = row("cand-x", "Stem two.", {"A": "Five", "B": "Six", "C": "Seven", "D": "Eight"})
    a["_file"] = b["_file"] = "chunk9-part1.json"
    try:
        cbi.check([a, b], {}, 0.82, "fixture")
    except SystemExit as exc:
        FAILS.append(f"no-payload run must never refuse, but it did: {exc}")


_collision_guard()
_no_collision_no_refusal()

if FAILS:
    print(f"\n  {len(FAILS)} FIXTURE FAILURE(S):")
    for f in FAILS:
        print(f"    - {f}")
    raise SystemExit(1)
print("  all check_batch_invariants fixtures pass")
