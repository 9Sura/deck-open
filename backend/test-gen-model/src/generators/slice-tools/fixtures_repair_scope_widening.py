"""Issue #130 fixtures: the repair scope was inverted, and --finding is the way out.

THE DEFECT. `build_repair_prompt.finding_scope()` derived a row's field scope ONLY from
the wording of that row's `check_authored` gate lines. A gate line matching none of
STEM_FINDINGS / EXPLANATION_FINDINGS / LETTER_FINDINGS falls through to
`fields.add("options")`; a row with NO gate line at all falls to UNSCOPED, which is
`("question", "options")`. So:

    gate line "key is the longest option"  ->  ('options',)              NARROW
    no gate line (named by hand, --ids)    ->  ('question', 'options')   WIDER

THE MORE EVIDENCE A ROW CARRIED, THE LESS OF IT COULD BE REPAIRED. §10-13 shipped
e0026, e0037 and e0040 into the entrepreneurship/ICDC pool with stem defects a blind
rater had found on all three -- each carried a soft length line, so the prompt told the
author the stem was copied through verbatim and the author correctly declined. m0003,
e0011 and m0013, audit-only with no gate line, had their stems fixed in the same run.

FACET TWO, worse: `explanation` is reachable from exactly two gate strings and is NOT in
UNSCOPED, so an audit-found explanation defect was undeliverable on EVERY row. §10-13's
arithmetic auditor found three explanations that do not reproduce their own stated
derivation and the whole batch had to be hand-written around the tool.

WHY A FIXTURE. Same reason as #76, #88, #89 and #127: this toolchain's rules survive as
code and evaporate as comments. #77 built the derivation, its comment described it
correctly, and nobody noticed it had no way in from outside the gate's vocabulary.

NON-VACUITY. The fix is ADDITIVE, so the old narrow derivation is asserted to still
hold with no --finding passed -- a regression that loosened everything would pass a
"the stem is in scope" check for entirely the wrong reason. The refusal cases are each
paired with the same call one argument different.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_repair_scope_widening.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, never hardcoded.
"""
import io
import json
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
import build_repair_prompt as brp  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# The two row shapes the real tools produce, in miniature.
# ---------------------------------------------------------------------------
def payload_row(cid: str) -> dict:
    return {
        "cand_id": cid, "cluster": "entrepreneurship", "level": "ICDC",
        "instructionalArea": "Operations",
        "performanceIndicator": "Apply project-management tools",
        "difficulty": "easy", "answer_letter": "A",
        "option_length_band": [15, 55], "key_may_be_longest": False,
        "longest_letter": "D",
    }


def authored_row(cid: str) -> dict:
    return {
        "cand_id": cid, "cluster": "entrepreneurship", "level": "ICDC",
        "instructionalArea": "Operations",
        "performanceIndicator": "Apply project-management tools",
        "difficulty": "easy",
        "question": "A founder tracking overlapping deadlines needs to see how tasks "
                    "depend on one another. Which document shows that best?",
        "options": {
            "A": "A Gantt chart of task dependencies",
            "B": "A team resource allocation spreadsheet",
            "C": "A project budget summary",
            "D": "A milestone chart marking each deliverable's due date",
        },
        "answer": "A",
        "explanation": "A is correct because a Gantt chart plots dependencies; (B) "
                       "allocates people, (C) tracks money, (D) marks dates only.",
    }


def gate_text(cids) -> str:
    """§10-13's own shape: a SOFT length finding that names no field."""
    return "".join(
        "  soft  %s  [easy] Apply project-management tools\n"
        "          possible length giveaway: key is the longest option\n\n" % c
        for c in cids)


def slice_dir(n_rows: int, n_flagged: int) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="issue130-"))
    cids = ["ent-icdc-pool-cand-e%04d" % i for i in range(1, n_rows + 1)]
    (tmp / "payload.json").write_text(json.dumps([payload_row(c) for c in cids]))
    (tmp / "chunk10-part1.json").write_text(json.dumps([authored_row(c) for c in cids]))
    time.sleep(0.01)   # the honest order: the report is written AFTER the parts it reads
    (tmp / "gate.txt").write_text(gate_text(cids[:n_flagged]))
    return tmp


