"""Issue #175's fix, pinned -- the C1/C2 hard route, derived rather than stamped.

THE DEFECT. `build_area` assigned every hard row a route (C1 chained computation / C2
two near-correct options) through a cluster allow-list, `C1_CLUSTERS = {"finance",
"pbm"}`, which short-circuited to C2 BEFORE the curated PI pool was ever read. The
allow-list was written when only those two clusters HAD a curated file. The other three
grew one and the guard stayed, so on marketing / entrepreneurship / hospitality the
"assignment" was a constant that described nothing about the row it sat on.

Measured over every plan-10 hard payload at the time of the fix: 95 of 95 rows on those
three clusters are in their cluster's curated pool -- the pool says C1 on all of them --
while the allow-list said C2 on all of them, and the authors realised C1 (§10-11 all 19,
§10-13 all 19, §10-14 20 of 21). The derivation the allow-list was hiding is the one that
agrees with the authors. Four slices of "the author refused the assignment" indict the
short-circuit, not the pool.

THE FIELD IS NOT AN AUTHORING INSTRUCTION AND MUST NOT BECOME ONE. Nothing renders
`route` into a prompt and no gate scores it, so printing it on a row line would state an
assignment nothing measures -- §10-10's `key_length_rank` shape with the fix inverted.
`authoring-hard-bare.txt` used to claim "Your payload tells you which route each row is
assigned", pointing at a field the prompt does not print; that line is gone. The field's
real consumers are the payload record and `build_hard_verify`'s stage-2 blind-solver
scoping, and both need it TRUE, not obeyed. Section 4 holds that line.

NO OVERRIDE. `--route` is gone from both builders. A route is a property of the PI, so
the place to change one is `data/pi-pools/<cluster>-computational.json`, where the change
persists and is reviewable; the flag's only measured use (§10-6/§10-7, forced all-C1)
produced a worse answer than the derivation it overrode. Section 2 keeps it gone.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_hard_route_derivation.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, never hardcoded.
"""

import inspect
import json
import sys
from pathlib import Path

GEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GEN))

import author_hard as ah                                              # noqa: E402
import build_area as ba                                               # noqa: E402
import build_prompt as bp                                             # noqa: E402
import pi_deficit as pd                                               # noqa: E402

POOL_DIR = GEN.parent.parent / "data" / "pi-pools"
BRIEF = GEN.parent / "prompts" / "authoring-hard-bare.txt"

# The three clusters the allow-list excluded. finance/pbm were inside it and are the
# control: their routing is unchanged by the fix.
FIXED = ("marketing", "entrepreneurship", "hospitality")
OLD_ALLOW_LIST = {"finance", "pbm"}

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print("  ok   %s" % label)
    else:
        print("  FAIL %s%s" % (label, ("  -- " + detail) if detail else ""))
        FAILURES.append(label)


def pool_entries(cluster):
    return json.loads((POOL_DIR / ("%s-computational.json" % cluster)).read_text("utf-8"))


def old_route(cluster, area, pi, computational):
    """The derivation as it stood before #175 -- the allow-list in front of the pool."""
    if cluster not in OLD_ALLOW_LIST:
        return "C2"
    if computational is not None:
        return "C1" if (pd.slug(area), pi) in computational else "C2"
    return "C1" if pd.slug(area) in ah.C1_AREAS else "C2"


# --------------------------------------------------------------------------------------
# 1. The pool decides, on every cluster -- and the old allow-list is what it disagrees
#    with. Read off the COMMITTED pool files, not a slice's output.
# --------------------------------------------------------------------------------------

def section1():
    print("\n1. every curated PI routes C1 now, and routed C2 under the allow-list")

    for cluster in FIXED:
        comp = ah.load_computational_pis(cluster)
        entries = pool_entries(cluster)
        check("%s: pool loads (%d entries)" % (cluster, len(entries)),
              comp is not None and len(entries) > 0)

        new = [ah.hard_route(cluster, e["area"], e["pi"], comp) for e in entries]
        old = [old_route(cluster, e["area"], e["pi"], comp) for e in entries]
        check("%s: all %d curated PIs derive C1" % (cluster, len(entries)),
              set(new) == {"C1"},
              "%d of %d came back C2" % (new.count("C2"), len(new)))
        # NON-VACUITY: the fix has to MOVE these rows, or it is asserting the status quo.
        check("%s: the allow-list called all %d of them C2" % (cluster, len(entries)),
              set(old) == {"C2"},
              "old derivation already agreed on %d row(s)" % old.count("C1"))

    # And the pool is a real discriminator, not a blanket C1: a PI outside it is C2.
    comp = ah.load_computational_pis("marketing")
    check("a PI outside the pool is C2",
          ah.hard_route("marketing", "Promotion",
                        "Explain the nature of direct marketing channels", comp) == "C2")
    check("a real pool PI is C1",
          ah.hard_route("marketing", "Pricing", "Calculate markup based on cost", comp) == "C1")

    # The two clusters INSIDE the old allow-list must be untouched by the fix.
    for cluster in sorted(OLD_ALLOW_LIST):
        comp = ah.load_computational_pis(cluster)
        entries = pool_entries(cluster)
        same = all(ah.hard_route(cluster, e["area"], e["pi"], comp)
                   == old_route(cluster, e["area"], e["pi"], comp) for e in entries)
        check("%s: routing unchanged by the fix (control)" % cluster, same)

    # A cluster with no pool file falls back to the area list, exactly as before.
    check("no pool file -> C1_AREAS fallback still routes",
          ah.load_computational_pis("nosuchcluster") is None
          and ah.hard_route("nosuchcluster", "Financial Analysis", "anything") == "C1"
          and ah.hard_route("nosuchcluster", "Communication Skills", "anything") == "C2")


