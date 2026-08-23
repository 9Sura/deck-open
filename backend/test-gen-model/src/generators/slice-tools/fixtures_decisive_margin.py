"""Issue #93 fixtures: the decisive length margin, per chunk.

The length tell is the bank's oldest measured defect, and plan 05 named TWO quantities
for it that `check_authored.py` had collapsed into one:

  * the KEY-IS-LONGEST RATE -- what share of a batch has the key at rank 1. Bar: 35%.
  * the DECISIVE MARGIN -- the key standing >=20ch clear of EVERY distractor. Plan 05
    §5a calls this the work list, and it is what "conspicuously longest" means.

The gate reported the first and computed the second only to sort an optional list whose
budget came from the rate: `longest - target_rate * n`. So a chunk already under the bar
budgeted ZERO and printed nothing, however far an individual key towered. Measured on
§10-11 before the fix: chunk 3 (24.7%, budget 0) carried a +29ch row and chunk 7 (24.7%,
budget 0) carried +29 and +28, while chunk 2 budgeted 1 against 9 decisive rows. All of
them only ever surfaced in `audit_tells.py`, which runs bank-wide AFTER assembly, by
which point `verify_bank`'s frozen-`answer` invariant makes the fix a reword plan.

So this file pins the rule that replaced it, in both halves, because either half alone
was already true before the fix:

  * the REPORT -- the decisive count is printed on every `--list-key-longest`-less run
    too, as a rate over the batch, next to the rate it qualifies.
  * the SCOPE -- `key_longest_scope` unions the rate budget with the margin floor, so a
    budget-0 chunk still hands back its outliers.

NON-VACUITY: the selector cases assert WHICH ids come back and in what ORDER, not just
how many -- a union that returned the right count from the wrong selector would read as
a pass. The end-to-end case asserts against a payload whose expected numbers were read
off the real §10-11 chunk 7 parts, so a change to the printed line is caught too.

WHAT THIS DOES NOT CHECK: whether 20ch is the right threshold (it is plan 05 §5a's, and
it is calibrated in `audit_tells.py`, not here), and whether a flagged row is ACTUALLY a
tell -- [[length-tell-tolerance]] is explicit that over-scrubbing is its own defect, so
the list is a work order for a human, never an automatic rewrite.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_decisive_margin.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
from check_authored import DECISIVE_MARGIN, key_longest_scope  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def offender(margin: int, cid: str) -> tuple:
    """One row of the gate's `offenders` list: (margin, cand_id, answer, key, runner)."""
    return (margin, cid, "A", 60 + margin, 60)


def ids(scoped) -> list:
    return [o[1] for o in scoped]


# ---------------------------------------------------------------------------
# 1. THE THRESHOLD IS NAMED ONCE.
# ---------------------------------------------------------------------------
check("DECISIVE_MARGIN is plan 05 §5a's 20ch",
      DECISIVE_MARGIN == 20, f"DECISIVE_MARGIN={DECISIVE_MARGIN}")

# ---------------------------------------------------------------------------
# 2. THE RATE-ONLY PATH IS UNCHANGED -- min_margin None must reproduce the old
#    behaviour exactly, or this fix silently widened every slice already scripted.
# ---------------------------------------------------------------------------
over_bar = [offender(m, f"c{i}") for i, m in enumerate([35, 29, 12, 8, 3, 2])]
scoped, budget = key_longest_scope(over_bar, longest=6, batch_size=12,
                                   target_rate=0.25, min_margin=None)
check("rate-only: budget is longest - target*n",
      budget == 3, f"budget={budget}")
check("rate-only: hands back exactly the budget, worst margin first",
      ids(scoped) == ["c0", "c1", "c2"], f"{ids(scoped)}")

