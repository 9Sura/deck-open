"""Issue #173 fixtures: the held-hard rubric is COMMITTED, and the rater split is REPORTED.

THE DEFECT. Plan-10's headline quality number for a hard batch -- "held hard, never authored
hard" -- came from two raters who were never told what hard means. `build_hard_verify.py`
stage 1 wrote a two-line instruction ("rate each: HARD, MEDIUM (demote), or DEFECTIVE") and
every slice plan's H1 block said only *"run 2 Sonnet raters. Reconcile. Both-medium =>
demote, honestly."* Each rater supplied its own rubric, and their returns were prose in two
agent replies that nothing on disk ever held.

§10-14, 21 rows, two Sonnet raters with the same task text, run independently:

    rater      HARD   MEDIUM   DEFECTIVE   agreed HARD with the other
    A            18        1           2                            3
    B             3       16           2                            3

Both re-derived all 21 items and both found the arithmetic sound, so this is NOT a
correctness disagreement. A counted DEPENDENT OPERATIONS; B counted OPERATIONS A COMPETENT
DISTRICT COMPETITOR ACTUALLY PERFORMS, discounting drilled chains. Both defensible. The
published number, 16 of 21, came from breaking the ties mechanically; rater B's own reading
is 3 of 21; and 0/19, 7/25, 7/22, ~10/19 were all produced the same way.

THE FIX IS TWO HALVES THAT FAIL IN OPPOSITE DIRECTIONS, which is why both are here:

  the COMMITTED RUBRIC in the referee set     removes the CAUSE -- §10-10 measured a written
                                              "second operation" rule moving agreement 6-of-9
                                              to 8-of-9. It cannot PROVE it worked: prose is
                                              not enforceable and two models can read it apart.
  `reconcile_raters.py`                       measures the RESIDUE -- the split is printed on
                                              the same line as the held count, mechanically,
                                              free, and cannot be forgotten.

NON-VACUITY runs through the file. The §10-14 marginals are replayed EXACTLY (18/1/2 vs
3/16/2, agreeing HARD on h0001/h0013/h0015 and demoting h0004) in a DEFECT arm, against a
NARROW-AGREEMENT control arm that must come back without the banner -- an instrument that
shouts on every batch is measuring nothing. Every refusal is shown FAILING on a hand-broken
input, so a regression that stops checking one fails here.

WHAT THIS FIXTURE DOES NOT CHECK -- stated, not implied:
  * That two raters given the rubric AGREE. That is a model behaviour and no fixture pins it.
    What is pinned is that their disagreement is measured and printed whatever it is.
  * That the rubric is RIGHT. Whether "independently fallible" is the correct line between
    hard and medium is a judgement recorded in plan-10 §4.6, not a testable property.
  * The blind SPREAD's cause. Two raters sharing a WRONG rubric agree, the split reads zero,
    and this suite reports a clean batch. That blind spot is real; the answer to it is that
    the rubric is committed and diffable, not that some instrument detects it.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_hard_referee_rubric.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded (#157).
"""
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
import build_hard_verify as bhv  # noqa: E402
import reconcile_raters as rr  # noqa: E402

REPO = Path(__file__).resolve().parents[5]
PLAN = REPO / "backend/test-gen-model/plans/10-per-pi-review-depth-plan.md"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# §10-14's H1, replayed from its real marginals. 21 rows:
#   3 agreed HARD (h0001, h0013, h0015) · 1 agreed MEDIUM (h0004)
#   2 agreed DEFECTIVE · 15 split A=HARD / B=MEDIUM
# which is exactly 18/1/2 for A and 3/16/2 for B.
# ---------------------------------------------------------------------------
PRE = "mkt-district-pool-cand-"
AGREED_HARD = [f"{PRE}h0001", f"{PRE}h0013", f"{PRE}h0015"]
AGREED_MEDIUM = [f"{PRE}h0004"]
AGREED_DEFECTIVE = [f"{PRE}h0016", f"{PRE}h0019"]
SPLIT = [f"{PRE}h{n:04d}" for n in
         (2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 14, 17, 18, 20, 21)]
ALL_IDS = AGREED_HARD + AGREED_MEDIUM + AGREED_DEFECTIVE + SPLIT

# Rater B's note on h0007, verbatim from the summary — the clearest statement of the gap.
B_NOTE_H0007 = ("3 multiplications, mechanical once series != additive is known "
                "(heavily drilled DECA convention)")


