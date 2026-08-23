"""Issue #76's guard, pinned -- and the #139 drift that first made it fire.

THE DEFECT. `build_prompt.GATED_FIELDS` maps every payload field `check_authored.py`
scores to the token that must appear in the RENDERED ROWS, so an author is never graded
on an assignment it was not shown. #76 made the map derive from the gate by AST-parsing
`check_authored.py`, and `assert_map_matches_gate()` fails the build when the two
disagree in either direction. **It was never pinned by a fixture.**

#139 then made it fire for real. `assigned_option_targets()` reads `option_target_lens`
(free-rank rows) and `distractor_target_lens` (ranked rows) off every row it scores, to
decide whether a length soft was caused by the ladder's own assignment. Both fields sat
in `ADVISORY_FIELDS` -- "the gate does not read them" -- which had stopped being true.
The guard caught it at §10-14's first prompt build after #139 landed, which is precisely
the job #76 gave it. `ADVISORY_FIELDS` is now empty.

THE DIRECTION IS BACKWARDS FROM #76 AND THEY STILL BELONG IN THE MAP. These two are read
to SUPPRESS a soft, not to grade the author, so omitting one cannot make a compliant
author look non-compliant -- the harm #76 was about. But `assignment_caused_softs` only
defers when the author wrote the key WITHIN `TARGET_TOLERANCE` OF ITS ASSIGNED TARGET,
and an author never shown the number cannot meet that condition. Drop the render and the
row keeps a soft its own ladder assignment caused: #76's failure mode one step removed,
"denied a deferral it was never given the chance to earn". Same 46 rows, same cause.

WHY A FIXTURE. #88's rule -- when a gate's behaviour is asserted in a comment, assert it
in a fixture too. The map's correctness now rests on a claim about payload SHAPES that
was measured once, by hand, in a session: that free-rank rows carry `option_target_lens`
only and ranked rows carry `distractor_target_lens` only, so the per-row `is None` skip
in `assert_assignments_rendered` resolves the right field without the precedence dance
`_length_assignment()` needs. Section 2 holds `build_chunk` to that. If a future payload
ever carried both, one of the two tokens would be demanded on a row that never renders
it, and every prompt build would fail -- loudly, but for a reason no comment explains.

NON-VACUITY. Section 1 pairs the clean baseline with four drift directions that must each
fire, so a guard that has quietly become unconditional fails here instead of passing for
the wrong reason. Section 3 renders real rows of BOTH shapes through the real row
renderer and then re-checks with the length render stripped, so "the token is present" is
proven to be a fact about the rows rather than about the legend -- the exact confusion
`assert_assignments_rendered`'s own docstring records as having passed a whole-prompt
check once.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_gated_fields_map.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, never hardcoded.
"""

import copy
import sys
from pathlib import Path

GEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GEN))

import build_area                                                    # noqa: E402
import build_prompt as bp                                            # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print("  ok   %s" % label)
    else:
        print("  FAIL %s%s" % (label, ("  -- " + detail) if detail else ""))
        FAILURES.append(label)


# --------------------------------------------------------------------------------------
# A synthetic work order. Self-contained: the fixture must not depend on a slice's
# untracked output, and `build_chunk` only needs rows plus a cluster.
# --------------------------------------------------------------------------------------

def workorder(n_pis=8):
    return {
        "meta": {"cluster": "marketing", "level": "District"},
        "rows": [{
            "cluster": "marketing",
            "level": "District",
            "instructionalArea": "Economics",
            "performanceIndicator": "Explain the concept of economic resources (%d)" % i,
            "is_core": True,
            "is_computational": False,
            "need_easy": 1,
            "need_medium": 1,
            "need_hard": 1,
        } for i in range(n_pis)],
    }


def payload(free_rank, tiers):
    return build_area.build_chunk(
        workorder(), areas=None, tiers=tiers, seed=505,
        avoid_scope="area", avoid_cap=0, free_rank=free_rank)


# --------------------------------------------------------------------------------------
# 1. The guard is clean as shipped, and still fires in all four drift directions.
# --------------------------------------------------------------------------------------

def section1():
    print("\n1. assert_map_matches_gate -- baseline and the four drifts")

    try:
        bp.assert_map_matches_gate()
        check("shipped map agrees with check_authored.py", True)
    except SystemExit as e:
        check("shipped map agrees with check_authored.py", False, str(e).replace("\n", " "))

    def fires(label, mutate, expect):
        saved_g, saved_a = dict(bp.GATED_FIELDS), bp.ADVISORY_FIELDS
        mutate()
        try:
            bp.assert_map_matches_gate()
            check(label, False, "no fire -- the guard is disarmed")
        except SystemExit as e:
            check(label, expect in str(e), "fired, but not with %r" % expect)
        finally:
            bp.GATED_FIELDS.clear()
            bp.GATED_FIELDS.update(saved_g)
            bp.ADVISORY_FIELDS = saved_a

    # The two #139 fields, dropped from the map -- the state that broke §10-14's build.
    fires("drops option_target_lens -> fires",
          lambda: bp.GATED_FIELDS.pop("option_target_lens"),
          "scored by the gate, unmapped here: option_target_lens")
    fires("drops distractor_target_lens -> fires",
          lambda: bp.GATED_FIELDS.pop("distractor_target_lens"),
          "scored by the gate, unmapped here: distractor_target_lens")
    # The tempting wrong fix: silence the guard by calling the field advisory again.
    # ADVISORY_FIELDS is itself a claim about the gate, so this must NOT be an escape.
    fires("re-declaring AIM advisory -> fires",
          lambda: setattr(bp, "ADVISORY_FIELDS", ("option_target_lens",)),
          "called advisory, now scored:")
    # The other direction: the map advertising coverage the gate no longer has.
    fires("mapping a field the gate never scores -> fires",
          lambda: bp.GATED_FIELDS.__setitem__("not_a_real_field", "X="),
          "mapped here, no longer scored:     not_a_real_field")