# --------------------------------------------------------------------------------------
# 2. There is no override, in either builder.
# --------------------------------------------------------------------------------------

def section2():
    print("\n2. --route is gone and build_chunk takes no route_override")

    for mod in (ah, ba):
        src = inspect.getsource(mod)
        check("%s: no --route argument" % mod.__name__, '"--route"' not in src,
              "the flag is back")
    check("build_chunk has no route_override parameter",
          "route_override" not in inspect.signature(ba.build_chunk).parameters)
    check("build_payload has no route parameter",
          "route" not in inspect.signature(ah.build_payload).parameters)
    check("C1_CLUSTERS is gone", not hasattr(ah, "C1_CLUSTERS"),
          "the allow-list is still defined and something may read it")


# --------------------------------------------------------------------------------------
# 3. ONE definition. build_area imports it; it does not keep a copy.
# --------------------------------------------------------------------------------------

def section3():
    print("\n3. one derivation, imported rather than copied")

    check("build_area.hard_route IS author_hard.hard_route", ba.hard_route is ah.hard_route)
    check("build_area defines no C1_AREAS of its own",
          not hasattr(ba, "C1_AREAS") or ba.C1_AREAS is ah.C1_AREAS,
          "build_area has a second, independent area list")
    check("build_area.load_computational_pis IS author_hard's",
          ba.load_computational_pis is ah.load_computational_pis)

    # pi_deficit keeps its OWN loader, and the one difference is deliberate: finance is
    # closed under the legacy predicate, so the DEFICIT must not re-read the pool, while
    # the ROUTER has no such constraint. Assert the divergence rather than trusting a
    # comment about it -- silently unifying them would move a closed cluster's numbers.
    check("pi_deficit returns None for finance (legacy, closed cluster)",
          pd.load_computational_pis("finance") is None)
    check("the router DOES read finance's pool",
          ah.load_computational_pis("finance") is not None)
    # Same shape everywhere else, which is the property §10-5 needs.
    for cluster in FIXED:
        check("%s: deficit and router agree on the pool" % cluster,
              pd.load_computational_pis(cluster) == ah.load_computational_pis(cluster))


# --------------------------------------------------------------------------------------
# 4. The route reaches no prompt and no gate -- the reason it is safe to derive it.
# --------------------------------------------------------------------------------------

def workorder():
    return {
        "meta": {"cluster": "marketing", "level": "District"},
        "rows": [{
            "cluster": "marketing",
            "level": "District",
            "instructionalArea": "Pricing",
            "performanceIndicator": "Calculate markup based on cost",
            "is_core": True,
            "is_computational": True,
            "need_easy": 0,
            "need_medium": 0,
            "need_hard": 1,
        }],
    }


def section4():
    print("\n4. `route` is on the payload, in no prompt, and in no gate")

    rows = ba.build_chunk(workorder(), areas=None, tiers=["hard"], seed=505,
                          avoid_scope="area", avoid_cap=0)
    check("the hard row carries a route", bool(rows) and rows[0].get("route") in ("C1", "C2"))
    check("and it is C1 -- this PI is in marketing's curated pool",
          rows[0].get("route") == "C1", "got %r" % rows[0].get("route"))

    rendered = bp.compact(rows, show_area=False)
    check("the rendered row does not print the route",
          "ROUTE" not in rendered.upper() and "C1" not in rendered and "C2" not in rendered,
          rendered.strip())

    check("route is not in build_prompt.GATED_FIELDS", "route" not in bp.GATED_FIELDS)
    check("check_authored does not score `route`", "route" not in bp.gate_scored_fields())

    # The brief's claim about an assignment the prompt never prints, gone.
    brief = BRIEF.read_text("utf-8")
    check("the brief no longer says the payload assigns a route",
          "payload tells you which route" not in brief)
    check("the brief still describes both routes",
          "ROUTE C1" in brief and "ROUTE C2" in brief)


def main():
    print(__doc__.strip().splitlines()[0])
    section1()
    section2()
    section3()
    section4()
    print()
    if FAILURES:
        print("FAILED (%d): %s" % (len(FAILURES), "; ".join(FAILURES)))
        return 1
    print("all green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
