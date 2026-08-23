"""Issue #89 fixtures: `answer` in `build_repair_prompt.py`'s COPY THROUGH block.

THE DEFECT. The prompt tells a repair agent which fields to reproduce character for
character, because `apply_repair.py` refuses the overlay if any of them drift. The code
that rendered them said, in a comment, "the PAYLOAD is authoritative for identity" --
and then read `r.get("answer", it.get("answer"))` from a payload row that HAS NO
`answer` KEY. It carries `answer_letter`. So on the one identity field the author itself
can get wrong, the lookup fell through to the AUTHORED row and echoed the wrong letter
straight back, four lines under an `ASSIGNED: answer=B` naming the right one:

    ASSIGNED:  answer=B   KEY LENGTH RANK 2 of 4 ...
    COPY THROUGH — verbatim, these exact strings:
        "answer": "C"

Whichever instruction the agent followed, the repair was wrong: copy `C` and the defect
survives the round trip; write `B` and `apply_repair` refuses the WHOLE overlay -- every
other row in the batch thrown away with it -- because the printed follow-up command
carried no `--payload`. §10-7 chunk 3's e0063 hit exactly this and was hand-edited.

WHY A FIXTURE AND NOT A COMMENT. This is the third guard in this toolchain to be wrong
while a comment above it described the correct behaviour (#76's GATED_FIELDS, #88's
rule-5 predicate, now this). The rule from §10-11 stands: when a gate's behaviour is
asserted in a comment, assert it in a fixture too.

NON-VACUITY: the mismatch cases assert what the OLD expression would have rendered, so a
regression that reverts the lookup fails here rather than passing for the wrong reason.
The clean-batch cases are the other half -- `--payload` must NOT appear when no row needs
it, since it widens what the merge will accept.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_repair_answer_letter.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded -- an absolute path into a session
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
MODEL_DIR = GEN.parents[1]                 # backend/test-gen-model
sys.path.insert(0, str(GEN))
import apply_repair  # noqa: E402
import build_repair_prompt as brp  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# A payload row and an authored row, in the two shapes the real tools produce.
# `build_area.py` writes the payload; the authoring agent writes the part.
# ---------------------------------------------------------------------------
def payload_row(cid: str, letter: str) -> dict:
    return {
        "cand_id": cid,
        "cluster": "entrepreneurship",
        "level": "District",
        "instructionalArea": "Operations",
        "performanceIndicator": "Apply project-management tools",
        "difficulty": "easy",
        "answer_letter": letter,
        "option_length_band": [15, 55],
        "key_may_be_longest": False,
        "longest_letter": "D",
    }


def authored_row(cid: str, letter: str) -> dict:
    return {
        "cand_id": cid,
        "cluster": "entrepreneurship",
        "level": "District",
        "instructionalArea": "Operations",
        "performanceIndicator": "Apply project-management tools",
        "difficulty": "easy",
        "question": "A team leader tracking overlapping deadlines needs to see how "
                    "tasks depend on one another. Which document shows that best?",
        "options": {
            "A": "A Gantt chart of task dependencies",
            "B": "A team resource allocation spreadsheet",
            "C": "A project budget summary",
            "D": "A milestone chart marking each deliverable's due date",
        },
        "answer": letter,
        "explanation": "A is correct because a Gantt chart plots dependencies; (B) "
                       "allocates people rather than sequencing work, (C) tracks money, "
                       "and (D) marks dates without showing what blocks what.",
    }


GATE_MISMATCH = """\
  FAIL  ent-district-pool-cand-e0001  [easy] Apply project-management tools
          hard: answer 'B' != assigned letter 'A'

"""
GATE_CLEAN = """\
  FAIL  ent-district-pool-cand-e0001  [easy] Apply project-management tools
          hard: key is the longest option