def item(cid, answer="B"):
    return {
        "cand_id": cid, "cluster": "marketing", "level": "District",
        "instructionalArea": "Pricing",
        "performanceIndicator": "Calculate the cost of a chain discount",
        "question": "A routine two-step pricing stem.",
        "options": {k: f"option {k}" for k in "ABCD"},
        "answer": answer, "explanation": "List price times the chain, then the net.",
        "difficulty": "hard",
    }


def payload_row(cid, answer="B"):
    return {"cand_id": cid, "answer_letter": answer, "route": "C2"}


def rater_row(cid, verdict, lands="C", note="", route="C1", second="a rate conversion"):
    return {"cand_id": cid, "verdict": verdict, "route": route,
            "second_operation": second if verdict != "DEFECTIVE" else "none",
            "skipping_lands_on": lands, "note": note}


def rater_a(lands_map=None):
    lands = lands_map or {}
    return ([rater_row(c, "HARD", lands.get(c, "C")) for c in AGREED_HARD]
            + [rater_row(c, "MEDIUM", "none") for c in AGREED_MEDIUM]
            + [rater_row(c, "DEFECTIVE", "none", "a second option is equally correct")
               for c in AGREED_DEFECTIVE]
            + [rater_row(c, "HARD", lands.get(c, "C")) for c in SPLIT])


def rater_b(lands_map=None):
    lands = lands_map or {}
    return ([rater_row(c, "HARD", lands.get(c, "C")) for c in AGREED_HARD]
            + [rater_row(c, "MEDIUM", "none") for c in AGREED_MEDIUM]
            + [rater_row(c, "DEFECTIVE", "none", "the key does not follow from the stem")
               for c in AGREED_DEFECTIVE]
            + [rater_row(c, "MEDIUM", lands.get(c, "C"),
                         B_NOTE_H0007 if c.endswith("h0007") else "drilled chain")
               for c in SPLIT])


def run(mod, *argv):
    """main() with stdout captured. Returns (text, exit_code)."""
    saved = sys.argv
    sys.argv = [mod.__name__ + ".py", *argv]
    buf = io.StringIO()
    code = 0
    try:
        with redirect_stdout(buf):
            mod.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if isinstance(e.code, str):
            buf.write(e.code)
    finally:
        sys.argv = saved
    return buf.getvalue(), code


def build_stage1(tmp, ids):
    """Write payload + part, run stage 1, return (text, code, outdir)."""
    rows = [item(c) for c in ids]
    (tmp / "h1.json").write_text(json.dumps([payload_row(c) for c in ids]),
                                 encoding="utf-8")
    (tmp / "h1-part1.json").write_text(json.dumps(rows), encoding="utf-8")
    outdir = tmp / "verify"
    text, code = run(bhv, "--payload", str(tmp / "h1.json"), "--part",
                     str(tmp / "h1-part1.json"), "--out", str(outdir))
    return text, code, outdir


def write_raters(tmp, a, b):
    (tmp / "r1.json").write_text(json.dumps(a), encoding="utf-8")
    (tmp / "r2.json").write_text(json.dumps(b), encoding="utf-8")
    return str(tmp / "r1.json"), str(tmp / "r2.json")


print("Issue #173 — the rubric is committed, and the split is reported\n")

# ---------------------------------------------------------------------------
# 1. STAGE 1 WRITES THE COMMITTED RUBRIC, NOT A TWO-LINE INSTRUCTION.
# ---------------------------------------------------------------------------
print("stage 1 — the referee set:")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    text, code, outdir = build_stage1(tmp, ALL_IDS)
    check("stage 1 builds and writes both files", code == 0
          and (outdir / "referee-set.txt").exists()
          and (outdir / "referee-ids.json").exists())

    rset = (outdir / "referee-set.txt").read_text(encoding="utf-8")
    rubric = bhv.REFEREE_PROMPT.read_text(encoding="utf-8")
    check("the rubric is the COMMITTED file, verbatim",
          rubric.rstrip() in rset,
          f"{bhv.REFEREE_PROMPT.name}, {len(rubric)} chars — not a per-slice paraphrase")
    check("the old bare instruction is GONE",
          "Rate each: HARD, MEDIUM (demote), or DEFECTIVE." not in rset,
          "twelve slices ran on those two lines")
    check("the set still shows keys and explanations (raters are NOT blind)",
          "AUTHORED KEY" in rset and "List price times the chain" in rset,
          "NON-VACUITY: stage 1's whole difference from stage 2 is that it is not blind")

    for name, needle in [
            ("the mechanical test", "SKIPPING IT LANDS EXACTLY ON AN OFFERED DISTRACTOR"),
            ("the not-a-chain bar", "A NAMED SINGLE FORMULA IS NOT A CHAIN"),
            ("the independently-fallible line", "INDEPENDENTLY FALLIBLE"),
            ("rater B's rubric, ruled OUT by name", "DO NOT APPLY A \"WOULD A COMPETENT"),
            ("the §10-14 numbers as the reason", "18        1           2"),
            ("one rater is not a correctness check", "OTHER RATED IT HARD")]:
        check(f"...and carries {name}", needle in rset)

    ids_meta = json.loads((outdir / "referee-ids.json").read_text())
    check("the id sidecar holds every row, in order",
          ids_meta["ids"] == ALL_IDS and ids_meta["n"] == 21
          and ids_meta["cluster"] == "marketing",
          "nothing on disk held this before — the returns were prose in two agent replies")
    check("stage 1 points at the reconcile step in its own output",
          "reconcile_raters.py" in text and "SAVE EACH RETURN AS JSON" in text)

