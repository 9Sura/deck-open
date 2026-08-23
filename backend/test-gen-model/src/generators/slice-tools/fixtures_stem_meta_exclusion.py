"""Issue #131 fixtures: the stem meta-exclusion finding in `check_authored`.

THE DEFECT. The standing fix for a row with two defensible answers is to make the stem
commit to one reading. The shortest way to comply is a clause that NAMES THE RIVAL
OPTION AND TELLS THE READER TO DISREGARD IT -- and that converts a knowledge item into
a reading item, which is strictly worse than the ambiguity it cures.

WHY IT NEEDS A FIXTURE RATHER THAN A COMMENT. The instrument is a PHRASE LIST, and this
repo has now watched a phrase list go wrong in both directions twice (issue #88's
combination option, issue #75's option tells). A phrase list that drifts wide stops
being readable as a rate; one that drifts narrow silently stops finding the defect. Both
failures are invisible without cases, so the cases live here.

THE CALIBRATION PAIR IS REAL AND IT IS THE POINT. §10-13's chunks 9/10 left behind an
adjudicated defect/fix pair on disk: `parts/chunk{9,10}-repair.json` is round 1, where a
repair agent bolted a meta-exclusion onto 5 of the 5 rows where a stem edit was in scope
and every one passed the full gate suite; `-repair2.json` is the accepted fix, where each
clause was replaced by a scenario fact that makes the rival wrong on the merits. The
instrument must flag 5 of 5 on the first and 0 of 5 on the second. That is the same shape
of calibration `label_divergence` got from §10-10's h1-deleak pair, and for the same
reason: a detector with no adjudicated negative is a detector nobody can falsify.

WHAT THIS FIXTURE ALSO PINS, and it matters more than the phrases: the finding is ONE
line per row. `build_repair_prompt.finding_scope` adds `options` to a row's scope for
every gate line it cannot place (issue #77), so splitting the guidance onto a second,
unprefixed line would silently widen a stem repair into an option repair -- exactly the
class of defect issue #130 was.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_stem_meta_exclusion.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, never hardcoded.
"""
import json
import sys
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
MODEL_DIR = GEN.parents[1]                 # backend/test-gen-model
PAIR_DIR = MODEL_DIR / "output" / "plan-10" / "10-13" / "parts"
sys.path.insert(0, str(GEN))
from bank_paths import BANK_DIR  # noqa: E402  the ONE bank path (#203)
from check_authored import (  # noqa: E402
    BANK_STEM_META_RATE,
    stem_meta_exclusion,
)
from build_repair_prompt import STEM_FINDINGS, finding_scope  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# 1. The §10-13 calibration pair, read off disk.
#
# Loaded rather than pasted: a copied stem is a stem that stops tracking the file it
# came from, and these two files are the only adjudicated evidence this instrument has.
# ---------------------------------------------------------------------------
PAIR_IDS = [
    "ent-icdc-pool-cand-e0003",
    "ent-icdc-pool-cand-e0008",
    "ent-icdc-pool-cand-e0014",
    "ent-icdc-pool-cand-e0029",
    "ent-icdc-pool-cand-m0003",
]


def pair_rows(suffix: str) -> dict:
    """{cand_id: stem} for the five pair rows, taken from chunk9 + chunk10.

    `m0003` lives in chunk 10 and the other four in chunk 9, and cand_ids COLLIDE
    across chunks (§10-11) -- `e0008` exists in both files and they are DIFFERENT
    questions. So each id is taken from its own chunk, never from whichever file
    happens to be read last.
    """
    out = {}
    for chunk, ids in (("chunk9", PAIR_IDS[:4]), ("chunk10", PAIR_IDS[4:])):
        path = PAIR_DIR / f"{chunk}-{suffix}.json"
        by_id = {r["cand_id"]: r for r in json.loads(path.read_text(encoding="utf-8"))}
        for cid in ids:
            out[cid] = by_id[cid]["question"]
    return out


print("Issue #131 -- stem meta-exclusion\n")
print("the §10-13 calibration pair (round 1 = defect, round 2 = accepted fix):")

defect = pair_rows("repair")
fixed = pair_rows("repair2")

for cid, stem in defect.items():
    hits = stem_meta_exclusion(stem)
    check(f"{cid.split('cand-')[1]} round 1 is FLAGGED", bool(hits),
          "; ".join(hits) if hits else f"stem = {stem!r}")

print()
for cid, stem in fixed.items():
    hits = stem_meta_exclusion(stem)
    check(f"{cid.split('cand-')[1]} round 2 is CLEAN", not hits,
          "; ".join(hits) if hits else "no hit")

# ---------------------------------------------------------------------------
# 2. Must FLAG -- the shapes, stated independently of the five rows above so that
#    narrowing a pattern to make some future batch read clean breaks something.
# ---------------------------------------------------------------------------
MUST_FLAG = [
    ("A shop owner wants to build a genuine relationship with repeat buyers, not just "
     "keep a record of their purchases. Which action best supports that goal?",
     "`not just` -- the §10-13 e0003 shape"),
    ("A retailer adds a chatbot to its site; logging each visitor's inquiry is a "
     "secondary side effect. What purpose does this technology mainly serve?",
     "`is a secondary` -- demotes the rival reading"),
    ("A receptionist wants to build rapport with a nervous first-time client by keeping "
     "the focus on the client, not on herself. Which action helps most?",
     "`, not on` -- the trailing exclusion"),
    ("Which underlying product attribute -- not the evidence used to prove it -- matters "
     "most to this positioning?",
     "the parenthetical exclusion, em-dash pair"),
    ("Setting aside how the access became possible, which legal issue is most directly "
     "raised by the exposure of the records?",
     "`setting aside how` -- an instruction to the reader"),
    ("A server wants to show measurable impact on her resume rather than just listing "
     "the daily tasks she performed. Which approach best achieves this?",
     "`rather than just` -- a real committed-bank hit"),
    ("Which is an example of a natural resource used in hospitality, as opposed to "
     "labor or capital?",
     "`as opposed to` naming two likely distractors"),
]

