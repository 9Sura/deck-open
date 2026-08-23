"""Issue #139 fixtures: the AIM ladder's own targets must not read as author defects.

THE DEFECT. `build_area._ladder` hands the key whatever rung its rank draws, and
`build_question_bank.check_question` then scores the realised key/distractor ratio. The
two were never checked against each other, and on four (tier, rung) cells the ratio the
ladder DESIGNS is at or past a soft's threshold -- so the gate fires on an author whose
deviation from its assignment is zero. §10-14's `mkt-district-pool-cand-e0025` is the
clean case: `AIM D~18` on the easy bottom rung, realised D=18, flagged for a reverse
length tell. 46 such rows across §10-10 to §10-13, in no summary, plan or findings file.

#74 is the precedent and this is its unaddressed half -- it inset the ladder, which
moved the easy bottom rung from 0.360x (below 0.45, firing on EVERY such row by design)
to 0.474x, i.e. from "always" to "on 2ch of drift".

WHY A FIXTURE. #88/#89/#127's rule, and #88 is the exact shape: the combination-option
predicate was wrong in both directions because its behaviour lived in a comment on one
side and in a regex on the other. This filter spans two modules and matches on message
SUBSTRINGS, so a reworded message would silently disarm it. Section 1 below is the guard
against precisely that -- it reads the markers off strings `check_question` really emits.

NON-VACUITY. Every suppression case is paired with a near-identical row that must still
be flagged, so a filter that has quietly become unconditional fails here rather than
passing for the wrong reason. Section 3 walks all 12 (tier, rung) cells against the real
`_ladder`, so a future inset change that opens or closes a cell shows up as a diff here.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_ladder_assigned_softs.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, never hardcoded.
"""
import sys
import tempfile
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
import build_area as ba  # noqa: E402
import build_question_bank as bqb  # noqa: E402
import build_repair_prompt as brp  # noqa: E402
import check_authored as ca  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def opts_of(lengths):
    """Four option texts of exactly the given lengths, keyed A-D and all distinct."""
    return {k: (k.lower() * n)[:n] for k, n in zip("ABCD", lengths)}


def ranked_spec(tier, rank):
    """The payload `build_area.py` writes for a RANKED row of this tier and rank."""
    band = ba.BANDS[tier]
    tl = ba.target_lengths(band, rank)
    return {"answer_letter": "A", "difficulty": tier, "option_length_band": list(band),
            "key_target_len": tl["key"], "distractor_target_lens": tl["distractors"],
            "max_top_gap": ba.MAX_TOP_GAP}


print("\n[1] THE MARKERS ARE READ OFF STRINGS check_question REALLY EMITS")
print("    A reworded message must break this file, not the filter.\n")

# A row whose key towers over its distractors -> the 1.5x giveaway soft. 50/30 = 1.67x,
# deliberately UNDER 2.2x: past that it is a hard drop and no soft is emitted at all.
_, soft_giveaway = bqb.check_question({
    "question": "Which pricing approach sets price from the cost of production plus a "
                "fixed percentage added on top of that cost figure?",
    "options": opts_of([50, 30, 30, 30]),
    "answer": "A", "explanation": "x" * 80, "difficulty": "easy",
    "instructionalArea": "Pricing", "performanceIndicator": "Explain the nature of pricing",
}, require_difficulty=True)
# ...and the mirror, a conspicuously short key -> the reverse soft.
_, soft_reverse = bqb.check_question({
    "question": "Which pricing approach sets price from the cost of production plus a "
                "fixed percentage added on top of that cost figure?",
    "options": opts_of([15, 60, 55, 50]),
    "answer": "A", "explanation": "x" * 80, "difficulty": "easy",
    "instructionalArea": "Pricing", "performanceIndicator": "Explain the nature of pricing",
}, require_difficulty=True)

hit_g = [m for m in soft_giveaway if bqb.SOFT_LENGTH_GIVEAWAY_RATIO in m]
hit_r = [m for m in soft_reverse if bqb.SOFT_REVERSE_TELL in m]
check("SOFT_LENGTH_GIVEAWAY_RATIO appears in the emitted giveaway message",
      len(hit_g) == 1, f"marker {bqb.SOFT_LENGTH_GIVEAWAY_RATIO!r} in {hit_g}")
check("SOFT_REVERSE_TELL appears in the emitted reverse message",
      len(hit_r) == 1, f"marker {bqb.SOFT_REVERSE_TELL!r} in {hit_r}")
check("the marker is DERIVED from the ratio, so it cannot go stale",
      bqb.SOFT_LENGTH_GIVEAWAY_RATIO == f"(>{bqb.LENGTH_GIVEAWAY_RATIO}x)",
      bqb.SOFT_LENGTH_GIVEAWAY_RATIO)