# ---------------------------------------------------------------------------
# 2. THE DEFECT ARM. §10-14's real marginals through reconcile_raters.
# ---------------------------------------------------------------------------
print("\nthe defect arm (§10-14's 18-vs-3, replayed):")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    _, _, outdir = build_stage1(tmp, ALL_IDS)
    ids_path = str(outdir / "referee-ids.json")
    r1, r2 = write_raters(tmp, rater_a(), rater_b())
    base = ["--ids", ids_path, "--rater", r1, r2]

    out, code = run(rr, *base)
    check("the per-rater marginals reproduce §10-14 exactly",
          "r1.json: 18 HARD · 1 MEDIUM · 2 DEFECTIVE" in out
          and "r2.json: 3 HARD · 16 MEDIUM · 2 DEFECTIVE" in out,
          "if these drift the fixture is no longer replaying the measured slice")
    check("the SPLIT is on the headline line, beside the held count",
          "raters AGREED HARD on 3 · SPLIT on 15" in out,
          next((ln.strip() for ln in out.splitlines() if "HELD" in ln), "<no line>"))
    check("the WIDE SPREAD banner fires", "WIDE SPREAD" in out
          and "rests on TIE-BREAKS" in out,
          "split 15 > agreed-hard 3")
    check("class 1 counts every tie somebody has to break",
          "CLASS 1 — VERDICT SPLIT, HARD vs MEDIUM  (15)" in out)
    check("class 2 counts the defect claims SEPARATELY",
          "CLASS 2 — DEFECTIVE NAMED BY EITHER RATER  (2)" in out,
          "a merged count reads two wrong items as two more routine disagreements (#154)")
    check("the three classes all print, at whatever count",
          out.count("CLASS 1") == 1 and out.count("CLASS 2") == 1
          and out.count("CLASS 3") == 1,
          "a class with no header reads as a class that was not run")
    check("...and it EXITS 1 rather than printing into a scrollback",
          code == 1 and "ADJUDICATION REQUIRED" in out)

    # Class 3: the rubric diagnosis. Both raters ran the mechanical test and agreed on
    # its answer, then split on the verdict anyway -- which is what §10-14 was.
    check("CLASS 3 names the split rows both raters read the SAME structural way",
          "CLASS 3 — RUBRIC DIVERGENCE  (15)" in out and B_NOTE_H0007 in out,
          "rater B's own note is the evidence the disagreement is about the rubric")

    # ...and it must not fire when they disagree about the ITEM rather than the rubric.
    r1b, r2b = write_raters(tmp, rater_a(), rater_b({c: "D" for c in SPLIT}))
    out2, _ = run(rr, "--ids", ids_path, "--rater", r1b, r2b)
    check("...and is EMPTY when they read the mechanical test differently",
          "CLASS 3 — RUBRIC DIVERGENCE  (0)" in out2
          and "CLASS 1 — VERDICT SPLIT, HARD vs MEDIUM  (15)" in out2,
          "class 3 diagnoses class 1; it is not a restatement of it")

# ---------------------------------------------------------------------------
# 3. THE CONTROL ARM. A batch whose raters agree — the banner must stay silent.
# ---------------------------------------------------------------------------
print("\nthe control arm (raters agree on 17 of 21):")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    _, _, outdir = build_stage1(tmp, ALL_IDS)
    agreed = [rater_row(c, "HARD") for c in ALL_IDS[:17]] \
        + [rater_row(c, "MEDIUM", "none") for c in ALL_IDS[17:]]
    r1, r2 = write_raters(tmp, agreed, list(agreed))
    out, code = run(rr, "--ids", str(outdir / "referee-ids.json"), "--rater", r1, r2)
    check("every class is EMPTY and the run exits 0",
          code == 0 and "VERDICT SPLIT, HARD vs MEDIUM  (0)" in out
          and "DEFECTIVE NAMED BY EITHER RATER  (0)" in out
          and "RUBRIC DIVERGENCE  (0)" in out,
          "an instrument that fires on an agreeing batch too is measuring nothing")
    check("the WIDE SPREAD banner stays silent", "WIDE SPREAD" not in out,
          "split 0, agreed-hard 17")
    check("...and the held count is reported anyway",
          "HELD 17 of 21 · raters AGREED HARD on 17 · SPLIT on 0" in out,
          "the split is a first-class field at zero too")