# --------------------------------------------------------------------------------------
# 2. The shape claim the map now rests on, held against the real emitter.
# --------------------------------------------------------------------------------------

RANKED_ONLY = ("key_length_rank", "key_target_len", "distractor_target_lens", "max_top_gap")
FREE_ONLY = ("key_may_be_longest", "longest_letter", "option_target_lens")


def section2():
    print("\n2. the two payload shapes are disjoint (build_area.build_chunk)")

    free = payload(free_rank=True, tiers=["easy", "medium"])
    ranked = payload(free_rank=False, tiers=["hard"])
    check("both shapes produced rows", bool(free) and bool(ranked))

    for name, rows, mine, theirs in (("free-rank", free, FREE_ONLY, RANKED_ONLY),
                                     ("ranked", ranked, RANKED_ONLY, FREE_ONLY)):
        have = {f for f in mine if all(r.get(f) is not None for r in rows)}
        cross = {f for f in theirs if any(r.get(f) is not None for r in rows)}
        check("%s rows carry all of %s" % (name, ", ".join(mine)),
              have == set(mine), "missing %s" % sorted(set(mine) - have))
        check("%s rows carry NONE of %s" % (name, ", ".join(theirs)),
              not cross, "also carries %s" % sorted(cross))

    # The consequence that matters: on every row, exactly one of the two #139 fields is
    # present, so `assert_assignments_rendered`'s `is None` skip is unambiguous.
    both = [r for r in free + ranked
            if (r.get("option_target_lens") is not None)
            == (r.get("distractor_target_lens") is not None)]
    check("no row carries both or neither #139 field", not both,
          "%d ambiguous row(s)" % len(both))


# --------------------------------------------------------------------------------------
# 3. The tokens are in the ROWS, and the check notices when they are not.
# --------------------------------------------------------------------------------------

def rendered_blocks(rows):
    """`blocks` as `build_prompt.main` assembles it -- group header, then the rows.

    The header is load-bearing and omitting it is not a shortcut: a single-area group
    states its `instructionalArea` ONCE in the header rather than on every row, and
    `instructionalArea` is in GATED_FIELDS. Rendering only `compact()` therefore fails
    the check for a reason that has nothing to do with the length fields under test --
    which is what the first draft of this fixture did.
    """
    areas = list(dict.fromkeys(r["instructionalArea"] for r in rows))
    mixed = len(areas) > 1
    hdr = ("INSTRUCTIONAL AREAS VARY IN THIS GROUP — copy each row's own AREA= value; "
           "do NOT stamp one area across the file"
           if mixed else
           "INSTRUCTIONAL AREA FOR EVERY ROW IN THIS GROUP: %s" % areas[0])
    return "%s\n%s" % (hdr, bp.compact(rows, show_area=mixed))


def section3():
    print("\n3. end-to-end: the render satisfies the map, and stripping it is caught")

    for name, rows, field, token in (
            ("free-rank", payload(True, ["easy", "medium"]), "option_target_lens", "AIM "),
            ("ranked", payload(False, ["hard"]), "distractor_target_lens", "distractors ~")):

        blocks = rendered_blocks(rows)
        check("%s: %r appears in the rendered ROWS" % (name, token), token in blocks)

        try:
            bp.assert_assignments_rendered(rows, blocks)
            check("%s: assert_assignments_rendered passes" % name, True)
        except SystemExit as e:
            check("%s: assert_assignments_rendered passes" % name, False,
                  str(e).replace("\n", " "))

        # NON-VACUITY. Strip the length render only. If the check still passes, it was
        # never reading these rows -- which is the whole-prompt confusion #76 hit.
        stripped = "\n".join(
            ln.split(" | %s" % token.rstrip(" ~"))[0] if token.rstrip(" ~") in ln else ln
            for ln in blocks.splitlines())
        stripped = "\n".join(
            ln.replace(token, "") for ln in stripped.splitlines())
        check("%s: stripping %r really removes it" % (name, token), token not in stripped)
        try:
            bp.assert_assignments_rendered(rows, stripped)
            check("%s: stripped render is REJECTED" % name, False,
                  "passed with the assignment missing from every row")
        except SystemExit as e:
            check("%s: stripped render is REJECTED" % name, field in str(e),
                  "rejected, but did not name %s" % field)


def main():
    print(__doc__.strip().splitlines()[0])
    section1()
    section2()
    section3()
    print()
    if FAILURES:
        print("FAILED (%d): %s" % (len(FAILURES), "; ".join(FAILURES)))
        return 1
    print("all green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
