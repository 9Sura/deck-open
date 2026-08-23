"""§10-12 fixtures: the key-is-assigned-longest row in `build_repair_prompt.py`.

THE DEFECT. `build_area.py --free-rank` assigns roughly a quarter of a concept batch
`LONGEST=<the key's own letter>` — on those rows the key is MEANT to be the longest
option, and `check_authored.py` scores that assignment (it reports `LONGEST=<letter>
honoured on N/M rows`, a bar that has held ~97% for four slices).

Such a row can still be handed to a repair: `--min-margin 20` lists every row whose key
stands >=20ch clear of every distractor, and a key that is RIGHTLY the longest can still
stand too FAR clear. That is a MARGIN finding. The correct fix is to raise the runner-up
and leave the key on top.

But `THE RULES THAT APPLY` was a single static block, emitted verbatim for every repair,
and it opened:

    KEY LENGTH — THIS IS A RANK TEST, NOT A MARGIN TEST ...
    So the target is RANK: PICK ONE SPECIFIC DISTRACTOR AND MAKE IT STRICTLY
    LONGER THAN THE KEY.

On a LONGEST=<key letter> row that instruction destroys the very assignment the gate
scores. `key_may_be_longest` appeared NOWHERE in the file and there was no branch of any
kind: the row printed `ASSIGNED: answer=B LONGEST=B` and then, 200 lines earlier, told
the agent to dethrone B.

WHAT IT COST. §10-12 chunk 3 handed back 4 length rows + 1 confession row. All four
length rows carried LONGEST=<key letter>. The repair fixed every margin (decisive 4 -> 0)
and pushed a distractor 2-3ch past the key on 5 of 5 rows it touched, dropping the
chunk's LONGEST= compliance 98.9% -> 93.3% — under the ~97% bar — and costing a whole
extra repair round (73.4k tokens) to undo. Neither the agent nor the rules block was
wrong in isolation; nothing told the agent this row was the exception.

    m0006  longest C (80ch), assigned LONGEST=D (77ch)      answer=D
    e0009  longest B (55ch), assigned LONGEST=A (53ch)      answer=A
    e0011  longest B (55ch), assigned LONGEST=D (51ch)      answer=D
    m0047  longest A (83ch), assigned LONGEST=B (80ch)      answer=B
    m0065  longest D (84ch), assigned LONGEST=C (81ch)      answer=C

WHY A FIXTURE AND NOT A COMMENT. This is the fourth guard in this toolchain to be wrong
while prose above it described correct behaviour (#76 GATED_FIELDS, #88 the rule-5
predicate, #89 the COPY THROUGH `answer`, now this). Same family as §10-10's
`key_length_rank` bug, where a gate hard-failed on an assignment `build_prompt.py` never
rendered and three slices read the failures as author non-compliance. The rule from
§10-11 stands: when a gate's behaviour is asserted in a comment, assert it in a fixture.

NON-VACUITY. The negative cases matter as much as the positive ones: a row whose LONGEST
letter is NOT the key must NOT get the warning, or the block becomes noise on every row
and the exception stops reading as an exception. Both directions are asserted, and the
static block is asserted to still carry the rank rule for the ordinary rows.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_repair_key_longest.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded — an absolute path into a session
scratchpad, or into `/Users/.../GNS DECA APP` (the pre-rename directory, now DECK-APP),
dies with the session or the rename and takes the file with it. #157 swept the last
three out of this toolchain; don't reintroduce one.
"""
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
import build_repair_prompt as brp  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


CID = "ent-association-pool-cand-m0047"

# The real shape `build_area.py --free-rank` writes. `longest_letter` == the answer
# letter is the case under test; `key_may_be_longest` rides alongside it.
def payload_row(answer: str, longest: str, may: bool) -> dict:
    return {
        "cand_id": CID,
        "cluster": "entrepreneurship",
        "level": "Association",
        "instructionalArea": "Operations",
        "performanceIndicator": "Explain supply chain",
        "difficulty": "medium",
        "answer_letter": answer,
        "option_length_band": [35, 85],
        "key_may_be_longest": may,
        "longest_letter": longest,
    }