# ---------------------------------------------------------------------------
# 3. THE DEFECT ITSELF -- a chunk UNDER the bar budgets 0 and must still hand back
#    its decisive rows. This is §10-11 chunk 7: 23/93 key-longest, budget 0, two rows
#    at +29 and +28 that no per-chunk instrument named.
# ---------------------------------------------------------------------------
under_bar = [offender(29, "m0068"), offender(28, "m0065")] + \
            [offender(4, f"n{i}") for i in range(21)]
scoped, budget = key_longest_scope(under_bar, longest=23, batch_size=93,
                                   target_rate=0.25, min_margin=None)
check("under the bar: the rate budget is 0 (the issue #93 defect)",
      budget == 0 and scoped == [], f"budget={budget} scoped={ids(scoped)}")

scoped, budget = key_longest_scope(under_bar, longest=23, batch_size=93,
                                   target_rate=0.25, min_margin=DECISIVE_MARGIN)
check("under the bar + floor: budget still 0, but both decisive rows come back",
      budget == 0 and ids(scoped) == ["m0068", "m0065"],
      f"budget={budget} scoped={ids(scoped)}")

# ---------------------------------------------------------------------------
# 4. THE UNION IS A UNION -- a row in BOTH selectors appears ONCE, and a row in
#    only the rate budget is not dropped by the floor. A floor that REPLACED the
#    rate scope would pass a count-only assertion here and fail this one.
# ---------------------------------------------------------------------------
mixed = [offender(35, "a"), offender(22, "b"), offender(12, "c"),
         offender(9, "d"), offender(5, "e"), offender(2, "f")]
scoped, budget = key_longest_scope(mixed, longest=6, batch_size=12,
                                   target_rate=0.25, min_margin=DECISIVE_MARGIN)
check("union: rate rows (a,b,c) plus floor rows (a,b) = a,b,c -- no duplicate 'a'",
      ids(scoped) == ["a", "b", "c"], f"budget={budget} scoped={ids(scoped)}")
check("union: every id is distinct",
      len(ids(scoped)) == len(set(ids(scoped))), f"{ids(scoped)}")

# A floor BELOW the rate rows must widen the scope, not narrow it.
scoped, _ = key_longest_scope(mixed, longest=6, batch_size=12,
                              target_rate=0.25, min_margin=5)
check("union: a lower floor widens the scope and keeps worst-margin order",
      ids(scoped) == ["a", "b", "c", "d", "e"], f"{ids(scoped)}")

# ---------------------------------------------------------------------------
# 5. ORDER SURVIVES THE DEDUP. The dict pass could reorder; the list is a work
#    order read top-down, so worst-first is load-bearing, and equal margins must not
#    raise -- the pre-fix `sorted(offenders, reverse=True)` fell through to comparing
#    cand_ids on a tie, which is a TypeError the moment one of them is None.
# ---------------------------------------------------------------------------
ties = [offender(20, "z"), offender(20, "y"), offender(30, "x")]
scoped, _ = key_longest_scope(ties, longest=3, batch_size=4,
                              target_rate=0.25, min_margin=DECISIVE_MARGIN)
check("ties on margin sort without comparing cand_ids, worst first",
      ids(scoped)[0] == "x" and set(ids(scoped)) == {"x", "y", "z"}, f"{ids(scoped)}")

# ---------------------------------------------------------------------------
# 6. THE BOUNDARY IS INCLUSIVE. 20 is decisive; 19 is the soft band.
# ---------------------------------------------------------------------------
edge = [offender(20, "at"), offender(19, "below")]
scoped, _ = key_longest_scope(edge, longest=2, batch_size=100,
                              target_rate=0.25, min_margin=DECISIVE_MARGIN)
check("floor is >=, so exactly 20ch is in scope and 19ch is not",
      ids(scoped) == ["at"], f"{ids(scoped)}")