# ---------------------------------------------------------------------------
# 4. THE TIE-BREAK IS AN ARTIFACT. §10-14 broke fifteen ties on one stated rule
#    and wrote it down nowhere; it had to be reconstructed from the summary.
# ---------------------------------------------------------------------------
print("\ntie-breaks and adjudication:")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    _, _, outdir = build_stage1(tmp, ALL_IDS)
    ids_path = str(outdir / "referee-ids.json")
    r1, r2 = write_raters(tmp, rater_a(), rater_b())
    base = ["--ids", ids_path, "--rater", r1, r2]
    RULE = "blind solver 1's per-item 'two or more dependent operations?' answer"
    HELD = SPLIT[:11]

    out, code = run(rr, *base, "--hold", *HELD)
    check("--hold on a split row without --tiebreak-rule is refused",
          code == 1 and "no --tiebreak-rule" in out,
          "the rule IS the artifact — it is what makes the held number readable")

    out, code = run(rr, *base, "--tiebreak-rule", "solver", "--hold", *HELD)
    check("a one-word rule is refused", code == 1 and "State the rule, not a label" in out)

    out, code = run(rr, *base, "--tiebreak-rule", RULE, "--hold", *HELD,
                    *AGREED_DEFECTIVE)
    check("--hold on a DEFECTIVE row with no reason is refused",
          code == 1 and "no --adjudicated reason" in out,
          "a defect claim re-enters the count by repair or refutation, on the record")

    out, code = run(rr, *base, "--tiebreak-rule", RULE, "--hold", AGREED_HARD[0])
    check("--hold on an uncontested row is refused",
          code == 1 and "not contested" in out,
          "it records a tie-break that never happened")

    out, code = run(rr, *base, "--adjudicated", SPLIT[0] + ":looks hard to me")
    check("--adjudicated on a merely SPLIT row is refused",
          code == 1 and "no DEFECTIVE finding" in out,
          "a split is settled by the rule, not by a per-row reason")

    out, code = run(rr, *base, "--tiebreak-rule", RULE, "--adjudicated",
                    AGREED_DEFECTIVE[0])
    check("a bare adjudicated id is refused — the reason IS the artifact",
          code == 1 and "has no reason" in out)

    reasons = [f"{c}:stem repaired; re-derived and the rival reading is gone"
               for c in AGREED_DEFECTIVE]
    out, code = run(rr, *base, "--tiebreak-rule", RULE, "--hold", *HELD,
                    *AGREED_DEFECTIVE, "--adjudicated", *reasons)
    check("a fully settled batch exits 0", code == 0,
          next((ln.strip() for ln in out.splitlines() if "HELD" in ln), "<no line>"))
    check("...and the held count is agreed-hard PLUS the rows the rule held",
          "HELD 16 of 21" in out, "3 agreed + 11 tie-broken + 2 repaired")
    check("...and the rule is PRINTED, with how many rows it covered",
          "applied to 11 of 15 split row(s)" in out and RULE in out)
    check("...and the split rows are marked held vs demoted",
          out.count("[held]") == 11 and out.count("[demoted]") == 4)
    check("...and a wide-spread batch is told to quote the split WITH the number",
          "QUOTE THE SPLIT WITH THE NUMBER" in out and "16 held, raters agreed on 3" in out,
          "the §10-14 rule: report the split before reporting the number")

# ---------------------------------------------------------------------------
# 5. THE PROMPT AND THE PARSER ARE ONE CONTRACT (#139's rule). Here the prompt is
#    a FILE, so the check also catches an edit to the file the parser never saw.
# ---------------------------------------------------------------------------
print("\nthe rubric and the parser, checked against each other:")
head = bhv.referee_head(21, "marketing", "District")
check("the builder reads the PARSER's field list, not a copy of it",
      bhv.RATER_FIELDS is rr.RATER_FIELDS,
      "#76's GATED_FIELDS: a hand-written second list drifts, in both directions")
check("every field reconcile_raters requires is named in the rubric",
      all(f'"{f}"' in head for f in rr.RATER_FIELDS),
      ", ".join(rr.RATER_FIELDS))