def build(tmp: Path, findings=(), **flags):
    """Run the real tool over real files. Returns (stdout, SystemExit message or '')."""
    argv = sys.argv
    sys.argv = ["build_repair_prompt.py",
                "--payload", str(tmp / "payload.json"),
                "--gate", str(tmp / "gate.txt"),
                "--part", str(tmp / "chunk10-part1.json"),
                "--out", str(tmp / "repair.prompt.txt"),
                "--overlay", str(tmp / "repair.json")]
    for k, v in flags.items():
        sys.argv += ["--" + k.replace("_", "-")] + (v if isinstance(v, list) else [v])
    for f in findings:          # append-action: one flag per value, never `--finding a b`
        sys.argv += ["--finding", f]
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            brp.main()
        return buf.getvalue(), ""
    except SystemExit as e:
        return buf.getvalue(), str(e)
    finally:
        sys.argv = argv


def prompt(tmp: Path) -> str:
    return (tmp / "repair.prompt.txt").read_text()


def row_block(tmp: Path, cid: str) -> str:
    """One row's section of the prompt, so a check cannot pass on a neighbour's text."""
    body = prompt(tmp)
    i = body.index("\n%s   [" % cid)
    j = body.find("\n" + "-" * 78, i)
    return body[i:j if j > 0 else len(body)]


CIDS = ["ent-icdc-pool-cand-e%04d" % i for i in range(1, 26)]
FLAGGED, AUDIT_ONLY = CIDS[:20], CIDS[20:]

print("Issue #130 -- the inverted repair scope\n")

# ---------------------------------------------------------------------------
# THE INVERSION, on the function itself. These are the numbers from the issue.
# ---------------------------------------------------------------------------
print("the inversion (asserted, not described):")
soft = ["[soft]", "possible length giveaway: key is the longest option"]
check("a gate-flagged length row is scoped OPTIONS ONLY",
      brp.finding_scope(soft) == ("options",), str(brp.finding_scope(soft)))
check("...while the SAME row with no gate line is scoped WIDER",
      brp.finding_scope([]) == ("question", "options"), str(brp.finding_scope([])))
check("that is the defect: more evidence, narrower repair",
      len(brp.finding_scope(soft)) < len(brp.finding_scope([])))
check("and `explanation` was reachable from NEITHER — facet two",
      "explanation" not in brp.finding_scope(soft)
      and "explanation" not in brp.finding_scope([]),
      "UNSCOPED = %s" % (brp.UNSCOPED,))

# ---------------------------------------------------------------------------
# --finding opens the field. NON-VACUITY: the derivation above is unchanged, so the
# widening has to come from the flag and cannot come from a loosened default.
# ---------------------------------------------------------------------------
print("\n--finding, the way out:")
check("it is additive — no --finding, no change",
      brp.finding_scope(soft, False, ()) == ("options",))
check("--finding question opens the stem on a gate-flagged row",
      brp.finding_scope(soft, False, ("question",)) == ("question", "options"),
      str(brp.finding_scope(soft, False, ("question",))))
check("--finding explanation reaches the scope SCOPE_WORD always had",
      brp.finding_scope([], False, ("explanation",)) == ("explanation",)
      and ("explanation",) in brp.SCOPE_WORD)
check("...and it SUPPRESSES the UNSCOPED fallback rather than adding to it",
      "question" not in brp.finding_scope([], False, ("explanation",)),
      "the operator said which field is wrong; a second --finding opens a second field")
check("a letter mismatch still wins its own scope alongside a widening",
      brp.finding_scope(soft, True, ("question",))
      == ("answer", "question", "options"))

# ---------------------------------------------------------------------------
# END TO END, on the §10-13 shape: 20 gate-flagged rows, three with an audit stem
# finding. This is e0026/e0037/e0040 exactly.
# ---------------------------------------------------------------------------
print("\nend to end — §10-13's three lost stem repairs:")
tmp = slice_dir(20, 20)
printed, err = build(tmp)
block = row_block(tmp, FLAGGED[0])
check("without --finding the prompt freezes the stem, as it did in §10-13",
      not err and "REPAIR SCOPE: OPTIONS ONLY" in block
      and "the stem and the explanation are copied through verbatim" in block,
      (err.splitlines() or ["OPTIONS ONLY on every row"])[0])