# ---------------------------------------------------------------------------
# 7. END TO END -- the CLI, on a SYNTHETIC batch built here.
#
#    Shaped as §10-11 chunk 7 was: 2 of 8 rows key-longest, so `0.25 * 8 == 2` and
#    the rate budget is 0, while one of the two stands +29ch clear. That is the exact
#    configuration that shipped a decisive row silently.
#
#    It is synthetic on purpose. Pointing at a slice's committed parts would make
#    this fixture depend on output/ that a branch may not carry, and those rows
#    hard-fail on their own committed twins post-assembly anyway (see the gate's
#    module docstring), which empties `ok_items` and skips the whole block.
# ---------------------------------------------------------------------------
STEM = ("A regional supplier reviews its {} process before the next quarter begins "
        "and asks which step the manager should take first.")
EXPL = ("The keyed option is the step that addresses the process named in the stem, "
        "which is what the performance indicator asks for. The other three describe "
        "activities that happen elsewhere in the business and do not resolve the "
        "situation the manager is facing at this point in the {} cycle.")


def row(i: int, key_len: int, runner_len: int) -> tuple:
    """A payload spec + its authored part row, with the key at a chosen length."""
    cand = f"fixture-cand-{i:04d}"
    def opt(n, tag):
        base = f"Review the {tag} record for this {i} cycle"
        return (base + " " + "and confirm the totals with the team" * 3)[:n].strip()
    payload_row = {
        "cand_id": cand, "cluster": "entrepreneurship", "level": "District",
        "instructionalArea": "Operations",
        "performanceIndicator": "Explain the nature of operations",
        "difficulty": "easy", "answer_letter": "A",
        "option_length_band": [15, 120],
    }
    part_row = dict(payload_row)
    del part_row["answer_letter"], part_row["option_length_band"]
    part_row.update({
        "question": STEM.format(f"number {i} scheduling"),
        "options": {"A": opt(key_len, f"first {i}"), "B": opt(runner_len, f"second {i}"),
                    "C": opt(runner_len - 4, f"third {i}"),
                    "D": opt(runner_len - 8, f"fourth {i}")},
        "answer": "A",
        "explanation": EXPL.format(f"number {i} operating"),
    })
    return payload_row, part_row


# rows 0-1 are key-longest (0 is decisive at +29, 1 is soft at +6); 2-7 are clean.
spec = [(81, 52), (58, 52), (40, 62), (40, 62), (40, 62), (40, 62), (40, 62), (40, 62)]
pairs = [row(i, k, r) for i, (k, r) in enumerate(spec)]

