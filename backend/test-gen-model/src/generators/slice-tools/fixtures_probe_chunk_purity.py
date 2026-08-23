"""Issue #92 fixtures: one unproven area per probe chunk in `plan_slice.py`.

THE DEFECT. `chunk()` quarantines areas no closed plan-10 slice has authored into
probe chunks that run ALONE, before the rest of the slice launches in parallel, so
their gate numbers can be read against §10-4's baselines. Its own docstring says why:

    a mixed chunk cannot be read, because a miss cannot be attributed to the new ground

But the probe cohort was packed by `_pack`, whose whole job is bagging small areas
together until the batch fills. So the invariant the code held was the one it wrote
down -- an unproven area is never packed alongside a PROVEN one -- and not the one it
needed: two unproven areas that fit under AGENT_MAX shared a chunk and produced ONE
set of gate numbers for TWO questions. §10-11 probed risk_management and
channel_management exactly that way (32 items, one chunk) and entered both in
PROVEN_AREAS on a read that was never specific to either; the caveat that slice wrote
next to `channel_management` is the tell -- the slice could not report a per-area
result because the tool did not produce one.

The decision the probe feeds is per-area. `PROVEN_AREAS` is a set of areas, added to
one at a time, so a shared read cannot be defended per area.

WHY A FIXTURE AND NOT A COMMENT. Fourth guard in this toolchain to be wrong while the
comment above it described the correct behaviour (#76 GATED_FIELDS, #88 the rule-5
predicate, #89 the COPY THROUGH lookup, now this). The §10-11 rule stands: when a
gate's behaviour is asserted in a comment, assert it in a fixture too.

NON-VACUITY: the §10-11 case is replayed against the OLD packer as well as the new
one, so a regression that routes the probe cohort back through `_pack` fails here
rather than passing for the wrong reason.

WHY SECTIONS 4b AND 5 BUILD THEIR OWN SLICE (issue #207). They used to read the live
`PROVEN_AREAS` and the committed bank, and assert that marketing's three slices each
emit one probe chunk naming `Marketing-Information Management`. That area was entered
in `PROVEN_AREAS` when §10-14 closed -- the documented, intended end state -- and it
was the LAST unproven area in plan 10, so `chunk()` emits zero probe chunks and no
input could satisfy those assertions any more: five permanently red checks for eleven
days. The old comment anticipated two causes for the census going quiet ("the area was
entered without its slice closing", "`is_proven` stopped matching") and not the third,
which is the one that happened: the area was entered BECAUSE its slice closed.

The lesson is narrower than "don't read live state". Section 4a still reads it, and
should. What cannot be an ASSERTION is a property of live state that the project is
actively working to make false -- an unproven area is a to-do list, and a fixture that
fails when the list empties has pinned the wrong thing. So the report shape, which is
what earns this file its place for the next cluster that adds an extra area, is now
driven from a hand-built slice; the live sweep stays, reports its own coverage, and
cannot go red for succeeding.

Run it:  python3 backend/test-gen-model/src/generators/slice-tools/fixtures_probe_chunk_purity.py
Exit 0 = green. There is no test runner in this repo; this is a standalone script.

Paths are derived from `__file__`, NOT hardcoded -- an absolute path into a session
scratchpad, or into `/Users/.../GNS DECA APP` (the pre-rename directory, now DECK-APP),
dies with the session or the rename and takes the file with it. #157 swept the last
three out of this toolchain; don't reintroduce one.
"""
import io
import sys
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
import plan_slice as ps  # noqa: E402
from build_prompt import AGENT_MAX  # noqa: E402
from pi_deficit import build_deficit  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail else ""))


def rows(*pairs):
    """Minimal `area_rows` output: (area, concept items). Only what `chunk()` reads."""
    return [{"area": a, "concept": n, "easy": n, "medium": 0, "hard": 0, "pis": 1,
             "core": None} for a, n in pairs]


def shape(chunks):
    return [(c["items"], [a for a, _ in c["areas"]], c["probe"]) for c in chunks]


def probes(chunks):
    return [c for c in chunks if c["probe"]]


print("Issue #92 -- one unproven area per probe chunk\n")

# ---------------------------------------------------------------------------
# 1. THE §10-11 CASE, replayed. Two unproven areas that fit under AGENT_MAX
#    together. This is the exact input that shipped one chunk for two areas.
# ---------------------------------------------------------------------------
print("two small unproven areas (the §10-11 shape):")
TWO_NEW = rows(("Risk Management", 25), ("Channel Management", 7),
               ("Operations", 60), ("Marketing", 30))
