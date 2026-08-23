"""Issue #88 fixtures: the rule-5 combination-option guard in `check_question`.

Rule 5 bans an option that points at the OTHER options ("All of the above", "A and B")
instead of saying something. The predicate that enforces it has now been wrong twice --
once in each direction -- and both times the wrong behaviour was asserted in a comment
and nowhere else:

  1. `a and b` as a bare substring hard-failed "protecting dat(a and b)eing honest in
     interactions", a clean distractor (§10-11 finding 3).
  2. The anchor that fixed it was pinned at `^` with no leading words, so `Options A
     and B` and `Choices A and B are correct` -- textbook rule-5 violations -- started
     PASSING, while `both a and b` stayed in the unanchored substring list and kept
     false-positiving on "...a rule that holds for both a and b parts of the form".

So this file pins BOTH directions, permanently. It is the table from issue #88 plus the
shapes the generalisation to `[abcd] and [abcd]` was supposed to close.

Why it matters where it runs: `check_question` is the shared gate. In
`build_question_bank.build_set` a hit is a silent DROP; in `check_authored.check_part`
it is a hard FAIL that scopes a repair; in `apply_repair` it refuses the overlay. A
false negative ships a banned option into the permanent bank; a false positive burns a
repair agent on a sound row -- which is exactly what §10-11 chunk 8 spent.

NON-VACUITY: every case asserts the REASON, not just pass/fail. A FAIL must carry the
all/none/both message specifically (a case that failed on a missing field or a length
tell would otherwise read as a pass for the wrong reason), and a PASS must carry NO
hard errors at all.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_combination_option.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded -- an absolute path into a session
scratchpad, or into `/Users/.../GNS DECA APP` (the pre-rename directory, now DECK-APP),
dies with the session or the rename and takes the file with it. #157 swept the last
three out of this toolchain; don't reintroduce one.
"""
import json
import re
import sys
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
MODEL_DIR = GEN.parents[1]                 # backend/test-gen-model
sys.path.insert(0, str(GEN))
from bank_paths import BANK_DIR  # noqa: E402  the ONE bank path (#203)
from build_question_bank import (  # noqa: E402
    BANNED_PHRASES,
    COMBINATION_OPTION,
    _norm,
    check_question,
)

REASON = "all/none/both"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def item(option_b: str) -> dict:
    """A structurally clean question whose ONLY candidate defect is option B.

    Every other field is padded past its own gate (20-char stem, 80-char explanation,
    four distinct options, no length giveaway) so the single hard error this fixture
    reads about is the one it is testing.
    """
    return {
        "question": "Which practice best supports the stated business goal here?",
        "options": {
            "A": "Reviewing the quarterly operating budget with the department head",
            "B": option_b,
            "C": "Filing the signed vendor agreement in the central contract system",
            "D": "Scheduling the annual physical inventory count for the warehouse",
        },
        "answer": "A",
        "explanation": (
            "A is correct because the budget review is the stated practice; B, C and D "
            "are routine tasks that do not address the goal in the stem at all."
        ),
        "instructionalArea": "Operations",
        "performanceIndicator": "Explain the nature of operations",
        "difficulty": "easy",
    }


def verdict(option_b: str):
    """Return (banned, hard) -- did the rule-5 check fire, and every hard error."""
    hard, _ = check_question(item(option_b), require_difficulty=True)
    return any(REASON in h for h in hard), hard


# ---------------------------------------------------------------------------
# 1. Must FAIL -- these are combination options, the shape rule 5 exists to ban.
# ---------------------------------------------------------------------------
MUST_FAIL = [
    ("A and B", "the bare pair"),
    ("Both A and B", "the `both` form"),
    ("A and B only", "the `only` tail"),
    ("Options A and B", "leading noun -- REGRESSION: passed after the first anchor fix"),
    ("Choices A and B are correct", "leading noun + tail -- REGRESSION, same fix"),
    ("Both options A and B", "leading `both` AND a noun"),
    ("The answers A and D", "article + noun + a non-AB pair"),
    ("A and B are both correct", "the pair with a trailing claim"),
    ("Both A and C", "NEVER caught by any version -- the same defect, different letters"),
    ("A and C", "ditto, bare"),
    ("All of the above", "the substring instrument, still live"),
    ("none of the above", "ditto, lowercase -- the check reads the normed text"),
    ("NONE OF THE ABOVE", "ditto, shouted"),
]

