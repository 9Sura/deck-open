"""Plan 07 §3c §7 fixtures. These MUST be red before --changed-vs diffs `question`.

THE TRAP
--------
`tag_difficulty.py --build-payload --changed-vs REF` selects items whose `options` differ.
A §3c fix changes ONLY the stem -- so every item §3c edits is INVISIBLE to §4's selector,
despite a de-triggered stem being exactly the kind of edit that moves difficulty. §4 would
re-tag the bank and silently skip the items whose difficulty had just moved most.

THE RULE THE SELECTOR ALREADY ENCODES
-------------------------------------
`CHANGED_FIELD = "options"` was never arbitrary. Its own comment gives the rule:

    `explanation` is deliberately NOT diffed: the rater never sees it, so an
    explanation-only edit cannot have moved the item's difficulty.

So the selector diffs THE FIELDS THE RATER SEES -- the intersection of "what a pass may
edit" and PAYLOAD_FIELDS. `question` satisfies both and always did; it was excluded only
because no pass had ever edited a stem. §3c is that pass. This is a widening the existing
rationale REQUIRES, not a new policy.

That is why this is fixed here (option (a) of §7) rather than by hand-adding §3c's ids to
§4's payload (option (b)). §1.1: mechanical constraints work, prose rules do not. Option
(b) is a prose rule that survives only as long as someone remembers it, and it would have
to be remembered again for every future stem pass.

CASES
  1. an options-only edit is SELECTED            (no regression -- §3/§3b's 88 still land)
  2. a question-only (stem) edit is SELECTED     <- THE TRAP. Red before the widening.
  3. an explanation-only edit is NOT selected    (the rater never sees it -- preserve this)
  4. an unchanged item is NOT selected
  5. a question AND options edit is selected ONCE, not twice
  6. STRICTLY ADDITIVE on the real bank: with no stem yet edited, the widened selector
     picks exactly the items the old one picked. A widening that moves today's selection
     is not a widening, it is a change.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]  # repo root, derived — was hardcoded to the
                                     # pre-rename "GNS DECA APP" path and silently dead
GEN = ROOT / "backend/test-gen-model/src/generators"
sys.path.insert(0, str(GEN))
import tag_difficulty  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def item(qid):
    return {
        "id": qid,
        "question": f"Stem for {qid}?",
        "options": {"A": "aaa", "B": "bbb", "C": "ccc", "D": "ddd"},
        "answer": "B",
        "explanation": f"Explanation for {qid}.",
        "performanceIndicator": "Explain worker rights",
        "instructionalArea": "Business Law",
        "cluster": "finance",
        "level": "association",
        "difficulty": "medium",
    }


IDS = ["fx-options-only", "fx-stem-only", "fx-expl-only", "fx-unchanged", "fx-both"]


def mutate(q):
    if q["id"] == "fx-options-only":
        q["options"]["A"] = "aaa changed"
    elif q["id"] == "fx-stem-only":
        q["question"] = "A DE-TRIGGERED stem for fx-stem-only?"
        q["explanation"] = "Explanation moved with the stem."
    elif q["id"] == "fx-expl-only":
        q["explanation"] = "Only the explanation moved."
    elif q["id"] == "fx-both":
        q["question"] = "Both moved?"
        q["options"]["C"] = "ccc changed"
    return q


with tempfile.TemporaryDirectory() as td:
    repo = Path(td) / "repo"
    bank = repo / "frontend/public/question-bank"
    (bank / "finance").mkdir(parents=True)
    f = bank / "finance" / "fin-fixture.json"

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fx@example.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "fixture"], cwd=repo, capture_output=True)

    f.write_text(json.dumps([item(i) for i in IDS], indent=2), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, capture_output=True)

    f.write_text(json.dumps([mutate(item(i)) for i in IDS], indent=2), encoding="utf-8")

    tag_difficulty.BANK_DIR = bank
    tag_difficulty.REPO_ROOT = repo

    sel = tag_difficulty.select_changed("HEAD", [f])
    got = [q["id"] for _, q in sel]

    check("1. options-only edit is SELECTED (no regression)",
          "fx-options-only" in got, f"selected={got}")
    check("2. STEM-only edit is SELECTED (THE TRAP)",
          "fx-stem-only" in got, f"selected={got}")
    check("3. explanation-only edit is NOT selected (the rater never sees it)",
          "fx-expl-only" not in got, f"selected={got}")
    check("4. unchanged item is NOT selected",
          "fx-unchanged" not in got, f"selected={got}")
    check("5. question+options edit is selected exactly ONCE",
          got.count("fx-both") == 1, f"selected={got}")

# ---- 6. strictly additive on the REAL bank -------------------------------
# The widened selector must never LOSE an item the old one caught, and everything it
# gains must be gained for exactly one reason: a stem moved while the options did not.
#
# This asserts the INVARIANT, not a snapshot. The first version of this check asserted
# `widened == old`, which was true only in the window before §3c edited a stem -- it
# went red the moment the pass it exists to support did its job, and the assertion, not
# the code, was what was wrong. A fixture that encodes a fact true at one moment fails
# on the clock. §13's "verify an inherited table before spending against it", one layer
# down: an assertion has a shelf life, so assert the property.
print("\n  [6] additive check against the real bank (this reads 45 files)")
old_field = "options"

# reload: the fixture repo was monkeypatched onto the module above, and case 6 must
# read the REAL bank through the REAL constants.
import importlib  # noqa: E402
importlib.reload(tag_difficulty)
REF = "79edf07^"
real = {q["id"] for _, q in tag_difficulty.select_changed(REF, tag_difficulty._bank_files())}

# Recompute the OLD behaviour by hand: options-only diff, same ref, same files.
old = set()
live = {}
prior_all = {}
for path in tag_difficulty._bank_files():
    before = tag_difficulty._git_show(tag_difficulty._rel(path), REF)
    prior = {q.get("id"): q for q in before}
    for q in json.loads(path.read_text(encoding="utf-8")):
        was = prior.get(q.get("id"))
        if was is None:
            continue
        live[q["id"]] = q
        prior_all[q["id"]] = was
        if was.get(old_field) != q.get(old_field):
            old.add(q["id"])

check("6a. widened selector LOSES nothing the old one caught (superset)",
      old <= real, f"missing={sorted(old - real)[:5]}")

gained = real - old
bad = [i for i in gained
       if not (prior_all[i].get("question") != live[i].get("question")
               and prior_all[i].get("options") == live[i].get("options"))]
check("6b. everything GAINED is a stem-only edit (question moved, options did not)",
      not bad,
      f"gained={len(gained)} ({sorted(gained)}) · gained-for-the-wrong-reason={bad}")

print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