saved = ps.PROVEN_AREAS
ps.PROVEN_AREAS = saved - {"risk_management", "channel_management"}
try:
    got = ps.chunk(TWO_NEW)
    # Graded INSIDE the patch: `is_proven` reads the module-level set, so asking it
    # after the restore asks a different question than the one `chunk()` answered.
    leaked = [a for c in probes(got) for a, _ in c["areas"] if ps.is_proven(a)]
finally:
    ps.PROVEN_AREAS = saved

check("each probe chunk names exactly ONE area",
      all(len(c["areas"]) == 1 for c in probes(got)),
      f"probe chunks: {[[a for a, _ in c['areas']] for c in probes(got)]}")
check("both unproven areas still get a chunk",
      sorted(c["areas"][0][0] for c in probes(got))
      == ["Channel Management", "Risk Management"],
      f"{shape(got)}")
check("the probe chunks carry their areas' full item counts",
      sorted(c["items"] for c in probes(got)) == [7, 25],
      "a probe that drops items reads clean for the wrong reason")
check("probe chunks are ordered FIRST",
      [c["probe"] for c in got] == sorted((c["probe"] for c in got), reverse=True),
      "§10-8 §3 sequencing: read the probe before the rest launches in parallel")
check("no PROVEN area is packed into a probe chunk",
      not leaked,
      f"leaked into quarantine: {leaked}" if leaked
      else "the invariant the old docstring DID hold — it survives the fix")

# Non-vacuity: the old packer, run on the same rows, merges the two.
old_probe = ps._pack(rows(("Risk Management", 25), ("Channel Management", 7)))
check("REGRESSION ANCHOR: `_pack` on the same cohort yields ONE chunk of 2 areas",
      len(old_probe) == 1 and len(old_probe[0]["areas"]) == 2,
      f"_pack => {shape(old_probe)} — the defect, reproduced")
check("`_pack` cannot be handed the probe cohort any more",
      "probe" not in ps._pack.__code__.co_varnames[:ps._pack.__code__.co_argcount],
      "the flag is gone, so there is no argument that routes probes through bagging")

# ---------------------------------------------------------------------------
# 2. THE CEILING STILL BINDS. Area-purity is not a licence to emit an over-cap
#    chunk -- build_prompt.py refuses those. A big unproven area splits into
#    same-area pieces, which is a sum to read, not an ambiguity.
# ---------------------------------------------------------------------------
print("\none unproven area over the band ceiling:")
saved = ps.PROVEN_AREAS
ps.PROVEN_AREAS = saved - {"risk_management"}
try:
    big = ps.chunk(rows(("Risk Management", 220), ("Operations", 60)))
finally:
    ps.PROVEN_AREAS = saved
bp = probes(big)
check(f"splits into pieces, none over AGENT_MAX ({AGENT_MAX})",
      len(bp) > 1 and all(c["items"] <= AGENT_MAX for c in bp),
      f"{[c['items'] for c in bp]}")
check("every piece is the SAME area", {a for c in bp for a, _ in c["areas"]} == {"Risk Management"})
check("the pieces sum to the area's items", sum(c["items"] for c in bp) == 220)
check("the pieces are near-equal (no runt piece)",
      max(c["items"] for c in bp) - min(c["items"] for c in bp) <= 1,
      f"{[c['items'] for c in bp]}")

# ---------------------------------------------------------------------------
# 3. THE PROVEN SIDE IS UNCHANGED. Packing small areas together is the point
#    there; a fix that "tidied" both cohorts would cost an agent per area on
#    every slice for nothing.
# ---------------------------------------------------------------------------
print("\nthe proven cohort:")
allproven = rows(("Operations", 20), ("Marketing", 18), ("Economics", 22),
                 ("Selling", 15))
pc = ps.chunk(allproven)
check("four small proven areas share ONE chunk",
      len(pc) == 1 and len(pc[0]["areas"]) == 4 and pc[0]["items"] == 75,
      f"{shape(pc)}")
check("nothing on the proven side is tagged probe", not probes(pc))
check("a zero-item area is dropped, not emitted as an empty chunk",
      not ps.chunk(rows(("Operations", 0))),
      "true on both sides — `_pack_probe` keeps `_pack`'s skip")