# The >=20ch absolute margin shares the giveaway message's LEADING words. If the marker
# were the prefix rather than the tail, suppressing one would suppress the other -- and
# that soft is never assignment-caused (designed top gap is 10ch easy / 13ch medium).
# 60 vs 40/40/40 is the only shape that reaches it: the branch is an `elif`, so the gap
# rule is only consulted when the ratio (here exactly 1.5x) does NOT fire.
_, soft_margin = bqb.check_question({
    "question": "Which pricing approach sets price from the cost of production plus a "
                "fixed percentage added on top of that cost figure?",
    "options": opts_of([60, 40, 40, 40]),
    "answer": "A", "explanation": "x" * 80, "difficulty": "easy",
    "instructionalArea": "Pricing", "performanceIndicator": "Explain the nature of pricing",
}, require_difficulty=True)
margin_msgs = [m for m in soft_margin if ">=20ch" in m]
check("the >=20ch margin soft fires and carries NEITHER ratio marker",
      len(margin_msgs) == 1
      and bqb.SOFT_LENGTH_GIVEAWAY_RATIO not in margin_msgs[0]
      and bqb.SOFT_REVERSE_TELL not in margin_msgs[0],
      margin_msgs[0] if margin_msgs else "not emitted")


print("\n[2] THE TWO CONDITIONS, EACH PAIRED WITH THE ROW THAT MUST STILL BE FLAGGED\n")

# §10-14 e0025, reconstructed: --free-rank shape, key on the easy bottom rung, author
# exactly on target, distractors drifted long. THE case the issue was filed for.
easy_ladder = ba._ladder(ba.BANDS["easy"])
e0025 = {"answer_letter": "D", "difficulty": "easy",
         "option_length_band": list(ba.BANDS["easy"]),
         "longest_letter": "C", "key_may_be_longest": False,
         "option_target_lens": {"A": easy_ladder[1], "B": easy_ladder[2],
                                "C": easy_ladder[0], "D": easy_ladder[3]}}
caused = ca.assignment_caused_softs(e0025, opts_of([39, 46, 52, 18]), "D")
check("e0025 (easy bottom rung, key 0ch off AIM, distractors +7.7ch) is suppressed",
      caused == {bqb.SOFT_REVERSE_TELL},
      f"AIM D~{easy_ladder[3]}, realised 18 -> {sorted(caused)}")

# Condition 2: the SAME cell, but the author missed its own target. Real drift.
caused = ca.assignment_caused_softs(e0025, opts_of([39, 46, 52, 6]), "D")
check("...but a key that MISSED its target on the same cell keeps the soft",
      caused == set(),
      f"AIM D~{easy_ladder[3]}, realised 6 (> {ca.TARGET_TOLERANCE}ch off) -> {sorted(caused)}")

# Condition 1: medium's bottom rung has 22.3ch of headroom, so a fire there is real.
med = ranked_spec("medium", 4)
caused = ca.assignment_caused_softs(med, opts_of([med["key_target_len"], 95, 95, 95]), "A")
check("medium bottom rung is NOT suppressed — 22.3ch of headroom is a real signal",
      caused == set(), f"key_target {med['key_target_len']} -> {sorted(caused)}")

# The forward half, which the issue did not name and which is worse: easy rung 1's
# designed ratio is 1.714x, over the 1.5x soft at ZERO drift.
easy1 = ranked_spec("easy", 1)
caused = ca.assignment_caused_softs(easy1, opts_of([easy1["key_target_len"]]
                                                   + easy1["distractor_target_lens"]), "A")
check("easy TOP rung is suppressed too — it fires at zero drift (1.714x)",
      caused == {bqb.SOFT_LENGTH_GIVEAWAY_RATIO}, f"{sorted(caused)}")

# A row with no ladder assignment at all keeps everything it earns.
check("a spec with no length targets suppresses nothing",
      ca.assignment_caused_softs(
          {"answer_letter": "A", "option_length_band": [15, 55]},
          opts_of([15, 60, 55, 50]), "A") == set())
check("a --free-rank spec whose answer_letter is absent from the AIM dict is inert",
      ca.assignment_caused_softs(
          {"answer_letter": "D", "option_target_lens": {"A": 48, "B": 38, "C": 28}},
          opts_of([48, 38, 28, 18]), "D") == set())


print("\n[3] ALL 12 CELLS AGAINST THE REAL LADDER")
print("    A future inset change that opens or closes a cell shows up as a diff here.\n")