def authored_row(answer: str) -> dict:
    return {
        "cand_id": CID,
        "cluster": "entrepreneurship",
        "level": "Association",
        "instructionalArea": "Operations",
        "performanceIndicator": "Explain supply chain",
        "difficulty": "medium",
        "question": "A furniture maker wants to map every step its lumber takes from "
                    "forest to finished chair. What is it documenting?",
        "options": {
            "A": "The retail markup applied at each store location",
            "B": "The full supply chain, from raw material through delivery to the buyer",
            "C": "The advertising schedule for the season",
            "D": "The warranty terms offered on each chair",
        },
        "answer": answer,
        "explanation": "B is correct because a supply chain spans sourcing through "
                       "delivery; (A) is pricing, (C) is promotion, and (D) is service.",
    }


# A margin finding — the shape `--min-margin 20` emits. NOT a rank finding.
GATE_MARGIN = """\
  soft  ent-association-pool-cand-m0047  [medium] Explain supply chain
          possible length giveaway: correct option is 27ch longer than every distractor (>=20ch)

"""


def build(gate_text: str, answer: str, longest: str, may: bool = True):
    """Run the real tool over real files. Returns the prompt text."""
    tmp = Path(tempfile.mkdtemp(prefix="keylongest-"))
    (tmp / "payload.json").write_text(json.dumps([payload_row(answer, longest, may)]))
    (tmp / "part1.json").write_text(json.dumps([authored_row(answer)]))
    (tmp / "gate.txt").write_text(gate_text)
    argv = sys.argv
    sys.argv = ["build_repair_prompt.py",
                "--payload", str(tmp / "payload.json"),
                "--gate", str(tmp / "gate.txt"),
                "--part", str(tmp / "part1.json"),
                "--out", str(tmp / "prompt.txt"),
                "--overlay", str(tmp / "overlay.json"),
                # Issue #127's pooling floor: a 1-row batch must say why it runs alone.
                # Pinned in fixtures_repair_round_guards.py; here it is just a fixture.
                "--solo-reason", "fixture — one synthetic row, no agent is launched"]
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            brp.main()
    finally:
        sys.argv = argv
    return (tmp / "prompt.txt").read_text(encoding="utf-8")


MARKER = "ON THIS ROW THE KEY IS ASSIGNED THE LONGEST OPTION"

print("§10-12 -- the key-is-assigned-longest repair row\n")

# ---------------------------------------------------------------------------
# 1. THE DEFECT ITSELF. answer == longest_letter must carry the warning.
# ---------------------------------------------------------------------------
print("the row under test (answer == LONGEST):")
p_same = build(GATE_MARGIN, answer="B", longest="B")
check("a LONGEST=<key letter> row carries the ⚠ block",
      MARKER in p_same,
      "without it the static rank rule tells the agent to dethrone the key")
check("the ⚠ block names the actual letter, not a placeholder",
      "LONGEST=B IS THE" in p_same,
      "a generic warning does not tell the agent WHICH option to protect")
check("the ⚠ block forbids pushing a distractor past the key",
      "Do NOT push any distractor past the key" in p_same)
check("the ⚠ block names the fix direction (raise the runner-up)",
      "runner-up" in p_same.split(MARKER, 1)[1][:800])
check("the ⚠ block sits with its own row, after that row's ASSIGNED line",
      p_same.index("ASSIGNED:  answer=B   LONGEST=B") < p_same.index(MARKER),
      "a warning printed before the row it qualifies reads as a general rule")

# ---------------------------------------------------------------------------
# 2. NON-VACUITY. The ordinary row must NOT get it, or the exception stops
#    reading as an exception and the block is noise on every row.
# ---------------------------------------------------------------------------
print("\nthe ordinary row (answer != LONGEST) — must NOT be warned:")
p_diff = build(GATE_MARGIN, answer="B", longest="D", may=False)
check("a LONGEST=<distractor> row does NOT carry the ⚠ block",
      MARKER not in p_diff,
      "the static rank rule is CORRECT on these rows")
check("that row still renders its ASSIGNED line",
      "ASSIGNED:  answer=B   LONGEST=D" in p_diff)

# ---------------------------------------------------------------------------
# 3. THE STATIC BLOCK still has to teach the rank test for the ordinary rows,
#    and has to point at the exception rather than flatly contradicting it.
# ---------------------------------------------------------------------------
print("\nthe static rules block:")
check("still states the rank test for ordinary rows",
      "PICK ONE SPECIFIC DISTRACTOR AND MAKE IT STRICTLY" in p_diff,
      "the fix must not disarm the rule that took a chunk 35.8% -> 23.9% (§10-6)")