with tempfile.TemporaryDirectory() as tmp:
    payload = Path(tmp) / "payload.json"
    part = Path(tmp) / "part1.json"
    payload.write_text(json.dumps([p for p, _ in pairs]), encoding="utf-8")
    part.write_text(json.dumps([a for _, a in pairs]), encoding="utf-8")

    def run(*extra):
        return subprocess.run(
            [sys.executable, str(GEN / "check_authored.py"), "--payload", str(payload),
             "--part", str(part), *extra], capture_output=True, text=True)

    def repair_ids(stdout: str) -> list:
        """The ids in the key-longest repair LIST -- not every id the report mentions.

        A row also appears in the `soft` roll-up above, so a bare substring test reads
        a listed row where there is none. Read the block, between its header and the
        repair-scope line that closes it.
        """
        out, inside = [], False
        for line in stdout.splitlines():
            if line.startswith("  repair ") and "item(s)" in line and "scope" not in line:
                inside = True
            elif inside and line.startswith("  repair scope:"):
                break
            elif inside and line.strip():
                out.append(line.split()[0])
        return out

    r = run()
    check("end-to-end: the batch is gate-clean, so the length block runs at all",
          "key-is-longest 2/8" in r.stdout,
          "\n          ".join(l for l in r.stdout.splitlines() if "FAIL" in l) or r.stdout[-400:])
    check("end-to-end: an ORDINARY run prints the decisive line -- no flag needed",
          "of those, 1 decisive (key >=20ch clear of every distractor)" in r.stdout,
          "\n          ".join(l for l in r.stdout.splitlines() if "decisive" in l))
    check("end-to-end: the decisive count is printed as a rate over this batch",
          "1/8 (12.5%) of this batch, against 1.3% of the committed bank" in r.stdout,
          "\n          ".join(l for l in r.stdout.splitlines() if "decisive" in l))

    r = run("--list-key-longest")
    check("end-to-end: rate-only, the budget is 0 and the decisive row is NOT listed",
          "repair 0 item(s)" in r.stdout and repair_ids(r.stdout) == [],
          f"listed {repair_ids(r.stdout)}")

    r = run("--list-key-longest", "--min-margin", "20")
    check("end-to-end: with the floor, ONLY the decisive row is listed, with its margin",
          "repair 1 item(s): 0 to reach 25% plus every margin >= 20ch" in r.stdout
          and repair_ids(r.stdout) == ["fixture-cand-0000"]
          and "fixture-cand-0000  key A 81ch vs runner-up 52ch (+29)" in r.stdout,
          f"listed {repair_ids(r.stdout)}")
    check("end-to-end: the floor row is scoped to the part file that holds it",
          "part1.json  (1): fixture-cand-0000" in r.stdout,
          "\n          ".join(l for l in r.stdout.splitlines() if "repair scope" in l))

    r = run("--min-margin", "20")
    check("end-to-end: --min-margin without --list-key-longest is refused, exit 2",
          r.returncode == 2 and "--min-margin requires --list-key-longest" in r.stderr,
          f"exit={r.returncode} {r.stderr.strip().splitlines()[-1:]}")

    r = run("--list-key-longest", "--min-margin", "-1")
    check("end-to-end: a negative floor is refused, exit 2",
          r.returncode == 2 and "--min-margin must be non-negative" in r.stderr,
          f"exit={r.returncode} {r.stderr.strip().splitlines()[-1:]}")

# ---------------------------------------------------------------------------
# 8. THE REFUSALS HAPPEN BEFORE THE PAYLOAD IS READ. A mistyped command must not
#    look like it ran a filter, and must not depend on a readable payload to say so.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    ghost = Path(tmp) / "does-not-exist.json"
    r = subprocess.run(
        [sys.executable, str(GEN / "check_authored.py"), "--payload", str(ghost),
         "--part", str(ghost), "--min-margin", "20"],
        capture_output=True, text=True)
    check("the CLI refuses on argument shape, not on reading a payload first",
          r.returncode == 2 and "--min-margin requires --list-key-longest" in r.stderr,
          f"exit={r.returncode}")

# ---------------------------------------------------------------------------
# 9. EVERY SLICE PLAN FROM §10-12 PASSES THE FLOOR. Half the fix is inert if the
#    command blocks the slices are actually driven from never pass it -- which is
#    exactly what shipped in the first cut of this change.
# ---------------------------------------------------------------------------
PLANS = GEN.parents[1] / "plans"
owed = ["10-12-entrepreneurship-association", "10-13-entrepreneurship-icdc",
        "10-14-marketing-district", "10-15-marketing-association",
        "10-16-marketing-icdc"]
missing = []
for stem in owed:
    text = (PLANS / f"{stem}-slice.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if "--list-key-longest" in line and "--min-margin" not in line:
            missing.append(f"{stem}: {line.strip()}")
check(f"all {len(owed)} un-run slice plans gate with --min-margin",
      not missing, "\n          ".join(missing) if missing else "")

# ---------------------------------------------------------------------------
# What this fixture does NOT check -- state it, don't imply coverage.
#
#  * That the decisive count means the same thing as `audit_tells.py`'s decisive
#    band. It does by construction (margin >=20 implies the key IS longest, so
#    scoping to `offenders` loses nothing), but the two tools measure different
#    POPULATIONS -- this one reads pre-repair candidates, `audit_tells` reads
#    committed rows -- and nothing here reconciles the rates.
#  * That a flagged row is worth repairing. That is a human read, and over-scrubbing
#    is its own defect.
#  * The rest of `check_authored`'s report. Only the two lines this change touches.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