"""

CID = "ent-district-pool-cand-e0001"


def build(gate_text: str, assigned: str, authored: str):
    """Run the real tool over real files. Returns (prompt text, printed stdout)."""
    tmp = Path(tempfile.mkdtemp(prefix="issue89-"))
    (tmp / "payload.json").write_text(json.dumps([payload_row(CID, assigned)]))
    (tmp / "part1.json").write_text(json.dumps([authored_row(CID, authored)]))
    (tmp / "gate.txt").write_text(gate_text)
    argv = sys.argv
    sys.argv = ["build_repair_prompt.py",
                "--payload", str(tmp / "payload.json"),
                "--gate", str(tmp / "gate.txt"),
                "--part", str(tmp / "part1.json"),
                "--out", str(tmp / "prompt.txt"),
                "--overlay", str(tmp / "overlay.json"),
                # A 1-row batch is under issue #127's pooling floor, so the tool now
                # asks why it is running alone. It is a fixture; that is the reason.
                # The guard itself is pinned in fixtures_repair_round_guards.py.
                "--solo-reason", "fixture — one synthetic row, no agent is launched"]
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            brp.main()
    finally:
        sys.argv = argv
    return (tmp / "prompt.txt").read_text(encoding="utf-8"), buf.getvalue()


def copy_through(prompt: str, field: str) -> str:
    """The value the first row's COPY THROUGH block tells the agent to write.

    Scanned from the block's own marker LINE, not from the whole prompt and not from
    the first mention of the phrase: the HEADER quotes "COPY THROUGH" in prose and then
    prints a "SHAPE OF ONE OBJECT" example carrying `"answer": "<letter>", ...` at the
    same indent, so a looser match reads the placeholder as the instruction.
    """
    needle = '      "%s": ' % field
    marker = "  COPY THROUGH — verbatim, these exact strings:"
    if marker not in prompt:
        return "<no COPY THROUGH block>"
    for line in prompt.split(marker, 1)[1].splitlines():
        if line.startswith(needle):
            return json.loads(line[len(needle):])
    return "<not rendered>"


def scope_line(prompt: str) -> str:
    """The first ROW's REPAIR SCOPE line — the header explains the line in prose."""
    return next((ln.strip() for ln in prompt.splitlines()
                 if ln.startswith("  REPAIR SCOPE:")), "<no row scope line>")


print("Issue #89 -- the `answer` COPY THROUGH block\n")

# ---------------------------------------------------------------------------
# 1. THE ROOT CAUSE. A payload row has no `answer`, so a `.get("answer")` on it can
#    only ever fall through. Asserted on the SYNTHETIC row and on every real payload
#    committed under output/, because the fix is an alias table and the table is only
#    correct if it covers the shapes build_area actually writes.
# ---------------------------------------------------------------------------
print("the two row shapes:")
check("a payload row carries `answer_letter` and NOT `answer`",
      "answer" not in payload_row(CID, "A") and "answer_letter" in payload_row(CID, "A"),
      "this is why the old `r.get('answer', it.get('answer'))` always read the part file")
check("PAYLOAD_ALIAS maps `answer` -> `answer_letter`",
      brp.PAYLOAD_ALIAS.get("answer") == "answer_letter",
      f"PAYLOAD_ALIAS = {brp.PAYLOAD_ALIAS}")
check("`difficulty` is the ONE field still read off the authored row (§10-8)",
      brp.AUTHORED_SOURCE == ("difficulty",),
      f"AUTHORED_SOURCE = {brp.AUTHORED_SOURCE}")
# The prompt's identity set must not drift from the set the merge tool enforces:
# a field in one and not the other is either an uninstructed refusal or an
# unmentioned freeze. `cand_id` is build-side only -- apply_repair matches on it.
check("IDENTITY mirrors apply_repair.IDENTITY, plus the id field",
      set(brp.IDENTITY) == set(apply_repair.IDENTITY) | {"cand_id"},
      f"prompt {brp.IDENTITY}\n          merge  {apply_repair.IDENTITY}")

# ---------------------------------------------------------------------------
# 2. THE DEFECT ROW. Payload assigns A; the author wrote B.
# ---------------------------------------------------------------------------
print("\nauthored answer B, assigned A — the issue-89 row:")
prompt, printed = build(GATE_MISMATCH, assigned="A", authored="B")

check("COPY THROUGH renders the ASSIGNED letter",
      copy_through(prompt, "answer") == "A",
      f'rendered "answer": {copy_through(prompt, "answer")!r}')
# Non-vacuity: the old expression, run on the same two rows, renders the wrong letter.
# If this ever stops being true the case above proves nothing.
old = payload_row(CID, "A").get("answer", authored_row(CID, "B").get("answer"))
check("REGRESSION ANCHOR: the old lookup would have rendered 'B'", old == "B",
      f"r.get('answer', it.get('answer')) == {old!r} — the defect, reproduced")
check("COPY THROUGH still renders the AUTHORED difficulty, not the payload's request",
      copy_through(prompt, "difficulty") == "easy")
check("the row carries the `answer`-is-the-defect warning",
      "THE `answer` FIELD ON THIS ROW IS THE DEFECT" in prompt
      and "Payload assigns A" in prompt)
check("the batch header names the row as the identity exception",
      "`answer` IS THE EXCEPTION ON 1 ROW(S)" in prompt and CID in prompt.split(
          "You are changing ONLY")[0])
check("the KEY marker sits on the ASSIGNED letter, not the authored one",
      "A Gantt chart of task dependencies" in prompt.split("<-- KEY")[1][:200],
      "marking the authored letter KEY would aim the repair at the wrong option")