expected = {
    ("easy", 1): {bqb.SOFT_LENGTH_GIVEAWAY_RATIO},   # 1.714x — fires at zero drift
    ("easy", 2): set(),                              # +9.0ch
    ("easy", 3): set(),                              # +27.6ch
    ("easy", 4): {bqb.SOFT_REVERSE_TELL},            # 0.474x — +2.0ch
    ("medium", 1): {bqb.SOFT_LENGTH_GIVEAWAY_RATIO},  # 1.490x — +0.5ch
    ("medium", 2): set(),
    ("medium", 3): set(),
    ("medium", 4): set(),                            # +22.3ch
    ("hard", 1): set(),                              # +20.0ch
    ("hard", 2): set(),
    ("hard", 3): set(),
    ("hard", 4): set(),                              # +60.1ch
}
bad = []
for tier in ("easy", "medium", "hard"):
    for rank in (1, 2, 3, 4):
        spec = ranked_spec(tier, rank)
        # The author on target everywhere, so only the CELL is under test.
        got = ca.assignment_caused_softs(
            spec, opts_of([spec["key_target_len"]] + spec["distractor_target_lens"]), "A")
        key_t = spec["key_target_len"]
        mean_t = sum(spec["distractor_target_lens"]) / 3
        print(f"    {tier:<6} rung {rank}  key {key_t:>2} vs mean {mean_t:>5.1f} = "
              f"{key_t / mean_t:.3f}x  ->  {sorted(got) or '-'}")
        if got != expected[(tier, rank)]:
            bad.append(f"{tier} rung {rank}: {sorted(got)} != {sorted(expected[(tier, rank)])}")
print()
check("every cell matches the measured headroom table", not bad, "; ".join(bad))
check("exactly 3 of the 12 cells are suppressed — this is not a blanket exemption",
      sum(1 for v in expected.values() if v) == 3)


print("\n[4] A `note` ROW IS NOT A REPAIR FINDING\n")

# parse_gate reads the gate REPORT TEXT. A note header is a two-space line the finding
# regex misses, so before #139 it left `cur` pointing at the previous soft row and the
# note's indented body was appended to it -- turning a suppressed note back into a
# finding, on the wrong question.
report = (
    "  soft  mkt-district-pool-cand-e0020  [easy] Identify research project errors\n"
    "          option C is 62ch, outside band 15-55\n"
    "  note  mkt-district-pool-cand-e0025  [easy] Identify research project errors\n"
    "          possible reverse length tell: correct option is much shorter — "
    "ASSIGNMENT-CAUSED, not a repair candidate\n"
)
with tempfile.NamedTemporaryFile("w", suffix=".gate.txt", delete=False) as fh:
    fh.write(report)
    gate_path = Path(fh.name)
try:
    flags = brp.parse_gate(gate_path)
finally:
    gate_path.unlink()

check("the noted cand_id is absent from the repair flags entirely",
      "mkt-district-pool-cand-e0025" not in flags, f"keys {sorted(flags)}")
check("the note body did NOT leak onto the preceding soft row",
      all("ASSIGNMENT-CAUSED" not in m for m in flags.get("mkt-district-pool-cand-e0020", [])),
      f"e0020 -> {flags.get('mkt-district-pool-cand-e0020')}")
check("the real soft row is still parsed normally",
      "[soft]" in flags.get("mkt-district-pool-cand-e0020", []))


# ---------------------------------------------------------------------------
# What these fixtures do NOT check -- state it, don't imply coverage.
#
#  * THAT SUPPRESSION IS THE RIGHT DIRECTION. The issue named two, and the other one
#    (stop letting the key draw rung 4) would have fixed only the reverse half; nothing
#    here can tell you the ladder should not have been rebuilt instead. If a later slice
#    finds the ladder's spread is worth trading for self-consistency, section 3's table
#    is what changes, not this decision.
#  * THE 8ch HEADROOM. LADDER_HEADROOM_CH is `build_area.LADDER_INSET_TOP`'s measured
#    median excess over the six closed hospitality/pbm pool tails. It separates two
#    populations that are 2.0ch and 22.3ch from the line, so nothing here is sensitive
#    to it within ~±6ch -- but it is one measurement, and section 3 is where a later
#    one would land.
#  * WHETHER A SUPPRESSED ROW IS ACTUALLY FINE. It is not. `e0025`'s key IS the shortest
#    option and a student can still game it; what the gate can no longer do is call that
#    the author's fault. Fixing it means moving the ladder, not the filter.
#  * THE ASSEMBLER. `build_question_bank.check_question` has no payload and still reports
#    these rows at assembly, deliberately -- it describes the bank as it stands.
#  * ANY RATE. This is a per-row predicate; the batch-level tell control is still
#    `audit_tells` and the LONGEST= assignment.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