# ---------------------------------------------------------------------------
# 4a. THE REAL SLICES. Conservation is the property that matters most: chunking
#     must not invent or lose items. READ THE PRINTED ITEM COUNT -- this arm is
#     VACUOUS today (issue #207): plan 10 is complete, so every one of the 15
#     committed slices has a concept deficit of 0 and `chunk()` returns nothing
#     at all. It is kept because it costs nothing and is load-bearing again the
#     moment a campaign re-opens a deficit; the coverage it USED to carry moved
#     to 4b, which builds its own cohort and cannot go quiet.
# ---------------------------------------------------------------------------
print("\nall 15 committed cluster x level slices:")
bad = []
probe_seen = []
live_items = 0
for cluster in ("finance", "pbm", "marketing", "entrepreneurship", "hospitality"):
    for level in ("District", "Association", "ICDC"):
        wo = build_deficit(cluster, level, split="even")
        areas = ps.area_rows(wo)
        chunks = ps.chunk(areas)
        want = Counter({a["area"]: a["concept"] for a in areas if a["concept"]})
        got_c = Counter()
        for c in chunks:
            for a, n in c["areas"]:
                got_c[a] += n
        total = wo["meta"]["need_easy"] + wo["meta"]["need_medium"]
        live_items += total
        tag = f"{cluster}/{level}"
        if got_c != want:
            bad.append(f"{tag}: per-area items drift {got_c - want} / {want - got_c}")
        if sum(c["items"] for c in chunks) != total:
            bad.append(f"{tag}: chunk items != deficit ({sum(c['items'] for c in chunks)} vs {total})")
        if any(c["items"] > AGENT_MAX for c in chunks):
            bad.append(f"{tag}: chunk over the {AGENT_MAX} ceiling")
        for c in probes(chunks):
            if len(c["areas"]) > 1:
                bad.append(f"{tag}: probe chunk spans {[a for a, _ in c['areas']]}")
            else:
                probe_seen.append((tag, c["areas"][0][0], c["items"]))
check("items conserved per area, ceiling held, every probe chunk area-pure",
      not bad,
      "\n          ".join(bad[:5]) if bad
      else f"15 slices, {live_items} concept items, {len(probe_seen)} probe chunk(s), "
           f"0 violations")
# NOT a check: an assertion that fires when the bank is FULL is issue #207 itself --
# a permanently red file that stops being a signal. State the coverage instead.
print("          NOTE: live deficit is 0 concept items — plan 10 is complete, so the"
      if not live_items else
      f"          NOTE: {live_items} live concept items across the 15 slices.")
if not live_items:
    print("          sweep above exercised nothing on real data. 4b/5 carry it now.")

# ---------------------------------------------------------------------------
# 4b. THE SAME SWEEP ON A SYNTHETIC SLICE. §10-14's marketing/District shape --
#     one unproven area (27 items) beside five proven ones -- rebuilt by hand so
#     the probe census survives the last real probe closing. `is_proven` reads
#     the module-level set, so grade INSIDE the patch, as section 1 does.
# ---------------------------------------------------------------------------
print("\na synthetic slice with one unproven area (§10-14's shape):")
NEW_AREA = "Marketing-Information Management"
SLICE_ROWS = rows((NEW_AREA, 27), ("Marketing", 88), ("Selling", 64),
                  ("Promotion", 41), ("Customer Relations", 22), ("Economics", 19))
saved = ps.PROVEN_AREAS
ps.PROVEN_AREAS = saved - {"marketing_information_management"}
try:
    sl = ps.chunk(SLICE_ROWS)
    sl_probes = probes(sl)
finally:
    ps.PROVEN_AREAS = saved
check("the slice probes exactly one area, and it is the unproven one",
      len(sl_probes) == 1 and sl_probes[0]["areas"] == [(NEW_AREA, 27)],
      f"{[[a for a, _ in c['areas']] for c in sl_probes]}")
check("the probe is chunk 1", bool(sl) and sl[0]["probe"], f"{shape(sl)}")
sl_want = Counter({a: n for a, n in ((r["area"], r["concept"]) for r in SLICE_ROWS)})
sl_got = Counter()
for c in sl:
    for a, n in c["areas"]:
        sl_got[a] += n
check("items conserved per area", sl_got == sl_want, f"{sl_got - sl_want} / {sl_want - sl_got}")
check(f"no chunk over the {AGENT_MAX}-item ceiling",
      all(c["items"] <= AGENT_MAX for c in sl), f"{[c['items'] for c in sl]}")