check("the authored letter is called out as the defect in CURRENT OPTIONS",
      "the authored `answer` points HERE" in prompt)
check("the row's REPAIR SCOPE names `answer` (not the bare OPTIONS ONLY catch-all)",
      "REPAIR SCOPE: THE `answer` LETTER" in prompt,
      scope_line(prompt))
check("the printed apply_repair command carries --payload",
      "--payload " in printed,
      [ln.strip() for ln in printed.splitlines() if "apply_repair.py" in ln][0][:160])
check("and says why",
      "--payload is REQUIRED here" in printed and "e0001 B->A" in printed)

# ---------------------------------------------------------------------------
# 3. THE CLEAN BATCH. Nothing above may fire when no row's letter is wrong --
#    --payload widens what the merge accepts and must not be handed out by default.
# ---------------------------------------------------------------------------
print("\nauthored answer A, assigned A — an ordinary repair batch:")
prompt, printed = build(GATE_CLEAN, assigned="A", authored="A")

check("COPY THROUGH renders the letter both rows agree on",
      copy_through(prompt, "answer") == "A")
check("NO --payload in the printed command", "--payload" not in printed,
      [ln.strip() for ln in printed.splitlines() if "apply_repair.py" in ln][0][:160])
check("no `answer`-exception block in the header",
      "IS THE EXCEPTION ON" not in prompt)
check("no per-row warning block",
      "THE `answer` FIELD ON THIS ROW IS THE DEFECT" not in prompt)
check("the scope stays OPTIONS ONLY for a key-longest finding",
      "REPAIR SCOPE: OPTIONS ONLY" in prompt, scope_line(prompt))

# ---------------------------------------------------------------------------
# 4. THE LOUD FAILURE. A payload row missing an identity field must raise, not fall
#    back -- the silent fallback IS this issue. (#76's GATED_FIELDS correction, applied
#    one tool over.)
# ---------------------------------------------------------------------------
print("\nthe next field that goes missing:")
short = payload_row(CID, "A")
del short["performanceIndicator"]
try:
    brp.payload_identity(short, authored_row(CID, "A"))
    raised = ""
except SystemExit as e:
    raised = str(e)
check("payload_identity raises on an identity field the payload lacks",
      "performanceIndicator" in raised and "issue #89" in raised,
      (raised.splitlines() or ["<no exception — it fell back silently>"])[0])
# ...and does NOT raise for `difficulty`, which legitimately lives on the authored row.
no_diff = payload_row(CID, "A")
del no_diff["difficulty"]
try:
    vals = brp.payload_identity(no_diff, authored_row(CID, "A"))
    ok = vals["difficulty"] == "easy"
except SystemExit as e:
    ok, vals = False, str(e)
check("...but AUTHORED_SOURCE fields are exempt", ok,
      f"difficulty resolved to {vals!r}" if not ok else "difficulty = 'easy' (authored)")

# ---------------------------------------------------------------------------
# 5. BLAST RADIUS. Every payload committed under output/ must resolve every identity
#    field through the same code path -- a real slice that raised here would be a
#    payload shape the alias table does not know about.
# ---------------------------------------------------------------------------
print("\ncommitted payloads:")
files = sorted((MODEL_DIR / "output").glob("plan-10/*/payload/*.json"))
scanned, bad = 0, []
for path in files:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        bad.append(f"{path.name}: unreadable — {e}")
        continue
    if not isinstance(rows, list):
        continue
    for r in rows:
        scanned += 1
        try:
            brp.payload_identity(r, {"difficulty": r.get("difficulty")})
        except SystemExit as e:
            bad.append(str(e).splitlines()[0])
check(f"every identity field resolves on all {scanned} committed payload rows "
      f"({len(files)} file(s))",
      scanned > 0 and not bad,
      "\n          ".join(bad[:5]) if bad else f"{scanned} rows, 0 unresolved")

# ---------------------------------------------------------------------------
# What this fixture does NOT check -- state it, don't imply coverage.
#
#  * That the REPAIR AGENT obeys the corrected block. Nothing here reads a model; the
#    prompt is the instrument and apply_repair --payload is the enforcement, and that
#    pairing is what is pinned.
#  * Whether the ASSIGNED letter is the genuinely correct answer. The payload assigns
#    letters to balance the key distribution (build_area.py rule 10); it cannot know
#    which option is true. The row block offers the option-swap branch for exactly that
#    case, and there is no mechanical test for which branch applies.
#  * The other direction of a letter defect -- a row where BOTH the payload and the
#    author are wrong about the answer. `check_key_figures.py` is the smoke detector
#    for that, at 7.9% coverage; 0.00% there never means the arithmetic is right.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
