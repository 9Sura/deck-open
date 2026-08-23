#!/usr/bin/env python3
"""Pin `build_repair_prompt.py --from-bank` — the committed-bank repair path (§10-17).

WHY THIS FILE EXISTS
--------------------
§10-17 is the only plan-10 work that EDITS committed rows, and `--from-bank` is the
prompt side of it. Everything it does is a guard from the in-flight path answering a
question a bank repair asks differently, so every one of them is a place the two paths
can silently diverge later. The repo's standing rule applies literally here: when a
tool's behaviour is asserted in a comment, assert it in a fixture too (#88).

Six properties, and the first is the one that protects everyone else:

  1. ADDITIVE. With no --from-bank, the in-flight derivation is BYTE-IDENTICAL to what
     it was before the mode existed. --payload/--gate went from `required=True` to
     validated-by-hand, which is exactly the kind of change that loosens a guard while
     looking like a refactor, so the refusals are asserted too.
  2. The modes are MUTUALLY EXCLUSIVE, refused rather than tolerated.
  3. The CENSUS substitutes for the gate on guard 1 (staleness) and guard 2 (every row
     is gate-named, so no --scope-reason).
  4. COPY THROUGH is DERIVED from the row minus verify_reword.MUTABLE. A field the
     prompt does not print is a field apply_repair deletes from the shipped bank, and
     `verified` is the live example.
  5. The §2 scope boundaries (set files, hard rows) are read off the census's own fields
     and refused without a reason.
  6. The RULE is sliced out of the committed brief and a missing marker RAISES; the READ
     PLAN describes the file it is inside, to the byte (#186).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE.parent
sys.path.insert(0, str(GEN))
import build_repair_prompt as brp                      # noqa: E402
from build_audit_input import READ_CAP_CHARS           # noqa: E402
from verify_reword import MUTABLE as REWORD_MUTABLE    # noqa: E402

PASS = FAIL = 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}")
    if detail:
        print(f"          {detail}")


def run(*args, cwd=None):
    """The tool, as a subprocess, so argparse-level refusals are exercised too."""
    return subprocess.run([sys.executable, str(GEN / "build_repair_prompt.py"), *args],
                          capture_output=True, text=True, cwd=cwd)


ROW = {
    "id": "hos-district-pool-0999",
    "cluster": "hospitality", "level": "District",
    "instructionalArea": "Operations",
    "performanceIndicator": "Calculate RevPAR from ADR and occupancy",
    "question": "A 100-room inn took $8,000 last night after selling 50 rooms. What was RevPAR?",
    "options": {"A": "About $160, from dividing revenue by the rooms sold",
                "B": "About $80, from dividing revenue by the rooms available",
                "C": "About $40, from halving the correct ADR value",
                "D": "About $200, from a lower occupancy figure"},
    "answer": "B",
    "explanation": "RevPAR is revenue over rooms available: 8,000 / 100 = $80. "
                   "Option A divides by rooms sold. Option C halves the ADR. "
                   "Option D uses a lower occupancy.",
    "difficulty": "medium",
    # NOT an identity field and NOT mutable — the field that made the derived
    # copy-through necessary. apply_repair replaces the row with the overlay object.
    "verified": True,
}


def bank_case(tmp, rows, census_extra=None, n=16):
    """A one-file bank plus its census, with the census written LAST so guard 1 passes."""
    bank = tmp / "hospitality-district-pool.json"
    # POOL_FLOOR rows, all clones of ROW with distinct ids, so guard 3 is not the thing
    # under test in cases that are about something else.
    items = []
    for i in range(n):
        r = json.loads(json.dumps(ROW))
        r["id"] = "hos-district-pool-%04d" % (900 + i)
        items.append(r)
    for r in rows:
        items.append(r)
    bank.write_text(json.dumps(items, indent=2), encoding="utf-8")
    census = [{"file": str(bank), "id": r["id"],
               "tells": ["option B narrates its own derivation (', from')"],
               "difficulty": r.get("difficulty"), "in_set": False,
               "key_tells": True, "eliminable": False} for r in items]
    for extra in census_extra or []:
        for c in census:
            if c["id"] == extra["id"]:
                c.update(extra)
    cpath = tmp / "workorder.json"
    cpath.write_text(json.dumps(census, indent=2), encoding="utf-8")
    return bank, cpath


print("\n--from-bank — the committed-bank repair path (§10-17)\n")

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    bank, census = bank_case(tmp, [])
    out = tmp / "r.prompt.txt"

    # ---- 2. mode exclusion -------------------------------------------------------
    r = run("--from-bank", str(census), "--payload", str(census), "--part", str(bank),
            "--out", str(out), "--overlay", str(tmp / "o.json"))
    check("--from-bank refuses --payload rather than ignoring it",
          r.returncode != 0 and "--payload" in r.stdout + r.stderr,
          "an empty or borrowed gate report is the input guard 1 exists to refuse")
    r = run("--from-bank", str(census), "--gate", str(census), "--part", str(bank),
            "--out", str(out), "--overlay", str(tmp / "o.json"))
    check("--from-bank refuses --gate too", r.returncode != 0)

    # The in-flight path must still REQUIRE both — the loosening is the hazard.
    r = run("--part", str(bank), "--out", str(out), "--overlay", str(tmp / "o.json"))
    check("without --from-bank, --payload is still required",
          r.returncode != 0 and "--payload is required" in r.stdout + r.stderr,
          "they moved from argparse's required=True to a hand check; it must still bite")

    # ---- overlay arity -----------------------------------------------------------
    r = run("--from-bank", str(census), "--part", str(bank), "--out", str(out),
            "--overlay", str(tmp / "a.json"), str(tmp / "b.json"))
    check("--from-bank refuses more --overlay paths than --part files",
          r.returncode != 0 and "ONE overlay per bank file" in (r.stdout + r.stderr),
          "--expect is scoped per file; a pooled overlay disarms the wrong-pool guard")

    # ---- 3a. the census IS the gate: no --scope-reason ---------------------------
    r = run("--from-bank", str(census), "--part", str(bank), "--out", str(out),
            "--overlay", str(tmp / "o.json"))
    ok = r.returncode == 0 and "16 from the census" in r.stdout
    check("every census row is gate-named — no --scope-reason is demanded", ok,
          "if all of them fell to the reason path the scope record would mean nothing")

    rec = json.loads((out.with_suffix(".scope.json")).read_text())
    check("the scope record names the mode and keeps the census in the `gate` slot",
          rec["mode"] == "from-bank" and rec["gate"] == str(census)
          and rec["rows"]["gate_flagged"] == 16 and rec["rows"]["widened"] == [])

    # ---- 4. copy-through is DERIVED ---------------------------------------------
    text = out.read_text()
    check("`verified` is in COPY THROUGH — the merge would otherwise DELETE it",
          '"verified": true' in text,
          "apply_repair replaces the row with the overlay object")
    # Scoped to the COPY THROUGH blocks alone. The header's worked example of an overlay
    # object legitimately shows `"options"` and `"explanation"` — that is the OUTPUT
    # shape, not a field to copy — so a whole-file search would fail on the example and
    # say nothing about the derivation.
    copy_blocks = "".join(
        chunk.split("\n\n")[0] for chunk in text.split("COPY THROUGH")[1:])
    for f in REWORD_MUTABLE:
        check(f"{f!r} is NOT copied through (it is the field being repaired)",
              f'"{f}":' not in copy_blocks)
    check("the copy-through set is verify_reword.MUTABLE's complement, imported",
          brp.REWORD_MUTABLE is REWORD_MUTABLE,
          "two hand-written copies of that set is #76's GATED_FIELDS drift")

    # ---- no assignment is invented ----------------------------------------------
    check("no ASSIGNED line is rendered — there is no payload to assign anything",
          "ASSIGNED:" not in text and "KEY LENGTH RANK" not in text
          and "LONGEST=" not in text,
          "§10-10: a prompt stating a length instruction nothing measures cost 3 slices")
    check("the census's own per-row facts are rendered instead",
          "CENSUS: difficulty=medium" in text and "tell on the KEY: YES" in text)

    # ---- 3b. staleness: the bank file newer than the census ----------------------
    bank.write_text(bank.read_text(), encoding="utf-8")   # touch, after the census
    r = run("--from-bank", str(census), "--part", str(bank), "--out", str(out),
            "--overlay", str(tmp / "o.json"))
    check("a bank file newer than the census is refused (guard 1's substitute)",
          r.returncode != 0 and "OLDER than the parts" in (r.stdout + r.stderr))
    r = run("--from-bank", str(census), "--part", str(bank), "--out", str(out),
            "--overlay", str(tmp / "o.json"),
            "--stale-gate-reason", "a fixture touched the file")
    check("...and it takes a REASON, never a bare flag", r.returncode == 0)

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    # ---- 5. the §2 scope boundaries ----------------------------------------------
    hard = json.loads(json.dumps(ROW))
    hard["id"], hard["difficulty"] = "hos-district-pool-0998", "hard"
    bank, census = bank_case(tmp, [hard], census_extra=[
        {"id": "hos-district-pool-0998", "difficulty": "hard"},
        {"id": "hos-district-pool-0901", "in_set": True}])
    out = tmp / "r.prompt.txt"
    r = run("--from-bank", str(census), "--part", str(bank), "--out", str(out),
            "--overlay", str(tmp / "o.json"))
    both = "hos-district-pool-0998" in (r.stdout + r.stderr) \
        and "hos-district-pool-0901" in (r.stdout + r.stderr)
    check("a hard row and a set-file row are both refused, by name",
          r.returncode != 0 and both,
          "the census records `difficulty` and `in_set` because they are §2's boundaries")
    r = run("--from-bank", str(census), "--part", str(bank), "--out", str(out),
            "--overlay", str(tmp / "o.json"),
            "--allow-out-of-scope", "a fixture, deliberately")
    check("...and the waiver takes a REASON, recorded in the scope record",
          r.returncode == 0
          and json.loads(out.with_suffix(".scope.json").read_text())
          ["guards"]["allow_out_of_scope"] == "a fixture, deliberately")
    r = run("--payload", str(census), "--gate", str(census), "--part", str(bank),
            "--out", str(out), "--overlay", str(tmp / "o.json"),
            "--allow-out-of-scope", "x")
    check("--allow-out-of-scope is refused on the in-flight path",
          r.returncode != 0, "only a census carries in_set/difficulty as scope fields")

# ---- 6. the rule comes out of the committed brief, and a missing marker RAISES ----
rule = brp.bank_rule_block()
check("the rule block is sliced from authoring-hard-bare.txt, not restated",
      "ALL FOUR OPTIONS ON A ROW DESCRIBE THE SAME QUANTITY" in rule
      and "KEEPS ITS NUMBER AND LOSES ITS LABEL" in rule
      and brp.BANK_RULE_BRIEF.exists(),
      f"{len(rule)} chars from {brp.BANK_RULE_BRIEF.name}")
check("the slice stops before the brief's LONGEST= block",
      "LONGEST=Y" not in rule,
      "a bank row carries no length assignment; quoting one would state an "
      "instruction nothing measures")
with tempfile.TemporaryDirectory() as td:
    empty = Path(td) / "brief.txt"
    empty.write_text("nothing here", encoding="utf-8")
    try:
        brp.bank_rule_block(empty)
        raised = False
    except SystemExit:
        raised = True
check("a brief that no longer carries the rule RAISES rather than emitting nothing",
      raised,
      "a rule quoted from a file that stopped containing it reads as sourced")

# ---- 6b. the read plan describes the file it is inside, to the byte ---------------
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    big = json.loads(json.dumps(ROW))
    # Rows fat enough to push the prompt past one Read, so the pager is exercised.
    big["explanation"] = ROW["explanation"] + " " + ("padding. " * 400)
    rows = []
    for i in range(40):
        r2 = json.loads(json.dumps(big))
        r2["id"] = "hos-district-pool-%04d" % (700 + i)
        rows.append(r2)
    bank, census = bank_case(tmp, rows, n=0)
    out = tmp / "r.prompt.txt"
    r = run("--from-bank", str(census), "--part", str(bank), "--out", str(out),
            "--overlay", str(tmp / "o.json"))
    text = out.read_text()
    rec = json.loads(out.with_suffix(".scope.json").read_text())
    check("a prompt over the single-read cap says so, and says it in the terminal",
          len(text) > READ_CAP_CHARS and "OVER THE SINGLE-READ CAP" in r.stdout,
          f"{len(text):,} chars against a {READ_CAP_CHARS:,}-char cap")
    check("the read plan's char and line counts describe the written bytes exactly",
          f"{len(text):,} characters" in text
          and f"{text.count(chr(10)):,} lines" in text
          and rec["prompt_chars"] == len(text),
          "self-referential, so it is solved to a fixed point (#186)")
    offs = rec["read_offsets"]
    check("its offsets page the file to the end",
          offs[0] == 1 and offs[-1] <= text.count("\n")
          and (len(offs) == 1 or offs[-1] + (offs[1] - offs[0]) > text.count("\n")),
          f"{len(offs)} Read call(s): {offs}")
    check("the requirement names the row count to reconcile against",
          f"It MUST equal n_rows ({len(rec['ids'])})" in text)

print(f"\n  {PASS} passed / {FAIL} failed\n")
sys.exit(1 if FAIL else 0)
