"""Plan 07 §3b §1.3 fixtures. These MUST be red before --min-top-gap/--freeze-rank exist.

Six cases, all mechanical:
  1. a gap-breaching item with margin < 5 is SELECTED (margin cannot see it)
  2. a gap-breaching item with NEGATIVE margin (distractor-held) is SELECTED
  3. an item at exactly the cap (gap == 20) is NOT selected (the gate is >, not >=)
  4. --freeze-rank emits key_length_rank == observed_rank for every item,
     and the rank tally matches the pre-build observed tally
  5. --min-top-gap together with --min-margin exits NON-ZERO
  6. a clean case (gap <= cap) is not selected, and margin mode still works
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
from repair_options import observed_rank, top_gap, _margin  # noqa: E402

PY = sys.executable
SCRIPT = str(GEN / "repair_options.py")


def opt(n: int, tag: str) -> str:
    """An option whose stripped length is exactly n."""
    body = (tag * n)[:n]
    assert len(body.strip()) == n
    return body


def q(qid, answer, lengths, ia="Financial Analysis"):
    """lengths: {"A": n, ...}. Frozen fields present so validate() is happy."""
    return {
        "id": qid,
        "question": "Stem for " + qid + "?",
        "options": {k: opt(v, chr(ord("a") + i)) for i, (k, v) in enumerate(sorted(lengths.items()))},
        "answer": answer,
        "explanation": "Explanation for " + qid + ".",
        "performanceIndicator": "PI:001",
        "instructionalArea": ia,
        "cluster": "finance",
        "level": "icdc",
        "difficulty": "medium",
    }


# ---- the fixture bank ----------------------------------------------------
FIXTURES = [
    # 1. margin < 5 (in fact negative -- see the note in the report below), gap 50
    q("fx-margin-lt5", "A", {"A": 100, "B": 150, "C": 60, "D": 50}),
    # 2. distractor-held, rank 4, gap 30, margin -50
    q("fx-neg-margin", "A", {"A": 100, "B": 150, "C": 120, "D": 110}),
    # 3. exactly at the cap: L1=100 (key), L2=80 -> gap == 20 -> NOT selected
    q("fx-at-cap", "A", {"A": 100, "B": 80, "C": 70, "D": 60}),
    # 4. rank fodder: key-held gap 40 (rank 1), and a rank-3 gap 25
    q("fx-rank1", "A", {"A": 140, "B": 100, "C": 90, "D": 80}),
    q("fx-rank3", "A", {"A": 100, "B": 160, "C": 135, "D": 90}),
    # 6. clean: gap 5, nothing to do
    q("fx-clean", "A", {"A": 100, "B": 95, "C": 90, "D": 85}),
]

GAP_SELECTED = {"fx-margin-lt5", "fx-neg-margin", "fx-rank1", "fx-rank3"}
NOT_SELECTED = {"fx-at-cap", "fx-clean"}

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def run(args):
    return subprocess.run([PY, SCRIPT] + args, capture_output=True, text=True)


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    bank = td / "fixture-bank.json"
    bank.write_text(json.dumps(FIXTURES, indent=2), encoding="utf-8")

    # sanity: our fixture geometry is what we claim
    print("\n  fixture geometry (independent of the code under test):")
    for f in FIXTURES:
        gap, holder = top_gap(f["options"])
        rank, tied = observed_rank(f["options"], f["answer"])
        margin = _margin(f)[0]
        print(f"    {f['id']:<16} gap={gap:>3}  margin={margin:>4}  rank={rank}  holder={holder}  tied={tied}")

    # ---- fixtures 1, 2, 3, 6: the gap selector -------------------------
    out = td / "gap-payload.json"
    r = run([str(bank), "--build-payload", str(out), "--min-top-gap", "20", "--freeze-rank"])
    if r.returncode != 0 or not out.exists():
        detail = (r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else "no output"
        check("1. margin<5 gap-breacher is SELECTED", False, f"--min-top-gap did not run: {detail}")
        check("2. negative-margin item is SELECTED", False, "--min-top-gap did not run")
        check("3. gap==20 is NOT selected", False, "--min-top-gap did not run")
        check("4. --freeze-rank emits observed rank", False, "--min-top-gap did not run")
        check("6. clean case not selected + margin mode works", False, "--min-top-gap did not run")
    else:
        items = json.loads(out.read_text())
        ids = {i["id"] for i in items}

        check("1. margin<5 gap-breacher is SELECTED",
              "fx-margin-lt5" in ids, f"selected={sorted(ids)}")
        check("2. negative-margin item is SELECTED",
              "fx-neg-margin" in ids, f"selected={sorted(ids)}")
        check("3. gap==20 is NOT selected",
              "fx-at-cap" not in ids, f"selected={sorted(ids)}")

        # 4: every emitted rank equals the observed rank, and the tally matches
        by_id = {f["id"]: f for f in FIXTURES}
        bad = [i["id"] for i in items
               if i["key_length_rank"] != observed_rank(by_id[i["id"]]["options"], by_id[i["id"]]["answer"])[0]]
        want_tally = {}
        for i in items:
            r_ = observed_rank(by_id[i["id"]]["options"], by_id[i["id"]]["answer"])[0]
            want_tally[r_] = want_tally.get(r_, 0) + 1
        got_tally = {}
        for i in items:
            got_tally[i["key_length_rank"]] = got_tally.get(i["key_length_rank"], 0) + 1
        check("4. --freeze-rank emits observed rank (+ tally matches)",
              not bad and got_tally == want_tally,
              f"mismatched={bad} got_tally={got_tally} want_tally={want_tally}")

        # the selected set is exactly right, sorted worst-gap-first, margin emitted
        check("6a. selected set is exactly the gap-breachers",
              ids == GAP_SELECTED, f"got={sorted(ids)} want={sorted(GAP_SELECTED)}")
        gaps = [top_gap(by_id[i["id"]]["options"])[0] for i in items]
        check("6b. sorted worst-gap-first", gaps == sorted(gaps, reverse=True), f"gaps={gaps}")
        check("6c. `margin` still emitted (repair_distractors.txt reads it)",
              all("margin" in i for i in items))
        check("6d. cap + targets emitted on every item",
              all(i.get("max_top_gap") == 20 and len(i.get("distractor_targets", [])) == 3
                  for i in items))

    # ---- fixture 5: mutual exclusion -----------------------------------
    r = run([str(bank), "--build-payload", str(td / "x.json"),
             "--min-top-gap", "20", "--min-margin", "5"])
    # NON-VACUOUS: before the flag exists argparse exits 2 with "unrecognized
    # arguments", which would pass a bare returncode check for the WRONG reason.
    # The exit must be a mutual-exclusion refusal, not a parse failure.
    blob = (r.stderr or "") + (r.stdout or "")
    check("5. --min-top-gap + --min-margin exits non-zero (as a REFUSAL, not a parse error)",
          r.returncode != 0 and "unrecognized arguments" not in blob
          and "not allowed with" in blob,
          f"returncode={r.returncode} :: {blob.strip().splitlines()[-1] if blob.strip() else 'no output'}")

    # ---- margin mode still behaves (no regression) ---------------------
    out2 = td / "margin-payload.json"
    r = run([str(bank), "--build-payload", str(out2), "--min-margin", "5"])
    if r.returncode == 0 and out2.exists():
        mids = {i["id"] for i in json.loads(out2.read_text())}
        # fx-at-cap has margin 20; fx-rank1 margin 40. The negative-margin ones must be MISSED.
        check("7. margin mode MISSES the gap-breachers (this is the bug)",
              "fx-margin-lt5" not in mids and "fx-neg-margin" not in mids,
              f"margin-mode selected={sorted(mids)}")
    else:
        check("7. margin mode still works", False, (r.stderr or r.stdout).strip()[-200:])

print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