# ---------------------------------------------------------------------------
# 3. Must NOT flag -- the wording deliberately left out, because a rate nobody can
#    read is worse than no rate. Each of these is the measured reason a pattern was
#    narrowed; re-widening any of them lights this section up.
# ---------------------------------------------------------------------------
MUST_PASS = [
    ("A caterer prefers to lease its delivery vans rather than purchase them outright. "
     "Which financing consideration matters most here?",
     "bare `rather than` -- 369 committed rows, 2.61%; ordinary contrastive prose"),
    ("A restaurant's rent, insurance, and manager's salary stay the same each month "
     "regardless of how many guests are served. What cost category is this?",
     "`regardless of how many` -- the canonical fixed-cost stem"),
    ("Priya writes down, 'Save $1,200 for a laptop within 8 months by setting aside "
     "$150 from each paycheck.' Which characteristic does this goal show?",
     "`setting aside` + money -- literal saving, not an exclusion"),
    ("A manager learns that closing a large contract requires quietly ignoring the "
     "client's request for an accessible meeting room. What should the manager do?",
     "`ignoring` mid-clause -- a scenario FACT, not an instruction to the reader"),
    ("A boutique furniture maker keeps a detailed purchase log for every repeat "
     "customer, yet several have mentioned they feel like just another sale. Which "
     "action best builds a genuine relationship with these customers?",
     "the accepted §10-13 fix: `just another` is not `not just`"),
]

print("\nmust FLAG:")
for stem, why in MUST_FLAG:
    hits = stem_meta_exclusion(stem)
    check(why, bool(hits), "; ".join(hits) if hits else "NO HIT")

print("\nmust NOT flag:")
for stem, why in MUST_PASS:
    hits = stem_meta_exclusion(stem)
    check(why, not hits, "; ".join(hits) if hits else "no hit")

# ---------------------------------------------------------------------------
# 4. The finding is ONE line, and it routes to the STEM scope.
#
# Both halves matter and neither implies the other. A row flagged here must reach the
# repair author as a stem repair -- if `finding_scope` cannot place the line it falls
# to the catch-all `options` scope, and the author is told to reword options on a row
# whose defect is in the stem.
# ---------------------------------------------------------------------------
print("\nrepair scope:")
one_line = stem_meta_exclusion(MUST_FLAG[0][0])
sample = "stem meta-exclusion — " + "; ".join(one_line) + " — the stem may be telling..."
check("the finding routes to the STEM scope, not the catch-all `options`",
      finding_scope([sample]) == ("question",),
      f"finding_scope -> {finding_scope([sample])}")
check("`stem meta-exclusion` is the string STEM_FINDINGS matches on",
      "stem meta-exclusion" in STEM_FINDINGS,
      f"STEM_FINDINGS = {STEM_FINDINGS}")
# The regression this guards: a SECOND, unprefixed guidance line on the same row.
check("a second unprefixed line would widen the scope (so there must not be one)",
      finding_scope([sample, "...replace it with a scenario fact"]) == ("question", "options"),
      "this asserts the HAZARD, not the behaviour: check_authored must emit one line")

# ---------------------------------------------------------------------------
# 5. The committed-bank baseline the gate prints.
#
# NOT a gate -- the bank's hits are a real mix of the defect and legitimate narrative
# prose, and only a reader can tell them apart. What is pinned is that the printed
# baseline still describes the bank: a rate quoted in a gate line and nowhere measured
# is how `BANK_LABEL_DIVERGENCE_RATE` would have gone stale unnoticed. Tolerance is
# generous because the bank grows every slice; a real drift trips it.
# ---------------------------------------------------------------------------
print("\ncommitted bank baseline:")
rows = 0
hits = []
for path in sorted(BANK_DIR.glob("*/*.json")):
    if path.name == "manifest.json":
        continue
    for q in json.loads(path.read_text(encoding="utf-8")):
        rows += 1
        if stem_meta_exclusion(q.get("question", "")):
            hits.append(q.get("id"))
rate = 100.0 * len(hits) / rows if rows else 0.0
check(f"the printed baseline {BANK_STEM_META_RATE:.2f}% still describes the bank "
      f"(measured {rate:.2f}%, {len(hits)} of {rows})",
      rows > 0 and abs(rate - BANK_STEM_META_RATE) <= 0.35,
      f"update BANK_STEM_META_RATE if this drifted legitimately")

# ---------------------------------------------------------------------------
# What this fixture does NOT check -- state it, don't imply coverage.
#
#  * That the instrument FINDS the defect. It finds the wording it has seen. The five
#    round-1 rows are the wording it was built from, so 5 of 5 is not evidence of
#    recall on wording nobody has written yet -- there is no such evidence, and
#    `check_authored`'s coverage map says so out loud.
#  * That a flagged row IS defective. It is not: the committed-bank hits include
#    "Rather than simply increasing its own on-site inventory, the director proposes..."
#    which is a scenario fact in narrative form. The rows are candidates for a reader.
#  * The structural alternative. An INVERTED stem pull (does the stem name what a
#    DISTRACTOR names?) was the obvious vocabulary-free instrument and is REFUTED on
#    this same pair -- the accepted fixes score HIGHER than the defects. The numbers
#    are in check_authored's STEM META-EXCLUSION block; do not re-propose it without
#    reading them.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
