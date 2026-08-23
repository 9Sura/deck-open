"""Issue #172 fixtures: the two blind solvers' DISAGREEMENT is an instrument, and it is read.

THE DEFECT. `build_hard_verify.py --blind` has always run two independent solvers, and the
entire value of the second one is that it can disagree with the first. Nothing read that.
The returns were prose in two agent replies, compared by whoever was orchestrating the
slice, and `output/plan-10/10-14/verify/` holds exactly two files -- the rater set and the
blind set. No solver return was ever an artifact, and no file on disk held the key the
blind set deliberately withholds, so the comparison could only be done by eye.

§10-14's `h0016` shipped a stem with TWO honest readings whose answers were BOTH offered:

    "reaches 40 rating points of the target audience with an average frequency of 5
     exposures, for a total campaign cost of $20,000"

    reading 1  "40 rating points" IS the GRP total  -> 20,000/40  = $500 = option A
    reading 2  40 is reach, GRP = 40 x 5 = 200      -> 20,000/200 = $100 = option B, the key

It passed check_authored (4 lists, no soft), check_batch_invariants, check_key_figures at
100% scope, audit_tells, the key-coherence audit at --profile full (class 1: 0, class 2: 0),
the arithmetic audit -- which explicitly checked cap/threshold rows for rival readings and
cleared this one -- and both difficulty raters, one recording "no readable tell". Solver 1
answered A. Solver 2 answered B. That was the whole detector, it was free, and a human
noticed it.

THE FIX IS TWO INSTRUMENTS THAT FAIL IN OPPOSITE DIRECTIONS, which is why both are here:

  the KEY SIDECAR + `reconcile_solvers.py`   mechanical, free, cannot be forgotten -- but
                                             silent when both solvers share a misreading
  the `readings` field in the blind header   legible from ONE solver, so it covers that --
                                             but it is a model self-report, which this repo
                                             has repeatedly found saturates

NON-VACUITY runs through the whole file. The §10-14 row is replayed with its REAL options,
key and explanation, in a DEFECT arm (the pre-fix stem, the two real solver answers) and a
CONTROL arm (the stem as committed, both solvers on the key) -- and the control must come
back empty, or the instrument is just flagging everything. Every refusal is shown FAILING
on a hand-broken input, so a regression that stops checking one fails here.

WHAT THIS FIXTURE DOES NOT CHECK -- stated, not implied:
  * That two solvers actually disagree on an ambiguous row. That is a model behaviour and
    no fixture can pin it. What is pinned is that a disagreement is READ when it happens.
  * That a class-A row IS ambiguous. Two solvers can differ because one is simply wrong;
    the adjudication is a human's, which is what --adjudicated records.
  * The blind solver PROMPTS beyond the header this tool writes. There is no committed
    solver prompt in the repo; the header IS the prompt, which is why the field-name
    contract below is checked against `reconcile_solvers.SOLVER_FIELDS` rather than trusted.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_solver_disagreement.py
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
import reconcile_solvers as rs  # noqa: E402

REPO = Path(__file__).resolve().parents[5]
PLAN = REPO / "backend/test-gen-model/plans/10-per-pi-review-depth-plan.md"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# §10-14 `h0016`, with its real options, key and explanation. Only the stem
# differs between the arms — which is exactly what the repair changed.
# ---------------------------------------------------------------------------
DEFECT_STEM = ("A local TV campaign reaches 40 rating points of the target audience with an "
               "average frequency of 5 exposures, for a total campaign cost of $20,000. "
               "What is the campaign's cost per rating point (CPP)?")
FIXED_STEM = DEFECT_STEM.replace("40 rating points of the target audience",
                                 "40% of the target audience")
H0016_OPTIONS = {
    "A": "A $500 cost per rating point for the local TV campaign, reported for the media buy",
    "B": "A $100 cost per rating point for the local TV campaign this quarter",
    "C": "A $10,000 cost per rating point for the local TV campaign this quarter",
    "D": "A $4,000 cost per rating point for the local TV campaign this coming quarter",
}
CID = "mkt-district-pool-cand-h0016"
FILLER = ["mkt-district-pool-cand-h0002", "mkt-district-pool-cand-h0007"]


def item(cid, stem, options=None, answer="B"):
    return {
        "cand_id": cid, "cluster": "marketing", "level": "District",
        "instructionalArea": "Promotion",
        "performanceIndicator": "Calculate cost per rating point (CPP) and GRPs",
        "question": stem,
        "options": options or {k: f"option {k}" for k in "ABCD"},
        "answer": answer, "explanation": "Reach times frequency is 200 GRPs; 20,000/200 = 100.",
        "difficulty": "hard",
    }


def payload_row(cid, answer="B"):
    return {"cand_id": cid, "answer_letter": answer, "route": "C2"}


def solver_row(cid, answer, readings=None, second="none", pickable=False, cue="",
               confidence="high"):
    return {"cand_id": cid, "answer": answer, "confidence": confidence,
            "readings": readings or [{"reading": "the only reading", "answer": answer}],
            "second_defensible": second, "pickable": pickable, "pickable_cue": cue}


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


DEFAULT_KEY = object()  # "use the default path", as distinct from "omit --key-out"


def build_stage2(tmp, rows, *, key_out=DEFAULT_KEY, out=None, extra=()):
    """Write payload + part, run stage 2, return (text, code, outdir, keypath).

    `key_out=None` OMITS the flag; leaving it unset uses a default path outside --out.
    """
    (tmp / "h1.json").write_text(json.dumps([payload_row(r["cand_id"]) for r in rows]),
                                 encoding="utf-8")
    (tmp / "h1-part1.json").write_text(json.dumps(rows), encoding="utf-8")
    outdir = out or (tmp / "verify")
    keypath = (tmp / "keys" / "blind-key.json") if key_out is DEFAULT_KEY else key_out
    argv = ["--payload", str(tmp / "h1.json"), "--part", str(tmp / "h1-part1.json"),
            "--out", str(outdir), "--blind", "--all", *extra]
    if keypath is not None:
        argv += ["--key-out", str(keypath)]
    text, code = run(bhv, *argv)
    return text, code, outdir, keypath


print("Issue #172 — solver disagreement is read, not noticed\n")

# ---------------------------------------------------------------------------
# 1. THE §10-14 CASE, replayed. The two real solver answers on the pre-fix stem.
# ---------------------------------------------------------------------------
print("the defect arm (§10-14 h0016, pre-fix stem, the real solver answers):")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    rows = [item(CID, DEFECT_STEM, H0016_OPTIONS)] + [item(c, "A routine stem.") for c in FILLER]
    text, code, outdir, keypath = build_stage2(tmp, rows)
    check("stage 2 builds and writes the key sidecar", code == 0 and keypath.exists(),
          text.strip().splitlines()[-1] if text else "")

    key = json.loads(keypath.read_text())
    check("the sidecar holds the key the blind set withholds",
          key["key"][CID] == "B" and key["ids"][0] == CID,
          "nothing on disk held this before — which is why the comparison was done by eye")
    blind = (outdir / "blind-set.txt").read_text()
    check("...and the blind set still does NOT hold it",
          "AUTHORED KEY" not in blind and "<==" not in blind
          and "Reach times frequency" not in blind,
          "NON-VACUITY for the leak guard below: blinding is unchanged by this fix")

    # Solver 1 answered A ($500); solver 2 answered B ($100), the key.
    s1 = [solver_row(CID, "A", confidence="medium",
                     readings=[{"reading": "'40 rating points' is already the GRP total, so "
                                           "frequency is extraneous", "answer": "A"}])] \
        + [solver_row(c, "B") for c in FILLER]
    s2 = [solver_row(CID, "B")] + [solver_row(c, "B") for c in FILLER]
    (tmp / "s1.json").write_text(json.dumps(s1), encoding="utf-8")
    (tmp / "s2.json").write_text(json.dumps(s2), encoding="utf-8")

    out, rcode = run(rs, "--key", str(keypath), "--solver", str(tmp / "s1.json"),
                     str(tmp / "s2.json"))
    check("CLASS A fires on the row §10-14 found by eye",
          "CLASS A — THE SOLVERS DISAGREE  (1)" in out and CID in out,
          next((ln.strip() for ln in out.splitlines() if CID in ln), "<no line>"))
    check("...and it EXITS 1 rather than printing into a scrollback",
          rcode == 1 and "ADJUDICATION REQUIRED" in out,
          "the signal was always free; what was missing is being obliged to look at it")
    check("class B is clear — the key really is B",
          "CLASS B — THE SOLVERS AGREE, AND THE KEY DIFFERS  (0)" in out,
          "a merged count would have read this as a wrong key (#154's rule)")
    check("the three classes are counted SEPARATELY and all print at zero",
          out.count("CLASS A") == 1 and out.count("CLASS B") == 1 and out.count("CLASS C") == 1,
          "a class with no header reads as a class that was not run")

    # The other half: solver 1 alone, having written both readings down.
    s1_readings = [solver_row(CID, "B", readings=[
        {"reading": "'40 rating points' is the GRP total; frequency is extraneous",
         "answer": "A"},
        {"reading": "40 is reach; GRP = 40 x 5 = 200", "answer": "B"},
        {"reading": "the $20,000 is per exposure", "answer": "none"}])] \
        + [solver_row(c, "B") for c in FILLER]
    (tmp / "s1r.json").write_text(json.dumps(s1_readings), encoding="utf-8")
    out2, rcode2 = run(rs, "--key", str(keypath), "--solver", str(tmp / "s1r.json"),
                       str(tmp / "s2.json"))
    check("CLASS C fires on a row BOTH solvers agreed about",
          "CLASS C" in out2 and "(1)" in out2.split("CLASS C")[1][:60] and CID in
          out2.split("CLASS C")[1],
          "this is the half that covers class A's blind spot — a SHARED misreading")
    check("...and class A is empty there, so C is not a restatement of A",
          "CLASS A — THE SOLVERS DISAGREE  (0)" in out2)
    check("a reading landing on NO offered option does not count toward class C",
          out2.split("CLASS C")[1].count(" A / B") == 1,
          "'this reading produces a number nobody offered' is evidence the item is sound")
    check("class C alone does NOT exit 1", rcode2 == 0,
          "the self-report arm is noisy by construction; read the rows, not the count")

# ---------------------------------------------------------------------------
# 2. THE CONTROL ARM. Same rows, repaired stem, both solvers on the key.
# ---------------------------------------------------------------------------
print("\nthe control arm (the stem as committed):")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    rows = [item(CID, FIXED_STEM, H0016_OPTIONS)] + [item(c, "A routine stem.") for c in FILLER]
    _, code, outdir, keypath = build_stage2(tmp, rows)
    both = [solver_row(r["cand_id"], "B") for r in rows]
    (tmp / "s1.json").write_text(json.dumps(both), encoding="utf-8")
    (tmp / "s2.json").write_text(json.dumps(both), encoding="utf-8")
    out, rcode = run(rs, "--key", str(keypath), "--solver", str(tmp / "s1.json"),
                     str(tmp / "s2.json"))
    check("every class is EMPTY and the run exits 0",
          rcode == 0 and "CLASS A — THE SOLVERS DISAGREE  (0)" in out
          and "THE KEY DIFFERS  (0)" in out and "TWO OFFERED LETTERS  (0)" in out,
          "an instrument that fires on the repaired row too is measuring nothing")
    check("...and the agreement tally is reported", "agreed with the key: 3" in out)

# ---------------------------------------------------------------------------
# 3. THE LEAK GUARD. blind_check reads the blind set's BYTES and cannot see a
#    second file, so the sidecar's separation is enforced by PATH.
# ---------------------------------------------------------------------------
print("\nthe key sidecar may not sit where the solver is sent:")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    rows = [item(CID, DEFECT_STEM, H0016_OPTIONS)]
    text, code, outdir, _ = build_stage2(tmp, rows, key_out=tmp / "verify" / "blind-key.json")
    check("--key-out INSIDE --out is refused",
          code == 1 and "is inside --out" in text,
          "a solver agent that lists its working directory would read the key")
    text, code, _, _ = build_stage2(tmp, rows,
                                    key_out=tmp / "verify" / "sub" / "k.json")
    check("...and so is a path NESTED under --out", code == 1 and "is inside --out" in text)
    text, code, _, _ = build_stage2(tmp, rows, key_out=None)
    check("--key-out is REQUIRED with --blind, not optional",
          code == 1 and "--key-out is REQUIRED" in text,
          "#156's lesson: a number left optional rides forward; a file left optional is "
          "never written")

# ---------------------------------------------------------------------------
# 4. THE SIDECAR IS A MAP, so a repeated cand_id would silently keep one answer.
# ---------------------------------------------------------------------------
print("\nduplicate rows in the scoped set:")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    dupe = [item(CID, DEFECT_STEM, H0016_OPTIONS), item(CID, FIXED_STEM, H0016_OPTIONS)]
    text, code, _, _ = build_stage2(tmp, dupe)
    check("a repeated cand_id is refused, not resolved",
          code == 1 and "appear more than once" in text,
          "two rows, one key entry — one solver scored against the other row's answer")
    # STAGE 1 REFUSES IT TOO, SINCE #173. When this fixture was written the guard was the
    # key sidecar's alone -- stage 1 wrote one file, held no per-id map and had nothing to
    # lose to a repeat, so the assertion here was that it stayed untouched. #173 gave stage
    # 1 its own sidecar and a reconcile that keys each rater's return by cand_id, so a
    # repeat now scores one rating against another row. The premise changed; the assertion
    # follows it rather than pinning a property that stopped being true.
    (tmp / "h1.json").write_text(json.dumps([payload_row(CID)]), encoding="utf-8")
    (tmp / "h1-part1.json").write_text(json.dumps(dupe), encoding="utf-8")
    s1text, s1code = run(bhv, "--payload", str(tmp / "h1.json"), "--part",
                         str(tmp / "h1-part1.json"), "--out", str(tmp / "v1"))
    check("...and STAGE 1 refuses it too, since #173 gave it a sidecar",
          s1code == 1 and "appear more than once" in s1text,
          "reconcile_raters.py keys a rater's return by cand_id")

# ---------------------------------------------------------------------------
# 5. THE PROMPT AND THE PARSER ARE ONE CONTRACT (#139's rule, one level up).
# ---------------------------------------------------------------------------
print("\nthe header and the parser, checked against each other:")
head = bhv.blind_head(3, "marketing", "District")
check("the builder reads the PARSER's field list, not a copy of it",
      bhv.SOLVER_FIELDS is rs.SOLVER_FIELDS,
      "#76's GATED_FIELDS: a hand-written second list drifts, in both directions")
check("every field reconcile_solvers requires is named in the header",
      all(f'"{f}"' in head for f in rs.SOLVER_FIELDS),
      ", ".join(rs.SOLVER_FIELDS))
check("the header asks about the STEM's readings, not just a second option",
      "readings" in head and "ABOUT THE STEM, NOT THE OPTIONS" in head,
      "the old header asked whether a SECOND OPTION was defensible — a question a solver "
      "committed to one reading answers 'no' to, honestly")
check("...and `second_defensible` is KEPT, not replaced",
      "second_defensible" in head and "older, different question" in head,
      "two options defensible under ONE reading is a different defect with its own yield")
check("the header carries the §10-14 case as its reason",
      "h0016" in head and "$500" in head and "$100" in head,
      "a requirement with no reason attached is the first thing an agent drops")
check("the header tells the solver its disagreement is the instrument",
      "INDEPENDENT" in head and "disagreement" in head)

saved = bhv.SOLVER_FIELDS
try:
    bhv.SOLVER_FIELDS = saved + ("a_field_no_prose_names",)
    broke = False
    try:
        bhv.blind_head(3, "marketing", "District")
    except SystemExit as e:
        broke = "a_field_no_prose_names" in str(e.code)
    check("a parser field the prose does not name STOPS THE BUILD", broke,
          "NON-VACUITY: the contract check can fail, so it is not decorative")
finally:
    bhv.SOLVER_FIELDS = saved

# ---------------------------------------------------------------------------
# 6. THE RETURN IS REFUSED, NEVER READ LENIENTLY. A return that has drifted
#    would be compared row-against-wrong-row — #155's failure, one tool over.
# ---------------------------------------------------------------------------
print("\nmalformed solver returns:")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    rows = [item(CID, DEFECT_STEM, H0016_OPTIONS)] + [item(c, "A stem.") for c in FILLER]
    _, _, _, keypath = build_stage2(tmp, rows)
    good = [solver_row(r["cand_id"], "B") for r in rows]

    def with_return(name, data, raw=None):
        p = tmp / name
        p.write_text(raw if raw is not None else json.dumps(data), encoding="utf-8")
        (tmp / "ok.json").write_text(json.dumps(good), encoding="utf-8")
        return run(rs, "--key", str(keypath), "--solver", str(p), str(tmp / "ok.json"))

    out, code = with_return("clean.json", good)
    check("a clean pair passes", code == 0, "NON-VACUITY for the refusals below")

    out, code = with_return("short.json", good[:2])
    check("a return missing rows is refused",
          code == 1 and "went unanswered" in out)

    out, code = with_return("extra.json", good + [solver_row("not-in-this-batch", "A")])
    check("a return naming a row outside the blind set is refused",
          code == 1 and "not in the blind set" in out,
          "the #155 shape: a finding that names a real, unrelated question")

    out, code = with_return("dupe.json", good + [solver_row(CID, "A")])
    check("a row returned twice is refused", code == 1 and "returned twice" in out)

    out, code = with_return("abstain.json",
                            [solver_row(CID, "unsure")] + good[1:])
    check("an answer that is not A-D is refused",
          code == 1 and "is not one of A-D" in out,
          "a blind solve that declines to answer is not a datum")

    out, code = with_return("noread.json",
                            [{**good[0], "readings": []}] + good[1:])
    check("an empty `readings` list is refused",
          code == 1 and "non-empty list" in out,
          "one entry is the common, healthy answer — zero is a field that was skipped")

    out, code = with_return("prose.json", None, raw="Here are my answers:\n[{}]")
    check("a return wrapped in prose is refused, not salvaged",
          code == 1 and "not valid JSON" in out)

    out, code = run(rs, "--key", str(keypath), "--solver", str(tmp / "clean.json"))
    check("ONE solver is refused", code == 1 and "TWO OR MORE" in out,
          "independence is the instrument; one return has nothing to disagree with")

# ---------------------------------------------------------------------------
# 7. --adjudicated CARRIES A REASON. The build_repair_prompt --scope-reason
#    shape: an override that takes a bare flag records that somebody silenced a
#    finding and nothing about why (#127 had to reconstruct 33-vs-124 by hand).
# ---------------------------------------------------------------------------
print("\nadjudication:")
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    rows = [item(CID, DEFECT_STEM, H0016_OPTIONS)] + [item(c, "A stem.") for c in FILLER]
    _, _, _, keypath = build_stage2(tmp, rows)
    (tmp / "s1.json").write_text(json.dumps(
        [solver_row(CID, "A")] + [solver_row(c, "B") for c in FILLER]), encoding="utf-8")
    (tmp / "s2.json").write_text(json.dumps(
        [solver_row(r["cand_id"], "B") for r in rows]), encoding="utf-8")
    base = ["--key", str(keypath), "--solver", str(tmp / "s1.json"), str(tmp / "s2.json")]

    out, code = run(rs, *base, "--adjudicated", CID)
    check("a bare id is refused — the reason IS the artifact",
          code == 1 and "has no reason" in out)

    out, code = run(rs, *base, "--adjudicated", f"{FILLER[0]}:looks fine to me")
    check("a reason attached to an unflagged row is refused",
          code == 1 and "no class-A or class-B finding" in out,
          "a record of nothing")

    reason = "stem repaired to '40% of the target audience'; the rival reading is gone"
    out, code = run(rs, *base, "--adjudicated", f"{CID}:{reason}")
    check("an adjudicated row clears the exit code", code == 0)
    check("...and is still PRINTED, with its reason",
          "[adjudicated]" in out and reason in out,
          "adjudicating a row settles it; it does not delete it from the record")

# ---------------------------------------------------------------------------
# 8. THE PLAN. The blind solvers have no committed prompt beyond the header this
#    tool writes, so plan-10 §4 step 6a is where the reconcile step has to live.
# ---------------------------------------------------------------------------
print("\nthe plan:")
plan = PLAN.read_text(encoding="utf-8")
check("plan-10 names the reconcile step", "reconcile_solvers.py" in plan)
check("...and says the disagreement is the signal, not the confidence",
      "#172" in plan and "disagree" in plan.lower())
check("...and says the sidecar goes outside the solver's directory",
      "--key-out" in plan and "outside" in plan)

print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
