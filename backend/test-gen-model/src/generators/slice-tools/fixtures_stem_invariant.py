"""Plan 07 §3c §4 fixtures. These MUST be red before verify_bank.py allows `question`.

§3c is a LEVER B pass: it edits the STEM (and the explanation that moves with it) and
must not touch `options` at all. verify_bank.py currently HARD-REFUSES `--allow-fields
question` -- lever B needed the widening and lever B was dropped, so it was never built.

The widening is only worth anything if it stays narrow at its load-bearing point. §13:
"a widened invariant must not widen at its load-bearing point". So these fixtures pin
BOTH directions:

  1. a stem edit FAILS the default invariant           (the widening is not a no-op)
  2. a stem edit PASSES --allow-fields question,explanation
  3. a KEY edit FAILS the default invariant
  4. a KEY edit FAILS --allow-fields question,explanation   <- THE ONE THAT MATTERS
  5. --allow-fields question is ACCEPTED by argparse (a REFUSAL, not a parse error,
     is what it emits today -- checked non-vacuously)
  6. a DISTRACTOR edit FAILS --allow-fields question,explanation -- allowing the stem
     must not smuggle `options` in with it (§3c's scope is disjoint from lever A's)
  7. the stem pass reports `question` as the touched field, not a silent no-op

Non-vacuity is the point of this file. §3b's mutual-exclusion fixture went green on
argparse's "unrecognized arguments" -- passing while testing nothing, the 5th time a
fixture was wrong before the gate was. So every case here asserts the REASON, not just
the exit code: a FAIL must name the right defect, and a PASS must show the right field
moved.

The module is imported and its globals are monkeypatched onto a throwaway git repo. It
is NOT copied into a scratchpad: §3b lost a session to a stale copy whose
`BASE_DIR = parents[2]` computed a bogus bank dir and made every file read "DIFFERS".
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
import verify_bank  # noqa: E402

PY = sys.executable
SCRIPT = str(GEN / "verify_bank.py")

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def item(qid="law-fx-0001"):
    return {
        "id": qid,
        "question": "Devlin agrees to buy a truck. Which element is required?",
        "options": {
            "A": "An offer that has been formally notarized by a public official",
            "B": "Consideration",
            "C": "A written record signed by both of the parties to the deal",
            "D": "Delivery of the goods",
        },
        "answer": "B",
        "explanation": "Consideration is the bargained-for exchange.",
        "performanceIndicator": "Describe the nature of legally binding contracts",
        "instructionalArea": "Business Law",
        "cluster": "finance",
        "level": "association",
        "difficulty": "medium",
    }


def run_invariant(bank_file, mutate, allow):
    """Commit the pristine item, apply `mutate`, run check_invariant vs that commit.

    Returns (fail_count, touched_report_text).
    """
    original = [item()]
    bank_file.write_text(json.dumps(original, indent=2), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=bank_file.parents[2], capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=bank_file.parents[2],
                   capture_output=True)

    mutated = [item()]
    mutate(mutated[0])
    bank_file.write_text(json.dumps(mutated, indent=2), encoding="utf-8")

    verify_bank.ok_count = 0
    verify_bank.fail_count = 0
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        verify_bank.check_invariant("HEAD", frozenset(allow))
    return verify_bank.fail_count, buf.getvalue()


# ---- mutations -----------------------------------------------------------
def edit_stem(q):
    # De-trigger the fact pattern: a services agreement, no goods sale. The key,
    # the options and the answer letter are untouched -- this is lever B's whole shape.
    q["question"] = "Devlin agrees to hire a consultant. Which element is required?"
    q["explanation"] = "Consideration is the bargained-for exchange in the services deal."


def edit_key(q):
    q["options"]["B"] = "Consideration, the bargained-for exchange between the parties"


def edit_distractor(q):
    q["options"]["A"] = "An offer that was notarized"


with tempfile.TemporaryDirectory() as td:
    repo = Path(td) / "repo"
    bank = repo / "frontend/public/question-bank"
    (bank / "finance").mkdir(parents=True)
    bank_file = bank / "finance" / "fin-law-fixture.json"

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fx@example.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "fixture"], cwd=repo, capture_output=True)

    # Point the module at the throwaway repo. The real layout is
    # REPO_ROOT/frontend/public/question-bank (bank_paths.py); mirror it exactly
    # so the relative paths _git_show builds are the ones the real run builds.
    verify_bank.BANK_DIR = bank
    verify_bank.REPO_ROOT = repo

    # ---- 1 & 7: a stem edit must FAIL the default invariant ---------------
    fails, report = run_invariant(bank_file, edit_stem, allow=[])
    check("1. stem edit FAILS the DEFAULT invariant (widening is not a no-op)",
          fails == 1 and "changed beyond" in report,
          f"fail_count={fails} :: {report.strip().splitlines()[-1] if report.strip() else 'no output'}")

    # ---- 2 & 7: ...and PASSES --allow-fields question,explanation ---------
    fails, report = run_invariant(bank_file, edit_stem, allow=["question", "explanation"])
    check("2. stem edit PASSES --allow-fields question,explanation",
          fails == 0,
          f"fail_count={fails} :: {report.strip().splitlines()[-1] if report.strip() else 'no output'}")
    # NON-VACUOUS: a pass is worthless if the invariant simply saw nothing move.
    # It must report `question` as touched -- proof it compared and allowed, rather
    # than never looking.
    check("7. ...and REPORTS `question` as touched (not a silent no-op)",
          "1 question" in report and "1 explanation" in report,
          f"report={report.strip().splitlines()[-1] if report.strip() else 'no output'}")

    # ---- 3: a key edit must FAIL the default -----------------------------
    fails, report = run_invariant(bank_file, edit_key, allow=[])
    check("3. KEY edit FAILS the DEFAULT invariant",
          fails == 1 and "changed beyond" in report,
          f"fail_count={fails} :: {report.strip().splitlines()[-1] if report.strip() else 'no output'}")

    # ---- 4: a key edit must FAIL the WIDENED invariant too ----------------
    # This is the load-bearing case. `options` is not in the allowlist, so the key
    # edit must be caught by the generic content check -- the stem widening must not
    # create a hole the key can walk through.
    fails, report = run_invariant(bank_file, edit_key, allow=["question", "explanation"])
    check("4. KEY edit FAILS --allow-fields question,explanation (THE LOAD-BEARING CASE)",
          fails == 1,
          f"fail_count={fails} :: {report.strip().splitlines()[-1] if report.strip() else 'no output'}")

    # ---- 6: a distractor edit must FAIL the widened invariant -------------
    fails, report = run_invariant(bank_file, edit_distractor, allow=["question", "explanation"])
    check("6. DISTRACTOR edit FAILS --allow-fields question,explanation "
          "(the stem pass must not smuggle in `options`)",
          fails == 1,
          f"fail_count={fails} :: {report.strip().splitlines()[-1] if report.strip() else 'no output'}")

# ---- 5: argparse must ACCEPT `question` ---------------------------------
# CLI-level, against the REAL script, because the refusal lives right after parse.
# NON-VACUOUS: today this exits with "refusing to widen the invariant over
# ['question']". Asserting only `returncode == 0` would be readable as a pass for the
# wrong reason once the bank checks start running, so assert the refusal is ABSENT by
# name and that the run actually reached the invariant stage.
r = subprocess.run([PY, SCRIPT, "--allow-fields", "question,explanation", "--no-invariant"],
                   capture_output=True, text=True, cwd=str(ROOT))
blob = (r.stdout or "") + (r.stderr or "")
check("5. --allow-fields question is ACCEPTED (no refusal), reaches the real checks",
      "refusing to widen" not in blob and "MANIFEST" in blob,
      f"returncode={r.returncode} :: {blob.strip().splitlines()[-1] if blob.strip() else 'no output'}")

print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