check("...and the merge command freezes it too", "--also-freeze question" in printed)

STEM_FINDING = ("stem says the products themselves did not change, which eliminates "
                "distractor C without any business knowledge")
printed, err = build(tmp, findings=[
    "%s:question:%s" % (c, STEM_FINDING) for c in FLAGGED[:3]])
check("with --finding the three rows may move their stems", not err
      and all("REPAIR SCOPE: the stem and the options" in row_block(tmp, c)
              for c in FLAGGED[:3]),
      (err.splitlines() or ["3 rows widened"])[0])
check("...and the other 17 are UNCHANGED — widening is per row, not per batch",
      all("REPAIR SCOPE: OPTIONS ONLY" in row_block(tmp, c) for c in FLAGGED[3:]))
check("the audit's own words are printed on the row, as evidence",
      STEM_FINDING in row_block(tmp, FLAGGED[0])
      and "AN AUDIT ALSO SAID" in row_block(tmp, FLAGGED[0]),
      "the author is told WHO said it and left to judge the row")
check("...and NOT on a row it was not passed for",
      STEM_FINDING not in row_block(tmp, FLAGGED[5]))
check("the merge stops freezing the stem, so the scope is enforced not just stated",
      "--also-freeze question" not in printed,
      "apply_repair would otherwise refuse the very repair the prompt asked for")
check("stdout names the rows the flag moved",
      "fields opened by --finding" in printed
      and all(c in printed for c in FLAGGED[:3]),
      [ln.strip() for ln in printed.splitlines() if "--finding" in ln][0][:100])
check("stdout also names the rows that are still NARROWED — the invisible half",
      "narrowed: 17 of 20 row(s) may touch OPTIONS only" in printed
      and all(c in printed for c in FLAGGED[3:6]),
      [ln.strip() for ln in printed.splitlines() if "narrowed" in ln][0][:100])
rec = json.loads((tmp / "repair.prompt.scope.json").read_text())
check("the scope record carries both axes: every row's fields, and the findings",
      rec["scopes"][FLAGGED[0]] == ["question", "options"]
      and rec["out_of_band_findings"][FLAGGED[0]][0]["field"] == "question"
      and STEM_FINDING in rec["out_of_band_findings"][FLAGGED[0]][0]["text"]
      and rec["fields_widened"][FLAGGED[0]] == ["question"],
      "so 'what was this agent asked to fix' needs no overlay archaeology")

# §10-13's chunk 10 was 3 of 3 rows options-only. `scope: 3 row(s) options` said so and
# read as a summary, not as a refusal, so the all-narrowed case is the one that most
# needs this line -- suppressing it as "redundant" would re-hide the original defect.
# Run LAST in this block: it rewrites the scope record the check above reads.
printed_all, _ = build(tmp)
check("...including when the WHOLE batch is narrowed, which is §10-13's own shape",
      "narrowed: 20 of 20 row(s)" in printed_all
      and "NOT deliverable on them without --finding" in printed_all,
      [ln.strip() for ln in printed_all.splitlines() if "narrowed" in ln][0][:100])

# ---------------------------------------------------------------------------
# FACET TWO: the arithmetic auditor's three explanation defects, on a CLEAN batch.
# ---------------------------------------------------------------------------
print("\nfacet two — an explanation defect on a batch whose gates are clean:")
tmp2 = slice_dir(25, 20)
printed, err = build(tmp2, ids=CIDS,
                     scope_reason="stated derivation does not reproduce the keyed figure")
check("an audit-only row's explanation is STILL frozen with no --finding", not err
      and "CURRENT EXPLANATION — OUT OF SCOPE" in row_block(tmp2, AUDIT_ONLY[0]),
      (err.splitlines() or ["the §10-13 dead end"])[0])

ARITH = "stated derivation gives 42%: the keyed option reads 38%"
printed, err = build(tmp2, ids=CIDS,
                     scope_reason="stated derivation does not reproduce the keyed figure",
                     findings=["%s:explanation:%s" % (AUDIT_ONLY[0], ARITH)])
blk = row_block(tmp2, AUDIT_ONLY[0])
check("--finding explanation makes it repairable", not err
      and "REPAIR SCOPE: THE EXPLANATION ONLY" in blk
      and "CURRENT EXPLANATION — IN SCOPE" in blk,
      (err.splitlines() or ["explanation opened"])[0])