# ---------------------------------------------------------------------------
# 2. Must PASS -- ordinary prose that earlier versions hard-dropped.
# ---------------------------------------------------------------------------
MUST_PASS = [
    ("Protecting data and being honest in interactions",
     "the §10-11 false positive: `dat(a and b)eing`"),
    ("A rule that holds for both a and b parts of the form",
     "REGRESSION: still failed after the first anchor fix, via the substring list"),
    ("A guarantee, a promise of satisfaction that entitles the buyer to a refund",
     "a real bank option that opens with the article `A`"),
    ("Comparing the a and b variants only after the campaign has ended",
     "the pair mid-sentence -- NOT caught, deliberately (see below)"),
    ("Recording all of the amounts above the line in the ledger",
     "`all of the` + `above` split across the phrase, not the banned phrase"),
]

print("Issue #88 -- rule-5 combination-option guard\n")
print("must FAIL:")
for text, why in MUST_FAIL:
    banned, hard = verdict(text)
    check(f"{text!r} -- {why}", banned,
          f"hard errors = {hard or 'none'}")

print("\nmust PASS:")
for text, why in MUST_PASS:
    banned, hard = verdict(text)
    check(f"{text!r} -- {why}", not banned and not hard,
          f"hard errors = {hard or 'none'}")

# ---------------------------------------------------------------------------
# 3. The predicate lives in ONE place, in the right instrument.
#
# The letter pair must NOT be back in the substring list: that list is matched
# unanchored, which is the exact mechanism of defect (1). A future edit that "just adds
# `both a and b` back to be safe" re-opens it, and nothing else here would notice --
# every MUST_FAIL case would still fail, for the wrong reason.
# ---------------------------------------------------------------------------
print("\nshape of the check:")
check("the letter pair is NOT in the unanchored substring list",
      not any("and b" in p for p in BANNED_PHRASES),
      f"BANNED_PHRASES = {BANNED_PHRASES}")
check("the combination regex is ANCHORED at the start of the option",
      COMBINATION_OPTION.pattern.startswith("^"),
      f"pattern = {COMBINATION_OPTION.pattern}")
check("the regex generalises past `a and b` (matches other letter pairs)",
      bool(COMBINATION_OPTION.match("both b and d")),
      "`Both B and D` must match")

# ---------------------------------------------------------------------------
# 4. Blast radius on the committed bank.
#
# A hit here is not a fixture bug, it is a banned option sitting in the permanent bank,
# so it gates. Measured at 0 of 12,778 rows on 2026-08-03, with the old predicate and
# the new one both reading 0 -- this fix is guard correctness, not data repair.
# ---------------------------------------------------------------------------
print("\ncommitted bank:")
rows = 0
hits = []
for path in sorted(BANK_DIR.glob("*/*.json")):
    if path.name == "manifest.json":
        continue
    for q in json.loads(path.read_text(encoding="utf-8")):
        rows += 1
        for letter, text in (q.get("options") or {}).items():
            normed = _norm(text)
            if any(b in normed for b in BANNED_PHRASES) or COMBINATION_OPTION.match(normed):
                hits.append(f"{q.get('id')} {letter}: {text!r}")
check(f"0 committed rows carry a combination option ({rows} scanned)",
      rows > 0 and not hits,
      "\n          ".join(hits) if hits else f"{rows} rows, 0 hits")

# ---------------------------------------------------------------------------
# What this fixture does NOT check -- state it, don't imply coverage.
#
#  * A combination option that names the other options MID-SENTENCE ("The correct
#    responses are A and B") is not caught by the anchor and is not tested as a
#    failure here. That is the accepted cost of the anchor: a hard drop is too
#    expensive to spend on a guess, and the false positives that cost cost real
#    repair agents twice.
#  * A company name of the literal shape "A and B Manufacturing" WOULD be dropped.
#    It needs an article `a` immediately followed by `and`, which is ungrammatical in
#    prose, so the exposure is proper nouns only -- 0 rows in the committed bank.
#  * Rule 5 in spirit (an option that adds nothing) is not mechanically checkable at
#    all; this guard only catches the two literal shapes above.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