# ---------------------------------------------------------------------------
# 5. THE REPORT SAYS WHAT IT IS READING. The probe read is per CHUNK, so both
#    output modes must name chunk -> area rather than listing areas and chunk
#    numbers separately -- the plan doc is copied out of `--md` verbatim.
#
#    `main()` builds its own work order from the committed bank, and that bank is
#    now full, so it is stubbed here alongside PROVEN_AREAS (issue #207). Both
#    stubs are needed and neither is sufficient: an unproven area with no deficit
#    rows produces no chunk, and a deficit whose areas are all proven produces no
#    PROBE chunk. The numbers below are §10-14's real ones.
# ---------------------------------------------------------------------------
print("\nthe --md and text reports:")

STUB_WO = {
    "rows": [{"instructionalArea": a, "performanceIndicator": f"{a} PI {i}",
              "need_easy": n, "need_medium": 0, "need_hard": 0, "need_total": n,
              "is_core": True}
             for i, (a, n) in enumerate((r["area"], r["concept"]) for r in SLICE_ROWS)],
    "meta": {"floor": "v2", "need_easy": sum(r["concept"] for r in SLICE_ROWS),
             "need_medium": 0, "need_hard": 21,
             "need_total": sum(r["concept"] for r in SLICE_ROWS) + 21,
             "pis_needing_work": len(SLICE_ROWS), "hard_met_by_medium": 0},
}


def run_cli(*argv):
    """Run `plan_slice.main()` against the stubbed slice, capturing stdout."""
    saved_argv, saved_bd, saved_pa = sys.argv, ps.build_deficit, ps.PROVEN_AREAS
    sys.argv = ["plan_slice.py", *argv]
    ps.build_deficit = lambda *a, **k: STUB_WO
    ps.PROVEN_AREAS = saved_pa - {"marketing_information_management"}
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            ps.main()
    finally:
        sys.argv, ps.build_deficit, ps.PROVEN_AREAS = saved_argv, saved_bd, saved_pa
    return buf.getvalue()


md = run_cli("marketing", "District", "--md")
txt = run_cli("marketing", "District")
check("--md lists the probe chunk on its own line, with its area and count",
      f"- chunk 1 — {NEW_AREA} (27 items)" in md,
      next((ln for ln in md.splitlines() if ln.startswith("- chunk")), "<no chunk line>"))
check("--md says one area per chunk", "**one area per chunk**" in md)
check("the text report lists probe chunks under an ONE PER CHUNK heading",
      "quarantined ONE PER CHUNK:" in txt
      and NEW_AREA in txt.split("ONE PER CHUNK:")[1])
check("the text report tells the reader to gate EACH chunk",
      "read EACH chunk's" in txt)
check("no impurity warning fires on a clean plan",
      "span more than one unproven area" not in txt)
check("...and neither does the ceiling warning", "over the" not in txt.split("UNPROVEN")[0]
      or "band ceiling" not in txt)

# The warning is the live guard, so prove it can actually fire: hand `main()` a
# chunker that returns the old shape. A guard that never fires in either direction
# is #76's GATED_FIELDS again.
saved_chunk = ps.chunk
ps.chunk = lambda areas: [{"areas": [("Risk Management", 20), ("Channel Management", 12)],
                           "items": 32, "probe": True}]
try:
    dirty = run_cli("marketing", "District")
finally:
    ps.chunk = saved_chunk
check("the impurity WARNING fires on a two-area probe chunk",
      "WARNING: probe chunk(s) 1 span more than one unproven area" in dirty
      and "issue #92" in dirty,
      next((ln.strip() for ln in dirty.splitlines() if "WARNING" in ln), "<no warning>"))
#    trade was argued in the issue, not measured.
#  * Whether PROVEN_AREAS is ACCURATE. `is_proven` is a set lookup -- an area entered
#    before its slice closed reads proven here and is never quarantined at all. The
#    comment block above the set is the only record of what each entry was earned by.
#  * channel_management's §10-11 evidence, which this fix does not retroactively
#    supply. It stays entered on a shared read; §10-14 is where it carries weight.
#  * ANY of this against real work-order data, as of #207. Every committed slice's
#    concept deficit is 0 (plan 10 is complete), so 4a sweeps 15 empty slices and 4b
#    and 5 run on rows built here. The chunking rules are exercised; `area_rows`'
#    reading of a REAL deficit row is not, and would go unnoticed if `pi_deficit`
#    changed shape. The next campaign to re-open a deficit gets that back for free.
# ---------------------------------------------------------------------------
print()
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"  {len(results) - n_fail} passed / {n_fail} failed")
sys.exit(1 if n_fail else 0)