check("the colon INSIDE the finding text survives the parse",
      ARITH in blk, "split(':', 2) — the text routinely carries one")
check("the header's explanation opener names the row and drops the gate-only claim",
      AUDIT_ONLY[0] in prompt(tmp2).split("THE SHAPE OF ONE OBJECT")[0]
      and "only because a finding on that row names the explanation itself"
          in prompt(tmp2))
check("every other row's explanation stays frozen",
      "CURRENT EXPLANATION — OUT OF SCOPE" in row_block(tmp2, FLAGGED[0]),
      "§10-10: both repair agents rewrote explanations they were not asked to touch")

# ---------------------------------------------------------------------------
# THE REFUSALS. Each paired with the same call one argument different.
# ---------------------------------------------------------------------------
print("\nthe refusals:")
ok_finding = "%s:question:%s" % (FLAGGED[0], STEM_FINDING)
tmp3 = slice_dir(20, 20)

printed, err = build(tmp3, findings=[ok_finding])
check("the well-formed control builds", not err, (err.splitlines() or ["built"])[0])

for label, bad, needle in (
    ("a --finding with no colons at all",
     "just some prose about a stem", "is not <cand_id>:<field>:<text>"),
    ("a --finding with only one colon",
     "%s:the stem is wrong" % FLAGGED[0], "It needs two colons"),
    ("a --finding with empty text",
     "%s:question:" % FLAGGED[0], "must be non-empty"),
    ("an unknown field",
     "%s:stem:the stem is wrong" % FLAGGED[0], "not a field this prompt can open"),
    ("`answer`, which is MEASURED and not assertable",
     "%s:answer:the key is B" % FLAGGED[0], "not widenable by hand"),
):
    printed, err = build(tmp3, findings=[bad])
    check("%s is REFUSED" % label, needle in err,
          (err.splitlines() or ["<built anyway>"])[0][:110])

check("...and the answer refusal says WHY, not just no",
      "assigned letter" in build(tmp3, findings=["%s:answer:x" % FLAGGED[0]])[1],
      "apply_repair accepts that move only onto the assigned letter, with --payload")
check("...and every refusal shows the shape it wanted",
      "--finding \"e0037:question:" in build(tmp3, findings=["nope"])[1])

printed, err = build(tmp3, ids=FLAGGED[:16],
                     findings=["%s:question:%s" % (FLAGGED[18], STEM_FINDING)])
check("a --finding naming a row this prompt does not cover is REFUSED",
      "this prompt does not cover" in err, (err.splitlines() or ["<no-op>"])[0])
check("...and it points at --ids + --scope-reason rather than adding the row",
      "--scope-reason" in err and "guard 2" in err,
      "the row axis is guard 2's; --finding must not route around it")

# A finding on a field the row already has is legitimate — the author still reads it —
# but it is not a widening and must not be reported as one.
printed, err = build(tmp3, findings=["%s:options:distractors B and C say the same thing"
                                     % FLAGGED[0]])
check("a --finding on an already-in-scope field prints but reports no widening",
      not err and "distractors B and C" in row_block(tmp3, FLAGGED[0])
      and "fields opened by --finding" not in printed,
      (err.splitlines() or ["printed as evidence, no scope change"])[0])

# ---------------------------------------------------------------------------
# What these fixtures do NOT check -- state it, don't imply coverage.
#
#  * That the finding is TRUE. --finding carries an audit's words into a prompt; nothing
#    here (and nothing in the tool) can tell a real stem defect from a rater's post-hoc
#    rationalisation. §10-7's rule stands: action a blind-solver cue only when both
#    solvers cite the same concrete thing AND a rater found it independently.
#  * That the author OBEYS the widened scope. apply_repair's --also-freeze is the
#    machine half, and it can only freeze fields the prompt did not open.
#  * Whether a row SHOULD have been widened. Guard 2 asks for a criterion on the row
#    axis; the finding text is the criterion on the field axis, and only a reader can
#    tell "the stem eliminates C on its own" from "the audit flagged it".
#  * The gate's own vocabulary. STEM_FINDINGS is still a phrase list and still only
#    recognises wording it has already seen -- 0 stem findings never meant clean, and
#    this changes nothing about that.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