check("no longer claims the rank test holds unconditionally",
      "NOT A MARGIN TEST, ON EVERY ROW EXCEPT" in p_diff,
      "an unqualified 'this is a rank test' contradicts the per-row ⚠ block")
check("points the reader at the ⚠ rows and yields to them",
      "let it win over this paragraph" in p_diff)

# ---------------------------------------------------------------------------
# 4. A HARD payload has no `longest_letter` at all (it carries key_length_rank).
#    The branch must not raise there — that KeyError made a hard batch
#    unrepairable in §10-8.
# ---------------------------------------------------------------------------
print("\nthe hard-payload shape (no longest_letter):")
tmp = Path(tempfile.mkdtemp(prefix="keylongest-hard-"))
hard = payload_row("B", "B", True)
del hard["longest_letter"], hard["key_may_be_longest"]
hard["key_length_rank"] = 1
hard["difficulty"] = "hard"
(tmp / "payload.json").write_text(json.dumps([hard]))
(tmp / "part1.json").write_text(json.dumps([dict(authored_row("B"), difficulty="hard")]))
(tmp / "gate.txt").write_text(GATE_MARGIN)
argv = sys.argv
sys.argv = ["build_repair_prompt.py",
            "--payload", str(tmp / "payload.json"), "--gate", str(tmp / "gate.txt"),
            "--part", str(tmp / "part1.json"), "--out", str(tmp / "prompt.txt"),
            "--overlay", str(tmp / "overlay.json"),
            "--solo-reason", "fixture — one synthetic row, no agent is launched"]
try:
    with redirect_stdout(io.StringIO()):
        brp.main()
    ok, detail = True, "renders KEY LENGTH RANK instead"
except Exception as e:                                    # noqa: BLE001
    ok, detail = False, f"{type(e).__name__}: {e}"
finally:
    sys.argv = argv
check("a hard row (key_length_rank, no longest_letter) does not raise", ok, detail)
if ok:
    ptxt = (tmp / "prompt.txt").read_text(encoding="utf-8")
    check("a hard row does not get the ⚠ block either",
          MARKER not in ptxt,
          "rank 1 is handled by the KEY LENGTH RANK paragraph, which already says "
          "'lengthening a distractor past it is the defect, not the fix'")

# ---------------------------------------------------------------------------
# 5. REAL PAYLOADS. The branch keys on longest_letter == answer_letter, so it is
#    only correct if that shape is what build_area actually writes. Assert the
#    committed payloads carry both fields and that the case is common, not rare
#    — if it were rare the block would be dead code.
# ---------------------------------------------------------------------------
print("\nagainst every committed --free-rank payload under output/:")
MODEL_DIR = GEN.parents[1]
scanned = same = bad = 0
for path in sorted((MODEL_DIR / "output").rglob("payload/*.json")):
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                     # noqa: BLE001
        continue
    if not isinstance(rows, list):
        continue
    for r in rows:
        if not isinstance(r, dict) or "longest_letter" not in r:
            continue
        scanned += 1
        if "answer_letter" not in r:
            bad += 1
        elif r["longest_letter"] == r["answer_letter"]:
            same += 1
check("every row carrying `longest_letter` also carries `answer_letter`",
      bad == 0 and scanned > 0,
      f"{scanned} rows scanned, {bad} missing answer_letter")
check("the warned case is common enough to matter (10-40% of rows)",
      scanned > 0 and 0.10 <= same / scanned <= 0.40,
      f"{same}/{scanned} = {same / max(scanned, 1):.1%} of --free-rank rows are "
      f"LONGEST=<key letter>; build_area targets ~25%")

# ---------------------------------------------------------------------------
# What this fixture does NOT check -- state it, don't imply coverage.
#
#  * That the REPAIR AGENT obeys the ⚠ block. Nothing here reads a model. The prompt
#    is the instrument; the enforcement is `check_authored.py`'s LONGEST= line on the
#    re-gate, and that is what caught the original regression.
#  * Whether narrowing a margin from below is always POSSIBLE. §10-11 measured that on
#    a rule-13-clean figure row the achievable spread is median 1ch / p90 2ch, so on
#    those rows neither direction reaches the ladder and the answer was to WAIVE. This
#    fixture asserts the instruction is right, not that every row can satisfy it.
#  * The decisive-margin threshold itself (20ch). That is `--min-margin`, pinned by
#    fixtures_decisive_margin.py.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