check("the rubric tells the rater its disagreement is an instrument",
      "independent raters" in head or "two INDEPENDENT" in head.replace("TWO", "two")
      or "disagreement with the other" in head)
check("...and that its rubric is NOT its own to choose",
      "NOT yours to choose" in head,
      "the whole defect: two defensible rubrics, applied to one batch")

saved = bhv.RATER_FIELDS
try:
    bhv.RATER_FIELDS = saved + ("a_field_no_rubric_names",)
    broke = False
    try:
        bhv.referee_head(21, "marketing", "District")
    except SystemExit as e:
        broke = "a_field_no_rubric_names" in str(e.code)
    check("a parser field the rubric does not name STOPS THE BUILD", broke,
          "NON-VACUITY: the contract check can fail, so it is not decorative")
finally:
    bhv.RATER_FIELDS = saved

saved_path = bhv.REFEREE_PROMPT
try:
    bhv.REFEREE_PROMPT = saved_path.parent / "no-such-rubric.txt"
    broke = False
    try:
        bhv.referee_head(21, "marketing", "District")
    except SystemExit as e:
        broke = "does not fall back" in str(e.code)
    check("a MISSING rubric stops the build rather than falling back", broke,
          "a bare instruction IS the defect; it must not be reachable by accident")
finally:
    bhv.REFEREE_PROMPT = saved_path

# ---------------------------------------------------------------------------
# 6. THE RETURN IS REFUSED, NEVER READ LENIENTLY — #155's shape, one tool over.
# ---------------------------------------------------------------------------
print("\nmalformed rater returns:")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    _, _, outdir = build_stage1(tmp, ALL_IDS)
    ids_path = str(outdir / "referee-ids.json")
    good = [rater_row(c, "HARD") for c in ALL_IDS]

    def with_return(name, data, raw=None):
        p = tmp / name
        p.write_text(raw if raw is not None else json.dumps(data), encoding="utf-8")
        (tmp / "ok.json").write_text(json.dumps(good), encoding="utf-8")
        return run(rr, "--ids", ids_path, "--rater", str(p), str(tmp / "ok.json"))

    out, code = with_return("clean.json", good)
    check("a clean pair passes", code == 0, "NON-VACUITY for the refusals below")

    out, code = with_return("short.json", good[:15])
    check("a return missing rows is refused", code == 1 and "went unrated" in out)

    out, code = with_return("extra.json", good + [rater_row("not-in-this-batch", "HARD")])
    check("a return naming a row outside the referee set is refused",
          code == 1 and "not in the referee set" in out,
          "the #155 shape: a finding that names a real, unrelated question")

    out, code = with_return("dupe.json", good + [rater_row(ALL_IDS[0], "MEDIUM")])
    check("a row returned twice is refused", code == 1 and "returned twice" in out)

    out, code = with_return("hedge.json", [rater_row(ALL_IDS[0], "unsure")] + good[1:])
    check("a verdict outside HARD/MEDIUM/DEFECTIVE is refused",
          code == 1 and "is not one of HARD/MEDIUM/DEFECTIVE" in out,
          "low confidence is a note, not a MEDIUM")

    out, code = with_return("lands.json",
                            [rater_row(ALL_IDS[0], "HARD", lands="maybe C")] + good[1:])
    check("a skipping_lands_on that is neither a letter nor \"none\" is refused",
          code == 1 and "neither an option letter nor" in out)

    out, code = with_return("none.json",
                            [rater_row(ALL_IDS[0], "HARD", lands="none")] + good[1:])
    check("...but \"none\" IS accepted — it is the decisive answer, not a missing one",
          code == 0,
          "no offered skip-result means no second operation; refusing it would lose the "
          "one answer that settles a row")

    out, code = with_return("prose.json", None, raw="Here are my ratings:\n[{}]")
    check("a return wrapped in prose is refused, not salvaged",
          code == 1 and "not valid JSON" in out)

    out, code = run(rr, "--ids", ids_path, "--rater", str(tmp / "clean.json"))
    check("ONE rater is refused", code == 1 and "TWO OR MORE" in out,
          "a held-hard count from one rater is that rater's rubric with no way to see it")

# ---------------------------------------------------------------------------
# 7. THE PLAN. The rubric and the reporting rule both have to be findable from it.
# ---------------------------------------------------------------------------
print("\nthe plan:")
plan = PLAN.read_text(encoding="utf-8")
check("plan-10 names the reconcile step", "reconcile_raters.py" in plan)
check("...and the committed rubric", "hard-referee.txt" in plan)
check("...and states the demotion case #173 asked for",
      "#173" in plan and "held-with-split" in plan.lower())

print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
